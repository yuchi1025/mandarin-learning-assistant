#!/usr/bin/env python3
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from pypinyin import Style, lazy_pinyin


REQUIRED_FIELDS = [
    "word",
    "pinyin",
    "english",
    "part_of_speech",
    "explanation",
    "examples",
]


def validate_entries(entries, expected_count=None):
    errors = []

    if not isinstance(entries, list):
        return ["Dictionary root must be a JSON array."]

    words = []
    for index, entry in enumerate(entries, start=1):
        label = f"entry {index}"
        if not isinstance(entry, dict):
            errors.append(f"{label}: must be an object.")
            continue

        word = str(entry.get("word", "")).strip()
        label = f"entry {index} ({word or 'missing word'})"
        words.append(word)

        field_names = list(entry)
        missing_fields = [field for field in REQUIRED_FIELDS if field not in entry]
        if missing_fields:
            errors.append(f"{label}: missing fields: {', '.join(missing_fields)}.")
        if field_names != REQUIRED_FIELDS:
            errors.append(f"{label}: fields should be ordered as: {', '.join(REQUIRED_FIELDS)}.")

        for field in REQUIRED_FIELDS:
            if field == "examples":
                continue
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{label}: `{field}` must be a non-empty string.")

        pinyin = str(entry.get("pinyin", "")).strip()
        expected_pinyin = " ".join(lazy_pinyin(word, style=Style.TONE)) if word else ""
        if word and pinyin and pinyin != expected_pinyin:
            errors.append(f"{label}: `pinyin` should be `{expected_pinyin}`.")

        examples = entry.get("examples")
        if not isinstance(examples, list) or not examples:
            errors.append(f"{label}: `examples` must be a non-empty list.")
            continue

        for example_index, example in enumerate(examples, start=1):
            if not isinstance(example, str) or not example.strip():
                errors.append(f"{label}: example {example_index} must be a non-empty string.")
            elif " (" not in example or not example.endswith(")"):
                errors.append(
                    f"{label}: example {example_index} should include an English translation in parentheses."
                )

    duplicates = sorted(word for word, count in Counter(words).items() if word and count > 1)
    for word in duplicates:
        errors.append(f"duplicate word: {word}.")

    if expected_count is not None and len(entries) != expected_count:
        errors.append(f"expected {expected_count} entries, found {len(entries)}.")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate the Mandarin dictionary JSON file.")
    parser.add_argument(
        "path",
        nargs="?",
        default="data/dictionary.json",
        help="Path to the dictionary JSON file.",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="Fail unless the dictionary contains this many entries.",
    )
    args = parser.parse_args()

    dictionary_path = Path(args.path)
    try:
        entries = json.loads(dictionary_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Dictionary file not found: {dictionary_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {dictionary_path}: {exc}", file=sys.stderr)
        return 1

    errors = validate_entries(entries, args.expected_count)
    if errors:
        print(f"Dictionary validation failed for {dictionary_path}:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"Dictionary validation passed: {len(entries)} entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
