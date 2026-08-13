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
import unicodedata
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
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
TRACKING_KEYS = {"fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid"}

WINNER_ANNOUNCEMENT_WORDS = [
    "winner", "winners", "congratulations", "congrats", "winner announcement",
    "فائز", "فائزة", "فائزين", "فائزينا", "الفائز", "الفائزة", "الفائزين", "مبروك", "نبارك", "تهانينا"
]

def social_post_role(text: str) -> str:
    folded = clean(text, 5000).casefold()
    if any(word.casefold() in folded for word in WINNER_ANNOUNCEMENT_WORDS):
        return "winner_announcement"
    return "promotion_or_content"


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


SOCIAL_HOSTS = ("instagram.com", "facebook.com", "m.facebook.com", "x.com", "twitter.com", "tiktok.com")

def social_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        host = (urlsplit(str(value)).hostname or "").casefold().removeprefix("www.")
        return any(host == h or host.endswith("." + h) for h in SOCIAL_HOSTS)
    except Exception:
        return False

def social_identity(value: str | None) -> str:
    """Stable identity for a social post URL; platform tracking/query params are ignored."""
    if not value:
        return ""
    try:
        parts = urlsplit(str(value).strip())
        host = (parts.hostname or "").casefold().removeprefix("www.")
        if host == "twitter.com":
            host = "x.com"
        if host == "m.facebook.com":
            host = "facebook.com"
        path = re.sub(r"/{2,}", "/", parts.path or "/").rstrip("/").casefold() or "/"
        return f"{host}{path}"
    except Exception:
        return clean(value).casefold().rstrip("/")

def specific_social_post_url(value: str | None) -> bool:
    if not social_url(value):
        return False
    try:
        parts = urlsplit(str(value))
        host = (parts.hostname or "").casefold().removeprefix("www.")
        path = (parts.path or "").casefold()
        if "instagram.com" in host:
            return bool(re.search(r"/(?:p|reel|reels|tv)/[^/]+", path))
        if host in {"x.com", "twitter.com"} or host.endswith(".x.com") or host.endswith(".twitter.com"):
            return "/status/" in path
        if "tiktok.com" in host:
            return "/video/" in path
        if "facebook.com" in host:
            return any(token in path for token in ("/posts/", "/videos/", "/reel/", "/share/", "/photo", "/permalink")) or "story.php" in str(value).casefold()
    except Exception:
        return False
    return False

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




_ARABIC_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_TITLE_STOP = {
    "offer", "offers", "campaign", "campaigns", "promotion", "promotions", "promo", "deal", "deals",
    "عرض", "عروض", "حملة", "حملات", "ترويج", "ترويجي"
}
_GENERIC_TITLES = {"read more", "learn more", "details", "view details", "more", "explore more", "view offer",
                   "اعرف المزيد", "استكشف المزيد", "المزيد", "التفاصيل", "تفاصيل العرض", "عرض التفاصيل"}


def normalized_title(value: str | None) -> str:
    """Unicode-safe identity key. Visually identical names must normalize identically."""
    text = html_lib.unescape(clean(value))
    text = unicodedata.normalize("NFKC", text).casefold().replace("ـ", "")
    text = _ARABIC_DIACRITICS.sub("", text)
    # Arabic-Indic / Eastern Arabic digits -> ASCII so date/value spelling does not fork an identity.
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    text = re.sub(r"[®™©]", " ", text)
    text = re.sub(r"[^\w%]+", " ", text, flags=re.UNICODE)
    return " ".join(x for x in text.split() if x not in _TITLE_STOP).strip()


def url_identity(value: str | None) -> str:
    """Canonical offer-detail identity; ignores tracking, www and ar/en locale path variants."""
    if not value:
        return ""
    value = canonical(value, value) or clean(value)
    try:
        parts = urlsplit(value)
        host = parts.netloc.casefold().removeprefix("www.")
        path = re.sub(r"/{2,}", "/", parts.path or "/").rstrip("/").casefold() or "/"
        path = re.sub(r"^/(?:ar|en)(?=/)", "", path)
        query = urlencode(sorted((k.casefold(), v) for k, v in parse_qsl(parts.query, keep_blank_values=True)))
        return f"{host}{path}" + (f"?{query}" if query else "")
    except Exception:
        return value.casefold().rstrip("/")


def title_similarity(a: str | None, b: str | None) -> float:
    aa=set(normalized_title(a).split()); bb=set(normalized_title(b).split())
    if not aa or not bb: return 0.0
    if normalized_title(a)==normalized_title(b): return 1.0
    return len(aa & bb) / max(1, len(aa | bb))


def generic_title(value: str | None) -> bool:
    return normalized_title(value) in {normalized_title(x) for x in _GENERIC_TITLES}


def merge_campaign_fields(target: dict[str, Any], source: dict[str, Any]) -> None:
    # Enrich the authoritative campaign instead of creating another campaign record.
    if source.get("official_campaign_page_url"):
        target["official_campaign_page_url"] = source["official_campaign_page_url"]
        target["primary_official_source_url"] = source["official_campaign_page_url"]
        target["link"] = source["official_campaign_page_url"]
    links=dict(target.get("social_links") or {})
    links.update({k:v for k,v in (source.get("social_links") or {}).items() if v})
    target["social_links"]=links; target["social_link_count"]=len(links)
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
            # Prefer a real offer/card heading over generic CTA text such as "Explore more" / "استكشف المزيد".
            raw_candidates = [anchor.get("aria-label"), anchor.get("title")]
            heading = anchor.find(["h1","h2","h3","h4","h5","h6"]) or (parent.find(["h1","h2","h3","h4","h5","h6"]) if parent else None)
            if heading is not None:
                raw_candidates.append(heading.get_text(" ", strip=True))
            raw_candidates.append(anchor.get_text(" ", strip=True))
            title = ""
            for candidate in raw_candidates:
                candidate = clean(candidate, 180)
                if candidate and not generic_title(candidate):
                    title = candidate
                    break
            title = title or clean(anchor.get_text(" ", strip=True), 180) or "Discovered official offer"
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
            post_role = social_post_role(combined)
            winner_unlinked = post_role == "winner_announcement"
            items.append({
                "id": f"post:{competitor['id']}:{platform}:{digest(link)}", "competitor_id": competitor["id"], "source_key": key,
                "source_type": "social", "platform": platform,
                # Winner/result announcements are never campaigns. They start in Needs Review and
                # enhance.py may safely link them to an existing campaign later.
                "content_type": "review" if winner_unlinked else ("awareness" if awareness else "social_post"),
                "campaign_category": category, "primary_category": category, "categories": categories,
                "title": row["title"], "snippet": row["summary"], "link": link, "social_links": {platform: link},
                "social_link_count": 1, "published_at": row["published_at"], "active": True, "direct_link": True,
                "verified": True,
                "review_required": winner_unlinked,
                "review_reasons": ["winner_announcement_unlinked"] if winner_unlinked else [],
                "current_status": "Needs Review" if winner_unlinked else None,
                "confidence": "medium", "post_role": post_role,
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
            if url and not social_url(url):
                official_map[url_identity(url)] = campaign
        for url in (campaign.get("social_links") or {}).values():
            if specific_social_post_url(url):
                social_map[social_identity(url)] = campaign

    enriched = {row["id"]: dict(row) for row in inventory}
    remaining: list[dict[str, Any]] = []
    for row in live:
        if row.get("source_type") == "social":
            key = social_identity(row.get("link"))
            campaign = social_map.get(key) if key else None
        else:
            key = url_identity(row.get("link"))
            campaign = official_map.get(key) if key else None

        # Website offer detail pages are also matched by title/category when the Excel row
        # does not yet contain that detail URL. This prevents duplicate campaigns.
        if not campaign and row.get("source_type") == "website":
            candidates = by_competitor.get(row.get("competitor_id"), [])
            scored = []
            for c in candidates:
                sim = title_similarity(row.get("title"), c.get("title"))
                if row.get("campaign_category") == c.get("campaign_category"):
                    sim += .12
                scored.append((sim, c))
            if scored:
                score, cand = max(scored, key=lambda x: x[0])
                if score >= .72:
                    campaign = cand

        if campaign:
            row["campaign_id"] = campaign["id"]
            target = enriched[campaign["id"]]
            if row.get("source_type") == "social":
                # Preserve the approved/master social URL; RSS activity is stored as a linked post.
                links = dict(target.get("social_links") or {})
                platform = row.get("platform")
                if platform and row.get("link") and not links.get(platform):
                    links[platform] = row["link"]
                target["social_links"] = links
                target["social_link_count"] = len([u for u in links.values() if u])
                target["last_live_verified_at"] = row.get("last_seen") or row.get("last_changed")
                remaining.append(row)
            else:
                merge_campaign_fields(target, row)
            continue
        remaining.append(row)
    return list(enriched.values()), remaining

def campaign_rank(row: dict[str, Any]) -> int:
    # Keep the Excel identity/record ID authoritative. Manual edits to that same row remain highest.
    if row.get("source_type") == "inventory" and row.get("manual_override"): return 70
    if row.get("source_type") == "inventory": return 60
    if row.get("source_type") == "manual": return 50
    if row.get("manual_override"): return 45
    if row.get("verified") and row.get("official_campaign_page_url"): return 30
    if row.get("source_type") == "website": return 20
    return 10


def deduplicate_campaign_records(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hard dedup: one campaign per competitor and campaign identity.

    Identity is resolved by official detail URL first, exact normalized title second, then a
    conservative near-title match within the same category. Different competitors are never merged.
    """
    records=[row for row in items if row.get("content_type") in {"campaign", "merchant_offer"}]
    others=[row for row in items if row.get("content_type") not in {"campaign", "merchant_offer"}]
    # Process authoritative rows first so live discoveries enrich the Excel/manual record.
    records.sort(key=lambda r: campaign_rank(r), reverse=True)
    kept: list[dict[str, Any]]=[]
    by_url: dict[tuple[str,str], dict[str, Any]]={}
    by_title: dict[tuple[str,str], dict[str, Any]]={}
    for row in records:
        comp=row.get("competitor_id") or ""
        record_type=row.get("content_type") or "campaign"
        title_key=normalized_title(row.get("title"))
        urls={(social_identity(u) if social_url(u) else url_identity(u)) for u in [row.get("official_campaign_page_url"),row.get("primary_official_source_url"),row.get("link")] if u}
        urls.discard("")
        target=None
        for u in urls:
            if (comp,record_type,u) in by_url:
                target=by_url[(comp,record_type,u)]; break
        if target is None and title_key and not generic_title(row.get("title")):
            target=by_title.get((comp,record_type,title_key))
        if target is None and title_key and not generic_title(row.get("title")):
            # Safety for tiny punctuation/site-title differences. 0.94 is intentionally strict.
            candidates=[c for c in kept if c.get("competitor_id")==comp and c.get("content_type")==record_type and c.get("campaign_category")==row.get("campaign_category")]
            scored=[(title_similarity(row.get("title"),c.get("title")),c) for c in candidates]
            if scored:
                score,cand=max(scored,key=lambda x:x[0])
                if score >= .94: target=cand
        if target is None:
            kept.append(row)
            if title_key and not generic_title(row.get("title")): by_title[(comp,record_type,title_key)]=row
            for u in urls: by_url[(comp,record_type,u)]=row
            continue
        merge_campaign_fields(target,row)
        for f in ["summary","snippet","start_date","end_date","published_at","mechanic","eligibility","terms_note","operation_type"]:
            if not target.get(f) and row.get(f): target[f]=row[f]
        target["review_required"] = bool(target.get("review_required") and row.get("review_required"))
        # Register every identity from the duplicate against the retained record.
        if title_key and not generic_title(row.get("title")): by_title[(comp,record_type,title_key)]=target
        for u in urls: by_url[(comp,record_type,u)]=target
    return kept + others

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
