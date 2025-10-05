"""Test bootstrap to ensure local packages are importable.

Pytest will automatically import sitecustomize if present on sys.path.
We append the project root (the directory containing this file) so that
`import api`, `import engine`, etc. work without requiring an editable install.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
