"""Artifact handoff: analyses/chapter-N/out/ -> personal-website/.

Per plan §3.3, this is the **only** sanctioned copy path between the two
repos. No submodules, no build-time coupling.

Usage::

    python -m shared.publish --chapter 0
    python -m shared.publish --chapter 1 --dry-run
    python -m shared.publish --chapter 1 --website-repo /path/to/other/site
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WEBSITE_REPO = REPO_ROOT.parent / "personal-website"


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chapter", type=int, required=True, help="0..10")
    ap.add_argument(
        "--website-repo",
        type=Path,
        default=DEFAULT_WEBSITE_REPO,
        help=f"default: {DEFAULT_WEBSITE_REPO}",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    try:
        publish(args.chapter, args.website_repo.resolve(), dry_run=args.dry_run)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
