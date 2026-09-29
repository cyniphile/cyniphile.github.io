"""Build the full site into _site/: the Quarto blog, marimo live notebooks, static files and redirects."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import check_site
from redirects import write_redirects

ROOT = Path(__file__).resolve().parents[1]


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
