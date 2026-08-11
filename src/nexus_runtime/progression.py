from __future__ import annotations

# Compatibility facade retained for public imports and older embeddings.
# The hardened implementation lives in progression_core so review fixes can
# replace the original implementation without changing the public module path.
from .progression_core import *  # noqa: F401,F403
from .progression_core import __all__
