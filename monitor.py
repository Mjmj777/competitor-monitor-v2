"""Competitor intelligence collector.

Collects official offer pages and RSS feeds, classifies each item, keeps history,
and generates ``data.json`` for the bilingual GitHub Pages dashboard.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
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
    "Chrome/150.0 Safari/537.36 CompetitorMonitor/2.0"
)

TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}

GENERIC_LINK_TEXT = {
    "view details",
    "learn more",
    "read more",
    "explore more",
    "open",
    "اعرف المزيد",
    "اعرف أكثر",
    "استكشف المزيد",
    "عرض التفاصيل",
    "تفاصيل العرض",
    "المزيد",
}


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
        lower_key = key.casefold()
        if lower_key.startswith("utm_") or lower_key in TRACKING_QUERY_KEYS:
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

    competitor_ids = [item.get("id") for item in competitors]
    category_ids = [item.get("id") for item in categories]

    if not competitors:
        errors.append("config.competitors is empty")
    if not categories:
        errors.append("config.categories is empty")
    if len(competitor_ids) != len(set(competitor_ids)):
        errors.append("competitor IDs must be unique")
    if len(category_ids) != len(set(category_ids)):
        errors.append("category IDs must be unique")
    if "other" not in category_ids:
        errors.append("an 'other' category is required")

    for competitor in competitors:
        if not competitor.get("id") or not competitor.get("name_ar") or not competitor.get("name_en"):
            errors.append(f"invalid competitor entry: {competitor!r}")
        for source in competitor.get("website_sources", []):
            if not source.get("id") or not source.get("url"):
                errors.append(f"invalid website source for {competitor.get('id')}")

    if errors:
        raise ValueError("; ".join(errors))


def keyword_matches(text: str, keywords: list[str]) -> list[str]:
    normalized = text.casefold()
    return [keyword for keyword in keywords if keyword.casefold() in normalized]


def classify_item(
    text: str,
    url: str,
    categories: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
) -> tuple[str, list[str], bool, list[str]]:
    combined = f"{text} {url}".casefold()

    for override in overrides:
        needle = clean_text(override.get("link_contains")).casefold()
        category_id = override.get("category_id")
        if needle and needle in url.casefold() and category_id:
            category = next((item for item in categories if item["id"] == category_id), None)
            if category:
                return category_id, [category_id], bool(category.get("strategic")), [f"override:{needle}"]

    matches: list[tuple[dict[str, Any], list[str], float]] = []
    for category in categories:
        if category.get("id") == "other":
            continue
        found = keyword_matches(combined, category.get("keywords", []))
        if not found:
            continue
        specificity = sum(len(item) for item in found) / 1000
        score = len(found) + specificity
        matches.append((category, found, score))

    if not matches:
        other = next(item for item in categories if item["id"] == "other")
        return "other", ["other"], bool(other.get("strategic")), []

    matches.sort(key=lambda row: row[0].get("priority", 999))
    category_ids = [row[0]["id"] for row in matches]
    primary = category_ids[0]
    strategic = any(bool(row[0].get("strategic")) for row in matches)
    evidence = [keyword for _, found, _ in matches for keyword in found][:12]
    return primary, category_ids, strategic, evidence


def best_anchor_content(anchor: Any) -> tuple[str, str]:
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

    candidates = [heading, title_attr, anchor_text]
    title = next(
        (
            item
            for item in candidates
            if item and item.casefold().strip(" .:-") not in GENERIC_LINK_TEXT and len(item) >= 3
        ),
        "",
    )
    if not title:
        title = context[:180] if context else "Offer"

    snippet = context if context and context != title else ""
    return clean_text(title, 180), clean_text(snippet, 500)


def website_items(
    session: requests.Session,
    competitor: dict[str, Any],
    source: dict[str, Any],
    config: dict[str, Any],
    now_iso: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_key = f"website:{competitor['id']}:{source['id']}"
    timeout = int(config["settings"].get("request_timeout_seconds", 25))
    status = {
        "source_key": source_key,
        "competitor_id": competitor["id"],
        "source_type": "website",
        "platform": "website",
        "url": source["url"],
        "checked_at": now_iso,
        "success": False,
        "item_count": 0,
        "error": None,
    }

    try:
        response = session.get(source["url"], timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        base_canonical = canonical_url(source["url"], source["url"])
        source_host = normalized_host(source["url"])
        link_keywords = [item.casefold() for item in source.get("link_keywords", [])]
        exclude_keywords = [item.casefold() for item in source.get("exclude_keywords", [])]
        allow_external = bool(source.get("allow_external_links", False))
        found: dict[str, dict[str, Any]] = {}

        for anchor in soup.find_all("a", href=True):
            link = canonical_url(source["url"], anchor.get("href", ""))
            if not link or link == base_canonical:
                continue
            if not allow_external and normalized_host(link) != source_host:
                continue

            title, snippet = best_anchor_content(anchor)
            combined = f"{link} {title} {snippet}".casefold()
            if exclude_keywords and any(keyword in combined for keyword in exclude_keywords):
                continue
            if link_keywords and not any(keyword in combined for keyword in link_keywords):
                continue

            primary, category_ids, strategic, evidence = classify_item(
                f"{title} {snippet}",
                link,
                config["categories"],
                config.get("category_overrides", []),
            )
            item = {
                "id": digest(competitor["id"], "website", link),
                "source_key": source_key,
                "source_type": "website",
                "platform": "website",
                "competitor_id": competitor["id"],
                "title": title,
                "snippet": snippet,
                "link": link,
                "published_at": None,
                "primary_category": primary,
                "categories": category_ids,
                "strategic": strategic,
                "classification_evidence": evidence,
            }
            current = found.get(link)
            if not current or len(item["snippet"]) > len(current["snippet"]):
                found[link] = item

        limit = int(config["settings"].get("max_items_per_source", 80))
        items = list(found.values())[:limit]
        status.update(success=True, item_count=len(items))
        return items, status
    except Exception as exc:  # keep other sources running
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


def parse_feed_date(value: str | None) -> str | None:
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
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return isoformat(parsed)
    except (TypeError, ValueError):
        return None


def parse_feed_entries(content: bytes) -> list[dict[str, str | None]]:
    root = ET.fromstring(content)
    root_name = xml_local_name(root.tag)
    entry_nodes: list[ET.Element]
    if root_name in {"rss", "rdf"}:
        entry_nodes = [node for node in root.iter() if xml_local_name(node.tag) == "item"]
    else:
        entry_nodes = [node for node in root.iter() if xml_local_name(node.tag) == "entry"]

    entries: list[dict[str, str | None]] = []
    for node in entry_nodes:
        link = ""
        for child in list(node):
            if xml_local_name(child.tag) != "link":
                continue
            href = clean_text(child.attrib.get("href"))
            rel = clean_text(child.attrib.get("rel")).casefold()
            text = clean_text(" ".join(child.itertext()))
            candidate = href or text
            if candidate and (not rel or rel == "alternate"):
                link = candidate
                break
        if not link:
            link = xml_child_text(node, {"guid", "id"})

        title = xml_child_text(node, {"title"})
        summary = xml_child_text(node, {"summary", "description", "content", "encoded"})
        date_value = xml_child_text(node, {"pubdate", "published", "updated", "date"})
        entries.append({
            "link": link,
            "title": title,
            "summary": summary,
            "published_at": parse_feed_date(date_value),
        })
    return entries


def social_items(
    session: requests.Session,
    competitor: dict[str, Any],
    platform: str,
    rss_url: str,
    config: dict[str, Any],
    now_iso: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_key = f"social:{competitor['id']}:{platform}"
    timeout = int(config["settings"].get("request_timeout_seconds", 25))
    status = {
        "source_key": source_key,
        "competitor_id": competitor["id"],
        "source_type": "social",
        "platform": platform,
        "url": rss_url,
        "checked_at": now_iso,
        "success": False,
        "item_count": 0,
        "error": None,
    }

    if not rss_url:
        status["error"] = "RSS URL is empty"
        return [], status

    try:
        response = session.get(rss_url, timeout=timeout)
        response.raise_for_status()
        parsed_entries = parse_feed_entries(response.content)

        items: list[dict[str, Any]] = []
        limit = int(config["settings"].get("max_items_per_source", 80))
        for entry in parsed_entries[:limit]:
            link = canonical_url(rss_url, entry.get("link", ""))
            if not link:
                continue
            title = clean_text(entry.get("title") or "Social post", 180)
            snippet = html_to_text(entry.get("summary"), 500)
            primary, category_ids, strategic, evidence = classify_item(
                f"{title} {snippet}",
                link,
                config["categories"],
                config.get("category_overrides", []),
            )
            items.append(
                {
                    "id": digest(competitor["id"], platform, link),
                    "source_key": source_key,
                    "source_type": "social",
                    "platform": platform,
                    "competitor_id": competitor["id"],
                    "title": title,
                    "snippet": snippet,
                    "link": link,
                    "published_at": entry.get("published_at"),
                    "primary_category": primary,
                    "categories": category_ids,
                    "strategic": strategic,
                    "classification_evidence": evidence,
                }
            )

        status.update(success=True, item_count=len(items))
        return items, status
    except Exception as exc:  # keep other sources running
        status["error"] = clean_text(f"{type(exc).__name__}: {exc}", 500)
        return [], status


def public_competitors(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "name_ar": item["name_ar"],
            "name_en": item["name_en"],
            "website": item.get("website"),
            "offers_url": item.get("offers_url"),
        }
        for item in config["competitors"]
    ]


def public_categories(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "name_ar": item["name_ar"],
            "name_en": item["name_en"],
            "strategic": bool(item.get("strategic")),
            "priority": item.get("priority", 999),
        }
        for item in config["categories"]
    ]


def reconcile_state(
    state: dict[str, Any],
    collected: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    config: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    now_iso = isoformat(now)
    state.setdefault("schema_version", 2)
    state_items: dict[str, dict[str, Any]] = state.setdefault("items", {})
    successful_sources = {item["source_key"] for item in statuses if item.get("success")}
    seen_ids: set[str] = set()

    for item in collected:
        item_id = item["id"]
        seen_ids.add(item_id)
        content_hash = digest(
            item.get("title"),
            item.get("snippet"),
            item.get("primary_category"),
            ",".join(item.get("categories", [])),
            length=32,
        )
        previous = state_items.get(item_id, {})
        changed = not previous or previous.get("content_hash") != content_hash
        first_seen = previous.get("first_seen") or now_iso
        last_changed = now_iso if changed else previous.get("last_changed") or first_seen
        version = int(previous.get("version", 0)) + (1 if changed else 0)

        state_items[item_id] = {
            **item,
            "content_hash": content_hash,
            "first_seen": first_seen,
            "last_seen": now_iso,
            "last_changed": last_changed,
            "version": max(version, 1),
            "active": True,
            "miss_count": 0,
        }

    inactive_after = int(config["settings"].get("inactive_after_missed_runs", 3))
    for item_id, previous in list(state_items.items()):
        if item_id in seen_ids:
            continue
        if previous.get("source_key") not in successful_sources:
            continue
        misses = int(previous.get("miss_count", 0)) + 1
        previous["miss_count"] = misses
        if misses >= inactive_after:
            previous["active"] = False

    retention_days = int(config["settings"].get("history_retention_days", 365))
    retention_cutoff = now - timedelta(days=retention_days)
    for item_id, previous in list(state_items.items()):
        last_seen = parse_iso(previous.get("last_seen")) or parse_iso(previous.get("first_seen"))
        if previous.get("active", True) is False and last_seen and last_seen < retention_cutoff:
            del state_items[item_id]

    state["updated_at"] = now_iso
    return state


def output_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    fields_to_hide = {"content_hash", "miss_count"}
    items = [
        {key: value for key, value in item.items() if key not in fields_to_hide}
        for item in state.get("items", {}).values()
    ]
    items.sort(
        key=lambda item: (
            bool(item.get("active")),
            parse_iso(item.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return items


def build_stats(items: list[dict[str, Any]], statuses: list[dict[str, Any]], config: dict[str, Any], now: datetime) -> dict[str, Any]:
    new_hours = int(config["settings"].get("new_badge_hours", 24))
    new_cutoff = now - timedelta(hours=new_hours)
    active = [item for item in items if item.get("active", True)]
    return {
        "total_history": len(items),
        "active_items": len(active),
        "strategic_active_items": sum(1 for item in active if item.get("strategic")),
        "new_or_updated_items": sum(
            1
            for item in active
            if (parse_iso(item.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc)) >= new_cutoff
        ),
        "healthy_sources": sum(1 for item in statuses if item.get("success")),
        "failed_sources": sum(1 for item in statuses if not item.get("success")),
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
            label = "OK" if status["success"] else "FAILED"
            print(f"[{label}] {status['source_key']}: {status['item_count']} items")
            if status.get("error"):
                print(f"       {status['error']}")

        for platform, rss_url in competitor.get("social_feeds", {}).items():
            items, status = social_items(session, competitor, platform, rss_url, config, now_iso)
            collected.extend(items)
            statuses.append(status)
            label = "OK" if status["success"] else "FAILED"
            print(f"[{label}] {status['source_key']}: {status['item_count']} items")
            if status.get("error"):
                print(f"       {status['error']}")

    # Dedupe by stable ID, preferring richer content.
    deduped: dict[str, dict[str, Any]] = {}
    for item in collected:
        previous = deduped.get(item["id"])
        if not previous or len(item.get("snippet", "")) > len(previous.get("snippet", "")):
            deduped[item["id"]] = item

    state = load_json(STATE_PATH, {"schema_version": 2, "items": {}})
    state = reconcile_state(state, list(deduped.values()), statuses, config, now)
    save_json_atomic(STATE_PATH, state)

    items = output_items(state)
    data = {
        "schema_version": 2,
        "generated_at": now_iso,
        "new_badge_hours": int(config["settings"].get("new_badge_hours", 24)),
        "default_strategic_only": bool(config["settings"].get("default_strategic_only", True)),
        "competitors": public_competitors(config),
        "categories": public_categories(config),
        "source_status": statuses,
        "stats": build_stats(items, statuses, config, now),
        "items": items,
    }
    save_json_atomic(DATA_PATH, data)
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect competitor offers and publish data.json")
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
            "Finished: "
            f"{data['stats']['active_items']} active items, "
            f"{data['stats']['strategic_active_items']} strategic, "
            f"{data['stats']['failed_sources']} failed sources."
        )
        return 0
    except Exception as exc:
        print(f"Fatal error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
