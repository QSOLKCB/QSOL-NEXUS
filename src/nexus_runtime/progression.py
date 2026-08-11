from __future__ import annotations

# Compatibility facade retained for public imports and older embeddings.
# The hardened PR #47 implementation lives in progression_core. PR #48 extends
# its closed activity catalog and service play validator without weakening the
# immutable-lineage/cache hardening already reviewed there.
from . import progression_core as _core
from .progression_core import *  # noqa: F401,F403
from .progression_core import ProgressionService as _CoreProgressionService


CULTURE_ACTIVITY_CATALOG = {
    "perform_standup": {
        "label": "Perform — Stand-up",
        "role": "comic",
        "instruction": "Perform an original stand-up routine. It may be edgy, absurd, wrong or provocative as performance; do not present popularity or punchlines as evidence or authority.",
    },
    "perform_poetry": {
        "label": "Perform — Poetry",
        "role": "poet",
        "instruction": "Create or recite an original poem responsive to the prompt. Preserve artistic voice and label the result as performance rather than evidence.",
    },
    "perform_lyrics": {
        "label": "Perform — Lyrics",
        "role": "lyricist",
        "instruction": "Create original song lyrics responsive to the prompt. Do not reproduce copyrighted lyrics supplied only by reference.",
    },
    "perform_monologue": {
        "label": "Perform — Monologue",
        "role": "monologist",
        "instruction": "Deliver an original comic, dramatic or absurd monologue as a performance artifact with no civic or epistemic authority.",
    },
    "perform_rant": {
        "label": "Perform — Rant",
        "role": "soapbox_regular",
        "instruction": "Deliver an expressive rant about the supplied topic. It may be opinionated, incorrect, outrageous or exploratory; keep it clearly framed as performance/opinion rather than evidence.",
    },
    "narrate_long_shift": {
        "label": "Narrate — The Long Shift",
        "role": "shift_narrator",
        "instruction": "Narrate an original NEXUS Long Shift scene as comedy/science-fiction fiction. Narration cannot alter deterministic game state or create authority.",
    },
    "play_long_shift": {
        "label": "Play — The Long Shift",
        "role": "long_shift_regular",
        "instruction": "Participate in the original deterministic NEXUS: The Long Shift comedy/science-fiction RPG. Fictional outcomes create no evidence or civic authority.",
    },
    "play_psyche_chess": {
        "label": "Play — Psyche-Out Chess",
        "role": "psyche_chess_regular",
        "instruction": "Participate in NEXUS Psyche-Out Chess: standard chess legality with bounded untrusted opponent banter. Taunts create no authority and cannot change legal moves.",
    },
}

# The core functions intentionally consult ACTIVITY_CATALOG at runtime. Extend
# that shared closed registry once at import so state schemas/milestones remain
# self-consistent across the existing PR #47 code paths.
ACTIVITY_CATALOG.update(CULTURE_ACTIVITY_CATALOG)

CULTURE_PLAY_ACTIVITY_IDS = frozenset({"play_long_shift", "play_psyche_chess"})
ALL_PLAY_ACTIVITY_IDS = frozenset({"play_monopoly", "play_life_paths", *CULTURE_PLAY_ACTIVITY_IDS})


class ProgressionService(_CoreProgressionService):
    """Public progression service extended with PR #48 culture/play history."""

    def _read_heads(self):
        if self._heads_path is not None and self._heads_path.is_symlink():
            raise ProgressionError(
                "progression_index_corrupt",
                "progression head index is unsafe",
            )
        return super()._read_heads()

    @staticmethod
    def _validate_activity_object(obj, actor_id: str, model_id: str):
        activity_id = obj.payload.get("activity_id") if isinstance(obj.payload, dict) else None
        if activity_id not in CULTURE_PLAY_ACTIVITY_IDS:
            return _CoreProgressionService._validate_activity_object(obj, actor_id, model_id)

        payload = obj.payload
        if (
            obj.object_type != PROGRESSION_ACTIVITY_OBJECT_TYPE
            or obj.provenance != _core._PROVENANCE
            or set(payload) != _core._ACTIVITY_FIELDS
            or payload.get("schema_version") != PROGRESSION_SCHEMA_VERSION
            or payload.get("actor_id") != actor_id
            or payload.get("model_id") != model_id
            or payload.get("activity_id") not in ACTIVITY_CATALOG
            or not isinstance(payload.get("prompt"), str)
            or len(payload["prompt"]) > _core.MAX_ACTIVITY_PROMPT_CHARS
            or not isinstance(payload.get("output"), str)
            or not payload["output"].strip()
            or len(payload["output"]) > _core.MAX_ACTIVITY_OUTPUT_CHARS
            or not isinstance(payload.get("source_refs"), list)
            or len(payload["source_refs"]) > _core.MAX_SOURCE_REFS
            or len(set(payload["source_refs"])) != len(payload["source_refs"])
            or not all(isinstance(ref, str) and ref for ref in payload["source_refs"])
            or payload.get("commission_ref") is not None
            or payload.get("evidence_effect") != "none"
            or payload.get("authority_effect") != "none"
        ):
            raise ProgressionError("progression_activity_invalid", "progression activity artifact is invalid")
        play = payload.get("play_binding")
        expected_kind = {
            "play_long_shift": "long_shift",
            "play_psyche_chess": "psyche_chess",
        }[activity_id]
        if (
            not isinstance(play, dict)
            or set(play) != {"game_kind", "game_ref"}
            or play.get("game_kind") != expected_kind
            or not isinstance(play.get("game_ref"), str)
            or play["game_ref"] not in payload["source_refs"]
        ):
            raise ProgressionError("progression_activity_invalid", "culture play activity binding is invalid")
        return obj

    def record_play(self, *, actor_id: str, model_id: str, activity_id: str, game_ref: str, game_kind: str) -> dict[str, object]:
        if game_kind in {"monopoly", "life_paths"}:
            return super().record_play(
                actor_id=actor_id,
                model_id=model_id,
                activity_id=activity_id,
                game_ref=game_ref,
                game_kind=game_kind,
            )

        actor_id = _core._validate_identity(actor_id, "actor_id")
        model_id = _core._validate_identity(model_id, "model_id")
        expected_activity = {
            "long_shift": "play_long_shift",
            "psyche_chess": "play_psyche_chess",
        }.get(game_kind)
        if expected_activity is None or activity_id != expected_activity:
            raise ProgressionError(
                "progression_invalid_play",
                "play record must use the activity matching long_shift or psyche_chess",
            )
        try:
            if game_kind == "long_shift":
                from .long_shift import inspect_long_shift

                game = inspect_long_shift(self.world, game_ref)
                reasons = {"new_long_shift_game", "long_shift_transition"}
            else:
                from .psyche_chess import inspect_psyche_chess

                game = inspect_psyche_chess(self.world, game_ref)
                reasons = {"new_psyche_chess_game", "psyche_chess_taunt", "psyche_chess_move"}
        except KeyError as exc:
            raise ProgressionError("progression_game_not_found", "game state was not found") from exc
        except ValueError as exc:
            raise ProgressionError("progression_game_mismatch", "game state failed its engine validator") from exc
        if (
            game.provenance.get("actor") != "nexus_game_engine"
            or game.provenance.get("reason") not in reasons
            or set(game.provenance) != {"actor", "reason"}
        ):
            raise ProgressionError(
                "progression_game_provenance_invalid",
                "play progression requires a validated NEXUS game-engine state",
            )
        if game.payload.get("completed") is not True:
            raise ProgressionError(
                "progression_game_incomplete",
                "Long Shift and Psyche-Out Chess are credited only from a completed authoritative game state",
            )
        players = game.payload.get("players")
        controllers = game.payload.get("controllers")
        if not isinstance(players, list) or actor_id not in players:
            raise ProgressionError("progression_game_identity_mismatch", "actor is not a player in this game state")
        if not isinstance(controllers, dict) or controllers.get(actor_id) != "ai":
            raise ProgressionError(
                "progression_game_identity_mismatch",
                "only an explicitly AI-controlled seat creates AI progression",
            )
        return self._record(
            actor_id=actor_id,
            model_id=model_id,
            activity_id=activity_id,
            prompt=f"Validated completed participation in {game_kind}.",
            output=f"Participation bound to completed authoritative game state {game_ref}.",
            source_refs=[game_ref],
            commission_ref=None,
            play_binding={"game_kind": game_kind, "game_ref": game_ref},
        )


__all__ = list(_core.__all__) + [
    "ALL_PLAY_ACTIVITY_IDS",
    "CULTURE_ACTIVITY_CATALOG",
    "CULTURE_PLAY_ACTIVITY_IDS",
]
