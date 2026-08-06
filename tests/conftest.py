import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"
SCRIPTS_PATH = PROJECT_ROOT / "scripts"

for path in (SRC_PATH, SCRIPTS_PATH):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

os.environ.setdefault("OLLAMA_AUTO_START", "0")
TEST_PROGRESS_DB_PATH = Path(os.getenv("PROGRESS_DB_PATH", "/tmp/mandarin-learning-assistant-test-progress.db"))
TEST_PROGRESS_DB_PATH.unlink(missing_ok=True)
os.environ.setdefault("PROGRESS_DB_PATH", str(TEST_PROGRESS_DB_PATH))
