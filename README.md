# Mandarin Learning Assistant

<p align="center"><small>Mandarin Learning Assistant · © 2026 Yuchi</small></p>

![Mandarin Learning Assistant banner](assets/logo/brand-banner.png)

Current version: `v3.1.1`

## Overview

### Problem

- Who is affected:
  - English-speaking beginners learning Mandarin for personal study.
  - Learners who need quick lookup, pronunciation, examples, and practice in one place.
- What is the issue:
  - Beginners often switch between separate tools for word lookup, pinyin, pronunciation, examples, and practice.
  - This slows down self-study because a fixed dictionary may not cover every word, while general AI answers may be inconsistent without structure.

### Outcome

- What was achieved:
  - Built a working local prototype of a Mandarin Learning Assistant for individual self-study.
  - Combined dictionary lookup, pinyin support, pronunciation audio, example sentences, recent searches, AI fallback, and quiz practice in one web app.
  - Enabled learners to search by Chinese, English, pinyin with tone marks, or pinyin without tone marks.
  - Added local AI fallback so unknown valid words can show a structured explanation instead of only returning “not found.”
  - Added Quiz Mode so lookup can turn into active recall practice with immediate feedback.

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
9. Search a word not in the built-in dictionary and watch the local AI loading state.
10. Switch to Quiz Mode, choose a wrong answer, then choose the correct answer.
11. Continue to the next quiz and choose a correct answer directly.

Screenshots:

- [Search Mode](assets/screenshots/search-mode.png)
- [Search Result](assets/screenshots/search-result.png)
- [Quiz Mode](assets/screenshots/quiz-mode.png)

Demo media:

- [Demo Video](assets/demo/demo.mp4)
- [Demo GIF Preview](assets/demo/demo.gif)

The demo video shows a visible cursor performing Chinese search, English search, pinyin search with tone marks, pinyin search without tone marks, reuse of the Recent Searches chip, word and sentence audio playback, local AI loading for a word not in the built-in dictionary, a wrong-then-correct quiz attempt, and a direct correct quiz attempt. The MP4 includes audio; the GIF is a silent compressed preview.

---

## Technology Stack

### Frontend components:

- `HTML` for page structure
- `CSS` for layout, responsive styling, cards, buttons, loading state, and quiz feedback
- Vanilla `JavaScript` for audio controls, recent searches, async AI loading, and client-side quiz interaction
- `Browser Speech Synthesis API` for Mandarin word and sentence pronunciation

### Backend components:

- `Python` for application logic and utility scripts
- `Flask` for web routes, form handling, static/data asset serving, and the AI explanation API endpoint
- `pypinyin` for tone-marked pinyin generation
- `Ollama local API` for optional unknown-word AI explanations
- `gemma3` as the default local explanation model
- `pytest` for automated regression tests

---

## Development Approach with AI

- AI tools, services, models, and purposes:
  - `ChatGPT` for early ideation, project scoping, and prompt suggestions before implementation
  - `Ollama` for optional local AI explanation fallback when a word is not in the built-in dictionary
  - `gemma3` as the default local explanation model because it produced better structured Mandarin explanations than smaller local models
  - `Browser Speech Synthesis API` for pronunciation playback without storing audio files
- AI agents:
  - `Codex` as coding co-developer for Flask implementation, frontend iteration, refactoring, test creation, validation tooling, documentation, and demo asset generation
- Process:
  - Discussed the initial idea of an AI Mandarin Learning Assistant with ChatGPT.
  - Used a ChatGPT-recommended starter prompt to begin the project in Codex.
  - Iterated in Codex from a simple prototype into a structured v3.1.1 project with data, tests, validation, screenshots, and demo media.
- Key prompts used:
  - Initial Idea And Setup:
    - ChatGPT-recommended v0 starter prompt:

      ```text
      Create a simple web-based AI Mandarin Learning Assistant prototype.

      Goal:
      Users can search by:
      - Chinese word
      - Pinyin
      - English meaning

      For v0, use mock backend data only. Do not use real AI API yet.

      Requirements:
      - Frontend page with one search input
      - Button: Search
      - Show result card:
        - Mandarin word
        - Pinyin
        - English meaning
        - Simple explanation
        - Two example sentences
      - Include mock database in JSON or Python dictionary
      - Keep the project simple and beginner-friendly
      - Explain how to run it
      ```
  - Core Features:
    - “Add an easy quiz mode so learners can practise Mandarin vocabulary.”
    - “Add audio playback for Chinese words and example sentences.”
    - “Add an AI feature: when the input word is not in the dictionary, use a local LLM to explain it.”
    - “Make the AI prompt more constrained so the local model returns consistent structured output.”
  - Data And Structure:
    - “Restructure the project into src, tests, docs, scripts, assets, and data folders.”
    - “Move the mock dictionary into a separate JSON file and add more daily-use Mandarin words.”
    - “Expand the dictionary dataset to 200 words, keep the JSON structure, and add a validation script to catch missing fields and duplicate words.”
  - Testing:
    - “What should we put in the tests directory?”
    - “Add pytest tests for dictionary quality, search behavior, Flask routes, AI endpoint validation, and audio text cleanup.”
  - Documentation:
    - “Update README.md, AGENTS.md, and VERSION_NOTES.md.”
    - “Update README sections for Demo, Project Structure, Current Version, Outcome, Usage, Testing, and Reflection.”
  - Branding:
    - “Create a logo/icon for this app to make it feel like a personal product.”
    - “Add Mandarin Learning Assistant - © 2026 Yuchi.”
    - “Use the logo in the app, README, favicon, screenshots, and demo assets.”
  - Demo Assets:
    - “Create screenshots, an MP4 demo video, and a GIF preview.”
    - “Record a real user workflow with a visible cursor instead of using a screenshot slideshow.”
    - “Update the demo video to show Chinese search, English search, pinyin search with tone marks, pinyin search without tone marks, Recent Searches, word audio, sentence audio, local AI loading, and quiz attempts.”
    - “Fix the demo MP4 so word and sentence audio playback is synced with the cursor clicks.”
  - Versioning And Git:
    - “What is the progress compared to v3?”
    - “Since we are in v3.1.1, update all files to be consistent.”
    - “Git push to https://github.com/yuchi1025/mandarin-learning-assistant.”
- Key review points and corresponding decisions made:

  | Review Point | Decision Made |
  | --- | --- |
  | Search results were too broad for short or exact inputs. | Tightened search ranking and added exact-match short-circuiting after testing inputs like `when`. |
  | Beginners need readable pinyin but may type without tone marks. | Displayed tone-marked pinyin while keeping tone-insensitive pinyin search. |
  | Local AI responses can be slow. | Kept AI fallback asynchronous so the page renders immediately while the local model responds. |
  | Repeated local AI lookups should not wait for the same response again. | Cached successful AI explanations in memory during the current session. |
  | Smaller local models produced weaker Mandarin explanations. | Used `gemma3` as the default local explanation model. |
  | AI output could be malformed or too low quality for learners. | Added output validation before showing AI responses in the UI. |
  | Dictionary content was cluttering Flask route logic. | Moved dictionary data into `data/dictionary.json`. |
  | Dictionary growth increased the risk of duplicate words, missing fields, and broken search behavior. | Added a validation script and pytest tests. |
  | Screenshots alone did not explain the interaction flow clearly. | Used a recorded browser workflow for the MP4 demo instead of a screenshot slideshow. |

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

2. Pull the default model:

```bash
ollama pull gemma3
```

The Flask app starts `ollama serve` automatically when the web app opens and Ollama is not already running.

Optional environment variables:

```bash
export OLLAMA_URL=http://localhost:11434/api/chat
export OLLAMA_MODEL=gemma3
export OLLAMA_KEEP_ALIVE=15m
export OLLAMA_AUTO_START=1
```

Set `OLLAMA_AUTO_START=0` if you prefer to manage Ollama yourself.

The app still runs without Ollama. In that case, built-in dictionary lookup and quiz mode work normally, while unknown-word AI fallback returns an unavailable message.

---

## Data Validation

Validate the built-in dictionary after editing it:

```bash
python3 scripts/validate_dictionary.py --expected-count 200
```

The script checks for invalid JSON, missing required fields, inconsistent field order, empty values, duplicate words, malformed examples, tone-marked dictionary pinyin, and the optional expected entry count.

---

## Testing

Run the automated tests:

```bash
python3 -m pytest
```

The current `16`-test suite covers dictionary quality, consistent dictionary field order, tone-marked dictionary pinyin, exact search behavior, partial search behavior, punctuation-only input, basic Flask routes, static JavaScript loading, invalid AI endpoint input, AI-learned quiz entries, AI cache cleanup, and cleaned sentence-audio text.

---

## Usage

How to use the project.

- Start the app with `python3 src/app.py`
- Example searches:
  - `学校`
  - `airport`
  - `nǐ hǎo`
  - `zuo bian`
- Expected behaviour:
  - Search:
    - Dictionary words return immediate results
    - `学校` or `school` returns the `学校` dictionary card
    - Exact Chinese, English, or pinyin matches return only the exact result
    - Pinyin search works with tone marks, such as `nǐ hǎo`
    - Pinyin search also works without tone marks, such as `zuo bian`
    - Punctuation-only input returns no result
    - Very short input is handled more strictly to reduce unrelated matches
    - Search input stays focused after each search
  - AI fallback:
    - A word not in the built-in dictionary may trigger local AI loading and explanation
    - AI fallback depends on Ollama being available locally
  - Audio:
    - Word and sentence audio can be played from result cards
  - Recent Searches:
    - Recent searches appear after successful searches
    - Clicking a recent search chip runs that search again
    - Refreshing or closing the browser page clears recent searches
  - Quiz Mode:
    - A wrong quiz answer shows feedback while keeping the same question available
    - A correct quiz answer advances to the next quiz after a short delay
  - Session behaviour:
    - Successful AI fallback searches can be practised in Quiz Mode during the same server session
    - Switching between Search Mode and Quiz Mode keeps AI-learned quiz words available
    - Refreshing or closing the browser page clears AI-learned quiz words from the server cache and clears recent searches
    - AI-learned quiz words are temporary because they come from in-memory cache, not persistent storage

---

## Project Structure

```text
mandarin-learning-assistant/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── AGENTS.md
├── src/
│   ├── app.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── app.js
│       └── style.css
├── tests/
│   ├── conftest.py
│   ├── test_dictionary.py
│   ├── test_routes.py
│   └── test_search.py
├── docs/
│   └── VERSION_NOTES.md
├── scripts/
│   └── validate_dictionary.py
├── assets/
│   ├── logo/
│   │   ├── brand-banner.png
│   │   └── icon.png
│   ├── screenshots/
│   │   ├── search-mode.png
│   │   ├── search-result.png
│   │   └── quiz-mode.png
│   └── demo/
│       ├── demo.mp4
│       └── demo.gif
└── data/
    └── dictionary.json
```

Key folders and files:

- `src/` contains the main Flask app and frontend source files.
- `src/app.py` contains Flask routes, dictionary loading, search logic, quiz logic, Ollama fallback, the async AI endpoint, and in-memory AI caching.
- `src/templates/index.html` contains the Search Mode and Quiz Mode page structure.
- `src/static/style.css` contains layout, card, quiz, loading, and branding styles.
- `src/static/app.js` contains Vanilla JavaScript for audio, recent searches, async AI loading, and quiz interaction.
- `tests/` contains pytest coverage for dictionary quality, consistent field order, tone-marked pinyin, search behavior, Flask routes, static JavaScript loading, and cleaned sentence-audio text.
- `docs/VERSION_NOTES.md` records the project progress from v0 to v3.1.1.
- `scripts/validate_dictionary.py` validates the 200-entry dictionary, required fields, consistent field order, duplicate words, examples, and tone-marked pinyin.
- `assets/logo/` contains the product banner, app icon, and favicon source.
- `assets/screenshots/` contains Search Mode, Search Result, and Quiz Mode screenshots.
- `assets/demo/` contains the MP4 demo with audio and the silent GIF preview.
- `data/dictionary.json` contains the built-in Mandarin dictionary dataset.
- `requirements.txt` lists Python dependencies.
- `AGENTS.md` contains project guidance for future AI-assisted editing.

---

## Reflection

- What worked:
  - The simple Flask structure made the prototype easy to build, explain, and extend.
  - Moving dictionary data into `data/dictionary.json` made it easier to expand the dataset without changing route logic.
  - Tone-marked pinyin, browser audio, recent searches, and Quiz Mode made the app more useful for beginner self-study.
  - Async AI loading improved the user experience because the page can show a loading state while Ollama responds.
  - Validation scripts and pytest tests made later changes safer, especially dictionary growth, pinyin cleanup, and search behavior.
  - AI was useful as a co-developer for scaffolding, refactoring, debugging, documentation, and demo generation.
- What failed or needed iteration:
  - Early fuzzy search returned too many results for exact English queries such as `when`.
  - Early AI prompts were too loose and sometimes produced inconsistent or low-quality responses.
  - Smaller local models produced weaker Mandarin explanations, so model choice mattered.
  - The first screenshot-style demo did not show the real user flow clearly enough.
  - The demo video needed several iterations to show a visible cursor, tone-marked pinyin, recent searches, AI loading, quiz behavior, and synced audio correctly.
- Changes made and rationale:

  | Change Made | Rationale |
  | --- | --- |
  | Added exact-match search. | Precise Chinese, English, or pinyin inputs should return only the intended result. |
  | Kept pinyin search tone-insensitive while displaying tone-marked pinyin. | Beginners may not know how to type tone marks, but they still need to see correct pronunciation. |
  | Added AI output validation. | Malformed or weak local model responses should not be shown directly to learners. |
  | Added in-memory AI caching. | Repeated AI lookups should be faster during the same session. |
  | Moved dictionary entries into `data/dictionary.json`. | Dictionary content should be easier to grow without cluttering Flask route logic. |
  | Expanded the dictionary to 200 daily-use words. | The app needed enough common vocabulary to feel useful as a prototype. |
  | Added dictionary validation and pytest tests. | Data format consistency, search behavior, Flask routes, and sentence-audio cleanup should be checked automatically. |
  | Replaced screenshot-only demo material with a recorded MP4 and GIF preview. | The submission needed to show the actual user flow, not only static screens. |
  | Added logo and copyright branding. | The app should feel like a personal learning product rather than an unfinished code exercise. |
- Remaining limitations:
  - The app is a local prototype and has not been publicly deployed.
  - AI fallback explanations are cached only in memory, so they disappear when the server restarts.
  - Audio quality depends on the browser or operating system speech synthesis voice.
  - The dictionary is useful for a prototype but would need more review before production use.
