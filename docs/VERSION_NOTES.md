# Version Notes

## Unreleased

- Added simple local student profiles without authentication or passwords. Learners can be created and selected from the app, with the active learner remembered in the browser.
- Moved progress ownership to stable SQLite student IDs. Search, batch search, and AI fallback progress now belong only to the selected learner, and Progress Mode is filtered to that learner.
- Added a backward-safe SQLite migration: previously global progress is preserved and assigned to an `Existing progress` profile rather than being discarded.
- Added Quiz Mode scoring and Mandarin question audio, plus consistent paired Simplified and Traditional Chinese display in Quiz Mode.

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

- Built a branded v3.1 polish update with a logo banner, square app icon, favicon, visible copyright line, refreshed screenshots, a full-page recorded MP4 demo, and a compressed GIF preview.
- Used AI to help create and integrate logo assets, update documentation, refresh screenshots, record a cursor-driven demo with synced audio and local AI loading, and generate a GIF preview from the MP4.
- Changed the project from a submission-ready v3 prototype into a more product-like personal learning assistant with clearer visual identity and stronger presentation materials.
- UI progress: added visible app branding in the header and favicon, then refreshed the demo to show a full-page `1280x1400` workflow with Chinese search, English search, pinyin search, Recent Searches reuse, synced audio playback, `lion` AI loading, and quiz attempts.

## v3.1.1

- Built a final v3.1.1 cleanup update with sentence-audio cleanup, tone-marked dictionary pinyin, consistent dictionary field order, separated frontend JavaScript, refresh cleanup for temporary session data, stricter pinyin validation, refreshed screenshots, refreshed MP4/GIF demo media, and stronger submission documentation.
- Used AI to convert stored dictionary pinyin to tone-marked pinyin, improve README sections against the submission checklist, separate JavaScript into `src/static/app.js`, and correct demo audio timing after review.
- Changed the project from a branded v3.1 demo into a more consistent submission-ready package with cleaned speech text, tone-marked data, consistent dictionary formatting, a cleaner HTML/static JavaScript split, AI-learned quiz entries that persist across internal mode switches, recent-search and AI-cache cleanup on browser refresh/close, `16` passing tests, categorized key prompts, a review-points table, deeper project structure documentation, and a clearer reflection section.
- UI progress: updated the visible version badge to `v3.1.1`, preserved the v3.1 interface and demo flow, refreshed screenshots and demo media to show tone-marked pinyin, corrected MP4 word/sentence audio sync with cursor clicks, and kept refresh cleanup invisible to normal Search Mode and Quiz Mode navigation.
