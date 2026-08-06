"""Bilingual competitor intelligence collector.

Collects official offer pages and RSS feeds, separates confirmed offers from
partner discounts and ordinary social posts, keeps a version history, extracts
available media, and produces ``data.json`` for GitHub Pages.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import mimetypes
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
STATE_PATH = BASE_DIR / "state.json"
DATA_PATH = BASE_DIR / "data.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0 Safari/537.36 CompetitorMonitor/3.0"
)

TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
GENERIC_LINK_TEXT = {
    "view details", "learn more", "read more", "explore more", "open",
    "اعرف المزيد", "اعرف أكثر", "استكشف المزيد", "عرض التفاصيل",
    "تفاصيل العرض", "المزيد",
}
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
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


def save_json_atomic(path: Path, payload: Any) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    temp_path.replace(path)


def clean_text(value: Any, limit: int | None = None) -> str:
    if value is None:
        return ""
    text = html_lib.unescape(str(value))
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def html_to_text(value: Any, limit: int | None = None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return clean_text(text, limit)


def canonical_url(base_url: str, href: str) -> str | None:
    href = clean_text(href)
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    absolute = urljoin(base_url, href)
    parts = urlsplit(absolute)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    filtered_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        key_lower = key.casefold()
        if key_lower.startswith("utm_") or key_lower in TRACKING_QUERY_KEYS:
            continue
        filtered_query.append((key, value))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    query = urlencode(sorted(filtered_query))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def normalized_host(url: str) -> str:
    host = urlsplit(url).netloc.casefold()
    return host[4:] if host.startswith("www.") else host


def digest(*parts: Any, length: int = 20) -> str:
    raw = "\x1f".join(clean_text(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def make_session() -> requests.Session:
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.8,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ar,en;q=0.9"})
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def validate_config(config: dict[str, Any]) -> None:
    errors: list[str] = []
    competitors = config.get("competitors") or []
    categories = config.get("categories") or []
    benefit_types = config.get("benefit_types") or []
    if not competitors:
        errors.append("config.competitors is empty")
    if not categories or "other" not in {item.get("id") for item in categories}:
        errors.append("categories must include 'other'")
    if not benefit_types:
        errors.append("config.benefit_types is empty")
    for key, rows in (("competitor", competitors), ("category", categories), ("benefit", benefit_types)):
        ids = [row.get("id") for row in rows]
        if len(ids) != len(set(ids)):
            errors.append(f"{key} IDs must be unique")
    for competitor in competitors:
        if not competitor.get("id") or not competitor.get("name_en"):
            errors.append(f"invalid competitor entry: {competitor!r}")
        for source in competitor.get("website_sources", []):
            if not source.get("id") or not source.get("url"):
                errors.append(f"invalid website source for {competitor.get('id')}")
    if errors:
        raise ValueError("; ".join(errors))


def keyword_matches(text: str, keywords: list[str]) -> list[str]:
    normalized = text.casefold()
    return [keyword for keyword in keywords if keyword.casefold() in normalized]


def classify_products(text: str, url: str, config: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    combined = f"{text} {url}".casefold()
    for override in config.get("classification_overrides", []):
        needle = clean_text(override.get("link_contains")).casefold()
        category_id = override.get("category_id")
        if needle and needle in url.casefold() and category_id:
            return category_id, [category_id], [f"override:{needle}"]

    matches: list[tuple[int, str, list[str]]] = []
    for category in config["categories"]:
        if category["id"] == "other":
            continue
        found = keyword_matches(combined, category.get("keywords", []))
        if found:
            matches.append((int(category.get("priority", 999)), category["id"], found))

    # "Spend and win" normally relates to cards unless an in-app marketplace is explicit.
    spend_terms = keyword_matches(combined, config.get("classification", {}).get("spend_terms", []))
    marketplace_terms = keyword_matches(combined, config.get("classification", {}).get("marketplace_terms", []))
    existing = {row[1] for row in matches}
    if spend_terms and "in_app_marketplace" not in existing and not marketplace_terms and "cards" not in existing:
        matches.append((65, "cards", spend_terms))

    if not matches:
        return "other", ["other"], []
    matches.sort(key=lambda row: row[0])
    category_ids = list(dict.fromkeys(row[1] for row in matches))
    evidence = [word for _, _, words in matches for word in words][:16]
    return category_ids[0], category_ids, evidence


def classify_content(
    text: str,
    url: str,
    source_type: str,
    direct_link: bool,
    config: dict[str, Any],
) -> dict[str, Any]:
    combined = f"{text} {url}".casefold()
    primary, categories, category_evidence = classify_products(text, url, config)

    benefit_matches: list[tuple[int, str, list[str]]] = []
    for benefit in config["benefit_types"]:
        found = keyword_matches(combined, benefit.get("keywords", []))
        if found:
            benefit_matches.append((int(benefit.get("priority", 999)), benefit["id"], found))
    benefit_matches.sort(key=lambda row: row[0])
    benefit_ids = list(dict.fromkeys(row[1] for row in benefit_matches))
    benefit_evidence = [word for _, _, words in benefit_matches for word in words][:12]

    rules = config.get("classification", {})
    partner_evidence = keyword_matches(combined, rules.get("partner_keywords", []))
    offer_evidence = keyword_matches(combined, rules.get("offer_words", []))
    awareness_evidence = keyword_matches(combined, rules.get("awareness_keywords", []))

    review_reasons: list[str] = []
    confidence = "high"
    if benefit_ids:
        inferred_partner_discount = primary == "other" and "discount" in benefit_ids
        content_type = "partner_offer" if (partner_evidence or inferred_partner_discount) else "offer"
        if primary == "other" and content_type == "offer":
            confidence = "medium"
            review_reasons.append("benefit_detected_without_product_category")
    elif source_type == "website" and direct_link and offer_evidence:
        # An official detail page that says "offer" but exposes no concrete benefit.
        content_type = "uncertain"
        confidence = "low"
        review_reasons.append("official_offer_without_detected_benefit")
    elif primary != "other":
        content_type = "product_post"
        confidence = "high" if category_evidence else "medium"
    elif awareness_evidence:
        content_type = "awareness"
    else:
        content_type = "general_post" if source_type == "social" else "uncertain"
        confidence = "medium" if source_type == "social" else "low"
        if content_type == "uncertain":
            review_reasons.append("unable_to_classify")

    if source_type == "website" and not direct_link:
        review_reasons.append("general_offer_page_link")
        confidence = "low"
        if content_type in {"offer", "partner_offer"}:
            content_type = "uncertain"

    return {
        "primary_category": primary,
        "categories": categories,
        "benefit_types": benefit_ids,
        "content_type": content_type,
        "confidence": confidence,
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
        "classification_evidence": (category_evidence + benefit_evidence + partner_evidence + offer_evidence)[:20],
    }


def best_anchor_content(anchor: Any) -> tuple[str, str, Any]:
    anchor_text = clean_text(anchor.get_text(" ", strip=True), 180)
    title_attr = clean_text(anchor.get("title") or anchor.get("aria-label"), 180)
    chosen_parent = anchor.parent
    for parent in list(anchor.parents)[:5]:
        text = clean_text(parent.get_text(" ", strip=True), 650)
        if 20 <= len(text) <= 650:
            chosen_parent = parent
            if parent.find(re.compile(r"^h[1-6]$")):
                break
    context = clean_text(chosen_parent.get_text(" ", strip=True), 500) if chosen_parent else anchor_text
    heading = ""
    if chosen_parent:
        heading_tag = chosen_parent.find(re.compile(r"^h[1-6]$"))
        if heading_tag:
            heading = clean_text(heading_tag.get_text(" ", strip=True), 180)
    title = next(
        (item for item in (heading, title_attr, anchor_text) if item and item.casefold().strip(" .:-") not in GENERIC_LINK_TEXT and len(item) >= 3),
        "",
    )
    if not title:
        title = context[:180] if context else "Offer"
    snippet = context if context and context != title else ""
    return clean_text(title, 180), clean_text(snippet, 500), chosen_parent


def media_type_from_url(url: str, hinted_type: str = "") -> str:
    hinted = hinted_type.casefold()
    if "video" in hinted:
        return "video"
    if "image" in hinted:
        return "image"
    suffix = Path(urlsplit(url).path).suffix.casefold()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    guessed, _ = mimetypes.guess_type(url)
    return "video" if guessed and guessed.startswith("video/") else "image"


def extract_media_from_html(node: Any, base_url: str) -> dict[str, str] | None:
    if not node:
        return None
    video = node.find("video") if hasattr(node, "find") else None
    if video:
        source = video.get("src")
        if not source:
            source_tag = video.find("source", src=True)
            source = source_tag.get("src") if source_tag else None
        media_url = canonical_url(base_url, source or "")
        if media_url:
            poster = canonical_url(base_url, video.get("poster") or "")
            return {"url": media_url, "type": "video", "thumbnail_url": poster or ""}
    image = node.find("img") if hasattr(node, "find") else None
    if image:
        source = image.get("src") or image.get("data-src") or image.get("data-lazy-src") or image.get("data-original")
        if not source and image.get("srcset"):
            source = image.get("srcset").split(",")[-1].strip().split(" ")[0]
        media_url = canonical_url(base_url, source or "")
        if media_url:
            return {"url": media_url, "type": "image", "thumbnail_url": media_url}
    return None


def extract_date_from_html(node: Any) -> str | None:
    if not node:
        return None
    time_tag = node.find("time") if hasattr(node, "find") else None
    candidates = []
    if time_tag:
        candidates.extend([time_tag.get("datetime"), time_tag.get_text(" ", strip=True)])
    text = clean_text(node.get_text(" ", strip=True), 800) if hasattr(node, "get_text") else ""
    candidates.extend(re.findall(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", text))
    candidates.extend(re.findall(r"\b\d{1,2}[-/]\d{1,2}[-/]20\d{2}\b", text))
    for value in candidates:
        parsed = parse_date_text(value)
        if parsed:
            return parsed
    return None


def parse_date_text(value: str | None) -> str | None:
    value = clean_text(value)
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return isoformat(parsed)
    except (TypeError, ValueError, OverflowError):
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return isoformat(datetime.strptime(value[:10], fmt).replace(tzinfo=timezone.utc))
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return isoformat(parsed)
    except (TypeError, ValueError):
        return None


def is_direct_detail_link(link: str, offers_url: str, source: dict[str, Any]) -> bool:
    canonical_link = canonical_url(link, link)
    canonical_offers = canonical_url(offers_url, offers_url)
    if not canonical_link or not canonical_offers or canonical_link == canonical_offers:
        return False
    patterns = source.get("detail_link_patterns", [])
    link_parts = urlsplit(canonical_link)
    offer_parts = urlsplit(canonical_offers)
    if patterns:
        if any(re.search(pattern, canonical_link, re.IGNORECASE) for pattern in patterns):
            return True
        return False
    if link_parts.query and link_parts.query != offer_parts.query:
        return True
    offer_path = offer_parts.path.rstrip("/")
    link_path = link_parts.path.rstrip("/")
    if offer_path and link_path.startswith(offer_path + "/"):
        return True
    return link_path not in {"", "/", offer_path}


def website_items(session: requests.Session, competitor: dict[str, Any], source: dict[str, Any], config: dict[str, Any], now_iso: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_key = f"website:{competitor['id']}:{source['id']}"
    status = {
        "source_key": source_key, "competitor_id": competitor["id"], "source_type": "website",
        "platform": "website", "url": source["url"], "checked_at": now_iso,
        "success": False, "item_count": 0, "review_count": 0, "skipped_general_links": 0, "error": None,
    }
    try:
        response = session.get(source["url"], timeout=int(config["settings"].get("request_timeout_seconds", 25)))
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        base_canonical = canonical_url(source["url"], source["url"])
        source_host = normalized_host(source["url"])
        link_keywords = [word.casefold() for word in source.get("link_keywords", [])]
        exclude_keywords = [word.casefold() for word in source.get("exclude_keywords", [])]
        allow_external = bool(source.get("allow_external_links", False))
        require_direct = bool(source.get("require_detail_link", True))
        found: dict[str, dict[str, Any]] = {}

        for anchor in soup.find_all("a", href=True):
            link = canonical_url(source["url"], anchor.get("href", ""))
            if not link or link == base_canonical:
                continue
            if not allow_external and normalized_host(link) != source_host:
                continue
            title, snippet, context_node = best_anchor_content(anchor)
            combined = f"{link} {title} {snippet}".casefold()
            if exclude_keywords and any(keyword in combined for keyword in exclude_keywords):
                continue
            if link_keywords and not any(keyword in combined for keyword in link_keywords):
                continue

            direct_link = is_direct_detail_link(link, competitor.get("offers_url") or source["url"], source)
            if require_direct and not direct_link:
                status["skipped_general_links"] += 1
                continue
            classification = classify_content(f"{title} {snippet}", link, "website", direct_link, config)
            media = extract_media_from_html(context_node, source["url"])
            item = {
                "id": digest(competitor["id"], "website", link),
                "source_key": source_key,
                "source_type": "website",
                "platform": "website",
                "competitor_id": competitor["id"],
                "title": title,
                "snippet": snippet,
                "link": link,
                "direct_link": direct_link,
                "published_at": extract_date_from_html(context_node),
                "media": media,
                **classification,
            }
            current = found.get(link)
            if not current or len(item["snippet"]) > len(current["snippet"]):
                found[link] = item

        limit = int(config["settings"].get("max_items_per_source", 80))
        items = list(found.values())[:limit]
        status.update(success=True, item_count=len(items), review_count=sum(1 for item in items if item["review_required"]))
        return items, status
    except Exception as exc:
        status["error"] = clean_text(f"{type(exc).__name__}: {exc}", 500)
        return [], status


def xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def xml_child_text(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if xml_local_name(child.tag) in names:
            text = " ".join(part for part in child.itertext())
            if clean_text(text):
                return clean_text(text)
    return ""


def xml_child_markup(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if xml_local_name(child.tag) in names:
            raw_text = child.text or ""
            if "<" in raw_text and ">" in raw_text:
                return raw_text
            inner = "".join(ET.tostring(grandchild, encoding="unicode", method="xml") for grandchild in list(child))
            return inner or raw_text
    return ""


def extract_feed_media(node: ET.Element, summary_markup: str, base_url: str) -> dict[str, str] | None:
    candidates: list[tuple[str, str, str]] = []
    for descendant in node.iter():
        name = xml_local_name(descendant.tag)
        if name not in {"content", "thumbnail", "enclosure", "image"}:
            continue
        url = clean_text(descendant.attrib.get("url") or descendant.attrib.get("href") or descendant.attrib.get("src"))
        media_type = clean_text(descendant.attrib.get("type") or descendant.attrib.get("medium"))
        if url:
            candidates.append((url, media_type, ""))
    if summary_markup:
        soup = BeautifulSoup(summary_markup, "html.parser")
        video = soup.find("video") or soup.find("source")
        if video:
            candidates.insert(0, (video.get("src") or "", "video", video.get("poster") or ""))
        image = soup.find("img")
        if image:
            candidates.append((image.get("src") or image.get("data-src") or "", "image", ""))
    for raw_url, hinted_type, poster in candidates:
        media_url = canonical_url(base_url, raw_url)
        if not media_url:
            continue
        poster_url = canonical_url(base_url, poster) if poster else ""
        media_type = media_type_from_url(media_url, hinted_type)
        return {"url": media_url, "type": media_type, "thumbnail_url": poster_url or (media_url if media_type == "image" else "")}
    return None


def parse_feed_entries(content: bytes, feed_url: str) -> list[dict[str, Any]]:
    root = ET.fromstring(content)
    root_name = xml_local_name(root.tag)
    entry_nodes = [node for node in root.iter() if xml_local_name(node.tag) == ("item" if root_name in {"rss", "rdf"} else "entry")]
    entries: list[dict[str, Any]] = []
    for node in entry_nodes:
        link = ""
        for child in list(node):
            if xml_local_name(child.tag) != "link":
                continue
            candidate = clean_text(child.attrib.get("href")) or clean_text(" ".join(child.itertext()))
            rel = clean_text(child.attrib.get("rel")).casefold()
            if candidate and (not rel or rel == "alternate"):
                link = candidate
                break
        if not link:
            link = xml_child_text(node, {"guid", "id"})
        title = xml_child_text(node, {"title"})
        summary_markup = xml_child_markup(node, {"summary", "description", "content", "encoded"})
        summary = html_to_text(summary_markup or xml_child_text(node, {"summary", "description", "content", "encoded"}), 500)
        date_value = xml_child_text(node, {"pubdate", "published", "updated", "date"})
        entries.append({
            "link": link,
            "title": title,
            "summary": summary,
            "published_at": parse_date_text(date_value),
            "media": extract_feed_media(node, summary_markup, feed_url),
        })
    return entries


def social_items(session: requests.Session, competitor: dict[str, Any], platform: str, rss_url: str, config: dict[str, Any], now_iso: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_key = f"social:{competitor['id']}:{platform}"
    status = {
        "source_key": source_key, "competitor_id": competitor["id"], "source_type": "social",
        "platform": platform, "url": rss_url, "checked_at": now_iso,
        "success": False, "item_count": 0, "review_count": 0, "error": None,
    }
    if not rss_url:
        status["error"] = "RSS URL is empty"
        return [], status
    try:
        response = session.get(rss_url, timeout=int(config["settings"].get("request_timeout_seconds", 25)))
        response.raise_for_status()
        entries = parse_feed_entries(response.content, rss_url)
        items: list[dict[str, Any]] = []
        limit = int(config["settings"].get("max_items_per_source", 80))
        for entry in entries[:limit]:
            link = canonical_url(rss_url, entry.get("link", ""))
            if not link:
                continue
            title = clean_text(entry.get("title") or "Social post", 180)
            snippet = clean_text(entry.get("summary"), 500)
            classification = classify_content(f"{title} {snippet}", link, "social", True, config)
            items.append({
                "id": digest(competitor["id"], platform, link),
                "source_key": source_key,
                "source_type": "social",
                "platform": platform,
                "competitor_id": competitor["id"],
                "title": title,
                "snippet": snippet,
                "link": link,
                "direct_link": True,
                "published_at": entry.get("published_at"),
                "media": entry.get("media"),
                **classification,
            })
        status.update(success=True, item_count=len(items), review_count=sum(1 for item in items if item["review_required"]))
        return items, status
    except Exception as exc:
        status["error"] = clean_text(f"{type(exc).__name__}: {exc}", 500)
        return [], status


def public_competitors(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "id": item["id"],
        "name_ar": item["name_en"],  # Brand names remain English in both languages.
        "name_en": item["name_en"],
        "website": item.get("website"),
        "offers_url": item.get("offers_url"),
    } for item in config["competitors"]]


def public_taxonomy(config: dict[str, Any], key: str) -> list[dict[str, Any]]:
    return [{
        "id": item["id"], "name_ar": item["name_ar"], "name_en": item["name_en"],
        "priority": item.get("priority", 999),
    } for item in config[key]]


def event_snapshot(item: dict[str, Any], at: str, event_type: str, version: int) -> dict[str, Any]:
    return {
        "at": at,
        "type": event_type,
        "version": version,
        "title": item.get("title"),
        "content_type": item.get("content_type"),
        "primary_category": item.get("primary_category"),
        "benefit_types": item.get("benefit_types", []),
        "direct_link": item.get("direct_link", False),
    }


def reconcile_state(state: dict[str, Any], collected: list[dict[str, Any]], statuses: list[dict[str, Any]], config: dict[str, Any], now: datetime) -> dict[str, Any]:
    now_iso = isoformat(now)
    previous_schema = int(state.get("schema_version", 0) or 0)
    migration = previous_schema < 3
    state_items: dict[str, dict[str, Any]] = state.setdefault("items", {})
    initial_baseline = not bool(state_items)
    successful_sources = {row["source_key"] for row in statuses if row.get("success")}
    seen_ids: set[str] = set()

    for item in collected:
        item_id = item["id"]
        seen_ids.add(item_id)
        content_hash = digest(
            item.get("title"), item.get("snippet"), item.get("content_type"),
            item.get("primary_category"), ",".join(item.get("categories", [])),
            ",".join(item.get("benefit_types", [])), item.get("direct_link"),
            item.get("media", {}).get("url") if item.get("media") else "",
            length=32,
        )
        previous = state_items.get(item_id)
        if not previous:
            version = 1
            history = [event_snapshot(item, now_iso, "baseline" if initial_baseline else "detected", version)]
            state_items[item_id] = {
                **item,
                "content_hash": content_hash,
                "first_seen": now_iso,
                "last_seen": now_iso,
                "last_changed": now_iso,
                "version": version,
                "active": True,
                "miss_count": 0,
                "baseline_import": initial_baseline,
                "change_history": history,
            }
            continue

        # During schema migration, preserve timestamps and avoid announcing every item as updated.
        changed = not migration and previous.get("content_hash") != content_hash
        reactivated = previous.get("active") is False
        version = int(previous.get("version", 1)) + (1 if changed else 0)
        history = list(previous.get("change_history", []))
        if changed:
            history.append(event_snapshot(item, now_iso, "updated", version))
        elif reactivated:
            history.append(event_snapshot(item, now_iso, "reactivated", version))
        history = history[-30:]
        state_items[item_id] = {
            **previous,
            **item,
            "content_hash": content_hash,
            "first_seen": previous.get("first_seen") or now_iso,
            "last_seen": now_iso,
            "last_changed": now_iso if changed else previous.get("last_changed") or previous.get("first_seen") or now_iso,
            "version": max(version, 1),
            "active": True,
            "miss_count": 0,
            "baseline_import": bool(previous.get("baseline_import", False)),
            "change_history": history,
        }

    inactive_after = int(config["settings"].get("inactive_after_missed_runs", 3))
    for item_id, previous in list(state_items.items()):
        if item_id in seen_ids or previous.get("source_key") not in successful_sources:
            continue
        misses = int(previous.get("miss_count", 0)) + 1
        previous["miss_count"] = misses
        if misses >= inactive_after and previous.get("active", True):
            previous["active"] = False
            previous.setdefault("change_history", []).append(event_snapshot(previous, now_iso, "inactive", int(previous.get("version", 1))))
            previous["change_history"] = previous["change_history"][-30:]

    retention_cutoff = now - timedelta(days=int(config["settings"].get("history_retention_days", 365)))
    for item_id, previous in list(state_items.items()):
        last_seen = parse_iso(previous.get("last_seen")) or parse_iso(previous.get("first_seen"))
        if previous.get("active") is False and last_seen and last_seen < retention_cutoff:
            del state_items[item_id]

    state["schema_version"] = 3
    state["updated_at"] = now_iso
    return state


def output_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    hidden = {"content_hash", "miss_count"}
    items = [{key: value for key, value in row.items() if key not in hidden} for row in state.get("items", {}).values()]
    items.sort(key=lambda row: (
        bool(row.get("active")),
        parse_iso(row.get("published_at")) or parse_iso(row.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc),
    ), reverse=True)
    return items


def item_activity_date(item: dict[str, Any]) -> datetime | None:
    published = parse_iso(item.get("published_at"))
    if published:
        return published
    # Initial website imports have unknown campaign dates and must not be plotted as today's activity.
    if item.get("source_type") == "website" and int(item.get("version", 1)) <= 1:
        return None
    if item.get("baseline_import"):
        return None
    return parse_iso(item.get("last_changed"))


def build_stats(items: list[dict[str, Any]], statuses: list[dict[str, Any]], config: dict[str, Any], now: datetime) -> dict[str, Any]:
    active = [row for row in items if row.get("active", True)]
    last_7 = now - timedelta(days=7)
    last_30 = now - timedelta(days=30)
    confirmed = [row for row in active if row.get("source_type") == "website" and row.get("content_type") == "offer" and row.get("direct_link")]
    partner = [row for row in active if row.get("source_type") == "website" and row.get("content_type") == "partner_offer" and row.get("direct_link")]
    social_7 = [row for row in active if row.get("source_type") == "social" and (item_activity_date(row) or datetime.min.replace(tzinfo=timezone.utc)) >= last_7]
    activity_30 = [row for row in active if (item_activity_date(row) or datetime.min.replace(tzinfo=timezone.utc)) >= last_30]
    return {
        "total_history": len(items),
        "active_items": len(active),
        "confirmed_offers": len(confirmed),
        "partner_offers": len(partner),
        "social_posts_7d": len(social_7),
        "activity_30d": len(activity_30),
        "review_required": sum(1 for row in active if row.get("review_required")),
        "healthy_sources": sum(1 for row in statuses if row.get("success")),
        "failed_sources": sum(1 for row in statuses if not row.get("success")),
        "total_sources": len(statuses),
    }


def run(config: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    now_iso = isoformat(now)
    session = make_session()
    collected: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    for competitor in config["competitors"]:
        for source in competitor.get("website_sources", []):
            items, status = website_items(session, competitor, source, config, now_iso)
            collected.extend(items)
            statuses.append(status)
            print(f"[{'OK' if status['success'] else 'FAILED'}] {status['source_key']}: {status['item_count']} items")
            if status.get("error"):
                print(f"       {status['error']}")
        for platform, rss_url in competitor.get("social_feeds", {}).items():
            items, status = social_items(session, competitor, platform, rss_url, config, now_iso)
            collected.extend(items)
            statuses.append(status)
            print(f"[{'OK' if status['success'] else 'FAILED'}] {status['source_key']}: {status['item_count']} items")
            if status.get("error"):
                print(f"       {status['error']}")

    deduped: dict[str, dict[str, Any]] = {}
    for item in collected:
        previous = deduped.get(item["id"])
        if not previous or len(item.get("snippet", "")) > len(previous.get("snippet", "")):
            deduped[item["id"]] = item

    state = load_json(STATE_PATH, {"schema_version": 3, "items": {}})
    state = reconcile_state(state, list(deduped.values()), statuses, config, now)
    save_json_atomic(STATE_PATH, state)
    items = output_items(state)
    data = {
        "schema_version": 3,
        "generated_at": now_iso,
        "new_badge_hours": int(config["settings"].get("new_badge_hours", 24)),
        "competitors": public_competitors(config),
        "categories": public_taxonomy(config, "categories"),
        "benefit_types": public_taxonomy(config, "benefit_types"),
        "content_types": config.get("content_types", []),
        "source_status": statuses,
        "stats": build_stats(items, statuses, config, now),
        "items": items,
    }
    save_json_atomic(DATA_PATH, data)
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect competitor intelligence and publish data.json")
    parser.add_argument("--validate-only", action="store_true", help="Validate config.json without network calls")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        config = load_json(CONFIG_PATH, None)
        if not isinstance(config, dict):
            raise ValueError("config.json is missing or invalid")
        validate_config(config)
        if args.validate_only:
            print("Configuration is valid.")
            return 0
        data = run(config)
        print(
            f"Finished: {data['stats']['confirmed_offers']} confirmed offers, "
            f"{data['stats']['partner_offers']} partner offers, "
            f"{data['stats']['social_posts_7d']} social posts in 7 days."
        )
        return 0
    except Exception as exc:
        print(f"Fatal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
