from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass

from .canonical import sha256_ref
from .modes import list_modes


_GEOMETRY_SEMANTICS = "operational_topology_not_physical_claim"


@dataclass(frozen=True)
class WorldRegion:
    region_id: str
    label: str
    x: int
    y: int
    neighbors: tuple[str, ...]
    description: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class WorldGeometry:
    """Small deterministic topological map for the shared NEXUS world.

    This is an operational geometry: named regions, integer coordinates and
    explicit adjacency. It is not a claim that semantic relationships possess
    literal physical geometry.
    """

    def __init__(self, regions: tuple[WorldRegion, ...], *, geometry_id: str | None = None) -> None:
        if not regions:
            raise ValueError("world geometry requires at least one region")
        for region in regions:
            if type(region.x) is not int or type(region.y) is not int:
                raise ValueError("world geometry coordinates must be exact integers")

        self._regions = {region.region_id: region for region in regions}
        if len(self._regions) != len(regions):
            raise ValueError("world geometry region_id values must be unique")
        coordinates = {(region.x, region.y) for region in regions}
        if len(coordinates) != len(regions):
            raise ValueError("world geometry coordinates must be unique")

        for region in regions:
            for neighbor in region.neighbors:
                if neighbor not in self._regions:
                    raise ValueError(f"unknown geometry neighbor: {neighbor}")
                if region.region_id not in self._regions[neighbor].neighbors:
                    raise ValueError("world geometry adjacency must be symmetric")

        for mode in list_modes():
            if mode.region_id not in self._regions:
                raise ValueError(f"mode {mode.mode_id} references unknown region {mode.region_id}")

        reachable = self._reachable_from(regions[0].region_id)
        if len(reachable) != len(self._regions):
            missing = sorted(set(self._regions) - reachable)
            raise ValueError(f"world geometry must be fully connected; unreachable regions: {', '.join(missing)}")

        topology_body = {
            "semantics": _GEOMETRY_SEMANTICS,
            "regions": [self._regions[key].as_dict() for key in sorted(self._regions)],
        }
        self._topology_ref = sha256_ref("geometry", topology_body)
        if geometry_id is not None and (not isinstance(geometry_id, str) or not geometry_id.strip()):
            raise ValueError("geometry_id must be a non-empty string when provided")
        self._geometry_id = geometry_id.strip() if geometry_id is not None else self._topology_ref

    def _reachable_from(self, source_region_id: str) -> set[str]:
        seen = {source_region_id}
        queue: deque[str] = deque([source_region_id])
        while queue:
            current = queue.popleft()
            for neighbor in self._regions[current].neighbors:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return seen

    def region(self, region_id: str) -> WorldRegion:
        try:
            return self._regions[region_id]
        except KeyError as exc:
            raise ValueError(f"unknown world region: {region_id}") from exc

    def region_for_mode(self, mode_id: str) -> WorldRegion:
        from .modes import get_mode

        return self.region(get_mode(mode_id).region_id)

    def distance(self, source_region_id: str, target_region_id: str) -> int:
        self.region(source_region_id)
        self.region(target_region_id)
        if source_region_id == target_region_id:
            return 0
        queue: deque[tuple[str, int]] = deque([(source_region_id, 0)])
        seen = {source_region_id}
        while queue:
            current, distance = queue.popleft()
            for neighbor in self._regions[current].neighbors:
                if neighbor == target_region_id:
                    return distance + 1
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append((neighbor, distance + 1))
        raise RuntimeError("validated world geometry became disconnected")

    def snapshot(self) -> dict[str, object]:
        return {
            "geometry_id": self._geometry_id,
            "topology_ref": self._topology_ref,
            "semantics": _GEOMETRY_SEMANTICS,
            "regions": [self._regions[key].as_dict() for key in sorted(self._regions)],
        }


DEFAULT_WORLD_GEOMETRY = WorldGeometry(
    (
        WorldRegion(
            "observatory",
            "Observatory",
            0,
            0,
            ("archive", "agora", "commons"),
            "Default evidence-first analytical region.",
        ),
        WorldRegion(
            "archive",
            "Archive",
            -2,
            1,
            ("observatory", "agora"),
            "Historical region for chronology, sources, lineage and contextual reconstruction.",
        ),
        WorldRegion(
            "agora",
            "Agora",
            0,
            2,
            ("archive", "observatory", "commons"),
            "Cultural region for norms, ambiguity, comparison and social meaning.",
        ),
        WorldRegion(
            "commons",
            "Commons",
            2,
            1,
            ("observatory", "agora"),
            "Meme/casual region for playful interaction without relaxing evidence boundaries.",
        ),
    ),
    geometry_id="named-regions-v1",
)
