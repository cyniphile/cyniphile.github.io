import re
import subprocess
from pathlib import Path

import pytest

import build

# A page like the ones Quarto writes for math: a script and a stylesheet from the KaTeX CDN.
KATEX_PAGE = """<head>
<script src="https://cdn.jsdelivr.net/npm/katex@{version}/dist/katex.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@{version}/dist/katex.min.css">
</head>
<body>Café ≥ 1</body>
"""


@pytest.fixture(autouse=True)
def no_notebook_conversion(monkeypatch):
    """The fake repo's notebook.py is empty: converting it is not the subject of these tests."""
    monkeypatch.setattr(build.marimo_to_blog, "up_to_date", lambda post: True)


def fake_repo(root: Path) -> Path:
    (root / "blog/gaussian-processes").mkdir(parents=True)
    (root / "blog/gaussian-processes/notebook.py").write_text("", encoding="utf-8")
    (root / "blog/abortion").mkdir()
    (root / "blog/abortion/index.qmd").write_text("", encoding="utf-8")
    (root / "site-root").mkdir()
    (root / "site-root/index.html").write_text("landing", encoding="utf-8")
    return root


def fake_quarto_output(root: Path) -> None:
    out = root / "blog/_site"
    out.mkdir(parents=True)
    (out / "index.html").write_text("post list", encoding="utf-8")
    (out / "index.xml").write_text("<rss/>", encoding="utf-8")


def test_live_notebooks_map_each_notebook_to_a_live_folder(tmp_path):
    root = fake_repo(tmp_path)
    assert build.live_notebooks(root / "blog", root / "_site") == [
        (root / "blog/gaussian-processes/notebook.py", root / "_site/blog/gaussian-processes/live/index.html")
    ]


# The giscus loader that Quarto 1.10.18 writes at the end of a post (shortened)
GISCUS_LOADER = """<script>
  function loadGiscus() {
    const script = document.createElement("script");
    script.src = "https://giscus.app/client.js";
    script.dataset.mapping = "pathname";
    script.dataset.lang = "en";
    script.crossOrigin = "anonymous";
  }
  loadGiscus();
</script>
"""


def test_lazy_giscus_adds_lazy_loading_once(tmp_path):
    post = tmp_path / "blog/abortion/index.html"
    other = tmp_path / "blog/about/index.html"
    post.parent.mkdir(parents=True)
    other.parent.mkdir(parents=True)
    post.write_text(GISCUS_LOADER, encoding="utf-8")
    other.write_text("no comments", encoding="utf-8")
    assert build.lazy_giscus(tmp_path) == 1
    assert '    script.dataset.lang = "en";\n    script.dataset.loading = "lazy";\n' in post.read_text(encoding="utf-8")
    assert other.read_text(encoding="utf-8") == "no comments"
    assert build.lazy_giscus(tmp_path) == 0  # a second build changes nothing


def test_lazy_giscus_fails_when_quartos_loader_changes(tmp_path):
    post = tmp_path / "blog/abortion/index.html"
    post.parent.mkdir(parents=True)
    post.write_text(GISCUS_LOADER.replace('script.dataset.lang = "en";', ""), encoding="utf-8")
    with pytest.raises(ValueError, match="giscus loader changed"):
        build.lazy_giscus(tmp_path)


def test_copy_feed_copies_the_quarto_feed(tmp_path):
    (tmp_path / "blog").mkdir()
    (tmp_path / "blog/index.xml").write_text("<rss/>", encoding="utf-8")
    build.copy_feed(tmp_path)
    assert (tmp_path / "blog/feed.xml").read_text(encoding="utf-8") == "<rss/>"


def test_copy_feed_fails_without_a_feed(tmp_path):
    with pytest.raises(FileNotFoundError):
        build.copy_feed(tmp_path)


def test_pin_katex_pins_nested_pages_and_changes_nothing_else(tmp_path):
    blog = tmp_path / "blog"
    (blog / "gaussian-processes").mkdir(parents=True)
    (blog / "about").mkdir()
    # CRLF line endings: a rewrite through normal text mode would change them.
    math_page = blog / "gaussian-processes/index.html"
    math_page.write_bytes(KATEX_PAGE.format(version="latest").replace("\n", "\r\n").encode("utf-8"))
    plain_page = blog / "about/index.html"
    plain_bytes = "<p>Café, no math</p>\r\n".encode("utf-8")
    plain_page.write_bytes(plain_bytes)
    search = blog / "search.json"
    search.write_text('[{"text": "katex@latest"}]', encoding="utf-8")

    assert re.fullmatch(r"\d+\.\d+\.\d+", build.KATEX_VERSION)
    assert build.pin_katex(tmp_path) == 1  # one changed file, although it has two references

    pinned = KATEX_PAGE.format(version=build.KATEX_VERSION).replace("\n", "\r\n").encode("utf-8")
    assert math_page.read_bytes() == pinned
    assert plain_page.read_bytes() == plain_bytes
    assert search.read_text(encoding="utf-8") == '[{"text": "katex@latest"}]'


def test_build_runs_all_steps_in_order(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)
    (root / "_site").mkdir()
    (root / "_site/stale.html").write_text("old", encoding="utf-8")
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd[:2])
        if cmd[:2] == ["quarto", "render"]:
            fake_quarto_output(root)

    monkeypatch.setattr(build, "run", fake_run)
    monkeypatch.setattr(build.check_site, "main", lambda argv: 0)
    assert build.build(root) == 0
    assert calls == [["quarto", "render"], ["marimo", "export"]]
    site = root / "_site"
    assert not (site / "stale.html").exists()
    assert (site / "index.html").read_text(encoding="utf-8") == "landing"
    assert (site / "blog/index.html").read_text(encoding="utf-8") == "post list"
    assert (site / "blog/feed.xml").read_text(encoding="utf-8") == "<rss/>"
    assert (site / "blog/abortion/politics/2020/10/20/abortion.html").is_file()


def test_build_exports_live_notebooks_that_run_at_load_and_show_code(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)
    exports = []

    def fake_run(cmd, cwd):
        if cmd[:2] == ["quarto", "render"]:
            fake_quarto_output(root)
        if cmd[:2] == ["marimo", "export"]:
            exports.append(cmd)
            out = Path(cmd[cmd.index("-o") + 1])
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("notebook", encoding="utf-8")
            (out.parent / "CLAUDE.md").write_text("a prompt that marimo writes", encoding="utf-8")

    monkeypatch.setattr(build, "run", fake_run)
    monkeypatch.setattr(build.check_site, "main", lambda argv: 0)
    assert build.build(root) == 0
    (cmd,) = exports
    # edit mode waits for "Run all" before any cell runs; run mode runs the cells at load
    assert cmd[cmd.index("--mode") + 1] == "run" and "--show-code" in cmd and "--execute" in cmd
    live = root / "_site/blog/gaussian-processes/live"
    assert (live / "index.html").is_file() and not (live / "CLAUDE.md").exists()


def test_build_pins_the_katex_version_in_the_copied_blog(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)

    def fake_run(cmd, cwd):
        if cmd[0] == "quarto":
            fake_quarto_output(root)
            (root / "blog/_site/math").mkdir()
            (root / "blog/_site/math/index.html").write_text(
                KATEX_PAGE.format(version="latest"), encoding="utf-8"
            )

    monkeypatch.setattr(build, "run", fake_run)
    monkeypatch.setattr(build.check_site, "main", lambda argv: 0)
    assert build.build(root) == 0
    page = (root / "_site/blog/math/index.html").read_text(encoding="utf-8")
    assert "katex@latest" not in page
    assert f"katex@{build.KATEX_VERSION}" in page


def test_build_returns_1_when_a_check_fails(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)

    def fake_run(cmd, cwd):
        if cmd[0] == "quarto":
            fake_quarto_output(root)

    monkeypatch.setattr(build, "run", fake_run)
    monkeypatch.setattr(build.check_site, "main", lambda argv: 1)
    assert build.build(root) == 1


def test_build_stops_when_a_command_fails(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)

    def failing_run(cmd, cwd):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(build, "run", failing_run)
    with pytest.raises(subprocess.CalledProcessError):
        build.build(root)
    assert not (root / "_site/index.html").exists()


def test_build_stops_when_site_delete_fails(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)
    (root / "_site").mkdir()
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd[:2])

    def failing_rmtree(path, ignore_errors=False):
        if ignore_errors:
            return  # Silently return when ignore_errors=True, like the real rmtree would
        raise OSError("Permission denied")

    monkeypatch.setattr(build, "run", fake_run)
    monkeypatch.setattr(build.shutil, "rmtree", failing_rmtree)

    with pytest.raises(OSError):
        build.build(root)
    assert calls == []  # No run calls should have been made


def test_convert_notebook_posts_converts_only_out_of_date_posts(tmp_path, monkeypatch):
    for slug in ("fresh", "stale"):
        (tmp_path / slug).mkdir()
        (tmp_path / slug / "notebook.py").write_text("", encoding="utf-8")
    (tmp_path / "plain").mkdir()  # a post without a notebook
    converted = []
    monkeypatch.setattr(build.marimo_to_blog, "up_to_date", lambda post: post.name == "fresh")
    monkeypatch.setattr(build.marimo_to_blog, "convert", lambda post: converted.append(post.name))
    assert build.convert_notebook_posts(tmp_path) == [tmp_path / "stale"]
    assert converted == ["stale"]
