from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Run the subprocess against the repo's source tree, so the test exercises the
# current code rather than whatever copy happens to be installed.
_SRC = str(Path(__file__).resolve().parent.parent / "src")


def _run(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "cookix", *args],
        capture_output=True, text=True, check=True, env=env,
    )


def test_python_m_cookix_runs():
    """`python -m cookix --version` must work (no console-script / PATH needed)."""
    assert "cookix" in _run("--version").stdout.lower()


def test_python_m_cookix_info():
    assert "CookiX" in _run("info").stdout
