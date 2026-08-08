from pathlib import Path

path = Path("tui/src/go64.rs")
text = path.read_text(encoding="utf-8")
old = '        choose(&lessons, &format!("{input}:{interaction}"))\n'
new = '        return vec![choose(&lessons, &format!("{input}:{interaction}")).to_string()];\n'
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected GO64 lifetime anchor once, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
