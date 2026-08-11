from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from typing import Sequence


OPERATOR_CONFIG_SCHEMA = "nexus-operator-config/1"
_NICK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,31}$")


class OperatorToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class OperatorPaths:
    repo: Path
    venv: Path
    python: Path
    runtime_cli: Path
    world: Path
    trap: Path
    stenographer: Path
    config_dir: Path
    config: Path
    tui_manifest: Path
    tui_binary: Path


def _repo_root() -> Path:
    override = os.environ.get("NEXUS_REPO_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def operator_paths(repo: Path | None = None) -> OperatorPaths:
    root = (repo or _repo_root()).resolve()
    if repo is None and os.environ.get("NEXUS_VENV"):
        venv = Path(os.environ["NEXUS_VENV"]).expanduser().resolve()
    else:
        venv = root / ".venv"
    return OperatorPaths(
        repo=root,
        venv=venv,
        python=venv / "bin" / "python",
        runtime_cli=venv / "bin" / "nexus",
        world=root / ".nexus-world",
        trap=root / ".nexus-trap",
        stenographer=root / ".nexus-stenographer",
        config_dir=root / ".nexus",
        config=root / ".nexus" / "operator.json",
        tui_manifest=root / "tui" / "Cargo.toml",
        tui_binary=root / "tui" / "target" / "release" / "nexus",
    )


def _bounded_nick(value: str | None) -> str:
    candidate = (value or "").strip()
    if _NICK_RE.fullmatch(candidate):
        return candidate
    raise OperatorToolError(
        "operator nickname must be 1-32 characters using letters, digits, '.', '_' or '-'"
    )


def _default_nick() -> str:
    for candidate in (os.environ.get("USER"), os.environ.get("USERNAME"), "operator"):
        try:
            return _bounded_nick(candidate)
        except OperatorToolError:
            continue
    return "operator"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _ensure_private_directory(path: Path, *, fix_permissions: bool = True) -> None:
    if path.is_symlink():
        raise OperatorToolError(f"refusing symlinked private directory: {path}")
    if path.exists() and not path.is_dir():
        raise OperatorToolError(f"private storage path is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt" and _mode(path) != 0o700:
        if not fix_permissions:
            raise OperatorToolError(
                f"private directory must have mode 0700: {path} (found {_mode(path):04o})"
            )
        path.chmod(0o700)


def _ensure_disjoint(paths: OperatorPaths) -> None:
    named = {
        "venv": paths.venv.resolve(),
        "world": paths.world.resolve(),
        "trap": paths.trap.resolve(),
        "stenographer": paths.stenographer.resolve(),
        "operator_config": paths.config_dir.resolve(),
    }
    items = list(named.items())
    for index, (left_name, left) in enumerate(items):
        for right_name, right in items[index + 1 :]:
            if left == right or left.is_relative_to(right) or right.is_relative_to(left):
                raise OperatorToolError(
                    f"operator roots must be disjoint: {left_name}={left} overlaps {right_name}={right}"
                )


def _load_config(paths: OperatorPaths) -> dict[str, object]:
    if not paths.config.exists():
        return {"schema_version": OPERATOR_CONFIG_SCHEMA, "nick": _default_nick()}
    if paths.config.is_symlink():
        raise OperatorToolError(f"refusing symlinked operator config: {paths.config}")
    if os.name != "nt" and _mode(paths.config) != 0o600:
        raise OperatorToolError(
            f"operator config must have mode 0600: {paths.config} (found {_mode(paths.config):04o})"
        )
    try:
        raw = json.loads(paths.config.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise OperatorToolError(f"operator config is unreadable: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != {"schema_version", "nick"}:
        raise OperatorToolError("operator config has an invalid closed schema")
    if raw.get("schema_version") != OPERATOR_CONFIG_SCHEMA:
        raise OperatorToolError("operator config schema version is unsupported")
    raw["nick"] = _bounded_nick(raw.get("nick") if isinstance(raw.get("nick"), str) else None)
    return raw


def _save_config(paths: OperatorPaths, nick: str) -> None:
    _ensure_private_directory(paths.config_dir)
    if paths.config.is_symlink():
        raise OperatorToolError(f"refusing symlinked operator config: {paths.config}")
    payload = {
        "schema_version": OPERATOR_CONFIG_SCHEMA,
        "nick": _bounded_nick(nick),
    }
    temporary = paths.config.with_name(f".{paths.config.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        if os.name != "nt":
            temporary.chmod(0o600)
        temporary.replace(paths.config)
        if os.name != "nt":
            paths.config.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _prepare_storage(paths: OperatorPaths, *, fix_permissions: bool = True) -> None:
    _ensure_disjoint(paths)
    for path in (paths.world, paths.trap, paths.stenographer, paths.config_dir):
        _ensure_private_directory(path, fix_permissions=fix_permissions)


def _source_newer_than_binary(paths: OperatorPaths) -> bool:
    if not paths.tui_binary.is_file():
        return True
    binary_mtime = paths.tui_binary.stat().st_mtime_ns
    candidates = [paths.tui_manifest, paths.repo / "tui" / "Cargo.lock"]
    src = paths.repo / "tui" / "src"
    if src.is_dir():
        candidates.extend(path for path in src.rglob("*") if path.is_file())
    return any(path.is_file() and path.stat().st_mtime_ns > binary_mtime for path in candidates)


def _cargo() -> str:
    executable = shutil.which("cargo")
    if executable is None:
        raise OperatorToolError(
            "Rust cargo is required to build the TUI; install a Rust toolchain or use './nexus demo'"
        )
    return executable


def _build_tui(paths: OperatorPaths, *, force: bool = False) -> bool:
    stale = _source_newer_than_binary(paths)
    if not force and not stale:
        return False
    print("[nexus] building Rust TUI release binary...", file=sys.stderr)
    subprocess.run(
        [_cargo(), "build", "--manifest-path", str(paths.tui_manifest), "--release"],
        cwd=paths.repo,
        check=True,
    )
    if not paths.tui_binary.is_file():
        raise OperatorToolError(f"cargo completed but TUI binary is missing: {paths.tui_binary}")
    return True


def _runtime_command(paths: OperatorPaths, extra: Sequence[str]) -> list[str]:
    if not paths.runtime_cli.is_file():
        raise OperatorToolError(
            f"installed NEXUS runtime CLI is missing: {paths.runtime_cli}; rerun ./nexus setup"
        )
    return [
        str(paths.runtime_cli),
        "--world",
        str(paths.world),
        "--trap-root",
        str(paths.trap),
        "--stenographer-root",
        str(paths.stenographer),
        *extra,
    ]


def _health(paths: OperatorPaths) -> dict[str, object]:
    completed = subprocess.run(
        _runtime_command(paths, []),
        cwd=paths.repo,
        input='{"operation":"system.health"}\n',
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"runtime exited {completed.returncode}"
        raise OperatorToolError(f"runtime health probe failed: {message}")
    line = next((item for item in completed.stdout.splitlines() if item.strip()), "")
    try:
        response = json.loads(line)
    except json.JSONDecodeError as exc:
        raise OperatorToolError("runtime health probe returned invalid JSON") from exc
    if not isinstance(response, dict) or response.get("status") != "ok":
        raise OperatorToolError(f"runtime health probe returned failure: {response}")
    return response


def _package_version() -> str:
    try:
        return importlib.metadata.version("qsol-nexus-runtime")
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def _tui_version(paths: OperatorPaths) -> str:
    try:
        with paths.tui_manifest.open("rb") as handle:
            manifest = tomllib.load(handle)
        package = manifest.get("package", {})
        version = package.get("version") if isinstance(package, dict) else None
        return version if isinstance(version, str) else "unknown"
    except (OSError, tomllib.TOMLDecodeError):
        return "unknown"


def _print_path_report(paths: OperatorPaths, *, as_json: bool) -> int:
    payload = {
        "repo": str(paths.repo),
        "venv": str(paths.venv),
        "python": str(paths.python),
        "runtime_cli": str(paths.runtime_cli),
        "world": str(paths.world),
        "trap": str(paths.trap),
        "stenographer": str(paths.stenographer),
        "operator_config": str(paths.config),
        "tui_binary": str(paths.tui_binary),
    }
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        width = max(len(key) for key in payload)
        for key, value in payload.items():
            print(f"{key:<{width}}  {value}")
    return 0


def _doctor(paths: OperatorPaths, *, fix: bool) -> int:
    rows: list[tuple[str, str, str]] = []

    def add(level: str, name: str, detail: str) -> None:
        rows.append((level, name, detail))

    if sys.version_info >= (3, 11):
        add("OK", "Python", sys.version.split()[0])
    else:
        add("FAIL", "Python", f"requires >=3.11, found {sys.version.split()[0]}")

    if paths.python.is_file():
        add("OK", "Virtualenv", str(paths.venv))
    else:
        add("FAIL", "Virtualenv", f"missing {paths.python}")

    package_version = _package_version()
    add("OK" if package_version != "not-installed" else "FAIL", "Runtime package", package_version)

    for label, path in (
        ("WorldStore", paths.world),
        ("Trap Base", paths.trap),
        ("Stenographer", paths.stenographer),
        ("Operator config dir", paths.config_dir),
    ):
        try:
            if fix:
                _ensure_private_directory(path)
            if path.is_symlink() or not path.is_dir():
                raise OperatorToolError("missing, non-directory, or symlink")
            mode = _mode(path) if os.name != "nt" else 0o700
            if os.name != "nt" and mode != 0o700:
                raise OperatorToolError(f"mode {mode:04o}; expected 0700")
            add("OK", label, f"{path} (private)")
        except (OSError, OperatorToolError) as exc:
            add("FAIL", label, str(exc))

    try:
        if paths.config.exists():
            if paths.config.is_symlink():
                raise OperatorToolError("operator config is a symlink")
            if fix and os.name != "nt" and _mode(paths.config) != 0o600:
                paths.config.chmod(0o600)
            if os.name != "nt" and _mode(paths.config) != 0o600:
                raise OperatorToolError(f"mode {_mode(paths.config):04o}; expected 0600")
            _load_config(paths)
            add("OK", "Operator config file", f"{paths.config} (closed/private)")
        else:
            add("WARN", "Operator config file", "not created yet; setup/TUI will create it")
    except (OSError, OperatorToolError) as exc:
        add("FAIL", "Operator config file", str(exc))

    stale = _source_newer_than_binary(paths)
    if stale and fix:
        try:
            _build_tui(paths)
            stale = False
        except (OSError, subprocess.SubprocessError, OperatorToolError) as exc:
            add("FAIL", "Rust TUI", str(exc))
    if not any(name == "Rust TUI" for _, name, _ in rows):
        if paths.tui_binary.is_file() and not stale:
            add("OK", "Rust TUI", f"{_tui_version(paths)} release binary ready")
        elif paths.tui_binary.is_file():
            add("WARN", "Rust TUI", "release binary exists but source is newer")
        else:
            add("WARN", "Rust TUI", "release binary not built")

    storage_failed = any(
        level == "FAIL" and name in {"WorldStore", "Trap Base", "Stenographer"}
        for level, name, _ in rows
    )
    if not storage_failed and paths.runtime_cli.is_file():
        try:
            health = _health(paths)
            protocol = health.get("protocol_version", health.get("protocol", "?"))
            runtime = health.get("runtime_version", health.get("runtime", "?"))
            add("OK", "Runtime health", f"protocol={protocol} runtime={runtime}")
        except (OSError, subprocess.SubprocessError, OperatorToolError) as exc:
            add("FAIL", "Runtime health", str(exc))
    else:
        add("WARN", "Runtime health", "skipped until runtime/storage prerequisites are healthy")

    print("QSOL NEXUS DOCTOR")
    print("=" * 72)
    for level, name, detail in rows:
        print(f"[{level:<4}] {name:<20} {detail}")
    failures = sum(level == "FAIL" for level, _, _ in rows)
    warnings = sum(level == "WARN" for level, _, _ in rows)
    print("=" * 72)
    if failures:
        print(f"NEXUS NOT READY: {failures} failure(s), {warnings} warning(s)")
        if not fix:
            print("Run './nexus doctor --fix' for safe non-destructive fixes.")
        return 2
    print(f"NEXUS READY ({warnings} warning(s))")
    return 0


def _setup(paths: OperatorPaths, *, nick: str | None, build: bool) -> int:
    _prepare_storage(paths)
    config = _load_config(paths)
    selected_nick = _bounded_nick(nick) if nick is not None else str(config["nick"])
    _save_config(paths, selected_nick)
    if build:
        _build_tui(paths)
    health = _health(paths)
    print("QSOL NEXUS setup complete")
    print(f"operator: {selected_nick}")
    print(f"world:    {paths.world}")
    print(f"runtime:  {health.get('runtime_version', health.get('runtime', '?'))}")
    if build:
        print(f"tui:      {paths.tui_binary}")
    return 0


def _launch_tui(paths: OperatorPaths, *, nick: str | None) -> int:
    _prepare_storage(paths)
    config = _load_config(paths)
    selected_nick = _bounded_nick(nick) if nick is not None else str(config["nick"])
    if not paths.config.exists() or selected_nick != config["nick"]:
        _save_config(paths, selected_nick)
    _build_tui(paths)
    environment = dict(os.environ)
    environment["NEXUS_PYTHON"] = str(paths.python)
    command = [
        str(paths.tui_binary),
        "--world",
        str(paths.world),
        "--trap-root",
        str(paths.trap),
        "--stenographer-root",
        str(paths.stenographer),
        "--nick",
        selected_nick,
    ]
    return subprocess.run(command, cwd=paths.repo, env=environment, check=False).returncode


def _demo(paths: OperatorPaths) -> int:
    _prepare_storage(paths)
    return subprocess.run(_runtime_command(paths, ["--demo"]), cwd=paths.repo, check=False).returncode


def _runtime_passthrough(paths: OperatorPaths, arguments: Sequence[str]) -> int:
    _prepare_storage(paths)
    return subprocess.run(_runtime_command(paths, list(arguments)), cwd=paths.repo, check=False).returncode


def _update(paths: OperatorPaths) -> int:
    print("[nexus] refreshing editable Python runtime...", file=sys.stderr)
    subprocess.run(
        [str(paths.python), "-m", "pip", "install", "-e", str(paths.repo)],
        cwd=paths.repo,
        check=True,
    )
    _prepare_storage(paths)
    _build_tui(paths, force=True)
    return _doctor(paths, fix=False)


def _test(paths: OperatorPaths) -> int:
    python = subprocess.run(
        [str(paths.python), "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=paths.repo,
        check=False,
    )
    if python.returncode != 0:
        return python.returncode
    rust = subprocess.run(
        [_cargo(), "test", "--manifest-path", str(paths.tui_manifest)],
        cwd=paths.repo,
        check=False,
    )
    return rust.returncode


def _version(paths: OperatorPaths, *, as_json: bool) -> int:
    payload: dict[str, object] = {
        "operator_tooling": "nexus-operator-tooling/1",
        "python_package": _package_version(),
        "rust_tui": _tui_version(paths),
    }
    try:
        health = _health(paths)
        payload["protocol"] = health.get("protocol_version", health.get("protocol"))
        payload["runtime"] = health.get("runtime_version", health.get("runtime"))
    except (OSError, subprocess.SubprocessError, OperatorToolError):
        payload["runtime_health"] = "unavailable"
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="./nexus",
        description="QSOL NEXUS one-command operator launcher",
    )
    sub = parser.add_subparsers(dest="command")

    setup = sub.add_parser("setup", help="create safe local state and build the operator TUI")
    setup.add_argument("--nick", default=None)
    setup.add_argument("--no-build", action="store_true")

    doctor = sub.add_parser("doctor", help="diagnose the local installation")
    doctor.add_argument("--fix", action="store_true", help="apply safe non-destructive fixes")

    tui = sub.add_parser("tui", help="launch the IRC-style operator shell")
    tui.add_argument("--nick", default=None)

    sub.add_parser("demo", help="run the deterministic mock Council smoke test")

    paths = sub.add_parser("paths", help="show resolved runtime and storage paths")
    paths.add_argument("--json", action="store_true")

    version = sub.add_parser("version", help="show component versions")
    version.add_argument("--json", action="store_true")

    sub.add_parser("update", help="refresh the editable runtime and rebuild the TUI")
    sub.add_parser("test", help="run Python and Rust regression suites")
    sub.add_parser("help", help="show this help message")

    runtime = sub.add_parser("runtime", help="pass arguments to the underlying Python NEXUS CLI")
    runtime.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    command = args.command or "tui"
    paths = operator_paths()
    try:
        if command == "help":
            parser.print_help()
            return 0
        if command == "setup":
            return _setup(paths, nick=args.nick, build=not args.no_build)
        if command == "doctor":
            return _doctor(paths, fix=args.fix)
        if command == "tui":
            return _launch_tui(paths, nick=getattr(args, "nick", None))
        if command == "demo":
            return _demo(paths)
        if command == "paths":
            return _print_path_report(paths, as_json=args.json)
        if command == "version":
            return _version(paths, as_json=args.json)
        if command == "update":
            return _update(paths)
        if command == "test":
            return _test(paths)
        if command == "runtime":
            forwarded = list(args.args)
            if forwarded[:1] == ["--"]:
                forwarded = forwarded[1:]
            return _runtime_passthrough(paths, forwarded)
        raise OperatorToolError(f"unsupported operator command: {command}")
    except KeyboardInterrupt:
        print("\n[nexus] interrupted", file=sys.stderr)
        return 130
    except (OSError, subprocess.SubprocessError, OperatorToolError) as exc:
        print(f"[nexus] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
