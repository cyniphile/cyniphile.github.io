# www.lukeschiefelbein.com

This repo builds the full site:

- `/` is the landing page. Its static files are in `site-root/`.
- `/blog/` is the blog. It is a Quarto project in `blog/`.

## Setup (one time)

1. Install uv, Quarto 1.10.18 and Node.js 22.
2. Run `uv sync`.

## Write a post

1. Make the folder `blog/<slug>/` with an `index.qmd` file. Put `title`, `date`, `description` and `categories` in its front matter.
2. Run `uv run quarto preview blog`. The page updates each time you save.
3. Commit the post and the files in `blog/_freeze/`. Push to `master`.

## Write an interactive post (a marimo notebook)

1. Make the folder `blog/<slug>/` with the marimo notebook `notebook.py` and the file `post.yml` (`title`, `date`, `description`, `categories`, and optionally `image`). Put the notebook's packages in its PEP 723 header (see `blog/gaussian-processes/notebook.py`).
2. Edit the notebook with `uv run marimo edit blog/<slug>/notebook.py`.
3. Run `uv run scripts/marimo_to_blog.py blog/<slug>`. It writes `index.qmd` and `widgets/*.json`. Do not edit these files. Read the warnings: each warning names a widget that does not act as in the notebook, or a marimo element that the blog shows without interaction.
4. Commit `notebook.py`, `post.yml`, `index.qmd` and `widgets/`. Push to `master`.

The converter runs the notebook with marimo. It calculates the effect of each slider and button before the page loads, it records the random draws for matrix inputs (the browser calculates the samples), and it runs code editors in the browser with Pyodide. After each conversion it compares the page with the notebook. The design is in `docs/superpowers/specs/2026-10-01-marimo-to-blog-design.md`. The build also publishes each `notebook.py` as a live marimo notebook at `<post URL>/live/`, and it converts a post again when its notebook, its `post.yml` or the converter changes.

## Build and test the full site

- `uv run pytest` tests the Python scripts and the JavaScript helpers (with Node.js).
- `uv run scripts/build.py` builds `_site/` and runs the site checks.
- `python3 -m http.server -d _site` serves the site at http://localhost:8000.

## Deploy

GitHub Actions (`.github/workflows/publish.yml`) builds and deploys each push to `master`. A pull request runs the same build and checks, but it does not deploy.
