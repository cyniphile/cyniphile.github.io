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

## 4. Architecture

### 4.1 Repo layout

```
cyniphile.github.io/
├── site-root/                 # static files, copied as they are to /
│   ├── index.html  css/  img/ # landing page, same look
│   ├── 404.html               # random 404 page (section 8.5)
│   ├── CNAME  googledd6e83b608092f4a.html  robots.txt  sitemap.xml
│   └── marimo-blog/           # 2 redirect pages (section 4.2)
├── blog/                      # Quarto project; it builds /blog/
│   ├── _quarto.yml
│   ├── index.qmd              # post list, RSS
│   ├── about/index.qmd
│   ├── subscribe/index.qmd
│   ├── gaussian-processes/    # index.qmd, live.py (marimo notebook), images
│   ├── abortion/              # index.qmd, images
│   ├── voter-fraud/           # index.qmd, images
│   ├── biology-rust/          # index.qmd, images
│   └── _freeze/               # stored outputs of Python chunks (committed)
├── design/                    # GIMP source files (.xcf); not published
├── docs/superpowers/specs/    # this file; not published
├── scripts/build.py           # full build (section 6.3)
├── scripts/check_site.py      # automatic checks (section 7.1)
├── pyproject.toml, uv.lock    # Python for build time
└── .github/workflows/publish.yml
```

### 4.2 URLs and redirects

| Page | New URL | Old URLs that redirect to it |
|---|---|---|
| Landing page | `/` | (same) |
| Post list | `/blog/` | `/blog/search/`, `/blog/categories/` |
| About | `/blog/about/` | (same) |
| Subscribe | `/blog/subscribe/` | (same) |
| GP post | `/blog/gaussian-processes/` | `/marimo-blog/`, `/marimo-blog/apps/Intro_to_Gaussian_Process_Regression.html` |
| GP live notebook | `/blog/gaussian-processes/live/` | (new) |
| Abortion post | `/blog/abortion/` | `/blog/abortion/politics/2020/10/20/abortion.html` |
| Election fraud post | `/blog/voter-fraud/` | `/blog/election%20fraud/politics/2020/11/12/voter-fraud.html` |
| Rust post | `/blog/biology-rust/` | `/blog/programming/rust/biology/2021/12/01/biology-rust.html` |
| RSS feed | `/blog/index.xml` | `/blog/feed.xml` is a copy of the new feed, not a redirect, because feed readers do not follow HTML redirects |

### 4.3 Redirect method

GitHub Pages cannot do server redirects.
- Redirects under `/blog/` use Quarto `aliases` in the front matter of the new page. Quarto makes a small HTML page at each old path. This page sends the reader to the new URL and gives search engines the new URL.
- The two `/marimo-blog/` redirects are static HTML files in `site-root/marimo-blog/`, because they are outside the Quarto project.

## 5. Posts and interactivity

### 5.1 Kinds of post

1. **Text post:** `index.qmd` with Markdown only.
2. **Data post:** `index.qmd` with Python chunks. Python runs at build time. The outputs are static charts or widgets. The code is folded (`code-fold: true`), so a reader can click "Code" to see it.
3. **Post with a live notebook:** a data post with a marimo notebook `live.py` in the same folder. The build exports the notebook to `<post URL>/live/`. The post has a link: "Open the live notebook (downloads Python: 20–70 s on a phone)".

### 5.2 Widget pattern

1. A Python chunk calculates all data at build time with a fixed random seed. It sends the data to the page with `ojs_define(...)`.
2. An Observable JS (OJS) cell makes the controls (`Inputs.range`, `Inputs.button`, `Inputs.text`) and selects the precomputed data for the current setting. A "New Sample" button adds the next stored sample to the chart. Each stored set has 50 samples. After 50 samples are on the chart, the button adds no more. "Clear" removes the samples, and the next click starts again at the first sample.
3. Observable Plot draws the chart. Plot is part of Quarto OJS.

Example:

````markdown
```{python}
#| code-fold: true
pools = {l: sample_gp(x, l, n=50).round(3).tolist() for l in range(1, 31)}
ojs_define(fuzzy={"x": x.tolist(), "pools": pools})
```

```{ojs}
viewof ell = Inputs.range([1, 30], {step: 1, value: 5, label: "ℓ"})
viewof n = Inputs.button("New Sample")
Plot.plot({marks: fuzzy.pools[ell].slice(0, n).map(ys =>
  Plot.line(ys, {x: (_, i) => fuzzy.x[i], y: d => d}))})
```
````

### 5.3 Rules

- JavaScript does no vector or matrix math. Short scalar formulas are permitted, for example μ + σ·z, the RBF formula for one pair of points, or the 3-line formula for a 2×2 Cholesky.
- The HTML, scripts and data of a post must be less than 1.5 MB compressed (images and the live notebook are not included).
- Widgets use Observable Plot. Static charts can use Plot or a Python library. Plotly adds approximately 1 MB, so use it only when you need its functions.

### 5.4 GP post

- Title, text and LaTeX come from `apps/Intro_to_Gaussian_Process_Regression.py` in `marimo-blog`.
- All calculations use the numpy code of the notebook with `np.random.seed(42)`. In the post, numpy replaces scipy, so the build environment does not need scipy. (The export of the live notebook installs its own packages from the notebook header.)
- The live notebook `live.py` is the current marimo notebook without changes.

| # | Widget in the notebook | New widget |
|---|---|---|
| 1 | Regression lines A and B: "New Sample", "Reset" | Python stores 50 (β₀, β₁) pairs and their lines for each plot. The buttons show the next line or clear the lines. |
| 2 | Histogram with "Mean" (−5 to 5, step 0.1) and "Variance" (0.1 to 5, step 0.1) sliders | Python stores 5,000 standard-normal values z. The chart shows μ + σ·z with σ = √variance. (The notebook uses the slider value as σ, so its label is wrong. The new widget fixes this.) |
| 3 | 2×2 covariance matrix and mean vector (step 0.1, minimum 0) | 5 number inputs with the same limits. Python stores 2,500 standard-normal pairs. The browser applies the 2×2 Cholesky formula. If the matrix is not positive semi-definite, the widget shows an error and only the gray reference cloud. |
| 4 | 1-D, 2-D, 3-D samples: "New Sample", "Clear" | Python stores 50 samples for each. |
| 5 | 50-D samples: "New Sample", "Connect Points", "Clear" | Python stores 50 samples. "Connect Points" changes the dots to lines with dots. |
| 6 | ℓ slider (1 to 30, step 1, default 5) with the 50×50 RBF heatmap (shown two times in the post) | The browser calculates exp(−(xᵢ−xⱼ)²/(2ℓ²)) for each cell. Both heatmaps use the same slider. |
| 7 | "Fuzzy" samples with the current ℓ: "New Sample", "Clear" | Python stores 50 samples for each ℓ from 1 to 30. |
| 8 | Samples at multiples of π; 50 samples at real values: "New Sample", "Clear" | Python stores 50 samples for each. |
| 9 | Code editor (the reader edits Python) | A text box for the points (default `1.549, 2, 3, 4, 5, 6, 10`) and an ℓ input (default 1). The browser calculates the annotated RBF heatmap. A link opens the live notebook. |
| 10 | ℓ slider (0.01 to 2.0, step 0.01, default 0.5) with samples and heatmap | The step changes to 0.05 (40 values from 0.05 to 2.0). Python stores 50 samples for each ℓ. The browser calculates the heatmap. "New Sample" adds a sample for the current ℓ, with ℓ in the legend. |
| 11 | Posterior samples of the housing data (ℓ = 1): "New Sample", "Clear" | Python stores 50 posterior samples. |
| 12 | "Sample 500 Functions from Posterior" | Python stores 500 posterior samples. The button shows all of them at 2% opacity. |
| 13 | Static charts: regression data, identity matrix, covariance heatmaps, housing data, conditional covariance and mean | Static Observable Plot charts from Python data. |

Estimated precomputed data: approximately 210,000 numbers with 3 decimals, which is approximately 1.4 MB raw and 0.5 MB compressed.

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
2. Run `quarto render blog`. The output goes to `_site/blog/`.
3. For each `blog/*/live.py`: run `marimo export html-wasm --mode run --no-show-code --execute` to `_site/blog/<slug>/live/index.html`.
4. Copy `site-root/` to `_site/`.
5. Copy `_site/blog/index.xml` to `_site/blog/feed.xml`.
6. Run `scripts/check_site.py`.

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

### 7.2 Manual, before the cutover

With the phone settings from section 1.1:
- The first text shows in less than 2 s on each post.
- The GP widgets work in less than 3 s. Test each widget in section 5.4.
- Each page looks correct at phone width and at desktop width, in light mode and in dark mode.
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

The GP post image for the post list and link previews is a PNG of the chart of 500 posterior samples. Python makes it one time, and the PNG is committed.

### 8.2 About and Subscribe

- About: the text of `_pages/about.md`. "powered by fastpages" changes to "powered by Quarto". The social links are text links, with Quarto icons where they exist.
- Subscribe: the same Mailchimp form and the RSS link. The social links are only on the About page.

### 8.3 Comments

- giscus uses GitHub Discussions in `cyniphile.github.io`, with the mapping `pathname`. Comments show on posts only.
- The 3 comments on the election fraud post move: transfer issue #17 from `blog` to `cyniphile.github.io`, convert it to a discussion, and set its title to the pathname of the new post.

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

- Post list at `/blog/`: the title, date, description and image of each post, with categories and RSS. Only posts show in the list, not About or Subscribe.
- Search: Quarto site search.
- Themes: `cosmo` (light) and `darkly` (dark), with a switch. The accent colors come from the wobble image.
- Navigation bar: a small wobble image, your name, and links to Blog, About, Subscribe and RSS.
- Math: KaTeX (`html-math-method: katex`). If a formula does not show correctly, that post uses MathJax.
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
| About and Subscribe are also `index.qmd` files under `blog/`, so the post list can include them. | The plan selects the method (a listing filter or a file pattern). The check in section 7.1 or a manual check confirms the list. |
| The old URL with a space (`election fraud`) fails as a Quarto alias. | Use a static redirect file in `site-root/blog/election fraud/...`. |
| GitHub serves a project site before a folder of the user site. | The cutover order handles this. Check after step 4. |
| The inline `ojs_define` data delays the first text. | Write large data to JSON files and load them with `FileAttachment`. |
| Each marimo export copies approximately 29 MB of frontend files. | No action for one notebook. Look again if the site gets more live notebooks. |
| The giscus mapping does not find the moved discussion. | Set the discussion title to the exact pathname. |
