# AGENTS.md

## Project Overview

This project is a beginner-friendly Flask web app for Mandarin learning.

It currently has two user modes:

- `Search Mode`
- `Quiz Mode`

The app uses mock local data only. There is no external AI API or database.

## Current Behavior

### Search Mode

- Users can search by:
  - Chinese word
  - Pinyin
  - English meaning
- Displayed pinyin uses tone marks.
- Search still works if the user types pinyin without tones.
- Punctuation-only input should return no results.
- Very short input is intentionally strict to avoid unrelated matches.

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
- Recent quiz words are avoided for a few rounds to reduce repetition.

## Main Files

- `app.py`
  - Flask routes
  - mock database
  - search ranking logic
  - pinyin generation
  - quiz generation
- `templates/index.html`
  - UI for search and quiz modes
  - browser audio controls
  - client-side quiz interaction
- `static/style.css`
  - layout and styling
- `requirements.txt`
  - Python packages

## Implementation Notes

- Pinyin generation uses `pypinyin`.
- Audio uses browser `speechSynthesis` with Mandarin voice selection when available.
- Search is ranked, not simple flat substring matching.
- The app is intentionally simple and suitable for learning/demo use.

## When Editing

- Keep the app beginner-friendly.
- Prefer simple Flask patterns over heavy abstractions.
- Preserve tone-marked display pinyin.
- Preserve tone-insensitive pinyin search.
- Avoid adding external services unless explicitly requested.
