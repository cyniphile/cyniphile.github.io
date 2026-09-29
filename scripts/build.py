"""Build the full site into _site/: the Quarto blog, marimo live notebooks, static files and redirects."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import check_site
from redirects import write_redirects

ROOT = Path(__file__).resolve().parents[1]
KATEX_VERSION = "0.18.9"


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def live_notebooks(blog_dir: Path, site_dir: Path) -> list[tuple[Path, Path]]:
    """Each blog/<slug>/live.py becomes _site/blog/<slug>/live/index.html."""
    return [
        (src, site_dir / "blog" / src.parent.name / "live" / "index.html")
        for src in sorted(blog_dir.glob("*/live.py"))
    ]


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def pin_katex(site_dir: Path) -> int:
    """Quarto loads KaTeX from katex@latest. Pin it to KATEX_VERSION in every page under blog/.

    Return the number of pages that changed. Only the version text changes: the encoding
    is UTF-8 and line endings stay as they are.
    """
    changed = 0
    for page in sorted((site_dir / "blog").rglob("*.html")):
        text = page.read_text(encoding="utf-8", newline="")
        pinned = text.replace("katex@latest", f"katex@{KATEX_VERSION}")
        if pinned != text:
            page.write_text(pinned, encoding="utf-8", newline="")
            changed += 1
    return changed


def copy_feed(site_dir: Path) -> None:
    """Keep the old feed URL /blog/feed.xml for current RSS subscribers."""
    feed = site_dir / "blog" / "index.xml"
    if not feed.is_file():
        raise FileNotFoundError(f"Quarto did not write the feed {feed}")
    shutil.copyfile(feed, site_dir / "blog" / "feed.xml")


def build(root: Path = ROOT) -> int:
    site = root / "_site"
    blog = root / "blog"
    if site.exists():
        shutil.rmtree(site)
    run(["quarto", "render", "blog"], cwd=root)
    copy_tree(blog / "_site", site / "blog")
    pin_katex(site)
    for src, out in live_notebooks(blog, site):
        run(
            ["marimo", "export", "html-wasm", str(src), "--mode", "run", "--no-show-code",
             "--execute", "-o", str(out), "-f"],
            cwd=root,
        )
    copy_tree(root / "site-root", site)
    write_redirects(site)
    copy_feed(site)
    return check_site.main(["--site", str(site), "--blog", str(blog)])


if __name__ == "__main__":
    sys.exit(build())
