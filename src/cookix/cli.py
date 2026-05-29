"""Command-line interface for CookiX.

    cookix info                 # environment + available layers
    cookix demo umbrella        # run a built-in demo scenario
    cookix demo pipe
    cookix serve                # launch the HTTP server + reasoning-path UI
    cookix eval                 # run the reproducible benchmark suite
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


def _cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve

    where = f"http://{args.host}:{args.port}"
    print(f"CookiX server + reasoning-path explorer: {where}")
    if args.demo:
        print(f"  loaded '{args.demo}' demo (use --demo to change, or build your own db)")
    print("  press Ctrl+C to stop")
    serve(demo=args.demo, host=args.host, port=args.port)
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    if args.extraction:
        from .eval import run_extraction_study, to_markdown_extraction

        extractors: dict[str, object] | None = None
        if args.llm:
            from .extraction.extractor import LLMExtractor, RuleBasedExtractor

            extractors = {"rule-based": RuleBasedExtractor(), "llm": LLMExtractor()}
        print(to_markdown_extraction(run_extraction_study(extractors)))
        return 0

    from .eval import run_benchmark, to_json, to_markdown

    report = run_benchmark(seed=args.seed, n_worlds=args.worlds, k=args.k)
    print(to_json(report) if args.json else to_markdown(report))
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

    srv = sub.add_parser("serve", help="launch the HTTP server + reasoning-path UI")
    srv.add_argument("--demo", choices=["umbrella", "pipe"], default="umbrella",
                     help="demo database to load on start (default: umbrella)")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.set_defaults(func=_cmd_serve)

    ev = sub.add_parser("eval", help="run the reproducible benchmark suite")
    ev.add_argument("--seed", type=int, default=0, help="RNG seed (default: 0)")
    ev.add_argument("--worlds", type=int, default=40,
                    help="number of synthetic worlds, <=80 (default: 40)")
    ev.add_argument("--k", type=int, default=5, help="retrieval cutoff k (default: 5)")
    ev.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    ev.add_argument("--extraction", action="store_true",
                    help="run the extraction-quality study instead of retrieval")
    ev.add_argument("--llm", action="store_true",
                    help="with --extraction, also score the LLM extractor (needs an API key)")
    ev.set_defaults(func=_cmd_eval)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
