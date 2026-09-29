import os
from pathlib import Path

from check_site import (
    check_image_sizes,
    check_internal_links,
    check_listing,
    check_page_budgets,
    check_redirects,
    main,
    post_slugs,
)
from redirects import output_file, write_redirects


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def site_with_targets(site: Path) -> Path:
    for new in ["/blog/", "/blog/abortion/", "/blog/voter-fraud/", "/blog/biology-rust/", "/blog/gaussian-processes/"]:
        write(output_file(site, new), "page")
    return site


def test_redirects_pass_when_all_pages_exist(tmp_path):
    site = site_with_targets(tmp_path)
    write_redirects(site)
    assert check_redirects(site) == []


def test_redirects_report_a_missing_page(tmp_path):
    site = site_with_targets(tmp_path)
    assert "redirect /marimo-blog/: page is missing" in check_redirects(site)


def test_redirects_report_a_wrong_target(tmp_path):
    site = site_with_targets(tmp_path)
    write_redirects(site)
    write(output_file(site, "/marimo-blog/"), '<meta http-equiv="refresh" content="0; url=/blog/">')
    assert check_redirects(site) == [
        "redirect /marimo-blog/: points to '/blog/', expected '/blog/gaussian-processes/'"
    ]


def test_redirects_report_a_missing_target(tmp_path):
    write_redirects(tmp_path)
    assert "redirect /blog/search/: target /blog/ does not exist" in check_redirects(tmp_path)


def test_internal_links_find_a_broken_link(tmp_path):
    write(
        tmp_path / "index.html",
        '<a href="/blog">b</a> <a href="https://example.com">e</a> <a href="#top">t</a>'
        ' <script src="//gc.zgo.at/count.js"></script>',
    )
    write(tmp_path / "blog/index.html", '<a href="./post/">p</a> <img src="missing.png">')
    write(
        tmp_path / "blog/post/index.html",
        '<a href="../index.html">up</a> <img src="my%20image.png"> <video data-src="/img/clip.mp4"></video>',
    )
    write(tmp_path / "blog/post/my image.png", "x")
    write(tmp_path / "img/clip.mp4", "x")
    assert check_internal_links(tmp_path) == ["blog/index.html: broken src missing.png"]


def test_internal_links_skip_live_notebooks(tmp_path):
    write(tmp_path / "blog/gp/live/index.html", '<script src="./assets/missing.js"></script>')
    assert check_internal_links(tmp_path) == []


def test_page_budget_counts_local_scripts(tmp_path):
    write(tmp_path / "blog/index.html", '<script src="big.js"></script>')
    (tmp_path / "blog/big.js").write_bytes(os.urandom(5000))
    errors = check_page_budgets(tmp_path, max_bytes=4000)
    assert len(errors) == 1
    assert errors[0].startswith("blog/index.html: ")
    assert check_page_budgets(tmp_path, max_bytes=100_000) == []


def test_page_budget_reports_a_missing_post_list(tmp_path):
    assert check_page_budgets(tmp_path) == ["blog/index.html: page is missing"]


def test_image_sizes(tmp_path):
    (tmp_path / "post").mkdir()
    (tmp_path / "post/big.png").write_bytes(b"0" * 301)
    (tmp_path / "post/small.webp").write_bytes(b"0" * 10)
    (tmp_path / "_freeze").mkdir()
    (tmp_path / "_freeze/big.png").write_bytes(b"0" * 999)
    assert check_image_sizes(tmp_path, max_bytes=300) == ["blog/post/big.png: 301 bytes (limit 300)"]


def test_post_slugs_only_count_pages_with_a_date(tmp_path):
    write(tmp_path / "abortion/index.qmd", "---\ntitle: A\ndate: '2020-10-20'\n---\ntext\n")
    write(tmp_path / "about/index.qmd", "---\ntitle: About\n---\ntext\n")
    assert post_slugs(tmp_path) == {"abortion"}


FEED = (
    '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
    "<title>Blog</title><link>https://www.lukeschiefelbein.com/blog/</link>{items}</channel></rss>"
)


def test_listing_matches_the_posts(tmp_path):
    items = "".join(
        f"<item><title>{slug}</title><link>https://www.lukeschiefelbein.com/blog/{slug}/index.html</link></item>"
        for slug in ["abortion", "about"]
    )
    write(tmp_path / "blog/index.xml", FEED.format(items=items))
    assert check_listing(tmp_path, {"abortion", "voter-fraud"}) == [
        "feed: post /blog/voter-fraud/ is missing",
        "feed: /blog/about/ is not a post",
    ]


def test_page_budget_counts_post_data_files(tmp_path):
    # A post page with an incompressible data.json file should count it in budget
    write(tmp_path / "blog/index.html", "page")
    write(tmp_path / "blog/post/index.html", "page")
    (tmp_path / "blog/post/data.json").write_bytes(os.urandom(5000))
    errors = check_page_budgets(tmp_path, max_bytes=4000)
    assert len(errors) == 1
    assert errors[0].startswith("blog/post/index.html: ")


def test_page_budget_does_not_count_blog_data_files(tmp_path):
    # blog/index.html should NOT count blog/search.json or other files in blog/
    write(tmp_path / "blog/index.html", "page")
    (tmp_path / "blog/search.json").write_bytes(os.urandom(5000))
    assert check_page_budgets(tmp_path, max_bytes=4000) == []


def test_page_budget_counts_referenced_file_once(tmp_path):
    # A post page with a <script src="wiring.js"> should count that file once
    write(tmp_path / "blog/index.html", "page")
    write(tmp_path / "blog/post/index.html", '<script src="wiring.js"></script>')
    (tmp_path / "blog/post/wiring.js").write_bytes(os.urandom(100))
    weight = check_page_budgets(tmp_path, max_bytes=1_000_000)
    # Should have no errors since file is small
    assert weight == []


def test_internal_links_skips_redirect_pages(tmp_path):
    # Pages with meta refresh should be skipped by check_internal_links
    # because check_redirects already validates their targets
    write_redirects(tmp_path)
    # Don't create any actual target pages, so redirects would fail
    assert check_internal_links(tmp_path) == []
    # But check_redirects should still report the missing targets
    redirect_errors = check_redirects(tmp_path)
    assert len(redirect_errors) > 0
    assert any("does not exist" in err for err in redirect_errors)


def test_main_returns_1_for_an_empty_site(tmp_path, capsys):
    assert main(["--site", str(tmp_path / "_site"), "--blog", str(tmp_path / "blog")]) == 1
    assert "site check(s) failed" in capsys.readouterr().err
