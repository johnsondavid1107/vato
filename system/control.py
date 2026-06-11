"""SystemControl: the single interface through which ALL OS interaction goes
(spec §7), so the codebase ports MacBook → Mac mini with zero logic changes.

The workspace jail AND the §6 hard denylist are enforced HERE, mechanically —
not left to the LLM. Denied commands raise DenylistError carrying the
in-character refusal; no amount of prompting (or confirmation) runs them.
"""

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

WORKSPACE = Path.home() / "VatoWorkspace"
REPO_ROOT = Path(__file__).resolve().parent.parent

REFUSAL = "I'm afraid that's quite beyond my station, sir."


class DenylistError(PermissionError):
    """A §6 hard-denylist hit — refused even with confirmation."""


# ── §6 hard denylist (checked against the joined command string) ─────────────
_DENY_PATTERNS: list[tuple[str, str]] = [
    (r"^sudo\b", "elevated privileges"),
    (r"^(diskutil\s+(erase|partition|reformat|zero)|mkfs|newfs)",
     "disk formatting/wiping"),
    (r"^dd\b.*\bof=/dev/", "writing raw devices"),
    (r"^(csrutil|spctl|tccutil|systemsetup|networksetup)\b",
     "security/network settings"),
    (r"^security\b", "the Keychain"),
    (r"^(defaults\s+(write|delete))\b.*\bcom\.apple\.(security|TCC|screensaver|loginwindow)",
     "security/privacy settings"),
    (r"^(dscl|sysadminctl)\b", "other user accounts"),
]


def check_denylist(cmd: list[str]) -> None:
    """Raise DenylistError if the command hits the §6 hard denylist."""
    joined = " ".join(cmd)
    for pattern, what in _DENY_PATTERNS:
        if re.search(pattern, joined):
            raise DenylistError(f"{REFUSAL} (denylist: {what})")
    # rm/rmdir/shred on anything outside the workspace — including the
    # audit log and Vato's own code/config (§6: disabling the audit log and
    # modifying the permission layer are denylisted, not confirmable).
    if cmd and cmd[0] in ("rm", "rmdir", "shred", "srm"):
        for arg in cmd[1:]:
            if arg.startswith("-"):
                continue
            target = (WORKSPACE / arg).resolve() if not arg.startswith(
                ("/", "~")) else Path(arg).expanduser().resolve()
            if not target.is_relative_to(WORKSPACE.resolve()):
                raise DenylistError(
                    f"{REFUSAL} (denylist: deleting outside the workspace)")
    # Any command that names the audit log, the repo, or the secrets file.
    sensitive = (str(REPO_ROOT), ".env", "audit.log")
    if cmd and cmd[0] not in ("echo", "cat", "ls"):
        for arg in cmd[1:]:
            if any(s in arg for s in sensitive):
                raise DenylistError(
                    f"{REFUSAL} (denylist: Vato's own code, audit trail, or "
                    "credentials)")


@dataclass
class ShellResult:
    returncode: int
    stdout: str
    stderr: str


class SystemControl(Protocol):
    def run_applescript(self, script: str) -> str: ...
    def run_shell(self, cmd: list[str], cwd: Path | None = None) -> ShellResult: ...
    def open_app(self, name: str) -> None: ...
    def open_url(self, url: str) -> None: ...
    def set_output_volume(self, pct: int) -> None: ...
    def file_read(self, path: str) -> str: ...
    def file_write(self, path: str, content: str) -> None: ...
    def file_list(self, path: str = ".") -> list[str]: ...
    def notify(self, text: str) -> None: ...


def _jailed(path: str) -> Path:
    """Resolve a path and refuse anything outside the workspace."""
    WORKSPACE.mkdir(exist_ok=True)
    resolved = (WORKSPACE / path).resolve()
    if not resolved.is_relative_to(WORKSPACE.resolve()):
        raise PermissionError(f"Path escapes the Vato workspace: {path}")
    return resolved


class MacSystemControl:
    """v1 implementation: osascript + subprocess."""

    def run_applescript(self, script: str) -> str:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"AppleScript failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def run_shell(self, cmd: list[str], cwd: Path | None = None) -> ShellResult:
        check_denylist(cmd)  # §6: enforced here, beneath every caller
        WORKSPACE.mkdir(exist_ok=True)
        result = subprocess.run(
            cmd, cwd=cwd or WORKSPACE, capture_output=True, text=True, timeout=120
        )
        return ShellResult(result.returncode, result.stdout, result.stderr)

    def open_app(self, name: str) -> None:
        subprocess.run(["open", "-a", name], check=True, timeout=15)

    def open_url(self, url: str) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("Only http(s) URLs may be opened")
        subprocess.run(["open", url], check=True, timeout=15)

    def set_output_volume(self, pct: int) -> None:
        pct = max(0, min(100, int(pct)))
        self.run_applescript(f"set volume output volume {pct}")

    def file_read(self, path: str) -> str:
        return _jailed(path).read_text()

    def file_write(self, path: str, content: str) -> None:
        target = _jailed(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def file_list(self, path: str = ".") -> list[str]:
        return sorted(p.name for p in _jailed(path).iterdir())

    def notify(self, text: str) -> None:
        safe = text.replace("\\", "\\\\").replace('"', '\\"')
        self.run_applescript(f'display notification "{safe}" with title "Vato"')


# ── Tool layer (spec §11: files_workspace T2, run_shell T2) ──────────────────

RUN_SHELL_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": ("The shell command to run, e.g. 'python3 "
                            "script.py'. Runs inside ~/VatoWorkspace; no "
                            "pipes/redirects (it is not a shell)."),
        },
    },
    "required": ["command"],
}

FILES_WORKSPACE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["read", "write", "list"]},
        "path": {
            "type": "string",
            "description": "Path relative to the workspace. Omit to list its root.",
        },
        "content": {"type": "string", "description": "File body, for 'write'."},
    },
    "required": ["action"],
}


class WorkspaceTools:
    """String-in/string-out wrappers the ToolRouter can register directly."""

    def __init__(self, system: MacSystemControl):
        self._system = system

    def tool_run_shell(self, command: str) -> str:
        result = self._system.run_shell(shlex.split(command))
        out = result.stdout.strip()
        err = result.stderr.strip()
        return (f"exit code {result.returncode}"
                + (f"\nstdout:\n{out}" if out else "")
                + (f"\nstderr:\n{err}" if err else ""))

    def tool_files(self, action: str, path: str | None = None,
                   content: str | None = None) -> str:
        if action == "read":
            return self._system.file_read(path or "")
        if action == "write":
            if path is None or content is None:
                return "Both 'path' and 'content' are required to write."
            self._system.file_write(path, content)
            return f"Wrote {path} in the workspace."
        entries = self._system.file_list(path or ".")
        return "\n".join(entries) if entries else "(empty)"
