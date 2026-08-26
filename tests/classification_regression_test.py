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
assert stc["classification_method"] == "verified_official_rules_v4"

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

print("Source-aware classification regression tests passed")
