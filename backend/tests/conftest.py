import os
import sys
import tempfile
from pathlib import Path

# Isolate tests from the real studio data directory.
_TEST_DATA = tempfile.mkdtemp(prefix="pas-test-")
os.environ["PAS_DATA_DIR"] = _TEST_DATA

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
