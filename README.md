# Mandarin Learning Assistant

This is a simple beginner-friendly Flask web app for learning Mandarin.

Current version: `v2`

The app currently supports:

- Search by Chinese word
- Search by pinyin
- Search by English meaning
- Tone-marked pinyin display
- Browser-based audio playback
- A simple quiz mode
- Optional local AI fallback with Ollama when a word is not in the dictionary
- Async AI loading with in-memory caching
- Quiz questions that can include AI-learned words

There is no required external AI API in this version.

## Features

### Search Mode

- One search input
- Search results ranked to prefer closer matches
- Pinyin search works with or without tone marks
- Punctuation-only input returns no results
- Very short input is handled more strictly to avoid unrelated matches
- If a valid word is not found in the dictionary, the app can ask a local Ollama model for an explanation
- The page returns immediately and loads AI explanations in the background
- Repeated AI searches are faster because successful results are cached in memory

Each result card shows:

- Chinese word
- Part of speech
- Pinyin with tones
- Meaning
- Simple explanation
- Example sentence audio
- Example sentences in Chinese
- Example sentence pinyin
- Example sentence translation

### Quiz Mode

- Users can switch into quiz mode themselves
- Click an answer to check immediately
- Correct answer:
  - turns green
  - quickly moves to the next quiz
- Wrong answer:
  - turns red
  - explains what the chosen wrong option matches
  - keeps the same question so the user can try again
- Recent quiz words are avoided so the same question does not appear too soon
- AI-learned words can also become future quiz questions

## Tech Stack

- Python
- Flask
- pypinyin
- Ollama local API
- HTML / CSS / vanilla JavaScript

## Project Files

- `app.py` - Flask app, dictionary data, search logic, quiz logic, Ollama fallback
- `templates/index.html` - page layout and browser interaction
- `static/style.css` - page styling
- `requirements.txt` - Python dependencies
- `AGENTS.md` - project behavior and editing guide

## How to Run

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
python3 app.py
```

5. Open:

```text
http://127.0.0.1:5000
```

## Optional AI Fallback With Ollama

If you want AI explanations for words that are not in the dictionary:

1. Install Ollama:

https://ollama.com/download

2. Start Ollama.

3. Pull a model:

```bash
ollama pull gemma3
```

4. Run the app normally.

When a search has no dictionary match, the app will try the local Ollama API at `http://localhost:11434/api/chat`.

The default explanation model in `v2` is `gemma3` for better quality.
The app also keeps the model warm and caches successful results for faster repeated lookups.

Optional environment variables:

```bash
export OLLAMA_URL=http://localhost:11434/api/chat
export OLLAMA_MODEL=gemma3
export OLLAMA_KEEP_ALIVE=15m
```

## Example Searches

- `你好`
- `ni hao`
- `nǐ hǎo`
- `friend`
- `work`

## Notes

- Word and sentence audio use the browser's built-in speech synthesis.
- Audio quality depends on the browser and installed system voices.
- This project is intentionally simple and designed for learning and prototyping.
- `v2` combines a built-in dictionary with optional local AI fallback, but still avoids any required paid API.
