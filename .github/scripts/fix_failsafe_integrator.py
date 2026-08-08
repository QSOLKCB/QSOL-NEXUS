from pathlib import Path

path = Path('.github/scripts/apply_failsafe.py')
text = path.read_text(encoding='utf-8')
block = '''replace_once(
    "src/nexus_runtime/council.py",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n        }\\n""",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n            \\"failsafe\\": failsafe_summary,\\n        }\\n""",
)
'''
count = text.count(block)
if count != 2:
    raise SystemExit(f'expected duplicated result/telemetry patch block twice, found {count}')
replacement = '''replace_count(
    "src/nexus_runtime/council.py",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n        }\\n""",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n            \\"failsafe\\": failsafe_summary,\\n        }\\n""",
    2,
)
'''
first = text.index(block)
text = text.replace(block, '', 2)
text = text[:first] + replacement + text[first:]
path.write_text(text, encoding='utf-8')
print('Fixed duplicated Council failsafe summary anchor.')
