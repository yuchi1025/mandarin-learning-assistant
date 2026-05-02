# Mandarin Learning Assistant Prototype

This is a simple beginner-friendly web app built with Flask.

It lets users search mock Mandarin learning data by:

- Chinese word
- Pinyin
- English meaning

## Features

- One search input
- Search button
- Result cards showing:
  - Mandarin word
  - Pinyin
  - English meaning
  - Simple explanation
  - Two example sentences
- Mock backend data stored in `app.py`

## Project Files

- `app.py` - Flask app and mock database
- `templates/index.html` - webpage layout
- `static/style.css` - page styling
- `requirements.txt` - Python dependency

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
python app.py
```

5. Open your browser and go to:

```text
http://127.0.0.1:5000
```

## Example Searches

- `你好`
- `xie xie`
- `friend`
