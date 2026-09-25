"""Verify the public bilingual Edukaizen RCS 61q series after publication."""

from __future__ import annotations

import json
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
PAGES = MANIFEST["pages"]
BY_PAIR = {(p["lang"], p["part"]): p for p in PAGES}
BASE = MANIFEST["base"]


class AnchorLabels(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.labels: list[str] = []
        self._parts: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._parts is not None:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._parts is not None:
            self.labels.append(" ".join("".join(self._parts).split()))
            self._parts = None


def fetch(url: str) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "Edukaizen-RCS61-series-verifier/1.0",
                                    "Cache-Control": "no-cache"})
    with urlopen(request, timeout=25) as response:
        return response.status, response.read().decode("utf-8", "replace")


def main() -> None:
    rows = []
    cache_bust = str(time.time_ns())
    for page in PAGES:
        url = BASE + page["path"] + "?rcs61verify=" + cache_bust
        status, html = fetch(url)
        other = BY_PAIR[("en" if page["lang"] == "nl" else "nl", page["part"])]
        checks = {
            "http_200": status == 200,
            "series_marker": "rcs61-series-20260925" in html,
            "language_link": other["path"] in html,
            "source_paper": "arxiv.org/abs/2609.28657" in html,
            "project_repo": "github.com/BramDo/rcs-nighthawk-replication" in html,
            "navigation": "rcs61-navigation" in html,
        }
        if page["part"] == 0:
            checks["part_four_link"] = BY_PAIR[(page["lang"], 4)]["path"] in html
        if page["part"] == 4:
            checks["rcs_theory"] = "Porter" in html and "Boixo" in html
            checks["applications"] = ("Processorbenchmark" in html if page["lang"] == "nl"
                                      else "Processor benchmarking" in html)
        rows.append({"key": page["key"], "url": BASE + page["path"], "checks": checks})
    status, homepage = fetch(BASE + "/?rcs61verify=" + cache_bust)
    anchors = AnchorLabels()
    anchors.feed(homepage)
    nighthawk_positions = [i for i, label in enumerate(anchors.labels) if label == "Nighthawk RCS 61q"]
    work_positions = [i for i, label in enumerate(anchors.labels) if label == "Work"]
    home = {"http_200": status == 200,
            "menu_label": "Nighthawk RCS 61q" in homepage,
            "english_hub_link": BY_PAIR[("en", 0)]["path"] in homepage,
            "nighthawk_before_work": bool(nighthawk_positions and work_positions
                                          and nighthawk_positions[0] < work_positions[0])}
    report = {"series": MANIFEST["series"], "pages": rows, "homepage": home}
    (ROOT / "verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pages": len(rows),
                      "page_checks_passed": sum(all(r["checks"].values()) for r in rows),
                      "homepage": home}, indent=2))
    failures = [r["key"] for r in rows if not all(r["checks"].values())]
    if failures or not all(home.values()):
        raise SystemExit(f"verification failed: {failures}; homepage={home}")


if __name__ == "__main__":
    main()
