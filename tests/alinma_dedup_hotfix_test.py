"""Regression coverage for Alinma Pay bilingual deduplication and saved Admin merges."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import enhance  # noqa: E402


def campaign(record_id, title, snippet, start, **values):
    row = {
        "id": record_id,
        "competitor_id": "alinma-pay",
        "source_type": "website",
        "content_type": "campaign",
        "campaign_category": "card",
        "title": title,
        "snippet": snippet,
        "summary": snippet,
        "start_date": start,
        "active": True,
        "verified": True,
        "review_required": False,
        "social_links": {},
        "source_verification": {"status": "verified_website"},
    }
    row.update(values)
    return row


assert enhance.social_identity("https://www.instagram.com/alinmapay/p/DbqaY05mm9E/") == enhance.social_identity("https://www.instagram.com/p/DbqaY05mm9E")

fee_official = campaign(
    "detected:alinma-pay:fees",
    "صفر رسوم على المشتريات الدولية",
    "صفر رسوم على عمليات الشراء الدولية ببطاقات الإنماء باي كاش باك.",
    "2026-06-24T00:00:00+00:00",
    campaign_category="card",
    end_date="2026-08-31T00:00:00+00:00",
    start_date_basis="official_start_date",
    official_campaign_page_url="https://www.alinmapay.com.sa/Offers/OIF-JUN2026",
    primary_official_source_url="https://www.alinmapay.com.sa/Offers/OIF-JUN2026",
    link="https://www.alinmapay.com.sa/Offers/OIF-JUN2026",
)
fee_social = campaign(
    "campaign:alinma-pay:fees-copy",
    "Zero International Transaction Fees on Cashback Cards",
    "Use Cashback Cards internationally with no foreign transaction fees and cashback.",
    "2026-08-06T00:00:00+00:00",
    source_type="inventory",
    source_verification={"status": "verified_social"},
    start_date_basis="first_observed",
    official_campaign_page_url="",
    primary_official_source_url="https://facebook.com/AlinmaPaySA/posts/fees/1619335260194305/",
    link="https://facebook.com/AlinmaPaySA/posts/fees/1619335260194305/",
    social_links={"facebook": "https://facebook.com/AlinmaPaySA/posts/fees/1619335260194305/"},
)
musaned_official = campaign(
    "detected:alinma-pay:musaned",
    "كاش باك 100% على رواتب عمالتك المنزلية",
    "حوّل راتب العمالة المنزلية عبر مساند وادخل السحب على كاش باك 100%.",
    "2026-07-28T00:00:00+00:00",
    campaign_category="musaned",
    end_date="2026-12-28T00:00:00+00:00",
    official_campaign_page_url="https://www.alinmapay.com.sa/Offers/Musaned-Cashback",
    primary_official_source_url="https://www.alinmapay.com.sa/Offers/Musaned-Cashback",
    link="https://www.alinmapay.com.sa/Offers/Musaned-Cashback",
    social_links={"instagram": "https://www.instagram.com/p/DbqaY05mm9E"},
)
musaned_social = campaign(
    "campaign:alinma-pay:musaned-copy",
    "Musaned Salary Transfer – 100% Cashback Draw",
    "Transfer a domestic worker salary through Musaned for 100% cashback.",
    "2026-08-05T00:00:00+00:00",
    campaign_category="musaned",
    source_type="inventory",
    source_verification={"status": "verified_social"},
    official_campaign_page_url="",
    primary_official_source_url="https://www.instagram.com/alinmapay/p/DbqaY05mm9E/",
    link="https://www.instagram.com/alinmapay/p/DbqaY05mm9E/",
    social_links={"instagram": "https://www.instagram.com/alinmapay/p/DbqaY05mm9E/"},
)

payload = {"items": [fee_official, fee_social, musaned_official, musaned_social]}
assert enhance.consolidate_duplicates(payload) == 2
kept = {row["id"]: row for row in payload["items"]}
assert set(kept) == {fee_official["id"], musaned_official["id"]}
assert kept[fee_official["id"]]["start_date"].startswith("2026-06-24")
assert kept[musaned_official["id"]]["end_date"].startswith("2026-12-28")

# A later campaign with the same mechanic is not a duplicate.
later = copy.deepcopy(fee_social)
later["id"] = "campaign:alinma-pay:fees-2027"
later["start_date"] = "2027-01-15T00:00:00+00:00"
later["link"] = later["primary_official_source_url"] = "https://facebook.com/AlinmaPaySA/posts/fees/999/"
later["social_links"] = {"facebook": "https://facebook.com/AlinmaPaySA/posts/fees/999/"}
separate = {"items": [copy.deepcopy(fee_official), later]}
assert enhance.consolidate_duplicates(separate) == 0

# Saved Admin merge fields survive a fresh inventory rebuild.
fresh = {"items": [
    {"id": "campaign:alinma:primary", "content_type": "campaign", "competitor_id": "alinma-pay", "active": True, "social_links": {"instagram": "https://instagram.com/p/ONE"}},
    {"id": "campaign:alinma:duplicate", "content_type": "campaign", "competitor_id": "alinma-pay", "active": True},
    {"id": "post:alinma:evidence", "content_type": "social_post", "competitor_id": "alinma-pay", "campaign_id": "campaign:alinma:duplicate"},
]}
overrides = {"items": {
    "campaign:alinma:primary": {"social_links": {"instagram": ["https://instagram.com/p/ONE", "https://instagram.com/p/TWO"]}},
    "campaign:alinma:duplicate": {"merged_into": "campaign:alinma:primary", "active": False, "current_status": "Merged"},
    "post:alinma:evidence": {"campaign_id": "campaign:alinma:primary", "linked_campaign_id": "campaign:alinma:primary", "merge_origin_campaign_id": "campaign:alinma:duplicate"},
}}
enhance.apply_persistent_item_overrides(fresh, overrides)
by_id = {row["id"]: row for row in fresh["items"]}
assert by_id["campaign:alinma:duplicate"]["merged_into"] == "campaign:alinma:primary"
assert by_id["campaign:alinma:duplicate"]["active"] is False
assert by_id["post:alinma:evidence"]["campaign_id"] == "campaign:alinma:primary"
assert len(by_id["campaign:alinma:primary"]["social_links"]["instagram"]) == 2

print("Alinma Pay deduplication and merge persistence tests passed")
