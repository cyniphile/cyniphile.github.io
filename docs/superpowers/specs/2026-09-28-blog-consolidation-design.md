# Blog consolidation: design

- Date: 2026-09-28
- Status: draft, for review
- Target repo: `cyniphile.github.io` (default branch `master`)
- Repos to archive: `blog`, `marimo-blog`

## 1. Goal

Make one fast personal site at `www.lukeschiefelbein.com`. The site has a blog for long posts on science and other topics. Posts can have interactive plots. Python does all the calculations.

### 1.1 Success criteria

1. On a phone, the first text of each post shows in less than 2 s. "Phone" means Chrome emulation with Fast 4G, a 4× slower CPU and an empty cache.
2. On the same phone, the widgets of the GP post work in less than 3 s.
3. A new post is one folder with an `index.qmd` file. A push to `master` publishes it.
4. All old URLs go to the new pages.
5. One repo contains the full site.

## 2. Current state (2026-09-28)

| Repo | Serves | Status |
|---|---|---|
| `cyniphile.github.io` | `/`: landing page (wobble image, links to blog and about) | static files; GitHub Pages deploys the `master` branch |
| `blog` | `/blog/`: fastpages (Jekyll) with 3 posts, About, Subscribe | last deploy 2022-11-01; fastpages was archived on 2022-11-13 and recommends Quarto |
| `marimo-blog` | `/marimo-blog/`: marimo WASM export of the GP post | works, but it is slow on phones |

Measurements of the GP post, with an empty cache:

| Test | First text | All plots | Widgets work |
|---|---|---|---|
| Laptop, live site | 5.5–7 s | 10 s | ~10 s |
| Phone, live site (marimo 0.23.8) | 55 s | 61 s | ~61 s |
| Phone, marimo 0.25.0 with `--execute` (local test) | 15 s | 31 s | ~74 s |
| Phone, old static Jekyll post | 0.5 s | – | – |

Cause: before a widget works, each reader downloads approximately 45 MB. The largest parts are scipy (12.8 MB), plotly (9.2 MB) and pandas (5.4 MB). The page is also a large JavaScript app, so the text shows late.

Other findings:
- The interactive chart in the abortion post is dead. Its Heroku app returns 404, and no copy of its code or data exists.
- The analytics ID `UA-52542530-2` is Universal Analytics. Google stopped this service in 2023.
- The old blog uses utterances comments in the `blog` repo. Only issue #17 (election fraud post) has comments (3).

## 3. Decisions

| # | Decision | Reason |
|---|---|---|
| D1 | Quarto builds the blog. marimo is used only for live notebooks. | Static HTML is fast. Quarto has blog functions and tools for long posts. |
| D2 | Python runs at build time. The browser gets precomputed data. | Readers do not download Python. |
| D3 | Live Python is opt-in. A post links to a marimo WASM notebook. | Only readers who open the notebook download Python. |
| D4 | No inline marimo islands (quarto-marimo) for now. | Islands start Pyodide when the page loads (mdx-marimo, `islands-bridge/src/browser/assets.ts`: `const ready = activate()`). There is no option to wait for a click. |
| D5 | JavaScript only connects the widgets. It does no vector or matrix math. Short scalar formulas are permitted. | The numpy-like math stays in Python. |
| D6 | The landing page at `/` keeps its look. The blog is at `/blog/`. | Owner's choice. |
| D7 | All 4 old posts move to the new site. Old URLs redirect. | Owner's choice. |
| D8 | Comments: giscus. Analytics: GoatCounter. Subscribe: the same Mailchimp form. | giscus replaces utterances. GoatCounter is free and uses no cookies. |
| D9 | The 404 page shows one of two versions at random. | Owner's choice. |
| D10 | The blog keeps the old fastpages look, in light mode only (section 8.6). | Owner's direction: mechanical changes with minimal aesthetic change. |

## 4. Architecture

### 4.1 Repo layout

```
cyniphile.github.io/
├── site-root/                 # static files, copied as they are to /
│   ├── index.html  css/  img/ # landing page, same look
│   ├── 404.html               # random 404 page (section 8.5)
│   └── CNAME  googledd6e83b608092f4a.html  robots.txt  sitemap.xml
├── blog/                      # Quarto project; it builds /blog/
│   ├── _quarto.yml
│   ├── index.qmd              # post list, RSS
│   ├── about/index.qmd
│   ├── subscribe/index.qmd
│   ├── topics/index.qmd       # all posts, filtered by the category links
│   ├── gaussian-processes/    # notebook.py + post.yml → index.qmd, widgets/ (scripts/marimo_to_blog.py)
│   ├── abortion/              # index.qmd, images
│   ├── voter-fraud/           # index.qmd, images
│   ├── biology-rust/          # index.qmd, images
│   └── _freeze/               # stored outputs of Python chunks (committed)
├── design/                    # GIMP source files (.xcf); not published
├── docs/superpowers/          # specs and plans; not published
├── scripts/redirects.py       # the list of old URLs and their redirect pages (section 4.3)
├── scripts/build.py           # full build (section 6.3)
├── scripts/check_site.py      # automatic checks (section 7.1)
├── scripts/migrate_fastpages.py  # one-time converter for the old posts (section 8.1)
├── tests/                     # pytest tests for the scripts and the converter
├── pyproject.toml, uv.lock    # Python for build time
└── .github/workflows/publish.yml
```

### 4.2 URLs and redirects

| Page | New URL | Old URLs that redirect to it |
|---|---|---|
| Landing page | `/` | (same) |
| Post list | `/blog/` | `/blog/search/` |
| About | `/blog/about/` | (same) |
| Subscribe | `/blog/subscribe/` | (same) |
| Topics | `/blog/topics/` | `/blog/categories/` (the old "Topics" page) |
| GP post | `/blog/gaussian-processes/` | `/marimo-blog/`, `/marimo-blog/apps/Intro_to_Gaussian_Process_Regression.html` |
| GP live notebook | `/blog/gaussian-processes/live/` | (new) |
| Abortion post | `/blog/abortion/` | `/blog/abortion/politics/2020/10/20/abortion.html` |
| Election fraud post | `/blog/voter-fraud/` | `/blog/election%20fraud/politics/2020/11/12/voter-fraud.html` |
| Rust post | `/blog/biology-rust/` | `/blog/programming/rust/biology/2021/12/01/biology-rust.html` |
| RSS feed | `/blog/index.xml` | `/blog/feed.xml` is a copy of the new feed, not a redirect, because feed readers do not follow HTML redirects |

### 4.3 Redirect method

GitHub Pages cannot do server redirects. So `scripts/redirects.py` holds one list of old paths and new paths. The build writes a small HTML page at each old path. Each page has:
- a `<meta http-equiv="refresh">` tag with the new path, which sends browsers to the new page
- a `<link rel="canonical">` tag with the full new URL, which gives search engines the new URL
- a normal link to the new page

The checks in section 7.1 use the same list. (Quarto `aliases` are not used. Their pages redirect with JavaScript only, and they are in a different place from the checks.)

## 5. Posts and interactivity

### 5.1 Kinds of post

1. **Text post:** `index.qmd` with Markdown only.
2. **Notebook post:** a marimo notebook `notebook.py` and `post.yml` (title, description, date, categories, image) in the post folder. `scripts/marimo_to_blog.py` writes `index.qmd` and `widgets/` from them; the build runs it when the notebook, `post.yml` or the converter changes. The build also exports `notebook.py` to `<post URL>/live/` in marimo's run mode with the code shown (`--show-code`): the live notebook. Its cells run when the page loads. (Edit mode was used first, but in edit mode marimo does not run the cells at load, so the widgets do nothing until the reader clicks "Run all". Run mode is read-only.)

### 5.2 Widgets (changed 2026-10-01)

The first design (Observable JS controls and Observable Plot charts over data from a separate `gp_data.py`) is replaced by the marimo → blog converter, on the owner's direction ("remiplementing in js is going to be a nightmare", "js version sucks", "made a dedicated transpilation script for these widgets so future posts can be easily made blog ready"). The design is in `docs/superpowers/specs/2026-10-01-marimo-to-blog-design.md`. In short: marimo runs the notebook at build time; the notebook's own Plotly and Altair figures and marimo-look controls go in the page; slider and button states are precomputed with marimo's semantics; matrix inputs that feed `np.random.multivariate_normal` are computed in the browser from recorded draws; code editors run live with Pyodide.

### 5.3 Rules

- A post has no JavaScript of its own. The shared runtime is `blog/assets/mb/` (written one time).
- The page HTML (with the default figures) must be less than 1.5 MB compressed. Widget data (`widgets/*.json`) loads when its widget comes near the screen.

### 5.4 GP post

- `blog/gaussian-processes/notebook.py` is a copy of `apps/Intro_to_Gaussian_Process_Regression.py` from `marimo-blog`.
- One text change: the sentence about "the ellipses in the upper right corner" links to the live notebook (the marimo page's menu has no "show code").

## 6. Build and deploy

### 6.1 Local work

1. Install Quarto 1.10.18 and uv (one time only). Run `uv sync`.
2. Make the folder `blog/<slug>/` with `index.qmd`.
3. Run `uv run quarto preview blog`. The page updates each time you save.
4. Commit the post and its `blog/_freeze/` files. Push to `master`.

To see the full site: run `uv run scripts/build.py`, then `python -m http.server -d _site`.

### 6.2 Freeze

`blog/_quarto.yml` sets `execute: freeze: auto`. Quarto runs the Python of a post only when its source changes. It stores the outputs in `blog/_freeze/`. Old posts do not run again, so a library upgrade cannot break them.

### 6.3 Build script (`scripts/build.py`)

The same script runs on the laptop and in CI:
1. Delete `_site/`.
2. Run `quarto render blog`. Quarto writes `blog/_site/`. Copy it to `_site/blog/`.
3. For each `blog/*/notebook.py`: convert it to `index.qmd` when it is out of date (before the Quarto render), and run `marimo export html-wasm --mode run --show-code --execute` to `_site/blog/<slug>/live/index.html` (then delete the `CLAUDE.md` that marimo writes next to it).
4. Copy `site-root/` to `_site/`.
5. Write the redirect pages from `scripts/redirects.py`. If a real page already exists at an old path, stop the build.
6. Copy `_site/blog/index.xml` to `_site/blog/feed.xml`.
7. Run `scripts/check_site.py`.

### 6.4 CI (`.github/workflows/publish.yml`)

- A push to `master`: install Quarto 1.10.18 and uv, run `uv sync --frozen`, run `scripts/build.py`, then deploy `_site` with `actions/upload-pages-artifact` and `actions/deploy-pages`.
- A pull request: the same build and checks, with no deploy.
- Python and marimo versions come from `uv.lock`.

### 6.5 Errors

- A Python error in a chunk stops `quarto render`.
- Each step of `scripts/build.py` stops the build on an error and returns a non-zero exit code. (The current `build.py` in `marimo-blog` prints the error and continues.)
- The deploy job runs only if the build job succeeds.
- To undo a bad deploy, revert the commit. CI then deploys the previous version.

## 7. Checks

### 7.1 Automatic (`scripts/check_site.py`, in each build)

- Each old URL in section 4.2 exists in `_site` and points to the correct new URL.
- No internal link or asset is missing (`/live/` folders are not included).
- For each post, the HTML with its local scripts, styles and data is less than 1.5 MB compressed.
- Each image in `blog/` is less than 300 KB.
- The RSS feed contains all posts and no other pages. (The feed has the same items as the post list.)
- Comments show on posts and on no other page.

### 7.2 Manual, before the cutover

With the phone settings from section 1.1:
- The first text shows in less than 2 s on each post.
- The GP widgets work in less than 3 s. Test each widget in section 5.4.
- Each page looks correct at phone width and at desktop width (light mode only; the site has no dark mode).
- The live notebook opens and runs.

## 8. Migration

### 8.1 Old posts

| Old (fastpages) | New (Quarto) |
|---|---|
| Jekyll front matter | Quarto front matter: `title`, `date`, `description`, `categories`, `image`, `aliases` |
| `{% fn 1 %}` and `fndetail` footnotes | Markdown footnotes (`[^1]`) |
| `{{ site.baseurl }}/images/...` | images in the post folder, with relative paths |
| file names with spaces or parentheses | lowercase names without spaces |
| large PNG screenshots (Rust post: 13 images, 2.4 MB) | WebP files, each less than 300 KB |
| YouTube iframes | the Quarto `{{< video >}}` shortcode, with the same start time |
| tweet embeds with `widgets.js` | the tweet text as a quote with a link, and no external script |
| the dead Heroku chart (abortion post) | a note: "The interactive chart for this post is no longer online." |

| Post | Date | Categories |
|---|---|---|
| The Slant Fueling The Abortion War Must End | 2020-10-20 | abortion, politics |
| The State That Commits More Election Fraud Than Michigan (By One Popular Metric) | 2020-11-12 | election fraud, politics |
| Five Levels Of (Bioinformatics) Programming | 2021-12-01 | programming, rust, biology |
| The First Blog Post You Should Read about Gaussian Processes (With Interactive Plots) | 2025-02-12 | statistics, machine learning, interactive |

The GP post image for the post list and link previews is a JPEG of the chart of 500 posterior samples. Python makes it one time, and the JPEG is committed.

### 8.2 About and Subscribe

- About: the old page layout and text of `_pages/about.md`, with the same Font Awesome social icons. "powered by fastpages" changes to "powered by Quarto".
- Subscribe: the old page layout, with the same Mailchimp form and the same social icons.

### 8.3 Comments

- giscus uses GitHub Discussions in `cyniphile.github.io`, with the mapping `pathname`. Comments show on posts only. The comment frame loads when the reader comes near it (the build adds lazy loading: Quarto 1.10.18 ignores the option).
- Each page has one path: a script in the page head changes `.../index.html` to `.../` before GoatCounter and giscus read it (the post list links to `.../index.html`). giscus's thread title for a post is its path without the first slash, for example `blog/voter-fraud/`.
- The 3 comments on the election fraud post move: transfer issue #17 from `blog` to `cyniphile.github.io`, convert it to a discussion, and set its title to `blog/voter-fraud/`.

### 8.4 Landing page

The files move into `site-root/`. The look does not change. Fixes:
- Remove the leftover text `| relative_url }}"` in the `mask-icon` link.
- Remove the Font Awesome script, because the page does not use it.
- Replace the Universal Analytics code with GoatCounter.
- Replace the 2020 `sitemap.xml` with a file that lists `/`. Add `robots.txt`. It lists `/sitemap.xml` and `/blog/sitemap.xml` (made by Quarto).
- Move the `.xcf` files to `design/`.

### 8.5 404 page

- One `site-root/404.html`. After the cutover, GitHub Pages uses it for all missing paths, also under `/blog/`.
- On each load, a small inline script shows version A or version B, with equal chance:
  - A: the current ASCII art with the Will Durant quote.
  - B: the old blog version: "404", "Page not found :(" and the GIF.
- Without JavaScript, version A shows.
- The GIF loads only when version B shows (the script sets its `src`).
- The GIF (3.8 MB) becomes a looping, muted MP4 video if the video looks the same. If not, the GIF stays.
- All asset paths are absolute (for example `/img/...`), because GitHub serves `404.html` at any path.

### 8.6 Site functions and look

Owner direction (2026-09-29): "mechanical changes with minimal aesthetic change", and no dark mode. So the blog keeps the look of the old fastpages blog. (This replaces an earlier version of this section that had new themes, a new navigation bar and a dark-mode switch.)

- Header: the old "Luke /// blog" header, with the same HTML and CSS: "Luke" links to the landing page, three colored slashes, and "blog" links to `/blog/`. There is no Quarto navigation bar. Where the old CSS and the live old page differ (the header line is not visible, and links in the text have the text color with no underline), the blog copies the live page.
- One light theme. There is no dark mode and no switch.
- Fonts and colors as the old site: Lato for titles and links in the header, footer and post list; Source Serif Pro (20 px, #515151) for post text; the old system font stack for other text. Code blocks use the Dracula colors.
- Post list at `/blog/`: the old cards, with the image on the left (hidden on small screens), then the title, description and date ("Dec 1, 2021"). There is no page heading, no category sidebar and no search box. Only posts show in the list, not About, Subscribe or Topics. The list has an RSS feed.
- Post pages: the old post header (title, description, date, and a tag icon with one link per category to the Topics page). The Rust and voter-fraud posts show the old inline table of contents at the top of the post body; the abortion post shows none, as on the old site. Image titles show as small, centered, italic captions, as on the old site. Tables in posts use the old table styles.
- Footer: the old fixed footer with the links About, Subscribe and Topics. (Search is dropped: Quarto search needs a navigation bar. The old Search URL redirects to `/blog/`.)
- Topics page at `/blog/topics/`: a list of all posts that the category links can filter.
- Math: KaTeX (`html-math-method: katex`, with the version pinned at build time). If a formula does not show correctly, that post uses MathJax.
- Link previews: Open Graph and Twitter card tags.
- Analytics: GoatCounter on all pages, including the landing page and the 404 page.

## 9. Cutover

The owner approves each change to GitHub settings and each action on an external site.

1. Build and check the new site on a branch (section 7).
2. Turn on Discussions in `cyniphile.github.io` and install the giscus app. Make the GoatCounter account.
3. Merge the branch to `master`. Set the Pages source of `cyniphile.github.io` to "GitHub Actions". Keep the custom domain `www.lukeschiefelbein.com`.
4. Turn off Pages in `blog` and `marimo-blog`. Until this step, their old sites stay at `/blog/` and `/marimo-blog/`, because GitHub serves a project site first.
5. Check all URLs, redirects, the feed, comments and analytics on the live site.
6. Move issue #17 (section 8.3).
7. Archive `blog` and `marimo-blog`.

## 10. Out of scope

- New posts.
- Inline live marimo cells (quarto-marimo islands), until they can load on demand.
- A click-to-load embed of a marimo app inside a post. Add it when a post needs it.
- A new version of the dead abortion chart.
- The post "Notes On A Year Off". It is not in the `blog` repo. (Issue #10 has 2 comments on it.)
- A rename of `master` to `main`.

## 11. Risks and open items

| Risk | Action |
|---|---|
| KaTeX does not show some GP formulas. | That post uses MathJax. |
| About and Subscribe are also `index.qmd` files under `blog/`, so the post list can include them. | The listing uses `exclude: {title: "{About,Subscribe}"}`. The feed check in section 7.1 confirms the list. |
| The old URL with a space (`election fraud`) gets the wrong file name. | `redirects.py` decodes `%20` to a space, and a test covers it. |
| GitHub serves a project site before a folder of the user site. | The cutover order handles this. Check after step 4. |
| Large widget data delays the first text. | The converter writes widget data to `widgets/*.json`; the runtime loads it near the screen. |
| Each marimo export copies approximately 29 MB of frontend files. | No action for one notebook. Look again if the site gets more live notebooks. |
| The giscus mapping does not find the moved discussion. | Set the discussion title to the exact giscus term `blog/voter-fraud/`. |
