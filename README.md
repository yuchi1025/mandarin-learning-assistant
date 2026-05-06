# Mandarin Learning Assistant

<p align="center"><small>Mandarin Learning Assistant · © 2026 Yuchi</small></p>

![Mandarin Learning Assistant banner](assets/logo/brand-banner.png)

Current version: `v3.1`

## Overview

### Problem

- English-speaking beginners learning Mandarin often switch between separate tools for word lookup, pinyin, pronunciation, examples, and practice.
- This slows down self-study because a fixed dictionary may not cover every word, while general AI answers may be inconsistent without structure.
- The project targets one learner using a local study assistant for personal Mandarin practice.

### Outcome

- Built a beginner-friendly web app with Search Mode and Quiz Mode.
- Added tone-marked pinyin, browser audio, and local AI fallback through Ollama.
- Added async AI loading and in-memory caching for a faster search experience.
- Added quiz support for AI-learned words within the current app session.
- Expanded the built-in daily-use Mandarin dictionary to `200` entries stored in a separate JSON file.
- Added exact-match search so precise Chinese, pinyin, or English queries return only the exact result.
- Added dictionary validation and `10` pytest tests for search, routes, and data quality.
- Added app screenshots under `assets/screenshots/` for documentation and submission use, refreshed to show the logo branding.
- Added a `52.48s` full-page recorded MP4 demo under `assets/demo/` that shows a visible cursor using Chinese search, English search, pinyin search with tone marks, pinyin search without tone marks, recent searches, synced word and sentence audio playback, local AI loading for `lion`, a wrong-then-correct quiz attempt, and a direct correct quiz attempt, refreshed to show the logo branding and `v3.1` badge.
- Added a branded logo set under `assets/logo/` for the app banner and icon.

---

## Demo

From the learner's perspective:

1. Open the app in Search Mode.
2. Search by Chinese word, such as `学校`.
3. Read the result card with pinyin, meaning, explanation, examples, and translations.
4. Click the word audio button and the sentence audio button.
5. Search by English meaning, such as `airport`.
6. Search by pinyin with tone marks, such as `nǐ hǎo`.
7. Search by pinyin without tone marks, such as `zuo bian`.
8. Click a Recent Searches chip to return to an older lookup.
9. Search an unknown word, such as `lion`, and watch the local AI loading state.
10. Switch to Quiz Mode, choose a wrong answer, then choose the correct answer.
11. Continue to the next quiz and choose a correct answer directly.

Screenshots:

- [Search Mode](assets/screenshots/search-mode.png)
- [Search Result](assets/screenshots/search-result.png)
- [Quiz Mode](assets/screenshots/quiz-mode.png)

Demo media:

- [Demo Video](assets/demo/demo.mp4)

The demo video shows a visible cursor performing Chinese search, English search, pinyin search with tone marks, pinyin search without tone marks, reuse of the Recent Searches chip, synced word and sentence audio playback, local AI loading for `lion`, a wrong-then-correct quiz attempt, and a direct correct quiz attempt. The screenshots and video were regenerated after the logo was added so the branding is visible in the product visuals.

---

## Technology Stack

### Frontend components:

- HTML
- CSS
- Vanilla JavaScript
- Browser Speech Synthesis API

### Backend components:

- Python
- Flask
- `pypinyin`
- Ollama local API
- pytest

---

## Development Approach with AI

- AI tools and services used:
  - ChatGPT for early ideation, project scoping, and prompt suggestions before implementation
  - Ollama for optional local AI explanation fallback when a word is not in the built-in dictionary
  - `gemma3` as the default local explanation model because it produced better structured Mandarin explanations than smaller local models
  - browser Speech Synthesis API for pronunciation playback without storing audio files
- AI agent used:
  - Codex as coding co-developer for Flask implementation, frontend iteration, refactoring, test creation, validation tooling, documentation, and demo asset generation
- Process:
  - Discussed the initial idea of an AI Mandarin Learning Assistant with ChatGPT.
  - Used a ChatGPT-recommended starter prompt to begin the project in Codex.
  - Iterated in Codex from a simple prototype into a structured v3.1 project with data, tests, validation, screenshots, and demo media.
- Key prompts used:
  - ChatGPT-recommended starter prompt for creating the first AI Mandarin Learning Assistant prototype
  - “Create a simple web-based AI Mandarin Learning Assistant prototype.”
  - “add an easy quiz part”
  - “add audios for the chinese word and sentences”
  - “add ai feature, when the input word is not in dictionary, use llm to explain”
  - “Fastest practical improvements”
  - “making the prompt more constrained”
  - “restructure folders”
  - “put mock data dictionary in another file”
  - “add more daily used data”
  - “add a validation script”
  - “create tests”
  - “record a demo video”
- Key review decisions:
  - Tightened search ranking to reduce irrelevant matches.
  - Added exact-match short-circuiting after testing inputs like `when`, which previously returned too many broad matches.
  - Displayed tone-marked pinyin while keeping tone-insensitive search for easier beginner input.
  - Kept AI fallback asynchronous so the page can render immediately while the local model responds.
  - Cached successful AI explanations in memory to make repeated AI lookups faster during the same session.
  - Used `gemma3` by default because smaller local models produced weaker or less reliable Mandarin explanations.
  - Added output validation to reject low-quality or malformed AI responses before showing them in the UI.
  - Moved dictionary data into `data/dictionary.json` so content can grow without cluttering Flask route logic.
  - Added a validation script and pytest tests to catch duplicate words, missing fields, broken search behavior, and route regressions.
  - Used a recorded browser workflow for the MP4 demo instead of a screenshot slideshow so the interaction flow is clear.

---

## Installation

Steps to run the project.

1. Create a virtual environment:

```bash
python3 -m venv .venv
```

2. Activate it:

```bash
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Start the app:

```bash
python3 src/app.py
```

5. Open:

```text
http://127.0.0.1:5000
```

Optional Ollama setup:

1. Install Ollama:

https://ollama.com/download

2. Start Ollama.

3. Pull the default model:

```bash
ollama pull gemma3
```

Optional environment variables:

```bash
export OLLAMA_URL=http://localhost:11434/api/chat
export OLLAMA_MODEL=gemma3
export OLLAMA_KEEP_ALIVE=15m
```

The app still runs without Ollama. In that case, built-in dictionary lookup and quiz mode work normally, while unknown-word AI fallback returns an unavailable message.

---

## Data Validation

Validate the built-in dictionary after editing it:

```bash
python3 scripts/validate_dictionary.py --expected-count 200
```

The script checks for invalid JSON, missing required fields, empty values, duplicate words, malformed examples, and the optional expected entry count.

---

## Testing

Run the automated tests:

```bash
python3 -m pytest
```

The current test suite covers dictionary quality, exact search behavior, partial search behavior, punctuation-only input, basic Flask routes, and invalid AI endpoint input.

---

## Usage

How to use the project.

- Start the app with `python3 src/app.py`
- Example searches:
  - `你好`
  - `ni hao`
  - `nǐ hǎo`
  - `hello`
- Expected behaviour:
  - dictionary words return immediate results
  - exact matches return only the exact result
  - unknown but valid words may trigger local AI fallback
  - pinyin search works with or without tone marks
  - word and sentence audio can be played from result cards
  - recent searches appear after successful searches
  - punctuation-only input returns no result
  - very short input is handled more strictly to reduce unrelated matches
  - search input stays focused after each search
  - quiz mode gives immediate answer feedback for wrong and correct choices
  - AI-learned quiz words are session-only because they come from in-memory cache, not persistent storage

---

## Project Structure

Explanation of key folders.

- `src/` contains the Flask app and frontend source files.
- `src/app.py` contains Flask routes, dictionary loading, search logic, quiz logic, the Ollama fallback, the async AI endpoint, and the in-memory cache.
- `data/dictionary.json` contains the built-in Mandarin dictionary entries used by search and quiz mode.
- `src/templates/index.html` is the main page for Search Mode and Quiz Mode.
- `src/static/style.css` contains layout, card, quiz, and loading styles.
- `tests/` contains automated tests for dictionary quality, search behavior, and Flask routes.
- `docs/` contains extended project documentation, including version notes.
- `scripts/` contains automation and utility scripts, including dictionary validation.
- `assets/logo/brand-banner.png` contains the wide logo banner.
- `assets/logo/icon.png` contains the square app icon and favicon source.
- `assets/screenshots/` contains app screenshots for Search Mode, Search Result, and Quiz Mode.
- `assets/demo/demo.mp4` contains a recorded user workflow with search, audio, AI loading, recent searches, and quiz interaction.
- `requirements.txt` lists Python dependencies.
- `AGENTS.md` contains internal implementation and editing guidance.

---

## Reflection

- What worked:
  - Simple Flask structure made the app easy to extend.
  - Tone-marked pinyin and browser audio added immediate learning value.
  - Async AI loading improved perceived speed.
  - Local Ollama fallback avoided the need for a paid API key.
  - Moving the dictionary into JSON made content expansion easier.
  - Tests and validation made later search and data changes safer.
- What failed:
  - Smaller local models produced weaker Mandarin explanations.
  - Early AI prompting was too loose and sometimes returned poor results.
  - Early fuzzy search returned too many results for exact English queries such as `when`.
  - A screenshot slideshow did not demonstrate the real user flow well enough, so it was replaced with a recorded browser workflow.
- Changes made:
  - tightened search ranking
  - added exact-match-only behavior for exact Chinese, pinyin, and English searches
  - refined quiz behavior
  - moved AI fallback to an async endpoint
  - added in-memory caching
  - added output validation
  - switched the default explanation model back to `gemma3`
  - moved dictionary entries into `data/dictionary.json`
  - expanded the dictionary to 200 entries
  - added dictionary validation and pytest tests
  - captured screenshots for the README/demo assets
  - recorded a user-flow MP4 demo with audio
  - added logo assets for personal-product branding
- Rationale:
  - Keep the app beginner-friendly while making it more capable than a fixed dictionary-only prototype, and keep the codebase structured enough to explain, test, and extend.
