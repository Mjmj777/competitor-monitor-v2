"""Validate Admin grouping, linking and audit persistence in isolated temp files."""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import apply_review  # noqa: E402
import enhance  # noqa: E402


def encoded(payload):
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


with tempfile.TemporaryDirectory() as folder:
    temp = Path(folder)
    apply_review.DATA_PATH = temp / "data.json"
    apply_review.OVERRIDES_PATH = temp / "manual_overrides.json"
    data = {
        "items": [
            {"id": "post:barq:x:one", "competitor_id": "barq", "source_type": "social", "platform": "x", "content_type": "review", "campaign_category": "engagement", "title": "Campaign launch", "snippet": "Enter the draw", "link": "https://x.com/barq/status/1", "review_required": True},
            {"id": "post:barq:instagram:two", "competitor_id": "barq", "source_type": "social", "platform": "instagram", "content_type": "review", "campaign_category": "engagement", "title": "Campaign reminder", "snippet": "Last chance", "link": "https://instagram.com/p/ABC123", "review_required": True},
            {"id": "campaign:barq:existing", "competitor_id": "barq", "source_type": "inventory", "content_type": "campaign", "title": "Existing", "active": True},
            {"id": "detected:barq:official", "competitor_id": "barq", "source_type": "website", "official_discovery": True, "content_type": "review", "campaign_category": "other", "title": "Official campaign candidate", "link": "https://barq.com/ar/offers/official-campaign/", "review_required": True},
            {"id": "post:urpay:x:three", "competitor_id": "urpay", "source_type": "social", "platform": "x", "content_type": "review", "title": "Other competitor", "link": "https://x.com/urpay/status/3", "review_required": True},
        ]
    }
    apply_review.DATA_PATH.write_text(json.dumps(data), encoding="utf-8")
    apply_review.OVERRIDES_PATH.write_text(json.dumps({"schema_version": 2, "items": {}, "new_items": []}), encoding="utf-8")
    payload = {"action": "group_campaign", "item_ids": ["post:barq:x:one", "post:barq:instagram:two"], "record_type": "campaign", "title": "One grouped campaign", "campaign_category": "engagement", "official_source_url": "https://barq.com/ar/offers/example-offer/"}
    apply_review.apply(apply_review.decode_payload(encoded(payload)), "admin", "12345678-1234-1234-1234-123456789abc")
    overrides = json.loads(apply_review.OVERRIDES_PATH.read_text(encoding="utf-8"))
    assert len(overrides["new_items"]) == 1
    campaign_id = overrides["new_items"][0]["id"]
    assert overrides["new_items"][0]["evidence_ids"] == payload["item_ids"]
    assert overrides["items"][payload["item_ids"][0]]["campaign_id"] == campaign_id
    assert overrides["items"][payload["item_ids"][1]]["campaign_id"] == campaign_id
    assert len(overrides["review_history"]) == 1

    # review.yml rebuilds without network access. The explicit Admin decision must
    # remain a counted campaign while a later scheduled run verifies the URL.
    rebuilt = json.loads(apply_review.DATA_PATH.read_text(encoding="utf-8"))
    enhance.add_manual_new_items(rebuilt, overrides)
    os.environ["CM_SKIP_NETWORK"] = "1"
    try:
        enhance.verify_details(rebuilt, {}, config=json.loads((ROOT / "config.json").read_text(encoding="utf-8")), overrides=overrides)
    finally:
        os.environ.pop("CM_SKIP_NETWORK", None)
    canonical = next(row for row in rebuilt["items"] if row.get("id") == campaign_id)
    assert canonical["content_type"] == "campaign"
    assert canonical["review_required"] is False
    assert canonical["review_approved"] is True
    assert canonical["review_decision"] == "group_campaign"

    apply_review.apply({"action": "confirm_campaign", "item_ids": ["detected:barq:official"], "campaign_category": "engagement"}, "admin", "87654321-1234-1234-1234-123456789abc")
    confirmed_data = json.loads(apply_review.DATA_PATH.read_text(encoding="utf-8"))
    confirmed = next(row for row in confirmed_data["items"] if row.get("id") == "detected:barq:official")
    assert confirmed["content_type"] == "campaign"
    assert confirmed["review_required"] is False
    assert confirmed["review_approved"] is True
    assert confirmed["review_decision"] == "confirm_campaign"

    try:
        apply_review.apply({"action": "group_campaign", "item_ids": ["post:barq:x:one", "post:urpay:x:three"], "official_source_url": "https://x.com/barq/status/1"}, "admin", "cross-test")
        raise AssertionError("Cross-competitor grouping was accepted")
    except ValueError as exc:
        assert "one competitor" in str(exc)

    # Merge is reversible: the duplicate is archived, its evidence moves to the
    # primary campaign, and Undo restores the previous relationship.
    merge_data = json.loads(apply_review.DATA_PATH.read_text(encoding="utf-8"))
    merge_data["items"].extend([
        {"id": "campaign:alinma:primary", "competitor_id": "alinma-pay", "content_type": "campaign", "title": "Musaned", "active": True, "current_status": "Active", "social_links": {}},
        {"id": "campaign:alinma:duplicate", "competitor_id": "alinma-pay", "content_type": "campaign", "title": "Musaned campaign", "active": True, "current_status": "Active", "social_links": {"instagram": "https://instagram.com/p/MUSANED"}},
        {"id": "post:alinma:musaned", "competitor_id": "alinma-pay", "source_type": "social", "content_type": "social_post", "campaign_id": "campaign:alinma:duplicate", "linked_campaign_id": "campaign:alinma:duplicate", "link": "https://instagram.com/p/MUSANED"},
    ])
    apply_review.DATA_PATH.write_text(json.dumps(merge_data), encoding="utf-8")
    apply_review.apply({"action": "merge_campaigns", "item_ids": ["campaign:alinma:duplicate"], "target_campaign_id": "campaign:alinma:primary"}, "admin", "merge-request-123456")
    merged = json.loads(apply_review.DATA_PATH.read_text(encoding="utf-8"))
    merged_by_id = {row["id"]: row for row in merged["items"]}
    assert merged_by_id["campaign:alinma:duplicate"]["active"] is False
    assert merged_by_id["campaign:alinma:duplicate"]["current_status"] == "Merged"
    assert merged_by_id["campaign:alinma:duplicate"]["merged_into"] == "campaign:alinma:primary"
    assert merged_by_id["post:alinma:musaned"]["campaign_id"] == "campaign:alinma:primary"
    assert merged_by_id["post:alinma:musaned"]["merge_origin_campaign_id"] == "campaign:alinma:duplicate"
    apply_review.apply({"action": "undo_merge", "item_ids": ["campaign:alinma:duplicate"]}, "admin", "undo-request-123456")
    restored = json.loads(apply_review.DATA_PATH.read_text(encoding="utf-8"))
    restored_by_id = {row["id"]: row for row in restored["items"]}
    assert restored_by_id["campaign:alinma:duplicate"]["active"] is True
    assert restored_by_id["campaign:alinma:duplicate"]["merged_into"] is None
    assert restored_by_id["post:alinma:musaned"]["campaign_id"] == "campaign:alinma:duplicate"

    apply_review.apply({"action": "set_site_layout", "item_ids": ["site:home-layout"], "layout": "intelligence-os"}, "admin", "layout-request-123456")
    layout_data = json.loads(apply_review.DATA_PATH.read_text(encoding="utf-8"))
    layout_overrides = json.loads(apply_review.OVERRIDES_PATH.read_text(encoding="utf-8"))
    assert layout_data["site_preferences"]["home_layout"] == "intelligence-os"
    assert layout_overrides["site_preferences"]["home_layout"] == "intelligence-os"
    assert layout_overrides["review_history"][-1]["action"] == "set_site_layout"

print("Admin review persistence tests passed")
