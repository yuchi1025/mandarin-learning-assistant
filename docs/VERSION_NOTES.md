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

- Built a more maintainable v3 project structure with `src/`, `tests/`, `docs/`, `scripts/`, `assets/`, and `data/`, a 200-entry JSON dictionary, exact-match search, recent searches, validation tooling, pytest coverage, screenshots, and MP4 demo media.
- Used AI to help restructure the folders, move dictionary data out of Flask route logic, curate additional daily-use entries, tighten search behavior, add validation checks, create regression tests, and document the final workflow.
- Changed the app from a compact local-AI prototype into a more submission-ready project with source code, data, tests, scripts, docs, screenshots, and demo assets separated into clear folders.
- UI progress: added Recent Searches, a cleaner spinner-based AI loading state, stricter exact-match behavior, and safer quiz generation while preserving the existing Search Mode and Quiz Mode interface.

## v3.1

- Built a branded v3.1 polish update with a logo banner, square app icon, favicon, visible copyright line, refreshed screenshots, and a full-page recorded MP4 demo.
- Used AI to help create and integrate logo assets, update documentation, refresh screenshots, and record a cursor-driven demo with synced audio and local AI loading.
- Changed the project from a submission-ready v3 prototype into a more product-like personal learning assistant with clearer visual identity and stronger presentation materials.
- UI progress: added visible app branding in the header and favicon, then refreshed the demo to show a full-page `1280x1400` workflow with Chinese search, English search, pinyin search, Recent Searches reuse, synced audio playback, `lion` AI loading, and quiz attempts.
