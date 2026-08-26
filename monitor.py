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
import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit, unquote

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


def response_text(response: requests.Response) -> str:
    """Decode HTML bytes without Requests' Latin-1 fallback corrupting Arabic.

    Several official sites, including Mobily Pay, return UTF-8 HTML without a
    charset in the HTTP Content-Type header. ``Response.text`` then historically
    falls back to ISO-8859-1, producing mojibake such as ``Ø¹Ø±ÙØ¶``. Prefer an
    explicitly declared charset, otherwise try UTF-8 before detector fallbacks.
    """
    raw = response.content
    content_type = response.headers.get("Content-Type", "")
    declared = re.search(r"charset\s*=\s*[\"']?([^\s;\"']+)", content_type, re.I)
    candidates = [declared.group(1) if declared else None, "utf-8-sig", response.apparent_encoding, response.encoding]
    tried: set[str] = set()
    for candidate in candidates:
        encoding = clean(candidate).casefold()
        if not encoding or encoding in tried:
            continue
        tried.add(encoding)
        try:
            return raw.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


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




_MOBILY_EXPIRED_PATH = re.compile(r"/(?:ar/)?(?:expired[-_]?offers?|expiredoffers?)/", re.I)
_MOBILY_CAMPAIGN_STRONG = (
    "تحويل دولي", "حوالة دولية", "الحوالات الدولية", "international transfer", "international transfers", "remittance",
    "كاش باك", "cashback", "cash back",
    "اكسب أميال", "أميال", "miles",
    "رسوم التحويل", "بدون رسوم", "صفر رسوم", "zero fee", "zero fees", "fee-free", "no fee",
    "راتب", "رواتب", "salary", "payroll",
    "مساند", "musaned", "سداد", "sadad",
    "اربح", "سحب", "جائزة", "جوائز", "win", "prize", "draw",
    "دعوة", "إحالة", "referral", "refer a friend",
)
_MOBILY_MERCHANT_PHRASES = (
    "خصم لدى", "خصم في", "خصم مع", "استمتع بخصم", "احصل على خصم", "استفد من خصم",
    "discount at", "discount with", "off at", "promo code", "promocode", "كود الخصم", "رمز الخصم", "استخدم الكود",
)

def mobily_offer_hint(title: str, snippet: str, link: str) -> str | None:
    """Deterministic first-pass type for Mobily Pay official offer cards.

    Mobily Pay mixes its own campaigns with third-party merchant discounts on the same
    Current Offers page. Strong product/campaign language wins; obvious retailer/partner
    discount language becomes Merchant. Ambiguous cards remain Needs Review for the
    later verifier/AI layer instead of inflating Campaign KPIs.
    """
    text = clean(f"{title} {snippet}", 5000).casefold()
    link_text = clean(link, 1000).casefold()
    if _MOBILY_EXPIRED_PATH.search(link_text):
        return "expired"

    # Competitor-owned promotional mechanics are campaigns even when the wording also
    # contains generic words such as discount/offer.
    if any(marker in text for marker in _MOBILY_CAMPAIGN_STRONG):
        return "campaign"

    # Typical Mobily partner offers are written as "discount at/with <merchant>" or
    # Arabic equivalents such as "خصم لدى" / "استمتع بخصم ... في".
    if any(marker in text for marker in _MOBILY_MERCHANT_PHRASES):
        return "merchant_offer"

    # A percentage discount tied to a named place/partner is also a strong merchant cue,
    # but only when no Mobily-owned campaign marker above was found.
    if re.search(r"(?:خصم|discount)\s*(?:حتى\s*)?\d{1,3}%", text, re.I) and re.search(r"(?:\sلدى\s|\sفي\s|\sمع\s|\sat\s|\swith\s)", text, re.I):
        return "merchant_offer"

    return None

def mobily_expired_candidate(anchor: Any, link: str, source: dict[str, Any]) -> bool:
    """Identify Mobily historical cards before they enter current discovery."""
    if _MOBILY_EXPIRED_PATH.search(clean(link, 1000)):
        return True
    markers = tuple(x.casefold() for x in (source.get("expired_headings") or _EXPIRED_HEADINGS))
    current_markers = ("أحدث العروض", "العروض المتاحة", "العروض الحالية", "current offers", "fresh offers", "latest offers")
    # Search farther back than the generic helper: Mobily's page can contain nested card
    # markup between the section heading and the anchor. Stop at the first recognized
    # current/expired section heading.
    for heading in anchor.find_all_previous(["h1","h2","h3","h4","h5","h6"], limit=24):
        label = clean(heading.get_text(" ", strip=True), 220).casefold()
        if any(marker in label for marker in markers):
            return True
        if any(marker in label for marker in current_markers):
            return False
    return False

def mobily_current_detail_link(link: str | None) -> bool:
    """Return True only for Mobily Pay's current official offer detail path."""
    if not link:
        return False
    try:
        path = (urlsplit(str(link)).path or "").casefold()
    except Exception:
        path = str(link).casefold()
    return bool(re.search(r"/(?:ar/)?offers/offer-[^/?#]+\.html$", path, re.I)) and not bool(_MOBILY_EXPIRED_PATH.search(path))

def mobily_card_title(anchor: Any, link: str) -> tuple[str, Any]:
    """Extract a current Mobily card title even when its heading is outside the CTA."""
    section_labels = {
        "تعرّف على أحدث العروض المتاحة", "تعرف على أحدث العروض المتاحة",
        "العروض المنتهية", "عروض منتهية", "expired offers", "previous offers",
        "offers", "العروض",
    }
    folded_labels = {value.casefold() for value in section_labels}
    for candidate in list(anchor.parents)[:9]:
        if getattr(candidate, "name", None) not in {"article", "li", "div", "section"}:
            continue
        live_links = []
        for child in candidate.find_all("a", href=True):
            candidate_url = canonical(link, child.get("href", ""))
            if mobily_current_detail_link(candidate_url):
                live_links.append(candidate_url)
        if len(set(live_links)) > 1:
            continue
        for node in candidate.find_all(["h1", "h2", "h3", "h4", "h5", "h6"], limit=4):
            title = strip_validity_prefix(clean(node.get_text(" ", strip=True), 220))
            if title and not generic_title(title) and title.casefold() not in folded_labels:
                return title, candidate
        image = candidate.find("img")
        if image is not None:
            title = strip_validity_prefix(clean(image.get("alt") or image.get("title"), 220))
            if title and not generic_title(title) and title.casefold() not in folded_labels:
                return title, candidate
    for node in anchor.find_all_previous(["h2", "h3", "h4", "h5", "h6"], limit=6):
        title = strip_validity_prefix(clean(node.get_text(" ", strip=True), 220))
        if title and not generic_title(title) and title.casefold() not in folded_labels:
            return title, anchor.parent or anchor
    match = re.search(r"offer-([^/?#]+)\.html$", urlsplit(link).path, re.I)
    suffix = clean(match.group(1) if match else digest(link, length=8), 40)
    return f"Mobily Pay offer {suffix}", anchor.parent or anchor

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


_BARQ_NON_TITLES = {
    "الشروط والأحكام", "الشروط والاحكام", "الأهلية", "الاهلية", "تفاصيل العرض",
    "مدة العرض", "رابط الموقع", "الجميع", "عروض", "offers", "terms and conditions",
}


def title_from_detail_url(link: str | None) -> str:
    """Best-effort fallback for sites whose CTA text is generic but detail URLs are unique."""
    if not link:
        return ""
    try:
        path = unquote(urlsplit(link).path or "").rstrip("/")
        slug = path.rsplit("/", 1)[-1]
        slug = re.sub(r"[-_]+", " ", slug)
        slug = clean(slug, 220)
        if not slug or generic_title(slug) or re.fullmatch(r"[0-9a-f-]{8,}", slug, re.I):
            return ""
        return slug
    except Exception:
        return ""


def meaningful_barq_title(anchor: Any, link: str) -> tuple[str, Any]:
    """Find the actual barq offer-card title instead of the generic `اعرف المزيد` CTA.

    barq's CTA can sit inside nested wrapper divs, so the first parent div is often too
    shallow. Walk up the card, prefer headings / early text nodes, then fall back to the
    detail URL slug.
    """
    ancestors = [a for a in list(anchor.parents)[:9] if getattr(a, "name", None) in {"article", "li", "div", "section"}]
    best_parent = ancestors[0] if ancestors else anchor

    # 1) A real heading anywhere in the nearest card ancestor is the strongest signal.
    for anc in ancestors:
        for h in anc.find_all(["h1", "h2", "h3", "h4", "h5", "h6"], limit=5):
            text = clean(h.get_text(" ", strip=True), 220)
            if text and not generic_title(text) and normalized_title(text) not in {normalized_title(x) for x in _BARQ_NON_TITLES}:
                return strip_validity_prefix(text), anc

    # 2) barq cards expose the title as an early text node even when no heading tag is used.
    for anc in ancestors:
        strings = []
        for raw in anc.stripped_strings:
            text = clean(raw, 220)
            key = normalized_title(text)
            if not text or generic_title(text) or key in {normalized_title(x) for x in _BARQ_NON_TITLES}:
                continue
            if text.casefold().startswith(("الشروط", "باستخدام هذا العرض", "بالاستفادة من هذا العرض")):
                continue
            strings.append(text)
            if len(strings) >= 8:
                break
        if strings:
            # Prefer an explicit offer/campaign label, otherwise the first meaningful card string.
            preferred = next((x for x in strings if re.search(r"(?:^|\s)(?:عرض|حملة)(?:\s|$)|(?:offer|campaign)", x, re.I)), strings[0])
            return strip_validity_prefix(preferred), anc

    # 3) Last resort: use the unique detail URL slug, never the CTA text.
    return strip_validity_prefix(title_from_detail_url(link)), best_parent


def invalid_discovered_website_item(row: dict[str, Any]) -> bool:
    """Rows created from a generic CTA are parser noise and must not survive in state."""
    if row.get("source_type") != "website" or not str(row.get("id") or "").startswith("detected:"):
        return False
    title = clean(row.get("title"), 220)
    return (not title) or generic_title(title) or normalized_title(title) == normalized_title("Discovered official offer")


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
    if (source.get("source_verification") or {}).get("verification_method") == "official_website_modal":
        for field in ("summary","snippet","start_date","end_date","date_evidence","evidence_snapshot","source_locator","source_detail_type","mechanic_tags","theme_tags"):
            if source.get(field) is not None:
                target[field] = source.get(field)
        target["source_verification"] = dict(source.get("source_verification") or {})
        target["verified"] = True
        if source.get("media"):
            target["media"] = source.get("media")


_AR_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_AR_MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4, "مايو": 5,
    "يونيو": 6, "يوليو": 7, "أغسطس": 8, "اغسطس": 8, "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10, "نوفمبر": 11, "ديسمبر": 12,
}
_EN_MONTHS = {
    "january":1,"jan":1,"february":2,"feb":2,"march":3,"mar":3,"april":4,"apr":4,
    "may":5,"june":6,"jun":6,"july":7,"jul":7,"august":8,"aug":8,"september":9,
    "sep":9,"sept":9,"october":10,"oct":10,"november":11,"nov":11,"december":12,"dec":12,
}
_DATE_TOKEN = r"(?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر)\s+20\d{2}|(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2},?\s+20\d{2}|20\d{2}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]20\d{2})"
_EXPIRED_HEADINGS = ("العروض المنتهية", "عروض منتهية", "expired offers", "previous offers", "past offers")


def parse_human_date(value: str | None) -> str | None:
    text = clean(value).translate(_AR_DIGIT_MAP).replace("،", " ")
    if not text:
        return None
    m = re.fullmatch(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if m:
        try: return iso(datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc))
        except ValueError: return None
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](20\d{2})", text)
    if m:
        try: return iso(datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)), tzinfo=timezone.utc))
        except ValueError: return None
    parts = text.casefold().replace(",", "").split()
    if len(parts) >= 3:
        # day month year (Arabic or English)
        try:
            day = int(parts[0]); year = int(parts[-1]); month_name = " ".join(parts[1:-1]).strip()
            month = _AR_MONTHS.get(month_name) or _EN_MONTHS.get(month_name)
            if month: return iso(datetime(year, month, day, tzinfo=timezone.utc))
        except Exception: pass
        # English month day year
        try:
            month = _EN_MONTHS.get(parts[0]); day = int(parts[1]); year = int(parts[-1])
            if month: return iso(datetime(year, month, day, tzinfo=timezone.utc))
        except Exception: pass
    return None


def listing_date_hints(text: str) -> tuple[str | None, str | None, str | None]:
    value = clean(text, 6000).translate(_AR_DIGIT_MAP)
    start = end = evidence = None
    time_suffix = r"(?:\s*,?\s*at\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?"
    ranges = [
        rf"(?:the\s+offer\s+is\s+)?(?:valid|available|campaign|offer|runs?)\s+(?:period\s+)?(?:from\s+)?({_DATE_TOKEN}){time_suffix}\s+(?:to|until|through|–|—|-)\s+({_DATE_TOKEN})",
        rf"(?:يسري\s+العرض|العرض\s+ساري|ساري|مدة\s+العرض|فترة\s+العرض)?\s*(?:من)\s+({_DATE_TOKEN})\s*(?:إلى|الى|و?حتى|ولغاية)\s+({_DATE_TOKEN})",
    ]
    for pattern in ranges:
        m = re.search(pattern, value, re.I)
        if m:
            start, end = parse_human_date(m.group(1)), parse_human_date(m.group(2)); evidence = clean(m.group(0), 500); break
    if not end:
        for pattern in [
            rf"(?:valid\s+(?:until|through)|ends?\s+(?:on)?|expires?\s+(?:on)?)\s*({_DATE_TOKEN})",
            rf"(?:ساري\s+حتى|يسري\s+حتى|ينتهي(?:\s+العرض)?(?:\s+في|\s+بتاريخ)?|تاريخ\s+انتهاء\s+العرض|حتى)\s*({_DATE_TOKEN})",
        ]:
            m = re.search(pattern, value, re.I)
            if m:
                end = parse_human_date(m.group(1)); evidence = evidence or clean(m.group(0), 500); break
    if not start:
        for pattern in [
            rf"(?:valid\s+from|starts?\s+(?:on|from)|available\s+from)\s*({_DATE_TOKEN})",
            rf"(?:ساري\s+من|يسري\s+العرض\s+من|يبدأ(?:\s+العرض)?(?:\s+من|\s+في)?|ابتداء(?:ً|ا)?\s+من|اعتبار(?:ًا|ا)?\s+من)\s*({_DATE_TOKEN})",
        ]:
            m = re.search(pattern, value, re.I)
            if m:
                start = parse_human_date(m.group(1)); evidence = evidence or clean(m.group(0), 500); break
    return start, end, evidence


def strip_validity_prefix(title: str) -> str:
    value = clean(title, 300)
    value = re.sub(r"^\s*valid\s+until\s+[^|–—:]+(?:20\d{2})?\s*", "", value, flags=re.I)
    return clean(value, 220) or clean(title, 220)


def expired_section(anchor: Any, source: dict[str, Any]) -> bool:
    markers = tuple(x.casefold() for x in (source.get("expired_headings") or _EXPIRED_HEADINGS))
    for heading in anchor.find_all_previous(["h1","h2","h3","h4","h5","h6"], limit=4):
        label = clean(heading.get_text(" ", strip=True), 200).casefold()
        if any(marker in label for marker in markers):
            return True
        # A current-offers heading before the expired heading means this anchor belongs to current offers.
        if any(x in label for x in ("أحدث العروض", "العروض المتاحة", "current offers", "fresh offers", "latest offers")):
            return False
    return False


def rendered_html(url: str, timeout_seconds: int) -> str:
    """Browser fallback for JS-heavy or WAF-sensitive offer indexes.

    Imported lazily so normal sources stay lightweight. GitHub Actions installs Chromium.
    """
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(user_agent=USER_AGENT, locale="ar-SA")
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
        try: page.wait_for_load_state("networkidle", timeout=min(timeout_seconds, 12) * 1000)
        except Exception: pass
        html = page.content()
        browser.close()
        return html



def tiqmo_modal_items(competitor: dict[str, Any], source: dict[str, Any], config: dict[str, Any], checked: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read tiqmo offer details from the official modal dialogs.

    tiqmo does not expose a stable detail URL for each offer. The official offers page
    opens a modal after clicking LEARN MORE. Each modal is therefore treated as the
    authoritative official detail source and is re-read on every scheduled source run.
    """
    from playwright.sync_api import sync_playwright

    key = f"website:{competitor['id']}:{source['id']}"
    status = {
        "source_key": key,
        "competitor_id": competitor["id"],
        "source_type": "website",
        "platform": "website",
        "url": source["url"],
        "checked_at": checked,
        "success": False,
        "item_count": 0,
        "error": None,
        "skipped_general_links": 0,
        "fetch_mode": "browser_modal",
        "verification_method": "official_website_modal",
    }
    timeout = int(config["settings"].get("browser_timeout_seconds", 25))
    cta_pattern = re.compile(r"^\s*(?:learn\s+more|view\s+details|offer\s+details|اعرف\s+المزيد|استكشف\s+المزيد|التفاصيل)\s*$", re.I)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def card_title_for(locator) -> str:
        try:
            value = locator.evaluate("""el => {
              let node = el;
              for (let i = 0; i < 7 && node; i++, node = node.parentElement) {
                const h = node.querySelector && node.querySelector('h1,h2,h3,h4,h5,h6');
                if (h && h.innerText && h.innerText.trim()) return h.innerText.trim();
              }
              return '';
            }""")
            return clean(value, 260)
        except Exception:
            return ""

    def visible_modal_payload(page) -> dict[str, Any] | None:
        # Prefer semantic dialog/modal containers. Fallback to a large fixed overlay with text.
        try:
            return page.evaluate("""() => {
              const visible = (el) => {
                const s = getComputedStyle(el), r = el.getBoundingClientRect();
                return s.display !== 'none' && s.visibility !== 'hidden' && Number(s.opacity || 1) > 0 && r.width > 260 && r.height > 180;
              };
              const picked = [];
              const selectors = ['[role="dialog"]','[aria-modal="true"]','[class*="modal" i]','[class*="dialog" i]','[class*="popup" i]'];
              for (const sel of selectors) {
                for (const el of document.querySelectorAll(sel)) {
                  if (!visible(el)) continue;
                  const text = (el.innerText || '').trim();
                  if (text.length < 60) continue;
                  const r = el.getBoundingClientRect();
                  const h = el.querySelector('h1,h2,h3,h4,h5,h6');
                  const img = el.querySelector('img');
                  picked.push({text, title: h ? (h.innerText || '').trim() : '', image: img ? (img.currentSrc || img.src || '') : '', area: r.width * r.height});
                }
              }
              if (!picked.length) {
                for (const el of document.querySelectorAll('body *')) {
                  if (!visible(el)) continue;
                  const s = getComputedStyle(el), r = el.getBoundingClientRect();
                  if (s.position !== 'fixed' || r.width < 300 || r.height < 250) continue;
                  const text = (el.innerText || '').trim();
                  if (text.length < 80 || text.length > 12000) continue;
                  const h = el.querySelector('h1,h2,h3,h4,h5,h6');
                  const img = el.querySelector('img');
                  picked.push({text, title: h ? (h.innerText || '').trim() : '', image: img ? (img.currentSrc || img.src || '') : '', area: r.width * r.height});
                }
              }
              picked.sort((a,b) => (b.text.length - a.text.length) || (a.area - b.area));
              return picked[0] || null;
            }""")
        except Exception:
            return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(user_agent=USER_AGENT, locale="en-US", viewport={"width": 1440, "height": 1000})
            page.goto(source["url"], wait_until="domcontentloaded", timeout=timeout * 1000)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout, 12) * 1000)
            except Exception:
                pass

            # If a cookie banner blocks clicks, dismiss common accept buttons when present.
            for label in ["Accept all", "Accept All", "Accept", "I agree", "موافق", "قبول الكل"]:
                try:
                    btn = page.get_by_role("button", name=re.compile(rf"^\s*{re.escape(label)}\s*$", re.I))
                    if btn.count() and btn.first.is_visible():
                        btn.first.click(timeout=1200)
                        break
                except Exception:
                    pass

            ctas = page.locator("button, a").filter(has_text=cta_pattern)
            count = min(ctas.count(), int(config["settings"].get("max_items_per_source", 80)))
            if count == 0:
                raise RuntimeError("No visible tiqmo LEARN MORE controls were found")

            for index in range(count):
                cta = ctas.nth(index)
                try:
                    if not cta.is_visible():
                        continue
                    card_title = card_title_for(cta)
                    cta.scroll_into_view_if_needed(timeout=3000)
                    cta.click(timeout=5000, force=True)

                    payload = None
                    for _ in range(12):
                        page.wait_for_timeout(250)
                        payload = visible_modal_payload(page)
                        if payload and clean(payload.get("text"), 12000):
                            break
                    if not payload:
                        raise RuntimeError(f"Offer modal did not appear for card {index + 1}")

                    modal_text = clean(payload.get("text"), 12000)
                    title = clean(payload.get("title"), 260) or card_title
                    if not title:
                        title = clean(modal_text.split("\n", 1)[0], 260) or f"tiqmo offer {index + 1}"
                    title = strip_validity_prefix(title)
                    identity = normalized_title(title) or digest(modal_text[:500])
                    if identity in seen:
                        page.keyboard.press("Escape")
                        continue
                    seen.add(identity)

                    start_date, end_date, date_evidence = listing_date_hints(modal_text)
                    category, categories = taxonomy_match(f"{title} {modal_text}", config)
                    mechanics, themes = infer_tags(f"{title} {modal_text}")
                    image = canonical(source["url"], clean(payload.get("image"))) if payload.get("image") else None
                    source_locator = {"type": "modal", "label": title, "ordinal": index + 1}
                    media = ({
                        "url": image,
                        "type": "image",
                        "thumbnail_url": image,
                        "source_type": "official_website",
                        "source_url": source["url"],
                        "verification_method": "official_website_modal",
                    } if image else None)

                    row = {
                        "id": f"detected:{competitor['id']}:{digest('official-modal', identity)}",
                        "competitor_id": competitor["id"],
                        "source_key": key,
                        "source_type": "website",
                        "platform": "website",
                        "content_type": "review",
                        "campaign_category": category,
                        "primary_category": category,
                        "categories": categories,
                        "title": title,
                        "snippet": modal_text,
                        "summary": modal_text[:1600],
                        "link": source["url"],
                        "official_campaign_page_url": source["url"],
                        "primary_official_source_url": source["url"],
                        "source_locator": source_locator,
                        "source_detail_type": "modal",
                        "social_links": {},
                        "social_link_count": 0,
                        "published_at": None,
                        "start_date": start_date,
                        "end_date": end_date,
                        "date_evidence": {"modal": date_evidence} if date_evidence else {},
                        "evidence_snapshot": date_evidence or modal_text[:1200],
                        "current_status": "Needs Review",
                        "active": True,
                        "direct_link": False,
                        "verified": True,
                        "official_discovery": True,
                        "discovery_section": "current",
                        "review_required": True,
                        "review_reasons": ["new_official_modal_not_in_excel_inventory"],
                        "confidence": "high",
                        "mechanic_tags": mechanics,
                        "theme_tags": themes,
                        "media": media,
                        "source_verification": {
                            "status": "verified_website",
                            "verification_method": "official_website_modal",
                            "checked_at": checked,
                            "source_url": source["url"],
                            "source_locator": source_locator,
                            "source_changed": False,
                            "conflicts": [],
                            "error": None,
                        },
                    }
                    rows.append(row)
                except Exception as exc:
                    print(f"[tiqmo modal {index + 1}] {type(exc).__name__}: {clean(exc, 300)}")
                finally:
                    # Close the current modal before opening the next card.
                    try:
                        page.keyboard.press("Escape")
                        page.wait_for_timeout(180)
                    except Exception:
                        pass
            browser.close()

        status["success"] = True
        status["item_count"] = len(rows)
        status["modal_count"] = len(rows)
        if not rows:
            status["error"] = "tiqmo page loaded but no offer modals could be extracted"
        return rows, status
    except Exception as exc:
        status["error"] = clean(f"{type(exc).__name__}: {exc}", 500)
        return [], status


def extract_website_candidates(markup: str, competitor: dict[str, Any], source: dict[str, Any], config: dict[str, Any], key: str) -> tuple[list[dict[str, Any]], int]:
    soup = BeautifulSoup(markup, "html.parser")
    found: dict[str, dict[str, Any]] = {}
    skipped_general = 0
    link_words = [word.casefold() for word in source.get("link_keywords", [])]
    excludes = [word.casefold() for word in source.get("exclude_keywords", [])]
    parser_name = source.get("parser") or competitor.get("id") or "generic"

    for anchor in soup.find_all("a", href=True):
        link = canonical(source["url"], anchor.get("href", ""))
        if not link:
            continue
        if parser_name == "mobily-pay":
            if not mobily_current_detail_link(link) or mobily_expired_candidate(anchor, link, source):
                continue
            title, parent = mobily_card_title(anchor, link)
        elif parser_name == "barq":
            title, parent = meaningful_barq_title(anchor, link)
        else:
            parent = anchor
            for candidate in list(anchor.parents)[:5]:
                if candidate.name in {"article", "li", "div", "section"}:
                    parent = candidate
                    break

            raw_candidates = [anchor.get("aria-label"), anchor.get("title")]
            heading = anchor.find(["h1","h2","h3","h4","h5","h6"]) or (parent.find(["h1","h2","h3","h4","h5","h6"]) if parent else None)
            if heading is not None:
                raw_candidates.append(heading.get_text(" ", strip=True))
            # Generic CTA text is never a valid offer title.
            raw_candidates.append(anchor.get_text(" ", strip=True))
            title = ""
            for candidate in raw_candidates:
                candidate = clean(candidate, 220)
                if candidate and not generic_title(candidate):
                    title = candidate
                    break
            if not title:
                title = title_from_detail_url(link)
            title = strip_validity_prefix(title)

        # If a detail link exists but we still cannot identify the card, skip it instead of
        # registering `Read more / اعرف المزيد` as a campaign name.
        if not title or generic_title(title):
            skipped_general += 1
            continue

        # Alinma Pay's offers index can place many unrelated offer cards inside the
        # same DOM container. Never use index-page body/card text as the detail
        # description for an Alinma campaign; the official detail page is authoritative.
        snippet = "" if parser_name == "alinma-pay" else (title if parser_name == "mobily-pay" else clean(parent.get_text(" ", strip=True), 1200))
        combined = f"{link} {title} {snippet}".casefold()
        if excludes and any(word in combined for word in excludes):
            continue
        if link_words and not any(word in combined for word in link_words):
            continue
        is_direct = direct_detail(link, source)
        if source.get("require_detail_link", True) and not is_direct:
            skipped_general += 1
            continue

        category, categories = taxonomy_match(combined, config)
        mechanics, themes = infer_tags(combined)
        start_date, end_date, date_evidence = listing_date_hints(f"{title} {snippet}")
        suggested_record_type = None
        review_reason = "new_official_item_not_in_excel_inventory"
        if parser_name == "mobily-pay":
            suggested_record_type = mobily_offer_hint(title, snippet, link)
            if suggested_record_type == "expired":
                # Defense in depth: never register a historical Mobily card as a current candidate.
                continue
            if suggested_record_type == "merchant_offer":
                category, categories = "merchant", ["merchant"]
                review_reason = "new_official_merchant_offer_not_in_excel_inventory"
            elif suggested_record_type == "campaign":
                review_reason = "new_official_campaign_not_in_excel_inventory"

        found[link] = {
            "id": f"detected:{competitor['id']}:{digest(link)}", "competitor_id": competitor["id"], "source_key": key,
            "source_type": "website", "platform": "website", "content_type": "review", "suggested_record_type": suggested_record_type, "campaign_category": category,
            "primary_category": category, "categories": categories, "title": title or "Discovered official offer",
            "snippet": snippet, "link": link, "official_campaign_page_url": link, "primary_official_source_url": link,
            "social_links": {}, "social_link_count": 0, "published_at": None, "start_date": start_date, "end_date": end_date,
            "date_evidence": {"listing": date_evidence} if date_evidence else {},
            "current_status": "Needs Review", "active": True, "direct_link": is_direct, "verified": True,
            "official_discovery": True, "discovery_section": "current",
            "review_required": True, "review_reasons": [review_reason], "confidence": "medium",
            "mechanic_tags": mechanics, "theme_tags": themes,
            "media": None if parser_name == "alinma-pay" else media_from_node(parent, source["url"]),
        }
    return list(found.values()), skipped_general


def website_items(http: requests.Session, competitor: dict[str, Any], source: dict[str, Any], config: dict[str, Any], checked: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    key = f"website:{competitor['id']}:{source['id']}"
    status = {"source_key": key, "competitor_id": competitor["id"], "source_type": "website", "platform": "website", "url": source["url"], "checked_at": checked, "success": False, "item_count": 0, "error": None, "skipped_general_links": 0, "fetch_mode": "requests"}
    timeout = int(config["settings"].get("request_timeout_seconds", 18))
    if source.get("discovery_mode") == "modal" and (source.get("parser") or competitor.get("id")) == "tiqmo":
        return tiqmo_modal_items(competitor, source, config, checked)
    markup = ""
    request_error = None
    try:
        response = http.get(source["url"], timeout=timeout)
        response.raise_for_status()
        markup = response_text(response)
    except Exception as exc:
        request_error = clean(f"{type(exc).__name__}: {exc}", 500)

    items: list[dict[str, Any]] = []
    skipped = 0
    if markup:
        items, skipped = extract_website_candidates(markup, competitor, source, config, key)

    needs_browser = bool(source.get("browser_fallback")) and (request_error is not None or len(items) < int(source.get("browser_fallback_below_items", 1)))
    browser_success = False
    if needs_browser:
        try:
            rendered = rendered_html(source["url"], int(config["settings"].get("browser_timeout_seconds", 25)))
            browser_items, browser_skipped = extract_website_candidates(rendered, competitor, source, config, key)
            if browser_items or not items:
                items, skipped = browser_items, browser_skipped
            status["fetch_mode"] = "browser"
            browser_success = True
            request_error = None
        except Exception as exc:
            browser_error = clean(f"{type(exc).__name__}: {exc}", 500)
            request_error = f"requests={request_error}; browser={browser_error}" if request_error else browser_error

    items = items[: int(config["settings"].get("max_items_per_source", 80))]
    status["skipped_general_links"] = skipped
    # For browser-fallback sources, a failed fallback after a zero/blocked normal fetch is a real
    # source-health failure. For simple sources, reachable HTML with zero offers is still healthy.
    if needs_browser:
        status["success"] = browser_success
    else:
        status["success"] = bool(markup) and request_error is None
    status["item_count"] = len(items)
    status["error"] = None if status["success"] else request_error
    return items, status

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


def lifecycle_status(item: dict[str, Any], at: datetime | None = None) -> tuple[str, bool]:
    at = at or now_utc()
    start = parse_iso(item.get("start_date"))
    end = parse_iso(item.get("end_date"))
    if start and start.date() > at.date():
        return "Upcoming", True
    if end:
        days = (end.date() - at.date()).days
        if days < 0:
            return "Expired", False
        if days <= 7:
            return "Expiring ≤7 Days", True
        if days <= 30:
            return "Expiring 8–30 Days", True
        return "Active", True
    return "End Date Not Stated", True


def stale_no_end_note(value: Any) -> bool:
    text = clean(value, 1000).casefold()
    if not text:
        return False
    markers = (
        "end date is not stated", "end date not stated", "no end date",
        "تاريخ الانتهاء غير", "تاريخ انتهاء غير", "لم يتم ذكر تاريخ الانتهاء", "لم يذكر تاريخ الانتهاء",
    )
    return any(marker in text for marker in markers)


def apply_override(item: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    allowed = {"title", "snippet", "summary", "content_type", "campaign_category", "primary_category", "categories", "current_status", "active", "published_at", "start_date", "end_date", "official_campaign_page_url", "primary_official_source_url", "link", "social_links", "review_required", "review_reasons", "mechanic_tags", "theme_tags", "operation_type", "mechanic", "eligibility", "terms_note", "deleted", "deleted_at", "deleted_title", "deleted_competitor_id", "deleted_url"}
    result = dict(item)
    for key, value in override.items():
        if key in allowed:
            result[key] = value
    if "campaign_category" in result:
        result["primary_category"] = result["campaign_category"]
        result["categories"] = [result["campaign_category"]]
    result["social_links"] = {k: v for k, v in (result.get("social_links") or {}).items() if v}
    result["social_link_count"] = len(result["social_links"])
    # Lifecycle is always derived from dates. A stale manual status/active flag must never
    # contradict a newly entered Start/End Date.
    if result.get("content_type") in {"campaign", "merchant_offer"}:
        status, active = lifecycle_status(result)
        result["current_status"] = status
        result["active"] = active
        if result.get("end_date") and stale_no_end_note(result.get("terms_note")):
            result["terms_note"] = ""
    result["manual_override"] = True
    return result


def deleted_by_override(item: dict[str, Any], overrides: dict[str, Any]) -> bool:
    patch = overrides.get(item.get("id"), {}) or {}
    if patch.get("deleted"):
        return True
    comp = item.get("competitor_id") or ""
    title_key = normalized_title(item.get("title"))
    if not title_key:
        return False
    for tomb in overrides.values():
        if not isinstance(tomb, dict) or not tomb.get("deleted"):
            continue
        tomb_comp = tomb.get("deleted_competitor_id") or ""
        tomb_title = normalized_title(tomb.get("deleted_title"))
        if tomb_comp == comp and tomb_title and tomb_title == title_key:
            return True
    return False


def repair_campaign_references(items: list[dict[str, Any]]) -> None:
    valid = {row.get("id") for row in items if row.get("content_type") in {"campaign", "merchant_offer"}}
    for row in items:
        broken = False
        for field in ("campaign_id", "linked_campaign_id", "suggested_campaign_id"):
            ref = row.get(field)
            if ref and ref not in valid:
                row[field] = None
                broken = True
        if broken and row.get("source_type") == "social":
            row["review_required"] = True
            row["current_status"] = "Needs Review"
            reasons = list(row.get("review_reasons") or [])
            if "linked_campaign_deleted" not in reasons:
                reasons.append("linked_campaign_deleted")
            row["review_reasons"] = reasons


def prune_old_social_state(state: dict[str, Any], now: datetime, config: dict[str, Any]) -> int:
    """Bound raw social history so hourly runs do not grow state.json forever.

    Campaign/inventory history is untouched. Only old social feed entries that are already
    inactive are removed; 180 days still comfortably covers the site's 7/30-day analytics.
    """
    days=int(config.get("settings",{}).get("social_history_retention_days",180))
    if days<=0:
        return 0
    cutoff=now-timedelta(days=days)
    items=state.setdefault("items",{})
    remove=[]
    for key,row in items.items():
        if row.get("source_type")!="social" or row.get("active") is not False:
            continue
        stamp=parse_iso(row.get("published_at")) or parse_iso(row.get("last_seen")) or parse_iso(row.get("first_seen"))
        if stamp and stamp<cutoff:
            remove.append(key)
    for key in remove:
        items.pop(key,None)
    if remove:
        print(f"[CLEANUP] pruned {len(remove)} inactive social records older than {days} days")
    return len(remove)


def reconcile_live(state: dict[str, Any], collected: list[dict[str, Any]], statuses: list[dict[str, Any]], now: datetime, config: dict[str, Any]) -> list[dict[str, Any]]:
    items = state.setdefault("items", {})

    # Purge parser noise from older runs immediately. Waiting for the normal missed-run
    # expiry would keep duplicate generic CTA records alive for several hours.
    for stale_id in [key for key, row in items.items() if invalid_discovered_website_item(row)]:
        items.pop(stale_id, None)

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
    prune_old_social_state(state, now, config)
    state["schema_version"] = 4
    state["updated_at"] = stamp
    save_json(STATE_PATH, state)
    hidden = {"content_hash", "miss_count"}
    return [{k: v for k, v in row.items() if k not in hidden} for row in items.values()]


def generic_competitor_source_url(value: str | None, competitor_id: str | None, config: dict[str, Any]) -> bool:
    """Return True for a competitor-level landing/offers URL, not a campaign-specific detail URL.

    These URLs must never be used as campaign identity keys. tiqmo is the clearest case:
    every offer modal shares the same /offers URL, so URL-based dedup would collapse unrelated campaigns.
    """
    if not value or not competitor_id:
        return False
    ident = url_identity(value)
    if not ident:
        return False
    for comp in config.get("competitors", []):
        if comp.get("id") != competitor_id:
            continue
        candidates = [comp.get("website"), comp.get("offers_url")]
        candidates += [src.get("url") for src in comp.get("website_sources", []) if src.get("url")]
        return any(url_identity(v) == ident for v in candidates if v)
    return False


def match_inventory(inventory: list[dict[str, Any]], live: list[dict[str, Any]], config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    official_map: dict[str, dict[str, Any]] = {}
    social_map: dict[str, dict[str, Any]] = {}
    by_competitor: dict[str, list[dict[str, Any]]] = {}
    for campaign in inventory:
        by_competitor.setdefault(campaign.get("competitor_id"), []).append(campaign)
        for url in [campaign.get("link"), campaign.get("official_campaign_page_url"), campaign.get("primary_official_source_url")]:
            if url and not social_url(url) and not generic_competitor_source_url(url, campaign.get("competitor_id"), config):
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
            raw_link = row.get("link")
            key = None if generic_competitor_source_url(raw_link, row.get("competitor_id"), config) else url_identity(raw_link)
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


def deduplicate_campaign_records(items: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
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
    redirect: dict[str, str] = {}
    for row in records:
        comp=row.get("competitor_id") or ""
        record_type=row.get("content_type") or "campaign"
        title_key=normalized_title(row.get("title"))
        urls=set()
        for u in [row.get("official_campaign_page_url"), row.get("primary_official_source_url"), row.get("link")]:
            if not u:
                continue
            # A shared offers/index page is evidence, not campaign identity.
            if not social_url(u) and generic_competitor_source_url(u, comp, config):
                continue
            ident = social_identity(u) if social_url(u) else url_identity(u)
            if ident:
                urls.add(ident)
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
        if row.get("id") and target.get("id") and row.get("id") != target.get("id"):
            redirect[row["id"]] = target["id"]
        for f in ["summary","snippet","start_date","end_date","published_at","mechanic","eligibility","terms_note","operation_type"]:
            if not target.get(f) and row.get(f): target[f]=row[f]
        target["review_required"] = bool(target.get("review_required") and row.get("review_required"))
        # Register every identity from the duplicate against the retained record.
        if title_key and not generic_title(row.get("title")): by_title[(comp,record_type,title_key)]=target
        for u in urls: by_url[(comp,record_type,u)]=target
    result = kept + others

    # Resolve redirect chains and repair references on social/review rows after a real dedup merge.
    def resolve(value: str | None) -> str | None:
        seen=set()
        while value in redirect and value not in seen:
            seen.add(value)
            value=redirect[value]
        return value

    valid_ids={row.get("id") for row in result if row.get("id")}
    for row in result:
        for field in ("campaign_id", "suggested_campaign_id"):
            old_id=row.get(field)
            if not old_id:
                continue
            new_id=resolve(old_id)
            if new_id in valid_ids:
                row[field]=new_id
            else:
                row.pop(field, None)
                if field=="campaign_id":
                    row["review_required"]=True
                    row["review_reasons"]=list(dict.fromkeys((row.get("review_reasons") or [])+["stale_campaign_reference_repaired"]))
    return result

def source_history(
    statuses: list[dict[str, Any]],
    previous_data: dict[str, Any],
    checked: str,
    selected_competitors: set[str] | None = None,
) -> list[dict[str, Any]]:
    old = {row.get("source_key"): row for row in previous_data.get("source_status", [])}
    for row in statuses:
        prior = old.get(row["source_key"], {})
        if row.get("success"):
            row["last_success_at"] = checked
            row["consecutive_failures"] = 0
        else:
            row["last_success_at"] = prior.get("last_success_at")
            row["consecutive_failures"] = int(prior.get("consecutive_failures", 0)) + 1
    current_keys = {row.get("source_key") for row in statuses}
    preserved = [
        row for row in previous_data.get("source_status", [])
        if row.get("source_key") not in current_keys
        and (
            row.get("source_type") == "campaign_detail"
            or (
                selected_competitors is not None
                and row.get("competitor_id") not in selected_competitors
            )
        )
    ]
    return sorted(statuses + preserved, key=lambda row: row.get("source_key", ""))


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


def run(config: dict[str, Any], competitor_id: str = "all") -> dict[str, Any]:
    validate(config)
    now = now_utc(); checked = iso(now)
    configured_ids = {row["id"] for row in config["competitors"]}
    if competitor_id != "all" and competitor_id not in configured_ids:
        raise ValueError(f"Unknown competitor: {competitor_id}")
    selected_competitors = configured_ids if competitor_id == "all" else {competitor_id}
    partial_run = competitor_id != "all"
    print(f"[RUN] target={competitor_id}")
    inventory_payload = load_json(BASE_DIR / config["settings"].get("inventory_path", "inventory.json"), {"items": []})
    inventory = inventory_payload.get("items", [])
    overrides = load_json(BASE_DIR / config["settings"].get("manual_overrides_path", "manual_overrides.json"), {"items": {}}).get("items", {})
    collected: list[dict[str, Any]] = []; statuses: list[dict[str, Any]] = []
    jobs: list[tuple[str, dict[str, Any], Any, Any]] = []
    for competitor in config["competitors"]:
        if competitor["id"] not in selected_competitors:
            continue
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
    inventory, live = match_inventory(inventory, live, config)
    items = inventory + live
    items = [apply_override(row, overrides.get(row["id"], {})) for row in items]
    items = [row for row in items if not deleted_by_override(row, overrides)]
    items = deduplicate_campaign_records(items, config)
    repair_campaign_references(items)
    items.sort(key=lambda row: (row.get("active") is not False, parse_iso(row.get("published_at")) or parse_iso(row.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    previous = load_json(DATA_PATH, {})
    statuses = source_history(statuses, previous, checked, selected_competitors if partial_run else None)
    competitors = [{"id": row["id"], "name_ar": row["name_en"], "name_en": row["name_en"], "website": row.get("website"), "offers_url": row.get("offers_url")} for row in config["competitors"]]
    data = {
        "schema_version": 4, "generated_at": checked,
        "refresh_scope": competitor_id,
        "inventory_source": {"workbook": inventory_payload.get("source_workbook"), "review_date": inventory_payload.get("source_review_date"), "reporting_convention": inventory_payload.get("reporting_convention")},
        "competitors": competitors, "categories": public_taxonomy(config, "categories"),
        "mechanic_types": public_taxonomy(config, "mechanic_types"), "themes": public_taxonomy(config, "themes"),
        "content_types": config.get("content_types", []), "source_status": statuses,
        "stats": build_stats(items, statuses, now), "items": items,
    }
    save_json(DATA_PATH, data)
    return data


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--competitor", default=os.environ.get("CM_COMPETITOR", "all"), help="Competitor id to refresh, or 'all'")
    return parser.parse_args()


def main() -> int:
    try:
        config = load_json(CONFIG_PATH, {})
        validate(config)
        options = args()
        if options.validate_only:
            print("Configuration is valid."); return 0
        data = run(config, clean(options.competitor) or "all"); print(json.dumps(data["stats"], ensure_ascii=False)); return 0
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", flush=True); return 1


if __name__ == "__main__":
    raise SystemExit(main())
