import json
from pathlib import Path

from validate_dictionary import validate_entries


DICTIONARY_PATH = Path(__file__).resolve().parent.parent / "data" / "dictionary.json"


def load_entries():
    return json.loads(DICTIONARY_PATH.read_text(encoding="utf-8"))


def test_dictionary_is_valid():
    entries = load_entries()

    assert validate_entries(entries, expected_count=200) == []


def test_dictionary_words_are_unique():
    entries = load_entries()
    words = [entry["word"] for entry in entries]

    assert len(words) == len(set(words))
