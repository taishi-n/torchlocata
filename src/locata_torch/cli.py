"""Explicit LOCATA preparation and path commands."""

import argparse
import sys
from collections.abc import Sequence

from ._download import download_locata
from ._storage import resolve_root
from ._tables import LocataError


def main(argv: Sequence[str] | None = None) -> int:
    """Run the installed CLI and return a process exit status."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    path = commands.add_parser("path", help="print the resolved unpacked root")
    path.add_argument("--root", help="an explicit existing unpacked root")
    path.add_argument("--split", choices=("dev", "eval"), action="append")
    download = commands.add_parser(
        "download", help="prepare the official LOCATA release"
    )
    download.add_argument("--split", choices=("dev", "eval"), action="append")
    download.add_argument(
        "--data-dir", help="managed storage, separate from an unpacked root"
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "download":
            print(download_locata(split=args.split or ["dev"], data_dir=args.data_dir))
        else:
            print(resolve_root(args.root, args.split or ["dev"]))
    except (LocataError, OSError, ValueError) as exc:
        print(f"locata-torch: {exc}", file=sys.stderr)
        return 1
    return 0
