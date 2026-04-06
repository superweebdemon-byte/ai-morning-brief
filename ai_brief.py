#!/usr/bin/env python3                                                                                                
"""                                                                                                                   
Distro Daily Brief - AI, Markets, Models, Repos, Insights                                                             
"""                                                                                                                   
import os, json, re, urllib.request, html, time                                                                       
from datetime import datetime, timedelta, timezone                                                                    
                                                                                                                      
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")                                                             
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")                                                                 
                                                                                                                      
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"            
                                                                                                                      
def fetch(url, timeout=15, retries=2):                                                                                
    for attempt in range(retries + 1):                                                                                
        try:                                                                                                          
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})                                     
            with urllib.request.urlopen(req, timeout=timeout) as resp:                                                
                return resp.read().decode("utf-8", errors="replace")                                                  
        except Exception:                                                                                             
            if attempt == retries: return None                                                                        
            time.sleep(1)                                                                                             
    return None                                                                                                       
                                                                                                                      
def clean_html(text):                                                                                                 
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', text.replace('\n', ' ').replace('&#x27;',                      
"'").replace('&quot;', '"').replace('&amp;', '&') )).strip()                                                          
                                                                                                                      
def get_market_indices():                                                                                             
    indices = {}                                                                                                      
    try:                                                                                                              
        resp = fetch("https://www.google.com/finance/", timeout=20)                                                   
        for n in re.finditer(r'class="pKBk1e">([^<]+)</div>', resp or ""):                                            
            name = n.group(1).replace("&amp;", "&")                                                                   
            if name in ("S&P 500", "Dow Jones", "Nasdaq", "VIX") and name not in indices:                             
                chunk = resp[n.start():n.start()+800]                                                                 
                price_m = re.search(r'class="YMlKec">([^<]+)</div>', chunk)                                           
                t7block = chunk.find('class="T7Akdb"')                                                                
                pct, pts = "?", "?"                                                                                   
                if t7block > 0:                                                                                       
                    block = chunk[t7block:t7block+500]                                                                
                    for s in re.findall(r"<span[^>]*>(.*?)</span>", block, re.DOTALL):                                
                        t = re.sub(r'<[^>]+>', '', s).strip().replace("\u202f", " ")                                  
                        if "%" in t: pct = t                                                                          
                        elif t and t[0] in "+-": pts = t                                                              
                indices[name] = {"price": price_m.group(1) if price_m else "?", "pct": pct, "pts": pts, "up": "+"     
in pct}                                                                                                               
    except Exception as e: return {"error": str(e)}                                                                   
    return indices if indices else {"error": "No data"}                                                               
                                                                                                                      
def get_ft_news():                                                                                                    
    headlines = []                                                                                                    
    for url in ["https://www.ft.com/markets?format=rss", "https://www.ft.com/companies?format=rss",                   
"https://www.ft.com/technology?format=rss"]:                                                                          
        try:                                                                                                          
            xml = fetch(url, timeout=20)                                                                              
            for entry in re.findall(r"<item>(.*?)</item>", xml or "", re.DOTALL)[:4]:                                 
                t = re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", entry)                                         
                l = re.search(r"<link>(.*?)</link>", entry)                                                           
                d = re.search(r"<description><!\[CDATA\[(.*?)\]\]></description>", entry)                             
                if t and l:                                                                                           
                    headlines.append({"t": html.unescape(t.group(1)).strip(), "u": l.group(1).strip(), "d":           
re.sub(r'<[^>]+>', '', html.unescape(d.group(1))).strip()[:120] if d else ""})                                        
        except: pass                                                                                                  
    return headlines                                                                                                  
                                                                                                                      
def get_hackernews():                                                                                                 
    stories = []                                                                                                      
    ids = json.loads(fetch("https://hacker-news.firebaseio.com/v0/topstories.json") or "[]")                          
    for item_id in ids[:40]:                                                                                          
        item = json.loads(fetch(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json") or "{}")                
        if item.get("score", 0) > 50:                                                                                 
            stories.append({"title": item.get("title", ""), "score": item.get("score", 0), "url":                     
f"https://news.ycombinator.com/item?id={item_id}", "kids": item.get("kids", []), "comments":                          
item.get("descendants", 0)})                                                                                          
    return stories[:8]                                                                                                
                                                                                                                      
def extract_wisdom(stories):                                                                                          
    insights = []                                                                                                     
    hot = [s for s in stories if s["comments"] > 40 and any(k in s["title"].lower() for k in ["agent", "llm", "ai",   
"model", "coding", "workflow"])]                                                                                      
    hot.sort(key=lambda s: -s["comments"])                                                                            
    for thread in hot[:2]:                                                                                            
        for kid_id in thread.get("kids", [])[:20]:                                                                    
            k = json.loads(fetch(f"https://hacker-news.firebaseio.com/v0/item/{kid_id}.json", timeout=8) or "{}")     
            txt = k.get("text", "")                                                                                   
            if len(txt) > 120 and any(w in txt.lower() for w in ["should", "need", "better", "problem", "issue",      
"annoying", "fix", "lack", "wish", "recommend"]):                                                                     
                clean = clean_html(txt)                                                                               
                insights.append(clean[:200])                                                                          
                if len(insights) >= 2: return insights                                                                
    return insights                                                                                                   
                                                                                                                      
def get_models():                                                                                                     
    models = []                                                                                                       
    data = json.loads(fetch("https://openrouter.ai/api/v1/models", timeout=20) or "{}")                               
    seen = set()                                                                                                      
    for m in data.get("data", []):                                                                                    
        mid = m.get("id", "")                                                                                         
        p = float(m.get("pricing", {}).get("prompt", "1"))                                                            
        c = float(m.get("pricing", {}).get("completion", "1"))                                                        
        avg = (p+c)/2                                                                                                 
        if mid not in seen and (avg < 0.10 or ":free" in mid.lower()):                                                
            seen.add(mid)                                                                                             
            models.append({"name": f"{mid.split('/')[0]}/{mid.split('/')[-1]}", "tier": "FREE" if avg==0 or ":free"   
in mid.lower() else "CHEAP", "price": "FREE" if avg==0 else f"~${avg*1e6:.2f}/M"})                                    
    return sorted(models, key=lambda x: 0 if x["tier"]=="FREE" else 1)[:10]                                           
                                                                                                                      
def get_github():                                                                                                     
    repos = []                                                                                                        
    data =                                                                                                            
json.loads(fetch("https://api.github.com/search/repositories?q=stars:>500+created:>2025-01-01&sort=stars&per_page=8   
") or "{}")                                                                                                           
    for i in data.get("items", []):                                                                                   
        repos.append({"name": i["full_name"], "url": i["html_url"], "desc": (i.get("description") or "")[:100],       
"stars": i["stargazers_count"], "lang": i.get("language") or "N/A"})                                                  
    return repos[:6]                                                                                                  
                                                                                                                      
def build():                                                                                                          
    status = {}                                                                                                       
    print("Fetching data...")                                                                                         
    indices = get_market_indices(); status["Markets"] = "OK" if "error" not in indices else "FAIL"                    
    news = get_ft_news(); status["News"] = "OK" if news else "FAIL"                                                   
    hn = get_hackernews(); status["HN"] = "OK" if hn else "FAIL"                                                      
    wisdom = extract_wisdom(hn)                                                                                       
    papers = [e for e in re.findall(r'<title>(.*?)</title>.*?<link>(.*?)</link>',                                     
fetch("https://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&max_results=5", timeout=20)     
or "", re.S) if 'arxiv' in e[1]]                                                                                      
    models = get_models(); status["Models"] = "OK" if models else "FAIL"                                              
    repos = get_github(); status["Repos"] = "OK" if repos else "FAIL"                                                 
                                                                                                                      
    all_text = " ".join(n.get("t","").lower() for n in news) + " " + " ".join(r.get("desc","").lower() for r in       
repos)                                                                                                                
    insights = []                                                                                                     
    if "agent" in all_text: insights.append("Agentic AI trending - Phase 2 readiness check")                          
    if "security" in all_text: insights.append("AI security focus - run hardening audit")                             
    if len(models) >= 3: insights.append(f"{len([m for m in models if m['tier']=='FREE'])} free models available -    
check list")                                                                                                          
    if not insights: insights.append("Steady day - focus on deliverables")                                            
                                                                                                                      
    now = datetime.now(timezone.utc) - timedelta(hours=5)                                                             
    msg = f"<b>Distro Daily Brief</b>\n<i>{now.strftime('%A, %b %d')} | 12:00 PM ET</i>"                              
    msg += "\n\n<b>MARKETS</b>"                                                                                       
    if "error" not in indices:                                                                                        
        for name in ["S&P 500", "Dow Jones", "Nasdaq", "VIX"]:                                                        
            d = indices.get(name)                                                                                     
            if d: msg += f"\n  {'🟢' if d['up'] else '🔴'} <b>{name}</b>: {d['price']} ({d['pts']}, {d['pct']})"      
                                                                                                                      
    msg += "\n\n<b>FINANCIAL NEWS (FT)</b>"                                                                           
    for n in news[:6]:                                                                                                
        msg += f'\n  <a href="{n["u"]}">{n["t"]}</a>'                                                                 
        if n["d"]: msg += f"\n  <i>{n['d']}</i>"                                                                      
                                                                                                                      
    msg += "\n\n<b>AI NEWS (HN)</b>"                                                                                  
    for s in hn: msg += f'\n  ({s["score"]}pts) <a href="{s["url"]}">{s["title"][:90]}</a>'                           
                                                                                                                      
    msg += "\n\n<b>OPENROUTER MODELS</b>"                                                                             
    for m in models: msg += f"\n  [{'🆓' if m['tier']=='FREE' else '💰'}] <b>{m['name']}</b> ({m['price']})"          
                                                                                                                      
    msg += "\n\n<b>TRENDING GITHUB</b>"                                                                               
    for r in repos:                                                                                                   
        msg += f'\n  <a href="{r["url"]}">{r["name"]}</a> ({r["stars"]} {r["lang"]})'                                 
        if r["desc"]: msg += f"\n  <i>{r['desc']}</i>"                                                                
                                                                                                                      
    msg += "\n\n<b>ACTION ITEMS</b>"                                                                                  
    for i in insights: msg += f"\n  {i}"                                                                              
                                                                                                                      
    msg += "\n\n<b>SELF-IMPROVEMENT</b>"                                                                              
    if wisdom: msg += f"\n  Community: {wisdom[0]}"                                                                   
    else: msg += "\n  Quiet discussions today."                                                                       
                                                                                                                      
    broken = [k for k,v in status.items() if v != "OK"]                                                               
    if broken: msg += f"\n  Fix sections: {', '.join(broken)}"                                                        
                                                                                                                      
    msg += "\n\n<i>Distro Daily Brief</i>"                                                                            
    return msg                                                                                                        
                                                                                                                      
if __name__ == "__main__":                                                                                            
    try:                                                                                                              
        text = build()                                                                                                
        print(f"Built ({len(text)} chars)")                                                                           
        for i in range(0, len(text), 4000):                                                                           
            chunk = text[i:i+4000]                                                                                    
            payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"}).encode()         
            req = urllib.request.Request(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",             
data=payload, headers={"Content-Type": "application/json"})                                                           
            resp = urllib.request.urlopen(req, timeout=10)                                                            
            print(f"Part sent: {json.loads(resp.read()).get('ok')}")                                                  
    except Exception as e:                                                                                            
        print(f"Error: {e}")                                                                                          
```                                                         