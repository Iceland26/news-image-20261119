# news-image-20261119

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/Iceland26/news-image-20261119/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/Iceland26/news-image-20261119/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

**THE WORLD TODAY** — one image that sums up the world's news of **Wednesday 19 November 2026**, drawn entirely in code. No photographs, no image assets, no fonts on disk: a pure Python 3 standard-library program typesets a newspaper front page with its own constructed outline typeface (three cuts — serif display, serif bold, sans — every glyph drawn as measured polygon contours on a 1000-unit em grid), a scanline rasteriser with 4× supersampling, and a hand-rolled PNG encoder.

The front page carries 27 stories of the day, every one of them reported on 19 November 2026: the first Trump–Xi–Putin trilateral summit in Shenzhen as the lead, Iran's widening war and the mined tankers near Hormuz, the ICJ's genocide ruling on Myanmar, Ukraine's third strike on the Kerch Bridge, Anthropic's record $81.3bn IPO (with a bar chart against SpaceX's $75bn), a "Day in Numbers" rail, a dot-grid world map with the day's hotspots, briefs from five continents, a live-style markets ticker, and a sport strip from Turin, Hobart and Manchester.

The render is deterministic — no randomness, no clock, no network — so two runs write byte-identical PNGs (1024×1024, ~100 KB, well under the 1 MiB cap).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
# writes out/entry.png
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=006egfwh&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
