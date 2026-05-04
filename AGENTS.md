# AGENTS.md

## Project Overview

This project is a beginner-friendly Flask web app for Mandarin learning.

Current version: `v2`

It currently has two user modes:

- `Search Mode`
- `Quiz Mode`

The app uses:

- a built-in local dictionary
- optional local AI fallback through Ollama

There is no required external paid API or external database.

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
- If no dictionary result is found, the app may request a local Ollama explanation.
- AI explanations load asynchronously after the page renders.
- Successful AI explanations are cached in memory for faster repeated searches.

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
- Recent quiz words are avoided for a few rounds to reduce repetition.
- AI-learned words can be added into the quiz pool after successful lookup.

## Main Files

- `app.py`
  - Flask routes
  - built-in dictionary
  - search ranking logic
  - pinyin generation
  - quiz generation
  - Ollama fallback
  - async AI endpoint
  - in-memory cache
- `templates/index.html`
  - UI for search and quiz modes
  - browser audio controls
  - client-side quiz interaction
  - async AI loading
- `static/style.css`
  - layout and styling
- `requirements.txt`
  - Python packages

## Implementation Notes

- Pinyin generation uses `pypinyin`.
- Audio uses browser `speechSynthesis` with Mandarin voice selection when available.
- Search is ranked, not simple flat substring matching.
- Local AI fallback uses Ollama’s chat API.
- The default AI explanation model is `gemma3`.
- The app is intentionally simple and suitable for learning/demo use.

## When Editing

- Keep the app beginner-friendly.
- Prefer simple Flask patterns over heavy abstractions.
- Preserve tone-marked display pinyin.
- Preserve tone-insensitive pinyin search.
- Preserve async AI loading and cache behavior.
- Preserve validation against low-quality AI output.
- Avoid adding external paid services unless explicitly requested.
