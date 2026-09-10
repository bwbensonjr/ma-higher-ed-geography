"""Command line entry point: fetch, build, validate."""

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ma-geo",
        description=(
            "Prepare Massachusetts higher-education geographic data: fetch the "
            "upstream sources, build the published layers, validate the result."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    p_fetch = sub.add_parser(
        "fetch", help="download the upstream sources into the raw cache"
    )
    p_fetch.add_argument(
        "--force",
        action="store_true",
        help="re-download even when a cached copy is present",
    )

    p_build = sub.add_parser(
        "build", help="transform the raw cache into the published outputs"
    )
    p_build.add_argument(
        "--tolerance",
        type=float,
        default=None,
        help="simplification tolerance in degrees (default: the tuned value)",
    )

    sub.add_parser("validate", help="check the published outputs against the spec")

    args = parser.parse_args(argv)

    if args.command == "fetch":
        from ma_geo.fetch import run_fetch

        return run_fetch(force=args.force)
    if args.command == "build":
        from ma_geo.build import run_build

        return run_build(tolerance=args.tolerance)
    if args.command == "validate":
        from ma_geo.validate import run_validate

        return run_validate()

    parser.error(f"unknown command {args.command!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
