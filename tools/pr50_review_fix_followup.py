from pathlib import Path

path = Path("src/nexus_runtime/wall_api.py")
text = path.read_text(encoding="utf-8")
old = '''        actor = self._culture_actor(request.get("member"))
        for field, identity in (
            ("member_id", actor.member.member_id),
            ("model_id", actor.member.model_id),
        ):
'''
new = '''        # The Wall is social memory, not progression or civic duty.  Use the
        # established actor admission path directly instead of routing harmless
        # Wall speech through Failsafe/Civic Due Process identity gates.
        actor = self._actor(request.get("member"))
        for field, identity in (
            ("member_id", actor.member.member_id),
            ("model_id", actor.member.model_id),
        ):
'''
if text.count(old) != 1:
    raise SystemExit("expected the staged Wall actor block exactly once")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("PR #50 Wall actor-path follow-up applied")
