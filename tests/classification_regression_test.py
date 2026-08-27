"""Regression tests for source-aware official campaign classification."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import enhance  # noqa: E402

config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def official_item(**values):
    row = {
        "id": "detected:test",
        "competitor_id": "stc-bank",
        "source_type": "website",
        "official_discovery": True,
        "content_type": "review",
        "campaign_category": "remittance",
        "title": "Transfer internationally and enter the draw",
        "snippet": "Make an international transfer and enter the draw to win a car every week and cash prizes.",
        "evidence_snapshot": "The campaign runs from 19 August 2026 to 19 October 2026",
        "link": "https://stcbank.com.sa/en/web/guest/w/transfer-internationally-and-enter-the-draw",
        "official_campaign_page_url": "https://stcbank.com.sa/en/web/guest/w/transfer-internationally-and-enter-the-draw",
        "source_verification": {"status": "verified_website", "verification_method": "official_website_page", "source_url": "https://stcbank.com.sa/en/web/guest/w/transfer-internationally-and-enter-the-draw"},
        "start_date": "2026-08-19T00:00:00+00:00",
        "end_date": "2026-10-19T00:00:00+00:00",
        "active": True,
        "review_required": True,
        "review_reasons": ["ai_needs_review", "new_official_campaign_needs_review"],
    }
    row.update(values)
    return row


stc = official_item()
data = {"items": [stc]}
assert enhance.apply_verified_official_classification(data, config) == 1
assert stc["content_type"] == "campaign"
assert stc["review_required"] is False
assert stc["classification_method"] == "verified_official_rules_v5"

# The cache key must change when a page moves from unverified to verified.
unverified = official_item(source_verification={"status": "needs_review"})
verified = copy.deepcopy(unverified)
verified["source_verification"]["status"] = "verified_website"
assert enhance.classification_content_key(unverified) != enhance.classification_content_key(verified)

barq = official_item(
    id="detected:barq",
    competitor_id="barq",
    campaign_category="other",
    title="Restaurant partner offer",
    snippet="Get a discount 20% at the restaurant when paying with a barq Visa card.",
    evidence_snapshot="Partner discount valid at the restaurant.",
    link="https://barq.com/ar/offers/restaurant-offer/",
    official_campaign_page_url="https://barq.com/ar/offers/restaurant-offer/",
)
alinma = official_item(
    id="detected:alinma",
    competitor_id="alinma-pay",
    campaign_category="musaned",
    title="Musaned Salary Cashback",
    snippet="Transfer domestic worker salary and enter the monthly draw for 100% cashback.",
    evidence_snapshot="The campaign is a monthly Musaned salary draw.",
    link="https://alinmapay.com.sa/Offers/Musaned-Cashback",
    official_campaign_page_url="https://alinmapay.com.sa/Offers/Musaned-Cashback",
)
ambiguous = official_item(
    id="detected:ambiguous",
    competitor_id="urpay",
    campaign_category="other",
    title="Learn more about urpay",
    snippet="Discover our services.",
    evidence_snapshot="General product information.",
    link="https://www.urpay.com.sa/en/services/example",
    official_campaign_page_url="https://www.urpay.com.sa/en/services/example",
)
payload = {"items": [barq, alinma, ambiguous]}
enhance.apply_verified_official_classification(payload, config)
assert barq["content_type"] == "merchant_offer"
assert alinma["content_type"] == "campaign"
assert ambiguous["content_type"] == "review"


def merchant_offer(**values):
    row = {
        "id": "detected:alinma-pay:iherb",
        "competitor_id": "alinma-pay",
        "source_type": "website",
        "official_discovery": True,
        "content_type": "merchant_offer",
        "campaign_category": "merchant",
        "title": "عرض آيهيرب 40%",
        "summary": "استمتع بخصم 40% على مشترياتك من آيهيرب. يسري العرض من 21 أغسطس 2026 حتى 4 سبتمبر 2026.",
        "link": "https://www.alinmapay.com.sa/Offers/iHerb_Aug_2026",
        "official_campaign_page_url": "https://www.alinmapay.com.sa/Offers/iHerb_Aug_2026",
        "source_verification": {"status": "verified_website", "verification_method": "official_website_page"},
        "verified": True,
        "start_date": "2026-08-21T00:00:00+00:00",
        "end_date": "2026-09-04T00:00:00+00:00",
        "active": True,
        "review_required": False,
        "review_reasons": [],
        "social_links": {},
    }
    row.update(values)
    return row


def social_post(post_id, title, **values):
    row = {
        "id": post_id,
        "competitor_id": "alinma-pay",
        "source_type": "social",
        "platform": "instagram",
        "content_type": "social_post",
        "campaign_category": "merchant",
        "title": title,
        "snippet": title,
        "link": f"https://www.instagram.com/p/{post_id.rsplit(':', 1)[-1]}/",
        "published_at": "2026-08-24T12:20:00+00:00",
        "active": True,
        "review_required": True,
        "review_reasons": ["social_campaign_match_uncertain"],
    }
    row.update(values)
    return row


social_config = copy.deepcopy(config)
social_config.setdefault("ai", {})["classification_enabled"] = False
iherb = merchant_offer()
iherb_instagram = social_post("post:alinma-pay:instagram:iherb", "ناوي تطلب من آيهيرب؟ استفد من خصم 40% ببطاقات الإنماء باي")
iherb_x = social_post("post:alinma-pay:x:iherb", "اطلب من آيهيرب واستفد من خصم 40%", platform="x", link="https://x.com/alinmapay/status/100")
wrong_value = social_post("post:alinma-pay:x:iherb-wrong", "عرض آيهيرب بخصم 20%", platform="x", link="https://x.com/alinmapay/status/101")
wrong_date = social_post("post:alinma-pay:x:iherb-date", "عرض آيهيرب بخصم 40%. العرض ساري حتى 5 سبتمبر 2026.", platform="x", link="https://x.com/alinmapay/status/102")
merchant_payload = {"items": [iherb, iherb_instagram, iherb_x, wrong_value, wrong_date]}
enhance.enrich_social(merchant_payload, {}, social_config, {"items": {}})
for linked in (iherb_instagram, iherb_x):
    assert linked["campaign_id"] == iherb["id"]
    assert linked["content_type"] == "social_post"
    assert linked["review_required"] is False
    assert linked["match_method"] == "merchant_name_value_date"
assert iherb["social_posts_total"] == 2
assert wrong_value.get("campaign_id") is None
assert wrong_value["review_required"] is True
assert "merchant_offer_match_conflict" in wrong_value["review_reasons"]
assert wrong_date.get("campaign_id") is None
assert wrong_date["review_required"] is True
assert "merchant_offer_match_conflict" in wrong_date["review_reasons"]

# An explicit end date printed on the official social poster fills a missing website date.
aliexpress = merchant_offer(
    id="detected:tiqmo:aliexpress",
    competitor_id="tiqmo",
    title="AliExpress offer",
    summary="Back-to-school savings with the tiqmo Platinum card.",
    link="https://tiqmo.com/en/offers/aliexpress",
    official_campaign_page_url="https://tiqmo.com/en/offers/aliexpress",
    start_date=None,
    end_date=None,
)
aliexpress_post = social_post(
    "post:tiqmo:instagram:aliexpress",
    "Get SAR 65 off at AliExpress. Offer valid until 31 August 2026.",
    competitor_id="tiqmo",
    link="https://www.instagram.com/p/ALIEXPRESS/",
    published_at="2026-08-21T18:00:00+00:00",
)
date_payload = {"items": [aliexpress, aliexpress_post]}
enhance.enrich_social(date_payload, {}, social_config, {"items": {}})
assert aliexpress_post["campaign_id"] == aliexpress["id"]
assert aliexpress_post["review_required"] is False
assert aliexpress["end_date"].startswith("2026-08-31")
assert aliexpress["date_extraction_method"] == "linked_official_social_post"

print("Source-aware classification regression tests passed")
