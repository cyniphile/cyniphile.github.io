"""Convert a marimo notebook post into a static Quarto post.

Usage:
    uv run scripts/marimo_to_blog.py blog/<slug>            write blog/<slug>/index.qmd and widgets/
    uv run scripts/marimo_to_blog.py blog/<slug> --check    exit 1 if index.qmd is out of date

The post folder has notebook.py (the marimo notebook) and post.yml (title, description, date,
categories, image). See docs/superpowers/specs/2026-10-01-marimo-to-blog-design.md.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
import time
from pathlib import Path

import plotly
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from marimo_blog import model as M  # noqa: E402
from marimo_blog import verify as V  # noqa: E402
from marimo_blog.emit import emit, recorded_source  # noqa: E402
from marimo_blog.runner import Session  # noqa: E402

CONVERTER_DIR = Path(__file__).resolve().parent / "marimo_blog"


def source_hash(post_dir: Path) -> str:
    """Changes when the notebook, post.yml or the converter changes."""
    digest = hashlib.sha256()
    files = [post_dir / "notebook.py", post_dir / "post.yml", Path(__file__).resolve(),
             *sorted(CONVERTER_DIR.glob("*.py"))]
    for path in files:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def up_to_date(post_dir: Path) -> bool:
    return recorded_source(post_dir / "index.qmd") == source_hash(post_dir)


def convert(post_dir: Path, verify: bool = True) -> M.Page:
    """Write the post. With verify, compare the page load with a fresh run of the notebook and
    replay random reader events on the result and on the notebook; each difference is a warning
    (scripts/marimo_blog/verify.py)."""
    post_dir = Path(post_dir)
    front = yaml.safe_load((post_dir / "post.yml").read_text())
    with Session(post_dir / "notebook.py") as session:
        page = M.build(session)
    if verify:
        page.warnings += [f"differs from the notebook: {problem}"
                          for problem in V.verify(post_dir / "notebook.py", page)]
    page.warnings = list(dict.fromkeys(page.warnings))
    sizes = emit(page, post_dir, front, source_hash(post_dir), plotly.offline.get_plotlyjs_version())
    for warning in page.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for name, size in sizes.items():
        data = (post_dir / name).read_bytes()
        print(f"{name}: {size / 1e3:.0f} kB ({len(gzip.compress(data)) / 1e3:.0f} kB gzip)")
    return page


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("post", type=Path, help="the post folder (with notebook.py and post.yml)")
    parser.add_argument("--check", action="store_true", help="exit 1 if index.qmd is out of date")
    parser.add_argument("--no-verify", action="store_true",
                        help="do not compare the result with the notebook (faster)")
    args = parser.parse_args(argv)
    if args.check:
        ok = up_to_date(args.post)
        print(f"{args.post}: {'up to date' if ok else 'out of date (run scripts/marimo_to_blog.py)'}")
        return 0 if ok else 1
    start = time.time()
    page = convert(args.post, verify=not args.no_verify)
    print(f"{args.post}: {len(page.cells)} cells, {len(page.controls)} controls, "
          f"{len(page.groups)} groups, {time.time() - start:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
