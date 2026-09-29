import subprocess
from pathlib import Path

import pytest

import build


def fake_repo(root: Path) -> Path:
    (root / "blog/gaussian-processes").mkdir(parents=True)
    (root / "blog/gaussian-processes/live.py").write_text("", encoding="utf-8")
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


def test_live_notebooks_map_each_live_py_to_a_live_folder(tmp_path):
    root = fake_repo(tmp_path)
    assert build.live_notebooks(root / "blog", root / "_site") == [
        (root / "blog/gaussian-processes/live.py", root / "_site/blog/gaussian-processes/live/index.html")
    ]


def test_copy_feed_copies_the_quarto_feed(tmp_path):
    (tmp_path / "blog").mkdir()
    (tmp_path / "blog/index.xml").write_text("<rss/>", encoding="utf-8")
    build.copy_feed(tmp_path)
    assert (tmp_path / "blog/feed.xml").read_text(encoding="utf-8") == "<rss/>"


def test_copy_feed_fails_without_a_feed(tmp_path):
    with pytest.raises(FileNotFoundError):
        build.copy_feed(tmp_path)


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
