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
from datetime import date, datetime, timedelta

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
TO_SIMPLIFIED_TAIWAN = OpenCC("tw2sp")
TO_TRADITIONAL_CHARACTERS = OpenCC("s2t")
# Use Taiwan Traditional vocabulary for learner-facing paired-script displays.
TO_TRADITIONAL = OpenCC("s2twp")
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
CATEGORY_LABELS = {
    "basics": "Basics & greetings",
    "actions": "Actions & routines",
    "time": "Time & dates",
    "places": "Places & travel",
    "food": "Food & shopping",
    "people": "People & home",
    "study": "School & work",
    "descriptions": "Descriptions",
    "grammar": "Grammar & questions",
    "health": "Health & weather",
    "technology": "Technology & media",
    "everyday": "Everyday life",
}
CATEGORY_WORDS = {
    "basics": "你好 谢谢 可以 不要 早上好 晚上好 再见 对不起 没关系 请 请问 没事 是 不是 有 没有 要 想 会 能 应该 怎么 哪里 什么时候 谁 哪个 几 很 也 都 还 就 但是 所以 如果 和 在 里 上 下 当然 一起 已经 还没有 正在 同意".split(),
    "actions": "吃饭 喝水 等一下 知道 觉得 喜欢 不喜欢 回家 出去 进来 看 听 说 打开 关上 开始 结束 找 给 带 用 做 去 来 到 走 坐 住 睡觉 起床 洗澡 洗手 穿 拿 放 送 帮忙 问 回答 懂 明白 认识 记得 忘记 建议 检查 通过 准备 希望 计划 决定 选择 参加 练习 介绍 解释 发现 改变 解决 试试 休息 运动 跑步 游泳 旅行 帮助".split(),
    "time": "现在 时间 今天 明天 昨天 早上 中午 晚上 周末 生日 年 月 日 星期 分钟 小时 去年 前年 后年 早 晚".split(),
    "places": "车站 地铁 公交车 出租车 机场 火车 飞机 路 左边 右边 前面 后面 旁边 公园 附近 地址 地图 护照 行李 预订 房子 公寓 银行 自行车 入口 出口 国家 城市 北京 上海".split(),
    "food": "多少钱 买 卖 商店 超市 饭店 水 咖啡 茶 饭 面条 苹果 香蕉 鸡蛋 牛奶 钱 卡 现金 票 产品 菜单 点菜 服务员 付款 找钱 价格 颜色 红色 白色 黑色".split(),
    "people": "家 人 男人 女人 孩子 爸爸 妈妈 哥哥 姐姐 弟弟 妹妹 房间 厨房 洗手间 门 窗户 桌子 椅子 教练".split(),
    "study": "学习 工作 下班 上班 学校 公司 医院 老师 学生 同事 书 考试 作业 课堂 同学 课程 老板 会议 项目 邮件 文件 经理 办公室".split(),
    "descriptions": "累 开心 热 冷 好吃 好喝 漂亮 贵 便宜 快 慢 远 近 忙 空 新 旧 大 小 多 少 重要 可能 不同 容易 困难 安全 小心 疼".split(),
    "grammar": "为什么 因为".split(),
    "health": "天气 雨 太阳 药 身体 生病 医生 预约 过敏".split(),
    "technology": "手机 电脑 电视 电影 音乐 电话 消息 照片 新闻 报纸 语言 中文 英文".split(),
}
CATEGORY_BY_WORD = {
    word: category for category, words in CATEGORY_WORDS.items() for word in words
}
CATEGORY_BY_WORD.update({
    word: category
    for category, words in {
        "basics": "答案 回复 通知 联系 邀请 庆祝 礼物 新年 假期".split(),
        "actions": "唱歌 跳舞 画画 阅读 写 读 充电 租 搬家 打扫 修理 开车 停车 加油 过马路 锻炼 借 还钱 注册 登录".split(),
        "time": "春天 夏天 秋天 冬天".split(),
        "places": "楼 电梯 邻居 司机 摩托车 交通 堵车 绿灯 红灯".split(),
        "food": "早餐 午饭 晚饭 水果 蔬菜 肉 鱼 鸡肉 牛肉 猪肉 汤 米饭 饺子 包子 甜 辣 咸 饿 饱 外卖 信用卡 工资 发票".split(),
        "people": "客厅 卧室 阳台 垃圾 干净 脏 坏 空调 冰箱 洗衣机".split(),
        "study": "故事 节目 游戏".split(),
        "descriptions": "免费".split(),
        "health": "诊所 护士 感冒 发烧 咳嗽 头疼 肚子 牙齿 眼睛 健康".split(),
        "technology": "歌曲 视频 网络 网站 密码 电池 耳机".split(),
    }.items()
    for word in words
})
CATEGORY_BY_WORD.update({
    word: category
    for category, words in {
        "basics": "相信 认为 同样 特别 比 最 更 一点 一些 每 从 向 跟 被 让 虽然 可是 还是 或者 一边 一直".split(),
        "actions": "爱 讨厌 担心 放心 理发 试穿 退货 交换 请假 加班".split(),
        "time": "延误".split(),
        "places": "邮局 出差 签证 海关 导游 旅馆 单程 往返 登机牌 航班 目的地".split(),
        "food": "顾客 商场 市场 订单 尺码 折扣 质量 品牌 收银员 快递 包裹 洗衣店".split(),
        "people": "亲戚 夫妻 丈夫 妻子 爷爷 奶奶 外公 外婆 儿子 女儿 理发店 锁 插座 灯 盘子 杯子 汤匙 筷子 刀 叉子 毛巾 牙刷 肥皂 镜子 床".split(),
        "study": "认真 正确 错误 面试 简历 客户 合同 培训 上司 任务 进度".split(),
        "descriptions": "紧张 害怕 生气 难过 惊讶 无聊 有趣 好笑 奇怪".split(),
        "health": "担心".split(),
        "technology": "".split(),
        "everyday": "".split(),
    }.items()
    for word in words
})


DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "dictionary.json"
DICTIONARY_ALIASES_PATH = Path(__file__).resolve().parent.parent / "data" / "dictionary_aliases.json"
PROGRESS_DB_PATH = Path(os.getenv("PROGRESS_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "progress.db"))
PINYIN_PHRASE_OVERRIDES = {
    "愛好": "ài hào",
    "个": "gè",
    "個": "gè",
    "不记得": "bú jì dé",
    "不記得": "bú jì dé",
    "不够": "bú gòu",
    "不夠": "bú gòu",
    "行為": "xíng wéi",
    "日期": "rì qí",
    "星期一": "xīng qí yī",
    "星期二": "xīng qí èr",
    "星期三": "xīng qí sān",
    "星期四": "xīng qí sì",
    "星期五": "xīng qí wǔ",
    "星期六": "xīng qí liù",
    "星期日": "xīng qí rì",
    "星期天": "xīng qí tiān",
    "星期": "xīng qí",
    "记得": "jì dé",
    "記得": "jì dé",
    "汤匙": "tāng chí",
    "湯匙": "tāng chí",
}
PINYIN_OVERRIDE_PHRASES = sorted(PINYIN_PHRASE_OVERRIDES, key=len, reverse=True)
BATCH_LIST_PREFIX_PATTERN = re.compile(
    r"^\s*(?:(?:[-*•‣◦▪‒–—])\s*|(?:\(?\d{1,3}\)?[.)、:])\s*)"
)
DAILY_CONVERSATION_PROMPTS = [
    ("今天做了什么？", "What did you do today?"),
    ("今天几点起床？", "What time did you get up today?"),
    ("今天工作或者上课怎么样？", "How was work or class today?"),
    ("晚餐吃了什么？", "What did you eat for dinner?"),
    ("周末有什么计划？", "What plans do you have for the weekend?"),
]


def to_sentence_pinyin(text):
    pinyin_parts = []
    plain_text = []

    def append_plain_text_pinyin():
        if plain_text:
            pinyin_parts.extend(lazy_pinyin("".join(plain_text), style=Style.TONE))
            plain_text.clear()

    index = 0
    while index < len(text):
        matched_phrase = next(
            (phrase for phrase in PINYIN_OVERRIDE_PHRASES if text.startswith(phrase, index)),
            None,
        )
        if matched_phrase:
            append_plain_text_pinyin()
            pinyin_parts.append(PINYIN_PHRASE_OVERRIDES[matched_phrase])
            index += len(matched_phrase)
            continue

        plain_text.append(text[index])
        index += 1

    append_plain_text_pinyin()

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


def load_dictionary_aliases():
    if not DICTIONARY_ALIASES_PATH.exists():
        return {}
    with DICTIONARY_ALIASES_PATH.open(encoding="utf-8") as aliases_file:
        raw_aliases = json.load(aliases_file)
    return {
        str(word).strip(): [str(alias).strip() for alias in aliases if str(alias).strip()]
        for word, aliases in raw_aliases.items()
        if str(word).strip() and isinstance(aliases, list)
    }


DICTIONARY_ALIASES = load_dictionary_aliases()
DICTIONARY_CANONICAL_BY_ALIAS = {
    alias: word for word, aliases in DICTIONARY_ALIASES.items() for alias in aliases
}


def canonicalize_dictionary_word(word):
    normalized = str(word or "").strip()
    return DICTIONARY_CANONICAL_BY_ALIAS.get(normalized, normalized)


def dictionary_reference_forms(word):
    canonical = canonicalize_dictionary_word(word)
    return [canonical, *DICTIONARY_ALIASES.get(canonical, [])]


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
                "aliases": DICTIONARY_ALIASES.get(word, []),
                "search_alias_pinyin": [
                    remove_tone_marks(" ".join(lazy_pinyin(alias, style=Style.TONE)))
                    for alias in DICTIONARY_ALIASES.get(word, [])
                ],
                "category": CATEGORY_BY_WORD.get(word, "everyday"),
            }
        )

    return entries


DICTIONARY_ENTRIES = load_dictionary()
DICTIONARY_ENTRIES_BY_WORD = {entry["word"]: entry for entry in DICTIONARY_ENTRIES}


def get_dictionary_entry(word):
    return DICTIONARY_ENTRIES_BY_WORD.get(canonicalize_dictionary_word(word))


def normalize_category(value):
    return value if value in CATEGORY_LABELS else "all"


def normalize_entry_category(value):
    return value if value in CATEGORY_LABELS else "everyday"


def get_entry_category(entry):
    return normalize_entry_category(entry.get("category") or CATEGORY_BY_WORD.get(entry.get("word", "")))


def filter_entries_by_category(entries, category):
    category = normalize_category(category)
    if category == "all":
        return entries
    return [entry for entry in entries if get_entry_category(entry) == category]


def get_progress_connection():
    PROGRESS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(PROGRESS_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def migrate_dictionary_alias_references(connection):
    """Keep learner history connected when a regional alias becomes canonical."""
    for alias, canonical in DICTIONARY_CANONICAL_BY_ALIAS.items():
        connection.execute(
            """
            INSERT OR IGNORE INTO saved_vocabulary
                (student_id, vocabulary_word, saved_at, source, entry_json)
            SELECT student_id, ?, saved_at, source, entry_json
            FROM saved_vocabulary WHERE vocabulary_word = ?
            """,
            (canonical, alias),
        )
        connection.execute("DELETE FROM saved_vocabulary WHERE vocabulary_word = ?", (alias,))
        connection.execute(
            """
            INSERT OR IGNORE INTO review_schedules
                (student_id, vocabulary_word, next_review_at, review_interval_days,
                 consecutive_correct, status, updated_at)
            SELECT student_id, ?, next_review_at, review_interval_days,
                   consecutive_correct, status, updated_at
            FROM review_schedules WHERE vocabulary_word = ?
            """,
            (canonical, alias),
        )
        connection.execute("DELETE FROM review_schedules WHERE vocabulary_word = ?", (alias,))
        connection.execute(
            """
            INSERT OR IGNORE INTO lesson_vocabulary (lesson_id, vocabulary_word)
            SELECT lesson_id, ? FROM lesson_vocabulary WHERE vocabulary_word = ?
            """,
            (canonical, alias),
        )
        connection.execute("DELETE FROM lesson_vocabulary WHERE vocabulary_word = ?", (alias,))
        connection.execute("UPDATE search_events SET word = ? WHERE word = ?", (canonical, alias))
        connection.execute(
            "UPDATE quiz_attempts SET vocabulary_word = ? WHERE vocabulary_word = ?",
            (canonical, alias),
        )
        connection.execute(
            "UPDATE sentence_practice_events SET target_word = ? WHERE target_word = ?",
            (canonical, alias),
        )


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
                quiz_source TEXT NOT NULL DEFAULT 'all',
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
        if "quiz_source" not in quiz_attempt_columns:
            connection.execute("ALTER TABLE quiz_attempts ADD COLUMN quiz_source TEXT NOT NULL DEFAULT 'all'")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_date ON quiz_attempts (student_id, completed_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student_source_date "
            "ON quiz_attempts (student_id, quiz_source, completed_at)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS saved_vocabulary (
                student_id INTEGER NOT NULL REFERENCES students(id),
                vocabulary_word TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'dictionary',
                entry_json TEXT,
                PRIMARY KEY (student_id, vocabulary_word)
            )
            """
        )
        saved_vocabulary_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(saved_vocabulary)")
        }
        if "source" not in saved_vocabulary_columns:
            connection.execute(
                "ALTER TABLE saved_vocabulary ADD COLUMN source TEXT NOT NULL DEFAULT 'dictionary'"
            )
        if "entry_json" not in saved_vocabulary_columns:
            connection.execute("ALTER TABLE saved_vocabulary ADD COLUMN entry_json TEXT")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_saved_vocabulary_student_date ON saved_vocabulary (student_id, saved_at)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS review_schedules (
                student_id INTEGER NOT NULL REFERENCES students(id),
                vocabulary_word TEXT NOT NULL,
                next_review_at TEXT NOT NULL,
                review_interval_days INTEGER NOT NULL,
                consecutive_correct INTEGER NOT NULL,
                status TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (student_id, vocabulary_word)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_schedules_due ON review_schedules (student_id, next_review_at)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sentence_practice_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id),
                target_word TEXT NOT NULL,
                original_sentence TEXT NOT NULL,
                target_used INTEGER CHECK (target_used IN (0, 1)),
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sentence_practice_student_date "
            "ON sentence_practice_events (student_id, created_at)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id),
                conversation_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                learner_answer TEXT NOT NULL,
                improved_answer TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_conversation_turns_student_session "
            "ON conversation_turns (student_id, conversation_id, id)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id),
                lesson_date TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_lessons_student_date "
            "ON lessons (student_id, lesson_date DESC, id DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_vocabulary (
                lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
                vocabulary_word TEXT NOT NULL,
                PRIMARY KEY (lesson_id, vocabulary_word)
            )
            """
        )
        migrate_dictionary_alias_references(connection)


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


def normalize_lesson_date(value):
    try:
        return date.fromisoformat(str(value or "")).isoformat()
    except ValueError:
        return None


def get_lessons(student_id, limit=None):
    student_id = parse_student_id(student_id)
    if student_id is None or get_student(student_id) is None:
        return []

    init_progress_db()
    query = """
        SELECT lessons.id, lessons.lesson_date, lessons.title, lessons.notes,
               lessons.created_at, lessons.updated_at, COUNT(lesson_vocabulary.vocabulary_word) AS vocabulary_count
        FROM lessons
        LEFT JOIN lesson_vocabulary ON lesson_vocabulary.lesson_id = lessons.id
        WHERE lessons.student_id = ?
        GROUP BY lessons.id
        ORDER BY lessons.lesson_date DESC, lessons.id DESC
    """
    parameters = [student_id]
    if limit is not None:
        query += " LIMIT ?"
        parameters.append(max(0, int(limit)))
    with get_progress_connection() as connection:
        return [row_to_dict(row) for row in connection.execute(query, parameters)]


def get_lesson(student_id, lesson_id):
    student_id = parse_student_id(student_id)
    try:
        lesson_id = int(lesson_id)
    except (TypeError, ValueError):
        return None
    if student_id is None or lesson_id <= 0 or get_student(student_id) is None:
        return None

    init_progress_db()
    with get_progress_connection() as connection:
        return row_to_dict(connection.execute(
            """
            SELECT id, lesson_date, title, notes, created_at, updated_at
            FROM lessons WHERE id = ? AND student_id = ?
            """,
            (lesson_id, student_id),
        ).fetchone())


def create_lesson(student_id, lesson_date, title="", notes=""):
    student_id = parse_student_id(student_id)
    normalized_date = normalize_lesson_date(lesson_date)
    if student_id is None or normalized_date is None or get_student(student_id) is None:
        return None

    now = datetime.now().isoformat(timespec="seconds")
    with get_progress_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO lessons (student_id, lesson_date, title, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (student_id, normalized_date, str(title or "").strip(), str(notes or "").strip(), now, now),
        )
    return get_lesson(student_id, cursor.lastrowid)


def update_lesson(student_id, lesson_id, lesson_date, title="", notes=""):
    lesson = get_lesson(student_id, lesson_id)
    normalized_date = normalize_lesson_date(lesson_date)
    if lesson is None or normalized_date is None:
        return False

    with get_progress_connection() as connection:
        connection.execute(
            """
            UPDATE lessons SET lesson_date = ?, title = ?, notes = ?, updated_at = ?
            WHERE id = ? AND student_id = ?
            """,
            (normalized_date, str(title or "").strip(), str(notes or "").strip(),
             datetime.now().isoformat(timespec="seconds"), lesson["id"], parse_student_id(student_id)),
        )
    return True


def get_lesson_vocabulary_entries(student_id, lesson_id):
    lesson = get_lesson(student_id, lesson_id)
    if lesson is None:
        return []

    with get_progress_connection() as connection:
        words = [row["vocabulary_word"] for row in connection.execute(
            "SELECT vocabulary_word FROM lesson_vocabulary WHERE lesson_id = ? ORDER BY vocabulary_word",
            (lesson["id"],),
        )]
    entries = []
    seen_words = set()
    for word in words:
        entry = get_dictionary_entry(word)
        if entry and entry["word"] not in seen_words:
            entries.append(entry)
            seen_words.add(entry["word"])
    return entries


def add_lesson_vocabulary(student_id, lesson_id, vocabulary_word):
    lesson = get_lesson(student_id, lesson_id)
    word = canonicalize_dictionary_word(vocabulary_word)
    if lesson is None:
        return "Choose a valid lesson first."
    if word not in DICTIONARY_ENTRIES_BY_WORD:
        return "Lesson vocabulary must be an existing built-in dictionary word."

    with get_progress_connection() as connection:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO lesson_vocabulary (lesson_id, vocabulary_word) VALUES (?, ?)",
            (lesson["id"], word),
        )
    return None if cursor.rowcount else "This word is already in the lesson."


def remove_lesson_vocabulary(student_id, lesson_id, vocabulary_word):
    lesson = get_lesson(student_id, lesson_id)
    if lesson is None:
        return False
    with get_progress_connection() as connection:
        for word in dictionary_reference_forms(vocabulary_word):
            connection.execute(
                "DELETE FROM lesson_vocabulary WHERE lesson_id = ? AND vocabulary_word = ?",
                (lesson["id"], word),
            )
    return True


def get_latest_lesson_entries(student_id):
    lessons = get_lessons(student_id, limit=1)
    return get_lesson_vocabulary_entries(student_id, lessons[0]["id"]) if lessons else []


def get_saved_vocabulary_entries(student_id):
    student_id = parse_student_id(student_id)
    if student_id is None or get_student(student_id) is None:
        return []

    init_progress_db()
    with get_progress_connection() as connection:
        saved_words = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT vocabulary_word, source, entry_json
                FROM saved_vocabulary
                WHERE student_id = ?
                ORDER BY saved_at DESC, vocabulary_word
                """,
                (student_id,),
            )
        ]
    entries = []
    seen_words = set()
    for saved_word in saved_words:
        if saved_word["source"] == "dictionary":
            entry = get_dictionary_entry(saved_word["vocabulary_word"])
        else:
            entry = deserialize_saved_ai_entry(saved_word["entry_json"])
        if entry and entry["word"] not in seen_words:
            entries.append(entry)
            seen_words.add(entry["word"])
    return entries


def save_vocabulary(student_id, vocabulary_word):
    student_id = parse_student_id(student_id)
    word = canonicalize_dictionary_word(vocabulary_word)
    if student_id is None or word not in DICTIONARY_ENTRIES_BY_WORD or get_student(student_id) is None:
        return False

    init_progress_db()
    with get_progress_connection() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO saved_vocabulary (student_id, vocabulary_word, saved_at)
            VALUES (?, ?, ?)
            """,
            (student_id, word, datetime.now().isoformat(timespec="seconds")),
        )
    if cursor.rowcount:
        ensure_new_review_schedule(student_id, word)
    return True


def unsave_vocabulary(student_id, vocabulary_word):
    student_id = parse_student_id(student_id)
    word = canonicalize_dictionary_word(vocabulary_word)
    if student_id is None or not word or get_student(student_id) is None:
        return False

    init_progress_db()
    with get_progress_connection() as connection:
        for reference_word in dictionary_reference_forms(word):
            connection.execute(
                "DELETE FROM saved_vocabulary WHERE student_id = ? AND vocabulary_word = ?",
                (student_id, reference_word),
            )
    return True


def is_vocabulary_saved(student_id, vocabulary_word):
    student_id = parse_student_id(student_id)
    word = canonicalize_dictionary_word(vocabulary_word)
    if student_id is None or not word or get_student(student_id) is None:
        return False

    init_progress_db()
    with get_progress_connection() as connection:
        return any(
            connection.execute(
                "SELECT 1 FROM saved_vocabulary WHERE student_id = ? AND vocabulary_word = ?",
                (student_id, reference_word),
            ).fetchone() is not None
            for reference_word in dictionary_reference_forms(word)
        )


def normalize_saved_ai_entry(result):
    if not isinstance(result, dict):
        return None

    word = str(result.get("word", "")).strip()
    traditional = str(result.get("traditional", word)).strip() or word
    word, traditional = normalize_ai_word_forms(word, word, traditional)
    examples = []
    for example in result.get("examples", [])[:2]:
        if not isinstance(example, dict):
            continue
        text = str(example.get("text", "")).strip()
        if text:
            examples.append(make_structured_example(text, str(example.get("translation", "")).strip()))

    entry = {
        "word": word,
        "traditional": traditional,
        "pinyin": str(result.get("pinyin", "")).strip() or to_sentence_pinyin(word),
        "english": str(result.get("english", "")).strip(),
        "part_of_speech": normalize_part_of_speech(str(result.get("part_of_speech", "word"))),
        "explanation": str(result.get("explanation", "")).strip(),
        "examples": examples,
        "category": normalize_entry_category(result.get("category")),
    }
    return entry if validate_ai_result(word, entry) else None


def deserialize_saved_ai_entry(entry_json):
    try:
        return normalize_saved_ai_entry(json.loads(entry_json or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def save_ai_vocabulary(student_id, result):
    student_id = parse_student_id(student_id)
    entry = normalize_saved_ai_entry(result)
    if student_id is None or entry is None or get_student(student_id) is None:
        return None
    dictionary_entry = get_dictionary_entry(entry["word"])
    if dictionary_entry:
        return dictionary_entry if save_vocabulary(student_id, dictionary_entry["word"]) else None

    init_progress_db()
    with get_progress_connection() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO saved_vocabulary (student_id, vocabulary_word, saved_at, source, entry_json)
            VALUES (?, ?, ?, 'ai', ?)
            """,
            (
                student_id,
                entry["word"],
                datetime.now().isoformat(timespec="seconds"),
                json.dumps(entry, ensure_ascii=True),
            ),
        )
    if cursor.rowcount:
        ensure_new_review_schedule(student_id, entry["word"])
    return entry


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


def log_sentence_practice_event(student_id, target_word, original_sentence, target_used=None):
    student_id = parse_student_id(student_id)
    word = str(target_word or "").strip()
    sentence = str(original_sentence or "").strip()
    if student_id is None or not word or not sentence or get_student(student_id) is None:
        return False

    init_progress_db()
    with get_progress_connection() as connection:
        connection.execute(
            """
            INSERT INTO sentence_practice_events (
                student_id, target_word, original_sentence, target_used, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                student_id,
                word,
                sentence,
                None if target_used is None else int(bool(target_used)),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return True


def get_conversation_turns(student_id, conversation_id):
    student_id = parse_student_id(student_id)
    session_id = str(conversation_id or "").strip()
    if student_id is None or not session_id or get_student(student_id) is None:
        return []

    init_progress_db()
    with get_progress_connection() as connection:
        turns = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT prompt, learner_answer, improved_answer, created_at
                FROM conversation_turns
                WHERE student_id = ? AND conversation_id = ?
                ORDER BY id ASC
                """,
                (student_id, session_id),
            )
        ]
    for turn in turns:
        turn["prompt"] = clean_generated_mandarin_sentence(turn["prompt"])
        if turn["improved_answer"]:
            turn["improved_answer"] = apply_common_mandarin_verb_corrections(
                clean_generated_mandarin_sentence(turn["improved_answer"])
            )
        turn["improvement_matches_original"] = (
            normalize_sentence_for_comparison(turn["improved_answer"])
            == normalize_sentence_for_comparison(turn["learner_answer"])
        ) if turn["improved_answer"] else False
    return turns


def log_conversation_turn(student_id, conversation_id, prompt, learner_answer, improved_answer=None):
    student_id = parse_student_id(student_id)
    session_id = str(conversation_id or "").strip()
    prompt = str(prompt or "").strip()
    answer = str(learner_answer or "").strip()
    if student_id is None or not session_id or not prompt or not answer or get_student(student_id) is None:
        return False

    init_progress_db()
    with get_progress_connection() as connection:
        connection.execute(
            """
            INSERT INTO conversation_turns (
                student_id, conversation_id, prompt, learner_answer, improved_answer, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                session_id,
                prompt,
                answer,
                str(improved_answer or "").strip() or None,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return True


def get_daily_conversation_prompt():
    return random.choice(DAILY_CONVERSATION_PROMPTS)


def get_conversation_vocabulary_hint(student_id):
    for source in ("today", "saved"):
        entries = get_quiz_pool(source, student_id)
        if entries:
            entry = entries[0]
            return f"{entry['word']} ({entry['english']})"
    return ""


def review_date_today():
    return datetime.now().date()


def ensure_new_review_schedule(student_id, vocabulary_word):
    student_id = parse_student_id(student_id)
    word = canonicalize_dictionary_word(vocabulary_word)
    if student_id is None or not word or get_student(student_id) is None:
        return

    today = review_date_today()
    init_progress_db()
    with get_progress_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO review_schedules (
                student_id, vocabulary_word, next_review_at, review_interval_days,
                consecutive_correct, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (student_id, word, today.isoformat(), 0, 0, "New", datetime.now().isoformat(timespec="seconds")),
        )


def update_review_schedule(student_id, vocabulary_word, first_attempt_correct):
    student_id = parse_student_id(student_id)
    word = canonicalize_dictionary_word(vocabulary_word)
    if student_id is None or not word or get_student(student_id) is None:
        return

    today = review_date_today()
    init_progress_db()
    with get_progress_connection() as connection:
        existing = connection.execute(
            """
            SELECT review_interval_days, consecutive_correct
            FROM review_schedules
            WHERE student_id = ? AND vocabulary_word = ?
            """,
            (student_id, word),
        ).fetchone()
        if first_attempt_correct:
            consecutive_correct = (existing["consecutive_correct"] if existing else 0) + 1
            if consecutive_correct == 1:
                interval_days = 2
            elif consecutive_correct == 2:
                interval_days = 4
            elif consecutive_correct == 3:
                interval_days = 7
            else:
                interval_days = min(30, max(7, (existing["review_interval_days"] if existing else 7) * 2))
            status = "Mastered" if consecutive_correct >= 4 else ("Review" if consecutive_correct >= 2 else "Learning")
        else:
            consecutive_correct = 0
            interval_days = 1
            status = "Learning"
        connection.execute(
            """
            INSERT INTO review_schedules (
                student_id, vocabulary_word, next_review_at, review_interval_days,
                consecutive_correct, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, vocabulary_word) DO UPDATE SET
                next_review_at = excluded.next_review_at,
                review_interval_days = excluded.review_interval_days,
                consecutive_correct = excluded.consecutive_correct,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                student_id,
                word,
                (today + timedelta(days=interval_days)).isoformat(),
                interval_days,
                consecutive_correct,
                status,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


def record_quiz_attempt(student_id, vocabulary_word, is_correct, interaction_key, quiz_source="all"):
    student_id = parse_student_id(student_id)
    word = canonicalize_dictionary_word(vocabulary_word)
    attempt_key = str(interaction_key or "").strip()
    source = normalize_quiz_source(quiz_source)
    if student_id is None or not word or not attempt_key or get_student(student_id) is None:
        return

    init_progress_db()
    first_attempt_recorded = False
    with get_progress_connection() as connection:
        existing_attempt = connection.execute(
            "SELECT id FROM quiz_attempts WHERE student_id = ? AND interaction_key = ?",
            (student_id, attempt_key),
        ).fetchone()
        values = (
            word,
            int(bool(is_correct)),
            datetime.now().isoformat(timespec="seconds"),
            source,
            student_id,
            attempt_key,
        )
        if existing_attempt:
            connection.execute(
                """
                UPDATE quiz_attempts
                SET vocabulary_word = ?, is_correct = ?, completed_at = ?, quiz_source = ?
                WHERE student_id = ? AND interaction_key = ?
                """,
                values,
            )
        else:
            connection.execute(
                """
                INSERT INTO quiz_attempts (
                    student_id, vocabulary_word, is_correct, first_attempt_correct, completed_at, interaction_key, quiz_source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    word,
                    int(bool(is_correct)),
                    int(bool(is_correct)),
                    datetime.now().isoformat(timespec="seconds"),
                    attempt_key,
                    source,
                ),
            )
            first_attempt_recorded = True
    if first_attempt_recorded:
        update_review_schedule(student_id, word, is_correct)


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


def get_weak_vocabulary_stats(student_id, limit=8):
    student_id = parse_student_id(student_id)
    if student_id is None or get_student(student_id) is None:
        return []

    init_progress_db()
    with get_progress_connection() as connection:
        rows = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT
                    vocabulary_word,
                    COUNT(*) AS attempts,
                    COALESCE(SUM(first_attempt_correct), 0) AS correct,
                    SUM(CASE WHEN first_attempt_correct = 0 THEN 1 ELSE 0 END) AS incorrect
                FROM quiz_attempts
                WHERE student_id = ?
                GROUP BY vocabulary_word
                HAVING SUM(CASE WHEN first_attempt_correct = 0 THEN 1 ELSE 0 END) > 0
                ORDER BY
                    CAST(SUM(first_attempt_correct) AS REAL) / COUNT(*) ASC,
                    COUNT(*) DESC,
                    vocabulary_word ASC
                LIMIT ?
                """,
                (student_id, limit),
            )
        ]

    entries_by_word = {entry["word"]: entry for entry in get_quiz_entries()}
    entries_by_word.update({entry["word"]: entry for entry in get_saved_vocabulary_entries(student_id)})
    stats = []
    for row in rows:
        entry = entries_by_word.get(row["vocabulary_word"], {})
        attempts = row["attempts"]
        stats.append(
            {
                "word": row["vocabulary_word"],
                "traditional": entry.get("traditional", traditionalize_known_simplified_text(row["vocabulary_word"])),
                "pinyin": entry.get("pinyin", to_sentence_pinyin(row["vocabulary_word"])),
                "correct": row["correct"],
                "incorrect": row["incorrect"],
                "attempts": attempts,
                "accuracy": round((row["correct"] / attempts) * 100) if attempts else 0,
            }
        )
    return stats


def get_weak_vocabulary_entries(student_id):
    weak_words = {item["word"] for item in get_weak_vocabulary_stats(student_id, limit=100)}
    entries_by_word = {entry["word"]: entry for entry in get_quiz_entries()}
    entries_by_word.update({entry["word"]: entry for entry in get_saved_vocabulary_entries(student_id)})
    return [entries_by_word[word] for word in weak_words if word in entries_by_word]


def get_due_review_entries(student_id):
    student_id = parse_student_id(student_id)
    if student_id is None or get_student(student_id) is None:
        return []

    init_progress_db()
    with get_progress_connection() as connection:
        due_rows = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT vocabulary_word, next_review_at, status
                FROM review_schedules
                WHERE student_id = ? AND next_review_at <= ?
                ORDER BY next_review_at ASC, vocabulary_word ASC
                """,
                (student_id, review_date_today().isoformat()),
            )
        ]

    entries_by_word = {entry["word"]: entry for entry in get_quiz_entries()}
    entries_by_word.update({entry["word"]: entry for entry in get_saved_vocabulary_entries(student_id)})
    due_entries = []
    for row in due_rows:
        entry = entries_by_word.get(row["vocabulary_word"])
        if entry:
            due_entries.append({**entry, "next_review_at": row["next_review_at"], "review_status": row["status"]})
    return due_entries


def get_recent_search_entries(student_id):
    student_id = parse_student_id(student_id)
    if student_id is None or get_student(student_id) is None:
        return []

    init_progress_db()
    with get_progress_connection() as connection:
        events = [
            row_to_dict(row)
            for row in connection.execute(
                """
                SELECT word, traditional, pinyin, english
                FROM search_events
                WHERE student_id = ? AND id IN (
                    SELECT MAX(id)
                    FROM search_events
                    WHERE student_id = ? AND word IS NOT NULL AND word != ''
                    GROUP BY word
                )
                ORDER BY id DESC
                LIMIT 30
                """,
                (student_id, student_id),
            )
        ]

    entries_by_word = {entry["word"]: entry for entry in get_quiz_entries()}
    entries_by_word.update({entry["word"]: entry for entry in get_saved_vocabulary_entries(student_id)})
    entries = []
    for event in events:
        word = str(event["word"] or "").strip()
        entry = entries_by_word.get(word)
        if entry is None:
            pinyin = str(event["pinyin"] or "").strip()
            english = str(event["english"] or "").strip()
            if not pinyin or not english:
                continue
            entry = {
                "word": word,
                "traditional": str(event["traditional"] or word).strip() or word,
                "pinyin": pinyin,
                "english": english,
                "part_of_speech": "word",
                "explanation": "",
                "examples": [],
            }
        entries.append(entry)
    return entries


def get_quiz_pool(source, student_id):
    if source == "recent":
        return get_recent_search_entries(student_id)
    if source == "saved":
        return get_saved_vocabulary_entries(student_id)
    if source == "review":
        return get_review_mistake_entries(student_id)
    if source == "today":
        return get_due_review_entries(student_id)
    if source == "lesson":
        return get_latest_lesson_entries(student_id)
    return get_quiz_entries()


def normalize_sentence_source(value):
    return value if value in {"saved", "today", "recent", "lesson"} else "saved"


def get_sentence_practice_pool(source, student_id):
    return get_quiz_pool(normalize_sentence_source(source), student_id)


def choose_sentence_target(source, student_id, requested_word=None):
    pool = get_sentence_practice_pool(source, student_id)
    requested_word = str(requested_word or "").strip()
    if requested_word:
        return next((entry for entry in pool if entry["word"] == requested_word), None)
    return random.choice(pool) if pool else None


def get_quiz_pool_entry(student_id, vocabulary_word):
    word = canonicalize_dictionary_word(vocabulary_word)
    entries_by_word = {entry["word"]: entry for entry in get_quiz_entries()}
    entries_by_word.update({entry["word"]: entry for entry in get_saved_vocabulary_entries(student_id)})
    return entries_by_word.get(word)


def keep_active_quiz_entry(student_id, quiz_pool, quiz_pool_words, question_word):
    """Keep a submitted question available while a live source changes after scoring."""
    if question_word not in set(quiz_pool_words):
        return quiz_pool
    if any(entry["word"] == question_word for entry in quiz_pool):
        return quiz_pool

    active_entry = get_quiz_pool_entry(student_id, question_word)
    return quiz_pool + [active_entry] if active_entry else quiz_pool


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
        "weak_words": [],
        "due_reviews": [],
        "recent_lessons": [],
        "weekly_summary": None,
    }


def get_weekly_improving_vocabulary(student_id, start_day, end_day, limit=3):
    student_id = parse_student_id(student_id)
    if student_id is None or get_student(student_id) is None:
        return []

    with get_progress_connection() as connection:
        rows = [row_to_dict(row) for row in connection.execute(
            """
            SELECT vocabulary_word,
                   SUM(CASE WHEN substr(completed_at, 1, 10) BETWEEN ? AND ? THEN first_attempt_correct ELSE 0 END) AS recent_correct,
                   SUM(CASE WHEN substr(completed_at, 1, 10) BETWEEN ? AND ? THEN 1 ELSE 0 END) AS recent_attempted,
                   SUM(CASE WHEN substr(completed_at, 1, 10) < ? THEN first_attempt_correct ELSE 0 END) AS earlier_correct,
                   SUM(CASE WHEN substr(completed_at, 1, 10) < ? THEN 1 ELSE 0 END) AS earlier_attempted
            FROM quiz_attempts
            WHERE student_id = ? AND substr(completed_at, 1, 10) <= ?
            GROUP BY vocabulary_word
            """,
            (start_day, end_day, start_day, end_day, start_day, start_day, student_id, end_day),
        )]

    improving_words = []
    for row in rows:
        if row["recent_attempted"] < 2 or row["earlier_attempted"] < 2:
            continue
        recent_accuracy = row["recent_correct"] / row["recent_attempted"]
        earlier_accuracy = row["earlier_correct"] / row["earlier_attempted"]
        if recent_accuracy <= earlier_accuracy:
            continue
        entry = get_dictionary_entry(row["vocabulary_word"])
        if entry:
            improving_words.append({
                "word": entry["word"],
                "traditional": entry.get("traditional", entry["word"]),
                "pinyin": entry["pinyin"],
                "recent_accuracy": round(recent_accuracy * 100),
                "earlier_accuracy": round(earlier_accuracy * 100),
            })
    return sorted(
        improving_words,
        key=lambda item: (item["recent_accuracy"] - item["earlier_accuracy"], item["recent_accuracy"]),
        reverse=True,
    )[:limit]


def get_weekly_progress_summary(student_id, today=None):
    student_id = parse_student_id(student_id)
    if student_id is None or get_student(student_id) is None:
        return None

    end_date = today or review_date_today()
    start_date = end_date - timedelta(days=6)
    start_day = start_date.isoformat()
    end_day = end_date.isoformat()
    window_parameters = (student_id, start_day, end_day)

    with get_progress_connection() as connection:
        quiz_metrics = row_to_dict(connection.execute(
            """
            SELECT COUNT(*) AS attempted,
                   COALESCE(SUM(first_attempt_correct), 0) AS correct,
                   COUNT(DISTINCT vocabulary_word) AS vocabulary_reviewed,
                   COALESCE(SUM(CASE WHEN quiz_source = 'today' AND is_correct = 1 THEN 1 ELSE 0 END), 0) AS review_today_completions
            FROM quiz_attempts
            WHERE student_id = ? AND substr(completed_at, 1, 10) BETWEEN ? AND ?
            """,
            window_parameters,
        ).fetchone())
        saved_vocabulary = connection.execute(
            "SELECT COUNT(*) AS count FROM saved_vocabulary WHERE student_id = ? AND substr(saved_at, 1, 10) BETWEEN ? AND ?",
            window_parameters,
        ).fetchone()["count"]
        sentence_practices = connection.execute(
            "SELECT COUNT(*) AS count FROM sentence_practice_events WHERE student_id = ? AND substr(created_at, 1, 10) BETWEEN ? AND ?",
            window_parameters,
        ).fetchone()["count"]
        conversation_metrics = row_to_dict(connection.execute(
            """
            SELECT COUNT(*) AS turns, COUNT(DISTINCT conversation_id) AS sessions
            FROM conversation_turns
            WHERE student_id = ? AND substr(created_at, 1, 10) BETWEEN ? AND ?
            """,
            window_parameters,
        ).fetchone())
        lessons_added = connection.execute(
            "SELECT COUNT(*) AS count FROM lessons WHERE student_id = ? AND substr(created_at, 1, 10) BETWEEN ? AND ?",
            window_parameters,
        ).fetchone()["count"]
        recent_lessons = [row_to_dict(row) for row in connection.execute(
            """
            SELECT lessons.id, lessons.lesson_date, lessons.title,
                   COUNT(lesson_vocabulary.vocabulary_word) AS vocabulary_count
            FROM lessons
            LEFT JOIN lesson_vocabulary ON lesson_vocabulary.lesson_id = lessons.id
            WHERE lessons.student_id = ? AND lessons.lesson_date BETWEEN ? AND ?
            GROUP BY lessons.id
            ORDER BY lessons.lesson_date DESC, lessons.id DESC
            LIMIT 3
            """,
            window_parameters,
        )]
        weekly_quiz_words = {
            row["vocabulary_word"] for row in connection.execute(
                """
                SELECT DISTINCT vocabulary_word FROM quiz_attempts
                WHERE student_id = ? AND substr(completed_at, 1, 10) BETWEEN ? AND ?
                """,
                window_parameters,
            )
        }

    attempted = quiz_metrics["attempted"]
    weak_words = [
        item for item in get_weak_vocabulary_stats(student_id, limit=100)
        if item["word"] in weekly_quiz_words
    ][:3]
    improving_words = get_weekly_improving_vocabulary(student_id, start_day, end_day)
    activity_count = (
        attempted + saved_vocabulary + sentence_practices + conversation_metrics["turns"] + lessons_added
    )
    return {
        "start_day": start_day,
        "end_day": end_day,
        "has_activity": bool(activity_count),
        "quiz_attempted": attempted,
        "quiz_correct": quiz_metrics["correct"],
        "quiz_accuracy": round((quiz_metrics["correct"] / attempted) * 100) if attempted else 0,
        "vocabulary_reviewed": quiz_metrics["vocabulary_reviewed"],
        "review_today_completions": quiz_metrics["review_today_completions"],
        "saved_vocabulary": saved_vocabulary,
        "sentence_practices": sentence_practices,
        "conversation_turns": conversation_metrics["turns"],
        "conversation_sessions": conversation_metrics["sessions"],
        "lessons_added": lessons_added,
        "recent_lessons": recent_lessons,
        "weak_words": weak_words,
        "improving_words": improving_words,
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

    weak_words = get_weak_vocabulary_stats(student_id)
    due_reviews = get_due_review_entries(student_id)
    recent_lessons = get_lessons(student_id, limit=3)
    weekly_summary = get_weekly_progress_summary(student_id)
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
        "weak_words": weak_words,
        "due_reviews": due_reviews,
        "recent_lessons": recent_lessons,
        "weekly_summary": weekly_summary,
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


@app.template_filter("display_entry_pair")
def display_entry_pair(word, traditional=None):
    simplified = str(word or "").strip()
    traditional_text = str(traditional or simplified).strip() or simplified
    return simplified if simplified == traditional_text else f"{simplified} / {traditional_text}"


def query_prefers_traditional(query, vocabulary_word):
    simplified_word = simplify_known_traditional_text(str(vocabulary_word or ""))
    for query_part in split_batch_queries(query):
        query_word = clean_ai_word_form(query_part)
        if not contains_chinese(query_word) or query_word == simplified_word:
            continue
        if simplified_word in {
            simplify_known_traditional_text(query_word),
            TO_SIMPLIFIED_TAIWAN.convert(query_word),
        }:
            return True
    return False


@app.template_filter("prefers_traditional")
def prefers_traditional_filter(query, vocabulary_word):
    return query_prefers_traditional(query, vocabulary_word)


def get_entry_sentence_forms(text, vocabulary_word, vocabulary_traditional):
    simplified = simplify_known_traditional_text(str(text or ""))
    word = simplify_known_traditional_text(str(vocabulary_word or ""))
    traditional_word = str(vocabulary_traditional or "").strip()
    taiwan_word = traditionalize_known_simplified_text(word)
    if word and traditional_word and traditional_word != taiwan_word:
        traditional = TO_TRADITIONAL_CHARACTERS.convert(simplified)
        generic_word = TO_TRADITIONAL_CHARACTERS.convert(word)
        traditional = traditional.replace(generic_word, traditional_word)
    else:
        traditional = traditionalize_known_simplified_text(simplified)
    return simplified, traditional


@app.template_filter("display_example_pair")
def display_example_pair(text, query, vocabulary_word, vocabulary_traditional):
    simplified, traditional = get_entry_sentence_forms(text, vocabulary_word, vocabulary_traditional)
    if simplified == traditional:
        return simplified
    if query_prefers_traditional(query, vocabulary_word):
        return f"{traditional} / {simplified}"
    return f"{simplified} / {traditional}"


@app.template_filter("display_example_pinyin")
def display_example_pinyin(text, query, vocabulary_word, vocabulary_traditional):
    simplified, traditional = get_entry_sentence_forms(text, vocabulary_word, vocabulary_traditional)
    simplified_pinyin = to_sentence_pinyin(simplified)
    traditional_pinyin = to_sentence_pinyin(traditional)
    if simplified_pinyin == traditional_pinyin:
        return simplified_pinyin
    if query_prefers_traditional(query, vocabulary_word):
        return f"{traditional_pinyin} / {simplified_pinyin}"
    return f"{simplified_pinyin} / {traditional_pinyin}"


@app.template_filter("display_pinyin_pair")
def display_pinyin_pair(pinyin, word, traditional=None, traditional_first=False):
    word_text = str(word or "").strip()
    primary = PINYIN_PHRASE_OVERRIDES.get(word_text, str(pinyin or "").strip())
    traditional_word = str(traditional or "").strip()
    if not traditional_word or traditional_word == word_text or not contains_chinese(traditional_word):
        return primary

    traditional_pinyin = to_sentence_pinyin(traditional_word)
    if not traditional_pinyin or traditional_pinyin == primary:
        return primary
    return f"{traditional_pinyin} / {primary}" if traditional_first else f"{primary} / {traditional_pinyin}"


def add_query_display_fields(entry, query):
    word = str(entry.get("word", ""))
    traditional = str(entry.get("traditional", word))
    traditional_first = query_prefers_traditional(query, word)
    entry["display_word"] = traditional if traditional_first else word
    entry["display_secondary_word"] = word if traditional_first and word != traditional else (
        traditional if not traditional_first and traditional != word else ""
    )
    entry["display_pinyin"] = display_pinyin_pair(
        entry.get("pinyin", ""), word, traditional, traditional_first
    )
    for example in entry.get("examples", []):
        example["display_text"] = display_example_pair(example.get("text", ""), query, word, traditional)
        example["display_pinyin"] = display_example_pinyin(example.get("text", ""), query, word, traditional)
    return entry


def clean_ai_word_form(text):
    cleaned = re.sub(r"\([^)]*\)", "", text).strip()
    if not contains_chinese(cleaned):
        return cleaned
    return "".join(char for char in cleaned if "\u4e00" <= char <= "\u9fff")


def normalize_ai_word_forms(query, word, traditional):
    query_word = clean_ai_word_form(query)
    word = clean_ai_word_form(word)
    traditional = clean_ai_word_form(traditional) or word

    if contains_chinese(word):
        word = simplify_known_traditional_text(word)
        traditional = traditionalize_known_simplified_text(word)
    elif contains_chinese(traditional):
        word = simplify_known_traditional_text(traditional)
        traditional = traditionalize_known_simplified_text(word)

    if (
        contains_chinese(query_word)
        and query_word != word
        and simplify_known_traditional_text(query_word) == word
    ):
        traditional = query_word

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
    normalized_query = normalize_lookup_query(query).lower()
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
        aliases = entry.get("aliases", [])
        search_alias_pinyin = entry.get("search_alias_pinyin", [])
        english = entry["english"].lower()

        english_parts = {alias.strip() for alias in re.split(r"[;/]", english) if alias.strip()}
        english_aliases = english_parts | {alias.removeprefix("to ").strip() for alias in english_parts}
        if (
            normalized_query == word
            or normalized_query == traditional
            or normalized_query in aliases
            or normalized_query_no_tones == search_pinyin
            or normalized_query_no_tones in search_alias_pinyin
            or normalized_query == english
            or normalized_query in english_aliases
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
        aliases = entry.get("aliases", [])
        search_alias_pinyin = entry.get("search_alias_pinyin", [])
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

        if normalized_query == word or normalized_query == traditional or normalized_query in aliases:
            score = (0, len(word))
        elif normalized_query_no_tones == search_pinyin or normalized_query_no_tones in search_alias_pinyin:
            score = (1, len(search_pinyin))
        elif normalized_query == english:
            score = (2, len(english))
        elif query_is_single_char:
            if (
                word.startswith(normalized_query)
                or traditional.startswith(normalized_query)
                or any(alias.startswith(normalized_query) for alias in aliases)
            ):
                score = (3, min(len(word), len(traditional)))
            elif search_pinyin.startswith(normalized_query_no_tones) or any(
                alias_pinyin.startswith(normalized_query_no_tones) for alias_pinyin in search_alias_pinyin
            ):
                score = (4, len(search_pinyin))
        elif (
            word.startswith(normalized_query)
            or traditional.startswith(normalized_query)
            or any(alias.startswith(normalized_query) for alias in aliases)
        ):
            score = (3, min(len(word), len(traditional)))
        elif search_pinyin.startswith(normalized_query_no_tones) or any(
            alias_pinyin.startswith(normalized_query_no_tones) for alias_pinyin in search_alias_pinyin
        ):
            score = (4, len(search_pinyin))
        elif english.startswith(normalized_query):
            score = (5, len(english))
        elif normalized_query in word or normalized_query in traditional or any(
            normalized_query in alias for alias in aliases
        ):
            score = (6, min(len(word), len(traditional)))
        elif (
            normalized_query_no_tones in search_pinyin
            or any(normalized_query_no_tones in alias_pinyin for alias_pinyin in search_alias_pinyin)
        ) and not query_is_short_ascii:
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
        query = normalize_lookup_query(raw_query)
        query_key = normalize_query_key(query)
        if not query or query_key in seen:
            continue
        queries.append(query)
        seen.add(query_key)
    return queries


def normalize_lookup_query(query):
    return BATCH_LIST_PREFIX_PATTERN.sub("", str(query or "")).strip()


def batch_search_entries(text, category="all"):
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
        for entry in filter_entries_by_category(matches, category):
            if entry["word"] in seen_words:
                continue
            results.append(entry)
            seen_words.add(entry["word"])
            added_match = True

    return results, missing_queries, ai_queries


def get_batch_card_orders(text, category="all"):
    entry_orders = {}
    ai_orders = {}
    seen_words = set()
    order = 0

    for query in split_batch_queries(text):
        matches = search_entries(query)
        if not matches:
            if is_meaningful_query(query):
                ai_orders[query] = order
                order += 1
            continue

        added_match = False
        for entry in filter_entries_by_category(matches, category):
            if entry["word"] in seen_words:
                continue
            entry_orders[entry["word"]] = order
            seen_words.add(entry["word"])
            order += 1
            added_match = True
    return entry_orders, ai_orders


def is_meaningful_query(query):
    normalized_query = query.strip().lower()
    if not normalized_query:
        return False

    normalized_query_no_tones = remove_tone_marks(normalized_query)
    return any(char.isalpha() or "\u4e00" <= char <= "\u9fff" for char in normalized_query_no_tones)


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

    if query_is_chinese:
        query_word = clean_ai_word_form(query)
        simplified_query = simplify_known_traditional_text(query_word)
        simplified_forms = {
            simplify_known_traditional_text(word),
            simplify_known_traditional_text(traditional),
        }
        if not query_word or simplified_query not in simplified_forms:
            return False

    if query_is_chinese and not english:
        return False

    return True


def request_ollama_json(system_prompt, user_prompt):
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
    http_request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(http_request, timeout=OLLAMA_TIMEOUT) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, socket.timeout, urllib.error.URLError, json.JSONDecodeError) as exc:
        return None, f"AI is unavailable right now. Start Ollama and load `{OLLAMA_MODEL}`. ({exc})"

    try:
        return json.loads(response_data["message"]["content"]), None
    except (KeyError, TypeError, json.JSONDecodeError):
        return None, "AI is unavailable right now because the local model returned an invalid response."


def fetch_ai_explanation(query):
    system_prompt = (
        "You are a Mandarin tutor for English-speaking beginners. "
        "Return JSON only with these keys: word, traditional, pinyin, english, part_of_speech, category, explanation, examples. "
        "Do not add extra keys. "
        "Use concise beginner-friendly English. "
        "The word field must be the simplified Chinese form of the exact Mandarin word or phrase being explained, not a sentence. "
        "The traditional field must be the traditional Chinese form of the same word or phrase. "
        "If simplified and traditional are the same, use the same value for both fields. "
        "If the input itself is Chinese, the input must match either the simplified word field or the traditional field. "
        "Set part_of_speech to exactly one of: noun, verb, adjective, adverb, phrase, expression, question word, conjunction, modal verb, time word, pronoun, measure word, word. "
        "Set category to exactly one of: basics, actions, time, places, food, people, study, descriptions, grammar, health, technology, everyday. "
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
        parsed, error = request_ollama_json(system_prompt, user_prompt)
        if error:
            return None, error.replace("AI is", "AI explanation is", 1)

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
            "display_pinyin": display_pinyin_pair(pinyin, word, traditional),
            "english": parsed.get("english", "").strip(),
            "part_of_speech": normalize_part_of_speech(parsed.get("part_of_speech", "word")),
            "category": normalize_entry_category(parsed.get("category")),
            "explanation": parsed.get("explanation", "").strip(),
            "examples": examples,
        }

        if validate_ai_result(query, ai_result):
            return ai_result, None

    return None, "AI explanation is unavailable right now because the local model returned a low-quality result."


def normalize_sentence_target_used(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    return None


def normalize_sentence_for_comparison(text):
    simplified = simplify_known_traditional_text(str(text or ""))
    return re.sub(r"[\s,，.。!?！？;；:：]+", "", simplified)


def normalize_mandarin_expression(text):
    match = re.search(r"[\u4e00-\u9fff]+", str(text or ""))
    return match.group(0) if match else ""


def clean_generated_mandarin_sentence(text):
    without_annotations = re.sub(r"[（(][^（）()]*[)）]", "", str(text or ""))
    cleaned = "".join(
        character
        for character in without_annotations
        if "\u4e00" <= character <= "\u9fff" or character.isdigit() or character in "，。！？；：、"
    )
    return re.sub(r"([。！？]){2,}", r"\1", cleaned).strip()


def apply_common_mandarin_verb_corrections(text):
    corrected = str(text or "")
    for beverage in ("咖啡", "茶", "水", "牛奶", "果汁", "汤"):
        corrected = corrected.replace(f"吃{beverage}", f"喝{beverage}")
    return corrected


def normalize_sentence_feedback(target_word, original_sentence, feedback):
    if not isinstance(feedback, dict) or not str(original_sentence or "").strip():
        return None
    target_used = normalize_sentence_target_used(feedback.get("target_used"))
    if target_used is None:
        return None
    for key in ("grammar", "naturalness", "suggested_sentence", "explanation"):
        if not isinstance(feedback.get(key), str) or not feedback[key].strip():
            return None
    suggested_sentence = feedback["suggested_sentence"].strip()
    if not contains_chinese(suggested_sentence):
        return None
    suggestion_matches_original = (
        normalize_sentence_for_comparison(suggested_sentence)
        == normalize_sentence_for_comparison(original_sentence)
    )
    return {
        "target_used": target_used,
        "grammar": feedback["grammar"].strip(),
        "naturalness": feedback["naturalness"].strip(),
        "suggested_sentence": suggested_sentence,
        "suggested_sentence_pinyin": to_sentence_pinyin(suggested_sentence),
        "suggestion_matches_original": suggestion_matches_original,
        "explanation": feedback["explanation"].strip(),
    }


def fetch_sentence_feedback(target_entry, original_sentence):
    target_word = str(target_entry.get("word", "")).strip()
    sentence = str(original_sentence or "").strip()
    if not target_word or not sentence:
        return None, "Write a sentence before checking it."

    system_prompt = (
        "You are a constructive Mandarin tutor for English-speaking beginners. "
        "Return JSON only with these keys: target_used, grammar, naturalness, suggested_sentence, explanation. "
        "Do not add extra keys. target_used must be a JSON boolean. "
        "grammar, naturalness, and explanation must be short, kind, beginner-friendly English. "
        "suggested_sentence must be a complete natural Mandarin sentence using the target word. "
        "Do not call a sentence wrong just because another phrasing is more natural. "
        "When the learner's sentence is acceptable, say so. Do not describe punctuation, Simplified/Traditional conversion, "
        "or identical wording as an improvement. In that case, repeat the learner's wording in suggested_sentence. "
        'Use this exact JSON shape: {"target_used":true,"grammar":"...","naturalness":"...",'
        '"suggested_sentence":"...","explanation":"..."}.'
    )
    for attempt in range(2):
        repair_instruction = ""
        if attempt:
            repair_instruction = (
                "Your previous response was invalid. Return JSON only, with exactly target_used, grammar, naturalness, "
                "suggested_sentence, and explanation. target_used must be true or false, not an explanation. "
                "Every other field must be a non-empty string, and suggested_sentence must be Chinese. "
            )
        user_prompt = (
            f"Target word (Simplified): {target_word}\n"
            f"Target word (Traditional): {target_entry.get('traditional', target_word)}\n"
            f"Target meaning: {target_entry.get('english', '')}\n"
            f"Learner sentence: {sentence}\n"
            f"{repair_instruction}Return valid JSON only."
        )
        feedback, error = request_ollama_json(system_prompt, user_prompt)
        if error:
            return None, error.replace("AI is", "Sentence feedback is", 1)
        normalized_feedback = normalize_sentence_feedback(target_word, sentence, feedback)
        if normalized_feedback:
            return normalized_feedback, None

    return None, "Sentence feedback is unavailable right now because the local model returned a low-quality result."


def normalize_conversation_feedback(learner_answer, feedback):
    if not isinstance(feedback, dict) or not str(learner_answer or "").strip():
        return None
    understandable = normalize_sentence_target_used(feedback.get("understandable"))
    if understandable is None:
        return None
    for key in (
        "grammar",
        "naturalness",
        "improved_answer",
        "explanation",
        "useful_expression",
        "useful_expression_english",
        "follow_up",
        "follow_up_english",
    ):
        if not isinstance(feedback.get(key), str) or not feedback[key].strip():
            return None
    improved_answer = apply_common_mandarin_verb_corrections(
        clean_generated_mandarin_sentence(feedback["improved_answer"])
    )
    follow_up = clean_generated_mandarin_sentence(feedback["follow_up"])
    useful_expression = normalize_mandarin_expression(feedback["useful_expression"])
    if not contains_chinese(improved_answer) or not contains_chinese(follow_up) or not useful_expression:
        return None
    return {
        "understandable": understandable,
        "grammar": feedback["grammar"].strip(),
        "naturalness": feedback["naturalness"].strip(),
        "improved_answer": improved_answer,
        "improved_answer_pinyin": to_sentence_pinyin(improved_answer),
        "explanation": feedback["explanation"].strip(),
        "useful_expression": useful_expression,
        "useful_expression_english": feedback["useful_expression_english"].strip(),
        "useful_expression_is_chinese": True,
        "useful_expression_pinyin": to_sentence_pinyin(useful_expression),
        "follow_up": follow_up,
        "follow_up_pinyin": to_sentence_pinyin(follow_up),
        "follow_up_english": feedback["follow_up_english"].strip(),
        "improvement_matches_original": (
            normalize_sentence_for_comparison(improved_answer)
            == normalize_sentence_for_comparison(learner_answer)
        ),
    }


def fetch_conversation_feedback(prompt, learner_answer, vocabulary_hint="", previous_turns=None):
    prompt = str(prompt or "").strip()
    answer = str(learner_answer or "").strip()
    if not prompt or not answer:
        return None, "Write an answer before checking it."

    history = previous_turns or []
    history_text = "\n".join(
        f"Prompt: {turn['prompt']}\nLearner: {turn['learner_answer']}"
        for turn in history[-3:]
    ) or "No previous turns."
    system_prompt = (
        "You are a supportive Mandarin conversation tutor for English-speaking beginners. "
        "Return JSON only with these keys: understandable, grammar, naturalness, improved_answer, explanation, "
        "useful_expression, useful_expression_english, follow_up, follow_up_english. Do not add extra keys. "
        "understandable must be a JSON boolean. All other values must be short non-empty strings. "
        "grammar, naturalness, and explanation must be constructive beginner-friendly English. "
        "Base every statement only on the current Mandarin prompt and the learner answer. "
        "Never say the learner used, liked, or mentioned a concrete word that is absent from the learner answer. "
        "A short relevant answer, such as a food or drink name, is understandable; gently offer a full sentence without calling it wrong. "
        "Do not over-correct an understandable, natural learner answer. Do not treat punctuation or Simplified/Traditional "
        "conversion as an error. improved_answer and follow_up must be Mandarin Chinese. "
        "useful_expression must be a Mandarin word or short phrase only, with no pinyin, English, or translation. "
        "useful_expression_english must be its short English meaning. "
        "follow_up must be one short, relevant beginner-friendly daily-life question. follow_up_english must translate it. "
        'Use this exact JSON shape: {"understandable":true,"grammar":"...","naturalness":"...",'
        '"improved_answer":"...","explanation":"...","useful_expression":"...","useful_expression_english":"...",'
        '"follow_up":"...","follow_up_english":"..."}.'
    )
    for attempt in range(2):
        repair_instruction = ""
        if attempt:
            repair_instruction = (
                "Your previous response was invalid. Return JSON only with exactly the required keys. "
                "understandable must be true or false; every other field must be a non-empty string; "
                "improved_answer, useful_expression, and follow_up must contain only Mandarin Chinese. "
            )
        user_prompt = (
            f"Current Mandarin prompt: {prompt}\n"
            f"Learner answer: {answer}\n"
            f"Previous turns:\n{history_text}\n"
            f"{repair_instruction}Return valid JSON only."
        )
        feedback, error = request_ollama_json(system_prompt, user_prompt)
        if error:
            return None, error.replace("AI is", "Conversation feedback is", 1)
        normalized_feedback = normalize_conversation_feedback(answer, feedback)
        if normalized_feedback:
            return normalized_feedback, None

    return None, "Conversation feedback is unavailable right now because the local model returned a low-quality result."


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


def build_quiz(question_word=None, exclude_word=None, choices=None, recent_words=None, allowed_words=None, pool_entries=None):
    correct_entry = None
    recent_words = recent_words or []
    all_quiz_entries = get_quiz_entries()
    quiz_entries = pool_entries if pool_entries is not None else all_quiz_entries
    if allowed_words is not None:
        allowed_word_set = set(allowed_words)
        quiz_entries = [entry for entry in quiz_entries if entry["word"] in allowed_word_set]

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
    return value if value in {"all", "recent", "saved", "review", "today", "lesson"} else "all"


def normalize_quiz_type(value):
    return "listening" if value == "listening" else "meaning"


def build_next_quiz(quiz_source, student_id, question_word, quiz_pool_words, recent_words, category="all"):
    if quiz_source == "all":
        return (
            build_quiz(
                exclude_word=question_word,
                recent_words=recent_words,
                pool_entries=filter_entries_by_category(get_quiz_pool("all", student_id), category),
            ),
            quiz_pool_words,
        )

    remaining_words = [word for word in quiz_pool_words if word != question_word]
    allowed_words = set(remaining_words)
    next_pool = [
        entry for entry in filter_entries_by_category(get_quiz_pool(quiz_source, student_id), category)
        if entry["word"] in allowed_words
    ]
    return build_quiz(recent_words=recent_words, pool_entries=next_pool), remaining_words


@app.route("/", methods=["GET", "POST"])
def home():
    mode = request.args.get("mode", "search")
    progress_day = request.args.get("day")
    student_id = parse_student_id(request.form.get("student_id") or request.args.get("student_id"))
    students = list_students()
    selected_student = get_student(student_id)
    if selected_student is None:
        student_id = None
    category = normalize_category(request.form.get("category") or request.args.get("category"))
    recent_words = request.args.getlist("recent_word")
    query = ""
    results = []
    batch_missing = []
    batch_ai_queries = []
    batch_entry_orders = {}
    batch_ai_orders = {}
    ai_pending = False
    conversion_text = ""
    converted_simplified = ""
    converted_traditional = ""
    sentence_source = normalize_sentence_source(request.form.get("sentence_source") or request.args.get("sentence_source"))
    sentence_target = choose_sentence_target(
        sentence_source,
        student_id,
        request.form.get("target_word") or request.args.get("target_word"),
    )
    sentence_text = ""
    sentence_feedback = None
    sentence_error = None
    lesson_id = request.form.get("lesson_id") or request.args.get("lesson_id")
    lessons = get_lessons(student_id)
    selected_lesson = get_lesson(student_id, lesson_id)
    lesson_vocabulary = get_lesson_vocabulary_entries(student_id, lesson_id)
    lesson_message = ""
    lesson_error = ""
    conversation_id = request.form.get("conversation_id") or request.args.get("conversation_id") or uuid.uuid4().hex
    default_conversation_prompt, default_conversation_prompt_english = get_daily_conversation_prompt()
    conversation_prompt = clean_generated_mandarin_sentence(
        request.form.get("conversation_prompt")
        or request.args.get("conversation_prompt")
        or default_conversation_prompt
    )
    conversation_prompt_english = (
        request.form.get("conversation_prompt_english")
        or request.args.get("conversation_prompt_english")
        or default_conversation_prompt_english
    )
    conversation_answer = ""
    conversation_feedback = None
    conversation_error = None
    conversation_turns = get_conversation_turns(student_id, conversation_id)
    if request.method == "GET" and mode == "batch":
        query = request.args.get("batch_query", "")
        if query:
            results, batch_missing, batch_ai_queries = batch_search_entries(query, category)
            batch_entry_orders, batch_ai_orders = get_batch_card_orders(query, category)
    quiz_source = normalize_quiz_source(request.form.get("quiz_source") or request.args.get("quiz_source"))
    quiz_type = normalize_quiz_type(request.form.get("quiz_type") or request.args.get("quiz_type"))
    quiz_pool_words = request.form.getlist("quiz_pool_word") or request.args.getlist("quiz_pool_word")
    quiz_pool = filter_entries_by_category(get_quiz_pool(quiz_source, student_id), category)
    if quiz_source != "all":
        if quiz_pool_words:
            quiz_pool = [entry for entry in quiz_pool if entry["word"] in set(quiz_pool_words)]
        else:
            quiz_pool_words = [entry["word"] for entry in quiz_pool]
    quiz = build_quiz(
        recent_words=recent_words,
        pool_entries=quiz_pool,
    )
    quiz_source_empty = quiz_source != "all" and not quiz_pool_words
    listening_reveal = False
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
            query = normalize_lookup_query(request.form.get("query", ""))
            results = filter_entries_by_category(search_entries(query), category)
            for entry in results:
                log_progress_event(query, entry, "dictionary", "search", student_id)
            if not results and category == "all" and is_meaningful_query(query):
                ai_pending = True
        elif form_type == "batch":
            mode = "batch"
            query = request.form.get("query", "")
            results, batch_missing, batch_ai_queries = batch_search_entries(query, category)
            batch_entry_orders, batch_ai_orders = get_batch_card_orders(query, category)
            for entry in results:
                log_progress_event(query, entry, "dictionary", "batch", student_id)
        elif form_type == "convert":
            mode = "convert"
            conversion_text = request.form.get("text", "")
            converted_simplified = simplify_known_traditional_text(conversion_text)
            converted_traditional = traditionalize_known_simplified_text(conversion_text)
        elif form_type == "sentence-practice":
            mode = "sentence"
            sentence_source = normalize_sentence_source(request.form.get("sentence_source"))
            sentence_target = choose_sentence_target(
                sentence_source, student_id, request.form.get("target_word")
            )
            sentence_text = request.form.get("sentence", "")
            if sentence_target is None:
                sentence_error = "This vocabulary source has no words to practise yet."
            elif not sentence_text.strip():
                sentence_error = "Write a sentence before checking it."
            else:
                sentence_feedback, sentence_error = fetch_sentence_feedback(sentence_target, sentence_text)
                log_sentence_practice_event(
                    student_id,
                    sentence_target["word"],
                    sentence_text,
                    sentence_feedback["target_used"] if sentence_feedback else None,
                )
        elif form_type == "lesson-create":
            mode = "lessons"
            if student_id is None:
                lesson_error = "Choose a learner before creating a lesson."
            else:
                selected_lesson = create_lesson(
                    student_id,
                    request.form.get("lesson_date"),
                    request.form.get("title"),
                    request.form.get("notes"),
                )
                if selected_lesson is None:
                    lesson_error = "Enter a valid lesson date."
                else:
                    lesson_id = selected_lesson["id"]
                    lesson_message = "Lesson created. Add vocabulary below."
                    lessons = get_lessons(student_id)
                    lesson_vocabulary = []
        elif form_type == "lesson-update":
            mode = "lessons"
            lesson_id = request.form.get("lesson_id")
            if update_lesson(
                student_id,
                lesson_id,
                request.form.get("lesson_date"),
                request.form.get("title"),
                request.form.get("notes"),
            ):
                lesson_message = "Lesson updated."
            else:
                lesson_error = "Enter a valid lesson date."
            selected_lesson = get_lesson(student_id, lesson_id)
            lesson_vocabulary = get_lesson_vocabulary_entries(student_id, lesson_id)
            lessons = get_lessons(student_id)
        elif form_type == "lesson-vocabulary-add":
            mode = "lessons"
            lesson_id = request.form.get("lesson_id")
            lesson_error = add_lesson_vocabulary(student_id, lesson_id, request.form.get("vocabulary_word")) or ""
            lesson_message = "Vocabulary added." if not lesson_error else ""
            selected_lesson = get_lesson(student_id, lesson_id)
            lesson_vocabulary = get_lesson_vocabulary_entries(student_id, lesson_id)
            lessons = get_lessons(student_id)
        elif form_type == "lesson-vocabulary-remove":
            mode = "lessons"
            lesson_id = request.form.get("lesson_id")
            if remove_lesson_vocabulary(student_id, lesson_id, request.form.get("vocabulary_word")):
                lesson_message = "Vocabulary removed from this lesson."
            else:
                lesson_error = "Choose a valid lesson first."
            selected_lesson = get_lesson(student_id, lesson_id)
            lesson_vocabulary = get_lesson_vocabulary_entries(student_id, lesson_id)
            lessons = get_lessons(student_id)
        elif form_type == "conversation":
            mode = "conversation"
            conversation_id = request.form.get("conversation_id") or uuid.uuid4().hex
            conversation_prompt = clean_generated_mandarin_sentence(request.form.get("conversation_prompt", ""))
            conversation_prompt_english = request.form.get("conversation_prompt_english", "")
            conversation_answer = request.form.get("conversation_answer", "")
            conversation_turns = get_conversation_turns(student_id, conversation_id)
            if not conversation_answer.strip():
                conversation_error = "Write an answer before checking it."
            elif not conversation_prompt.strip():
                conversation_error = "Choose a new conversation prompt and try again."
            else:
                conversation_feedback, conversation_error = fetch_conversation_feedback(
                    conversation_prompt,
                    conversation_answer,
                    "",
                    conversation_turns,
                )
                log_conversation_turn(
                    student_id,
                    conversation_id,
                    conversation_prompt,
                    conversation_answer,
                    conversation_feedback["improved_answer"] if conversation_feedback else None,
                )
        elif form_type == "saved-vocabulary":
            mode = request.form.get("return_mode", "saved")
            vocabulary_word = request.form.get("vocabulary_word", "")
            if request.form.get("saved_action") == "save":
                save_vocabulary(student_id, vocabulary_word)
            elif request.form.get("saved_action") == "unsave":
                unsave_vocabulary(student_id, vocabulary_word)

            if mode == "search":
                query = request.form.get("query", "")
                results = filter_entries_by_category(search_entries(query), category) if query else []
            elif mode == "batch":
                query = request.form.get("query", "")
                results, batch_missing, batch_ai_queries = batch_search_entries(query, category) if query else ([], [], [])
                batch_entry_orders, batch_ai_orders = get_batch_card_orders(query, category) if query else ({}, {})
        elif form_type == "quiz":
            mode = "quiz"
            query = request.form.get("query", "")
            results = search_entries(query) if query else []
            question_word = request.form.get("question_word")
            selected_answer = request.form.get("selected_answer", "")
            current_choices = request.form.getlist("choice")
            recent_words = request.form.getlist("recent_word")
            quiz_source = normalize_quiz_source(request.form.get("quiz_source"))
            quiz_type = normalize_quiz_type(request.form.get("quiz_type"))
            category = normalize_category(request.form.get("category"))
            quiz_pool_words = request.form.getlist("quiz_pool_word")
            quiz_pool = filter_entries_by_category(get_quiz_pool(quiz_source, student_id), category)
            if quiz_source != "all":
                quiz_pool = [entry for entry in quiz_pool if entry["word"] in set(quiz_pool_words)]
                quiz_pool = keep_active_quiz_entry(student_id, quiz_pool, quiz_pool_words, question_word)
            quiz_score = {
                "correct": parse_quiz_score(request.form.get("score_correct")),
                "attempted": parse_quiz_score(request.form.get("score_attempted")),
                "question_counted": request.form.get("question_counted") == "1",
            }
            quiz_attempt_key = request.form.get("quiz_attempt_key") or uuid.uuid4().hex
            advance_listening_quiz = request.form.get("advance_listening_quiz") == "1"
            quiz = build_quiz(
                question_word,
                choices=current_choices or None,
                recent_words=recent_words,
                pool_entries=quiz_pool,
            )
            if quiz is None:
                quiz_source_empty = quiz_source != "all"
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
                    quiz_type=quiz_type,
                    quiz_pool_words=quiz_pool_words,
                    quiz_source_empty=quiz_source_empty,
                    listening_reveal=False,
                    recent_words=recent_words,
                    progress_summary=progress_summary,
                    category=category,
                    category_labels=CATEGORY_LABELS,
                )
            if advance_listening_quiz:
                recent_words = (recent_words + [question_word])[-RECENT_QUIZ_LIMIT:]
                quiz, quiz_pool_words = build_next_quiz(
                    quiz_source, student_id, question_word, quiz_pool_words, recent_words, category
                )
                quiz_source_empty = quiz is None
                quiz_attempt_key = uuid.uuid4().hex
            else:
                is_correct = selected_answer == quiz["correct_answer"]
                record_quiz_attempt(student_id, quiz["word"], is_correct, quiz_attempt_key, quiz_source)
                if is_correct:
                    if not quiz_score["question_counted"]:
                        quiz_score["attempted"] += 1
                        quiz_score["correct"] += 1
                    quiz_score["question_counted"] = False
                    if quiz_type == "listening":
                        listening_reveal = True
                    else:
                        recent_words = (recent_words + [question_word])[-RECENT_QUIZ_LIMIT:]
                        quiz, quiz_pool_words = build_next_quiz(
                            quiz_source, student_id, question_word, quiz_pool_words, recent_words, category
                        )
                        quiz_source_empty = quiz is None
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
                        "wrong_traditional": (
                            wrong_entry.get("traditional")
                            or traditionalize_known_simplified_text(wrong_entry["word"])
                        ) if wrong_entry else "",
                        "wrong_pinyin": wrong_entry["pinyin"] if wrong_entry else "",
                    }

    if mode == "progress":
        progress_summary = get_progress_summary(student_id, progress_day)

    conversation_prompt_pinyin = to_sentence_pinyin(conversation_prompt)
    conversation_answer_pinyin = to_sentence_pinyin(conversation_answer) if contains_chinese(conversation_answer) else ""

    saved_entries = filter_entries_by_category(get_saved_vocabulary_entries(student_id), category) if mode == "saved" else []
    saved_words = {entry["word"] for entry in get_saved_vocabulary_entries(student_id)}

    return render_template(
        "index.html",
        mode=mode,
        query=query,
        results=results,
        batch_missing=batch_missing,
        batch_ai_queries=batch_ai_queries,
        batch_entry_orders=batch_entry_orders,
        batch_ai_orders=batch_ai_orders,
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
        quiz_type=quiz_type,
        quiz_pool_words=quiz_pool_words,
        quiz_source_empty=quiz_source_empty,
        listening_reveal=listening_reveal,
        recent_words=recent_words,
        progress_summary=progress_summary,
        saved_entries=saved_entries,
        saved_words=saved_words,
        sentence_source=sentence_source,
        sentence_target=sentence_target,
        sentence_text=sentence_text,
        sentence_feedback=sentence_feedback,
        sentence_error=sentence_error,
        lessons=lessons,
        selected_lesson=selected_lesson,
        lesson_vocabulary=lesson_vocabulary,
        lesson_message=lesson_message,
        lesson_error=lesson_error,
        today_date=date.today().isoformat(),
        conversation_id=conversation_id,
        conversation_prompt=conversation_prompt,
        conversation_prompt_english=conversation_prompt_english,
        conversation_prompt_pinyin=conversation_prompt_pinyin,
        conversation_answer=conversation_answer,
        conversation_answer_pinyin=conversation_answer_pinyin,
        conversation_feedback=conversation_feedback,
        conversation_error=conversation_error,
        conversation_turns=conversation_turns,
        category=category,
        category_labels=CATEGORY_LABELS,
    )


@app.get("/api/ai-explanation")
def ai_explanation():
    query = normalize_lookup_query(request.args.get("query", ""))
    mode = request.args.get("mode", "search")
    student_id = parse_student_id(request.args.get("student_id"))
    if not is_meaningful_query(query):
        return jsonify({"ok": False, "error": "Please enter a real Chinese word, pinyin, or English meaning."}), 400

    result, error = get_ai_explanation(query)
    if error:
        return jsonify({"ok": False, "error": error}), 503

    result = dict(result)
    result["examples"] = [dict(example) for example in result.get("examples", [])]
    add_query_display_fields(result, query)
    result["category"] = get_entry_category(result)
    result["category_label"] = CATEGORY_LABELS[result["category"]]

    log_progress_event(query, result, "ai", mode if mode in {"search", "batch"} else "search", student_id)
    return jsonify({"ok": True, "result": result, "saved": is_vocabulary_saved(student_id, result["word"])})


@app.post("/api/saved-vocabulary")
def saved_vocabulary_api():
    payload = request.get_json(silent=True) or {}
    student_id = parse_student_id(payload.get("student_id"))
    action = payload.get("action")
    if action == "save-ai":
        entry = save_ai_vocabulary(student_id, payload.get("result"))
        if entry is None:
            return jsonify({"ok": False, "error": "Choose a learner and save a valid AI result."}), 400
        return jsonify({"ok": True, "saved": True, "word": entry["word"]})
    if action == "unsave":
        word = str(payload.get("vocabulary_word", "")).strip()
        if not unsave_vocabulary(student_id, word):
            return jsonify({"ok": False, "error": "Choose a learner and a saved word."}), 400
        return jsonify({"ok": True, "saved": False, "word": word})

    return jsonify({"ok": False, "error": "Unsupported saved vocabulary action."}), 400


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
