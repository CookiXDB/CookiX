"""Enable ``python -m cookix`` as an alias for the ``cookix`` CLI.

Handy when the console-script shim isn't on PATH (a common Windows situation):
``python -m cookix info`` works without any PATH setup.
"""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
