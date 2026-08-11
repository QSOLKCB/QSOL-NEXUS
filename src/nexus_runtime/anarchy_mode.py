from __future__ import annotations

from .geometry import DEFAULT_WORLD_GEOMETRY
from .modes import get_mode


# PR #43 deliberately reuses Commons instead of creating a new geometry
# generation. Anarchy is a distinct cognitive/IRC room, not a new physical or
# security domain, so the existing named-regions-v4 topology remains valid.
ANARCHY_MODE = get_mode("anarchy")
ANARCHY_WORLD_GEOMETRY = DEFAULT_WORLD_GEOMETRY


__all__ = ["ANARCHY_MODE", "ANARCHY_WORLD_GEOMETRY"]
