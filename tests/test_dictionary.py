import json
from pathlib import Path

from pypinyin import Style, lazy_pinyin

from validate_dictionary import validate_entries


DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "dictionary.json"
EXPECTED_FIELDS = ["word", "pinyin", "english", "part_of_speech", "explanation", "examples"]


def load_entries():
    return json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))


def test_dictionary_is_valid():
    entries = load_entries()

    assert validate_entries(entries, expected_count=200) == []


def test_dictionary_words_are_unique():
    entries = load_entries()
    words = [entry["word"] for entry in entries]

    assert len(words) == len(set(words))


def test_dictionary_entries_use_consistent_field_order():
    entries = load_entries()

    for entry in entries:
        assert list(entry) == EXPECTED_FIELDS


def test_dictionary_pinyin_uses_tone_marks():
    entries = load_entries()

    for entry in entries:
        expected_pinyin = " ".join(lazy_pinyin(entry["word"], style=Style.TONE))
        assert entry["pinyin"] == expected_pinyin
