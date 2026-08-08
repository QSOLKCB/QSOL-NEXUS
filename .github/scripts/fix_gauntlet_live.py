from pathlib import Path

path = Path('tools/nexus_adversary.py')
text = path.read_text(encoding='utf-8')
old = '''                            [
                                sys.executable,
                                "-m",
                                "unittest",
                                "tests.test_ollama_integration",
                                "-v",
                            ],
'''
new = '''                            [
                                sys.executable,
                                "-m",
                                "unittest",
                                "discover",
                                "-s",
                                "tests",
                                "-p",
                                "test_ollama_integration.py",
                                "-v",
                            ],
'''
if text.count(old) != 1:
    raise SystemExit(f'expected live invocation anchor once, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Aligned live gauntlet invocation with canonical Ollama CI discovery command.')
