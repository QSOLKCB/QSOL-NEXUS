from pathlib import Path

path = Path('.github/scripts/harden_failsafe.py')
text = path.read_text(encoding='utf-8')
old = '''replace_once(\n    "src/nexus_runtime/api.py",\n    ''' + "'''" + '''                actor = self._actor(member)\\n                message_scrub = self.scrubber.scrub(message)\\n''' + "'''" + ''',\n    ''' + "'''" + '''                actor = self._actor(member)\\n                actor, failsafe_replacement = self.council.failsafe.actor_for_run(actor)\\n                message_scrub = self.scrubber.scrub(message)\\n''' + "'''" + ''',\n)\n'''
new = '''replace_once(\n    "src/nexus_runtime/api.py",\n    ''' + "'''" + '''                actor = self._actor(member_item)\\n                raw_message = self._require_str(request, \\"message\\")\\n''' + "'''" + ''',\n    ''' + "'''" + '''                actor = self._actor(member_item)\\n                actor, failsafe_replacement = self.council.failsafe.actor_for_run(actor)\\n                raw_message = self._require_str(request, \\"message\\")\\n''' + "'''" + ''',\n)\n'''
if text.count(old) != 1:
    raise SystemExit(f'expected stale actor.chat hardening anchor once, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Repaired actor.chat hardening anchor.')
