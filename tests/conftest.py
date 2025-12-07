import sys
from pathlib import Path

from dotenv import load_dotenv

# Load local .env so integration tests can pick up tokens/URLs without exporting.
load_dotenv()

# Ensure local src/ is on sys.path so tests use the working tree, not installed package.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
