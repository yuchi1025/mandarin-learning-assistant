# Mandarin Learning Assistant

## Overview

### Problem

- English-speaking beginners learning Mandarin often need word lookup, pinyin, pronunciation help, and simple practice in one place.
- A fixed dictionary is helpful, but it cannot explain words outside its built-in list.

### Outcome

- Built a beginner-friendly web app with Search Mode and Quiz Mode.
- Added tone-marked pinyin, browser audio, and local AI fallback through Ollama.
- Added async AI loading and in-memory caching for a faster search experience.
- Added quiz support for AI-learned words within the current app session.
- Expanded the built-in daily-use Mandarin dictionary to 200 entries stored in a separate JSON file.
- Added dictionary validation and pytest coverage for search, routes, and data quality.
- Added app screenshots under `assets/screenshots/` for documentation and submission use.
- Added a recorded MP4 demo under `assets/demo/` that shows search, audio playback, AI loading, recent searches, and quiz feedback.

---

## Demo

- Open the app and start in Search Mode.
- Search by Chinese word, pinyin with tone marks, pinyin without tone marks, or English meaning.
- Built-in dictionary matches return a normal word card immediately.
- Unknown but valid words can load an AI-generated word card through local Ollama.
- Word cards include the word, part of speech, pinyin, meaning, explanation, example sentences, sentence pinyin, and audio controls.
- Recent search chips let users quickly repeat earlier searches in the same browser.
- Switch to Quiz Mode to answer meaning questions.
- Correct answers turn green and quickly move to the next question.
- Wrong answers turn red and explain what the selected wrong option matched.

Screenshots:

- [Search Mode](assets/screenshots/search-mode.png)
- [Search Result](assets/screenshots/search-result.png)
- [Quiz Mode](assets/screenshots/quiz-mode.png)

Demo media:

- [Demo Video](assets/demo/demo.mp4)

The demo video shows Chinese search, English search, pinyin search with tone marks, pinyin search without tone marks, recent searches, word and sentence audio playback, local AI loading for an unknown word, and a wrong-then-correct quiz attempt.

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
  - Ollama for local AI explanation fallback
  - `gemma3` as the default explanation model
  - browser speech synthesis for pronunciation playback
- AI agent used:
  - Codex for implementation, refactoring, testing, and documentation
- Key prompts used:
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
  - tightened search ranking to reduce irrelevant matches
  - displayed tone-marked pinyin while keeping tone-insensitive search
  - kept async loading and caching for speed
  - used `gemma3` by default for better local explanation quality
  - added validation to reject obviously bad AI output
  - separated dictionary data from application logic
  - added automated tests for exact search behavior and route health
  - used a recorded browser workflow for the MP4 demo instead of a screenshot slideshow

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
  - `friend`
  - `work`
  - `苹果`
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
- `assets/screenshots/` contains app screenshots for Search Mode, Search Result, and Quiz Mode.
- `assets/demo/demo.mp4` contains a recorded user workflow with search, audio, AI loading, recent searches, and quiz interaction.
- `data/` contains optional datasets and local app data.
- `requirements.txt` lists Python dependencies.
- `AGENTS.md` contains internal implementation and editing guidance.

---

## Reflection

- What worked:
  - Simple Flask structure made the app easy to extend.
  - Tone-marked pinyin and browser audio added immediate learning value.
  - Async AI loading improved perceived speed.
  - Local Ollama fallback avoided the need for a paid API key.
- What failed:
  - Smaller local models produced weaker Mandarin explanations.
  - Early AI prompting was too loose and sometimes returned poor results.
- Changes made:
  - tightened search ranking
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
- Rationale:
  - Keep the app beginner-friendly while making it more capable than a fixed dictionary-only prototype.
