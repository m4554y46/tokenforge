"""SPC — Command Line Interface."""

import argparse
import sys
import json
import logging

from .pipeline import SPC
from .profiles import get_profile, PROFILES


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="spc",
        description="Semantic Prompt Compiler — compress text while preserving meaning",
    )
    parser.add_argument("input", nargs="?", help="Input file path (reads from stdin if omitted)")
    parser.add_argument("-o", "--output", help="Output file path (stdout if omitted)")
    parser.add_argument("-p", "--profile", choices=list(PROFILES.keys()), default="safe",
                        help="Execution profile (default: safe)")
    parser.add_argument("--cost", type=float, default=0.0,
                        help="Cost per 1K tokens in $ (default: 0)")
    parser.add_argument("--json", action="store_true",
                        help="Output full JSON result with metrics")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--version", action="version", version="spc 1.0.0")

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    # Read input
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    if not text.strip():
        print("Error: empty input", file=sys.stderr)
        return 1

    # Run SPC
    profile = get_profile(args.profile)
    spc = SPC(profile=profile, cost_per_1k=args.cost)
    result = spc.compile(text)

    # Output
    if args.json:
        output = json.dumps({
            "profile": result.profile,
            "input_tokens": result.metrics.input_tokens if result.metrics else 0,
            "output_tokens": result.metrics.output_tokens if result.metrics else 0,
            "reduction_ratio": result.metrics.reduction_ratio if result.metrics else 0.0,
            "elapsed_ms": result.metrics.elapsed_ms if result.metrics else 0.0,
            "compressed": result.compressed,
            "fallback": result.fallback,
            "errors": result.validation.errors if result.validation else [],
            "warnings": result.validation.warnings if result.validation else [],
        }, indent=2, ensure_ascii=False)
    else:
        output = result.compressed

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output, end="")

    if result.fallback:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
