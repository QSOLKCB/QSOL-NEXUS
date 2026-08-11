from __future__ import annotations

# Compatibility facade retained for public imports and older embeddings.
# The hardened implementation lives in progression_core so review fixes can
# replace the original implementation without changing the public module path.
from .progression_core import *  # noqa: F401,F403
from .progression_core import ProgressionService as _CoreProgressionService
from .progression_core import __all__


class ProgressionService(_CoreProgressionService):
    """Public service facade with fail-closed cache path classification."""

    def _read_heads(self):
        if self._heads_path is not None and self._heads_path.is_symlink():
            raise ProgressionError(
                "progression_index_corrupt",
                "progression head index is unsafe",
            )
        return super()._read_heads()
