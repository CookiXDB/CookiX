"""Command-line interface for CookiX.

    cookix info                 # environment + available layers
    cookix demo umbrella        # run a built-in demo scenario
    cookix demo pipe
"""

from __future__ import annotations

import argparse

from . import __version__, sheaf, topology


def _cmd_info(_: argparse.Namespace) -> int:
    topo = "available" if topology.AVAILABLE else 'not installed (pip install "cookix[topology]")'
    print(f"CookiX {__version__} - topological-relational memory database")
    print(f"  topology layer (persistent homology): {topo}")
    print(f"  sheaf layer (composition):            {'available' if sheaf.AVAILABLE else 'unavailable'}")
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    from .demos import DEMOS

    db = DEMOS[args.scenario]()
    print(f"Loaded '{args.scenario}' demo: {len(db)} Knowledge Objects\n")
    if args.scenario == "umbrella":
        anchor, target = "umbrella", "wet_coat"
    else:
        anchor, target = "pipe_120mm", "steel_pipe"
    print(f"Query: reasoning path from '{anchor}' to '{target}'\n")
    for result in db.query(anchor=anchor, target=target, mode="reasoning"):
        print("  " + result.explain())
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cookix", description=__doc__)
    parser.add_argument("--version", action="version", version=f"cookix {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="show environment and available layers").set_defaults(
        func=_cmd_info
    )

    demo = sub.add_parser("demo", help="run a built-in demo scenario")
    demo.add_argument("scenario", choices=["umbrella", "pipe"])
    demo.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
