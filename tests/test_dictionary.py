import json
from pathlib import Path

from pypinyin import Style, lazy_pinyin

from validate_dictionary import validate_entries


DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "dictionary.json"
EXPECTED_FIELDS = ["word", "traditional", "pinyin", "english", "part_of_speech", "explanation", "examples"]
PINYIN_WORD_OVERRIDES = {
    "记得": "jì dé",
}


def load_entries():
    return json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))


def test_dictionary_is_valid():
    entries = load_entries()

    assert validate_entries(entries, expected_count=400) == []


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
