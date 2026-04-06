#!/usr/bin/env python3
"""
Distro Daily Brief - AI, Markets, Models, Repos, Insights
"""
import os, json, re, urllib.request, html, time
from datetime import datetime, timedelta, timezone

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


def fetch(url, timeout=15, retries=2):
    """Fetch URL with retries. Returns string or None."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt == retries:
                return None
            time.sleep(1)
    return None


def clean_html(html_text):
    """Strip HTML tags and decode entities. Returns plain text."""
    text = re.sub(r'<[^>]+>', ' ', html_text).replace('\n', ' ').strip()
    text = (text.replace('&#x27;', "'").replace('&#x2F;', '/')
            .replace('&quot;', '"').replace('&amp;', '&')
            .replace('&gt;', '>').replace('&lt;', '<'))
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_market_indices():
    """
    Scrape Google Finance main page for major indices.
    Structure: pKBk1e (name) -> YMlKec (price) -> T7Akdb (change).
    """
    indices = {}
    try:
        resp = fetch("https://www.google.com/finance/", timeout=20)
        if not resp:
            return {"error": "Google Finance request failed"}

        names = list(re.finditer(r'class="pKBk1e">([^<]+)</div>', resp))

        for n in names:
            name = n.group(1).replace("&amp;", "&")
            if name not in ("S&P 500", "Dow Jones", "Nasdaq", "VIX"):
                continue
            if name in indices:
                continue

            start = n.start()
            chunk = resp[start:start + 800]

            # Price
            price_m = re.search(r'class="YMlKec">([^<]+)</div>', chunk)
            price = price_m.group(1) if price_m else "?"

            # Change values
            t7block = chunk.find('class="T7Akdb"')
            pct_val = "?"
            pt_val = "?"
            if t7block > 0:
                block = chunk[t7block:t7block + 500]
                spans = re.findall(r"<span[^>]*>(.*?)</span>", block, re.DOTALL)
                for s in spans:
                    t = (re.sub(r"<[^>]+>", "", s)
                         .replace("\u202f", " ").replace("\xa0", " ").strip())
                    if t and "%" in t:
                        pct_val = t
                    elif t and re.match(r"[+-]", t):
                        pt_val = t

            direction = "+" in (pct_val or "") and pct_val != "?"
            indices[name] = {
                "price": price,
                "change_pct": pct_val,
                "change_pts": pt_val,
                "direction": "green" if direction else "red",
            }

    except Exception as e:
        return {"error": str(e)}

    if not indices:
        return {"error": "No index data parsed"}

    return indices


def get_ft_news():
    """
    FT Markets + Companies + Technology RSS feeds.
    Verified: returns 25+ items per feed.
    """
    headlines = []
    feeds = [
        "https://www.ft.com/markets?format=rss",
        "https://www.ft.com/companies?format=rss",
        "https://www.ft.com/technology?format=rss",
    ]

    for feed_url in feeds:
        try:
            xml = fetch(feed_url, timeout=20)
            if not xml:
                continue
            entries = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
            for entry in entries[:4]:
                title_m = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", entry)
                desc_m = re.search(r"<description><!\[CDATA\[(.*?)\]\]></description>", entry)
                link_m = re.search(r"<link>(.*?)</link>", entry)
                if title_m and link_m:
                    title = html.unescape(title_m.group(1).strip())
                    link = link_m.group(1).strip()
                    desc = ""
                    if desc_m:
                        desc = re.sub(
                            r"<[^>]+>", "", html.unescape(desc_m.group(1))
                        ).strip()
                    headlines.append({
                        "title": title,
                        "url": link,
                        "desc": desc[:120],
                    })
        except Exception:
            pass

    return headlines


def get_hackernews():
    """Top stories filtered for AI/tech from HN."""
    stories = []
    try:
        ids_json = fetch("https://hacker-news.firebaseio.com/v0/topstories.json")
        if not ids_json:
            return stories
        ids = json.loads(ids_json or "[]")
        for item_id in ids[:40]:
            item_json = fetch(
                "https://hacker-news.firebaseio.com/v0/item/%d.json" % item_id
            )
            if not item_json:
                continue
            item = json.loads(item_json or "{}")
            title = item.get("title", "")
            score = item.get("score", 0)
            if score < 50 or not title:
                continue
            stories.append({
                "title": title,
                "score": score,
                "url": "https://news.ycombinator.com/item?id=%d" % item_id,
                "id": item_id,
                "comments": item.get("descendants", 0),
                "kids": item.get("kids", []),
            })
    except Exception:
        pass
    return stories[:8]


def extract_community_wisdom(stories):
    """
    Extract real improvement ideas from TODAY's HN discussions.
    """
    if not stories:
        return None

    hot = [s for s in stories if s["comments"] > 40
           and any(kw in s["title"].lower()
                   for kw in ["agent", "coding", "llm", "claude", "ai",
                              "assistant", "model", "workflow"])]
    hot.sort(key=lambda s: -s["comments"])

    if not hot:
        return None

    insights = []
    for thread in hot[:2]:
        kids = thread.get("kids", [])[:30]
        for kid_id in kids:
            cr = fetch("https://hacker-news.firebaseio.com/v0/item/%d.json" % kid_id, timeout=8)
            if not cr:
                continue
            kid = json.loads(cr or "{}")
            text = kid.get("text", "")
            if not text or len(text) < 120:
                continue

            clean = clean_html(text)
            if len(clean) < 100:
                continue

            lower = clean.lower()
            keywords = [
                "should", "need", "would be better", "problem", "issue",
                "annoying", "frustrating", "slow", "rate limit", "context",
                "memory", "planning", "subagent", "sandbox", "skill", "tool",
                "doesn't work", "doesn't handle", "lacks", "missing",
                "worse than", "better if", "improvement", "workaround",
                "solution", "the key", "important", "recommend", "suggest",
                "work well", "unlike", "wish", "critical",
            ]
            is_signal = any(kw in lower for kw in keywords)

            if is_signal:
                summary = clean[:200]
                if len(clean) > 200:
                    summary += "..."
                insights.append(summary)
                if len(insights) >= 2:
                    break
        if len(insights) >= 2:
            break

    if not insights:
        return None
    return insights


def get_arxiv():
    """Latest ML/AI research papers."""
    papers = []
    try:
        xml = fetch(
            "https://export.arxiv.org/api/query?"
            "search_query=cat:cs.LG+OR+cat:cs.AI&"
            "sortBy=submittedDate&sortOrder=descending&"
            "max_results=8",
            timeout=20,
        )
        if not xml:
            return papers
        for entry in re.split(r"<entry>", xml)[1:9]:
            t = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
            l = re.search(r'href="(https://arxiv.org/abs/[^"]+)"', entry)
            if t and l:
                title = re.sub(r"\s+", " ", t.group(1)).strip()
                if 10 < len(title) < 150:
                    papers.append({"title": title[:90], "url": l.group(1)})
    except Exception:
        pass
    return papers[:5]


def get_openrouter_models():
    """Free and cheap models from OpenRouter API."""
    models = []
    try:
        data = json.loads(fetch("https://openrouter.ai/api/v1/models", timeout=20) or "{}")
        seen = set()
        for m in data.get("data", []):
            mid = m.get("id", "")
            pricing = m.get("pricing", {})
            prompt_p = float(pricing.get("prompt", "0"))
            comp_p = float(pricing.get("completion", "0"))
            avg = (prompt_p + comp_p) / 2
            if mid in seen:
                continue
            seen.add(mid)

            if avg == 0 or ":free" in mid.lower():
                tier = "FREE"
                price_label = "FREE"
            elif avg < 0.10:
                tier = "CHEAP"
                price_per_m = avg * 1_000_000
                price_label = "~$%.3f/1M tks" % price_per_m
            else:
                continue

            creator = mid.split("/")[0] if "/" in mid else "unknown"
            name = mid.split("/")[-1] if "/" in mid else mid
            models.append({"name": "%s/%s" % (creator, name), "tier": tier, "price": price_label})
            if len(models) >= 10:
                break
    except Exception:
        pass
    return sorted(models, key=lambda x: 0 if x["tier"] == "FREE" else 1)


def get_trending_github():
    """Trending repos via GitHub Search API."""
    repos = []
    url = (
        "https://api.github.com/search/repositories?"
        "q=stars:>500+created:>2025-01-01&"
        "sort=stars&order=desc&per_page=8"
    )
    try:
        data = json.loads(fetch(url) or "{}")
        for item in data.get("items", []):
            repos.append({
                "name": item["full_name"],
                "url": item["html_url"],
                "desc": (item.get("description") or "")[:100],
                "stars": item["stargazers_count"],
                "lang": item.get("language") or "N/A",
            })
    except Exception:
        pass
    return repos[:6]


def generate_insights(papers, models, repos, ft_news):
    """Smart action items based on today's data."""
    insights = []
    all_text = " ".join(p.get("title", "").lower() for p in papers)
    all_text += " " + " ".join(r.get("desc", "").lower() for r in repos)
    all_text += " " + " ".join(n.get("title", "").lower() for n in ft_news)

    if "agent" in all_text:
        insights.append("Agentic AI trending - eval Phase 2 readiness")
    if "rag" in all_text or "retrieval" in all_text:
        insights.append("RAG improvements active - review pipeline")
    if "security" in all_text:
        insights.append("AI security focus - run hardening audit")

    free_count = sum(1 for m in models if m["tier"] == "FREE")
    if free_count >= 3:
        insights.append("%d free models available - audit migration" % free_count)

    fin_text = " ".join(n.get("title", "").lower() for n in ft_news)
    if any(w in fin_text for w in ("war", "conflict", "oil")):
        insights.append("Geopolitical risk elevated - monitor cloud costs")
    if any(w in fin_text for w in ("fed", "rate", "inflation")):
        insights.append("Fed/inflation in focus - watch tech spending")

    if not insights:
        insights.append("Steady day - focus on deliverables")

    return insights


def generate_self_improvement(community_wisdom, section_status):
    """
    Generate self-improvement from REAL live sources + self-reflection.
    """
    suggestions = []

    # 1. Community wisdom (live external signal)
    if community_wisdom:
        suggestions.append("Community: %s" % community_wisdom[0])

    # 2. Self-reflection on brief quality
    if section_status:
        broken = [name for name, status in section_status.items() if status != "OK"]
        if broken:
            suggestions.append("Fix sections: %s" % ", ".join(broken[:3]))

    # 3. Meta-check if everything is fine
    if not suggestions:
        now = datetime.now(timezone.utc)
        day = now.strftime("%A")
        if day == "Monday":
            suggestions.append("Weekly: Review 7 briefs - what am I ignoring?")
        elif day == "Friday":
            suggestions.append("Weekly: What automation wins this week?")
        else:
            suggestions.append("Daily: What section was weakest today?")

    # 4. Add one more community insight if available
    if community_wisdom and len(community_wisdom) > 1:
        suggestions.append("Also: %s" % community_wisdom[1])

    return suggestions


def build():
    section_status = {}

    indices = get_market_indices()
    section_status["Markets"] = "OK" if "error" not in indices else indices["error"]

    ft_news = get_ft_news()
    section_status["News"] = "OK" if ft_news else "FAIL"

    hn = get_hackernews()
    section_status["HN"] = "OK" if hn else "FAIL"

    papers = get_arxiv()
    section_status["Papers"] = "OK" if papers else "FAIL"

    community_wisdom = extract_community_wisdom(hn)
    section_status["Community"] = "OK" if community_wisdom else "FAIL"

    models = get_openrouter_models()
    section_status["Models"] = "OK" if models else "FAIL"

    repos = get_trending_github()
    section_status["Repos"] = "OK" if repos else "FAIL"

    insights = generate_insights(papers, models, repos, ft_news)
    self_improve = generate_self_improvement(community_wisdom, section_status)

    now = datetime.now(timezone.utc) - timedelta(hours=5)
    date_str = now.strftime("%A, %B %d, 2026")
    msg = "<b>Distro Daily Brief</b>\n<i>%s | 12:00 PM ET</i>" % date_str

    msg += "\n\n<b>MARKETS</b>"
    if "error" in indices:
        msg += "\n  Market data unavailable"
    else:
        for name in ["S&P 500", "Dow Jones", "Nasdaq", "VIX"]:
            d = indices.get(name)
            if d:
                arrow = "\U0001f53a" if d["direction"] == "green" else "\U0001f53b"
                msg += ("\n  %s <b>%s</b>: %s (%s, %s)"
                        % (arrow, name, d["price"], d["change_pts"], d["change_pct"]))

    msg += "\n\n<b>FINANCIAL NEWS (FT)</b>"
    if ft_news:
        for n in ft_news[:6]:
            msg += '\n  <a href="%s">%s</a>' % (n["url"], html.escape(n["title"]))
            if n.get("desc"):
                msg += "\n  <i>%s</i>" % html.escape(n["desc"])
    else:
        msg += "\n  No financial headlines available"

    msg += "\n\n<b>AI NEWS (HN)</b>"
    if hn:
        for s in hn:
            msg += ('\n  (%d pts) <a href="%s">%s</a>'
                    % (s["score"], s["url"], html.escape(s["title"][:85])))
    else:
        msg += "\n  Quiet on HN today"

    msg += "\n\n<b>LATEST RESEARCH</b>"
    if papers:
        for p in papers:
            msg += '\n  <a href="%s">%s</a>' % (p["url"], p["title"])
    else:
        msg += "\n  No papers fetched"

    msg += "\n\n<b>MODELS</b>"
    if models:
        for m in models:
            badge = "\U0001f193" if m["tier"] == "FREE" else "\U0001f4b0"
            msg += "\n  [%s] <b>%s</b> (%s)" % (badge, m["name"], m["price"])
    else:
        msg += "\n  Model data unavailable"

    msg += "\n\n<b>GITHUB</b>"
    if repos:
        for r in repos:
            msg += ('\n  <a href="%s">%s</a> (%d %s)'
                    % (r["url"], r["name"], r.get("stars", 0), r.get("lang", "")))
            if r.get("desc"):
                msg += "\n  <i>%s</i>" % html.escape(r["desc"])
    else:
        msg += "\n  No repos fetched"

    msg += "\n\n<b>ACTIONS</b>"
    for i in insights:
        msg += "\n  %s" % i

    msg += "\n\n<b>SELF-IMPROVE</b>"
    for s in self_improve:
        msg += "\n  %s" % s

    msg += "\n\n<i>Distro Daily Brief</i>"
    return msg


def send(text):
    parts = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for i, part in enumerate(parts, 1):
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": part,
            "parse_mode": "HTML",
        }).encode()
        try:
            req = urllib.request.Request(
                "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_BOT_TOKEN,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=15)
            result = json.loads(resp.read().decode())
            if result.get("ok"):
                print("Part %d sent" % i)
            else:
                print("Part %d error: %s" % (i, result))
        except Exception as e:
            print("Part %d send error: %s" % (i, e))


if __name__ == "__main__":
    try:
        text = build()
        print("Built (%d chars)" % len(text))
        send(text)
    except Exception as e:
        print("Error: %s" % e)