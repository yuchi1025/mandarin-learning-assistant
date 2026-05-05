# Version Notes

## v0

- Built a simple Flask-based Mandarin lookup prototype with one search input and mock dictionary data.
- Used AI to help scaffold the first app structure, result card layout, and beginner-friendly content format.
- Changed the project from an empty workspace into a working local web prototype.
- UI progress: basic single-page search UI with simple result cards.

## v1

- Built a more complete Mandarin learning app with Search Mode and Quiz Mode, including pinyin, pronunciation audio, part of speech, and example sentence support.
- Used AI to help refine the search behavior, quiz interaction, UI layout, and documentation.
- Changed the app from a basic dictionary demo into a more usable learning prototype with stronger search logic and interactive quiz flow.
- UI progress: moved from a basic search page to a more polished dictionary-and-quiz interface.

## v2

- Built a local-AI-enhanced Mandarin learning app with Ollama fallback for unknown words, async AI loading, in-memory caching, and AI-learned quiz words.
- Used AI to help implement the local LLM flow, tighten prompts, improve output validation, and iterate on performance and UX decisions.
- Changed the app from a fixed dictionary-and-quiz tool into a hybrid dictionary plus local-AI learning experience.
- UI progress: kept the polished v1 interface while adding async AI-driven result behavior and quieter loading states.

## v3

- Restructured the project into clearer top-level folders: `src/`, `tests/`, `docs/`, `scripts/`, `assets/`, and `data/`.
- Moved the built-in dictionary out of `src/app.py` and into `data/dictionary.json`.
- Expanded the daily-use Mandarin dictionary to 200 entries.
- Added exact-match search behavior so exact Chinese, pinyin, or English searches return only the exact matching result.
- Added recent searches backed by browser `localStorage`.
- Replaced the quiet AI placeholder with a spinner-based loading state.
- Hardened quiz generation by filtering unsuitable cached AI words and cleaning duplicate choices.
- Added `scripts/validate_dictionary.py` to catch invalid JSON, missing fields, empty values, duplicate words, malformed examples, and unexpected entry counts.
- Added pytest coverage for dictionary quality, search behavior, Flask route health, and invalid AI endpoint input.
- Added a project `LICENSE` and updated documentation for the new run, validation, and test commands.
- Added documentation screenshots under `assets/screenshots/` for Search Mode, Search Result, and Quiz Mode.
- Added demo media under `assets/demo/` as an MP4 file.
- Updated the MP4 demo to show a fuller user workflow: Chinese search, English search, pinyin search with tone marks, pinyin search without tone marks, recent searches, word and sentence audio playback, AI loading, one wrong quiz choice, then the correct quiz choice.
- Used AI to help restructure the project, curate additional daily-use entries, add validation tooling, and create regression tests.
- Changed the app from a compact prototype layout into a more maintainable project structure with data and tests separated from application logic.
- UI progress: added recent searches and a cleaner AI loading spinner while preserving the existing search and quiz interface.
