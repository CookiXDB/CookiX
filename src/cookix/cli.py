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
    anchors = {
        "umbrella": ("umbrella", "wet_coat"),
        "pipe": ("pipe_120mm", "steel_pipe"),
        "deps": ("checkout_api", "CVE_2024_5001"),
    }
    anchor, target = anchors[args.scenario]
    print(f"Query: reasoning path from '{anchor}' to '{target}'\n")
    for result in db.query(anchor=anchor, target=target, mode="reasoning"):
        print("  " + result.explain())
    return 0


def _cmd_serve(args: argparse.Namespace) -> int:
    from .server import ServerConfig, serve

    cfg = ServerConfig.from_env()
    if args.api_key:
        cfg.api_key = args.api_key
    if args.rate_limit:
        cfg.rate_limit_rpm = args.rate_limit
    if args.read_only:
        cfg.read_only = True
    if args.insecure:
        cfg.allow_insecure = True

    where = f"http://{args.host}:{args.port}"
    print(f"CookiX server + reasoning-path explorer: {where}")
    if args.demo:
        print(f"  loaded '{args.demo}' demo (use --demo to change, or build your own db)")
    guards = []
    if cfg.auth_enabled:
        guards.append("auth")
    if cfg.rate_limit_rpm:
        guards.append(f"rate-limit={cfg.rate_limit_rpm}/min")
    if cfg.read_only:
        guards.append("read-only")
    print(f"  protections: {', '.join(guards) if guards else 'none (open server)'}")
    print("  press Ctrl+C to stop")
    serve(demo=args.demo, host=args.host, port=args.port, config=cfg)
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    if args.dataset:
        from .eval import load_2wiki, run_dataset_eval, to_markdown_dataset

        if not args.path:
            print("error: --dataset requires --path to the dataset JSON "
                  "(e.g. 2WikiMultiHopQA dev.json). See ROADMAP.md Phase 6.")
            return 2
        ds = load_2wiki(args.path, limit=args.limit)
        report = run_dataset_eval(ds, k=args.k, oracle_anchor=not args.no_oracle,
                                  linker=args.linker)
        print(to_markdown_dataset(report))
        return 0

    if args.perf:
        from .eval import run_perf_benchmark, to_markdown_perf

        print(to_markdown_perf(
            run_perf_benchmark(seed=args.seed, n_worlds=args.worlds, k=args.k)
        ))
        return 0

    if args.scale:
        from .eval import run_scale_benchmark, to_markdown_scale

        print(to_markdown_scale(run_scale_benchmark(seed=args.seed)))
        return 0

    if args.sheaf:
        from .eval import run_sheaf_ablation, to_markdown_sheaf

        print(to_markdown_sheaf(run_sheaf_ablation(seed=args.seed)))
        return 0

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


def _cmd_loadtest(args: argparse.Namespace) -> int:
    from .eval import run_load_test, to_markdown_load

    print(f"Load test: {args.workers} clients × {args.duration}s on "
          f"{args.objects} objects (starting server on :{args.port})…")
    report = run_load_test(
        objects=args.objects, workers=args.workers,
        duration_s=args.duration, port=args.port,
    )
    print(to_markdown_load(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cookix", description=__doc__)
    parser.add_argument("--version", action="version", version=f"cookix {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="show environment and available layers").set_defaults(
        func=_cmd_info
    )

    demo = sub.add_parser("demo", help="run a built-in demo scenario")
    demo.add_argument("scenario", choices=["umbrella", "pipe", "deps"])
    demo.set_defaults(func=_cmd_demo)

    srv = sub.add_parser("serve", help="launch the HTTP server + reasoning-path UI")
    srv.add_argument("--demo", choices=["umbrella", "pipe", "deps"], default="umbrella",
                     help="demo database to load on start (default: umbrella)")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--api-key", help="require this API key on data endpoints "
                     "(or set COOKIX_API_KEY)")
    srv.add_argument("--rate-limit", type=int, default=0,
                     help="max requests per minute per client (0 = unlimited)")
    srv.add_argument("--read-only", action="store_true",
                     help="reject all mutations (serve a frozen database)")
    srv.add_argument("--insecure", action="store_true",
                     help="allow binding a public interface without auth (not recommended)")
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
    ev.add_argument("--sheaf", action="store_true",
                    help="run the learned-sheaf residual ablation instead of retrieval")
    ev.add_argument("--perf", action="store_true",
                    help="time the query engine per ablation mode instead of scoring")
    ev.add_argument("--scale", action="store_true",
                    help="benchmark build/latency/memory as the graph grows")
    ev.add_argument("--dataset", choices=["2wiki"],
                    help="evaluate on an external multi-hop QA dataset vs BM25")
    ev.add_argument("--path", help="path to the dataset JSON (with --dataset)")
    ev.add_argument("--limit", type=int, default=None,
                    help="cap the number of dataset examples (with --dataset)")
    ev.add_argument("--no-oracle", action="store_true",
                    help="with --dataset: link the anchor (no oracle entity-linking)")
    ev.add_argument("--linker", choices=["surface", "bm25"], default="surface",
                    help="with --no-oracle: entity-linking strategy (default: surface)")
    ev.set_defaults(func=_cmd_eval)

    lt = sub.add_parser("loadtest", help="load/soak-test the HTTP server with concurrent clients")
    lt.add_argument("--objects", type=int, default=5000, help="graph size (default: 5000)")
    lt.add_argument("--workers", type=int, default=8, help="concurrent clients (default: 8)")
    lt.add_argument("--duration", type=float, default=10.0, help="seconds to run (default: 10)")
    lt.add_argument("--port", type=int, default=8917, help="server port (default: 8917)")
    lt.set_defaults(func=_cmd_loadtest)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
