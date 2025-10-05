# Ensure local packages (api, engine, etc.) importable when running tests directly

import os
import sys

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
