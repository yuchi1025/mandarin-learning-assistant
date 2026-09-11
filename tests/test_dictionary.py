import json
from pathlib import Path

from pypinyin import Style, lazy_pinyin

from validate_dictionary import validate_entries


DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "dictionary.json"
ALIASES_PATH = Path(__file__).resolve().parent.parent / "data" / "dictionary_aliases.json"
EXPECTED_FIELDS = ["word", "traditional", "pinyin", "english", "part_of_speech", "explanation", "examples"]
PINYIN_WORD_OVERRIDES = {
    "记得": "jì dé",
    "日期": "rì qí",
    "星期": "xīng qí",
    "垃圾": "lè sè",
    "品质": "pǐn zhí",
}


def load_entries():
    return json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))


def test_dictionary_is_valid():
    entries = load_entries()

    assert validate_entries(entries, expected_count=501) == []


def test_dictionary_words_are_unique():
    entries = load_entries()
    words = [entry["word"] for entry in entries]
    traditional_words = [entry["traditional"] for entry in entries]

    assert len(words) == len(set(words))
    assert len(traditional_words) == len(set(traditional_words))


def test_dictionary_entries_use_consistent_field_order():
    entries = load_entries()

    for entry in entries:
        assert list(entry) == EXPECTED_FIELDS


def test_dictionary_pinyin_uses_tone_marks():
    entries = load_entries()

    for entry in entries:
        expected_pinyin = PINYIN_WORD_OVERRIDES.get(
            entry["word"],
            " ".join(lazy_pinyin(entry["word"], style=Style.TONE)),
        )
        assert entry["pinyin"] == expected_pinyin


def test_dictionary_has_traditional_words():
    entries = load_entries()

    assert all(entry["traditional"].strip() for entry in entries)
    assert any(entry["traditional"] != entry["word"] for entry in entries)


def test_dictionary_includes_new_daily_use_words():
    entries_by_word = {entry["word"]: entry for entry in load_entries()}

    assert entries_by_word["产品"]["traditional"] == "產品"
    assert entries_by_word["建议"]["pinyin"] == "jiàn yì"
    assert entries_by_word["教练"]["english"] == "coach"
    assert entries_by_word["检查"]["english"] == "to check; inspection"
    assert entries_by_word["歌曲"]["pinyin"] == "gē qǔ"
    assert entries_by_word["紧张"]["pinyin"] == "jǐn zhāng"
    assert entries_by_word["登机证"]["traditional"] == "登機證"
    assert entries_by_word["通过"]["traditional"] == "通過"
    assert entries_by_word["通过"]["pinyin"] == "tōng guò"


def test_dictionary_uses_taiwan_spoon_term_with_legacy_alias():
    entries_by_word = {entry["word"]: entry for entry in load_entries()}
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))

    assert "勺子" not in entries_by_word
    assert entries_by_word["汤匙"]["traditional"] == "湯匙"
    assert entries_by_word["汤匙"]["pinyin"] == "tāng chí"
    assert aliases["汤匙"] == ["勺子"]


def test_dictionary_uses_taiwan_contact_term_with_legacy_alias():
    entries_by_word = {entry["word"]: entry for entry in load_entries()}
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))

    assert entries_by_word["联络"]["traditional"] == "聯絡"
    assert aliases["联络"] == ["联系", "聯繫"]


def test_dictionary_uses_taiwan_bus_term_with_mainland_aliases():
    entries_by_word = {entry["word"]: entry for entry in load_entries()}
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))

    assert "公交车" not in entries_by_word
    assert entries_by_word["公车"]["traditional"] == "公車"
    assert entries_by_word["公车"]["pinyin"] == "gōng chē"
    assert entries_by_word["公车"]["english"] == "bus"
    assert aliases["公车"] == ["公交车", "公交車"]


def test_dictionary_uses_taiwan_primary_regional_vocabulary():
    entries_by_word = {entry["word"]: entry for entry in load_entries()}
    aliases = json.loads(ALIASES_PATH.read_text(encoding="utf-8"))
    expected_terms = {
        "早安": ("早安", "good morning", ["早上好"]),
        "餐厅": ("餐廳", "restaurant", ["饭店", "飯店"]),
        "捷运": ("捷運", "MRT; subway", ["地铁", "地鐵"]),
        "计程车": ("計程車", "taxi", ["出租车", "出租車"]),
        "服务生": ("服務生", "server; waiter", ["服务员", "服務員"]),
        "专案": ("專案", "project", ["项目", "項目"]),
        "影片": ("影片", "video", ["视频", "視頻"]),
        "网路": ("網路", "internet; network", ["网络", "網絡"]),
        "冷气": ("冷氣", "air conditioner", ["空调", "空調"]),
        "机车": ("機車", "motorcycle", ["摩托车", "摩托車"]),
        "午餐": ("午餐", "lunch", ["午饭", "午飯"]),
        "晚餐": ("晚餐", "dinner", ["晚饭", "晚飯"]),
        "外送": ("外送", "food delivery", ["外卖", "外賣"]),
        "薪水": ("薪水", "salary; wages", ["工资", "工資"]),
        "登入": ("登入", "to log in", ["登录", "登錄"]),
        "尺寸": ("尺寸", "size", ["尺码", "尺碼"]),
        "品质": ("品質", "quality", ["质量", "質量"]),
        "登机证": ("登機證", "boarding pass", ["登机牌", "登機牌"]),
        "班机": ("班機", "flight", ["航班"]),
        "履历": ("履歷", "resume", ["简历", "簡歷"]),
        "训练": ("訓練", "training", ["培训", "培訓"]),
    }

    for word, (traditional, english, mainland_aliases) in expected_terms.items():
        assert entries_by_word[word]["traditional"] == traditional
        assert entries_by_word[word]["english"] == english
        assert aliases[word] == mainland_aliases
        assert not set(mainland_aliases) & entries_by_word.keys()

    assert entries_by_word["垃圾"]["pinyin"] == "lè sè"
