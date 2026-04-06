#!/usr/bin/env python3
"""Distro Daily Brief -> Plain Text (Bulletproof)"""
import os, json, re, urllib.request, html, time
from datetime import datetime, timedelta, timezone

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"

def fetch(url, timeout=15):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None

def clean(text):
    return re.sub(r'\s+', ' ', text.replace('\n', ' ')).strip()

def get_markets():
    d = {}
    try:
        r = fetch("https://www.google.com/finance/", 20) or ""
        for m in re.finditer(r'class="pKBk1e">([^<]+)</div>', r):
            name = m.group(1).replace("&amp;", "&")
            if name in ["S&P 500", "Dow Jones", "Nasdaq", "VIX"] and name not in d:
                c = r[m.start():m.start()+800]
                pm = re.search(r'class="YMlKec">([^<]+)</div>', c)
                tb = c.find('class="T7Akdb"')
                pct, pts = "?", "?"
                if tb > 0:
                    block = c[tb:tb+600]
                    for s in re.findall(r"<span[^>]*>(.*?)</span>", block, re.S):
                        val = re.sub(r'<[^>]+>', '', s).strip().replace("\u202f", " ")
                        if "%" in val: pct = val
                        elif val and val[0] in "+-": pts = val
                d[name] = {"p": pm.group(1) if pm else "?", "pct": pct, "pts": pts}
    except: pass
    return d

def get_ft():
    res = []
    urls = ["https://www.ft.com/markets?format=rss", "https://www.ft.com/companies?format=rss"]
    for u in urls:
        r = fetch(u, 20)
        if r:
            for e in re.findall(r"<item>(.*?)</item>", r, re.S)[:4]:
                t = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", e)
                l = re.search(r"<link>(.*?)</link>", e)
                if t and l:
                    res.append({"t": html.unescape(t.group(1)), "u": l.group(1).strip()})
    return res

def get_hn():
    ids = json.loads(fetch("https://hacker-news.firebaseio.com/v0/topstories.json") or "[]")
    res = []
    for i in ids[:40]:
        item = json.loads(fetch(f"https://hacker-news.firebaseio.com/v0/item/{i}.json") or "{}")
        if item.get("score", 0) > 50:
            res.append({"title": item.get("title", ""), "score": item.get("score", 0),
                        "url": "https://news.ycombinator.com/item?id=" + str(i),
                        "kids": item.get("kids", []), "c": item.get("descendants", 0)})
    return res[:8]

def get_wisdom(stories):
    hot = [s for s in stories if s["c"] > 40 and any(k in s["title"].lower() for k in ["agent", "ai", "llm", "model", "coding"])]
    hot.sort(key=lambda s: -s["c"])
    res = []
    for th in hot[:2]:
        for kid in th.get("kids", [])[:15]:
            k = json.loads(fetch(f"https://hacker-news.firebaseio.com/v0/item/{kid}.json") or "{}")
            txt = k.get("text", "")
            if txt and len(txt) > 100 and any(w in txt.lower() for w in ["should", "need", "better", "problem", "lack"]):
                res.append(clean(txt)[:150])
                if len(res) == 2: return res
    return res

def get_models():
    res = []
    d = json.loads(fetch("https://openrouter.ai/api/v1/models", timeout=20) or "{}")
    seen = set()
    for m in d.get("data", []):
        mid = m.get("id", "")
        if mid in seen: continue
        seen.add(mid)
        p = float(m.get("pricing", {}).get("prompt", 1))
        c = float(m.get("pricing", {}).get("completion", 1))
        avg = (p+c)/2
        if avg < 0.10 or ":free" in mid.lower():
            tier = "FREE" if avg == 0 else "CHEAP"
            parts = mid.split("/")
            name = f"{parts[0]}/{parts[-1]}"
            label = "FREE" if avg == 0 else f"~${avg*1e6:.1f}/1M"
            res.append({"n": name, "p": label})
    return res[:8]

def get_github():
    res = []
    url = "https://api.github.com/search/repositories?q=stars:>500+created:>2025-01-01&sort=stars&per_page=6"
    d = json.loads(fetch(url) or "{}")
    for i in d.get("items", []):
        desc = (i.get("description") or "")[:80]
        res.append({"n": i["full_name"], "s": i["stargazers_count"], "l": i.get("language") or "N/A", "d": desc})
    return res

def main():
    markets = get_markets()
    ft = get_ft()
    hn = get_hn()
    wisdom = get_wisdom(hn)
    models = get_models()
    repos = get_github()
    
    text = " ".join(n.get("t","").lower() for n in ft) + " " + " ".join(r.get("n","").lower() for r in repos)
    actions = []
    if "agent" in text: actions.append("Agentic AI trending - Phase 2 check")
    if "security" in text: actions.append("Security focus - harden setup")
    if not actions: actions.append("Steady day - focus on deliverables")

    now = datetime.now(timezone.utc) - timedelta(hours=5)
    msg = f"DISTRO DAILY BRIEF | {now.strftime('%A, %b %d')} | 12:00 PM ET\n\n"
    
    msg += "MARKETS\n"
    for name in ["S&P 500", "Dow Jones", "Nasdaq", "VIX"]:
        m = markets.get(name)
        if m:
            msg += f"  {name}: {m['p']} ({m['pts']}, {m['pct']})\n"
    
    msg += "\nFINANCIAL NEWS\n"
    for n in ft[:4]:
        msg += f"  {n['t']}\n  {n['u']}\n\n"
        
    msg += "AI NEWS (HN)\n"
    for s in hn[:5]:
        msg += f"  [{s['score']}pts] {s['title']}\n  {s['url']}\n\n"
        
    msg += "MODELS\n"
    for m in models: msg += f"  {m['n']} ({m['p']})\n"
        
    msg += "\nGITHUB\n"
    for r in repos:
        msg += f"  {r['n']} ({r['s']})\n"
        if r["d"]: msg += f"    {r['d']}\n"
        
    msg += "\nACTIONS\n"
    for a in actions: msg += f"  - {a}\n"
    
    msg += "\nSELF-IMPROVE\n"
    if wisdom: msg += f"  Community: {wisdom[0]}\n"
    else: msg += "  Quiet today.\n"
    msg += "\n-Distro"

    print(f"Built ({len(msg)} chars)")
    
    # Send as plain text (no parse_mode) to prevent 400 errors
    for i in range(0, len(msg), 4000):
        chunk = html.unescape(msg[i:i+4000])
        data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": chunk}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=data, headers={"Content-Type":"application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        print(f"Sent OK")

if __name__ == "__main__":
    main()