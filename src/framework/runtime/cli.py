"""The paper command deliberately imports workflows only after profile selection."""

import argparse
from dataclasses import asdict
import json
import sys
from framework.config import load_study_spec, PROFILES


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="paper", description="Independent research workflow templates"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in (
        "validate",
        "plan",
        "run",
        "force",
        "submit",
        "worker",
        "finalize",
        "materialize",
    ):
        p = sub.add_parser(name)
        p.add_argument("study")
        if name in ("run", "force", "worker", "finalize"):
            p.add_argument("--progress", action="store_true")
        if name == "force":
            p.add_argument("--node", action="append", default=[])
        if name == "plan":
            p.add_argument(
                "--visualize",
                nargs="?",
                const="overview",
                choices=("overview", "detail", "full"),
            )
        if name == "submit":
            p.add_argument("--dry-run", action="store_true")
        if name == "worker":
            p.add_argument("--method", required=True)
    p = sub.add_parser("export")
    p.add_argument("study_dir")
    p.add_argument("output")
    p.add_argument("--method", action="append")
    p.add_argument("--metric", action="append")
    p.add_argument("--split")
    p = sub.add_parser("archive")
    p.add_argument("study_id")
    p = sub.add_parser("cache")
    cs = p.add_subparsers(dest="cache_command", required=True)
    for name in ("status", "gc"):
        c = cs.add_parser(name)
        c.add_argument("study_id")
        if name == "gc":
            c.add_argument("--apply", action="store_true")
            c.add_argument("--include-failures", action="store_true")
    p = sub.add_parser("template")
    ts = p.add_subparsers(dest="template_command", required=True)
    t = ts.add_parser("export")
    t.add_argument("profile", choices=PROFILES)
    t.add_argument("target")
    args = parser.parse_args(argv)
    try:
        if args.command == "template":
            from framework.templates import export_template

            print(export_template(args.profile, args.target))
            return 0
        if args.command == "export":
            from framework.runtime.reporting import export_metrics

            print(
                export_metrics(
                    args.study_dir,
                    args.output,
                    methods=args.method,
                    metrics=args.metric,
                    split=args.split,
                )
            )
            return 0
        if args.command == "archive":
            from framework.runtime.archive import archive_study

            print(archive_study(args.study_id))
            return 0
        if args.command == "cache":
            from framework.runtime.cache import inspect_cache, clean_cache
            from framework.runtime.paths import study_artifact_root

            root = study_artifact_root(args.study_id)
            value = (
                inspect_cache(root)
                if args.cache_command == "status"
                else clean_cache(
                    root,
                    apply=args.apply,
                    include_failures=args.include_failures,
                    drop_latest=True,
                )
            )
            print(json.dumps(asdict(value), default=str, indent=2))
            return 0
        spec = load_study_spec(args.study)
        if args.command == "submit":
            from framework.runtime.slurm import submit_slurm_study

            print(
                json.dumps(
                    submit_slurm_study(args.study, dry_run=args.dry_run), indent=2
                )
            )
            return 0
        if args.command == "materialize":
            from framework.runtime.hooks import run_study_hook

            run_study_hook(spec, "materialize")
            return 0
        from framework.runtime.study import prepare_study, run_study, plan_study

        if args.command == "validate":
            compiled = prepare_study(spec)
            print(f"{spec.id}: valid ({len(compiled.plan.nodes)} nodes)")
            return 0
        if args.command == "plan":
            planned = plan_study(spec)
            for node in planned:
                print(f"{node.status.value:5} {node.logical_id}")
            if args.visualize:
                from framework.runtime.plan_visualization import (
                    render_plan_visualization,
                )

                print(
                    render_plan_visualization(
                        study_id=spec.id,
                        groups={spec.profile: planned},
                        mode=args.visualize,
                    )
                )
            return 0
        if args.command == "worker":
            from framework.runtime.slurm import select_method

            spec = select_method(spec, args.method)
        force = ()
        if args.command == "force":
            force = args.node or tuple(prepare_study(spec).plan.nodes)
        callback = (
            (lambda e: print(f"{e.event.value}: {e.logical_id}", flush=True))
            if args.progress
            else None
        )
        result = run_study(
            spec,
            force=force,
            progress=callback,
            publish=args.command != "worker",
            require_cached=args.command == "finalize",
        )
        print(
            f"{result['run_id']}: {result['status']}; executed={len(result['executed'])} reused={len(result['reused'])}"
        )
        return 0
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
