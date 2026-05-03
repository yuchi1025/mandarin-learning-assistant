# Mandarin Learning Assistant

This is a simple beginner-friendly Flask web app for learning Mandarin with mock local data.

The app currently supports:

- Search by Chinese word
- Search by pinyin
- Search by English meaning
- Tone-marked pinyin display
- Browser-based audio playback
- A simple quiz mode

There is no external AI API in this version.

## Features

### Search Mode

- One search input
- Search results ranked to prefer closer matches
- Pinyin search works with or without tone marks
- Punctuation-only input returns no results
- Very short input is handled more strictly to avoid unrelated matches

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

## Tech Stack

- Python
- Flask
- pypinyin
- HTML / CSS / vanilla JavaScript

## Project Files

- `app.py` - Flask app, mock data, search logic, quiz logic
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
