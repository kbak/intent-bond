import hashlib
import json
import os
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

RECOVERY_RECORDS = ".traceability/recovery"


class CheckError(Exception):
    """An input or execution error, never a successful validation."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()


def write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_json(content):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise CheckError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(content, object_pairs_hook=unique)


def read_json(path: Path):
    try:
        return parse_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CheckError(f"Cannot read JSON {path}: {exc}") from exc


def xml_tree(path):
    try:
        content = path.read_bytes()
        if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
            raise CheckError(f"XML DTDs/entities are unsupported: {path}")
        return ET.fromstring(content)
    except (OSError, ET.ParseError) as exc:
        raise CheckError(f"Cannot read XML {path.name}: {exc}") from exc


def relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise CheckError(f"Expected a repository-relative POSIX path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or ".git" in path.parts or str(path) != value:
        raise CheckError(f"Unsafe or noncanonical relative path: {value!r}")
    return value


def within(path, roots):
    return any(root == "." or path == root or path.startswith(root + "/") for root in roots)


def run(command, cwd, log: Path, timeout=120, env=None):
    """Capture output and stop the whole process group on timeout (POSIX)."""
    started = time.monotonic()
    result = {"command": [str(arg) for arg in command], "status": "error", "exit_code": None}
    with log.open("wb") as output:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=output,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
            try:
                result["exit_code"] = process.wait(timeout=timeout)
                result["status"] = "passed" if process.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                result["error"] = f"Command timed out after {timeout} seconds"
            finally:
                # Also stop descendants left behind by a command that exited normally.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
        except OSError as exc:
            result["error"] = str(exc)
            output.write(str(exc).encode())
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    result["log"] = log.name
    return result
