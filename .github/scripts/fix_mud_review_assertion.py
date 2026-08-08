from pathlib import Path

path = Path("tests/test_mud.py")
text = path.read_text(encoding="utf-8")
old = '        self.assertEqual(recovered.payload["players"]["Trent"]["clout"], 10)\n'
new = '''        self.assertEqual(
            recovered.payload["players"]["Trent"]["clout"],
            defeated.payload["players"]["Trent"]["clout"] + 10,
        )
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one Crown clout assertion, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
