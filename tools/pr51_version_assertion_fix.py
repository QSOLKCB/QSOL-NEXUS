from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = '"2.0.0-alpha10.3"'
NEW = '"2.0.0"'

for rel in ("tests/test_runtime.py", "tests/test_un_sim.py"):
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"{rel}: expected exactly one stale release literal, found {count}")
    path.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
