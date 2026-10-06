"""SmokeShopSpectator — fetch industry feeds, tag each story, and build a static page.

Usage:
    python build.py                       # uses feeds.json, writes to ./_site
    python build.py --config feeds.json --out _site
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import feedparser

HERE = Path(__file__).parent
USER_AGENT = "Mozilla/5.0 (compatible; SmokeShopSpectator/1.0; +https://github.com/hmahmoud1/Warehouse)"
TIMEOUT_SECONDS = 20


# ---------- fetching ----------

def fetch(source):
    """Return (source, entries, error). Never raises."""
    url = source["url"]
    try:
        if url.startswith(("http://", "https://")):
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                data = resp.read()
        else:  # local file, used for testing
            data = (HERE / url).read_bytes() if not Path(url).is_absolute() else Path(url).read_bytes()
        parsed = feedparser.parse(data)
        if parsed.bozo and not parsed.entries:
            return source, [], f"unreadable feed ({parsed.bozo_exception.__class__.__name__})"
        return source, parsed.entries, None
    except Exception as exc:  # network errors, timeouts, HTTP errors
        return source, [], exc.__class__.__name__


# ---------- cleaning ----------

TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def clean_text(value, limit=None):
    text = html.unescape(TAG_RE.sub(" ", value or ""))
    text = SPACE_RE.sub(" ", text).strip()
    if limit and len(text) > limit:
        text = text[: limit].rsplit(" ", 1)[0] + "…"
    return text


def entry_time(entry):
    for key in ("published_parsed", "updated_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(time.mktime(value), tz=timezone.utc)
    return None


def split_google_title(title, source):
    """Google News titles look like 'Headline - Publisher'. Pull the publisher out."""
    if "news.google.com" in source["url"] and " - " in title:
        headline, publisher = title.rsplit(" - ", 1)
        return headline.strip(), publisher.strip()
    return title, source["name"]


def normalize_key(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


# ---------- tagging ----------

def compile_tags(tags):
    compiled = []
    for tag in tags:
        pattern = r"\b(" + "|".join(re.escape(k) for k in tag["keywords"]) + r")\b"
        compiled.append((tag, re.compile(pattern, re.IGNORECASE)))
    return compiled


def tag_story(text, compiled_tags):
    return [tag["id"] for tag, rx in compiled_tags if rx.search(text)]


# ---------- build ----------

def build(config_path, out_dir):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    site = config["site"]
    compiled = compile_tags(config["tags"])
    kinds = {t["id"]: t["kind"] for t in config["tags"]}
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=site.get("max_age_days", 30))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch, config["sources"]))

    stories, seen, status = [], {}, []
    for source, entries, error in results:
        kept = 0
        for entry in entries:
            raw_title = clean_text(entry.get("title"))
            link = entry.get("link")
            if not raw_title or not link:
                continue
            title, publisher = split_google_title(raw_title, source)
            published = entry_time(entry)
            if published and published < cutoff:
                continue
            summary = clean_text(entry.get("summary"), limit=240)
            if "news.google.com" in source["url"]:
                summary = ""  # Google News summaries just repeat the headline
            tags = tag_story(f"{title} {summary}", compiled)
            if source.get("relevant_only") and not any(kinds[t] == "product" for t in tags):
                continue

            key = normalize_key(title)
            if key in seen:  # same story from two feeds: merge tags, keep first link
                existing = seen[key]
                merged = set(existing["tags"]) | set(tags)
                existing["tags"] = [t["id"] for t in config["tags"] if t["id"] in merged]
                continue
            story = {
                "title": title,
                "link": link,
                "publisher": publisher,
                "group": source["group"],
                "summary": summary,
                "published": published.isoformat() if published else None,
                "tags": tags,
            }
            seen[key] = story
            stories.append(story)
            kept += 1
        status.append({"name": source["name"], "group": source["group"], "ok": error is None, "error": error, "count": kept})

    stories.sort(key=lambda s: s["published"] or "", reverse=True)
    stories = stories[: site.get("max_items", 400)]

    payload = {
        "site": site,
        "built": now.isoformat(),
        "tags": [{k: t[k] for k in ("id", "label", "color", "kind")} for t in config["tags"]],
        "stories": stories,
        "sources": status,
    }

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "stories.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    template = (HERE / "template.html").read_text(encoding="utf-8")
    data_js = json.dumps(payload).replace("</", "<\\/")  # safe inside <script>
    page = template.replace("__DATA__", data_js).replace("__TITLE__", html.escape(site["title"]))
    (out / "index.html").write_text(page, encoding="utf-8")

    failed = [s["name"] for s in status if not s["ok"]]
    print(f"Built {len(stories)} stories from {len(status) - len(failed)}/{len(status)} sources -> {out / 'index.html'}")
    if failed:
        print("Not responding: " + ", ".join(failed))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(HERE / "feeds.json"))
    parser.add_argument("--out", default=str(HERE / "_site"))
    args = parser.parse_args()
    sys.exit(build(args.config, args.out))
