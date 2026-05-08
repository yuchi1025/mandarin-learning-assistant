# AGENTS.md

## Project Overview

This project is a beginner-friendly Flask web app for Mandarin learning.

Current version: `v3.1.1`

It currently has two user modes:

- `Search Mode`
- `Quiz Mode`

The app uses:

- a built-in local dictionary
- optional local AI fallback through Ollama
- automated dictionary validation and pytest coverage
- documentation screenshots in `assets/screenshots/`
- recorded MP4 and GIF demo media in `assets/demo/`
- logo assets in `assets/logo/`

There is no required external paid API or external database.

## Current Behavior

### Search Mode

- Users can search by:
  - Chinese word
  - Pinyin with tone marks
  - Pinyin without tone marks
  - English meaning
- Displayed pinyin uses tone marks.
- Search still works if the user types pinyin without tones.
- Punctuation-only input should return no results.
- Exact Chinese, pinyin, or English matches should return only the exact matching entry.
- Very short input is intentionally strict to avoid unrelated matches.
- If no dictionary result is found, the app may request a local Ollama explanation.
- AI explanations load asynchronously after the page renders.
- Successful AI explanations are cached in memory for faster repeated searches.
- Recent searches are saved in browser `localStorage` and rendered as reusable chips.

Each result card shows:

- Chinese word
- Part of speech
- Pinyin with tones
- Meaning
- Simple explanation
- Example sentences
- Example sentence pinyin
- Example sentence translation
- Audio buttons for the word and each sentence
- Sentence audio should use cleaned speech text, while displayed sentence text may keep punctuation and quote marks.

If the result comes from AI:

- it should still look like a normal word card
- it should still include part of speech and word audio
- the UI should avoid noisy “waiting” text while loading

### Quiz Mode

- Users enter quiz mode by clicking the mode switch.
- Each quiz asks for the English meaning of one Mandarin word.
- Clicking a choice checks it immediately.
- If correct:
  - the selected choice turns green
  - the app quickly moves to the next quiz
- If wrong:
  - the selected choice turns red
  - the app explains what that wrong option matches
  - the same question stays on screen so the user can try again
- If the user later clicks the correct answer, it turns green and advances to the next quiz.
- Recent quiz words are avoided for a few rounds to reduce repetition.
- AI-learned words can be added into the quiz pool after successful lookup.

## Main Files

- `src/app.py`
  - Flask routes
  - dictionary loading
  - search ranking logic
  - pinyin generation
  - quiz generation
  - Ollama fallback
  - async AI endpoint
  - in-memory cache
- `src/templates/index.html`
  - UI for search and quiz modes
  - browser audio controls
  - client-side quiz interaction
  - async AI loading
- `src/static/style.css`
  - layout and styling
- `data/dictionary.json`
  - 200 built-in daily-use Mandarin dictionary entries
- `scripts/validate_dictionary.py`
  - validates required dictionary fields, examples, duplicates, and optional expected count
- `tests/`
  - pytest coverage for dictionary quality, search behavior, and Flask routes
- `assets/screenshots/`
  - Search Mode, Search Result, and Quiz Mode screenshots for documentation/demo use
- `assets/demo/`
  - full-page recorded MP4 demo showing a visible cursor using Chinese search, English search, pinyin search with tone marks, pinyin search without tone marks, recent searches, synced audio playback, AI loading for a word not in the built-in dictionary, a wrong-then-correct quiz attempt, and a direct correct quiz attempt
  - compressed silent GIF preview generated from the MP4
- `assets/logo/`
  - brand banner and square app icon
- `requirements.txt`
  - Python packages

## Implementation Notes

- Pinyin generation uses `pypinyin`.
- Audio uses browser `speechSynthesis` with Mandarin voice selection when available.
- Search is ranked, not simple flat substring matching.
- Search performs an exact-match pass before fuzzy ranking.
- Local AI fallback uses Ollama’s chat API.
- The default AI explanation model is `gemma3`.
- Demo recording should use a controlled browser workflow with a visible cursor overlay, full-page `1280x1400` capture, and generated speech audio synced to the audio-button clicks so the MP4 is reproducible.
- The app is intentionally simple and suitable for learning/demo use.

## Validation and Tests

- Validate dictionary data with `python3 scripts/validate_dictionary.py --expected-count 200`.
- Run automated tests with `python3 -m pytest`.
- Dictionary validation should require stored tone-marked pinyin to match each Chinese word.
- Dictionary validation should require the same field order for every entry: `word`, `pinyin`, `english`, `part_of_speech`, `explanation`, `examples`.
- Keep tests independent of Ollama and external network access.
- Keep screenshots in `assets/screenshots/` if demo visuals are refreshed, especially after logo or branding changes.
- Keep demo videos and GIF previews in `assets/demo/` and refresh them when the UI branding changes.
- Keep logo assets in `assets/logo/`.

## When Editing

- Keep the app beginner-friendly.
- Prefer simple Flask patterns over heavy abstractions.
- Keep dictionary entries in `data/dictionary.json`, not inline in `src/app.py`.
- Preserve consistent dictionary field order.
- Preserve tone-marked dictionary and display pinyin.
- Preserve tone-insensitive pinyin search.
- Preserve exact-match-only behavior for exact Chinese, pinyin, and English searches.
- Preserve async AI loading and cache behavior.
- Preserve validation against low-quality AI output.
- Update dictionary tests and validation expectations if the target dictionary size changes.
- Avoid adding external paid services unless explicitly requested.
