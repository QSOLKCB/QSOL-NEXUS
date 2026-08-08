from pathlib import Path

path = Path('.github/scripts/apply_failsafe.py')
text = path.read_text(encoding='utf-8')

generic = '''replace_once(
    "src/nexus_runtime/council.py",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n        }\\n""",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n            \\"failsafe\\": failsafe_summary,\\n        }\\n""",
)
'''
if text.count(generic) != 1:
    raise SystemExit(f'expected generic result/telemetry patch once, found {text.count(generic)}')
generic_replacement = '''replace_count(
    "src/nexus_runtime/council.py",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n        }\\n""",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n            \\"failsafe\\": failsafe_summary,\\n        }\\n""",
    2,
)
'''
text = text.replace(generic, generic_replacement, 1)

contextual = '''replace_once(
    "src/nexus_runtime/council.py",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n        }\\n\\n    def build_evidence_context\\n""",
    """            \\"result\\": result,\\n            \\"telemetry\\": telemetry,\\n            \\"failsafe\\": failsafe_summary,\\n        }\\n\\n    def build_evidence_context\\n""",
)
'''
if text.count(contextual) != 1:
    raise SystemExit(f'expected contextual response patch once, found {text.count(contextual)}')
text = text.replace(contextual, '', 1)

path.write_text(text, encoding='utf-8')
print('Fixed Council failsafe summary integration to update both payload and response.')
