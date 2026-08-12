from __future__ import annotations
import hashlib, html as html_lib, json, os, re, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

BASE = Path(__file__).resolve().parent
DATA_PATH = BASE / "data.json"
STATE_PATH = BASE / "state.json"
CONFIG_PATH = BASE / "config.json"
OVERRIDES_PATH = BASE / "manual_overrides.json"
USER_AGENT = "CompetitorMonitor/5.0 (+GitHub Actions)"

CATEGORY_LABELS = {"remittance":"Remittance","musaned":"Musaned","sadad":"SADAD","card":"Card","engagement":"Engagement","other":"Other"}
COUNTRIES = {
    "India":["india","indian","الهند","هندي"],"Pakistan":["pakistan","pakistani","باكستان"],"Philippines":["philippines","filipino","الفلبين"],
    "Bangladesh":["bangladesh","bangladeshi","بنغلاديش","بنجلا"],"Indonesia":["indonesia","indonesian","اندونيسيا","إندونيسيا"],"Nepal":["nepal","nepali","نيبال"],
    "China":["china","chinese","الصين"],"Egypt":["egypt","egyptian","مصر"],"Sri Lanka":["sri lanka","srilanka","سريلانكا"],"Jordan":["jordan","الأردن","الاردن"],"Morocco":["morocco","المغرب"]
}
MECHANICS = {
    "discount":["discount","% off","خصم"],"cashback":["cashback","cash back","كاش باك","استرداد نقدي"],"fee_waiver":["zero fee","0 fee","fee-free","no fee","without fees","بدون رسوم","صفر رسوم"],
    "prize_draw":["win","winner","draw","prize","اربح","فائز","سحب","جائزة"],"reward":["reward","points","miles","مكافأة","نقاط","أميال"],"preferred_rate":["preferred rate","special rate","exchange rate","fx rate","سعر صرف","سعر تفضيلي"]
}

WINNER_ANNOUNCEMENT_WORDS=["winner","winners","congratulations","congrats","winner announcement","فائز","فائزة","فائزين","فائزينا","الفائز","الفائزة","الفائزين","مبروك","نبارك","تهانينا"]
SOCIAL_HOSTS=("instagram.com","facebook.com","m.facebook.com","x.com","twitter.com","tiktok.com")

def is_winner_announcement(item):
    text=f"{item.get('title','')} {item.get('snippet','')}".casefold()
    return item.get("post_role")=="winner_announcement" or any(w.casefold() in text for w in WINNER_ANNOUNCEMENT_WORDS)

def social_url(value):
    if not value:return False
    try:
        host=urlsplit(str(value)).netloc.casefold().removeprefix("www.")
        return any(host==h or host.endswith("."+h) for h in SOCIAL_HOSTS)
    except Exception:return False

def generic_offers_url(value, config, competitor_id):
    if not value:return True
    try:
        ident=detail_url_identity(value) if "detail_url_identity" in globals() else str(value).strip().casefold().rstrip("/")
        for c in config.get("competitors",[]):
            if c.get("id")!=competitor_id:continue
            vals=[c.get("website"),c.get("offers_url")]+[x.get("url") for x in c.get("website_sources",[]) if x.get("url")]
            for v in vals:
                if not v:continue
                other=detail_url_identity(v) if "detail_url_identity" in globals() else str(v).strip().casefold().rstrip("/")
                if ident==other:return True
        return False
    except Exception:return False

def accepted_direct_source(item, config):
    # Specific official social post is accepted even when no dedicated campaign page exists.
    if any(social_url(v) for v in (item.get("social_links") or {}).values()):return True
    for key in ("official_campaign_page_url","primary_official_source_url","link"):
        value=item.get(key)
        if not value:continue
        if social_url(value):return True
        if str(value).startswith(("http://","https://")) and not generic_offers_url(value,config,item.get("competitor_id")):
            return True
    return False

def enforce_record_integrity(data, config):
    """Social posts cannot create counted campaigns; unsourced campaigns are quarantined."""
    changed=0
    for item in data.get("items",[]):
        if item.get("source_type")=="social" and item.get("content_type") in {"campaign","merchant_offer"}:
            suggested=item.get("content_type")
            if item.get("campaign_id"):
                item["content_type"]="social_post"
                item["review_required"]=False
                item["review_reasons"]=[r for r in (item.get("review_reasons") or []) if r not in {"social_post_cannot_create_campaign","winner_announcement_unlinked"}]
            else:
                item["content_type"]="review"
                item["suggested_record_type"]=suggested
                item["review_required"]=True
                item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["social_post_cannot_create_campaign"]))
                if is_winner_announcement(item):
                    item["review_reasons"]=list(dict.fromkeys(item["review_reasons"]+["winner_announcement_unlinked"]))
            changed+=1
        if item.get("content_type")=="campaign" and not accepted_direct_source(item,config):
            item["content_type"]="review"
            item["suggested_record_type"]="campaign"
            item["review_required"]=True
            item["current_status"]="Needs Review"
            item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["missing_direct_official_source"]))
            changed+=1
    data["record_integrity"]={"quarantined_or_demoted":changed,"at":iso(now())}
    return changed


def load(path: Path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def save(path: Path, obj): path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
def now(): return datetime.now(timezone.utc)
def iso(d): return d.astimezone(timezone.utc).isoformat() if d else None

def dt(v):
    if not v: return None
    try:
        d=dateparser.parse(str(v))
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception: return None

def clean(v, limit=1000):
    s=re.sub(r"\s+"," ",str(v or "")).strip()
    return s[:limit]

def hash_text(*parts): return hashlib.sha256("|".join(clean(p,5000) for p in parts).encode()).hexdigest()[:24]

def direct_url(item): return item.get("official_campaign_page_url") or item.get("primary_official_source_url") or item.get("link")

def status_for(item, at=None):
    at=at or now(); start=dt(item.get("start_date")); end=dt(item.get("end_date"))
    if start and start.date()>at.date(): return "Upcoming", True
    if end:
        days=(end.date()-at.date()).days
        if days<0: return "Expired", False
        if days<=7: return "Expiring ≤7 Days", True
        if days<=30: return "Expiring 8–30 Days", True
        return "Active", True
    return "End Date Not Stated", True

def mechanics(text):
    s=text.casefold(); return [k for k, words in MECHANICS.items() if any(w.casefold() in s for w in words)]

def corridors(text):
    s=text.casefold(); return [country for country, words in COUNTRIES.items() if any(w.casefold() in s for w in words)]

def offer_values(text):
    patterns=[r"(?:SAR|SR|ريال)\s*[\d,]+(?:\.\d+)?",r"[\d,]+(?:\.\d+)?\s*(?:SAR|SR|ريال)",r"\b\d+(?:\.\d+)?\s*%",r"(?:up to|حتى)\s+(?:SAR\s*)?[\d,]+(?:\.\d+)?(?:\s*%|\s*SAR|\s*ريال)?"]
    out=[]
    for p in patterns:
        out += [clean(x,80) for x in re.findall(p,text,flags=re.I)]
    return list(dict.fromkeys(out))[:10]

def jsonld_objects(soup):
    out=[]
    for node in soup.select('script[type="application/ld+json"]'):
        try:
            obj=json.loads(node.get_text(" ",strip=True))
            stack=obj if isinstance(obj,list) else [obj]
            while stack:
                x=stack.pop()
                if isinstance(x,dict):
                    out.append(x); stack.extend(v for v in x.values() if isinstance(v,(dict,list)))
                elif isinstance(x,list): stack.extend(x)
        except Exception: pass
    return out

def first_date(values):
    for v in values:
        d=dt(v)
        if d: return iso(d.replace(hour=0,minute=0,second=0,microsecond=0))
    return None

def extract_dates_from_text(text):
    # Conservative patterns: ranges/explicit validity only. Never infer from first detection.
    months="January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    date_pat=rf"(?:\d{{1,2}}\s+(?:{months})\s+20\d{{2}}|(?:{months})\s+\d{{1,2}},?\s+20\d{{2}}|20\d{{2}}[-/]\d{{1,2}}[-/]\d{{1,2}}|\d{{1,2}}[-/]\d{{1,2}}[-/]20\d{{2}})"
    start=end=None; evidence=None
    range_patterns=[rf"(?:valid|available|runs?|campaign)\s+(?:from\s+)?({date_pat})\s+(?:to|until|through|–|-)\s+({date_pat})",rf"(?:من)\s+({date_pat})\s+(?:إلى|الى|حتى)\s+({date_pat})"]
    for p in range_patterns:
        m=re.search(p,text,re.I)
        if m:
            start,end=first_date([m.group(1)]),first_date([m.group(2)]); evidence=clean(m.group(0),500); break
    if not end:
        for p in [rf"(?:valid until|valid through|ends? on|expires? on)\s+({date_pat})",rf"(?:ساري حتى|ينتهي في|ينتهي بتاريخ|حتى)\s+({date_pat})"]:
            m=re.search(p,text,re.I)
            if m: end=first_date([m.group(1)]); evidence=clean(m.group(0),500); break
    return start,end,evidence

def extract_page(html,url):
    soup=BeautifulSoup(html,"html.parser")
    title=clean((soup.find("meta",property="og:title") or {}).get("content") if soup.find("meta",property="og:title") else "",300) or clean(soup.title.get_text(" ",strip=True) if soup.title else "",300)
    desc_node=soup.find("meta",attrs={"name":"description"}) or soup.find("meta",property="og:description")
    summary=clean(desc_node.get("content") if desc_node else "",1000)
    text=clean(soup.get_text(" ",strip=True),20000)
    pub=[]; starts=[]; ends=[]
    for obj in jsonld_objects(soup):
        for k in ["datePublished","dateCreated","uploadDate"]:
            if obj.get(k): pub.append(obj[k])
        for k in ["startDate","validFrom"]:
            if obj.get(k): starts.append(obj[k])
        for k in ["endDate","validThrough","expiryDate"]:
            if obj.get(k): ends.append(obj[k])
    for attr, target in [("article:published_time",pub),("offer:valid_from",starts),("offer:valid_through",ends)]:
        n=soup.find("meta",property=attr)
        if n and n.get("content"): target.append(n["content"])
    text_start,text_end,evidence=extract_dates_from_text(text)
    image=None
    n=soup.find("meta",property="og:image")
    if n and n.get("content"): image=urljoin(url,n["content"])
    return {
        "title":title,"summary":summary,"published_at":first_date(pub),"start_date":first_date(starts) or text_start,"end_date":first_date(ends) or text_end,
        "mechanic_tags":mechanics(text),"corridors":corridors(text),"offer_values":offer_values(text),"image":image,
        "evidence_snapshot": evidence or clean(text[:1200],1200),"content_hash":hash_text(title,summary,text[:10000])
    }

def manual_patch(overrides,item_id): return (overrides.get("items") or {}).get(item_id,{})

def append_change(item,typ,details=None):
    h=item.setdefault("change_history",[])
    h.append({"at":iso(now()),"type":typ,"details":details or {}})
    item["change_history"]=h[-30:]

def add_manual_new_items(data, overrides):
    existing={i.get("id") for i in data.get("items",[])}
    for row in overrides.get("new_items",[]) or []:
        if not row.get("id") or row["id"] in existing: continue
        item={
            "id":row["id"],"record_id":None,"competitor_id":row.get("competitor_id"),"source_key":f"manual:{row.get('competitor_id')}","source_type":"manual","platform":"website",
            "content_type":row.get("content_type","campaign"),"campaign_category":row.get("campaign_category","other"),"primary_category":row.get("campaign_category","other"),"categories":[row.get("campaign_category","other")],
            "title":row.get("title") or "New campaign pending source analysis","snippet":row.get("summary","") ,"summary":row.get("summary",""),"link":row.get("official_campaign_page_url") or row.get("primary_official_source_url"),
            "official_campaign_page_url":row.get("official_campaign_page_url"),"primary_official_source_url":row.get("primary_official_source_url") or row.get("official_campaign_page_url"),"social_links":row.get("social_links",{}),
            "published_at":row.get("published_at"),"start_date":row.get("start_date"),"end_date":row.get("end_date"),"current_status":"Needs Review","active":row.get("active",True),"operation_type":row.get("operation_type","") ,"mechanic":row.get("mechanic","") ,"eligibility":row.get("eligibility","") ,"terms_note":row.get("terms_note",""),
            "verified":False,"review_required":True,"review_reasons":["manual_new_campaign_pending_verification"],"manual_override":True,"first_seen":row.get("created_at") or iso(now()),"last_changed":row.get("created_at") or iso(now()),"change_history":[]
        }
        append_change(item,"manual_created")
        data.setdefault("items",[]).append(item); existing.add(item["id"])

def verify_details(data,state,config,overrides):
    cache=state.setdefault("detail_cache",{})
    interval=float(config.get("settings",{}).get("detail_verification_interval_hours",6)); timeout=int(config.get("settings",{}).get("request_timeout_seconds",18)); max_checks=int(config.get("settings",{}).get("max_detail_checks_per_run",16))
    current=now(); checks=0; new_status=[]; skip=os.environ.get("CM_SKIP_NETWORK")=="1"
    session=requests.Session(); session.headers.update({"User-Agent":USER_AGENT,"Accept-Language":"ar,en;q=0.9"})
    for item in data.get("items",[]):
        if item.get("content_type") not in {"campaign","merchant_offer"}: continue
        if item.get("active") is False and item.get("source_type")!="manual": continue
        url=direct_url(item)
        if not url or not str(url).startswith("http"): continue
        cached=cache.get(item["id"],{}); last=dt(cached.get("checked_at")); due=not last or current-last>=timedelta(hours=interval)
        if due and checks<max_checks and not skip:
            checks+=1; st={"source_key":f"detail:{item['id']}","competitor_id":item.get("competitor_id"),"source_type":"campaign_detail","platform":"website","url":url,"checked_at":iso(current),"success":False,"item_count":0,"error":None}
            try:
                r=session.get(url,timeout=timeout); r.raise_for_status(); ex=extract_page(r.text,url)
                old_hash=(cached.get("extracted") or {}).get("content_hash")
                cached={"checked_at":iso(current),"last_success_at":iso(current),"success":True,"url":url,"extracted":ex,"error":None}; cache[item["id"]]=cached
                st.update(success=True,item_count=1,last_success_at=iso(current))
                if old_hash and old_hash!=ex.get("content_hash"): append_change(item,"source_content_changed")
            except Exception as exc:
                cached={**cached,"checked_at":iso(current),"success":False,"url":url,"error":clean(f"{type(exc).__name__}: {exc}",500)}; cache[item["id"]]=cached
                st["error"]=cached["error"]; st["last_success_at"]=cached.get("last_success_at")
            new_status.append(st)
        ex=cached.get("extracted") or {}
        if not ex: continue
        manual=manual_patch(overrides,item["id"]); conflicts=[]
        for field in ["published_at","start_date","end_date"]:
            src=ex.get(field); old=item.get(field)
            if src and old and dt(src) and dt(old) and abs((dt(src)-dt(old)).total_seconds())>36*3600: conflicts.append({"field":field,"current":old,"source":src})
            if src and field not in manual and src!=old:
                item[field]=src; append_change(item,f"{field}_updated",{"from":old,"to":src})
        if ex.get("title") and not item.get("title") and "title" not in manual: item["title"]=ex["title"]
        if ex.get("summary") and not (item.get("summary") or item.get("snippet")) and "summary" not in manual: item["summary"]=item["snippet"]=ex["summary"]
        item["mechanic_tags"]=list(dict.fromkeys((item.get("mechanic_tags") or [])+(ex.get("mechanic_tags") or [])))
        item["corridors"]=ex.get("corridors") or item.get("corridors") or []
        item["offer_values"]=ex.get("offer_values") or item.get("offer_values") or []
        item["evidence_snapshot"]=ex.get("evidence_snapshot")
        if ex.get("image") and not item.get("media"): item["media"]={"type":"image","url":ex["image"],"thumbnail_url":ex["image"]}
        item["source_verification"]={"status":"verified" if cached.get("success") else "failed","checked_at":cached.get("checked_at"),"source_url":url,"source_changed":bool(conflicts),"conflicts":conflicts,"error":cached.get("error")}
        if cached.get("success"):
            item["last_live_verified_at"]=cached.get("checked_at"); item["last_reviewed"]=cached.get("checked_at")
        st,active=status_for(item,current)
        if "current_status" not in manual: item["current_status"]=st
        if "active" not in manual: item["active"]=active
        if conflicts:
            item["review_required"]=True; item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["official_source_conflict"]))
    if new_status:
        old={s.get("source_key"):s for s in data.get("source_status",[])}
        for s in new_status: old[s["source_key"]]=s
        data["source_status"]=sorted(old.values(),key=lambda x:x.get("source_key",""))

def tokenize(text):
    return {x for x in re.findall(r"[\w%]+",clean(text,5000).casefold()) if len(x)>2}

def heuristic_match(post,campaigns):
    pt=tokenize(f"{post.get('title','')} {post.get('snippet','')}")
    best=(0,None)
    for c in campaigns:
        # Exact known social URL is strongest.
        if post.get("link") and post.get("link") in (c.get("social_links") or {}).values(): return c["id"],"exact_url"
        ct=tokenize(f"{c.get('title','')} {c.get('summary','')} {c.get('mechanic','')} {c.get('terms_note','')}")
        union=len(pt|ct) or 1; lexical=len(pt&ct)/union
        cat_bonus=.18 if post.get("campaign_category") and post.get("campaign_category")==c.get("campaign_category") else 0
        corr_bonus=.18 if set(post.get("corridors") or []) & set(c.get("corridors") or []) else 0
        value=lexical+cat_bonus+corr_bonus
        if value>best[0]: best=(value,c["id"])
    if best[0]>=.36:return best[1],"heuristic"
    if best[0]>=.20:return best[1],"suggested"
    return None,None

def openai_client():
    if not os.environ.get("OPENAI_API_KEY"): return None
    try:
        from openai import OpenAI
        return OpenAI()
    except Exception as exc:
        print(f"[OpenAI unavailable] {exc}"); return None

def usage_numbers(resp):
    u=getattr(resp,"usage",None)
    return int(getattr(u,"input_tokens",0) or 0), int(getattr(u,"output_tokens",0) or 0)

def add_usage(state,kind,model,inp,out,config):
    u=state.setdefault("ai_usage",{"calls":0,"input_tokens":0,"output_tokens":0,"estimated_usd":0.0,"by_type":{}})
    u["calls"]+=1;u["input_tokens"]+=inp;u["output_tokens"]+=out
    prices=config.get("ai",{}).get("pricing",{}).get(model,{})
    cost=inp/1_000_000*float(prices.get("input",0))+out/1_000_000*float(prices.get("output",0));u["estimated_usd"]=round(float(u.get("estimated_usd",0))+cost,6)
    b=u["by_type"].setdefault(kind,{"calls":0,"input_tokens":0,"output_tokens":0,"estimated_usd":0.0});b["calls"]+=1;b["input_tokens"]+=inp;b["output_tokens"]+=out;b["estimated_usd"]=round(float(b.get("estimated_usd",0))+cost,6)

def ai_classify(posts,campaigns,state,config):
    if not posts or not config.get("ai",{}).get("classification_enabled",True): return {}
    client=openai_client()
    if not client:return {}
    model=config.get("ai",{}).get("classification_model","gpt-5.6-terra")
    allowed_campaigns=[{"id":c["id"],"competitor_id":c.get("competitor_id"),"title":c.get("title"),"category":c.get("campaign_category"),"mechanic":c.get("mechanic"),"corridors":c.get("corridors",[])} for c in campaigns if c.get("active") is not False]
    rows=[{"id":p["id"],"competitor_id":p.get("competitor_id"),"title":p.get("title"),"text":p.get("snippet"),"platform":p.get("platform"),"published_at":p.get("published_at")} for p in posts]
    categories=["remittance","musaned","sadad","card","engagement","merchant","other"]
    schema={"type":"object","additionalProperties":False,"properties":{"items":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{"id":{"type":"string"},"decision":{"type":"string","enum":["link","review","standalone"]},"record_type":{"type":"string","enum":["campaign","merchant_offer","social_post","awareness","review"]},"category":{"type":"string","enum":categories},"matched_campaign_id":{"type":["string","null"]}},"required":["id","decision","record_type","category","matched_campaign_id"]}}},"required":["items"]}
    instructions="""Classify official competitor social posts for a Saudi fintech intelligence monitor. A social post NEVER creates a counted campaign by itself. Winner announcements, congratulations, reminders, winner/result posts, and follow-up posts must be linked to an existing campaign when supported; otherwise use decision=review. NEVER link across competitors: matched_campaign_id must belong to the same competitor_id as the post/item. Link to an existing campaign only when the meaning, product/corridor and mechanic support the match. A product-awareness post without a concrete campaign mechanic is awareness/social content, not a campaign. Merchant partner discounts are merchant_offer. If uncertain use decision=review. Return only the schema. Do not invent dates, values or campaigns."""
    try:
        r=client.responses.create(model=model,reasoning={"effort":config.get("ai",{}).get("classification_reasoning","low")},text={"format":{"type":"json_schema","name":"post_classification","schema":schema,"strict":True}},input=[{"role":"system","content":instructions},{"role":"user","content":json.dumps({"campaigns":allowed_campaigns,"posts":rows},ensure_ascii=False)}])
        result=json.loads(r.output_text); inp,out=usage_numbers(r); add_usage(state,"classification",model,inp,out,config); return {x["id"]:x for x in result.get("items",[])}
    except Exception as exc:
        print(f"[AI classification] {type(exc).__name__}: {exc}");return {}

def enrich_social(data,state,config,overrides):
    items=data.get("items",[]); campaigns=[i for i in items if i.get("content_type") in {"campaign","merchant_offer"}]; byid={i["id"]:i for i in campaigns}
    for post in [i for i in items if i.get("source_type")=="social"]:
        post["corridors"]=corridors(f"{post.get('title','')} {post.get('snippet','')}")
        patch=manual_patch(overrides,post["id"]); manual_link=patch.get("linked_campaign_id")
        if manual_link in byid: post["campaign_id"]=manual_link;post["match_method"]="manual";post["review_required"]=False;continue
        if post.get("campaign_id") in byid:continue
        cand=[c for c in campaigns if c.get("competitor_id")==post.get("competitor_id") and c.get("active") is not False]
        match,method=heuristic_match(post,cand)
        if method in {"exact_url","heuristic"}:post["campaign_id"]=match;post["match_method"]=method;post["review_required"]=False
        elif method=="suggested":post["suggested_campaign_id"]=match;post["review_required"]=True;post["review_reasons"]=list(dict.fromkeys((post.get("review_reasons") or [])+["social_campaign_match_uncertain"]))
    cache=state.setdefault("ai_classification_cache",{}); maxn=int(config.get("ai",{}).get("classification_max_items_per_run",20)); recent=now()-timedelta(days=int(config.get("ai",{}).get("classification_recent_days",14))); ambiguous=[]
    for p in [i for i in items if i.get("source_type")=="social" and not i.get("campaign_id")]:
        d=dt(p.get("published_at")) or dt(p.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc)
        if d<recent:continue
        key=hash_text("classifier-v2",p.get("title"),p.get("snippet"),p.get("link")); cached=cache.get(p["id"],{})
        if cached.get("content_key")==key and cached.get("decision"):
            dec=dict(cached["decision"])
            cid=dec.get("campaign_id") or dec.get("matched_campaign_id")
            if cid in byid and byid[cid].get("competitor_id")!=p.get("competitor_id"):
                dec.pop("campaign_id",None);dec["matched_campaign_id"]=None;dec["content_type"]="review";dec["review_required"]=True
                dec["review_reasons"]=list(dict.fromkeys((dec.get("review_reasons") or [])+["invalid_cross_competitor_match"]))
            if dec.get("content_type") in {"campaign","merchant_offer"}:
                dec["suggested_record_type"]=dec.get("content_type");dec["content_type"]="review";dec["review_required"]=True
                dec["review_reasons"]=list(dict.fromkeys((dec.get("review_reasons") or [])+["social_post_cannot_create_campaign"]))
            p.update(dec);continue
        ambiguous.append(p)
    decisions=ai_classify(ambiguous[:maxn],campaigns,state,config)
    for p in ambiguous[:maxn]:
        d=decisions.get(p["id"])
        if not d:continue
        patch={"ai_classification":d,"campaign_category":d["category"],"primary_category":d["category"],"categories":[d["category"]]};match=d.get("matched_campaign_id")
        if match in byid and byid[match].get("competitor_id")!=p.get("competitor_id"):
            match=None; d={**d,"decision":"review","matched_campaign_id":None}; patch["ai_classification"]=d
        if d["decision"]=="link" and match in byid:
            # The campaign remains the authoritative record; the social item remains a post.
            patch.update(content_type="social_post",campaign_id=match,match_method="ai",review_required=False,review_reasons=[])
        elif d["record_type"] in {"campaign","merchant_offer"}:
            # Never promote a social post into a counted campaign automatically.
            patch.update(content_type="review",suggested_record_type=d["record_type"],review_required=True,review_reasons=list(dict.fromkeys((p.get("review_reasons") or [])+["social_post_cannot_create_campaign"])),suggested_campaign_id=match if match in byid else p.get("suggested_campaign_id"))
        elif d["decision"]=="review":
            patch.update(content_type="review",review_required=True,review_reasons=list(dict.fromkeys((p.get("review_reasons") or [])+["ai_needs_review"])),suggested_campaign_id=match if match in byid else p.get("suggested_campaign_id"))
        else:
            patch.update(content_type=d["record_type"] if d["record_type"] in {"awareness","social_post"} else "social_post",review_required=False)
        if is_winner_announcement(p) and not patch.get("campaign_id"):
            patch.update(content_type="review",review_required=True,review_reasons=list(dict.fromkeys((patch.get("review_reasons") or [])+["winner_announcement_unlinked"])))
        p.update(patch);cache[p["id"]]={"content_key":hash_text("classifier-v2",p.get("title"),p.get("snippet"),p.get("link")),"decision":patch,"at":iso(now())}
    # Apply the same hybrid classifier to newly discovered ambiguous website records.
    extra=[]
    for row in [i for i in items if i.get("source_type") in {"website"} and (i.get("review_required") or i.get("content_type")=="review")]:
        key=hash_text("classifier-v2",row.get("title"),row.get("snippet"),row.get("link")); cached=cache.get(row["id"],{})
        if cached.get("content_key")==key and cached.get("decision"):
            row.update(cached["decision"]); continue
        extra.append(row)
    extra_decisions=ai_classify(extra[:maxn],campaigns,state,config)
    for row in extra[:maxn]:
        d=extra_decisions.get(row["id"]);
        if not d: continue
        match=d.get("matched_campaign_id")
        if match in byid and byid[match].get("competitor_id")!=row.get("competitor_id"):
            d={**d,"decision":"review","matched_campaign_id":None}
        patch={"ai_classification":d,"campaign_category":d["category"],"primary_category":d["category"],"categories":[d["category"]]}
        if d["decision"]=="review":
            patch.update(content_type="review",review_required=True,review_reasons=["ai_needs_review"])
        elif d["decision"]=="link" and d.get("matched_campaign_id") in byid:
            # Existing campaign wins. This website row will be physically merged/removed below.
            patch.update(duplicate_candidate_id=d["matched_campaign_id"],content_type="review",review_required=True,review_reasons=["possible_duplicate_campaign"])
        elif d["record_type"]=="campaign":
            # Critical anti-dup rule: a newly discovered official-page row never becomes a counted
            # campaign automatically. Keep it in Needs Review until it is matched or manually approved.
            patch.update(content_type="review",suggested_record_type="campaign",review_required=True,review_reasons=["new_official_campaign_needs_review"])
        else:
            patch.update(content_type=d["record_type"],review_required=False,review_reasons=[])
        row.update(patch); cache[row["id"]]={"content_key":hash_text("classifier-v2",row.get("title"),row.get("snippet"),row.get("link")),"decision":patch,"at":iso(now())}

    linked=defaultdict(list)
    for p in [i for i in items if i.get("source_type")=="social" and i.get("campaign_id") in byid]:linked[p["campaign_id"]].append({k:p.get(k) for k in ["id","platform","title","link","published_at","media","match_method"]})
    current=now()
    for c in campaigns:
        posts=sorted(linked.get(c["id"],[]),key=lambda p:dt(p.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc));counts=Counter(p.get("platform") for p in posts if p.get("platform"))
        c["linked_posts"]=posts;c["social_post_counts"]={p:int(counts.get(p,0)) for p in ["instagram","x","facebook","tiktok"]};c["social_posts_total"]=len(posts);c["social_platform_count"]=sum(v>0 for v in c["social_post_counts"].values())
        c["social_first_post"]=posts[0].get("published_at") if posts else None;c["social_latest_post"]=posts[-1].get("published_at") if posts else None;c["social_posts_7d"]=sum((dt(p.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc))>=current-timedelta(days=7) for p in posts);c["social_posts_30d"]=sum((dt(p.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc))>=current-timedelta(days=30) for p in posts)
        links=dict(c.get("social_links") or {})
        for p in posts:
            if p.get("platform") and p.get("link"):links[p["platform"]]=p["link"]
        c["social_links"]=links;c["social_link_count"]=len(links)

ARABIC_DIACRITICS=re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
TITLE_STOP={"offer","offers","campaign","campaigns","promotion","promotions","promo","deal","deals","عرض","عروض","حملة","حملات","ترويج","ترويجي"}
GENERIC_TITLE_KEYS={"read more","learn more","details","view details","more","explore more","view offer","اعرف المزيد","استكشف المزيد","المزيد","التفاصيل","تفاصيل العرض","عرض التفاصيل"}

def campaign_title_key(value):
    text=html_lib.unescape(clean(value,500))
    text=unicodedata.normalize("NFKC",text).casefold().replace("ـ","")
    text=ARABIC_DIACRITICS.sub("",text)
    text=text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹","01234567890123456789"))
    text=re.sub(r"[®™©]"," ",text)
    text=re.sub(r"[^\w%]+"," ",text,flags=re.UNICODE)
    return " ".join(x for x in text.split() if x not in TITLE_STOP).strip()

def generic_campaign_title(value):
    key=campaign_title_key(value)
    return key in {campaign_title_key(x) for x in GENERIC_TITLE_KEYS}

def detail_url_identity(value):
    if not value:return ""
    try:
        parts=urlsplit(str(value).strip())
        host=parts.netloc.casefold()
        if host.startswith("www."):host=host[4:]
        path=re.sub(r"/{2,}","/",parts.path or "/").rstrip("/").casefold() or "/"
        path=re.sub(r"^/(?:ar|en)(?=/)","",path)
        query=urlencode(sorted((k.casefold(),v) for k,v in parse_qsl(parts.query,keep_blank_values=True) if not k.casefold().startswith("utm_")))
        return f"{host}{path}"+(f"?{query}" if query else "")
    except Exception:return str(value).strip().casefold().rstrip("/")

def title_similarity(a,b):
    aa=set(campaign_title_key(a).split());bb=set(campaign_title_key(b).split())
    if not aa or not bb:return 0.0
    if campaign_title_key(a)==campaign_title_key(b):return 1.0
    return len(aa&bb)/(len(aa|bb) or 1)

def merge_into_campaign(target, source):
    if source.get("official_campaign_page_url"):
        target["official_campaign_page_url"]=source["official_campaign_page_url"]
        target["primary_official_source_url"]=source["official_campaign_page_url"]
        target["link"]=source["official_campaign_page_url"]
    links=dict(target.get("social_links") or {}); links.update({k:v for k,v in (source.get("social_links") or {}).items() if v})
    target["social_links"]=links; target["social_link_count"]=len(links)
    for f in ["summary","snippet","start_date","end_date","published_at","mechanic","eligibility","terms_note","media","evidence_snapshot"]:
        if not target.get(f) and source.get(f): target[f]=source[f]
    if source.get("last_live_verified_at"): target["last_live_verified_at"]=source["last_live_verified_at"]

def campaign_rank(row):
    if row.get("source_type")=="inventory" and row.get("manual_override"):return 70
    if row.get("source_type")=="inventory":return 60
    if row.get("source_type")=="manual":return 50
    if row.get("manual_override"):return 45
    if row.get("verified") and row.get("official_campaign_page_url"):return 30
    if row.get("source_type")=="website":return 20
    return 10

def consolidate_duplicates(data):
    """Physically remove duplicate campaigns and merge official evidence into one record.

    Never merges across competitors. Official URL identity is strongest; exact normalized title is
    next; near-title matching is intentionally strict and only within the same category.
    """
    items=data.get("items",[]);byid={i.get("id"):i for i in items};remove=set();redirect={}
    # Explicit AI/heuristic link to an existing authoritative campaign.
    for row in items:
        target_id=row.get("duplicate_candidate_id")
        if target_id in byid and row.get("id")!=target_id:
            merge_into_campaign(byid[target_id],row);remove.add(row.get("id"));redirect[row.get("id")]=target_id

    campaigns=[i for i in items if i.get("id") not in remove and i.get("content_type")=="campaign"]
    campaigns.sort(key=campaign_rank,reverse=True)
    kept=[];by_title={};by_url={}
    for row in campaigns:
        comp=row.get("competitor_id") or "";title_key=campaign_title_key(row.get("title"))
        urls={detail_url_identity(u) for u in [row.get("official_campaign_page_url"),row.get("primary_official_source_url"),row.get("link")] if u};urls.discard("")
        target=None
        for u in urls:
            if (comp,u) in by_url:target=by_url[(comp,u)];break
        if target is None and title_key and not generic_campaign_title(row.get("title")):
            target=by_title.get((comp,title_key))
        if target is None and title_key and not generic_campaign_title(row.get("title")):
            scored=[(title_similarity(row.get("title"),c.get("title")),c) for c in kept if c.get("competitor_id")==comp and c.get("campaign_category")==row.get("campaign_category")]
            if scored:
                score,cand=max(scored,key=lambda x:x[0])
                if score>=.94:target=cand
        if target is None:
            kept.append(row)
            if title_key and not generic_campaign_title(row.get("title")):by_title[(comp,title_key)]=row
            for u in urls:by_url[(comp,u)]=row
            continue
        merge_into_campaign(target,row);remove.add(row.get("id"));redirect[row.get("id")]=target.get("id")
        for f in ["summary","snippet","start_date","end_date","published_at","mechanic","eligibility","terms_note","operation_type"]:
            if not target.get(f) and row.get(f):target[f]=row[f]
        if title_key and not generic_campaign_title(row.get("title")):by_title[(comp,title_key)]=target
        for u in urls:by_url[(comp,u)]=target

    if remove:
        data["items"]=[i for i in items if i.get("id") not in remove]
        # Preserve post links after a duplicate campaign is removed.
        for p in data["items"]:
            cid=p.get("campaign_id")
            if cid in redirect:p["campaign_id"]=redirect[cid]
            sid=p.get("suggested_campaign_id")
            if sid in redirect:p["suggested_campaign_id"]=redirect[sid]
    data["deduplication"]={"removed":len(remove),"at":iso(now())}
    return len(remove)

def detect_duplicates_replacements(data):
    # Duplicate campaigns are consolidated before this point. Keep only replacement hints.
    items=[i for i in data.get("items",[]) if i.get("content_type")=="campaign"]
    for i in items:i.pop("duplicate_candidate_id",None);i.pop("replacement_candidate_id",None)
    for idx,a in enumerate(items):
        at=tokenize(f"{a.get('title','')} {a.get('mechanic','')}")
        for b in items[idx+1:]:
            if a.get("competitor_id")!=b.get("competitor_id"):continue
            bt=tokenize(f"{b.get('title','')} {b.get('mechanic','')}");sim=len(at&bt)/(len(at|bt) or 1)
            if sim>=.60 and a.get("campaign_category")==b.get("campaign_category"):
                newer,older=(a,b) if (dt(a.get("start_date")) or datetime.min.replace(tzinfo=timezone.utc))>(dt(b.get("start_date")) or datetime.min.replace(tzinfo=timezone.utc)) else (b,a)
                if older.get("active") is False:newer["replacement_candidate_id"]=older["id"]

def review_priority(item):
    n=0
    if item.get("review_required"):n+=20
    if item.get("campaign_category")=="remittance":n+=8
    if item.get("source_type") in {"website","manual"}:n+=5
    if item.get("source_verification",{}).get("source_changed"):n+=6
    if item.get("suggested_campaign_id"):n+=3
    return n

def snapshot_campaigns(items):
    return {i["id"]:{k:i.get(k) for k in ["title","campaign_category","mechanic","current_status","start_date","end_date","active"]} for i in items if i.get("content_type")=="campaign"}

def material_delta(previous,current):
    added=[k for k in current if k not in previous];removed=[k for k in previous if k not in current];changed=[]
    for k in current.keys()&previous.keys():
        fields=[f for f in current[k] if current[k].get(f)!=previous[k].get(f)]
        if fields:changed.append({"id":k,"fields":fields,"before":previous[k],"after":current[k]})
    return {"added":added,"removed":removed,"changed":changed,"initial":not bool(previous),"material":bool(added or removed or changed)}

def deterministic_summary(items,delta):
    campaigns=[i for i in items if i.get("content_type")=="campaign" and i.get("active") is not False];counts=Counter(i.get("campaign_category") for i in campaigns)
    if delta.get("initial"):what=["Initial baseline generated; no previous snapshot is available for comparison."]
    elif delta.get("material"):what=[f"{len(delta['added'])} added · {len(delta['removed'])} removed · {len(delta['changed'])} updated"]
    else:what=["No material campaign change confirmed since the previous snapshot."]
    cats=[{"category":CATEGORY_LABELS[k],"summary":f"{counts[k]} active campaign(s) in the current verified inventory."} for k in CATEGORY_LABELS if counts.get(k)]
    return {"what_changed":what,"why_it_matters":["Current campaign totals and expiry status are calculated from the full active inventory."],"management_takeaway":"Continue monitoring current campaign mechanics and upcoming expiries; social activity is supporting context rather than market performance.","category_snapshot":cats,"generated_by":"rules","generated_at":iso(now())}

def ai_summary(items,delta,state,config):
    prior=state.get("ai_summary")
    if prior and not delta.get("material"):return prior
    fallback=deterministic_summary(items,delta);client=openai_client()
    if not client or not config.get("ai",{}).get("summary_enabled",True):return fallback
    model=config.get("ai",{}).get("summary_model","gpt-5.6-sol");campaigns=[i for i in items if i.get("content_type")=="campaign" and i.get("active") is not False]
    compact=[{"competitor_id":i.get("competitor_id"),"title":i.get("title"),"category":i.get("campaign_category"),"mechanic":i.get("mechanic"),"start_date":i.get("start_date"),"end_date":i.get("end_date"),"status":i.get("current_status"),"corridors":i.get("corridors",[]),"offer_values":i.get("offer_values",[]),"social_posts_total":i.get("social_posts_total",0)} for i in campaigns]
    schema={"type":"object","additionalProperties":False,"properties":{"what_changed":{"type":"array","items":{"type":"string"},"maxItems":4},"why_it_matters":{"type":"array","items":{"type":"string"},"minItems":1,"maxItems":4},"management_takeaway":{"type":"string"},"category_snapshot":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{"category":{"type":"string"},"summary":{"type":"string"}},"required":["category","summary"]}}},"required":["what_changed","why_it_matters","management_takeaway","category_snapshot"]}
    prompt="""Produce a concise management summary for a Saudi fintech competitor monitor. Use the full current active campaign inventory. What Changed contains only confirmed campaign additions/removals/mechanic/date/status changes from delta; on initial baseline say no previous snapshot exists in one sentence. Why It Matters: 2-4 concise implications. Management Takeaway: one short paragraph. Category Snapshot: factual active categories only. Do not produce a 7-day brief, opportunities/gaps, competitive gap recommendations, watchlists, strength/activity scores, or performance claims. Merchant offers are excluded from campaign KPIs. Social post counts are context only."""
    try:
        r=client.responses.create(model=model,reasoning={"effort":config.get("ai",{}).get("summary_reasoning","xhigh")},text={"format":{"type":"json_schema","name":"management_summary","schema":schema,"strict":True}},input=[{"role":"system","content":prompt},{"role":"user","content":json.dumps({"delta":delta,"active_campaigns":compact},ensure_ascii=False)}])
        result=json.loads(r.output_text);result["generated_by"]=model;result["generated_at"]=iso(now());inp,out=usage_numbers(r);add_usage(state,"summary",model,inp,out,config);return result
    except Exception as exc:
        print(f"[AI summary] {type(exc).__name__}: {exc}");return fallback

def recompute_stats(data):
    items=data.get("items",[]);current=now();campaigns=[i for i in items if i.get("content_type")=="campaign" and i.get("active") is not False];merchants=[i for i in items if i.get("content_type")=="merchant_offer" and i.get("active") is not False];social7=[i for i in items if i.get("source_type")=="social" and i.get("active") is not False and (dt(i.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc))>=current-timedelta(days=7)];statuses=[s for s in data.get("source_status",[]) if s.get("source_type") in {"website","social"}]
    data["stats"]={"active_campaigns":len(campaigns),"merchant_offers":len(merchants),"remittance_campaigns":sum(i.get("campaign_category")=="remittance" for i in campaigns),"expiring_30d":sum("Expiring" in (i.get("current_status") or "") for i in campaigns),"social_posts_7d":len(social7),"review_required":sum(i.get("active") is not False and i.get("review_required") for i in items),"healthy_sources":sum(bool(s.get("success")) for s in statuses),"failed_sources":sum(not s.get("success") for s in statuses),"total_sources":len(statuses)}

def main():
    data=load(DATA_PATH,{});state=load(STATE_PATH,{"schema_version":5,"items":{}});config=load(CONFIG_PATH,{});overrides=load(OVERRIDES_PATH,{"items":{},"new_items":[]})
    if not data.get("items"):print("No data items");return 0
    add_manual_new_items(data,overrides);verify_details(data,state,config,overrides);enforce_record_integrity(data,config);enrich_social(data,state,config,overrides);enforce_record_integrity(data,config);consolidate_duplicates(data);detect_duplicates_replacements(data)
    for item in data.get("items",[]):
        item["review_priority"]=review_priority(item);item.pop("confidence",None) # confidence stays internal, never a displayed score
    snap=snapshot_campaigns(data["items"]);delta=material_delta(state.get("summary_snapshot",{}),snap);summary=ai_summary(data["items"],delta,state,config)
    state.update(summary_snapshot=snap,ai_summary=summary,authoritative_delta=delta,schema_version=5,updated_at=iso(now()))
    data.update(schema_version=5,ai_summary=summary,authoritative_delta=delta,ai_usage=state.get("ai_usage",{}));recompute_stats(data)
    data["items"].sort(key=lambda i:(i.get("active") is not False,i.get("review_priority",0),dt(i.get("published_at")) or dt(i.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc)),reverse=True)
    save(DATA_PATH,data);save(STATE_PATH,state);print(f"Enhanced {len(data['items'])} items · review={data['stats']['review_required']} · AI calls total={data.get('ai_usage',{}).get('calls',0)}");return 0

if __name__=="__main__": raise SystemExit(main())
