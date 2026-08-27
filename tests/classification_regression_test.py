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

# Winner mechanics stay eligible for campaign matching; only actual result announcements
# are quarantined as winner posts.
assert not enhance.is_winner_announcement({"title": "Spend SAR 100 and enter to win — one winner every week"})
assert not enhance.is_winner_announcement({"title": "Spend SAR 100 and enter to win — one winner every week", "post_role": "winner_announcement"})
assert enhance.is_winner_announcement({"title": "Congratulations to our winner, who received the prize"})

# Full review reconciliation scans the existing backlog, links safe matches, clears ordinary
# awareness posts and leaves genuinely new promotions as Potential Campaign/Merchant Offer.
canonical_campaign = official_item(
    id="campaign:stc-bank:zero-fee-india",
    content_type="campaign",
    title="Zero-fee international transfers to India",
    snippet="Transfer internationally to India with zero fees through STC Bank.",
    evidence_snapshot="Valid from 19 August 2026 to 19 October 2026.",
    review_required=False,
    review_reasons=[],
    verified=True,
)
campaign_post = social_post(
    "post:stc-bank:instagram:zero-fee-india",
    "Transfer internationally to India with zero fees until 19 October 2026",
    competitor_id="stc-bank",
    campaign_category="remittance",
)
awareness_post = social_post(
    "post:stc-bank:x:security",
    "Protect your account and never share your password",
    competitor_id="stc-bank",
    campaign_category="other",
    platform="x",
    link="https://x.com/stcbank/status/900",
)
potential_merchant = social_post(
    "post:stc-bank:instagram:blue-cafe",
    "Get 25% discount at Blue Cafe with your card",
    competitor_id="stc-bank",
    campaign_category="merchant",
)
website_duplicate = official_item(
    id="detected:stc-bank:zero-fee-india-copy",
    title="صفر رسوم على التحويل الدولي إلى الهند",
    snippet="حوّل دوليًا إلى الهند بدون رسوم.",
    link=canonical_campaign["official_campaign_page_url"],
    official_campaign_page_url=canonical_campaign["official_campaign_page_url"],
)
manual_review = social_post(
    "post:stc-bank:x:manual",
    "A manually approved review decision",
    competitor_id="stc-bank",
    platform="x",
    link="https://x.com/stcbank/status/901",
    review_approved=True,
)
review_payload = {"items": [canonical_campaign, campaign_post, awareness_post, potential_merchant, website_duplicate, manual_review]}
scan = enhance.rescan_needs_review(review_payload, config)
assert scan["linked_social"] == 1
assert campaign_post["campaign_id"] == canonical_campaign["id"]
assert campaign_post["review_required"] is False
assert awareness_post["content_type"] == "awareness" and awareness_post["review_required"] is False
assert potential_merchant["suggested_record_type"] == "merchant_offer" and potential_merchant["review_required"] is True
assert website_duplicate["duplicate_candidate_id"] == canonical_campaign["id"]
assert manual_review["review_required"] is True
assert enhance.consolidate_duplicates(review_payload) == 1
assert website_duplicate["id"] not in {row["id"] for row in review_payload["items"]}

# A lower-confidence review URL is retained as alternate evidence and never replaces the
# canonical verified website URL during deduplication.
canonical_url = "https://stcbank.com.sa/en/w/canonical-offer"
target = official_item(id="campaign:canonical", content_type="campaign", official_campaign_page_url=canonical_url, primary_official_source_url=canonical_url, link=canonical_url, review_required=False, verified=True)
source = official_item(id="detected:copy", official_campaign_page_url="https://stcbank.com.sa/en/w/unverified-copy", primary_official_source_url="https://stcbank.com.sa/en/w/unverified-copy", link="https://stcbank.com.sa/en/w/unverified-copy", source_verification={"status": "needs_review"})
enhance.merge_into_campaign(target, source)
assert target["official_campaign_page_url"] == canonical_url
assert source["official_campaign_page_url"] in target["alternate_official_source_urls"]

# Generic card mechanics are not enough to link a different promotion. Prize amounts and
# specialised products must agree before the full scan auto-links them.
zero_fee_card = official_item(
    id="campaign:tiqmo:zero-fees",
    competitor_id="tiqmo",
    content_type="campaign",
    campaign_category="card",
    title="Zero International Card Transaction Fees",
    snippet="Use the Platinum card with 0% international transaction fees.",
    review_required=False,
    review_reasons=[],
    verified=True,
)
new_spend_campaign = social_post(
    "post:tiqmo:facebook:new-spend",
    "Spend More, Win More! Every riyal spent gets you closer to win SAR 100,000",
    competitor_id="tiqmo",
    campaign_category="card",
    platform="facebook",
)
assert enhance.campaign_record_match(new_spend_campaign, [zero_fee_card], include_inactive=True) == (None, None)

musaned_campaign = official_item(
    id="campaign:alinma-pay:musaned",
    competitor_id="alinma-pay",
    content_type="campaign",
    campaign_category="musaned",
    title="Musaned Salary Transfer – 100% Cashback Draw",
    snippet="Transfer a domestic worker salary through Musaned for a chance at 100% cashback.",
    review_required=False,
    review_reasons=[],
    verified=True,
)
generic_card_cashback = social_post(
    "post:alinma-pay:tiktok:new-customer",
    "New customers get 100% cashback when shopping online with the card",
    competitor_id="alinma-pay",
    campaign_category="card",
    platform="tiktok",
)
assert enhance.campaign_record_match(generic_card_cashback, [musaned_campaign], include_inactive=True) == (None, None)

print("Source-aware classification regression tests passed")
