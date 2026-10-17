from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance, keyed by client IP. Imported by main.py (to wire the
# middleware/exception handler) and by routes that need a stricter limit than
# the app-wide default (e.g. /auth/login, which is unauthenticated).
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
