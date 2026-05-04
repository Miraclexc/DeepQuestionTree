"""Compatibility import for the SQLite session store.

The implementation lives in ``src.backend.infrastructure.session_store``.
This module remains so older imports keep using the same module object.
"""

from __future__ import annotations

import sys

from ..infrastructure import session_store as _session_store

sys.modules[__name__] = _session_store
