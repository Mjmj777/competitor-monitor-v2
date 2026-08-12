"""Competitor intelligence collector aligned with the approved Excel inventory.

The Excel-derived ``inventory.json`` is the reporting baseline. Live website and
RSS checks add source health, recent social posts, media and newly discovered
items. Merchant offers remain separate from campaign KPIs.
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
DATA_PATH = BASE_DIR / "data.json"
USER_AGENT = "Mozilla/5.0 CompetitorMonitor/4.0"
TRACKING_KEYS = {"fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    tmp.replace(path)


def clean(value: Any, limit: int | None = None) -> str:
    text = html_lib.unescape("" if value is None else str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text if not limit or len(text) <= limit else text[: limit - 1].rstrip() + "…"


def canonical(base: str, href: str) -> str | None:
    href = clean(href)
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    absolute = urljoin(base, href)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.casefold().startswith("utm_") and k.casefold() not in TRACKING_KEYS]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), re.sub(r"/{2,}", "/", parts.path or "/"), urlencode(sorted(query)), ""))


def digest(*parts: Any, length: int = 20) -> str:
    raw = "\x1f".join(clean(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def session() -> requests.Session:
    retry = Retry(total=2, connect=2, read=2, backoff_factor=.6, status_forcelist=(429, 500, 502, 503, 504))
    adapter = HTTPAdapter(max_retries=retry)
    value = requests.Session()
    value.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ar,en;q=0.9"})
    value.mount("https://", adapter)
    value.mount("http://", adapter)
    return value


def parse_date(value: str | None) -> str | None:
    value = clean(value)
    if not value:
        return None
    try:
        return iso(parsedate_to_datetime(value))
    except (TypeError, ValueError, OverflowError):
        pass
    parsed = parse_iso(value)
    return iso(parsed) if parsed else None


def taxonomy_match(text: str, config: dict[str, Any]) -> tuple[str, list[str]]:
    normalized = text.casefold()
    matches: list[tuple[int, str]] = []
    for row in config["categories"]:
        if row["id"] in {"other", "merchant"}:
            continue
        if any(word.casefold() in normalized for word in row.get("keywords", [])):
            matches.append((int(row.get("priority", 999)), row["id"]))
    matches.sort()
    ids = list(dict.fromkeys(item[1] for item in matches))
    return (ids[0] if ids else "other", ids or ["other"])


def infer_tags(text: str) -> tuple[list[str], list[str]]:
    t = text.casefold()
    mechanic_rules = [
        ("discount", ["discount", "% off", "خصم", "كود"]),
        ("cashback", ["cashback", "cash back", "كاش باك", "استرداد"]),
        ("fee_waiver", ["zero fee", "0% fee", "no fee", "fee-free", "بدون رسوم", "إعفاء"]),
        ("prize_draw", ["prize", "win", "winner", "draw", "جائزة", "اربح", "سحب"]),
        ("reward", ["reward", "points", "voucher", "bonus", "مكافأة", "نقاط", "قسيمة"]),
        ("preferred_rate", ["preferred rate", "special rate", "exchange rate", "سعر صرف", "سعر تفضيلي"]),
    ]
    theme_rules = [
        ("international_transfer", ["international transfer", "remittance", "تحويل دولي", "حوالة دولية"]),
        ("travel", ["travel", "flight", "hotel", "airport", "سفر", "طيران", "فندق", "مطار"]),
        ("international_fees", ["international fee", "foreign transaction", "رسوم دولية", "مشتريات دولية"]),
        ("cards", ["card", "visa", "mastercard", "mada", "بطاقة", "فيزا", "مدى"]),
        ("musaned", ["musaned", "masaned", "domestic worker", "مساند", "عمالة منزلية"]),
        ("sadad", ["sadad", "bill", "سداد", "فواتير"]),
        ("engagement", ["quiz", "game", "prediction", "competition", "مسابقة", "لعبة", "توقع"]),
    ]
    mechanics = [key for key, words in mechanic_rules if any(word in t for word in words)] or ["other"]
    themes = [key for key, words in theme_rules if any(word in t for word in words)] or ["other"]
    return mechanics, themes


def direct_detail(link: str, source: dict[str, Any]) -> bool:
    return any(re.search(pattern, link, re.I) for pattern in source.get("detail_link_patterns", []))


def media_from_node(node: Any, base: str) -> dict[str, str] | None:
    if node is None:
        return None
    video = node.find("video") or node.find("source")
    if video:
        url = canonical(base, video.get("src") or "")
        if url:
            poster = canonical(base, video.get("poster") or "") or ""
            return {"url": url, "type": "video", "thumbnail_url": poster}
    image = node.find("img")
    if image:
        url = canonical(base, image.get("src") or image.get("data-src") or "")
        if url:
            return {"url": url, "type": "image", "thumbnail_url": url}
    return None




def normalized_title(value: str | None) -> str:
    text = clean(value).casefold()
    text = re.sub(r"[^\w%]+", " ", text, flags=re.UNICODE)
    stop = {"offer","offers","campaign","promotion","عرض","عروض","حملة"}
    return " ".join(x for x in text.split() if x not in stop).strip()


def title_similarity(a: str | None, b: str | None) -> float:
    aa=set(normalized_title(a).split()); bb=set(normalized_title(b).split())
    if not aa or not bb: return 0.0
    if normalized_title(a)==normalized_title(b): return 1.0
    return len(aa & bb) / max(1, len(aa | bb))


def merge_campaign_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    # Enrich the authoritative campaign instead of creating another campaign record.
    if source.get("official_campaign_page_url"):
        target["official_campaign_page_url"] = source["official_campaign_page_url"]
        target["primary_official_source_url"] = source["official_campaign_page_url"]
        target["link"] = source["official_campaign_page_url"]
    links=dict(target.get("social_links") or {})
    links.update({k:v for k,v in (source.get("social_links") or {}).items() if v})
    target["social_links"]=links; target["social_link_count"]=len(links)
    if not target.get("media") and source.get("media"): target["media"]=source["media"]
    if source.get("last_seen") or source.get("last_changed"):
        target["last_live_verified_at"] = source.get("last_seen") or source.get("last_changed")

def website_items(http: requests.Session, competitor: dict[str, Any], source: dict[str, Any], config: dict[str, Any], checked: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    key = f"website:{competitor['id']}:{source['id']}"
    status = {"source_key": key, "competitor_id": competitor["id"], "source_type": "website", "platform": "website", "url": source["url"], "checked_at": checked, "success": False, "item_count": 0, "error": None, "skipped_general_links": 0}
    try:
        response = http.get(source["url"], timeout=int(config["settings"].get("request_timeout_seconds", 18)))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        found: dict[str, dict[str, Any]] = {}
        link_words = [word.casefold() for word in source.get("link_keywords", [])]
        excludes = [word.casefold() for word in source.get("exclude_keywords", [])]
        for anchor in soup.find_all("a", href=True):
            link = canonical(source["url"], anchor.get("href", ""))
            if not link:
                continue
            parent = anchor
            for candidate in list(anchor.parents)[:4]:
                if candidate.name in {"article", "li", "div", "section"}:
                    parent = candidate
                    break
            title = clean(anchor.get_text(" ", strip=True) or anchor.get("aria-label") or anchor.get("title"), 180)
            snippet = clean(parent.get_text(" ", strip=True), 500)
            combined = f"{link} {title} {snippet}".casefold()
            if excludes and any(word in combined for word in excludes):
                continue
            if link_words and not any(word in combined for word in link_words):
                continue
            is_direct = direct_detail(link, source)
            if source.get("require_detail_link", True) and not is_direct:
                status["skipped_general_links"] += 1
                continue
            category, categories = taxonomy_match(combined, config)
            mechanics, themes = infer_tags(combined)
            found[link] = {
                "id": f"detected:{competitor['id']}:{digest(link)}", "competitor_id": competitor["id"], "source_key": key,
                "source_type": "website", "platform": "website", "content_type": "review", "campaign_category": category,
                "primary_category": category, "categories": categories, "title": title or "Discovered official offer",
                "snippet": snippet, "link": link, "official_campaign_page_url": link, "primary_official_source_url": link,
                "social_links": {}, "social_link_count": 0, "published_at": None, "start_date": None, "end_date": None,
                "current_status": "Needs Review", "active": True, "direct_link": is_direct, "verified": True,
                "review_required": True, "review_reasons": ["new_official_item_not_in_excel_inventory"], "confidence": "medium",
                "mechanic_tags": mechanics, "theme_tags": themes, "media": media_from_node(parent, source["url"]),
            }
        items = list(found.values())[: int(config["settings"].get("max_items_per_source", 80))]
        status.update(success=True, item_count=len(items))
        return items, status
    except Exception as exc:  # one failing source must not stop the full run
        status["error"] = clean(f"{type(exc).__name__}: {exc}", 500)
        return [], status


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if local(child.tag) in names:
            return clean(" ".join(child.itertext()))
    return ""


def feed_media(node: ET.Element, markup: str, base: str) -> dict[str, str] | None:
    candidates: list[tuple[str, str]] = []
    for desc in node.iter():
        if local(desc.tag) in {"content", "thumbnail", "enclosure", "image"}:
            url = clean(desc.attrib.get("url") or desc.attrib.get("href") or desc.attrib.get("src"))
            if url:
                candidates.append((url, clean(desc.attrib.get("type") or desc.attrib.get("medium"))))
    soup = BeautifulSoup(markup or "", "html.parser")
    for tag in soup.find_all(["video", "source", "img"]):
        url = clean(tag.get("src") or tag.get("data-src"))
        if url:
            candidates.append((url, "video" if tag.name in {"video", "source"} else "image"))
    for raw, hinted in candidates:
        url = canonical(base, raw)
        if not url:
            continue
        kind = "video" if "video" in hinted.casefold() or re.search(r"\.(mp4|webm|mov)(\?|$)", url, re.I) else "image"
        return {"url": url, "type": kind, "thumbnail_url": url if kind == "image" else ""}
    return None


def parse_feed(content: bytes, url: str) -> list[dict[str, Any]]:
    root = ET.fromstring(content)
    nodes = [node for node in root.iter() if local(node.tag) in {"item", "entry"}]
    rows = []
    for node in nodes:
        link = ""
        for child in list(node):
            if local(child.tag) == "link":
                link = clean(child.attrib.get("href") or " ".join(child.itertext()))
                if link:
                    break
        link = link or child_text(node, {"guid", "id"})
        title = child_text(node, {"title"}) or "Social post"
        markup = ""
        for child in list(node):
            if local(child.tag) in {"summary", "description", "content", "encoded"}:
                markup = child.text or "".join(ET.tostring(grand, encoding="unicode") for grand in list(child))
                if markup:
                    break
        summary = clean(BeautifulSoup(markup, "html.parser").get_text(" ", strip=True), 500)
        rows.append({"link": link, "title": clean(title, 180), "summary": summary, "published_at": parse_date(child_text(node, {"pubdate", "published", "updated", "date"})), "media": feed_media(node, markup, url)})
    return rows


def social_items(http: requests.Session, competitor: dict[str, Any], platform: str, rss_url: str, config: dict[str, Any], checked: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    key = f"social:{competitor['id']}:{platform}"
    status = {"source_key": key, "competitor_id": competitor["id"], "source_type": "social", "platform": platform, "url": rss_url, "checked_at": checked, "success": False, "item_count": 0, "error": None}
    try:
        response = http.get(rss_url, timeout=int(config["settings"].get("request_timeout_seconds", 18)))
        response.raise_for_status()
        rows = parse_feed(response.content, rss_url)
        items = []
        for row in rows[: int(config["settings"].get("max_items_per_source", 80))]:
            link = canonical(rss_url, row["link"])
            if not link:
                continue
            combined = f"{row['title']} {row['summary']} {link}"
            category, categories = taxonomy_match(combined, config)
            mechanics, themes = infer_tags(combined)
            awareness = any(word.casefold() in combined.casefold() for word in config.get("classification", {}).get("awareness_keywords", []))
            items.append({
                "id": f"post:{competitor['id']}:{platform}:{digest(link)}", "competitor_id": competitor["id"], "source_key": key,
                "source_type": "social", "platform": platform, "content_type": "awareness" if awareness else "social_post",
                "campaign_category": category, "primary_category": category, "categories": categories,
                "title": row["title"], "snippet": row["summary"], "link": link, "social_links": {platform: link},
                "social_link_count": 1, "published_at": row["published_at"], "active": True, "direct_link": True,
                "verified": True, "review_required": False, "review_reasons": [], "confidence": "medium",
                "mechanic_tags": mechanics, "theme_tags": themes, "media": row["media"],
            })
        status.update(success=True, item_count=len(items))
        return items, status
    except Exception as exc:
        status["error"] = clean(f"{type(exc).__name__}: {exc}", 500)
        return [], status


def apply_override(item: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    allowed = {"title", "snippet", "summary", "content_type", "campaign_category", "primary_category", "categories", "current_status", "active", "published_at", "start_date", "end_date", "official_campaign_page_url", "primary_official_source_url", "link", "social_links", "review_required", "review_reasons", "mechanic_tags", "theme_tags", "operation_type", "mechanic", "eligibility", "terms_note"}
    result = dict(item)
    for key, value in override.items():
        if key in allowed:
            result[key] = value
    if "campaign_category" in result:
        result["primary_category"] = result["campaign_category"]
        result["categories"] = [result["campaign_category"]]
    result["social_links"] = {k: v for k, v in (result.get("social_links") or {}).items() if v}
    result["social_link_count"] = len(result["social_links"])
    result["manual_override"] = True
    return result


def reconcile_live(state: dict[str, Any], collected: list[dict[str, Any]], statuses: list[dict[str, Any]], now: datetime, config: dict[str, Any]) -> list[dict[str, Any]]:
    items = state.setdefault("items", {})
    successful = {row["source_key"] for row in statuses if row.get("success")}
    seen: set[str] = set()
    stamp = iso(now)
    for row in collected:
        seen.add(row["id"])
        old = items.get(row["id"])
        content_hash = digest(row.get("title"), row.get("snippet"), row.get("content_type"), row.get("campaign_category"), row.get("link"), row.get("media", {}).get("url") if row.get("media") else "", length=32)
        if not old:
            row.update(first_seen=stamp, last_seen=stamp, last_changed=stamp, version=1, miss_count=0, content_hash=content_hash, change_history=[{"at": stamp, "type": "detected", "version": 1}])
            items[row["id"]] = row
        else:
            changed = old.get("content_hash") != content_hash
            version = int(old.get("version", 1)) + (1 if changed else 0)
            history = list(old.get("change_history", []))
            if changed:
                history.append({"at": stamp, "type": "updated", "version": version})
            items[row["id"]] = {**old, **row, "first_seen": old.get("first_seen") or stamp, "last_seen": stamp, "last_changed": stamp if changed else old.get("last_changed") or stamp, "version": version, "miss_count": 0, "content_hash": content_hash, "change_history": history[-30:]}
    inactive_after = int(config["settings"].get("inactive_after_missed_runs", 3))
    for key, old in items.items():
        if key in seen or old.get("source_key") not in successful:
            continue
        old["miss_count"] = int(old.get("miss_count", 0)) + 1
        if old["miss_count"] >= inactive_after:
            old["active"] = False
    state["schema_version"] = 4
    state["updated_at"] = stamp
    save_json(STATE_PATH, state)
    hidden = {"content_hash", "miss_count"}
    return [{k: v for k, v in row.items() if k not in hidden} for row in items.values()]


def match_inventory(inventory: list[dict[str, Any]], live: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    official_map: dict[str, dict[str, Any]] = {}
    social_map: dict[str, dict[str, Any]] = {}
    by_competitor: dict[str, list[dict[str, Any]]] = {}
    for campaign in inventory:
        by_competitor.setdefault(campaign.get("competitor_id"), []).append(campaign)
        for url in [campaign.get("link"), campaign.get("official_campaign_page_url"), campaign.get("primary_official_source_url")]:
            if url: official_map[canonical(url, url) or url] = campaign
        for url in (campaign.get("social_links") or {}).values():
            if url: social_map[canonical(url, url) or url] = campaign
    enriched = {row["id"]: dict(row) for row in inventory}
    remaining: list[dict[str, Any]] = []
    for row in live:
        key = canonical(row.get("link", ""), row.get("link", "")) or row.get("link")
        campaign = social_map.get(key) if row.get("source_type") == "social" else official_map.get(key)
        # Website offer detail pages are also matched by title/category when the Excel row
        # does not yet contain that detail URL. This is what prevents duplicate campaigns.
        if not campaign and row.get("source_type") == "website":
            candidates=by_competitor.get(row.get("competitor_id"), [])
            scored=[]
            for c in candidates:
                sim=title_similarity(row.get("title"), c.get("title"))
                if row.get("campaign_category") == c.get("campaign_category"): sim += .12
                scored.append((sim,c))
            if scored:
                score,cand=max(scored,key=lambda x:x[0])
                if score >= .72: campaign=cand
        if campaign:
            row["campaign_id"] = campaign["id"]
            target = enriched[campaign["id"]]
            if row.get("source_type") == "social":
                links = dict(target.get("social_links") or {}); links[row["platform"]] = row["link"]
                target["social_links"] = links; target["social_link_count"] = len(links)
                if not target.get("media") and row.get("media"): target["media"] = row["media"]
                target["last_live_verified_at"] = row.get("last_seen") or row.get("last_changed")
                remaining.append(row)  # social posts stay visible as activity
            else:
                merge_campaign_fields(target,row)
                # Do NOT keep a matched website row as a separate item.
            continue
        remaining.append(row)
    return list(enriched.values()), remaining


def deduplicate_campaign_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Last safety net: one active campaign record per competitor/campaign identity."""
    keep=[]; campaign_keys={}
    for row in items:
        if row.get("content_type") != "campaign":
            keep.append(row); continue
        urls=[]
        for u in [row.get("official_campaign_page_url"),row.get("primary_official_source_url"),row.get("link")]:
            if u: urls.append(canonical(u,u) or u)
        title_key=normalized_title(row.get("title"))
        keys=[("url",row.get("competitor_id"),u) for u in urls]
        if title_key: keys.append(("title",row.get("competitor_id"),title_key))
        target=None
        for k in keys:
            if k in campaign_keys: target=campaign_keys[k]; break
        if target is None:
            keep.append(row)
            for k in keys: campaign_keys[k]=row
        else:
            merge_campaign_fields(target,row)
            # Prefer the richer/manual/inventory fields while preserving one record only.
            for f in ["summary","snippet","start_date","end_date","published_at","mechanic","eligibility","terms_note"]:
                if not target.get(f) and row.get(f): target[f]=row[f]
            target["review_required"] = bool(target.get("review_required") and row.get("review_required"))
    return keep

def source_history(statuses: list[dict[str, Any]], previous_data: dict[str, Any], checked: str) -> list[dict[str, Any]]:
    old = {row.get("source_key"): row for row in previous_data.get("source_status", [])}
    for row in statuses:
        prior = old.get(row["source_key"], {})
        if row.get("success"):
            row["last_success_at"] = checked
            row["consecutive_failures"] = 0
        else:
            row["last_success_at"] = prior.get("last_success_at")
            row["consecutive_failures"] = int(prior.get("consecutive_failures", 0)) + 1
    return statuses


def public_taxonomy(config: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [{k: row.get(k) for k in ("id", "name_ar", "name_en", "priority") if row.get(k) is not None} for row in config.get(key, [])]


def build_stats(items: list[dict[str, Any]], statuses: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    active_campaigns = [row for row in items if row.get("active") is not False and row.get("content_type") == "campaign"]
    active_merchants = [row for row in items if row.get("active") is not False and row.get("content_type") == "merchant_offer"]
    social_7 = [row for row in items if row.get("source_type") == "social" and row.get("active") is not False and (parse_iso(row.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= now - timedelta(days=7)]
    expiring = [row for row in active_campaigns if row.get("current_status") in {"Expiring ≤7 Days", "Expiring 8–30 Days", "Expiring ≤7d", "Expiring 8–30d"}]
    return {
        "active_campaigns": len(active_campaigns), "merchant_offers": len(active_merchants),
        "remittance_campaigns": sum(1 for row in active_campaigns if row.get("campaign_category") == "remittance"),
        "expiring_30d": len(expiring), "social_posts_7d": len(social_7),
        "review_required": sum(1 for row in items if row.get("active") is not False and row.get("review_required")),
        "healthy_sources": sum(1 for row in statuses if row.get("success")),
        "failed_sources": sum(1 for row in statuses if not row.get("success")), "total_sources": len(statuses),
    }


def validate(config: dict[str, Any]) -> None:
    if not config.get("competitors"):
        raise ValueError("No competitors configured")
    category_ids = {row["id"] for row in config.get("categories", [])}
    required = {"remittance", "musaned", "sadad", "card", "engagement", "other", "merchant"}
    if not required.issubset(category_ids):
        raise ValueError(f"Missing Excel categories: {sorted(required - category_ids)}")


def run(config: dict[str, Any]) -> dict[str, Any]:
    validate(config)
    now = now_utc(); checked = iso(now)
    inventory_payload = load_json(BASE_DIR / config["settings"].get("inventory_path", "inventory.json"), {"items": []})
    inventory = inventory_payload.get("items", [])
    overrides = load_json(BASE_DIR / config["settings"].get("manual_overrides_path", "manual_overrides.json"), {"items": {}}).get("items", {})
    collected: list[dict[str, Any]] = []; statuses: list[dict[str, Any]] = []
    jobs: list[tuple[str, dict[str, Any], Any, Any]] = []
    for competitor in config["competitors"]:
        for source in competitor.get("website_sources", []):
            jobs.append(("website", competitor, source, None))
        for platform, rss_url in competitor.get("social_feeds", {}).items():
            jobs.append(("social", competitor, platform, rss_url))

    def execute(job: tuple[str, dict[str, Any], Any, Any]):
        kind, competitor, third, fourth = job
        http = session()
        if kind == "website":
            return website_items(http, competitor, third, config, checked)
        return social_items(http, competitor, third, fourth, config, checked)

    with ThreadPoolExecutor(max_workers=min(10, max(1, len(jobs)))) as pool:
        futures = [pool.submit(execute, job) for job in jobs]
        for future in as_completed(futures):
            rows, status = future.result()
            collected.extend(rows); statuses.append(status)
            print(f"[{'OK' if status['success'] else 'FAILED'}] {status['source_key']}: {status['item_count']} items")
            if status.get("error"):
                print(f"    {status['error']}")
    statuses.sort(key=lambda row: row["source_key"])
    state = load_json(STATE_PATH, {"schema_version": 4, "items": {}})
    live = reconcile_live(state, collected, statuses, now, config)
    inventory, live = match_inventory(inventory, live)
    items = inventory + live
    items = [apply_override(row, overrides.get(row["id"], {})) for row in items]
    items = deduplicate_campaign_records(items)
    items.sort(key=lambda row: (row.get("active") is not False, parse_iso(row.get("published_at")) or parse_iso(row.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    previous = load_json(DATA_PATH, {})
    statuses = source_history(statuses, previous, checked)
    competitors = [{"id": row["id"], "name_ar": row["name_en"], "name_en": row["name_en"], "website": row.get("website"), "offers_url": row.get("offers_url")} for row in config["competitors"]]
    data = {
        "schema_version": 4, "generated_at": checked,
        "inventory_source": {"workbook": inventory_payload.get("source_workbook"), "review_date": inventory_payload.get("source_review_date"), "reporting_convention": inventory_payload.get("reporting_convention")},
        "competitors": competitors, "categories": public_taxonomy(config, "categories"),
        "mechanic_types": public_taxonomy(config, "mechanic_types"), "themes": public_taxonomy(config, "themes"),
        "content_types": config.get("content_types", []), "source_status": statuses,
        "stats": build_stats(items, statuses, now), "items": items,
    }
    save_json(DATA_PATH, data)
    return data


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(); parser.add_argument("--validate-only", action="store_true"); return parser.parse_args()


def main() -> int:
    try:
        config = load_json(CONFIG_PATH, {})
        validate(config)
        if args().validate_only:
            print("Configuration is valid."); return 0
        data = run(config); print(json.dumps(data["stats"], ensure_ascii=False)); return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", flush=True); return 1


if __name__ == "__main__":
    raise SystemExit(main())
