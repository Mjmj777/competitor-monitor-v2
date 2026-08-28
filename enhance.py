from __future__ import annotations
import argparse, hashlib, html as html_lib, json, os, re, time, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = Path(__file__).resolve().parent
DATA_PATH = BASE / "data.json"
STATE_PATH = BASE / "state.json"
CONFIG_PATH = BASE / "config.json"
OVERRIDES_PATH = BASE / "manual_overrides.json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"

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

WINNER_ANNOUNCEMENT_PHRASES=(
    "winner announcement", "announcing our winner", "meet our winner", "congratulations", "congrats",
    "the winner is", "the winners are", "prize handover", "received the prize",
    "مبروك", "نبارك", "تهانينا", "الفائز هو", "الفائزة هي", "الفائزون هم", "الفائزين هم",
    "إعلان الفائز", "اعلان الفائز", "تسليم الجائزة", "استلم الجائزة", "استلمت الجائزة",
)
SOCIAL_HOSTS=("instagram.com","facebook.com","m.facebook.com","x.com","twitter.com","tiktok.com")
AI_DATE_CALLS_THIS_RUN=0
DETAIL_EXTRACTOR_VERSION="focused-detail-v3-mobily-en"
CLASSIFIER_VERSION="classifier-v6-merchant-review-cleanup"
SOCIAL_MATCHER_VERSION="social-merchant-offer-v2"

def is_winner_announcement(item):
    text=f"{item.get('title','')} {item.get('snippet','')}".casefold()
    # Re-evaluate legacy automatic role labels from the text. Older builds labelled any
    # occurrence of "winner" (including campaign mechanics) as a result announcement.
    if item.get("post_role")=="winner_announcement" and item.get("post_role_source")=="manual":return True
    if any(phrase.casefold() in text for phrase in WINNER_ANNOUNCEMENT_PHRASES):return True
    # "One winner every week" and "enter to win" describe campaign mechanics; they are
    # not result announcements. Require a past/result verb before quarantining the post.
    return bool(
        re.search(r"\b(?:winner|winners)\b.{0,45}\b(?:announced|selected|received|won)\b",text,re.I)
        or re.search(r"\b(?:announced|selected)\b.{0,45}\b(?:winner|winners)\b",text,re.I)
        or re.search(r"(?:فاز|فازت|تم اختيار|تم إعلان|تم اعلان|استلم|استلمت).{0,45}(?:الفائز|الفائزة|الجائزة)",text,re.I)
        or re.search(r"(?:الفائز(?:ون|ين)?|فائز(?:ون|ين)?).{0,45}(?:@|اليوم|هذا الأسبوع|هذا الاسبوع|تواصلوا|استلام)",text,re.I)
        or re.search(r"(?:اليوم|هذا الأسبوع|هذا الاسبوع).{0,35}(?:الفائز(?:ون|ين)?|فائز(?:ون|ين)?)",text,re.I)
    )

def social_url(value):
    if not value:return False
    try:
        host=(urlsplit(str(value)).hostname or "").casefold().removeprefix("www.")
        return any(host==h or host.endswith("."+h) for h in SOCIAL_HOSTS)
    except Exception:return False

def social_identity(value):
    if not value:return ""
    try:
        parts=urlsplit(str(value).strip()); host=(parts.hostname or "").casefold().removeprefix("www.")
        if host=="twitter.com":host="x.com"
        if host=="m.facebook.com":host="facebook.com"
        path=re.sub(r"/{2,}","/",parts.path or "/").rstrip("/").casefold() or "/"
        return f"{host}{path}"
    except Exception:return clean(value,2000).casefold().rstrip("/")

def specific_social_post_url(value):
    if not social_url(value):return False
    try:
        parts=urlsplit(str(value));host=(parts.hostname or "").casefold().removeprefix("www.");path=(parts.path or "").casefold()
        if "instagram.com" in host:return bool(re.search(r"/(?:p|reel|reels|tv)/[^/]+",path))
        if host in {"x.com","twitter.com"} or host.endswith(".x.com") or host.endswith(".twitter.com"):return "/status/" in path
        if "tiktok.com" in host:return "/video/" in path
        if "facebook.com" in host:return any(x in path for x in ("/posts/","/videos/","/reel/","/share/","/photo","/permalink")) or "story.php" in str(value).casefold()
    except Exception:return False
    return False

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
    # A verified official modal is valid campaign evidence even though all tiqmo offers share the same index URL.
    sv=item.get("source_verification") or {}
    if sv.get("status")=="verified_website" and sv.get("verification_method")=="official_website_modal" and item.get("source_locator"):
        return True
    # Only a specific official social post is acceptable; a generic social profile is not evidence.
    if any(specific_social_post_url(v) for v in (item.get("social_links") or {}).values()):return True
    for key in ("official_campaign_page_url","primary_official_source_url","link"):
        value=item.get(key)
        if not value:continue
        if social_url(value):
            if specific_social_post_url(value):return True
            continue
        if str(value).startswith(("http://","https://")) and not generic_offers_url(value,config,item.get("competitor_id")):
            return True
    return False

def normalize_winner_announcements(data):
    """Deterministically quarantine every unlinked winner/result announcement.

    This runs for the full social history, not only the recent AI-classification window.
    If a valid campaign link was found, the item remains a social post. Otherwise it is
    always Needs Review and can never inflate campaign counts.
    """
    changed = 0
    byid = {i.get("id"): i for i in data.get("items", []) if i.get("id")}
    for item in data.get("items", []):
        if item.get("source_type") != "social" or not is_winner_announcement(item):
            continue
        cid = item.get("campaign_id")
        target = byid.get(cid) if cid else None
        valid_link = bool(
            target
            and target.get("competitor_id") == item.get("competitor_id")
            and target.get("content_type") in {"campaign", "merchant_offer"}
        )
        reasons = list(item.get("review_reasons") or [])
        if valid_link:
            if item.get("content_type") != "social_post":
                item["content_type"] = "social_post"
                changed += 1
            reasons = [r for r in reasons if r != "winner_announcement_unlinked"]
            item["review_reasons"] = reasons
            # A winner announcement that is now linked no longer needs review solely for being a winner post.
            if not reasons:
                item["review_required"] = False
                if item.get("current_status") == "Needs Review":
                    item.pop("current_status", None)
        else:
            if item.get("content_type") != "review" or not item.get("review_required"):
                changed += 1
            item["content_type"] = "review"
            item["review_required"] = True
            item["current_status"] = "Needs Review"
            item["review_reasons"] = list(dict.fromkeys(reasons + ["winner_announcement_unlinked"]))
            # Never retain a stale/invalid automatic campaign link on an unverified winner post.
            if cid and not valid_link:
                item.pop("campaign_id", None)
                item.pop("match_method", None)
    data["winner_announcement_integrity"] = {"normalized": changed, "at": iso(now())}
    return changed


def enforce_record_integrity(data, config):
    """Hard guardrails for counted records before deduplication.

    Social posts never become counted records. Newly discovered official website rows are
    allowed into Campaign/Merchant Offer only after the detail page itself was verified.
    This rule is deterministic and overrides stale AI/classification cache decisions.
    """
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

        if item.get("content_type") in {"campaign","merchant_offer"}:
            # An auto-discovered website card/link is only counted after its own detail page
            # was successfully fetched and verified. A stale AI cache can never bypass this.
            if item.get("source_type")=="website" and item.get("official_discovery") and not item.get("review_approved"):
                sv=(item.get("source_verification") or {}).get("status")
                listing_merchant=item.get("content_type")=="merchant_offer" and trusted_barq_listing_merchant(item,config)
                if sv!="verified_website" and not listing_merchant:
                    suggested=item.get("content_type")
                    item["content_type"]="review"
                    item["suggested_record_type"]=suggested
                    item["review_required"]=True
                    item["current_status"]="Needs Review"
                    item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["official_detail_not_verified"]))
                    changed+=1
                    continue

            if item.get("content_type")=="campaign" and not accepted_direct_source(item,config):
                item["content_type"]="review"
                item["suggested_record_type"]="campaign"
                item["review_required"]=True
                item["current_status"]="Needs Review"
                item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["missing_direct_official_source"]))
                changed+=1
    data["record_integrity"]={"quarantined_or_demoted":changed,"at":iso(now())}
    return changed




_MOBILY_EXPIRED_PATH = re.compile(r"/(?:(?:ar|en)/)?(?:expired[-_]?offers?|expiredoffers?)/", re.I)
_MOBILY_CAMPAIGN_STRONG = (
    "تحويل دولي", "حوالة دولية", "الحوالات الدولية", "international transfer", "international transfers", "remittance",
    "كاش باك", "cashback", "cash back",
    "اكسب أميال", "أميال", "miles",
    "رسوم التحويل", "بدون رسوم", "صفر رسوم", "zero fee", "zero fees", "fee-free", "no fee",
    "راتب", "رواتب", "salary", "payroll",
    "مساند", "musaned", "سداد", "sadad",
    "رسوم العمليات الدولية", "رسوم المعاملات الدولية", "رسوم المشتريات الدولية",
    "international transaction fee", "international transaction fees",
    "foreign transaction fee", "foreign transaction fees",
    "اربح", "سحب", "جائزة", "جوائز", "win", "prize", "draw",
    "دعوة", "إحالة", "referral", "refer a friend",
)
_MOBILY_MERCHANT_PHRASES = (
    "خصم لدى", "خصم في", "خصم مع", "استمتع بخصم", "احصل على خصم", "استفد من خصم",
    "discount at", "discount with", "off at", "promo code", "promocode", "كود الخصم", "رمز الخصم", "استخدم الكود",
)

def mobily_offer_hint(item):
    if item.get("competitor_id") != "mobily-pay":
        return None
    if item.get("source_type") != "website" or not item.get("official_discovery"):
        return None
    url=clean(direct_url(item),1200).casefold()
    if _MOBILY_EXPIRED_PATH.search(url):
        return "expired"
    text=clean(" ".join(str(item.get(k) or "") for k in ("title","summary","snippet","mechanic","eligibility","terms_note","evidence_snapshot")),7000).casefold()
    if any(marker in text for marker in _MOBILY_CAMPAIGN_STRONG):
        return "campaign"
    if any(marker in text for marker in _MOBILY_MERCHANT_PHRASES):
        return "merchant_offer"
    if re.search(r"(?:خصم|discount)\s*(?:حتى\s*)?\d{1,3}%",text,re.I) and re.search(r"(?:\sلدى\s|\sفي\s|\sمع\s|\sat\s|\swith\s)",text,re.I):
        return "merchant_offer"
    return None

def apply_mobily_deterministic_classification(data):
    """Separate Mobily Pay's own campaigns from partner/merchant offers before AI.

    Only verified official website discoveries are promoted. Clear partner discounts become
    Merchant Offers (excluded from Campaign KPIs); clear Mobily-owned mechanics become
    Campaigns. Ambiguous records stay Needs Review for the AI/manual layer. Expired records
    remain historical and inactive regardless of which section still displays them.
    """
    changed=0
    current=now()
    for item in data.get("items",[]):
        hint=mobily_offer_hint(item)
        if not hint:
            continue
        if hint=="expired":
            if item.get("active") is not False or item.get("current_status")!="Expired":
                changed+=1
            item["active"]=False
            item["current_status"]="Expired"
            continue

        verified=(item.get("source_verification") or {}).get("status")=="verified_website"
        if not verified:
            item["content_type"]="review"
            item["suggested_record_type"]=hint
            item["review_required"]=True
            item["current_status"]="Needs Review"
            item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["official_detail_not_verified"]))
            continue

        status,active=status_for(item,current)
        if hint=="merchant_offer":
            if item.get("content_type")!="merchant_offer" or item.get("campaign_category")!="merchant":
                changed+=1
            item["content_type"]="merchant_offer"
            item["suggested_record_type"]="merchant_offer"
            item["campaign_category"]="merchant"
            item["primary_category"]="merchant"
            item["categories"]=["merchant"]
        elif hint=="campaign":
            if item.get("content_type")!="campaign":
                changed+=1
            item["content_type"]="campaign"
            item["suggested_record_type"]="campaign"
            # A stale Merchant category from a prior AI decision must not survive a clear
            # Mobily-owned campaign classification. Preserve a useful non-merchant category
            # from discovery; otherwise fall back to Other.
            if item.get("campaign_category")=="merchant":
                item["campaign_category"]="other"
                item["primary_category"]="other"
                item["categories"]=["other"]

        item["current_status"]=status
        item["active"]=active
        item["review_required"]=False
        item["review_reasons"]=[r for r in (item.get("review_reasons") or []) if r not in {
            "new_official_item_not_in_excel_inventory","new_official_merchant_offer_not_in_excel_inventory",
            "new_official_campaign_not_in_excel_inventory","ai_needs_review","official_detail_not_verified",
            "new_official_campaign_needs_review","expired_official_candidate"
        }]
        item["classification_method"]="mobily_official_rules"
    data["mobily_deterministic_classification"]={"changed":changed,"at":iso(current)}
    return changed


_GENERIC_CAMPAIGN_STRONG = (
    "campaign runs", "campaign period", "enter the draw", "weekly draw", "prize draw",
    "win a car", "win prizes", "cash prizes", "cashback game", "cash back game",
    "international transfer", "international transfers", "remittance", "fee-free", "zero fee",
    "salary cashback", "payroll", "musaned", "sadad", "exchange rate", "preferred rate", "fixed rate",
    "فترة الحملة", "تبدأ الحملة", "تنتهي الحملة", "ادخل السحب", "دخول السحب",
    "سحب أسبوعي", "سحب شهري", "اربح سيارة", "جوائز نقدية", "لعبة الكاش باك",
    "حوالة دولية", "تحويل دولي", "الحوالات الدولية", "رواتب العمالة", "مساند", "سداد",
    "سعر صرف", "سعر التحويل", "تثبيت الليرة", "تثبيت سعر",
)
_GENERIC_MERCHANT_STRONG = (
    "partner offer", "merchant offer", "exclusive partner", "discount at", "discount with",
    "promo code", "promocode", "use code", "at checkout", "at the restaurant", "at the store",
    "عرض شريك", "عروض الشركاء", "خصم لدى", "خصم في", "خصم مع", "رمز الخصم",
    "كود الخصم", "عند الدفع", "في المطعم", "في المتجر",
)

_GENERIC_MERCHANT_TITLE_TERMS = (
    "restaurant", "cafe", "coffee", "hotel", "resort", "spa", "clinic", "store", "shop",
    "shopping", "fashion", "beauty", "fitness", "furniture", "perfume", "chocolate", "tickets", "college", "school",
    "مطعم", "كافيه", "قهوة", "فندق", "منتجع", "سبا", "عيادة", "متجر", "تسوق",
    "أثاث", "اثاث", "عطور", "شوكولات", "مجوهرات", "هدايا", "بيوتي", "فتنس", "برقر", "كوليدج", "مدرسة",
)

_GENERIC_OWN_CAMPAIGN_TITLE_TERMS = (
    "campaign", "حملة", "تحويل", "حوالة", "سعر صرف", "سعر التحويل", "تثبيت الليرة",
    "دولار", "ريال", "بطاقة", "محفظة", "كاش باك", "cashback", "cash back", "draw", "سحب",
    "prize", "جائزة", "متجر برق", "شرائح الكترونية", "شرائح إلكترونية",
)


def likely_named_merchant_offer(item, text):
    """Suggest a partner/retailer offer from its official detail-page title.

    Many Barq and STC partner pages expose only a merchant name in the card title.  This
    helper intentionally creates a suggestion, not an automatic counted record; the page
    must still pass official detail verification or receive explicit Admin approval.
    """
    title = clean(item.get("title"), 500).casefold()
    if not title or any(marker in title for marker in _GENERIC_OWN_CAMPAIGN_TITLE_TERMS):
        return False
    if any(marker in title for marker in _GENERIC_MERCHANT_TITLE_TERMS):
        return True
    if re.search(r"(?:^|\s)[x×](?:\s|$)", title, re.I):
        return True
    if re.match(r"^\s*(?:عرض|offer)\b", title, re.I) or re.search(r"\b(?:عرض|offer)\s*$", title, re.I):
        return True
    return bool(
        re.search(r"(?:exclusive|خصم|discount|off)\b", text, re.I)
        and re.search(r"(?:\bat\b|\bwith\b|\bfrom\b|\s(?:لدى|مع|في|من)\s)", text, re.I)
    )


def trusted_barq_listing_merchant(item, config):
    """Accept a current named Barq partner card when its detail URL rejects direct fetches.

    Barq's official offers index is browser-rendered and some current partner links return 404
    to the verification client. A freshly rediscovered named `merchant × barq` card with dated
    offer evidence is still first-party evidence; this exception never applies to campaigns.
    """
    if item.get("competitor_id")!="barq" or item.get("source_type")!="website" or not item.get("official_discovery"):
        return False
    if not item.get("verified") or item.get("active") is False or not accepted_direct_source(item,config):
        return False
    seen=dt(item.get("last_seen"))
    if not seen or seen<now()-timedelta(days=3):
        return False
    title=clean(item.get("title"),500).casefold()
    evidence=clean(" ".join(str(item.get(k) or "") for k in ("summary","snippet","evidence_snapshot")),6000).casefold()
    named_pattern=bool(re.search(r"(?:^|\s)[x×](?:\s|$)",title,re.I) and re.search(r"\bbarq\b|برق",title,re.I))
    partner_evidence=bool(re.search(r"visa|فيزا|partner|شراك",evidence,re.I) and re.search(r"offer|عرض",f"{title} {evidence}",re.I))
    return bool(named_pattern and partner_evidence and item.get("start_date"))


def verified_official_hint(item):
    """Conservatively classify a verified first-party offer detail page.

    This is deliberately competitor-agnostic.  It fixes the STC stale-review case and
    applies the same rule to barq, urpay and alinma Pay: first-party campaigns are counted,
    partner discounts become Merchant Offers, and ambiguous pages remain in review.
    """
    if item.get("source_type") != "website" or not item.get("official_discovery"):
        return None
    mobily_hint = mobily_offer_hint(item)
    if mobily_hint in {"campaign", "merchant_offer", "expired"}:
        return mobily_hint
    title_text = clean(item.get("title"), 1000).casefold()
    text = clean(" ".join(str(item.get(k) or "") for k in (
        "title", "summary", "snippet", "mechanic", "eligibility", "terms_note",
        "evidence_snapshot", "date_evidence",
    )), 12000).casefold()
    # Title-first rules prevent a listing page's combined snippet from leaking campaign
    # language into every merchant card (notably STC Bank's offers index).
    if re.search(r"(?:\bcampaign\b|\bdraw\b|\bprize(?:s)?\b|\bwin\b|حملة|سحب|جائزة|جوائز|اربح)", title_text, re.I):
        return "campaign"
    if any(marker in title_text for marker in _GENERIC_CAMPAIGN_STRONG):
        return "campaign"
    if any(marker in title_text for marker in _GENERIC_MERCHANT_STRONG) or likely_named_merchant_offer(item, title_text):
        return "merchant_offer"
    # Preserve an earlier Merchant suggestion when the title does not contradict it.
    # This is safer than allowing a combined listing-page snippet to turn every card into
    # the first campaign mentioned on that page.
    if item.get("suggested_record_type") == "merchant_offer":
        return "merchant_offer"
    # Explicit campaign wording and proprietary mechanics outrank generic partner wording.
    if re.search(r"(?:\bcampaign\b|\bdraw\b|\bprize(?:s)?\b|\bwin\b|حملة|سحب|جائزة|جوائز|اربح)", text, re.I):
        return "campaign"
    if any(marker in text for marker in _GENERIC_CAMPAIGN_STRONG):
        return "campaign"
    merchant_signal = any(marker in text for marker in _GENERIC_MERCHANT_STRONG)
    merchant_discount = bool(re.search(r"(?:discount|خصم)\s*(?:up\s+to|حتى)?\s*\d{1,3}\s*%", text, re.I))
    partner_name = bool(re.search(r"(?:\s[x×]\s|\bwith\b|\bat\b|\s(?:لدى|مع|في)\s)", text, re.I))
    if merchant_signal or (merchant_discount and partner_name) or likely_named_merchant_offer(item, text):
        return "merchant_offer"
    if item.get("campaign_category") == "merchant" or item.get("primary_category") == "merchant":
        return "merchant_offer"
    # Cashback/fee mechanics tied to the competitor's own card, transfer or wallet are campaigns.
    proprietary = bool(re.search(r"(?:cash\s*back|كاش\s*باك|استرداد نقدي|بدون رسوم|إعفاء من الرسوم)", text, re.I))
    own_product = bool(re.search(r"(?:card|wallet|transfer|remittance|salary|بطاقة|محفظة|تحويل|حوالة|راتب)", text, re.I))
    if proprietary and own_product:
        return "campaign"
    # Existing AI/cache suggestions are considered only after deterministic source-aware
    # rules so a stale campaign suggestion cannot hide a clear named merchant offer.
    suggested = item.get("suggested_record_type")
    return suggested if suggested in {"campaign", "merchant_offer"} else None


_CLASSIFICATION_REVIEW_REASONS = {
    "new_official_item_not_in_excel_inventory", "new_official_merchant_offer_not_in_excel_inventory",
    "new_official_campaign_not_in_excel_inventory", "new_official_campaign_needs_review",
    "ai_needs_review", "official_detail_not_verified", "expired_official_candidate",
}


def apply_verified_official_classification(data, config):
    """Promote only verified, specific, current first-party pages with a strong rule hint."""
    changed = 0
    current = now()
    for item in data.get("items", []):
        if item.get("review_approved") and item.get("review_decision") in {"confirm_campaign","confirm_merchant_offer","confirm_merchant_offers_bulk"}:
            continue
        hint = verified_official_hint(item)
        if not hint:
            continue
        if hint == "expired":
            item["active"] = False
            item["current_status"] = "Expired"
            continue
        listing_verified=hint=="merchant_offer" and trusted_barq_listing_merchant(item,config)
        verified = (item.get("source_verification") or {}).get("status") == "verified_website" or listing_verified
        if not verified or not accepted_direct_source(item, config):
            item["content_type"] = "review"
            item["suggested_record_type"] = hint
            item["review_required"] = True
            item["current_status"] = "Needs Review"
            item["review_reasons"] = list(dict.fromkeys((item.get("review_reasons") or []) + ["official_detail_not_verified"]))
            continue
        status, active = status_for(item, current)
        if not active:
            item["active"] = False
            item["current_status"] = status
            item["suggested_record_type"] = hint
            continue
        previous = item.get("content_type")
        item["content_type"] = hint
        item["suggested_record_type"] = hint
        if hint == "merchant_offer":
            item["campaign_category"] = item["primary_category"] = "merchant"
            item["categories"] = ["merchant"]
        elif item.get("campaign_category") == "merchant":
            item["campaign_category"] = item["primary_category"] = "other"
            item["categories"] = ["other"]
        item["current_status"] = status
        item["active"] = active
        item["review_required"] = False
        item["review_reasons"] = [r for r in (item.get("review_reasons") or []) if r not in _CLASSIFICATION_REVIEW_REASONS]
        item["classification_method"] = "verified_official_listing_merchant_v1" if listing_verified else "verified_official_rules_v6"
        if previous != hint:
            changed += 1
    data["verified_official_classification"] = {"changed": changed, "at": iso(current), "version": CLASSIFIER_VERSION}
    return changed


def classification_content_key(item):
    """Include verification state/evidence so a stale Needs Review cache cannot survive verification."""
    verification = item.get("source_verification") or {}
    return hash_text(
        CLASSIFIER_VERSION,
        item.get("title"), item.get("snippet"), item.get("link"),
        verification.get("status"), verification.get("verification_method"),
        verification.get("source_url"), item.get("evidence_snapshot"),
        item.get("start_date"), item.get("end_date"),
    )

def load(path: Path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def save(path: Path, obj):
    """Atomically replace generated JSON so an interrupted run cannot leave a partial file."""
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)
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

def response_text(response):
    """Prefer UTF-8 for official HTML that omits an HTTP charset."""
    raw=response.content;content_type=response.headers.get("Content-Type","")
    declared=re.search(r"charset\s*=\s*[\"']?([^\s;\"']+)",content_type,re.I)
    tried=set()
    for candidate in [declared.group(1) if declared else None,"utf-8-sig",response.apparent_encoding,response.encoding]:
        encoding=clean(candidate,100).casefold()
        if not encoding or encoding in tried:continue
        tried.add(encoding)
        try:return raw.decode(encoding)
        except (LookupError,UnicodeDecodeError):continue
    return raw.decode("utf-8",errors="replace")

def contains_mojibake(value):
    if isinstance(value,dict):return any(contains_mojibake(v) for v in value.values())
    if isinstance(value,(list,tuple)):return any(contains_mojibake(v) for v in value)
    text=str(value or "")
    return "Ø" in text or "Ù" in text or "\ufffd" in text

def repair_mojibake(value):
    """Recover UTF-8 text that an older run decoded as Latin-1/Windows-1252."""
    if isinstance(value,dict):return {k:repair_mojibake(v) for k,v in value.items()}
    if isinstance(value,list):return [repair_mojibake(v) for v in value]
    if not isinstance(value,str) or not contains_mojibake(value):return value
    for encoding in ("latin-1","cp1252"):
        try:
            fixed=value.encode(encoding).decode("utf-8")
            if not contains_mojibake(fixed):return fixed
        except (UnicodeEncodeError,UnicodeDecodeError):
            continue
    return value.replace("\ufffd","")

def repair_legacy_mobily_text(data):
    changed=0
    for item in data.get("items",[]):
        if item.get("competitor_id")!="mobily-pay":continue
        for field in ("title","summary","snippet","evidence_snapshot"):
            old=item.get(field);new=repair_mojibake(old)
            if contains_mojibake(new):
                if field=="title":
                    match=re.search(r"offer-([^/?#]+)",clean(direct_url(item),1500),re.I)
                    suffix=clean(match.group(1) if match else str(item.get("id") or "").rsplit(":",1)[-1],40)
                    new=f"Mobily Pay offer {suffix or 'pending verification'}"
                else:
                    # The old cleaner collapsed some Latin-1 control bytes to spaces, so
                    # those strings cannot be reconstructed reliably. Clear them and let
                    # the forced official-detail recheck repopulate clean source text.
                    new=None
            if new!=old:item[field]=new;changed+=1
    if changed:data["mobily_text_repairs"]={"fields_repaired":changed,"at":iso(now())}
    return changed

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


_AR_DIGIT_MAP=str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹","01234567890123456789")
_AR_MONTHS={"يناير":1,"فبراير":2,"مارس":3,"أبريل":4,"ابريل":4,"مايو":5,"يونيو":6,"يوليو":7,"أغسطس":8,"اغسطس":8,"سبتمبر":9,"أكتوبر":10,"اكتوبر":10,"نوفمبر":11,"ديسمبر":12}
_EN_MONTHS={"january":1,"jan":1,"february":2,"feb":2,"march":3,"mar":3,"april":4,"apr":4,"may":5,"june":6,"jun":6,"july":7,"jul":7,"august":8,"aug":8,"september":9,"sep":9,"sept":9,"october":10,"oct":10,"november":11,"nov":11,"december":12,"dec":12}
_MONTH_NAMES="January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|يناير|فبراير|مارس|أبريل|ابريل|مايو|يونيو|يوليو|أغسطس|اغسطس|سبتمبر|أكتوبر|اكتوبر|نوفمبر|ديسمبر"
_DATE_FULL=rf"(?:\d{{1,2}}\s+(?:{_MONTH_NAMES})\s*20\d{{2}}|(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{{1,2}},?\s*20\d{{2}}|20\d{{2}}[-/]\d{{1,2}}[-/]\d{{1,2}}|\d{{1,2}}[-/]\d{{1,2}}[-/]20\d{{2}})"
_DATE_FLEX=rf"(?:\d{{1,2}}\s+(?:{_MONTH_NAMES})(?:\s*20\d{{2}})?|(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{{1,2}},?(?:\s*20\d{{2}})?|20\d{{2}}[-/]\d{{1,2}}[-/]\d{{1,2}}|\d{{1,2}}[-/]\d{{1,2}}[-/](?:20\d{{2}}|\d{{2}}))"

def normalize_date_text(value):
    text=clean(value,25000).translate(_AR_DIGIT_MAP).replace("،",",")
    # Sites often concatenate Arabic month and year: أكتوبر2026.
    text=re.sub(r"(?<=[A-Za-z\u0600-\u06FF])(?=20\d{2}\b)"," ",text)
    return text

def parse_human_date(value,default_year=None):
    text=normalize_date_text(value).strip(" .،,;:")
    if not text:return None
    m=re.fullmatch(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})",text)
    if m:
        try:return datetime(int(m.group(1)),int(m.group(2)),int(m.group(3)),tzinfo=timezone.utc)
        except ValueError:return None
    m=re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](20\d{2}|\d{2})",text)
    if m:
        year=int(m.group(3));year=year+2000 if year<100 else year
        try:return datetime(year,int(m.group(2)),int(m.group(1)),tzinfo=timezone.utc)
        except ValueError:return None
    tokens=text.casefold().replace(","," ").split()
    if len(tokens)>=2:
        try:
            day=int(tokens[0]); month_name=tokens[1]; year=int(tokens[2]) if len(tokens)>=3 and tokens[2].isdigit() else default_year
            month=_AR_MONTHS.get(month_name) or _EN_MONTHS.get(month_name)
            if month and year:return datetime(year,month,day,tzinfo=timezone.utc)
        except Exception:pass
        try:
            month=_EN_MONTHS.get(tokens[0]);day=int(tokens[1]);year=int(tokens[2]) if len(tokens)>=3 and tokens[2].isdigit() else default_year
            if month and year:return datetime(year,month,day,tzinfo=timezone.utc)
        except Exception:pass
    try:
        parsed=dateparser.parse(text,dayfirst=True,default=datetime(default_year or now().year,1,1))
        if parsed:
            if parsed.tzinfo is None:parsed=parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
    except Exception:pass
    return None

def first_date(values):
    for v in values:
        d=dt(v) or parse_human_date(v)
        if d:return iso(d.replace(hour=0,minute=0,second=0,microsecond=0))
    return None

def extract_dates_from_text(text):
    """Extract only explicit validity dates; never infer dates from detection/publication time."""
    value=normalize_date_text(text)
    start=end=None;evidence=None
    time_suffix=r"(?:\s*,?\s*at\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?"
    range_patterns=[
        rf"(?:the\s+offer\s+is\s+)?(?:valid|available|offer|campaign|runs?)\s+(?:period\s+)?(?:from\s+)?({_DATE_FLEX}){time_suffix}\s+(?:to|until|through|–|—|-)\s+({_DATE_FLEX})",
        rf"(?:يسري(?:\s+هذا)?\s+العرض|العرض\s+ساري|هذا\s+العرض\s+ساري|ساري|مدة\s+العرض|فترة\s+العرض)?\s*(?:من(?:\s+تاريخ)?|ابتداء(?:ً|ا)?\s+من)\s+({_DATE_FLEX})\s*(?:إلى|الى|و?حتى|ولغاية)\s+({_DATE_FLEX})",
    ]
    for p in range_patterns:
        m=re.search(p,value,re.I)
        if not m:continue
        right=parse_human_date(m.group(2))
        left=parse_human_date(m.group(1),right.year if right else None)
        if left:start=iso(left.replace(hour=0,minute=0,second=0,microsecond=0))
        if right:end=iso(right.replace(hour=0,minute=0,second=0,microsecond=0))
        if start or end:evidence=clean(m.group(0),500);break
    if not end:
        end_patterns=[
            rf"(?:validity(?:\s+(?:until|through))?|valid\s+(?:until|through)|ends?\s+(?:on)?|expires?\s+(?:on)?)\s*[:\-]?\s*({_DATE_FULL})",
            rf"(?:الصلاحية(?:\s+حتى)?|ساري\s+حتى|يسري\s+حتى|ينتهي(?:\s+العرض)?(?:\s+في|\s+بتاريخ)?|تاريخ\s+انتهاء\s+العرض|حتى)\s*[:\-]?\s*({_DATE_FULL})",
        ]
        for p in end_patterns:
            m=re.search(p,value,re.I)
            if m:
                d=parse_human_date(m.group(1))
                if d:end=iso(d.replace(hour=0,minute=0,second=0,microsecond=0));evidence=evidence or clean(m.group(0),500);break
    if not start:
        start_patterns=[
            rf"(?:valid\s+from|starts?\s+(?:on|from)|available\s+from)\s*[:\-]?\s*({_DATE_FULL})",
            rf"(?:هذا\s+العرض\s+ساري\s+من|ساري\s+من|يسري\s+العرض\s+من|يبدأ(?:\s+العرض)?(?:\s+من|\s+في)?|ابتداء(?:ً|ا)?\s+من|اعتبار(?:ًا|ا)?\s+من)\s*[:\-]?\s*({_DATE_FULL})",
        ]
        for p in start_patterns:
            m=re.search(p,value,re.I)
            if m:
                d=parse_human_date(m.group(1))
                if d:start=iso(d.replace(hour=0,minute=0,second=0,microsecond=0));evidence=evidence or clean(m.group(0),500);break
    return start,end,evidence

def date_context(text):
    value=normalize_date_text(text)
    markers=("valid","validity","start","starts","end","ends","expire","campaign period","offer period","يسري","ساري","مدة العرض","فترة العرض","الصلاحية","ينتهي","يبدأ","ابتداء")
    pieces=re.split(r"(?<=[.!?؟])\s+|\n+",value)
    selected=[clean(x,700) for x in pieces if any(m in x.casefold() for m in markers)]
    return "\n".join(selected[:12])[:5000]

def _prepare_detail_soup(html):
    """Return a cleaned soup for campaign-detail extraction, excluding global chrome."""
    soup=BeautifulSoup(html,"html.parser")
    for tag in soup.find_all(["script","style","noscript","svg","nav","header","footer","aside","form"]):
        tag.decompose()
    # Common cookie / generic site chrome containers. Only remove when selectors are explicit.
    for selector in ["[id*='cookie']","[class*='cookie']","[id*='footer']","[class*='footer']","[id*='header']","[class*='header']"]:
        try:
            for tag in soup.select(selector):
                tag.decompose()
        except Exception:
            pass
    return soup


def _detail_scope(soup):
    """Find the smallest campaign-specific DOM region around the primary heading.

    This prevents offer-index carousels / related offers from leaking into one campaign's
    summary and, more importantly, from contributing another offer's validity dates.
    """
    h1=soup.find("h1")
    date_markers=("valid","validity","until","through","يسري","ساري","حتى","مدة العرض","فترة العرض","ينتهي","يبدأ")
    if h1:
        candidates=[]
        for depth,parent in enumerate(h1.parents):
            if getattr(parent,"name",None) in {"html","body"}: break
            if getattr(parent,"name",None) not in {"main","article","section","div"}: continue
            text=clean(parent.get_text(" ",strip=True),12000)
            if len(text)<80: continue
            marker=any(m in text.casefold() for m in date_markers)
            link_count=len(parent.find_all("a",href=True))
            heading_count=len(parent.find_all("h1"))
            # Prefer a compact container that contains validity evidence and only one primary heading.
            score=(0 if marker else 1, 0 if heading_count<=1 else 1, 0 if link_count<=12 else 1, len(text), depth)
            if len(text)<=8000:
                candidates.append((score,parent))
        if candidates:
            candidates.sort(key=lambda x:x[0])
            return candidates[0][1]
    return soup.find("article") or soup.find("main") or soup.body or soup


def _focused_summary(scope,title):
    """Build a concise description from the campaign detail body, never from listing cards."""
    seen=set(); parts=[]
    title_key=clean(title,300).casefold()
    for node in scope.find_all(["p","li"],recursive=True):
        text=clean(node.get_text(" ",strip=True),600)
        key=text.casefold()
        if not text or len(text)<20 or key==title_key or key in seen: continue
        if any(x in key for x in ("cookie","privacy policy","سياسة استخدام ملفات تعريف الارتباط")): continue
        seen.add(key);parts.append(text)
        # The first descriptive paragraph is normally enough for the dashboard card.
        if len(" ".join(parts))>=450 or len(parts)>=2: break
    return clean(" ".join(parts),700) if parts else clean(scope.get_text(" ",strip=True),700)


def extract_page(html,url):
    soup=_prepare_detail_soup(html)
    title=clean((soup.find("meta",property="og:title") or {}).get("content") if soup.find("meta",property="og:title") else "",300) or clean(soup.title.get_text(" ",strip=True) if soup.title else "",300)
    h1=soup.find("h1")
    if h1:
        h1_title=clean(h1.get_text(" ",strip=True),300)
        # Prefer a meaningful H1 when the metadata title is generic / site-branded.
        if h1_title and (not title or len(h1_title)>=len(title)*0.35):
            title=title or h1_title
    scope=_detail_scope(soup)
    focused_text=clean(scope.get_text(" ",strip=True),16000)
    desc_node=soup.find("meta",attrs={"name":"description"}) or soup.find("meta",property="og:description")
    meta_summary=clean(desc_node.get("content") if desc_node else "",700)
    summary=_focused_summary(scope,title) or meta_summary
    pub=[];starts=[];ends=[]
    for obj in jsonld_objects(soup):
        for k in ["datePublished","dateCreated","uploadDate"]:
            if obj.get(k):pub.append(obj[k])
        for k in ["startDate","validFrom"]:
            if obj.get(k):starts.append(obj[k])
        for k in ["endDate","validThrough","expiryDate"]:
            if obj.get(k):ends.append(obj[k])
    for attr,target in [("article:published_time",pub),("offer:valid_from",starts),("offer:valid_through",ends)]:
        n=soup.find("meta",property=attr)
        if n and n.get("content"):target.append(n["content"])
    # Dates/tags/values are extracted only from the campaign-specific detail scope.
    text_start,text_end,evidence=extract_dates_from_text(focused_text)
    structured_start=first_date(starts);structured_end=first_date(ends)
    image=None;n=soup.find("meta",property="og:image")
    if n and n.get("content"):image=urljoin(url,n["content"])
    return {
        "title":title,"summary":summary,"published_at":first_date(pub),"start_date":structured_start or text_start,"end_date":structured_end or text_end,
        "mechanic_tags":mechanics(focused_text),"corridors":corridors(focused_text),"offer_values":offer_values(focused_text),"image":image,
        "evidence_snapshot":evidence or summary or title or None,
        "date_evidence":{"start":evidence if (structured_start or text_start) else None,"end":evidence if (structured_end or text_end) else None},
        "date_context":date_context(focused_text),
        "date_extraction_method":"structured_or_rules" if (structured_start or structured_end or text_start or text_end) else "not_found",
        "content_hash":hash_text(title,summary,focused_text[:12000])
    }

def ai_fill_dates(ex,state,config):
    global AI_DATE_CALLS_THIS_RUN
    """Optional cached AI fallback for explicit dates that rule-based parsing missed."""
    if not config.get("ai",{}).get("date_extraction_enabled",True):return ex
    if ex.get("start_date") and ex.get("end_date"):return ex
    context=clean(ex.get("date_context"),5000)
    if not context or not os.environ.get("OPENAI_API_KEY"):return ex
    cache=state.setdefault("ai_date_cache",{});key=ex.get("content_hash") or hash_text(context)
    cached=cache.get(key)
    if cached:
        result=cached.get("result") or {}
    else:
        max_calls=int(config.get("ai",{}).get("date_extraction_max_items_per_run",6))
        if AI_DATE_CALLS_THIS_RUN>=max_calls:return ex
        client=openai_client(config)
        if not client:return ex
        model=config.get("ai",{}).get("date_extraction_model",config.get("ai",{}).get("classification_model","gpt-5.6-terra"))
        schema={"type":"object","additionalProperties":False,"properties":{"start_date":{"type":["string","null"]},"end_date":{"type":["string","null"]},"evidence":{"type":["string","null"]}},"required":["start_date","end_date","evidence"]}
        prompt="Extract campaign validity dates ONLY when explicitly stated in the supplied official-source text. Return ISO YYYY-MM-DD. If a date is not explicitly supported, return null. You may infer a missing year on the first date only when an explicit date range gives the year on the second date. Never use publication, detection, current date, or guesswork."
        try:
            r=client.responses.create(model=model,reasoning={"effort":config.get("ai",{}).get("date_extraction_reasoning","low")},text={"format":{"type":"json_schema","name":"date_extraction","schema":schema,"strict":True}},input=[{"role":"system","content":prompt},{"role":"user","content":context}])
            result=json.loads(r.output_text);inp,out=usage_numbers(r);add_usage(state,"date_extraction",model,inp,out,config);AI_DATE_CALLS_THIS_RUN+=1;cache[key]={"result":result,"at":iso(now())}
        except Exception as exc:
            print(f"[AI date extraction] {type(exc).__name__}: {exc}");return ex
    for field in ("start_date","end_date"):
        if ex.get(field):continue
        raw=result.get(field);d=dt(raw) or parse_human_date(raw)
        if d:ex[field]=iso(d.replace(hour=0,minute=0,second=0,microsecond=0))
    if result.get("evidence") and (ex.get("start_date") or ex.get("end_date")):
        ex["date_evidence"]={"start":result.get("evidence") if ex.get("start_date") else None,"end":result.get("evidence") if ex.get("end_date") else None}
        ex["evidence_snapshot"]=clean(result.get("evidence"),500)
        ex["date_extraction_method"]="ai_explicit_text"
    return ex

def manual_patch(overrides,item_id): return (overrides.get("items") or {}).get(item_id,{})

def deletion_tombstones(overrides):
    return [patch for patch in (overrides.get("items") or {}).values() if isinstance(patch,dict) and patch.get("deleted")]

def deleted_by_override(item, overrides):
    patch=manual_patch(overrides,item.get("id"))
    if patch.get("deleted"): return True
    comp=item.get("competitor_id") or ""; key=campaign_title_key(item.get("title"))
    if not key: return False
    for tomb in deletion_tombstones(overrides):
        if (tomb.get("deleted_competitor_id") or "")==comp and campaign_title_key(tomb.get("deleted_title"))==key:
            return True
    return False

def apply_manual_deletions(data, overrides):
    before=len(data.get("items",[]))
    data["items"]=[i for i in data.get("items",[]) if not deleted_by_override(i,overrides)]
    valid={i.get("id") for i in data.get("items",[]) if i.get("content_type") in {"campaign","merchant_offer"}}
    for row in data.get("items",[]):
        broken=False
        for field in ("campaign_id","linked_campaign_id","suggested_campaign_id"):
            if row.get(field) and row.get(field) not in valid:
                row[field]=None;broken=True
        if broken and row.get("source_type")=="social":
            row["review_required"]=True;row["current_status"]="Needs Review"
            reasons=list(row.get("review_reasons") or [])
            if "linked_campaign_deleted" not in reasons: reasons.append("linked_campaign_deleted")
            row["review_reasons"]=reasons
    return before-len(data.get("items",[]))

def append_change(item,typ,details=None):
    h=item.setdefault("change_history",[])
    h.append({"at":iso(now()),"type":typ,"details":details or {}})
    item["change_history"]=h[-30:]

def add_manual_new_items(data, overrides):
    existing={i.get("id") for i in data.get("items",[])}
    for row in overrides.get("new_items",[]) or []:
        if not row.get("id") or row["id"] in existing: continue
        if manual_patch(overrides,row["id"]).get("deleted"): continue
        approved=bool(row.get("review_approved"))
        item={
            "id":row["id"],"record_id":None,"competitor_id":row.get("competitor_id"),"source_key":f"manual:{row.get('competitor_id')}","source_type":"manual","platform":"website",
            "content_type":row.get("content_type","campaign"),"suggested_record_type":row.get("content_type","campaign"),"campaign_category":row.get("campaign_category","other"),"primary_category":row.get("campaign_category","other"),"categories":[row.get("campaign_category","other")],
            "title":row.get("title") or "New campaign pending source analysis","snippet":row.get("summary","") ,"summary":row.get("summary",""),"link":row.get("official_campaign_page_url") or row.get("primary_official_source_url"),
            "official_campaign_page_url":row.get("official_campaign_page_url"),"primary_official_source_url":row.get("primary_official_source_url") or row.get("official_campaign_page_url"),"social_links":row.get("social_links",{}),
            "published_at":row.get("published_at"),"start_date":row.get("start_date"),"end_date":row.get("end_date"),"current_status":"Needs Review","active":row.get("active",True),"operation_type":row.get("operation_type","") ,"mechanic":row.get("mechanic","") ,"eligibility":row.get("eligibility","") ,"terms_note":row.get("terms_note",""),
            "verified":False,"review_required":not approved,"review_reasons":[] if approved else ["manual_new_campaign_pending_verification"],"manual_override":True,"first_seen":row.get("created_at") or iso(now()),"last_changed":row.get("created_at") or iso(now()),"change_history":[],
            "review_approved":approved,"review_decision":row.get("review_decision"),"reviewed_by":row.get("reviewed_by"),"reviewed_at":row.get("reviewed_at"),"review_request_id":row.get("review_request_id"),"evidence_ids":row.get("evidence_ids") or []
        }
        append_change(item,"manual_created")
        data.setdefault("items",[]).append(item); existing.add(item["id"])

def is_manual_source_candidate(item):
    """Manual Add Campaign records must be verified immediately from their supplied source URL."""
    if item.get("source_type") != "manual":
        return False
    url=direct_url(item)
    return bool(url and str(url).startswith(("http://","https://")))

def manual_pending_review(item):
    reasons=set(item.get("review_reasons") or [])
    return is_manual_source_candidate(item) and (
        not item.get("verified")
        or (item.get("source_verification") or {}).get("status") not in {"verified_website","verified_social"}
        or bool(reasons & {"manual_new_campaign_pending_verification","manual_source_verification_failed","official_detail_not_verified"})
    )

def clear_manual_verification_review(item):
    reasons=[r for r in (item.get("review_reasons") or []) if r not in {
        "manual_new_campaign_pending_verification",
        "manual_source_verification_failed",
        "official_detail_not_verified",
        "missing_direct_official_source",
        "generic_social_source_not_evidence",
    }]
    item["review_reasons"]=reasons
    if not reasons:
        item["review_required"]=False
    if item.get("content_type")=="review":
        item["content_type"]=item.get("suggested_record_type") or "campaign"


def verify_details(data,state,config,overrides,competitor_filter=None):
    cache=state.setdefault("detail_cache",{})
    interval=float(config.get("settings",{}).get("detail_verification_interval_hours",6))
    missing_interval=float(config.get("settings",{}).get("detail_verification_missing_date_hours",2))
    expiring_interval=float(config.get("settings",{}).get("detail_verification_expiring_hours",2))
    timeout=int(config.get("settings",{}).get("request_timeout_seconds",18))
    competitor_filter=clean(competitor_filter or "").strip()
    if competitor_filter.casefold() in {"", "all", "*"}:competitor_filter=""
    max_checks=int(config.get("settings",{}).get("max_detail_checks_per_run",24))
    if competitor_filter:
        max_checks=max(max_checks,int(config.get("settings",{}).get("manual_refresh_max_detail_checks",60)))
    time_budget=float(config.get("settings",{}).get("detail_verification_time_budget_seconds",150))
    max_timeout=max(5,int(config.get("settings",{}).get("detail_verification_max_timeout_seconds",12)))
    retries=max(0,int(config.get("settings",{}).get("detail_verification_retries",0)))
    current=now(); checks=0; new_status=[]; skip=os.environ.get("CM_SKIP_NETWORK")=="1"
    budget_notice_printed=False
    perf_started=time.perf_counter()
    session=requests.Session(); session.headers.update({"User-Agent":USER_AGENT,"Accept-Language":"en,ar;q=0.9"})
    retry=Retry(total=retries,connect=retries,read=0,backoff_factor=.3,status_forcelist=[429,500,502,503,504],allowed_methods=["GET"])
    session.mount("https://",HTTPAdapter(max_retries=retry));session.mount("http://",HTTPAdapter(max_retries=retry))

    candidates=[]
    for item in data.get("items",[]):
        if competitor_filter and item.get("competitor_id")!=competitor_filter:continue
        is_counted=item.get("content_type") in {"campaign","merchant_offer"}
        is_official_candidate=(item.get("source_type")=="website" and item.get("official_discovery") and item.get("content_type")=="review")
        is_manual_candidate=is_manual_source_candidate(item)
        if not (is_counted or is_official_candidate or is_manual_candidate):continue
        if item.get("active") is False and item.get("source_type")!="manual" and not is_official_candidate:continue
        candidates.append(item)
    # Manual Add Campaign verification is highest priority, then newly discovered official pages.
    candidates.sort(key=lambda x:(
        0 if manual_pending_review(x) else 1,
        0 if (x.get("source_type")=="website" and x.get("official_discovery")) else 1,
        0 if verified_official_hint(x) in {"campaign","merchant_offer"} else 1,
        0 if not x.get("end_date") else 1,
        0 if not x.get("start_date") else 1,
        dt((cache.get(x.get("id")) or {}).get("checked_at")) or datetime.min.replace(tzinfo=timezone.utc)
    ))

    for item in candidates:

        if item.get("competitor_id")=="mobily-pay":
            for field in ("title","summary","snippet","evidence_snapshot"):
                if field in item:item[field]=repair_mojibake(item.get(field))

        existing_sv=item.get("source_verification") or {}
        if existing_sv.get("status")=="verified_website" and existing_sv.get("verification_method")=="official_website_modal" and item.get("source_locator"):
            item["verified"]=True
            st,active=status_for(item,current)
            manual=manual_patch(overrides,item["id"])
            if "current_status" not in manual:item["current_status"]=st
            if "active" not in manual:item["active"]=active
            continue

        url=direct_url(item)
        if not url or not str(url).startswith("http"): continue
        manual=manual_patch(overrides,item["id"])
        manual_candidate=is_manual_source_candidate(item)

        # Social networks must never be scraped as campaign-detail webpages.
        # Their public HTML often returns login/navigation shells instead of post content.
        if social_url(url):
            item["evidence_snapshot"]=None
            is_specific=specific_social_post_url(url)
            item["source_verification"]={
                "status":"verified_social" if is_specific else "needs_review",
                "verification_method":"official_social_rss_or_inventory" if is_specific else "generic_social_url",
                "checked_at":iso(current),
                "source_url":url,
                "source_changed":False,
                "conflicts":[],
                "error":None if is_specific else "Generic social profile/page is not sufficient campaign evidence.",
            }
            item["verified"]=bool(is_specific)
            if is_specific:
                item["last_reviewed"]=item.get("last_reviewed") or iso(current)
                if manual_candidate:
                    clear_manual_verification_review(item)
                    append_change(item,"manual_source_verified",{"source":url,"method":"official_social"})
            item.pop("media", None)
            st,active=status_for(item,current)
            if "current_status" not in manual:item["current_status"]=st if is_specific else "Needs Review"
            if "active" not in manual:item["active"]=active
            if not is_specific:
                item["review_required"]=True
                if manual_candidate:
                    item["content_type"]="review"
                    item["suggested_record_type"]=item.get("suggested_record_type") or "campaign"
                item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["generic_social_source_not_evidence"]))
            continue

        cached=cache.get(item["id"],{})
        # Do not let a legacy Latin-1-decoded Mobily detail cache overwrite the
        # clean UTF-8 listing text produced by monitor.py. Invalid entries are
        # removed and will be fetched again within the normal verification quota.
        if item.get("competitor_id")=="mobily-pay" and contains_mojibake(cached.get("extracted")):
            cache.pop(item["id"],None)
            cached={}
        last=dt(cached.get("checked_at"))
        # Force one immediate re-verification whenever the detail-extraction algorithm changes.
        # This cleans legacy listing-page contamination without waiting for the normal interval.
        # The offers indexes are checked every hour by monitor.py. Re-opening every known detail
        # page every hour adds latency without materially improving discovery. New/manual pages are
        # immediate; pages missing dates and near-expiry pages are checked more often; stable, fully
        # dated pages use the normal detail interval.
        item_interval=interval
        if not item.get("start_date") or not item.get("end_date"):
            item_interval=min(item_interval,missing_interval)
        end_dt=dt(item.get("end_date"))
        if end_dt and current<=end_dt<=current+timedelta(days=30):
            item_interval=min(item_interval,expiring_interval)
        due=(
            not last
            or current-last>=timedelta(hours=item_interval)
            or cached.get("extractor_version")!=DETAIL_EXTRACTOR_VERSION
            or (manual_candidate and (cached.get("url")!=url or manual_pending_review(item)))
        )

        # Admin-added campaigns get an immediate verification slot and cannot be starved by
        # the normal detail-page quota. They are few and explicitly requested by the user.
        elapsed_now=time.perf_counter()-perf_started
        within_budget=elapsed_now<time_budget
        if due and not within_budget and not skip and not budget_notice_printed:
            print(f"[PERF] detail verification time budget reached at {elapsed_now:.1f}s; remaining pages keep last-known-good data.",flush=True)
            budget_notice_printed=True
        if due and (manual_candidate or checks<max_checks) and not skip and within_budget:
            checks+=1
            detail_status={
                "source_key":f"detail:{item['id']}",
                "competitor_id":item.get("competitor_id"),
                "source_type":"campaign_detail",
                "platform":"website",
                "url":url,
                "checked_at":iso(current),
                "success":False,
                "item_count":0,
                "error":None,
            }
            try:
                item_timeout=min(max_timeout,max(5,int(item.get("detail_timeout_seconds") or timeout)))
                print(f"[DETAIL {checks}/{max_checks}] {item.get('competitor_id')} · timeout={item_timeout}s",flush=True)
                r=session.get(url,timeout=item_timeout)
                r.raise_for_status()
                ex=ai_fill_dates(extract_page(response_text(r),url),state,config)
                old_hash=(cached.get("extracted") or {}).get("content_hash")
                cached={
                    "checked_at":iso(current),
                    "last_success_at":iso(current),
                    "success":True,
                    "url":url,
                    "extracted":ex,
                    "extractor_version":DETAIL_EXTRACTOR_VERSION,
                    "error":None,
                }
                cache[item["id"]]=cached
                detail_status.update(success=True,item_count=1,last_success_at=iso(current))
                if old_hash and old_hash!=ex.get("content_hash"):
                    append_change(item,"source_content_changed")
            except Exception as exc:
                cached={
                    **cached,
                    "checked_at":iso(current),
                    "success":False,
                    "url":url,
                    "error":clean(f"{type(exc).__name__}: {exc}",500),
                }
                cache[item["id"]]=cached
                detail_status["error"]=cached["error"]
                detail_status["last_success_at"]=cached.get("last_success_at")
            print(f"[DETAIL {checks}/{max_checks}] {'ok' if detail_status.get('success') else 'failed'} · {item.get('competitor_id')}",flush=True)
            new_status.append(detail_status)

        ex=cached.get("extracted") or {}
        if not ex:
            item["source_verification"]={
                "status":"failed" if cached.get("checked_at") else "needs_review",
                "verification_method":"official_website_page",
                "checked_at":cached.get("checked_at"),
                "source_url":url,
                "source_changed":False,
                "conflicts":[],
                "error":cached.get("error"),
            }
            if manual_candidate and item.get("review_approved"):
                # The Admin decision is authoritative. review.yml intentionally rebuilds
                # without network access, so a newly grouped campaign must become visible
                # immediately. The next scheduled monitor run still retries source
                # verification and exposes any failure through Source Health.
                item["verified"]=False
                item["review_required"]=False
                item["review_reasons"]=[]
                item["current_status"],item["active"]=status_for(item,current)
            elif manual_candidate:
                item["verified"]=False
                item["content_type"]="review"
                item["suggested_record_type"]=item.get("suggested_record_type") or "campaign"
                item["current_status"]="Needs Review"
                item["review_required"]=True
                item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["manual_source_verification_failed"]))
            continue

        conflicts=[]
        for field in ["published_at","start_date","end_date"]:
            src=ex.get(field); old=item.get(field)
            if src and old and dt(src) and dt(old) and abs((dt(src)-dt(old)).total_seconds())>36*3600:
                conflicts.append({"field":field,"current":old,"source":src})
            if src and field not in manual and src!=old:
                item[field]=src
                append_change(item,f"{field}_updated",{"from":old,"to":src})

        placeholder_titles={"new campaign pending source analysis","new campaign"}
        current_title=clean(item.get("title"),300)
        technical_placeholder=bool(re.fullmatch(r"mobily pay offer [^ ]+",current_title.casefold()))
        damaged_mobily_title=item.get("competitor_id")=="mobily-pay" and contains_mojibake(current_title)
        if ex.get("title") and (not current_title or current_title.casefold() in placeholder_titles or technical_placeholder or damaged_mobily_title) and "title" not in manual:
            item["title"]=ex["title"]
        if ex.get("summary") and "summary" not in manual:
            current_summary=clean(item.get("summary") or item.get("snippet"),5000)
            # Official detail content is authoritative for auto-discovered records. Also repair
            # legacy listing-page contamination (very long card/list text merged into a campaign).
            contaminated=(
                len(current_summary)>700
                or len(re.findall(r"(?:حتى|until|through)\s+[^,.؛]{0,35}20\d{2}",current_summary,re.I))>=3
                or len(re.findall(r"\b\d{1,3}%",current_summary))>=4
            )
            if item.get("source_type")=="website" or item.get("official_discovery") or manual_candidate or not current_summary or contaminated:
                item["summary"]=item["snippet"]=ex["summary"]

        item["mechanic_tags"]=list(dict.fromkeys((item.get("mechanic_tags") or [])+(ex.get("mechanic_tags") or [])))
        item["corridors"]=ex.get("corridors") or item.get("corridors") or []
        item["offer_values"]=ex.get("offer_values") or item.get("offer_values") or []
        item["evidence_snapshot"]=ex.get("evidence_snapshot")
        if ex.get("date_evidence"):item["date_evidence"]=ex.get("date_evidence")
        if ex.get("date_extraction_method"):item["date_extraction_method"]=ex.get("date_extraction_method")
        # Campaign hero media is allowed only when it was extracted from this exact
        # official campaign-detail webpage. This overwrites/removes stale social media
        # accidentally attached by older monitor versions.
        if ex.get("image"):
            item["media"]={
                "type":"image",
                "url":ex["image"],
                "thumbnail_url":ex["image"],
                "source_type":"official_website",
                "source_url":url,
            }
        else:
            item.pop("media", None)

        item["source_verification"]={
            "status":"verified_website" if cached.get("success") else "failed",
            "verification_method":"official_website_page",
            "checked_at":cached.get("checked_at"),
            "source_url":url,
            "source_changed":bool(conflicts),
            "conflicts":conflicts,
            "error":cached.get("error"),
        }
        if cached.get("success"):
            item["verified"]=True
            item["last_live_verified_at"]=cached.get("checked_at")
            item["last_reviewed"]=cached.get("checked_at")
            if manual_candidate:
                clear_manual_verification_review(item)
                # Preserve an admin-entered mechanic; otherwise provide a factual compact value
                # from deterministic page extraction rather than leaving the field blank.
                if not item.get("mechanic") and "mechanic" not in manual:
                    parts=[]
                    if item.get("mechanic_tags"):parts.extend(str(x).replace("_"," ").title() for x in item.get("mechanic_tags",[])[:2])
                    if item.get("offer_values"):parts.extend(str(x) for x in item.get("offer_values",[])[:2])
                    if parts:item["mechanic"]=" · ".join(dict.fromkeys(parts))
                append_change(item,"manual_source_verified",{"source":url,"method":"official_website"})

        st,active=status_for(item,current)
        if "current_status" not in manual: item["current_status"]=st
        if "active" not in manual: item["active"]=active
        if conflicts:
            item["review_required"]=True
            item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["official_source_conflict"]))

    if new_status:
        old={s.get("source_key"):s for s in data.get("source_status",[])}
        for source_status in new_status:
            old[source_status["source_key"]]=source_status
        data["source_status"]=sorted(old.values(),key=lambda x:x.get("source_key",""))
    elapsed=round(time.perf_counter()-perf_started,1)
    data["detail_verification_stats"]={
        "network_checks":checks,
        "elapsed_seconds":elapsed,
        "completed_at":iso(now()),
    }
    print(f"[PERF] detail verification: {checks} network checks in {elapsed:.1f}s",flush=True)

def tokenize(text):
    return {x for x in re.findall(r"[\w%]+",clean(text,5000).casefold()) if len(x)>2}

def heuristic_match(post,campaigns):
    pt=tokenize(f"{post.get('title','')} {post.get('snippet','')}")
    best=(0,None)
    for c in campaigns:
        # Exact known social URL is strongest.
        if post.get("link"):
            pid=social_identity(post.get("link"))
            if pid and any(pid==social_identity(u) for u in (c.get("social_links") or {}).values() if u):return c["id"],"exact_url"
        evidence=post.get("official_evidence_url") or post.get("official_campaign_page_url")
        if evidence:
            eid=detail_url_identity(evidence)
            campaign_urls=[c.get("official_campaign_page_url"),c.get("primary_official_source_url"),c.get("link")]
            if eid and any(eid==detail_url_identity(value) for value in campaign_urls if value):
                return c["id"],"exact_official_evidence"
        ct=tokenize(f"{c.get('title','')} {c.get('summary','')} {c.get('mechanic','')} {c.get('terms_note','')}")
        union=len(pt|ct) or 1; lexical=len(pt&ct)/union
        cat_bonus=.18 if post.get("campaign_category") and post.get("campaign_category")==c.get("campaign_category") else 0
        corr_bonus=.18 if set(post.get("corridors") or []) & set(c.get("corridors") or []) else 0
        value=lexical+cat_bonus+corr_bonus
        if value>best[0]: best=(value,c["id"])
    if best[0]>=.36:return best[1],"heuristic"
    if best[0]>=.20:return best[1],"suggested"
    return None,None


_MERCHANT_MATCH_STOP = {
    "a", "al", "an", "and", "at", "by", "enjoy", "exclusive", "experience", "for", "from",
    "get", "in", "la", "of", "off", "on", "offer", "offers", "shopping", "the", "to", "up",
    "use", "using", "valid", "with", "your", "discount", "cashback", "cash", "back", "promo",
    "code", "card", "cards", "visa", "store", "restaurant", "hotel", "cafe", "shop",
    "barq", "stc", "bank", "mobily", "pay", "urpay", "tiqmo", "alinma",
    "international", "transfer", "transfers", "transaction", "transactions", "send", "money",
    "fee", "fees", "free", "platinum", "spend", "win", "winner", "winners", "draw", "prize",
    "reward", "rewards", "purchase", "purchases", "products", "school", "back", "more", "sar",
    "jan", "january", "feb", "february", "mar", "march", "apr", "april", "may", "jun", "june",
    "jul", "july", "aug", "august", "sep", "sept", "september", "oct", "october", "nov", "november", "dec", "december",
    "استمتع", "استمتعوا", "احصل", "احصلوا", "استخدم", "استخدموا", "عرض", "عروض", "خصم",
    "بخصم", "كاش", "باك", "كود", "رمز", "القسيمة", "في", "من", "مع", "لدى", "على",
    "عند", "الدفع", "باستخدام", "بطاقة", "بطاقات", "فيزا", "حتى", "رائعة", "أجواء",
    "بأجواء", "اجواء", "باجواء", "متجر", "مطعم", "فندق", "كافيه", "مقهى", "تسوق",
    "برق", "تكمو", "يورباي", "موبايلي", "الانماء", "الإنماء", "باي",
    "تحويل", "حوالة", "حوالات", "دولي", "دولية", "الدولية", "رسوم", "مجاني", "مجانية",
    "اربح", "فائز", "فائزين", "سحب", "جائزة", "جوائز", "مكافأة", "مكافآت", "مشتريات",
    "منتجات", "العودة", "مدارس", "المدارس", "ريال",
}

_SOCIAL_LINK_REVIEW_REASONS = {
    "social_campaign_match_uncertain", "social_post_cannot_create_campaign", "ai_needs_review",
    "new_social_campaign_needs_review", "invalid_cross_competitor_match", "merchant_offer_match_conflict",
    "potential_merchant_offer_unmatched",
}


def _merchant_match_tokens(value):
    """Return name-bearing tokens while removing generic offer and competitor language."""
    text=html_lib.unescape(clean(value,6000))
    text=unicodedata.normalize("NFKC",text).casefold().replace("ـ","")
    text=ARABIC_DIACRITICS.sub("",text)
    text=text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹","01234567890123456789"))
    text=re.sub(r"[^\w]+"," ",text,flags=re.UNICODE)
    return [
        token for token in text.split()
        if token not in _MERCHANT_MATCH_STOP
        and not token.isdigit()
        and len(token)>=2
        and not re.fullmatch(r"20\d{2}",token)
    ]


def _item_url_tokens(item):
    tokens=set()
    for value in (item.get("official_campaign_page_url"),item.get("primary_official_source_url"),item.get("link")):
        if not value or social_url(value):continue
        try:
            parts=urlsplit(str(value));segments=[unquote(segment) for segment in parts.path.split("/") if segment]
            for segment in segments[-2:]:
                tokens.update(_merchant_match_tokens(re.sub(r"[_-]+"," ",segment)))
        except Exception:
            continue
    return tokens


def _merchant_anchor_tokens(item):
    # Include the official slug even when the visible title is Arabic. This safely joins
    # bilingual versions such as "ميموزا" / "Mimosa" without a merchant-by-merchant taxonomy.
    return set(_merchant_match_tokens(item.get("title"))) | _item_url_tokens(item)


def _offer_match_values(value):
    """Comparable benefit values. Percentages and promo codes are safer than spend thresholds."""
    text=normalize_date_text(value).casefold()
    found={f"pct:{m.group(1).lstrip('0') or '0'}" for m in re.finditer(r"(\d{1,3}(?:\.\d+)?)\s*%",text)}
    code_patterns=(
        r"(?:promo\s*code|coupon\s*code|code)\s*[:\-]?\s*[\"']?([a-z0-9][a-z0-9_-]{2,19})",
        r"(?:كود(?:\s+الخصم)?|رمز(?:\s+القسيمة)?)\s*[:\-]?\s*[\"']?([a-z0-9][a-z0-9_-]{2,19})",
    )
    for pattern in code_patterns:
        found.update(f"code:{match.casefold()}" for match in re.findall(pattern,text,re.I))
    # Prize/cashback amounts distinguish otherwise similar spend-and-win campaigns. Only
    # capture an SAR amount when nearby wording says it is a prize/reward, not a spend floor.
    amount_pattern=r"(?:\bsar\s*([\d,]{2,})|([\d,]{2,})\s*(?:sar\b|ريال))"
    for match in re.finditer(amount_pattern,text,re.I):
        context=text[max(0,match.start()-70):match.end()+70]
        if not re.search(r"\b(?:win|winner|prize|cashback|reward)\b|(?:اربح|ربح|فائز|جائزة|كاش\s*باك|مكافأة)",context,re.I):continue
        amount=(match.group(1) or match.group(2) or "").replace(",","").lstrip("0") or "0"
        found.add(f"prize_sar:{amount}")
    return found


def _website_backed_merchant(item):
    if item.get("content_type")!="merchant_offer":return False
    url=item.get("official_campaign_page_url") or item.get("primary_official_source_url") or item.get("link")
    if not url or social_url(url):return False
    verification=item.get("source_verification") or {}
    return bool(
        verification.get("status")=="verified_website"
        or item.get("verified")
        or item.get("review_approved")
        or item.get("source_type") in {"inventory","manual"}
    )


def _merchant_date_compatibility(post,offer):
    post_start=dt(post.get("start_date"));post_end=dt(post.get("end_date"));published=dt(post.get("published_at"))
    offer_start=dt(offer.get("start_date"));offer_end=dt(offer.get("end_date"))
    if post_end and offer_end and post_end.date()!=offer_end.date():return False,0.0
    if post_start and offer_end and post_start.date()>offer_end.date():return False,0.0
    if post_end and offer_start and post_end.date()<offer_start.date():return False,0.0
    if published and offer_start and published.date()<(offer_start-timedelta(days=14)).date():return False,0.0
    if published and offer_end and published.date()>(offer_end+timedelta(days=2)).date():return False,0.0
    dated=bool(post_start or post_end or published) and bool(offer_start or offer_end)
    return True,0.14 if dated else 0.0


def _extract_social_offer_dates(post):
    """Capture only explicit full validity dates printed in the official social post."""
    if post.get("start_date") and post.get("end_date"):return
    start,end,evidence=extract_dates_from_text(f"{post.get('title','')} {post.get('snippet','')}")
    if start and not post.get("start_date"):post["start_date"]=start
    if end and not post.get("end_date"):post["end_date"]=end
    if evidence and (start or end):
        date_evidence=dict(post.get("date_evidence") or {})
        date_evidence["official_social_post"]=evidence
        post["date_evidence"]=date_evidence
        post["date_extraction_method"]="official_social_explicit_text"


def merchant_offer_match(post,candidates,include_inactive=False):
    """Match an official social poster to one existing website-backed Merchant Offer.

    A unique merchant name is required. Benefit values and validity dates disambiguate
    repeated offers from the same merchant. Conflicts never auto-link.
    """
    if is_winner_announcement(post):return None,None
    offers=[row for row in candidates if (include_inactive or row.get("active") is not False) and _website_backed_merchant(row)]
    if not offers:return None,None

    # A direct outbound link to one specific website offer is conclusive. Shared modal/index
    # URLs can point at many offers and therefore are deliberately excluded from this shortcut.
    evidence_urls=[post.get("official_evidence_url"),post.get("official_campaign_page_url")]
    evidence_urls.extend(post.get("outbound_links") or [])
    evidence_ids={detail_url_identity(value) for value in evidence_urls if value and not social_url(value)}
    exact=[]
    for offer in offers:
        verification=offer.get("source_verification") or {}
        if verification.get("verification_method")=="official_website_modal" or offer.get("source_detail_type")=="modal":continue
        offer_ids={detail_url_identity(value) for value in (offer.get("official_campaign_page_url"),offer.get("primary_official_source_url"),offer.get("link")) if value and not social_url(value)}
        if evidence_ids & offer_ids:exact.append(offer)
    if len(exact)==1:return exact[0]["id"],"merchant_offer_exact_evidence"

    post_tokens=set(_merchant_match_tokens(f"{post.get('title','')} {post.get('snippet','')}")) | _item_url_tokens(post)
    post_values=_offer_match_values(f"{post.get('title','')} {post.get('snippet','')}")
    scored=[];conflicted=[]
    for offer in offers:
        # Score the visible merchant name and official URL slug as alternative anchors.
        # Joining them into one required token set would make an Arabic title + English slug
        # impossible to match to either language on social media.
        anchors=[set(_merchant_match_tokens(offer.get("title"))),_item_url_tokens(offer)]
        name_score=0.0
        for anchor in [value for value in anchors if value]:
            overlap=anchor&post_tokens
            if len(anchor)==1:
                token=next(iter(anchor));score=.76 if len(token)>=4 and token in post_tokens else 0.0
            elif anchor<=post_tokens:
                score=.80
            elif len(overlap)>=2 and len(overlap)/len(anchor)>=.67:
                score=.62
            else:
                score=0.0
            name_score=max(name_score,score)
        if not name_score:continue

        offer_values=_offer_match_values(f"{offer.get('title','')} {offer.get('summary','')} {offer.get('snippet','')} {offer.get('mechanic','')}")
        post_pct={v for v in post_values if v.startswith("pct:")};offer_pct={v for v in offer_values if v.startswith("pct:")}
        post_codes={v for v in post_values if v.startswith("code:")};offer_codes={v for v in offer_values if v.startswith("code:")}
        if post_pct and offer_pct and not (post_pct&offer_pct):conflicted.append(offer);continue
        if post_codes and offer_codes and not (post_codes&offer_codes):conflicted.append(offer);continue
        compatible,date_bonus=_merchant_date_compatibility(post,offer)
        if not compatible:conflicted.append(offer);continue
        value_bonus=.20 if post_values&offer_values else 0.0
        scored.append((name_score+value_bonus+date_bonus,offer))

    if not scored:
        if conflicted:return (conflicted[0].get("id") if len(conflicted)==1 else None),"merchant_offer_conflict"
        return None,None
    scored.sort(key=lambda row:(row[0],row[1].get("end_date") or "",row[1].get("id") or ""),reverse=True)
    best_score,best=scored[0]
    second_score=scored[1][0] if len(scored)>1 else 0.0
    if best_score>=.76 and (len(scored)==1 or best_score-second_score>=.15):
        return best["id"],"merchant_name_value_date"
    if best_score>=.62:return best["id"],"merchant_offer_suggested"
    return None,None


def _sync_linked_merchant_dates(offer,post):
    """Website remains authoritative; social evidence only fills a missing explicit date."""
    changed=False
    for field in ("start_date","end_date"):
        if not offer.get(field) and post.get(field):offer[field]=post[field];changed=True
    if changed:
        evidence=(post.get("date_evidence") or {}).get("official_social_post")
        if evidence:
            date_evidence=dict(offer.get("date_evidence") or {})
            date_evidence["official_social_post"]=evidence
            offer["date_evidence"]=date_evidence
        offer["date_extraction_method"]="linked_official_social_post"
    return changed


def _link_social_post(post,target,method):
    post["campaign_id"]=target["id"]
    post["content_type"]="social_post"
    post["match_method"]=method
    post.pop("suggested_campaign_id",None)
    post.pop("suggested_record_type",None)
    remaining=[reason for reason in (post.get("review_reasons") or []) if reason not in _SOCIAL_LINK_REVIEW_REASONS]
    post["review_reasons"]=remaining
    post["review_required"]=bool(remaining)
    if not remaining and post.get("current_status")=="Needs Review":post["current_status"]=None
    if target.get("content_type")=="merchant_offer":_sync_linked_merchant_dates(target,post)


def social_classification_content_key(post,candidates):
    """Invalidate a cached social decision whenever available match targets change."""
    target_keys=sorted(hash_text(
        row.get("id"),row.get("title"),row.get("content_type"),row.get("active"),
        row.get("start_date"),row.get("end_date"),row.get("official_campaign_page_url"),
        json.dumps(row.get("offer_values") or [],ensure_ascii=False,sort_keys=True),
    ) for row in candidates)
    return hash_text(SOCIAL_MATCHER_VERSION,classification_content_key(post),*target_keys)


_CAMPAIGN_MATCH_STOP={
    "a","an","and","at","by","for","from","in","of","on","or","the","to","up","with","your",
    "offer","offers","campaign","campaigns","promotion","promotions","exclusive","use","using","valid",
    "barq","stc","bank","mobily","pay","urpay","tiqmo","alinma",
    "عرض","عروض","حملة","حملات","استخدم","استخدموا","ساري","حتى","في","من","مع","على","لدى","عند",
    "برق","تكمو","يورباي","موبايلي","الانماء","الإنماء","باي",
}
_CONCRETE_MECHANIC_TAGS={"discount","cashback","fee_waiver","prize_draw","reward","preferred_rate","spend_reward","referral"}
_PRODUCT_TAGS={"remittance","musaned","sadad","card","salary","travel","bill_payment","wallet"}
_AUTO_SOCIAL_REVIEW_REASONS={
    "social_campaign_match_uncertain","social_post_cannot_create_campaign","ai_needs_review",
    "new_social_campaign_needs_review","potential_merchant_offer_unmatched","invalid_cross_competitor_match",
}


def _campaign_match_tokens(item):
    value=" ".join(str(item.get(field) or "") for field in ("title","summary","snippet","mechanic","eligibility","terms_note"))
    value=unicodedata.normalize("NFKC",html_lib.unescape(value)).casefold().replace("ـ","")
    value=ARABIC_DIACRITICS.sub("",value)
    return {
        token for token in re.findall(r"[\w%]+",value,re.UNICODE)
        if len(token)>=2 and token not in _CAMPAIGN_MATCH_STOP and not token.isdigit()
    }


def _semantic_campaign_tags(item):
    text=clean(" ".join(str(item.get(field) or "") for field in (
        "title","summary","snippet","mechanic","eligibility","terms_note","evidence_snapshot",
    )),12000).casefold()
    tags=set(str(value).casefold() for value in (item.get("mechanic_tags") or []) if value)
    for tag,markers in MECHANICS.items():
        if any(marker.casefold() in text for marker in markers):tags.add(tag)
    patterns={
        "remittance":r"international\s+transfer|remittance|تحويل(?:ات)?\s+دولي|حوال(?:ة|ات)\s+دولي|الحوالات الدولية",
        "musaned":r"\bmusaned\b|مساند|عمالة منزلية|domestic worker",
        "sadad":r"\bsadad\b|سداد",
        "card":r"\bcard\b|\bcards\b|visa|mastercard|بطاقة|بطاقات|فيزا",
        "salary":r"\bsalary\b|\bpayroll\b|راتب|رواتب",
        "travel":r"\btravel\b|\btrip\b|سفر|سافر|رحلة",
        "bill_payment":r"\bbill(?:s)?\b|دفع الفواتير|فواتير",
        "wallet":r"\bwallet\b|محفظة",
        "referral":r"refer\s+(?:a\s+)?friend|referral|invite\s+friend|دعوة صديق|إحالة",
        "spend_reward":r"spend\s+more|get\s+more|every\s+riyal\s+spent|كل\s+ريال|أنفق|انفق",
    }
    for tag,pattern in patterns.items():
        if re.search(pattern,text,re.I):tags.add(tag)
    category=str(item.get("campaign_category") or item.get("primary_category") or "").casefold()
    if category and category!="merchant":tags.add(category)
    tags.update(f"corridor:{value.casefold()}" for value in (item.get("corridors") or corridors(text)))
    tags.update(_offer_match_values(text))
    return tags


def campaign_record_match(item,candidates,include_inactive=False):
    """Find one existing campaign using official URLs, mechanics, values, corridors and dates."""
    targets=[row for row in candidates if row.get("content_type")=="campaign" and (include_inactive or row.get("active") is not False)]
    if not targets:return None,None
    evidence=[item.get("official_evidence_url"),item.get("official_campaign_page_url"),item.get("primary_official_source_url")]
    evidence.extend(item.get("outbound_links") or [])
    evidence_ids={detail_url_identity(value) for value in evidence if value and not social_url(value)}
    exact=[]
    post_identity=social_identity(item.get("link")) if item.get("link") and social_url(item.get("link")) else ""
    for target in targets:
        target_urls={detail_url_identity(value) for value in (
            target.get("official_campaign_page_url"),target.get("primary_official_source_url"),target.get("link"),
        ) if value and not social_url(value)}
        social_ids={social_identity(value) for value in (target.get("social_links") or {}).values() if value}
        if (evidence_ids and evidence_ids&target_urls) or (post_identity and post_identity in social_ids):exact.append(target)
    if len(exact)==1:return exact[0]["id"],"campaign_exact_evidence"

    source_tokens=_campaign_match_tokens(item);source_tags=_semantic_campaign_tags(item)
    source_values={value for value in source_tags if value.startswith(("pct:","code:","prize_sar:"))}
    source_corridors={value for value in source_tags if value.startswith("corridor:")}
    source_mechanics=source_tags&_CONCRETE_MECHANIC_TAGS
    source_products=source_tags&_PRODUCT_TAGS
    scored=[]
    for target in targets:
        target_tokens=_campaign_match_tokens(target);target_tags=_semantic_campaign_tags(target)
        target_values={value for value in target_tags if value.startswith(("pct:","code:","prize_sar:"))}
        target_corridors={value for value in target_tags if value.startswith("corridor:")}
        target_mechanics=target_tags&_CONCRETE_MECHANIC_TAGS
        target_products=target_tags&_PRODUCT_TAGS
        source_title=campaign_title_key(item.get("title"));target_title=campaign_title_key(target.get("title"))
        exact_title=bool(source_title and source_title==target_title and not generic_campaign_title(item.get("title")))
        if source_values and not (source_values&target_values) and not exact_title:continue
        if source_corridors and target_corridors and not (source_corridors&target_corridors):continue
        compatible,date_bonus=_merchant_date_compatibility(item,target)
        if not compatible:continue
        overlap=source_tokens&target_tokens
        lexical=len(overlap)/(min(len(source_tokens),len(target_tokens)) or 1)
        shared_mechanics=source_mechanics&target_mechanics
        shared_products=source_products&target_products
        shared_values=source_values&target_values
        shared_corridors=source_corridors&target_corridors
        source_specific=source_products-{"card","travel","wallet"};target_specific=target_products-{"card","travel","wallet"}
        # Never infer a specialised campaign (Musaned, SADAD, remittance, salary, etc.)
        # from a generic card/cashback post that does not mention that product.
        if target_specific and not (source_specific&target_specific) and lexical<.55 and not exact_title:continue
        distinctive=(
            exact_title or lexical>=.55 or bool(shared_values or shared_corridors or source_specific&target_specific)
            or bool(shared_mechanics&{"spend_reward","referral"}) or len(shared_mechanics)>=2
        )
        if not distinctive:continue
        score=.82 if exact_title else min(.46,lexical*.56)
        if shared_mechanics:score+=.30+min(.08,.04*(len(shared_mechanics)-1))
        if shared_products:score+=.16
        if shared_values:score+=.22
        if shared_corridors:score+=.18
        if item.get("campaign_category") and item.get("campaign_category")==target.get("campaign_category"):score+=.08
        score+=date_bonus
        scored.append((score,target))
    if not scored:return None,None
    scored.sort(key=lambda row:(row[0],row[1].get("start_date") or "",row[1].get("id") or ""),reverse=True)
    best_score,best=scored[0];second_score=scored[1][0] if len(scored)>1 else 0.0
    if best_score>=.64 and (len(scored)==1 or best_score-second_score>=.12):return best["id"],"campaign_semantic_strong"
    if best_score>=.46:return best["id"],"campaign_semantic_suggested"
    return None,None


def social_promotion_type(item):
    """Return a safe potential record type, or None for ordinary non-promotional content."""
    text=clean(f"{item.get('title','')} {item.get('snippet','')}",12000).casefold()
    tags=_semantic_campaign_tags(item);values=_offer_match_values(text);mechanics=tags&_CONCRETE_MECHANIC_TAGS
    concrete=bool(mechanics or values or re.search(r"(?:\bpromo\s*code\b|كود\s+الخصم|رمز\s+الخصم)",text,re.I))
    if not concrete:return None
    merchant_tokens=set(_merchant_match_tokens(text)) | _item_url_tokens(item)
    explicit_partner=bool(
        item.get("campaign_category")=="merchant"
        or re.search(r"(?:discount\s+(?:at|with|from)|promo\s*code|خصم\s+(?:لدى|في|مع)|كود\s+الخصم|رمز\s+الخصم)",text,re.I)
        or (values and merchant_tokens and not (tags&{"remittance","musaned","sadad","salary"}))
    )
    return "merchant_offer" if explicit_partner and merchant_tokens else "campaign"


def _specific_official_identities(item,config):
    identities=set()
    for value in (item.get("official_campaign_page_url"),item.get("primary_official_source_url"),item.get("official_evidence_url"),item.get("link")):
        if not value or social_url(value) or generic_offers_url(value,config,item.get("competitor_id")):continue
        identity=detail_url_identity(value)
        if identity:identities.add(identity)
    return identities


def rescan_needs_review(data,config):
    """Reconcile every Needs Review row with all known records, then clear routine content.

    The scan never creates a counted campaign from social media. High-confidence matches link
    to an existing record; unmatched promotional posts remain Potential Campaign/Merchant Offer;
    ordinary non-promotional posts leave the review queue as Awareness.
    """
    rows=data.get("items",[]);before=sum(i.get("active") is not False and i.get("review_required") for i in rows)
    targets=[i for i in rows if i.get("content_type") in {"campaign","merchant_offer"} and i.get("source_type")!="social" and not i.get("deleted")]
    byid={i.get("id"):i for i in targets if i.get("id")}
    url_targets=defaultdict(list)
    for target in targets:
        for identity in _specific_official_identities(target,config):url_targets[(target.get("competitor_id"),identity)].append(target)
    summary={"review_before":before,"linked_social":0,"matched_website_duplicates":0,"awareness_cleared":0,"potential_campaigns":0,"potential_merchant_offers":0,"stale_reasons_cleared":0}

    for item in [row for row in rows if row.get("review_required")]:
        if item.get("review_approved") or item.get("review_decision") in {"confirm_campaign","confirm_merchant_offer","confirm_merchant_offers_bulk","group_campaign","link_existing"}:continue
        competitor=item.get("competitor_id");candidates=[target for target in targets if target.get("competitor_id")==competitor]
        if item.get("source_type")=="website":
            hint=verified_official_hint(item) or item.get("suggested_record_type")
            exact=[]
            for identity in _specific_official_identities(item,config):exact.extend(url_targets.get((competitor,identity),[]))
            exact=list({row.get("id"):row for row in exact if row.get("id")!=item.get("id")}.values())
            if hint in {"campaign","merchant_offer"}:
                typed=[row for row in exact if row.get("content_type")==hint]
                if typed:exact=typed
            target=sorted(exact,key=campaign_rank,reverse=True)[0] if exact else None
            if not target:
                if hint=="merchant_offer":
                    match,method=merchant_offer_match(item,candidates,include_inactive=True)
                    if method in {"merchant_offer_exact_evidence","merchant_name_value_date"}:target=byid.get(match)
                    elif match:item["suggested_campaign_id"]=match
                elif hint=="campaign":
                    match,method=campaign_record_match(item,candidates,include_inactive=True)
                    if method in {"campaign_exact_evidence","campaign_semantic_strong"}:target=byid.get(match)
                    elif match:item["suggested_campaign_id"]=match
            if target:
                item["duplicate_candidate_id"]=target["id"]
                item["review_reasons"]=["possible_duplicate_existing_record"]
                summary["matched_website_duplicates"]+=1
            continue

        if item.get("source_type")!="social":continue
        winner_post=is_winner_announcement(item)
        if not winner_post and item.get("post_role")=="winner_announcement" and item.get("post_role_source")!="manual":item.pop("post_role",None)
        if not winner_post and "winner_announcement_unlinked" in (item.get("review_reasons") or []):
            item["review_reasons"]=[reason for reason in item.get("review_reasons",[]) if reason!="winner_announcement_unlinked"]
            summary["stale_reasons_cleared"]+=1
        existing=byid.get(item.get("campaign_id"))
        if existing and existing.get("competitor_id")==competitor:
            _link_social_post(item,existing,item.get("match_method") or "full_review_existing_link");summary["linked_social"]+=1;continue
        merchant_match,merchant_method=merchant_offer_match(item,candidates,include_inactive=True)
        if merchant_method in {"merchant_offer_exact_evidence","merchant_name_value_date"} and merchant_match in byid:
            _link_social_post(item,byid[merchant_match],f"full_review_{merchant_method}");summary["linked_social"]+=1;continue
        campaign_match,campaign_method=campaign_record_match(item,candidates,include_inactive=True)
        if campaign_method in {"campaign_exact_evidence","campaign_semantic_strong"} and campaign_match in byid:
            _link_social_post(item,byid[campaign_match],f"full_review_{campaign_method}");summary["linked_social"]+=1;continue
        if merchant_match:item["suggested_campaign_id"]=merchant_match
        elif campaign_match:item["suggested_campaign_id"]=campaign_match
        potential=social_promotion_type(item)
        if not potential and not winner_post:
            remaining=[reason for reason in (item.get("review_reasons") or []) if reason not in _AUTO_SOCIAL_REVIEW_REASONS and reason!="winner_announcement_unlinked"]
            item["content_type"]="awareness";item["review_reasons"]=remaining;item["review_required"]=bool(remaining)
            item.pop("suggested_record_type",None);item.pop("suggested_campaign_id",None)
            if not remaining and item.get("current_status")=="Needs Review":item.pop("current_status",None)
            item["review_resolution_method"]="full_review_non_promotional"
            summary["awareness_cleared"]+=1
            continue
        potential=potential or "campaign"
        item["content_type"]="review";item["suggested_record_type"]=potential;item["review_required"]=True;item["current_status"]="Needs Review"
        keep=[reason for reason in (item.get("review_reasons") or []) if reason not in _AUTO_SOCIAL_REVIEW_REASONS]
        reason="potential_merchant_offer_unmatched" if potential=="merchant_offer" else "new_social_campaign_needs_review"
        item["review_reasons"]=list(dict.fromkeys(keep+[reason]))
        summary["potential_merchant_offers" if potential=="merchant_offer" else "potential_campaigns"]+=1
    summary["completed_at"]=iso(now())
    return summary

def openai_client(config=None):
    if not os.environ.get("OPENAI_API_KEY"): return None
    try:
        from openai import OpenAI
        ai=(config or {}).get("ai",{})
        return OpenAI(
            timeout=float(ai.get("request_timeout_seconds",45)),
            max_retries=int(ai.get("request_max_retries",0)),
        )
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
    client=openai_client(config)
    if not client:return {}
    model=config.get("ai",{}).get("classification_model","gpt-5.6-terra")
    relevant_competitors={p.get("competitor_id") for p in posts if p.get("competitor_id")}
    allowed_campaigns=[{"id":c["id"],"competitor_id":c.get("competitor_id"),"record_type":c.get("content_type"),"title":clean(c.get("title"),300),"category":c.get("campaign_category"),"mechanic":clean(c.get("mechanic"),600),"corridors":c.get("corridors",[]),"offer_values":c.get("offer_values",[]),"start_date":c.get("start_date"),"end_date":c.get("end_date")} for c in campaigns if c.get("active") is not False and c.get("competitor_id") in relevant_competitors]
    rows=[{"id":p["id"],"competitor_id":p.get("competitor_id"),"source_type":p.get("source_type"),"title":clean(p.get("title"),300),"text":clean(p.get("snippet"),1600),"platform":p.get("platform"),"published_at":p.get("published_at"),"start_date":p.get("start_date"),"end_date":p.get("end_date"),"official_url":p.get("official_campaign_page_url") or p.get("link")} for p in posts]
    categories=["remittance","musaned","sadad","card","engagement","merchant","other"]
    schema={"type":"object","additionalProperties":False,"properties":{"items":{"type":"array","items":{"type":"object","additionalProperties":False,"properties":{"id":{"type":"string"},"decision":{"type":"string","enum":["link","review","standalone"]},"record_type":{"type":"string","enum":["campaign","merchant_offer","social_post","awareness","review"]},"category":{"type":"string","enum":categories},"matched_campaign_id":{"type":["string","null"]},"confidence":{"type":"number","minimum":0,"maximum":1},"merchant_name":{"type":["string","null"]}},"required":["id","decision","record_type","category","matched_campaign_id","confidence","merchant_name"]}}},"required":["items"]}
    instructions="""Classify official competitor intelligence items for a Saudi fintech monitor. Respect source_type. For source_type=social, a post NEVER creates a counted campaign by itself: winner announcements, congratulations, reminders, result/follow-up posts should link to an existing same-competitor campaign when clearly supported, otherwise decision=review. A social post MAY be decision=standalone, record_type=merchant_offer only when it clearly names a retailer/restaurant/hotel/merchant and states a concrete benefit such as a discount, cashback, promo code or dated partner offer; use confidence>=0.90 only when this is explicit. Return the normalized merchant_name for Merchant Offers. When a social poster clearly names the same merchant as an existing merchant_offer and its discount, promo code or validity dates are compatible, decision=link to that merchant_offer; obvious Arabic/English transliterations are valid evidence. If the same merchant has multiple offers, require compatible benefit values, codes or dates. For source_type=website, a specific detail page discovered from the competitor's configured official offers page may be classified as campaign or merchant_offer. A merchant/partner discount at a named retailer, restaurant, hotel, clinic, store or partner using a card/promo code is merchant_offer and must NOT be a campaign KPI. A campaign is the competitor's own promotional mechanic such as remittance pricing/cashback/prizes, card-spend campaign, SADAD/Musaned promotion, or engagement competition. NEVER link across competitors. Link only when meaning, product/corridor and mechanic support the match. Product awareness without a concrete mechanic is awareness. If uncertain use decision=review. Return only the schema. Do not invent dates, values, merchants or campaigns."""
    try:
        r=client.responses.create(model=model,reasoning={"effort":config.get("ai",{}).get("classification_reasoning","low")},text={"format":{"type":"json_schema","name":"post_classification","schema":schema,"strict":True}},input=[{"role":"system","content":instructions},{"role":"user","content":json.dumps({"campaigns":allowed_campaigns,"posts":rows},ensure_ascii=False)}])
        result=json.loads(r.output_text); inp,out=usage_numbers(r); add_usage(state,"classification",model,inp,out,config); return {x["id"]:x for x in result.get("items",[])}
    except Exception as exc:
        print(f"[AI classification] {type(exc).__name__}: {exc}");return {}


def ai_classify_batched(posts,campaigns,state,config):
    """Classify a large review backlog in bounded cached API calls."""
    batch_size=max(1,min(50,int(config.get("ai",{}).get("classification_batch_size",40))))
    decisions={}
    for offset in range(0,len(posts),batch_size):
        decisions.update(ai_classify(posts[offset:offset+batch_size],campaigns,state,config))
    return decisions


def _social_merchant_group_key(post):
    if post.get("source_type")!="social" or post.get("campaign_id") or post.get("active") is False:
        return None
    if is_winner_announcement(post) or social_promotion_type(post)!="merchant_offer":
        return None
    published=dt(post.get("published_at"))
    title_key=campaign_title_key(post.get("title") or post.get("snippet"))
    if not published or len(title_key)<5:
        return None
    return post.get("competitor_id"),published.date().isoformat(),title_key


def _create_social_merchant_offer(data,posts,method,merchant_name=None):
    """Create one canonical Merchant Offer and attach its official social evidence."""
    posts=[post for post in posts if post.get("source_type")=="social" and post.get("link")]
    if not posts:return None
    posts.sort(key=lambda post:dt(post.get("published_at")) or datetime.max.replace(tzinfo=timezone.utc))
    first=posts[0];competitor=first.get("competitor_id")
    signature=campaign_title_key(first.get("title") or first.get("snippet"))
    offer_id=f"social-merchant:{competitor}:{hash_text(signature,first.get('published_at','')[:10])}"
    existing=next((row for row in data.get("items",[]) if row.get("id")==offer_id),None)
    if existing:
        for post in posts:_link_social_post(post,existing,method)
        return existing
    start=dt(first.get("published_at")) or now()
    ends=[dt(post.get("end_date")) for post in posts if dt(post.get("end_date"))]
    end=max(ends) if ends else None
    title=clean(first.get("title") or first.get("snippet") or merchant_name or "Merchant offer",300)
    links={}
    for post in posts:
        if post.get("platform") and post.get("link"):links.setdefault(post["platform"],post["link"])
    status,active=status_for({"start_date":iso(start),"end_date":iso(end)})
    offer={
        "id":offer_id,"competitor_id":competitor,"source_type":"official_social_group",
        "content_type":"merchant_offer","suggested_record_type":"merchant_offer",
        "campaign_category":"merchant","primary_category":"merchant","categories":["merchant"],
        "title":title,"merchant_name":clean(merchant_name,200) or None,"summary":clean(first.get("snippet") or first.get("title"),1600),
        "snippet":clean(first.get("snippet") or first.get("title"),1600),
        "link":first.get("link"),"primary_official_source_url":first.get("link"),
        "official_evidence_url":first.get("link"),"social_links":links,
        "start_date":iso(start),"end_date":iso(end),"start_date_basis":"first_verified_social_post",
        "start_date_evidence_type":"first_verified_social_post","start_date_estimated":True,
        "start_date_source_url":first.get("link"),"current_status":status,"active":active,
        "verified":True,"review_required":False,"review_reasons":[],
        "source_verification":{"status":"verified_social","verification_method":method,"source_url":first.get("link"),"checked_at":iso(now())},
        "classification_method":method,"offer_values":sorted(set().union(*(_offer_match_values(f"{post.get('title','')} {post.get('snippet','')}") for post in posts))),
        "mechanic_tags":sorted(set().union(*(_semantic_campaign_tags(post)&_CONCRETE_MECHANIC_TAGS for post in posts))),
        "corridors":sorted(set().union(*(set(post.get("corridors") or []) for post in posts))),
        "first_seen":iso(start),"last_seen":iso(max((dt(post.get("published_at")) or start for post in posts))),
        "last_changed":iso(start),"change_history":[{"at":iso(start),"type":"detected_from_official_social","version":1}],
    }
    data.setdefault("items",[]).append(offer)
    for post in posts:_link_social_post(post,offer,method)
    return offer


def promote_repeated_social_merchant_offers(data):
    """Collapse the same offer posted on multiple official platforms into one record."""
    groups=defaultdict(list)
    for post in data.get("items",[]):
        key=_social_merchant_group_key(post)
        if key:groups[key].append(post)
    created=[]
    for posts in groups.values():
        if len({post.get("platform") for post in posts if post.get("platform")})<2:continue
        offer=_create_social_merchant_offer(data,posts,"official_social_cross_platform_match")
        if offer and offer not in created:created.append(offer)
    return created

def enrich_social(data,state,config,overrides):
    items=data.get("items",[]); campaigns=[i for i in items if i.get("content_type") in {"campaign","merchant_offer"} and i.get("source_type")!="social"]; byid={i["id"]:i for i in campaigns}
    for post in [i for i in items if i.get("source_type")=="social"]:
        _extract_social_offer_dates(post)
        post["corridors"]=corridors(f"{post.get('title','')} {post.get('snippet','')}")
        patch=manual_patch(overrides,post["id"]); manual_link=patch.get("linked_campaign_id")
        if manual_link in byid:_link_social_post(post,byid[manual_link],"manual");continue
        if post.get("campaign_id") in byid:_link_social_post(post,byid[post["campaign_id"]],post.get("match_method") or "existing_link");continue
        cand=[c for c in campaigns if c.get("competitor_id")==post.get("competitor_id") and c.get("active") is not False]
        merchant_match,merchant_method=merchant_offer_match(post,cand)
        if merchant_method in {"merchant_offer_exact_evidence","merchant_name_value_date"}:
            _link_social_post(post,byid[merchant_match],merchant_method);continue
        if merchant_method=="merchant_offer_suggested":
            post["suggested_campaign_id"]=merchant_match;post["suggested_record_type"]="merchant_offer";post["review_required"]=True
            post["review_reasons"]=list(dict.fromkeys((post.get("review_reasons") or [])+["social_campaign_match_uncertain"]));continue
        if merchant_method=="merchant_offer_conflict":
            if merchant_match:post["suggested_campaign_id"]=merchant_match
            post["suggested_record_type"]="merchant_offer";post["review_required"]=True
            post["review_reasons"]=list(dict.fromkeys((post.get("review_reasons") or [])+["merchant_offer_match_conflict"]));continue
        match,method=heuristic_match(post,cand)
        if method in {"exact_url","exact_official_evidence","heuristic"}:_link_social_post(post,byid[match],method)
        elif method=="suggested":post["suggested_campaign_id"]=match;post["review_required"]=True;post["review_reasons"]=list(dict.fromkeys((post.get("review_reasons") or [])+["social_campaign_match_uncertain"]))
    repeated_offers=promote_repeated_social_merchant_offers(data)
    cleanup_stats={"cross_platform_merchant_offers_created":len(repeated_offers),"ai_social_items_processed":0,"ai_social_merchant_offers_created":0,"ai_website_items_processed":0}
    for offer in repeated_offers:
        if offer.get("id") not in byid:
            campaigns.append(offer);byid[offer["id"]]=offer
    cache=state.setdefault("ai_classification_cache",{}); maxn=int(config.get("ai",{}).get("classification_max_items_per_run",20)); recent=now()-timedelta(days=int(config.get("ai",{}).get("classification_recent_days",14))); ambiguous=[]
    for p in [i for i in items if i.get("source_type")=="social" and not i.get("campaign_id")]:
        d=dt(p.get("published_at")) or dt(p.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc)
        if d<recent:continue
        matching_targets=[c for c in campaigns if c.get("competitor_id")==p.get("competitor_id") and c.get("active") is not False]
        key=social_classification_content_key(p,matching_targets); cached=cache.get(p["id"],{})
        if cached.get("content_key")==key and cached.get("decision"):
            dec=dict(cached["decision"])
            cid=dec.get("campaign_id") or dec.get("matched_campaign_id")
            if cid in byid and byid[cid].get("competitor_id")!=p.get("competitor_id"):
                dec.pop("campaign_id",None);dec["matched_campaign_id"]=None;dec["content_type"]="review";dec["review_required"]=True
                dec["review_reasons"]=list(dict.fromkeys((dec.get("review_reasons") or [])+["invalid_cross_competitor_match"]))
            if dec.get("content_type") in {"campaign","merchant_offer"}:
                dec["suggested_record_type"]=dec.get("content_type");dec["content_type"]="review";dec["review_required"]=True
                dec["review_reasons"]=list(dict.fromkeys((dec.get("review_reasons") or [])+["social_post_cannot_create_campaign"]))
            p.update(dec)
            if cid in byid and dec.get("content_type")=="social_post":_link_social_post(p,byid[cid],dec.get("match_method") or "ai_cached")
            continue
        ambiguous.append(p)
    ambiguous.sort(key=lambda post:(
        bool(post.get("review_required")),post.get("suggested_record_type")=="merchant_offer",
        dt(post.get("published_at")) or dt(post.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc),
    ),reverse=True)
    decisions=ai_classify_batched(ambiguous[:maxn],campaigns,state,config)
    cleanup_stats["ai_social_items_processed"]=len(decisions)
    for p in ambiguous[:maxn]:
        d=decisions.get(p["id"])
        if not d:continue
        patch={"ai_classification":d,"campaign_category":d["category"],"primary_category":d["category"],"categories":[d["category"]]};match=d.get("matched_campaign_id")
        if match in byid and byid[match].get("competitor_id")!=p.get("competitor_id"):
            match=None; d={**d,"decision":"review","matched_campaign_id":None}; patch["ai_classification"]=d
        if d["decision"]=="link" and match in byid:
            # The campaign remains the authoritative record; the social item remains a post.
            patch.update(content_type="social_post",campaign_id=match,match_method="ai",review_required=False,review_reasons=[])
        elif d["decision"]=="standalone" and d["record_type"]=="merchant_offer" and float(d.get("confidence") or 0)>=.90 and social_promotion_type(p)=="merchant_offer":
            offer=_create_social_merchant_offer(data,[p],"ai_verified_official_social_merchant",d.get("merchant_name"))
            if offer:
                cleanup_stats["ai_social_merchant_offers_created"]+=1
                if offer.get("id") not in byid:campaigns.append(offer);byid[offer["id"]]=offer
                patch.update(content_type="social_post",campaign_id=offer["id"],match_method="ai_verified_official_social_merchant",review_required=False,review_reasons=[])
        elif d["record_type"] in {"campaign","merchant_offer"}:
            # Never promote a social post into a counted campaign automatically.
            patch.update(content_type="review",suggested_record_type=d["record_type"],review_required=True,review_reasons=list(dict.fromkeys((p.get("review_reasons") or [])+["social_post_cannot_create_campaign"])),suggested_campaign_id=match if match in byid else p.get("suggested_campaign_id"))
        elif d["decision"]=="review":
            patch.update(content_type="review",review_required=True,review_reasons=list(dict.fromkeys((p.get("review_reasons") or [])+["ai_needs_review"])),suggested_campaign_id=match if match in byid else p.get("suggested_campaign_id"))
        else:
            patch.update(content_type=d["record_type"] if d["record_type"] in {"awareness","social_post"} else "social_post",review_required=False)
        if is_winner_announcement(p) and not patch.get("campaign_id"):
            patch.update(content_type="review",review_required=True,review_reasons=list(dict.fromkeys((patch.get("review_reasons") or [])+["winner_announcement_unlinked"])))
        p.update(patch)
        if patch.get("campaign_id") in byid:_link_social_post(p,byid[patch["campaign_id"]],patch.get("match_method") or "ai")
        cache[p["id"]]={"content_key":social_classification_content_key(p,[c for c in campaigns if c.get("competitor_id")==p.get("competitor_id") and c.get("active") is not False]),"decision":patch,"at":iso(now())}
    # Apply the same hybrid classifier to newly discovered ambiguous website records.
    extra=[]
    for row in [i for i in items if i.get("source_type") in {"website"} and (i.get("review_required") or i.get("content_type")=="review")]:
        key=classification_content_key(row); cached=cache.get(row["id"],{})
        if cached.get("content_key")==key and cached.get("decision"):
            decision=dict(cached["decision"])
            # Never let a stale cached classification promote an unverified official discovery.
            listing_merchant=decision.get("content_type")=="merchant_offer" and trusted_barq_listing_merchant(row,config)
            if decision.get("content_type") in {"campaign","merchant_offer"} and (row.get("source_verification") or {}).get("status")!="verified_website" and not listing_merchant:
                decision["suggested_record_type"]=decision.get("content_type")
                decision["content_type"]="review"
                decision["review_required"]=True
                decision["review_reasons"]=list(dict.fromkeys((decision.get("review_reasons") or [])+["official_detail_not_verified"]))
            row.update(decision); continue
        extra.append(row)
    website_maxn=int(config.get("ai",{}).get("classification_website_max_items_per_run",0))
    extra_decisions=ai_classify_batched(extra[:website_maxn],campaigns,state,config) if website_maxn>0 else {}
    cleanup_stats["ai_website_items_processed"]=len(extra_decisions)
    for row in extra[:website_maxn]:
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
            # A verified, current detail page discovered directly from the configured official
            # offers index is strong enough to register automatically. Deduplication still runs
            # afterwards, so an existing Excel/master campaign remains authoritative.
            verified=(row.get("source_verification") or {}).get("status")=="verified_website" or trusted_barq_listing_merchant(row,config)
            if verified and row.get("official_discovery") and row.get("active") is not False and accepted_direct_source(row,config):
                patch.update(content_type="campaign",review_required=False,review_reasons=[])
            else:
                reason="expired_official_candidate" if row.get("active") is False else "new_official_campaign_needs_review"
                patch.update(content_type="review",suggested_record_type="campaign",review_required=True,review_reasons=[reason])
        else:
            # Merchant offers discovered from a website need the same detail-page verification
            # as campaigns before they become counted records.
            verified=(row.get("source_verification") or {}).get("status")=="verified_website"
            if d["record_type"]=="merchant_offer" and row.get("official_discovery") and not verified:
                patch.update(content_type="review",suggested_record_type="merchant_offer",review_required=True,review_reasons=["official_detail_not_verified"])
            else:
                patch.update(content_type=d["record_type"],review_required=False,review_reasons=[])
        row.update(patch); cache[row["id"]]={"content_key":classification_content_key(row),"decision":patch,"at":iso(now())}

    data["merchant_review_cleanup"]=cleanup_stats

    # Build campaign social analytics from BOTH approved/master direct links and RSS-linked posts.
    # A URL is counted once even if it appears in Excel and again in RSS with tracking parameters.
    linked=defaultdict(list)
    for p in [i for i in items if i.get("source_type")=="social" and i.get("campaign_id") in byid]:
        linked[p["campaign_id"]].append({k:p.get(k) for k in ["id","platform","title","link","published_at","media","match_method"]})

    current=now()
    platforms=["instagram","x","facebook","tiktok"]
    for c in campaigns:
        unique={}
        # Master/approved URLs are authoritative source links and count as known social posts.
        for platform,value in (c.get("social_links") or {}).items():
            values=value if isinstance(value,list) else [value]
            for url in values:
                if not specific_social_post_url(url):continue
                ident=social_identity(url)
                if not ident:continue
                unique[ident]={
                    "id":f"source:{c.get('id')}:{platform}:{hash_text(ident)}",
                    "platform":platform,
                    "title":f"Official {platform} post",
                    "link":url,
                    "published_at":None,
                    "media":None,
                    "match_method":"master_link",
                    "source_origin":"master",
                }

        # RSS posts enrich the same URL (date/title/media) or add additional unique posts.
        for p in linked.get(c["id"],[]):
            url=p.get("link");ident=social_identity(url)
            if not ident:continue
            if ident in unique:
                prior=unique[ident]
                unique[ident]={**prior,**{k:v for k,v in p.items() if v not in (None,"")},"source_origin":"master+rss"}
            else:
                unique[ident]={**p,"source_origin":"rss"}

        posts=list(unique.values())
        posts.sort(key=lambda p:(dt(p.get("published_at")) is not None,dt(p.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),p.get("platform") or ""))
        counts=Counter(p.get("platform") for p in posts if p.get("platform"))
        dated=[p for p in posts if dt(p.get("published_at"))]
        c["linked_posts"]=posts
        c["social_post_counts"]={p:int(counts.get(p,0)) for p in platforms}
        c["social_posts_total"]=len(posts)
        c["social_platform_count"]=sum(v>0 for v in c["social_post_counts"].values())
        c["social_first_post"]=min((p.get("published_at") for p in dated),key=lambda x:dt(x),default=None)
        c["social_latest_post"]=max((p.get("published_at") for p in dated),key=lambda x:dt(x),default=None)
        c["social_posts_7d"]=sum(dt(p.get("published_at"))>=current-timedelta(days=7) for p in dated)
        c["social_posts_30d"]=sum(dt(p.get("published_at"))>=current-timedelta(days=30) for p in dated)

        # Preserve the approved/master URL per platform; RSS only fills a missing platform.
        links=dict(c.get("social_links") or {})
        for p in posts:
            platform=p.get("platform");url=p.get("link")
            if platform and url and not links.get(platform):links[platform]=url
        c["social_links"]={k:v for k,v in links.items() if v}
        c["social_link_count"]=len({social_identity(u) for v in c["social_links"].values() for u in (v if isinstance(v,list) else [v]) if specific_social_post_url(u)})


def recompute_social_analytics(data):
    """Rebuild offer-level social analytics from the FINAL post-deduplication graph.

    Deduplication can merge approved social URLs into an authoritative campaign and can
    redirect social posts from a removed campaign id to the retained id. Any analytics
    calculated before that merge are stale, so this function is intentionally run after
    consolidate_duplicates(). Only direct post URLs count; generic social profile URLs do not.
    """
    items=data.get("items",[])
    campaigns=[i for i in items if i.get("content_type") in {"campaign","merchant_offer"} and i.get("source_type")!="social"]
    byid={i.get("id"):i for i in campaigns if i.get("id")}
    linked=defaultdict(list)
    for p in items:
        if p.get("source_type")!="social":continue
        cid=p.get("campaign_id")
        if cid not in byid:continue
        linked[cid].append({k:p.get(k) for k in ["id","platform","title","link","published_at","media","match_method"]})

    current=now();platforms=["instagram","x","facebook","tiktok"]
    for c in campaigns:
        unique={}
        # Approved/master links are authoritative only when they point to a specific post.
        for platform,value in (c.get("social_links") or {}).items():
            values=value if isinstance(value,list) else [value]
            for url in values:
                if not specific_social_post_url(url):continue
                ident=social_identity(url)
                if not ident:continue
                unique[ident]={
                    "id":f"source:{c.get('id')}:{platform}:{hash_text(ident)}",
                    "platform":platform,
                    "title":f"Official {platform} post",
                    "link":url,
                    "published_at":None,
                    "media":None,
                    "match_method":"master_link",
                    "source_origin":"master",
                }

        # Final RSS links are read after campaign-id redirects caused by deduplication.
        for post in linked.get(c.get("id"),[]):
            url=post.get("link")
            if not specific_social_post_url(url):continue
            ident=social_identity(url)
            if not ident:continue
            if ident in unique:
                prior=unique[ident]
                unique[ident]={**prior,**{k:v for k,v in post.items() if v not in (None,"")},"source_origin":"master+rss"}
            else:
                unique[ident]={**post,"source_origin":"rss"}

        posts=list(unique.values())
        posts.sort(key=lambda row:(dt(row.get("published_at")) is not None,dt(row.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),row.get("platform") or ""))
        counts=Counter(row.get("platform") for row in posts if row.get("platform"))
        dated=[row for row in posts if dt(row.get("published_at"))]
        c["linked_posts"]=posts
        c["social_post_counts"]={platform:int(counts.get(platform,0)) for platform in platforms}
        c["social_posts_total"]=len(posts)
        c["social_platform_count"]=sum(v>0 for v in c["social_post_counts"].values())
        c["social_first_post"]=min((row.get("published_at") for row in dated),key=lambda x:dt(x),default=None)
        c["social_latest_post"]=max((row.get("published_at") for row in dated),key=lambda x:dt(x),default=None)
        c["social_posts_7d"]=sum(dt(row.get("published_at"))>=current-timedelta(days=7) for row in dated)
        c["social_posts_30d"]=sum(dt(row.get("published_at"))>=current-timedelta(days=30) for row in dated)
        c["social_link_count"]=len({social_identity(url) for value in (c.get("social_links") or {}).values() for url in (value if isinstance(value,list) else [value]) if specific_social_post_url(url)})

    data["social_analytics_rebuilt_at"]=iso(current)
    return len(campaigns)

def ensure_campaign_start_dates(data):
    """Guarantee every approved campaign has a start date without fabricating a market launch.

    Priority: explicit official start date, earliest verified campaign publication/post, then
    first observed date as a clearly marked estimate. Suggested social links never qualify.
    """
    current=now();stats=Counter()
    for item in data.get("items",[]):
        if item.get("content_type")!="campaign" or item.get("review_required"):continue
        if dt(item.get("start_date")):
            item.setdefault("start_date_basis","official_start_date")
            item.setdefault("start_date_estimated",False)
            stats["official"]+=1
            continue

        evidence=[]
        published=dt(item.get("published_at"))
        if published:evidence.append((published,"record_publication",item.get("primary_official_source_url") or item.get("link")))
        social_first=dt(item.get("social_first_post"))
        if social_first:
            source_url=None
            for post in item.get("linked_posts") or []:
                if dt(post.get("published_at"))==social_first:
                    source_url=post.get("link");break
            evidence.append((social_first,"first_verified_social_post",source_url))

        if evidence:
            chosen,basis,source_url=min(evidence,key=lambda row:row[0])
            item["start_date"]=iso(chosen)
            item["start_date_basis"]="first_verified_social_post"
            item["start_date_estimated"]=True
            item["start_date_evidence_type"]=basis
            if source_url:item["start_date_source_url"]=source_url
            append_change(item,"start_date_inferred",{"basis":basis,"source":source_url})
            stats["verified_post"]+=1
            continue

        observed=dt(item.get("first_seen")) or dt(item.get("last_changed")) or current
        item["start_date"]=iso(observed)
        item["start_date_basis"]="first_observed"
        item["start_date_estimated"]=True
        item["start_date_evidence_type"]="first_observed"
        append_change(item,"start_date_estimated",{"basis":"first_observed"})
        stats["first_observed"]+=1

    remaining=sum(
        i.get("content_type")=="campaign" and not i.get("review_required") and not dt(i.get("start_date"))
        for i in data.get("items",[])
    )
    data["campaign_start_date_fill"]={
        "official":stats["official"],"from_verified_post":stats["verified_post"],
        "from_first_observed":stats["first_observed"],"remaining_missing":remaining,"at":iso(current),
    }
    return data["campaign_start_date_fill"]

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
    source_url=source.get("official_campaign_page_url") or source.get("primary_official_source_url")
    target_url=target.get("official_campaign_page_url") or target.get("primary_official_source_url")
    source_verified=(source.get("source_verification") or {}).get("status")=="verified_website"
    target_verified=(target.get("source_verification") or {}).get("status")=="verified_website"
    # A stale Needs Review row must never replace a proven canonical URL. Preserve it as
    # supporting evidence unless it is the first URL or carries stronger verification.
    if source_url and (not target_url or (source_verified and not target_verified)):
        if target_url and detail_url_identity(target_url)!=detail_url_identity(source_url):
            target["alternate_official_source_urls"]=list(dict.fromkeys((target.get("alternate_official_source_urls") or [])+[target_url]))
        target["official_campaign_page_url"]=source_url
        target["primary_official_source_url"]=source_url
        target["link"]=source_url
    elif source_url and detail_url_identity(source_url)!=detail_url_identity(target_url):
        target["alternate_official_source_urls"]=list(dict.fromkeys((target.get("alternate_official_source_urls") or [])+[source_url]))
    links=dict(target.get("social_links") or {}); links.update({k:v for k,v in (source.get("social_links") or {}).items() if v})
    target["social_links"]=links; target["social_link_count"]=len(links)
    for f in ["summary","snippet","start_date","end_date","published_at","mechanic","eligibility","terms_note","evidence_snapshot"]:
        if not target.get(f) and source.get(f): target[f]=source[f]
    # Never copy an arbitrary/social image while consolidating duplicate campaigns.
    # Only an image explicitly proven to come from an official campaign webpage may merge.
    sm=source.get("media") or {}
    if (
        not target.get("media")
        and sm.get("source_type")=="official_website"
        and sm.get("source_url")
        and not social_url(sm.get("source_url"))
    ):
        target["media"]=sm
    if source.get("last_live_verified_at"): target["last_live_verified_at"]=source["last_live_verified_at"]
    if (source.get("source_verification") or {}).get("verification_method")=="official_website_modal":
        target["source_verification"]=dict(source.get("source_verification") or {})
        target["source_locator"]=source.get("source_locator")
        target["source_detail_type"]="modal"
        target["verified"]=True

def sanitize_campaign_media(data):
    """Remove stale/unproven campaign hero images left by older builds.

    Social images remain on social-post records and linked_posts; a campaign/merchant
    hero is shown only when media provenance points to its official website detail page.
    """
    removed=0
    for item in data.get("items",[]):
        if item.get("content_type") not in {"campaign","merchant_offer"}:
            continue
        media=item.get("media") or {}
        if not media:
            continue
        source_url=media.get("source_url")
        official=item.get("official_campaign_page_url") or item.get("primary_official_source_url")
        valid=(
            media.get("source_type")=="official_website"
            and source_url
            and official
            and not social_url(source_url)
            and detail_url_identity(source_url)==detail_url_identity(official)
        )
        if not valid:
            item.pop("media",None)
            removed+=1
    data["media_sanitization"]={"removed":removed,"at":iso(now())}
    return removed

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
        if row.get("merged_into"):continue
        target_id=row.get("duplicate_candidate_id")
        target=byid.get(target_id)
        if (
            target and row.get("id")!=target_id
            and target.get("competitor_id")==row.get("competitor_id")
            and target.get("content_type") in {"campaign","merchant_offer"}
        ):
            merge_into_campaign(target,row);remove.add(row.get("id"));redirect[row.get("id")]=target_id

    campaigns=[i for i in items if i.get("id") not in remove and i.get("content_type") in {"campaign","merchant_offer"} and not i.get("merged_into")]
    campaigns.sort(key=campaign_rank,reverse=True)
    kept=[];by_title={};by_url={}
    for row in campaigns:
        comp=row.get("competitor_id") or "";record_type=row.get("content_type") or "campaign";title_key=campaign_title_key(row.get("title"))
        is_modal=(row.get("source_verification") or {}).get("verification_method")=="official_website_modal" or row.get("source_detail_type")=="modal"
        urls=set() if is_modal else {(social_identity(u) if social_url(u) else detail_url_identity(u)) for u in [row.get("official_campaign_page_url"),row.get("primary_official_source_url"),row.get("link")] if u};urls.discard("")
        target=None
        for u in urls:
            if (comp,record_type,u) in by_url:target=by_url[(comp,record_type,u)];break
        if target is None and title_key and not generic_campaign_title(row.get("title")):
            target=by_title.get((comp,record_type,title_key))
        if target is None and title_key and not generic_campaign_title(row.get("title")):
            scored=[(title_similarity(row.get("title"),c.get("title")),c) for c in kept if c.get("competitor_id")==comp and c.get("content_type")==record_type and c.get("campaign_category")==row.get("campaign_category")]
            if scored:
                score,cand=max(scored,key=lambda x:x[0])
                if score>=.94:target=cand
        if target is None:
            kept.append(row)
            if title_key and not generic_campaign_title(row.get("title")):by_title[(comp,record_type,title_key)]=row
            for u in urls:by_url[(comp,record_type,u)]=row
            continue
        merge_into_campaign(target,row);remove.add(row.get("id"));redirect[row.get("id")]=target.get("id")
        for f in ["summary","snippet","start_date","end_date","published_at","mechanic","eligibility","terms_note","operation_type"]:
            if not target.get(f) and row.get(f):target[f]=row[f]
        if title_key and not generic_campaign_title(row.get("title")):by_title[(comp,record_type,title_key)]=target
        for u in urls:by_url[(comp,record_type,u)]=target

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


def consolidate_review_duplicates(data,config):
    """Remove only exact official-URL duplicates that remain inside Needs Review.

    This intentionally avoids fuzzy title merging. Two genuine promotions can have similar
    wording, while a normalized official detail URL is safe enough to represent one record.
    """
    items=data.get("items",[]);groups=defaultdict(list)
    for item in items:
        if not item.get("review_required") or item.get("source_type")!="website":continue
        identities=_specific_official_identities(item,config)
        for identity in identities:groups[(item.get("competitor_id"),identity)].append(item)
    remove=set();redirect={}
    for rows in groups.values():
        remaining=[row for row in rows if row.get("id") not in remove]
        if len(remaining)<2:continue
        def review_rank(row):
            sv=row.get("source_verification") or {}
            return (
                sv.get("status")=="verified_website",
                bool(row.get("verified")),
                bool(row.get("end_date"))+bool(row.get("start_date")),
                len(clean(row.get("summary") or row.get("snippet"),5000)),
                dt(row.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc),
            )
        keeper=max(remaining,key=review_rank)
        for row in remaining:
            if row is keeper:continue
            merge_into_campaign(keeper,row)
            keeper["review_reasons"]=list(dict.fromkeys((keeper.get("review_reasons") or [])+(row.get("review_reasons") or [])))
            remove.add(row.get("id"));redirect[row.get("id")]=keeper.get("id")
    if remove:
        data["items"]=[item for item in items if item.get("id") not in remove]
        for item in data["items"]:
            for field in ("campaign_id","suggested_campaign_id","duplicate_candidate_id"):
                if item.get(field) in redirect:item[field]=redirect[item[field]]
    return len(remove)

def detect_duplicates_replacements(data):
    # Duplicate campaigns are consolidated before this point. Keep only replacement hints.
    items=[i for i in data.get("items",[]) if i.get("content_type")=="campaign" and not i.get("merged_into")]
    for i in items:i.pop("duplicate_candidate_id",None);i.pop("replacement_candidate_id",None)
    for idx,a in enumerate(items):
        at=tokenize(f"{a.get('title','')} {a.get('mechanic','')}")
        for b in items[idx+1:]:
            if a.get("competitor_id")!=b.get("competitor_id"):continue
            bt=tokenize(f"{b.get('title','')} {b.get('mechanic','')}");sim=len(at&bt)/(len(at|bt) or 1)
            if sim>=.60 and a.get("campaign_category")==b.get("campaign_category"):
                newer,older=(a,b) if (dt(a.get("start_date")) or datetime.min.replace(tzinfo=timezone.utc))>(dt(b.get("start_date")) or datetime.min.replace(tzinfo=timezone.utc)) else (b,a)
                if older.get("active") is False:newer["replacement_candidate_id"]=older["id"]

def stale_no_end_note(value):
    text=clean(value,1000).casefold()
    if not text:return False
    markers=("end date is not stated","end date not stated","no end date","تاريخ الانتهاء غير","تاريخ انتهاء غير","لم يتم ذكر تاريخ الانتهاء","لم يذكر تاريخ الانتهاء")
    return any(marker in text for marker in markers)


def finalize_counted_statuses(data, overrides, config):
    """Recalculate counted-record status after deduplication/merging.

    Deduplication can copy a newly discovered end date into an older inventory record.
    Therefore expiry must be recalculated *after* merges, otherwise an expired campaign can
    incorrectly remain active until the next run. Expiry is a hard rule and is not inferred.
    """
    current=now(); changed=0
    for item in data.get("items",[]):
        if item.get("content_type") not in {"campaign","merchant_offer"}:
            continue
        if item.get("merged_into"):
            item["active"]=False
            item["current_status"]="Merged"
            item["review_required"]=False
            continue
        listing_merchant=item.get("content_type")=="merchant_offer" and trusted_barq_listing_merchant(item,config)
        if item.get("source_type")=="website" and item.get("official_discovery") and not item.get("review_approved") and (item.get("source_verification") or {}).get("status")!="verified_website" and not listing_merchant:
            suggested=item.get("content_type")
            item["content_type"]="review"
            item["suggested_record_type"]=suggested
            item["review_required"]=True
            item["current_status"]="Needs Review"
            item["review_reasons"]=list(dict.fromkeys((item.get("review_reasons") or [])+["official_detail_not_verified"]))
            changed+=1
            continue
        status,active=status_for(item,current)
        if item.get("current_status")!=status:
            item["current_status"]=status; changed+=1
        # A known past end date always wins over stale active flags, including inventory rows.
        if item.get("active")!=active:
            item["active"]=active; changed+=1
        # If a manual/source update adds an End Date, remove legacy wording that still says
        # the campaign has no stated end date. The explicit End Date is authoritative.
        if item.get("end_date") and stale_no_end_note(item.get("terms_note")):
            item["terms_note"]=""; changed+=1
        if status=="Expired":
            item["review_required"]=False if not item.get("review_reasons") else item.get("review_required",False)
    data["final_status_normalization"]={"changed":changed,"at":iso(current)}
    return changed

def review_priority(item):
    n=0
    if item.get("review_required"):n+=20
    if item.get("suggested_record_type")=="merchant_offer":n+=12
    if item.get("campaign_category")=="remittance":n+=8
    if item.get("source_type") in {"website","manual"}:n+=5
    if item.get("source_verification",{}).get("source_changed"):n+=6
    if item.get("suggested_campaign_id"):n+=3
    return n

MANAGEMENT_WINDOW_DAYS=7
MANAGEMENT_EXPIRY_DAYS=7
MARKET_UPDATE_FIELDS=("mechanic","eligibility","terms_note","start_date","end_date","offer_values","corridors")
SNAPSHOT_FIELDS=(
    "competitor_id","title","campaign_category","mechanic","eligibility","terms_note",
    "start_date","end_date","offer_values","corridors","current_status","active",
    "market_launch_date","market_date_basis","market_last_changed","market_expiry_date",
)
COMPETITOR_LABELS={
    "stc-bank":"STC Bank","barq":"barq","mobily-pay":"Mobily Pay","tiqmo":"tiqmo",
    "urpay":"urpay","alinma-pay":"AlinmaPay",
}

def competitor_label(value):
    return COMPETITOR_LABELS.get(clean(value,100),clean(value,100).replace("-"," ").title())

def _snapshot_value(value):
    if isinstance(value,list):return sorted((_snapshot_value(v) for v in value),key=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True))
    if isinstance(value,dict):return {k:_snapshot_value(value[k]) for k in sorted(value)}
    return value

def campaign_market_date(item):
    """Return a source-side market date, never an Admin review or ingestion timestamp."""
    start=dt(item.get("start_date"));basis=item.get("start_date_basis")
    if start:
        if basis=="first_observed":return None,None
        if basis=="first_verified_social_post":
            event_basis="official_published_date" if item.get("start_date_evidence_type")=="record_publication" else "first_official_campaign_post"
            return iso(start),event_basis
        return iso(start),"official_start_date"
    return None,None

def annotate_market_timing(items):
    for item in items:
        if item.get("content_type")!="campaign":continue
        # An Admin merge is inventory maintenance, not a market launch, update or expiry.
        # Clear any inherited market-event dates so the Management Summary never reports
        # a human deduplication action as competitor activity.
        if item.get("merged_into"):
            for field in ("market_launch_date","market_date_basis","market_last_changed","market_expiry_date"):
                item.pop(field,None)
            continue
        value,basis=campaign_market_date(item)
        if value:
            item["market_launch_date"]=value;item["market_date_basis"]=basis
        else:
            item.pop("market_launch_date",None);item.pop("market_date_basis",None)
        source_changed=_latest_change_at(item,{"source_content_changed"})
        if source_changed:item["market_last_changed"]=iso(source_changed)
        end=dt(item.get("end_date"))
        if item.get("active") is False and end:item["market_expiry_date"]=iso(end)
        elif item.get("active") is not False:item.pop("market_expiry_date",None)

def snapshot_campaigns(items):
    return {
        i["id"]:{k:_snapshot_value(i.get(k)) for k in SNAPSHOT_FIELDS}
        for i in items if i.get("content_type")=="campaign" and i.get("id") and not i.get("merged_into")
    }

def _has_value(value):
    return value not in (None,"",[],{})

def _in_past_window(value,days,current=None):
    parsed=dt(value);current=current or now()
    return bool(parsed and current-timedelta(days=days)<=parsed<=current)

def _verified_campaign(item):
    status=(item.get("source_verification") or {}).get("status")
    return bool(item.get("verified") or item.get("review_approved") or status in {"verified_website","verified_social"})

def _latest_change_at(item,types,after=None):
    values=[]
    for row in item.get("change_history") or []:
        if row.get("type") not in types:continue
        stamp=dt(row.get("at"))
        if stamp and (not after or stamp>after):values.append(stamp)
    return max(values) if values else None

def material_delta(previous,current,items=None,previous_at=None):
    """Separate verified market events from Admin review and data-enrichment changes."""
    items_by_id={i.get("id"):i for i in (items or []) if i.get("id")}
    current_time=now();previous_time=dt(previous_at)
    added=[k for k in current if k not in previous];removed=[k for k in previous if k not in current];changed=[]
    inventory_adjustments=[];new_market_updates=[];new_market_expiries=[]
    for key in current.keys()&previous.keys():
        before=previous[key];after=current[key]
        # A code deployment can add fields to the snapshot schema. Missing legacy keys are not
        # inventory corrections and must not create a one-off management message for every record.
        fields=[field for field in SNAPSHOT_FIELDS if field in before and before.get(field)!=after.get(field)]
        if not fields:continue
        changed.append({"id":key,"fields":fields,"before":before,"after":after})
        item=items_by_id.get(key) or {}
        substantive=[field for field in fields if field in MARKET_UPDATE_FIELDS and _has_value(before.get(field)) and _has_value(after.get(field))]
        source_changed_at=_latest_change_at(item,{"source_content_changed"},previous_time)
        if substantive and source_changed_at and _verified_campaign(item):
            item["market_last_changed"]=iso(source_changed_at)
            item["market_last_change_fields"]=substantive
            new_market_updates.append({"id":key,"at":iso(source_changed_at),"fields":substantive})
        else:
            inventory_adjustments.append({"id":key,"fields":fields})

        end_date=dt(after.get("end_date"))
        if (
            before.get("active") is not False and after.get("active") is False
            and before.get("end_date")==after.get("end_date") and end_date
            and current_time-timedelta(days=MANAGEMENT_WINDOW_DAYS)<=end_date<=current_time
        ):
            item["market_expiry_date"]=iso(end_date)
            new_market_expiries.append({"id":key,"at":iso(end_date)})
        elif after.get("active") is not False and item.get("market_expiry_date"):
            item.pop("market_expiry_date",None)

    for key in added:
        item=items_by_id.get(key) or {}
        if not (_verified_campaign(item) and _in_past_window(item.get("market_launch_date"),MANAGEMENT_WINDOW_DAYS,current_time)):
            inventory_adjustments.append({"id":key,"fields":["record_added"]})
    inventory_adjustments.extend({"id":key,"fields":["record_removed"]} for key in removed)

    # Launches are based on the real campaign date, so a recent launch remains visible for the
    # whole management window while a late Admin approval of an old campaign never becomes new.
    market_launches=[]
    for key,item in items_by_id.items():
        if item.get("content_type")!="campaign" or item.get("active") is False or item.get("review_required"):continue
        if _verified_campaign(item) and _in_past_window(item.get("market_launch_date"),MANAGEMENT_WINDOW_DAYS,current_time):
            market_launches.append({"id":key,"at":item.get("market_launch_date"),"basis":item.get("market_date_basis")})
    market_updates=[];market_expiries=[]
    for key,item in items_by_id.items():
        if _in_past_window(item.get("market_last_changed"),MANAGEMENT_WINDOW_DAYS,current_time):
            market_updates.append({"id":key,"at":item.get("market_last_changed"),"fields":item.get("market_last_change_fields") or []})
        if _in_past_window(item.get("market_expiry_date"),MANAGEMENT_WINDOW_DAYS,current_time):
            market_expiries.append({"id":key,"at":item.get("market_expiry_date")})
    return {
        "added":added,"removed":removed,"changed":changed,"initial":not bool(previous),
        "market_launches":market_launches,"market_updates":market_updates,"market_expiries":market_expiries,
        "new_market_updates":new_market_updates,"new_market_expiries":new_market_expiries,
        "inventory_adjustments":inventory_adjustments,"inventory_adjustment_count":len(inventory_adjustments),
        "new_event_detected":bool(new_market_updates or new_market_expiries or any(row["id"] in added for row in market_launches)),
        "material":bool(market_launches or market_updates or market_expiries),
        "window_days":MANAGEMENT_WINDOW_DAYS,
    }

def _management_date(value):
    parsed=dt(value)
    return parsed.strftime("%d %b %Y") if parsed else "date unconfirmed"

def _event_rows(items,delta):
    byid={i.get("id"):i for i in items if i.get("id")}
    rows=[];seen=set()
    for kind,label in (("market_launches","launched"),("market_updates","material terms changed"),("market_expiries","expired")):
        for event in delta.get(kind,[]):
            item=byid.get(event.get("id")) or {};key=(event.get("id"),kind)
            if key in seen:continue
            seen.add(key);rows.append({
                "kind":kind,"label":label,"at":event.get("at"),"competitor":competitor_label(item.get("competitor_id")),
                "title":clean(item.get("title"),180) or "Untitled campaign","fields":event.get("fields") or [],"basis":event.get("basis"),
                "text":" ".join(clean(item.get(k),800) for k in ("title","summary","snippet","mechanic","terms_note")),
            })
    return sorted(rows,key=lambda row:dt(row.get("at")) or datetime.min.replace(tzinfo=timezone.utc),reverse=True)

def deterministic_summary(items,delta):
    campaigns=[i for i in items if i.get("content_type")=="campaign" and i.get("active") is not False and not i.get("review_required") and _verified_campaign(i)]
    counts=Counter(i.get("campaign_category") for i in campaigns);competitors={i.get("competitor_id") for i in campaigns if i.get("competitor_id")}
    total=len(campaigns);category_rank=counts.most_common();events=_event_rows(items,delta)
    executive=f"{total} verified active campaigns are tracked across {len(competitors)} competitors."
    if delta.get("inventory_adjustment_count") and not delta.get("initial"):
        executive+=" Inventory coverage was corrected after source verification; that administrative adjustment is excluded from recent market developments."

    developments=[]
    for row in events[:4]:
        if row["kind"]=="market_updates" and row["fields"]:
            fields=", ".join(str(v).replace("_"," ") for v in row["fields"][:3])
            developments.append(f"{row['competitor']} — {row['title']}: {fields} changed on the verified source ({_management_date(row['at'])}).")
        elif row["kind"]=="market_launches" and row.get("basis")=="first_official_campaign_post":
            developments.append(f"{row['competitor']} — {row['title']}: the first verified official campaign post was published on {_management_date(row['at'])}.")
        elif row["kind"]=="market_launches" and row.get("basis")=="official_published_date":
            developments.append(f"{row['competitor']} — {row['title']} was published on the verified official source on {_management_date(row['at'])}.")
        else:
            developments.append(f"{row['competitor']} — {row['title']} {row['label']} on {_management_date(row['at'])}.")
    if not developments:
        developments=[f"No verified market launch, material campaign change or confirmed expiry was identified in the last {MANAGEMENT_WINDOW_DAYS} days."]

    current_time=now();expiring=sorted(
        (i for i in campaigns if dt(i.get("end_date")) and current_time<dt(i.get("end_date"))<=current_time+timedelta(days=MANAGEMENT_EXPIRY_DAYS)),
        key=lambda i:dt(i.get("end_date")),
    )
    attention=[]
    if expiring:
        names=", ".join(f"{competitor_label(i.get('competitor_id'))} — {clean(i.get('title'),90)}" for i in expiring[:3])
        noun="campaign" if len(expiring)==1 else "campaigns"
        attention.append(f"{len(expiring)} {noun} are scheduled to expire within {MANAGEMENT_EXPIRY_DAYS} days: {names}{'…' if len(expiring)>3 else '.'}")
    pressure=[row for row in events if any(term in row["text"].casefold() for term in ("zero fee","0 fee","fee-free","no fee","cashback","صفر رسوم","بدون رسوم","استرداد نقدي"))]
    if pressure:
        attention.append(f"Recent verified activity includes a fee or cashback mechanic from {pressure[0]['competitor']}; assess potential pricing pressure before treating it as a broader market trend.")
    if not attention:attention=["No immediate verified launch, pricing signal or near-term campaign expiry requires escalation."]

    actions=[]
    launches=[row for row in events if row["kind"]=="market_launches"]
    updates=[row for row in events if row["kind"]=="market_updates"]
    if launches:actions.append(f"Benchmark the mechanic and eligibility of {launches[0]['competitor']} — {launches[0]['title']} against the current campaign plan.")
    if updates:actions.append(f"Review the commercial impact of the verified change to {updates[0]['competitor']} — {updates[0]['title']} before the next pricing or campaign decision.")
    if expiring:actions.append("Monitor the listed expiries for an extension or replacement campaign and refresh the response plan only when an official change is verified.")
    if not actions:actions=["No immediate management action is required; continue routine monitoring for verified market events."]

    if category_rank and total:
        top=category_rank[:2];top_total=sum(value for _,value in top);share=round(top_total*100/total)
        details=" and ".join(f"{CATEGORY_LABELS.get(category,category.title())} ({value})" for category,value in top)
        portfolio=f"{details} account for {share}% of the verified active campaign portfolio."
    else:portfolio="No verified active campaign portfolio is available for category analysis."
    return {
        "executive_view":executive,"key_developments":developments,"management_attention":attention,
        "recommended_actions":actions,"portfolio_insight":portfolio,"market_window_days":MANAGEMENT_WINDOW_DAYS,
        "generated_by":"management-rules-v2","generated_at":iso(now()),
    }

def _summary_contains_internal_ids(summary):
    if not summary:
        return False
    text=json.dumps(summary,ensure_ascii=False).lower()
    return any(token in text for token in ["detected:","campaign:","post:","merchant:","manual:"])

def ai_summary(items,delta,state,config):
    fallback=deterministic_summary(items,delta)
    # Most runs contain no newly verified market event. Returning the grounded rules summary here
    # avoids an unnecessary AI call and prevents generic prose from replacing factual management insight.
    if not delta.get("new_event_detected"):return fallback
    client=openai_client(config)
    if not client or not config.get("ai",{}).get("summary_enabled",True):return fallback
    model=config.get("ai",{}).get("summary_model","gpt-5.6-sol")
    schema={"type":"object","additionalProperties":False,"properties":{
        "executive_view":{"type":"string"},"key_developments":{"type":"array","items":{"type":"string"},"minItems":1,"maxItems":4},
        "management_attention":{"type":"array","items":{"type":"string"},"minItems":1,"maxItems":3},
        "recommended_actions":{"type":"array","items":{"type":"string"},"minItems":1,"maxItems":3},"portfolio_insight":{"type":"string"},
    },"required":["executive_view","key_developments","management_attention","recommended_actions","portfolio_insight"]}
    prompt="""Refine a grounded management summary for a Saudi fintech competitor monitor. Use only the supplied draft facts. Never add a market event, performance claim, causal claim, or recommendation unsupported by the draft. An Admin approval, reclassification, missing-date backfill, source-link correction, or historical record addition is not a market event. Merchant offers are excluded. Social activity is context only. Preserve exact campaign and competitor names, dates, counts and percentages. Keep the result concise, decision-oriented and suitable for senior management. Never expose internal IDs, hashes or technical workflow terminology."""
    try:
        r=client.responses.create(model=model,reasoning={"effort":config.get("ai",{}).get("summary_reasoning","xhigh")},text={"format":{"type":"json_schema","name":"management_summary","schema":schema,"strict":True}},input=[{"role":"system","content":prompt},{"role":"user","content":json.dumps(fallback,ensure_ascii=False)}])
        result=json.loads(r.output_text)
        # Final guardrail: never publish a management summary containing internal IDs.
        if _summary_contains_internal_ids(result):
            print("[AI summary] blocked output containing internal IDs; using rules fallback")
            return fallback
        result["market_window_days"]=MANAGEMENT_WINDOW_DAYS;result["generated_by"]=model;result["generated_at"]=iso(now());inp,out=usage_numbers(r);add_usage(state,"summary",model,inp,out,config);return result
    except Exception as exc:
        print(f"[AI summary] {type(exc).__name__}: {exc}");return fallback

def recompute_stats(data):
    items=data.get("items",[]);current=now();campaigns=[i for i in items if i.get("content_type")=="campaign" and i.get("active") is not False];merchants=[i for i in items if i.get("content_type")=="merchant_offer" and i.get("active") is not False];social7=[i for i in items if i.get("source_type")=="social" and i.get("active") is not False and (dt(i.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc))>=current-timedelta(days=7)];statuses=[s for s in data.get("source_status",[]) if s.get("source_type") in {"website","social"}]
    data["stats"]={"active_campaigns":len(campaigns),"merchant_offers":len(merchants),"remittance_campaigns":sum(i.get("campaign_category")=="remittance" for i in campaigns),"expiring_30d":sum("Expiring" in (i.get("current_status") or "") for i in campaigns),"social_posts_7d":len(social7),"review_required":sum(i.get("active") is not False and i.get("review_required") for i in items),"healthy_sources":sum(bool(s.get("success")) for s in statuses),"failed_sources":sum(not s.get("success") for s in statuses),"total_sources":len(statuses)}

def refresh_fingerprint(row):
    raw="\x1f".join(clean(part,5000) for part in (
        row.get("title"),row.get("summary") or row.get("snippet"),row.get("content_type"),
        row.get("campaign_category"),row.get("current_status"),row.get("active"),
        row.get("start_date"),row.get("end_date"),row.get("official_campaign_page_url") or row.get("link")
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

def finalize_refresh_metadata(data):
    """Refresh Admin-visible counts after classification, verification and deduplication."""
    summary=data.get("refresh_summary") or {}
    if not summary:return
    target=clean(summary.get("competitor") or "all")
    in_scope=lambda row: target in {"", "all", "*"} or row.get("competitor_id")==target
    scoped=[i for i in data.get("items",[]) if in_scope(i)]
    baseline=(data.pop("_refresh_baseline",{}) or {}).get("offers",{})
    current_offers={i.get("id"):i for i in scoped if i.get("id") and i.get("content_type") in {"campaign","merchant_offer","review"} and i.get("source_type")!="social"}
    if baseline:
        new_ids=set(current_offers)-set(baseline);common_ids=set(current_offers)&set(baseline)
        summary["new_offers"]=len(new_ids)
        summary["updated_offers"]=sum(refresh_fingerprint(current_offers[key])!=baseline[key] for key in common_ids)
        summary["unchanged_offers"]=sum(refresh_fingerprint(current_offers[key])==baseline[key] for key in common_ids)
    statuses=[s for s in data.get("source_status",[]) if in_scope(s) and s.get("source_type") in {"website","social"}]
    summary["needs_review"]=sum(i.get("active") is not False and i.get("review_required") for i in scoped)
    summary["failed_sources"]=sum(not s.get("success") for s in statuses)
    summary["zero_item_sources"]=sum(bool(s.get("success")) and int(s.get("item_count") or 0)==0 for s in statuses)
    summary["preserved_last_known_good"]=summary["failed_sources"]+summary["zero_item_sources"]
    summary["completed_at"]=iso(now())
    history=data.get("refresh_history") or []
    for row in reversed(history):
        if row.get("request_id")==summary.get("request_id"):
            row.update(summary);break
    data["data_safety"]={"zero_or_failed_sources_preserved":summary["preserved_last_known_good"],"policy":"last_known_good"}

def cli_args():
    parser=argparse.ArgumentParser()
    parser.add_argument("--competitor",default=os.environ.get("CM_COMPETITOR","all"),help="Competitor id for a scoped on-demand refresh, or 'all'.")
    return parser.parse_args()

def main():
    cli=cli_args();target=clean(cli.competitor or "all")
    data=load(DATA_PATH,{});state=load(STATE_PATH,{"schema_version":5,"items":{}});config=load(CONFIG_PATH,{});overrides=load(OVERRIDES_PATH,{"items":{},"new_items":[]})
    preference=overrides.get("site_preferences") or {}
    if preference.get("home_layout") in {"classic","intelligence-os"}:
        data["site_preferences"]={
            "home_layout":preference["home_layout"],
            "updated_at":preference.get("updated_at"),
            "updated_by":preference.get("updated_by"),
            "request_id":preference.get("request_id"),
        }
    else:
        data.setdefault("site_preferences",{"home_layout":"classic"})
    if not data.get("items"):print("No data items");return 0
    initial_review_count=sum(item.get("active") is not False and item.get("review_required") for item in data.get("items",[]))
    if target.casefold() not in {"", "all", "*"}:print(f"[TARGET] detail verification for {target}")
    print(f"[STAGE 1/5] Verify official detail pages · review queue={initial_review_count}",flush=True)
    repair_legacy_mobily_text(data)
    apply_manual_deletions(data,overrides)
    add_manual_new_items(data,overrides)
    verify_details(data,state,config,overrides,target)
    print("[STAGE 2/5] Classify and link official/social records",flush=True)
    apply_mobily_deterministic_classification(data)
    apply_verified_official_classification(data,config)
    enforce_record_integrity(data,config)
    enrich_social(data,state,config,overrides)
    apply_mobily_deterministic_classification(data)
    apply_verified_official_classification(data,config)

    print("[STAGE 3/5] Reconcile the full Needs Review backlog",flush=True)
    # Every run now reconciles the complete Needs Review backlog with all canonical
    # campaigns and merchant offers, instead of looking only at newly fetched rows.
    scan_summary=rescan_needs_review(data,config)
    normalize_winner_announcements(data)
    enforce_record_integrity(data,config)
    scan_summary["counted_duplicates_removed"]=consolidate_duplicates(data)
    scan_summary["review_duplicates_removed"]=consolidate_review_duplicates(data,config)

    apply_manual_deletions(data,overrides)
    apply_mobily_deterministic_classification(data)
    apply_verified_official_classification(data,config)
    finalize_counted_statuses(data,overrides,config)
    recompute_social_analytics(data)
    ensure_campaign_start_dates(data)
    sanitize_campaign_media(data)
    detect_duplicates_replacements(data)
    scan_summary["review_after"]=sum(item.get("active") is not False and item.get("review_required") for item in data.get("items",[]))
    # Stage 2 can legitimately surface previously unflagged social posts as Potential Campaigns
    # or Potential Merchant Offers. Measure the cleanup against the queue that the full scan
    # actually received, while retaining the workflow-entry count for an honest net comparison.
    scan_summary["workflow_review_before"]=initial_review_count
    scan_summary["cleaned"]=max(0,scan_summary["review_before"]-scan_summary["review_after"])
    scan_summary["workflow_net_change"]=scan_summary["review_after"]-initial_review_count
    data["full_review_scan"]=scan_summary
    print(f"[STAGE 4/5] Review reconciliation complete · {scan_summary['review_before']} → {scan_summary['review_after']} · workflow input={initial_review_count}",flush=True)
    for item in data.get("items",[]):
        item["review_priority"]=review_priority(item);item.pop("confidence",None) # confidence stays internal, never a displayed score
    annotate_market_timing(data["items"])
    snap=snapshot_campaigns(data["items"])
    delta=material_delta(state.get("summary_snapshot",{}),snap,data["items"],state.get("summary_snapshot_at"))
    # material_delta can persist a verified source-side update/expiry timestamp on the campaign.
    snap=snapshot_campaigns(data["items"])
    summary=ai_summary(data["items"],delta,state,config)
    snapshot_at=iso(now())
    state.update(summary_snapshot=snap,summary_snapshot_at=snapshot_at,ai_summary=summary,authoritative_delta=delta,schema_version=5,updated_at=snapshot_at)
    print("[STAGE 5/5] Save generated data",flush=True)
    data.update(schema_version=5,ai_summary=summary,authoritative_delta=delta,ai_usage=state.get("ai_usage",{}));recompute_stats(data);finalize_refresh_metadata(data)
    data["items"].sort(key=lambda i:(i.get("active") is not False,i.get("review_priority",0),dt(i.get("published_at")) or dt(i.get("last_changed")) or datetime.min.replace(tzinfo=timezone.utc)),reverse=True)
    save(DATA_PATH,data);save(STATE_PATH,state);print(f"Enhanced {len(data['items'])} items · review={data['stats']['review_required']} · AI calls total={data.get('ai_usage',{}).get('calls',0)}",flush=True);return 0

if __name__=="__main__": raise SystemExit(main())
