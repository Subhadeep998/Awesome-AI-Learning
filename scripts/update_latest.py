#!/usr/bin/env python3
"""Rebuild LATEST.md: trending papers, newest arXiv research, rising AI repos.

Runs weekly from .github/workflows/latest.yml. Standard library only.
Each section is independent: if one source is down, the others still render.
"""
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Awesome-AI-Learning-feed (github.com/Subhadeep998)"}
ATOM = "{http://www.w3.org/2005/Atom}"


def get(url, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def clean(text):
    return " ".join((text or "").split()).replace("|", "\\|")


def hf_trending(limit=12):
    data = json.loads(get("https://huggingface.co/api/daily_papers?limit=100"))
    papers = []
    for d in data:
        p = d.get("paper", d)
        papers.append((p.get("upvotes", 0) or 0, p.get("id"), clean(p.get("title") or d.get("title"))))
    papers.sort(reverse=True)
    rows = ["| ▲ | Paper |", "|--:|:--|"]
    for up, pid, title in papers[:limit]:
        rows.append(f"| {up} | [{title}](https://huggingface.co/papers/{pid}) |")
    return rows


def arxiv(query, limit=10):
    params = urllib.parse.urlencode({
        "search_query": query, "sortBy": "submittedDate", "sortOrder": "descending",
        "start": 0, "max_results": limit,
    })
    root = ET.fromstring(get(f"https://export.arxiv.org/api/query?{params}"))
    rows = ["| Date | Paper | Category |", "|:--|:--|:--|"]
    for e in root.findall(f"{ATOM}entry"):
        title = clean(e.findtext(f"{ATOM}title"))
        link = (e.findtext(f"{ATOM}id") or "").replace("http://", "https://")
        date = (e.findtext(f"{ATOM}published") or "")[:10]
        cat_el = e.find("{http://arxiv.org/schemas/atom}primary_category")
        cat = cat_el.get("term") if cat_el is not None else ""
        rows.append(f"| {date} | [{title}]({link}) | `{cat}` |")
    return rows


def github_rising(limit=12):
    since = (dt.date.today() - dt.timedelta(days=30)).isoformat()
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    found = {}
    for topic in ("llm", "ai-agents", "generative-ai", "machine-learning", "mcp"):
        url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
            {"q": f"topic:{topic} created:>{since}", "sort": "stars", "order": "desc", "per_page": limit})
        try:
            for it in json.loads(get(url, headers)).get("items", []):
                found[it["full_name"]] = it
        except Exception as exc:
            print(f"[github] {topic}: {exc}", file=sys.stderr)
    items = sorted(found.values(), key=lambda x: x.get("stargazers_count", 0), reverse=True)[:limit]
    rows = ["| ★ | Repository | What it is |", "|--:|:--|:--|"]
    for it in items:
        desc = clean(it.get("description") or "")[:140]
        rows.append(f"| {it.get('stargazers_count', 0):,} | [{it['full_name']}]({it['html_url']}) | {desc} |")
    return rows


SECTIONS = [
    ("🔥 Trending papers this week", "Most-upvoted on Hugging Face Daily Papers.", lambda: hf_trending()),
    ("🧠 Newest in AI & machine learning", "Latest arXiv submissions in cs.AI and cs.LG.",
     lambda: arxiv("cat:cs.AI OR cat:cs.LG")),
    ("💬 Newest in language models & NLP", "Latest arXiv submissions in cs.CL.", lambda: arxiv("cat:cs.CL")),
    ("🤖 Newest on AI agents", "arXiv papers mentioning agents.",
     lambda: arxiv('(cat:cs.AI OR cat:cs.CL) AND (ti:agent OR ti:agents OR ti:agentic)')),
    ("🧬 AI × biology & medicine", "Where machine learning meets the life sciences.",
     lambda: arxiv("(cat:q-bio.QM OR cat:q-bio.GN OR cat:q-bio.BM) AND (abs:\"deep learning\" OR abs:\"language model\" OR abs:\"machine learning\")")),
    ("🛠️ Rising open-source AI repos", "Most-starred AI repos created in the last 30 days.", lambda: github_rising()),
]


def main():
    out = [
        "# ⚡ Latest in AI",
        "",
        f"> Auto-generated on **{dt.date.today():%d %B %Y}** · refreshed every Monday.",
        "> Preprints are not peer-reviewed and stars are not quality — use your judgement.",
        "",
        "[← Back to Awesome AI Learning](README.md)",
        "",
    ]
    ok = 0
    for title, blurb, fn in SECTIONS:
        try:
            rows = fn()
            if len(rows) <= 2:
                continue
            out += [f"## {title}", "", f"<sub>{blurb}</sub>", "", *rows, ""]
            ok += 1
        except Exception as exc:
            print(f"[skip] {title}: {exc}", file=sys.stderr)
    if ok == 0:
        print("All sources failed; leaving LATEST.md unchanged.")
        return 0
    out += ["---", f"<sub>Sources: Hugging Face Papers · arXiv API · GitHub Search API · generated {dt.datetime.utcnow():%Y-%m-%d %H:%M} UTC</sub>", ""]
    with open("LATEST.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"Wrote LATEST.md with {ok} sections.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
