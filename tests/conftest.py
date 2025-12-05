import sys
from pathlib import Path

# Ensure local src/ is on sys.path so tests use the working tree, not installed package.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
