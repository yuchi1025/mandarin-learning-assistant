import json
import os
from pathlib import Path
import random
import re
import socket
import sqlite3
import subprocess
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime

from flask import after_this_request, Flask, jsonify, render_template, request, send_file, send_from_directory
from opencc import OpenCC
from pypinyin import Style, lazy_pinyin

app = Flask(__name__)
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
RECENT_QUIZ_LIMIT = 5
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "15m")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "45"))
OLLAMA_COMMAND = os.getenv("OLLAMA_COMMAND", "ollama")
OLLAMA_AUTO_START = os.getenv("OLLAMA_AUTO_START", "1").lower() not in {"0", "false", "no"}
TTS_VOICE = os.getenv("TTS_VOICE", "Tingting")
TTS_COMMAND = os.getenv("TTS_COMMAND", "/usr/bin/say")
AI_EXPLANATION_CACHE = {}
OLLAMA_START_ATTEMPTED = False
TO_SIMPLIFIED = OpenCC("t2s")
TO_TRADITIONAL = OpenCC("s2t")
VALID_PARTS_OF_SPEECH = {
    "noun",
    "verb",
    "adjective",
    "adverb",
    "phrase",
    "expression",
    "question word",
    "conjunction",
    "modal verb",
    "time word",
    "pronoun",
    "measure word",
    "word",
}


DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "dictionary.json"
PROGRESS_DB_PATH = Path(os.getenv("PROGRESS_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "progress.db"))
PINYIN_PHRASE_OVERRIDES = {
    "不记得": "bú jì dé",
    "不記得": "bú jì dé",
    "行为": "xíng wéi",
    "行為": "xíng wéi",
    "日期": "rì qí",
    "记得": "jì dé",
    "記得": "jì dé",
}
PINYIN_OVERRIDE_PHRASES = sorted(PINYIN_PHRASE_OVERRIDES, key=len, reverse=True)


def to_sentence_pinyin(text):
    pinyin_parts = []
    index = 0
    while index < len(text):
        matched_phrase = next(
            (phrase for phrase in PINYIN_OVERRIDE_PHRASES if text.startswith(phrase, index)),
            None,
        )
        if matched_phrase:
            pinyin_parts.append(PINYIN_PHRASE_OVERRIDES[matched_phrase])
            index += len(matched_phrase)
            continue

        pinyin_parts.extend(lazy_pinyin(text[index], style=Style.TONE))
        index += 1

    pinyin_text = " ".join(pinyin_parts)
    return re.sub(r"\s+([,.!?;:，。！？；：])", r"\1", pinyin_text)


def remove_tone_marks(text):
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def split_example(example):
    chinese_text = example
    translation = ""

    if " (" in example and example.endswith(")"):
        chinese_text, english_part = example.rsplit(" (", 1)
        translation = english_part[:-1]

    return chinese_text, translation


def to_speech_text(text):
    return re.sub(r"[\"'‘’“”「」『』]", "", text).strip()


def load_dictionary():
    with DICTIONARY_PATH.open(encoding="utf-8") as dictionary_file:
        raw_entries = json.load(dictionary_file)

    entries = []
    for raw_entry in raw_entries:
        word = str(raw_entry.get("word", "")).strip()
        if not word:
            continue
        traditional = str(raw_entry.get("traditional", word)).strip() or word

        structured_examples = []
        for example in raw_entry.get("examples", []):
            chinese_text, translation = split_example(str(example))
            structured_examples.append(
                {
                    "text": chinese_text,
                    "speech_text": to_speech_text(chinese_text),
                    "pinyin": to_sentence_pinyin(chinese_text),
                    "translation": translation,
                }
            )

        pinyin = str(raw_entry.get("pinyin", "")).strip() or " ".join(lazy_pinyin(word, style=Style.TONE))
        entries.append(
            {
                "word": word,
                "traditional": traditional,
                "pinyin": pinyin,
                "english": str(raw_entry.get("english", "")).strip(),
                "part_of_speech": str(raw_entry.get("part_of_speech", "word")).strip() or "word",
                "explanation": str(raw_entry.get("explanation", "")).strip(),
                "examples": structured_examples,
                "search_pinyin": remove_tone_marks(pinyin),
            }
        )

    return entries


DICTIONARY_ENTRIES = load_dictionary()


def get_progress_connection():
    PROGRESS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(PROGRESS_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_progress_db():
    with get_progress_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL COLLATE NOCASE UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS search_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                searched_at TEXT NOT NULL,
                query TEXT NOT NULL,
                word TEXT,
                traditional TEXT,
                pinyin TEXT,
                english TEXT,
                source TEXT NOT NULL,
                mode TEXT NOT NULL
            )
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(search_events)")
        }
        if "student_id" not in columns:
            connection.execute(
                "ALTER TABLE search_events ADD COLUMN student_id INTEGER REFERENCES students(id)"
            )

        legacy_event_count = connection.execute(
            "SELECT COUNT(*) AS count FROM search_events WHERE student_id IS NULL"
        ).fetchone()["count"]
        if legacy_event_count:
            legacy_student = connection.execute(
                "SELECT id FROM students WHERE name = ?", ("Existing progress",)
            ).fetchone()
            if legacy_student is None:
                cursor = connection.execute(
                    "INSERT INTO students (name, created_at) VALUES (?, ?)",
                    ("Existing progress", datetime.now().isoformat(timespec="seconds")),
                )
                legacy_student_id = cursor.lastrowid
            else:
                legacy_student_id = legacy_student["id"]
            connection.execute(
                "UPDATE search_events SET student_id = ? WHERE student_id IS NULL",
                (legacy_student_id,),
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_events_searched_at ON search_events (searched_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_events_word ON search_events (word)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_events_student_date ON search_events (student_id, searched_at)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id),
                vocabulary_word TEXT NOT NULL,
                is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
                first_attempt_correct INTEGER NOT NULL CHECK (first_attempt_correct IN (0, 1)),
                completed_at TEXT NOT NULL,
                interaction_key TEXT NOT NULL,
                UNIQUE (student_id, interaction_key)
            )
            """
        )
        quiz_attempt_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(quiz_attempts)")
        }
        if "first_attempt_correct" not in quiz_attempt_columns:
            connection.execute("ALTER TABLE quiz_attempts ADD COLUMN first_attempt_correct INTEGER")
            connection.execute(
                "UPDATE quiz_attempts SET first_attempt_correct = is_correct WHERE first_attempt_correct IS NULL"
            )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_date ON quiz_attempts (student_id, completed_at)"
        )


def row_to_dict(row):
    return dict(row) if row else None


def parse_student_id(value):
    try:
        student_id = int(value)
    except (TypeError, ValueError):
        return None
    return student_id if student_id > 0 else None


def list_students():
    init_progress_db()
    with get_progress_connection() as connection:
        return [
            row_to_dict(row)
            for row in connection.execute("SELECT id, name FROM students ORDER BY name COLLATE NOCASE, id")
        ]


def get_student(student_id):
    student_id = parse_student_id(student_id)
    if student_id is None:
        return None

    init_progress_db()
    with get_progress_connection() as connection:
        return row_to_dict(
            connection.execute("SELECT id, name FROM students WHERE id = ?", (student_id,)).fetchone()
        )


def create_student(name):
    cleaned_name = str(name or "").strip()
    if not cleaned_name:
        return None

    init_progress_db()
    with get_progress_connection() as connection:
        existing_student = connection.execute(
            "SELECT id, name FROM students WHERE name = ?", (cleaned_name,)
        ).fetchone()
        if existing_student:
            return row_to_dict(existing_student)
        cursor = connection.execute(
            "INSERT INTO students (name, created_at) VALUES (?, ?)",
            (cleaned_name, datetime.now().isoformat(timespec="seconds")),
        )
        return {"id": cursor.lastrowid, "name": cleaned_name}


def log_progress_event(query, entry, source, mode, student_id=None):
    word = str(entry.get("word", "")).strip()
    student_id = parse_student_id(student_id)
    if not word or student_id is None:
        return

    init_progress_db()
    with get_progress_connection() as connection:
        connection.execute(
            """
            INSERT INTO search_events (
                searched_at, query, word, traditional, pinyin, english, source, mode, student_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                query.strip(),
                word,
                str(entry.get("traditional", word)).strip() or word,
                str(entry.get("pinyin", "")).strip(),
                str(entry.get("english", "")).strip(),
                source,
                mode,
                student_id,
            ),
        )


def record_quiz_attempt(student_id, vocabulary_word, is_correct, interaction_key):
    student_id = parse_student_id(student_id)
    word = str(vocabulary_word or "").strip()
    attempt_key = str(interaction_key or "").strip()
    if student_id is None or not word or not attempt_key or get_student(student_id) is None:
        return

    init_progress_db()
    with get_progress_connection() as connection:
        existing_attempt = connection.execute(
            "SELECT id FROM quiz_attempts WHERE student_id = ? AND interaction_key = ?",
            (student_id, attempt_key),
        ).fetchone()
        values = (word, int(bool(is_correct)), datetime.now().isoformat(timespec="seconds"), student_id, attempt_key)
        if existing_attempt:
            connection.execute(
                """
                UPDATE quiz_attempts
                SET vocabulary_word = ?, is_correct = ?, completed_at = ?
                WHERE student_id = ? AND interaction_key = ?
                """,
                values,
            )
        else:
            connection.execute(
                """
                INSERT INTO quiz_attempts (
                    student_id, vocabulary_word, is_correct, first_attempt_correct, completed_at, interaction_key
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    word,
                    int(bool(is_correct)),
                    int(bool(is_correct)),
                    datetime.now().isoformat(timespec="seconds"),
                    attempt_key,
                ),
            )


def get_review_mistake_entries(student_id):
    student_id = parse_student_id(student_id)
    if student_id is None or get_student(student_id) is None:
        return []

    init_progress_db()
    with get_progress_connection() as connection:
        mistake_words = [
            row["vocabulary_word"]
            for row in connection.execute(
                """
                SELECT vocabulary_word
                FROM quiz_attempts
                WHERE student_id = ?
                    AND id IN (
                        SELECT MAX(id)
                        FROM quiz_attempts
                        WHERE student_id = ?
                        GROUP BY vocabulary_word
                    )
                    AND first_attempt_correct = 0
                ORDER BY completed_at ASC, id ASC
                """,
                (student_id, student_id),
            )
        ]

    entries_by_word = {entry["word"]: entry for entry in get_quiz_entries()}
    return [entries_by_word[word] for word in mistake_words if word in entries_by_word]


def get_empty_progress_summary(selected_day=None):
    return {
        "total_searches": 0,
        "unique_words": 0,
        "today_count": 0,
        "today_events": [],
        "selected_day": selected_day,
        "selected_day_events": [],
        "recent_events": [],
        "daily_counts": [],
        "top_words": [],
        "quiz_stats": {"attempted": 0, "correct": 0, "accuracy": 0},
    }


def get_progress_summary(student_id, selected_day=None):
    init_progress_db()
    student_id = parse_student_id(student_id)
    if get_student(student_id) is None:
        return get_empty_progress_summary(selected_day)

    today = datetime.now().date().isoformat()
    if selected_day:
        try:
            selected_day = datetime.strptime(selected_day, "%Y-%m-%d").date().isoformat()
        except ValueError:
            selected_day = None

    with get_progress_connection() as connection:
        total_searches = connection.execute(
            "SELECT COUNT(*) AS count FROM search_events WHERE student_id = ?", (student_id,)
        ).fetchone()["count"]
        unique_words = connection.execute(
            "SELECT COUNT(DISTINCT word) AS count FROM search_events WHERE student_id = ? AND word IS NOT NULL AND word != ''",
            (student_id,),
        ).fetchone()["count"]
        today_count = connection.execute(
            "SELECT COUNT(*) AS count FROM search_events WHERE student_id = ? AND substr(searched_at, 1, 10) = ?",
            (student_id, today),
        ).fetchone()["count"]
        today_events = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT searched_at, query, word, traditional, pinyin, english, source, mode
                FROM search_events
                WHERE student_id = ? AND id IN (
                    SELECT MAX(id)
                    FROM search_events
                    WHERE student_id = ? AND substr(searched_at, 1, 10) = ?
                    GROUP BY word
                )
                ORDER BY searched_at DESC, id DESC
                LIMIT 20
                """,
                (student_id, student_id, today),
            )
        ]
        selected_day_events = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT searched_at, query, word, traditional, pinyin, english, source, mode
                FROM search_events
                WHERE student_id = ? AND id IN (
                    SELECT MAX(id)
                    FROM search_events
                    WHERE student_id = ? AND substr(searched_at, 1, 10) = ?
                    GROUP BY word
                )
                ORDER BY searched_at DESC, id DESC
                """,
                (student_id, student_id, selected_day),
            )
        ] if selected_day else []
        recent_events = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT searched_at, query, word, traditional, pinyin, english, source, mode
                FROM search_events
                WHERE student_id = ?
                ORDER BY searched_at DESC, id DESC
                LIMIT 20
                """,
                (student_id,),
            )
        ]
        daily_counts = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT substr(searched_at, 1, 10) AS day, COUNT(*) AS count
                FROM search_events
                WHERE student_id = ?
                GROUP BY day
                ORDER BY day DESC
                LIMIT 14
                """,
                (student_id,),
            )
        ]
        top_words = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT word, traditional, pinyin, english, COUNT(*) AS count
                FROM search_events
                WHERE student_id = ? AND word IS NOT NULL AND word != ''
                GROUP BY word, traditional, pinyin, english
                ORDER BY count DESC, MAX(searched_at) DESC
                LIMIT 10
                """,
                (student_id,),
            )
        ]
        quiz_stats_row = connection.execute(
            """
            SELECT COUNT(*) AS attempted, COALESCE(SUM(first_attempt_correct), 0) AS correct
            FROM quiz_attempts
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        quiz_attempted = quiz_stats_row["attempted"]
        quiz_correct = quiz_stats_row["correct"]

    return {
        "total_searches": total_searches,
        "unique_words": unique_words,
        "today_count": today_count,
        "today_events": today_events,
        "selected_day": selected_day,
        "selected_day_events": selected_day_events,
        "recent_events": recent_events,
        "daily_counts": daily_counts,
        "top_words": top_words,
        "quiz_stats": {
            "attempted": quiz_attempted,
            "correct": quiz_correct,
            "accuracy": round((quiz_correct / quiz_attempted) * 100) if quiz_attempted else 0,
        },
    }

def simplify_known_traditional_text(text):
    return TO_SIMPLIFIED.convert(text)


def traditionalize_known_simplified_text(text):
    return TO_TRADITIONAL.convert(text)


@app.template_filter("display_chinese_pair")
def display_chinese_pair(text):
    simplified = simplify_known_traditional_text(str(text or ""))
    traditional = traditionalize_known_simplified_text(simplified)
    return simplified if simplified == traditional else f"{simplified} / {traditional}"


def clean_ai_word_form(text):
    cleaned = re.sub(r"\([^)]*\)", "", text).strip()
    if not contains_chinese(cleaned):
        return cleaned
    return "".join(char for char in cleaned if "\u4e00" <= char <= "\u9fff")


def normalize_ai_word_forms(query, word, traditional):
    word = clean_ai_word_form(word)
    traditional = clean_ai_word_form(traditional) or word

    if contains_chinese(word):
        word = simplify_known_traditional_text(word)
        traditional = traditionalize_known_simplified_text(word)
    elif contains_chinese(traditional):
        word = simplify_known_traditional_text(traditional)
        traditional = traditionalize_known_simplified_text(word)

    return word, traditional


def get_ollama_health_url():
    parsed_url = urllib.parse.urlparse(OLLAMA_URL)
    if not parsed_url.scheme or not parsed_url.netloc:
        return "http://localhost:11434/api/tags"
    return urllib.parse.urlunparse((parsed_url.scheme, parsed_url.netloc, "/api/tags", "", "", ""))


def is_ollama_running():
    try:
        with urllib.request.urlopen(get_ollama_health_url(), timeout=0.5):
            return True
    except (OSError, TimeoutError, urllib.error.URLError):
        return False


def ensure_ollama_started():
    global OLLAMA_START_ATTEMPTED

    if not OLLAMA_AUTO_START or OLLAMA_START_ATTEMPTED or is_ollama_running():
        return

    OLLAMA_START_ATTEMPTED = True
    try:
        subprocess.Popen(
            [OLLAMA_COMMAND, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return


@app.before_request
def auto_start_ollama():
    ensure_ollama_started()


def search_entries(query):
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    normalized_query_no_tones = remove_tone_marks(normalized_query)
    if not any(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in normalized_query_no_tones):
        return []

    exact_matches = []
    for entry in DICTIONARY_ENTRIES:
        word = entry["word"]
        traditional = entry["traditional"]
        search_pinyin = entry["search_pinyin"]
        english = entry["english"].lower()

        if (
            normalized_query == word
            or normalized_query == traditional
            or normalized_query_no_tones == search_pinyin
            or normalized_query == english
        ):
            exact_matches.append(entry)

    if exact_matches:
        return exact_matches

    query_is_single_char = len(normalized_query_no_tones) == 1
    query_is_short_ascii = len(normalized_query_no_tones) < 3 and normalized_query_no_tones.isascii()
    scored_matches = []
    for entry in DICTIONARY_ENTRIES:
        word = entry["word"]
        traditional = entry["traditional"]
        pinyin = entry["pinyin"].lower()
        search_pinyin = entry["search_pinyin"]
        english = entry["english"].lower()
        explanation = entry["explanation"].lower()
        part_of_speech = entry["part_of_speech"].lower()
        english_words = re.findall(r"[a-z0-9]+", english)
        explanation_words = re.findall(r"[a-z0-9]+", explanation)
        part_of_speech_words = re.findall(r"[a-z0-9]+", part_of_speech)
        english_word_starts = any(word_part.startswith(normalized_query) for word_part in english_words)
        english_word_contains = normalized_query in english_words
        part_of_speech_contains = normalized_query in part_of_speech_words
        explanation_word_starts = any(word_part.startswith(normalized_query) for word_part in explanation_words)

        score = None

        if normalized_query == word or normalized_query == traditional:
            score = (0, len(word))
        elif normalized_query_no_tones == search_pinyin:
            score = (1, len(search_pinyin))
        elif normalized_query == english:
            score = (2, len(english))
        elif query_is_single_char:
            if word.startswith(normalized_query) or traditional.startswith(normalized_query):
                score = (3, min(len(word), len(traditional)))
            elif search_pinyin.startswith(normalized_query_no_tones):
                score = (4, len(search_pinyin))
        elif word.startswith(normalized_query) or traditional.startswith(normalized_query):
            score = (3, min(len(word), len(traditional)))
        elif search_pinyin.startswith(normalized_query_no_tones):
            score = (4, len(search_pinyin))
        elif english.startswith(normalized_query):
            score = (5, len(english))
        elif normalized_query in word or normalized_query in traditional:
            score = (6, min(len(word), len(traditional)))
        elif normalized_query_no_tones in search_pinyin and not query_is_short_ascii:
            score = (7, len(search_pinyin))
        elif english_word_contains:
            score = (8, len(english))
        elif english_word_starts and not query_is_short_ascii:
            score = (9, len(english))
        elif part_of_speech_contains and not query_is_short_ascii:
            score = (9, len(part_of_speech))
        elif explanation_word_starts and not query_is_short_ascii:
            score = (10, len(explanation))

        if score is not None:
            scored_matches.append((score, entry))

    scored_matches.sort(key=lambda item: item[0])
    return [entry for _, entry in scored_matches]


def split_batch_queries(text):
    queries = []
    seen = set()
    for raw_query in re.split(r"[\n,;，；]+", text):
        query = raw_query.strip()
        query_key = normalize_query_key(query)
        if not query or query_key in seen:
            continue
        queries.append(query)
        seen.add(query_key)
    return queries


def batch_search_entries(text):
    results = []
    missing_queries = []
    ai_queries = []
    seen_words = set()

    for query in split_batch_queries(text):
        matches = search_entries(query)
        if not matches:
            if is_meaningful_query(query):
                ai_queries.append(query)
            else:
                missing_queries.append(query)
            continue

        added_match = False
        for entry in matches:
            if entry["word"] in seen_words:
                continue
            results.append(entry)
            seen_words.add(entry["word"])
            added_match = True

        if not added_match:
            ai_queries.append(query)

    return results, missing_queries, ai_queries


def is_meaningful_query(query):
    normalized_query = query.strip().lower()
    if not normalized_query:
        return False

    normalized_query_no_tones = remove_tone_marks(normalized_query)
    return any(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in normalized_query_no_tones)


def normalize_query_key(query):
    return remove_tone_marks(query.strip().lower())


def contains_chinese(text):
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def looks_like_mandarin_quiz_word(text):
    cleaned = text.strip()
    if not cleaned:
        return False
    if not contains_chinese(cleaned):
        return False
    return len(cleaned) <= 8


def normalize_part_of_speech(value):
    cleaned = " ".join(value.strip().lower().split())
    return cleaned if cleaned in VALID_PARTS_OF_SPEECH else "word"


def make_structured_example(text, translation):
    return {
        "text": text,
        "speech_text": to_speech_text(text),
        "pinyin": to_sentence_pinyin(text),
        "translation": translation,
    }


def get_curated_ai_result(query):
    query_key = normalize_query_key(query)
    if query_key != normalize_query_key("前年"):
        return None

    return {
        "word": "前年",
        "traditional": "前年",
        "pinyin": "qián nián",
        "english": "the year before last",
        "part_of_speech": "time word",
        "explanation": "前年 means the year before last, two years before the current year.",
        "examples": [
            make_structured_example("前年我去了北京。", "The year before last, I went to Beijing."),
            make_structured_example("前年我们一起旅行。", "The year before last, we traveled together."),
        ],
    }


def validate_ai_result(query, result):
    word = result.get("word", "").strip()
    traditional = result.get("traditional", word).strip() or word
    english = result.get("english", "").strip()
    explanation = result.get("explanation", "").strip()

    if not word:
        return False

    query_is_chinese = contains_chinese(query)
    word_is_chinese = contains_chinese(word) or contains_chinese(traditional)

    if query_is_chinese and not word_is_chinese:
        return False

    if word in {"我是", "你是", "他是", "她是"}:
        return False

    if not explanation:
        return False

    if query_is_chinese and query.strip() not in {word, traditional}:
        return False

    if query_is_chinese and not english:
        return False

    return True


def fetch_ai_explanation(query):
    system_prompt = (
        "You are a Mandarin tutor for English-speaking beginners. "
        "Return JSON only with these keys: word, traditional, pinyin, english, part_of_speech, explanation, examples. "
        "Do not add extra keys. "
        "Use concise beginner-friendly English. "
        "The word field must be the simplified Chinese form of the exact Mandarin word or phrase being explained, not a sentence. "
        "The traditional field must be the traditional Chinese form of the same word or phrase. "
        "If simplified and traditional are the same, use the same value for both fields. "
        "If the input itself is Chinese, the input must match either the simplified word field or the traditional field. "
        "Set part_of_speech to exactly one of: noun, verb, adjective, adverb, phrase, expression, question word, conjunction, modal verb, time word, pronoun, measure word, word. "
        "Set examples to exactly 2 short Chinese sentence objects with keys text and translation. "
        "If the input is not a real Mandarin word or phrase, explain that clearly and return examples as an empty list."
    )
    for attempt in range(2):
        retry_instruction = ""
        if attempt:
            retry_instruction = (
                "Your previous answer did not meet the required quality checks. "
                "Correct it now: provide a real Chinese word or phrase, a non-empty English meaning, "
                "and a non-empty beginner-friendly explanation. "
                "For Chinese input, the word or traditional field must exactly match the input. "
            )
        user_prompt = (
            f"Explain this Mandarin word or phrase for a learner: {query}\n"
            f"{retry_instruction}"
            "Return valid JSON only."
        )
        payload = {
            "model": OLLAMA_MODEL,
            "stream": False,
            "format": "json",
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request_data = json.dumps(payload).encode("utf-8")
        http_request = urllib.request.Request(
            OLLAMA_URL,
            data=request_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_request, timeout=OLLAMA_TIMEOUT) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError, socket.timeout, urllib.error.URLError, json.JSONDecodeError) as exc:
            return None, f"AI explanation is unavailable right now. Start Ollama and load `{OLLAMA_MODEL}`. ({exc})"

        try:
            content = response_data["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, TypeError, json.JSONDecodeError):
            return None, "AI explanation is unavailable right now because the local model returned an invalid response."

        examples = []
        for example in parsed.get("examples", [])[:2]:
            text = example.get("text", "").strip()
            translation = example.get("translation", "").strip()
            if not text:
                continue
            examples.append(make_structured_example(text, translation))

        word = parsed.get("word", query).strip() or query
        traditional = parsed.get("traditional", word).strip() or word
        word, traditional = normalize_ai_word_forms(query, word, traditional)
        pinyin = to_sentence_pinyin(word) if contains_chinese(word) else parsed.get("pinyin", "").strip()

        ai_result = {
            "word": word,
            "traditional": traditional,
            "pinyin": pinyin,
            "english": parsed.get("english", "").strip(),
            "part_of_speech": normalize_part_of_speech(parsed.get("part_of_speech", "word")),
            "explanation": parsed.get("explanation", "").strip() or "No explanation available.",
            "examples": examples,
        }

        if validate_ai_result(query, ai_result):
            return ai_result, None

    return None, "AI explanation is unavailable right now because the local model returned a low-quality result."


def get_ai_explanation(query):
    cache_key = normalize_query_key(query)
    if cache_key in AI_EXPLANATION_CACHE:
        return AI_EXPLANATION_CACHE[cache_key]

    curated_result = get_curated_ai_result(query)
    if curated_result:
        result = (curated_result, None)
        AI_EXPLANATION_CACHE[cache_key] = result
        return result

    result = fetch_ai_explanation(query)
    if result[0] and not result[1]:
        AI_EXPLANATION_CACHE[cache_key] = result
    return result


def get_quiz_entries():
    entries = list(DICTIONARY_ENTRIES)
    existing_words = {entry["word"] for entry in entries}

    for cached_result, cached_error in AI_EXPLANATION_CACHE.values():
        if cached_error or not cached_result:
            continue
        if cached_result["word"] in existing_words:
            continue
        if not looks_like_mandarin_quiz_word(cached_result["word"]):
            continue
        entries.append(cached_result)
        existing_words.add(cached_result["word"])

    valid_entries = []
    for entry in entries:
        word = str(entry.get("word", "")).strip()
        pinyin = str(entry.get("pinyin", "")).strip()
        english = str(entry.get("english", "")).strip()
        if not word or not pinyin or not english:
            continue
        valid_entries.append(entry)

    return valid_entries


def find_entry_by_english(english_meaning):
    for entry in get_quiz_entries():
        if entry["english"] == english_meaning:
            return entry
    return None


def build_quiz(question_word=None, exclude_word=None, choices=None, recent_words=None, allowed_words=None):
    correct_entry = None
    recent_words = recent_words or []
    all_quiz_entries = get_quiz_entries()
    quiz_entries = all_quiz_entries
    if allowed_words is not None:
        allowed_word_set = set(allowed_words)
        quiz_entries = [entry for entry in all_quiz_entries if entry["word"] in allowed_word_set]

    if not quiz_entries:
        return None

    if question_word:
        for entry in quiz_entries:
            if entry["word"] == question_word:
                correct_entry = entry
                break

    if correct_entry is None:
        candidates = [
            entry for entry in quiz_entries
            if entry["word"] != exclude_word and entry["word"] not in recent_words
        ]
        if not candidates:
            candidates = [entry for entry in quiz_entries if entry["word"] != exclude_word]
        if not candidates:
            candidates = quiz_entries
        correct_entry = random.choice(candidates)

    if choices is None:
        wrong_answers = []
        for entry in all_quiz_entries:
            english = str(entry.get("english", "")).strip()
            if entry["word"] == correct_entry["word"] or not english:
                continue
            if english in wrong_answers:
                continue
            wrong_answers.append(english)

        choices = random.sample(wrong_answers, k=min(3, len(wrong_answers)))
        choices.append(str(correct_entry["english"]).strip())
        random.shuffle(choices)
    else:
        cleaned_choices = []
        for choice in choices:
            value = str(choice).strip()
            if not value or value in cleaned_choices:
                continue
            cleaned_choices.append(value)
        if str(correct_entry["english"]).strip() not in cleaned_choices:
            cleaned_choices.append(str(correct_entry["english"]).strip())
        choices = cleaned_choices

    return {
        "word": correct_entry["word"],
        "traditional": correct_entry.get("traditional", correct_entry["word"]),
        "pinyin": correct_entry["pinyin"],
        "correct_answer": correct_entry["english"],
        "choices": choices,
    }


def parse_quiz_score(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_quiz_source(value):
    return "review" if value == "review" else "normal"


@app.route("/", methods=["GET", "POST"])
def home():
    mode = request.args.get("mode", "search")
    progress_day = request.args.get("day")
    student_id = parse_student_id(request.form.get("student_id") or request.args.get("student_id"))
    students = list_students()
    selected_student = get_student(student_id)
    if selected_student is None:
        student_id = None
    recent_words = request.args.getlist("recent_word")
    query = ""
    results = []
    batch_missing = []
    batch_ai_queries = []
    ai_pending = False
    conversion_text = ""
    converted_simplified = ""
    converted_traditional = ""
    quiz_source = normalize_quiz_source(request.form.get("quiz_source") or request.args.get("quiz_source"))
    review_words = request.form.getlist("review_word") or request.args.getlist("review_word")
    if quiz_source == "review" and not review_words:
        review_words = [entry["word"] for entry in get_review_mistake_entries(student_id)]
    quiz = build_quiz(
        recent_words=recent_words,
        allowed_words=review_words if quiz_source == "review" else None,
    )
    review_empty = quiz_source == "review" and not review_words
    quiz_feedback = None
    quiz_score = {
        "correct": parse_quiz_score(request.args.get("score_correct")),
        "attempted": parse_quiz_score(request.args.get("score_attempted")),
        "question_counted": request.args.get("question_counted") == "1",
    }
    quiz_attempt_key = request.form.get("quiz_attempt_key") or request.args.get("quiz_attempt_key") or uuid.uuid4().hex
    progress_summary = get_progress_summary(student_id, progress_day) if mode == "progress" else None

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "student":
            mode = request.form.get("return_mode", mode)
            selected_student = create_student(request.form.get("student_name"))
            student_id = selected_student["id"] if selected_student else None
            students = list_students()
        elif form_type == "search":
            mode = "search"
            query = request.form.get("query", "")
            results = search_entries(query)
            for entry in results:
                log_progress_event(query, entry, "dictionary", "search", student_id)
            if not results and is_meaningful_query(query):
                ai_pending = True
        elif form_type == "batch":
            mode = "batch"
            query = request.form.get("query", "")
            results, batch_missing, batch_ai_queries = batch_search_entries(query)
            for entry in results:
                log_progress_event(query, entry, "dictionary", "batch", student_id)
        elif form_type == "convert":
            mode = "convert"
            conversion_text = request.form.get("text", "")
            converted_simplified = simplify_known_traditional_text(conversion_text)
            converted_traditional = traditionalize_known_simplified_text(conversion_text)
        elif form_type == "quiz":
            mode = "quiz"
            query = request.form.get("query", "")
            results = search_entries(query) if query else []
            question_word = request.form.get("question_word")
            selected_answer = request.form.get("selected_answer", "")
            current_choices = request.form.getlist("choice")
            recent_words = request.form.getlist("recent_word")
            quiz_source = normalize_quiz_source(request.form.get("quiz_source"))
            review_words = request.form.getlist("review_word")
            quiz_score = {
                "correct": parse_quiz_score(request.form.get("score_correct")),
                "attempted": parse_quiz_score(request.form.get("score_attempted")),
                "question_counted": request.form.get("question_counted") == "1",
            }
            quiz_attempt_key = request.form.get("quiz_attempt_key") or uuid.uuid4().hex
            quiz = build_quiz(
                question_word,
                choices=current_choices or None,
                recent_words=recent_words,
                allowed_words=review_words if quiz_source == "review" else None,
            )
            if quiz is None:
                review_empty = quiz_source == "review"
                quiz_attempt_key = uuid.uuid4().hex
                return render_template(
                    "index.html",
                    mode=mode,
                    query=query,
                    results=results,
                    batch_missing=batch_missing,
                    batch_ai_queries=batch_ai_queries,
                    ai_pending=ai_pending,
                    conversion_text=conversion_text,
                    converted_simplified=converted_simplified,
                    converted_traditional=converted_traditional,
                    students=students,
                    selected_student=selected_student,
                    quiz=None,
                    quiz_feedback=None,
                    quiz_score=quiz_score,
                    quiz_attempt_key=quiz_attempt_key,
                    quiz_source=quiz_source,
                    review_words=review_words,
                    review_empty=review_empty,
                    recent_words=recent_words,
                    progress_summary=progress_summary,
                )
            is_correct = selected_answer == quiz["correct_answer"]
            record_quiz_attempt(student_id, quiz["word"], is_correct, quiz_attempt_key)
            if is_correct:
                if not quiz_score["question_counted"]:
                    quiz_score["attempted"] += 1
                    quiz_score["correct"] += 1
                quiz_score["question_counted"] = False
                recent_words = (recent_words + [question_word])[-RECENT_QUIZ_LIMIT:]
                if quiz_source == "review":
                    review_words = [word for word in review_words if word != question_word]
                    quiz = build_quiz(recent_words=recent_words, allowed_words=review_words)
                    review_empty = quiz is None
                else:
                    quiz = build_quiz(exclude_word=question_word, recent_words=recent_words)
                quiz_attempt_key = uuid.uuid4().hex
            else:
                if not quiz_score["question_counted"]:
                    quiz_score["attempted"] += 1
                    quiz_score["question_counted"] = True
                wrong_entry = find_entry_by_english(selected_answer)
                quiz_feedback = {
                    "selected_answer": selected_answer,
                    "is_correct": False,
                    "wrong_word": wrong_entry["word"] if wrong_entry else "",
                    "wrong_pinyin": wrong_entry["pinyin"] if wrong_entry else "",
                }

    if mode == "progress":
        progress_summary = get_progress_summary(student_id, progress_day)

    return render_template(
        "index.html",
        mode=mode,
        query=query,
        results=results,
        batch_missing=batch_missing,
        batch_ai_queries=batch_ai_queries,
        ai_pending=ai_pending,
        conversion_text=conversion_text,
        converted_simplified=converted_simplified,
        converted_traditional=converted_traditional,
        students=students,
        selected_student=selected_student,
        quiz=quiz,
        quiz_feedback=quiz_feedback,
        quiz_score=quiz_score,
        quiz_attempt_key=quiz_attempt_key,
        quiz_source=quiz_source,
        review_words=review_words,
        review_empty=review_empty,
        recent_words=recent_words,
        progress_summary=progress_summary,
    )


@app.get("/api/ai-explanation")
def ai_explanation():
    query = request.args.get("query", "")
    mode = request.args.get("mode", "search")
    student_id = parse_student_id(request.args.get("student_id"))
    if not is_meaningful_query(query):
        return jsonify({"ok": False, "error": "Please enter a real Chinese word, pinyin, or English meaning."}), 400

    result, error = get_ai_explanation(query)
    if error:
        return jsonify({"ok": False, "error": error}), 503

    log_progress_event(query, result, "ai", mode if mode in {"search", "batch"} else "search", student_id)
    return jsonify({"ok": True, "result": result})


@app.post("/api/clear-ai-cache")
def clear_ai_cache():
    AI_EXPLANATION_CACHE.clear()
    return jsonify({"ok": True})


@app.get("/api/tts")
def text_to_speech():
    text = to_speech_text(request.args.get("text", ""))[:200]
    if not text:
        return jsonify({"ok": False, "error": "Missing text to speak."}), 400

    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as audio_file:
        audio_path = Path(audio_file.name)

    try:
        subprocess.run(
            [TTS_COMMAND, "-v", TTS_VOICE, "-o", str(audio_path), text],
            check=True,
            timeout=30,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        audio_path.unlink(missing_ok=True)
        return jsonify({"ok": False, "error": "Local text-to-speech command was not found."}), 503
    except subprocess.TimeoutExpired:
        audio_path.unlink(missing_ok=True)
        return jsonify({"ok": False, "error": "Local text-to-speech timed out."}), 503
    except subprocess.CalledProcessError as error:
        audio_path.unlink(missing_ok=True)
        detail = (error.stderr or error.stdout or "").strip()
        return jsonify({"ok": False, "error": detail or "Local text-to-speech is unavailable."}), 503

    @after_this_request
    def remove_audio_file(response):
        audio_path.unlink(missing_ok=True)
        return response

    return send_file(audio_path, mimetype="audio/aiff", download_name="mandarin.aiff")


@app.post("/api/speak")
def speak_text():
    text = to_speech_text(request.form.get("text", ""))[:200]
    if not text:
        return jsonify({"ok": False, "error": "Missing text to speak."}), 400

    try:
        subprocess.Popen(
            [TTS_COMMAND, "-v", TTS_VOICE, text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "Local text-to-speech command was not found."}), 503

    return jsonify({"ok": True})


@app.get("/assets/<path:filename>")
def asset_file(filename):
    return send_from_directory(ASSETS_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
