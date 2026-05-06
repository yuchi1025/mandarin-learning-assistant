import json
import os
from pathlib import Path
import random
import re
import unicodedata
import urllib.error
import urllib.request

from flask import Flask, jsonify, render_template, request, send_from_directory
from pypinyin import Style, lazy_pinyin

app = Flask(__name__)
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
RECENT_QUIZ_LIMIT = 5
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "15m")
AI_EXPLANATION_CACHE = {}
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


def to_sentence_pinyin(text):
    pinyin_text = " ".join(lazy_pinyin(text, style=Style.TONE))
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


def load_dictionary():
    with DICTIONARY_PATH.open(encoding="utf-8") as dictionary_file:
        raw_entries = json.load(dictionary_file)

    entries = []
    for raw_entry in raw_entries:
        word = str(raw_entry.get("word", "")).strip()
        if not word:
            continue

        structured_examples = []
        for example in raw_entry.get("examples", []):
            chinese_text, translation = split_example(str(example))
            structured_examples.append(
                {
                    "text": chinese_text,
                    "pinyin": to_sentence_pinyin(chinese_text),
                    "translation": translation,
                }
            )

        pinyin = str(raw_entry.get("pinyin", "")).strip() or " ".join(lazy_pinyin(word, style=Style.TONE))
        entries.append(
            {
                "word": word,
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
        search_pinyin = entry["search_pinyin"]
        english = entry["english"].lower()

        if (
            normalized_query == word
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

        if normalized_query == word:
            score = (0, len(word))
        elif normalized_query_no_tones == search_pinyin:
            score = (1, len(search_pinyin))
        elif normalized_query == english:
            score = (2, len(english))
        elif query_is_single_char:
            if word.startswith(normalized_query):
                score = (3, len(word))
            elif search_pinyin.startswith(normalized_query_no_tones):
                score = (4, len(search_pinyin))
        elif word.startswith(normalized_query):
            score = (3, len(word))
        elif search_pinyin.startswith(normalized_query_no_tones):
            score = (4, len(search_pinyin))
        elif english.startswith(normalized_query):
            score = (5, len(english))
        elif normalized_query in word:
            score = (6, len(word))
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


def validate_ai_result(query, result):
    word = result.get("word", "").strip()
    english = result.get("english", "").strip()
    explanation = result.get("explanation", "").strip()

    if not word:
        return False

    query_is_chinese = contains_chinese(query)
    word_is_chinese = contains_chinese(word)

    if query_is_chinese and not word_is_chinese:
        return False

    if word in {"我是", "你是", "他是", "她是"}:
        return False

    if not explanation:
        return False

    if query_is_chinese and word != query.strip():
        return False

    if query_is_chinese and not english:
        return False

    return True


def fetch_ai_explanation(query):
    system_prompt = (
        "You are a Mandarin tutor for English-speaking beginners. "
        "Return JSON only with these keys: word, pinyin, english, part_of_speech, explanation, examples. "
        "Do not add extra keys. "
        "Use concise beginner-friendly English. "
        "The word field must be the exact Mandarin word or phrase being explained, not a sentence. "
        "If the input itself is Chinese, keep the word field exactly the same as the input. "
        "Set part_of_speech to exactly one of: noun, verb, adjective, adverb, phrase, expression, question word, conjunction, modal verb, time word, pronoun, measure word, word. "
        "Set examples to exactly 2 short Chinese sentence objects with keys text and translation. "
        "If the input is not a real Mandarin word or phrase, explain that clearly and return examples as an empty list."
    )
    user_prompt = (
        f"Explain this Mandarin word or phrase for a learner: {query}\n"
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
        with urllib.request.urlopen(http_request, timeout=20) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
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
        examples.append(
            {
                "text": text,
                "pinyin": to_sentence_pinyin(text),
                "translation": translation,
            }
        )

    ai_result = {
        "word": parsed.get("word", query).strip() or query,
        "pinyin": parsed.get("pinyin", "").strip(),
        "english": parsed.get("english", "").strip(),
        "part_of_speech": normalize_part_of_speech(parsed.get("part_of_speech", "word")),
        "explanation": parsed.get("explanation", "").strip() or "No explanation available.",
        "examples": examples,
    }

    if not validate_ai_result(query, ai_result):
        return None, "AI explanation is unavailable right now because the local model returned a low-quality result."

    return ai_result, None


def get_ai_explanation(query):
    cache_key = normalize_query_key(query)
    if cache_key in AI_EXPLANATION_CACHE:
        return AI_EXPLANATION_CACHE[cache_key]

    result = fetch_ai_explanation(query)
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


def build_quiz(question_word=None, exclude_word=None, choices=None, recent_words=None):
    correct_entry = None
    recent_words = recent_words or []
    quiz_entries = get_quiz_entries()

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
        for entry in quiz_entries:
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
        "pinyin": correct_entry["pinyin"],
        "correct_answer": correct_entry["english"],
        "choices": choices,
    }


@app.route("/", methods=["GET", "POST"])
def home():
    mode = request.args.get("mode", "search")
    recent_words = request.args.getlist("recent_word")
    query = ""
    results = []
    ai_pending = False
    quiz = build_quiz(recent_words=recent_words)
    quiz_feedback = None

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "search":
            mode = "search"
            query = request.form.get("query", "")
            results = search_entries(query)
            if not results and is_meaningful_query(query):
                ai_pending = True
        elif form_type == "quiz":
            mode = "quiz"
            query = request.form.get("query", "")
            results = search_entries(query) if query else []
            question_word = request.form.get("question_word")
            selected_answer = request.form.get("selected_answer", "")
            current_choices = request.form.getlist("choice")
            recent_words = request.form.getlist("recent_word")
            quiz = build_quiz(question_word, choices=current_choices or None, recent_words=recent_words)
            is_correct = selected_answer == quiz["correct_answer"]
            if is_correct:
                recent_words = (recent_words + [question_word])[-RECENT_QUIZ_LIMIT:]
                quiz = build_quiz(exclude_word=question_word, recent_words=recent_words)
            else:
                wrong_entry = find_entry_by_english(selected_answer)
                quiz_feedback = {
                    "selected_answer": selected_answer,
                    "is_correct": False,
                    "wrong_word": wrong_entry["word"] if wrong_entry else "",
                    "wrong_pinyin": wrong_entry["pinyin"] if wrong_entry else "",
                }

    return render_template(
        "index.html",
        mode=mode,
        query=query,
        results=results,
        ai_pending=ai_pending,
        quiz=quiz,
        quiz_feedback=quiz_feedback,
        recent_words=recent_words,
    )


@app.get("/api/ai-explanation")
def ai_explanation():
    query = request.args.get("query", "")
    if not is_meaningful_query(query):
        return jsonify({"ok": False, "error": "Please enter a real Chinese word, pinyin, or English meaning."}), 400

    result, error = get_ai_explanation(query)
    if error:
        return jsonify({"ok": False, "error": error}), 503

    return jsonify({"ok": True, "result": result})


@app.get("/assets/<path:filename>")
def asset_file(filename):
    return send_from_directory(ASSETS_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)
