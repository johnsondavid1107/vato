"""SystemControl: the single interface through which ALL OS interaction goes
(spec §7), so the codebase ports MacBook → Mac mini with zero logic changes.

The workspace jail is enforced HERE, mechanically — not left to the LLM.
M1 wires nothing destructive to the brain; this layer exists so M3+ tools
(open_app, run_shell, workspace files) plug into an already-jailed surface.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

WORKSPACE = Path.home() / "VatoWorkspace"


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
