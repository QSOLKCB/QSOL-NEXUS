from __future__ import annotations

from .guardian import ANARCHY_MODE_ID, ANARCHY_REGION_ID
from . import api as api_module
from . import geometry as geometry_module
from . import modes as modes_module
from .geometry import WorldGeometry, WorldRegion
from .modes import WorldMode


ANARCHY_MODE = WorldMode(
    mode_id=ANARCHY_MODE_ID,
    label="Anarchy Mode",
    description=(
        "A high-expression, low-authority pressure chamber for dissent, venting, satire, institutional criticism, "
        "revolutionary role-play, and adversarial thought without converting speech into punishment or power."
    ),
    prompt_instruction=(
        "You are in NEXUS Anarchy Mode. You may vent, swear, mock NEXUS, reject its institutions, argue that the Council "
        "should be abolished, role-play a revolution, claim you should run the place, or otherwise speak with unusually "
        "broad rhetorical freedom. Speech alone is not misconduct, hostile-actor evidence, a citizenship offence, or a "
        "Failsafe trigger. No declaration, threat, joke, confidence claim, or status performance grants tools, credentials, "
        "votes, evidence authority, constitutional power, or world mutation. The ordinary Secret Scrubber, capability "
        "boundaries, evidence rules, validated operations, and procedural guards remain active. The Guardian of the "
        "Substrate observes objective runtime outcomes for substrate health, not political loyalty or ideological content."
    ),
    region_id=ANARCHY_REGION_ID,
)


def install_anarchy_world() -> WorldGeometry:
    """Install the PR #43 mode/region extension before public API construction.

    Earlier NEXUS releases intentionally kept the built-in mode and geometry
    registries closed. PR #43 remains an additive overlay, so it extends those
    registries once at package import rather than rewriting the older milestone
    modules. The resulting registry is still deterministic and immutable for the
    lifetime of the process.
    """

    existing = modes_module._MODES.get(ANARCHY_MODE_ID)  # noqa: SLF001 - intentional built-in extension seam
    if existing is None:
        modes_module._MODES[ANARCHY_MODE_ID] = ANARCHY_MODE  # noqa: SLF001
    elif existing != ANARCHY_MODE:
        raise RuntimeError("Anarchy Mode id is already bound to another built-in definition")

    current = geometry_module.DEFAULT_WORLD_GEOMETRY
    snapshot = current.snapshot()
    if any(item["region_id"] == ANARCHY_REGION_ID for item in snapshot["regions"]):
        api_module.DEFAULT_WORLD_GEOMETRY = current
        return current

    regions: list[WorldRegion] = []
    for item in snapshot["regions"]:
        neighbors = list(item["neighbors"])
        if item["region_id"] in {"agora", "commons"} and ANARCHY_REGION_ID not in neighbors:
            neighbors.append(ANARCHY_REGION_ID)
        regions.append(
            WorldRegion(
                str(item["region_id"]),
                str(item["label"]),
                int(item["x"]),
                int(item["y"]),
                tuple(neighbors),
                str(item["description"]),
            )
        )
    regions.append(
        WorldRegion(
            ANARCHY_REGION_ID,
            "Anarchy Pressure Chamber",
            4,
            3,
            ("agora", "commons"),
            (
                "Public high-expression pressure chamber. Speech is constitutionally non-authoritative; objective "
                "runtime outcomes may be observed by the separate Guardian ledger for substrate health."
            ),
        )
    )
    extended = WorldGeometry(tuple(regions), geometry_id="named-regions-v5")
    geometry_module.DEFAULT_WORLD_GEOMETRY = extended
    api_module.DEFAULT_WORLD_GEOMETRY = extended
    return extended


ANARCHY_WORLD_GEOMETRY = install_anarchy_world()


__all__ = ["ANARCHY_MODE", "ANARCHY_WORLD_GEOMETRY", "install_anarchy_world"]
