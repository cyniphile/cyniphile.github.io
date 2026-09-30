"""One-time converter: fastpages (Jekyll) posts to Quarto posts in blog/<slug>/index.qmd."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import yaml
from PIL import Image

MAX_IMAGE_BYTES = 300_000
MAX_WIDTH = 1600

POSTS = {
    "2020-10-20-abortion.md": "abortion",
    "2020-11-12-voter-fraud.md": "voter-fraud",
    "2021-12-1-biology-rust.md": "biology-rust",
}

DEAD_CHART_NOTE = "::: {.callout-note}\nThe interactive chart for this post is no longer online.\n:::"


def split_front_matter(text: str) -> tuple[dict, str]:
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError("the post has no front matter")
    return yaml.safe_load(match.group(1)), text[match.end():]


def post_date(filename: str) -> str:
    year, month, day = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})-", filename).groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def image_name(old: str) -> str:
    """'Stright ticket ballot.jpg' -> 'stright-ticket-ballot.jpg'. Folders are dropped."""
    path = Path(old)
    stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    return stem + path.suffix.lower()


def convert_footnotes(body: str) -> str:
    body = re.sub(r"\{%\s*fn\s+(\d+)\s*%\}", r"[^\1]", body)
    return re.sub(
        r"\{\{\s*([\"'])(.*?)\1\s*\|\s*fndetail:\s*(\d+)\s*\}\}",
        lambda match: f"[^{match.group(3)}]: {match.group(2)}",
        body,
        flags=re.DOTALL,
    )


def convert_youtube(body: str) -> str:
    def video(match: re.Match) -> str:
        start = f' start="{match.group(2)}"' if match.group(2) else ""
        return f"{{{{< video https://www.youtube.com/embed/{match.group(1)}{start} >}}}}"

    return re.sub(
        r'<iframe[^>]*src="https://www\.youtube\.com/embed/([\w-]+)(?:\?start=(\d+))?"[^>]*>\s*</iframe>',
        video,
        body,
        flags=re.DOTALL,
    )


def remove_twitter_script(body: str) -> str:
    return re.sub(
        r'\s*<script async src="https://platform\.twitter\.com/widgets\.js" charset="utf-8"></script>',
        "",
        body,
    )


def replace_dead_chart(body: str) -> str:
    return re.sub(
        r'(<!--[^>]*-->\s*)?<div class="holds-the-iframe">.*?abortion-blog\.herokuapp\.com.*?</script>',
        DEAD_CHART_NOTE,
        body,
        flags=re.DOTALL,
    )


def convert_images(body: str, final_name: Callable[[str], str]) -> tuple[str, list[str]]:
    """Point {{ site.baseurl }}/images/... links at files in the post folder.

    Returns the new body and the old image paths (relative to the old images/ folder).
    """
    found: list[str] = []

    def link(match: re.Match) -> str:
        alt, old, title = match.group(1), match.group(2).strip(), match.group(3)
        found.append(old)
        title_part = f' "{title}"' if title else ""
        return f"![{alt}]({final_name(old)}{title_part})"

    new_body = re.sub(
        r'!\[([^\]]*)\]\(\{\{\s*site\.baseurl\s*\}\}/images/([^")]+?)\s*(?:"([^"]*)")?\s*\)',
        link,
        body,
    )
    return new_body, found


MARKDOWN_IMAGE = re.compile(r'!\[([^\]]*)\]\(\s*([^\s")]+)(?:\s+"([^"]*)")?\s*\)(?!\{)')


def convert_captions(body: str) -> str:
    """Show each image title as the caption, as the old site did, and keep the alt text as fig-alt.

    Quarto shows the alt text as the caption. The old site showed the title as the caption and
    never showed the alt text:
        ![ALT](SRC "TITLE")  ->  ![TITLE](SRC){fig-alt="ALT"}
        ![ALT](SRC)          ->  ![](SRC){fig-alt="ALT"}
    An image with neither stays as it is. So does an image that already has an attribute block.
    """

    def rewrite(match: re.Match) -> str:
        alt, src, title = (" ".join((text or "").split()) for text in match.groups())
        if not alt and not title:
            return match.group(0)
        caption = re.sub(r"([\\\[\]])", r"\\\1", title)
        fig_alt = alt.replace("\\", "\\\\").replace('"', '\\"')
        return f'![{caption}]({src}){{fig-alt="{fig_alt}"}}' if alt else f"![{caption}]({src})"

    return MARKDOWN_IMAGE.sub(rewrite, body)


def needs_webp(src: Path) -> bool:
    return src.suffix.lower() in {".png", ".jpg", ".jpeg"} and src.stat().st_size > MAX_IMAGE_BYTES


def final_image_name(images_dir: Path, old: str) -> str:
    name = image_name(old)
    return str(Path(name).with_suffix(".webp")) if needs_webp(images_dir / old) else name


def save_image(src: Path, dst: Path) -> None:
    """Copy a small image. Convert a large one to WebP that is at most MAX_WIDTH wide."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.suffix != ".webp":
        shutil.copyfile(src, dst)
        return
    with Image.open(src) as image:
        if image.width > MAX_WIDTH:
            image = image.resize((MAX_WIDTH, round(image.height * MAX_WIDTH / image.width)), Image.LANCZOS)
        for quality in (85, 75, 65, 55):
            image.save(dst, "WEBP", quality=quality, method=6)
            if dst.stat().st_size <= MAX_IMAGE_BYTES:
                return
    raise ValueError(f"{src} is still larger than {MAX_IMAGE_BYTES} bytes as WebP")


def convert_front_matter(meta: dict, date: str, image: str | None) -> dict:
    out = {
        "title": meta["title"],
        "description": meta.get("description", ""),
        "date": date,
        "categories": list(meta.get("categories", [])),
    }
    if meta.get("keywords"):
        out["keywords"] = [word.strip() for word in str(meta["keywords"]).split(",")]
    if image:
        out["image"] = image
    out["toc"] = bool(meta.get("toc", False))
    return out


def convert_post(src: Path, images_dir: Path, out_dir: Path) -> Path:
    meta, body = split_front_matter(src.read_text(encoding="utf-8"))

    def rename(old: str) -> str:
        return final_image_name(images_dir, old)

    body, found = convert_images(body, rename)
    body = convert_captions(body)
    body = replace_dead_chart(remove_twitter_script(convert_youtube(convert_footnotes(body))))
    if re.search(r"\{\{(?!<)|\{%", body):
        raise ValueError(f"{src.name}: unconverted Liquid tags remain")
    header = meta["image"].removeprefix("images/") if meta.get("image") else None
    front = convert_front_matter(meta, post_date(src.name), rename(header) if header else None)
    out_dir.mkdir(parents=True, exist_ok=True)
    text = "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=1000) + "---\n" + body
    (out_dir / "index.qmd").write_text(text, encoding="utf-8")
    for old in dict.fromkeys(found + ([header] if header else [])):
        save_image(images_dir / old, out_dir / rename(old))
    return out_dir / "index.qmd"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-blog", type=Path, required=True, help="the old fastpages repo")
    parser.add_argument("--out", type=Path, default=Path("blog"))
    args = parser.parse_args(argv)
    for filename, slug in POSTS.items():
        path = convert_post(args.old_blog / "_posts" / filename, args.old_blog / "images", args.out / slug)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
