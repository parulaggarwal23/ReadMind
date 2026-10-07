import os
import sys
from pathlib import Path

# make `import config`, `import rag...` work when running `pytest` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBED_MODEL", "hash")
