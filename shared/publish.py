"""Artifact handoff: analyses/chapter-N/out/ -> the website repo.

Per plan §3.3, this is the **only** sanctioned copy path between the two
repos. No submodules, no build-time coupling.

The target path is read from (in priority order):
  1. `--website-repo /path/to/site` CLI flag
  2. `WEBSITE_REPO_PATH` environment variable
There is no hardcoded default — set one of the two before running.

Usage::

    python -m shared.publish --chapter 0
    python -m shared.publish --chapter 1 --dry-run
    python -m shared.publish --chapter 1 --website-repo /path/to/other/site
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _chapter_dir(chapter: int) -> Path:
    return REPO_ROOT / "analyses" / f"chapter-{chapter:02d}" / "out"


def _target_dir(website_repo: Path, chapter: int) -> Path:
    return website_repo / "public" / "measuring-new-york" / f"chapter-{chapter:02d}"


def publish(chapter: int, website_repo: Path, dry_run: bool = False) -> list[Path]:
    src = _chapter_dir(chapter)
    if not src.exists():
        raise FileNotFoundError(f"no artifacts directory: {src}")

    dest = _target_dir(website_repo, chapter)
    if not dest.parent.exists():
        raise FileNotFoundError(
            f"target parent missing: {dest.parent}. is the website repo cloned at "
            f"{website_repo}?"
        )

    artifacts = sorted(p for p in src.iterdir() if p.is_file())
    if not artifacts:
        print(f"[publish] no files in {src} — nothing to copy", file=sys.stderr)
        return []

    dest.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for p in artifacts:
        target = dest / p.name
        action = "would copy" if dry_run else "copied"
        print(f"[publish] {action}: {p.name}  ->  {target}")
        if not dry_run:
            shutil.copy2(p, target)
        copied.append(target)
    return copied


def _resolve_website_repo(cli_arg: Path | None) -> Path:
    """Pick the website repo path from --website-repo flag or env var."""
    if cli_arg is not None:
        return cli_arg
    env = os.environ.get("WEBSITE_REPO_PATH")
    if env:
        return Path(env)
    raise FileNotFoundError(
        "no website repo path provided. set WEBSITE_REPO_PATH in your "
        "environment, or pass --website-repo /path/to/site."
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter", type=int, required=True, help="0..10")
    ap.add_argument(
        "--website-repo",
        type=Path,
        default=None,
        help="path to the website repo root. overrides $WEBSITE_REPO_PATH.",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    try:
        website_repo = _resolve_website_repo(args.website_repo)
        publish(args.chapter, website_repo.resolve(), dry_run=args.dry_run)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
