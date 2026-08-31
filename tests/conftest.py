import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


import os
import tempfile

# Every test process writes its run records, gate records and trajectories into a
# throwaway directory. A test must never be able to change a published result.
_TMP = tempfile.mkdtemp(prefix="ssf-hve-tests-")
os.environ["SSF_HVE_RESULTS_DIR"] = _TMP
