import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PATH = PROJECT_ROOT / "src"
SCRIPTS_PATH = PROJECT_ROOT / "scripts"

for path in (SRC_PATH, SCRIPTS_PATH):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)
