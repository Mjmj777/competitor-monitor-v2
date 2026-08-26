"""Apply an authenticated Admin review decision to persistent project data.

The browser never writes GitHub contents directly.  Cloudflare dispatches review.yml with
one base64url payload; this script validates that payload, updates manual_overrides.json as
the durable source of truth, and mirrors the decision into data.json for immediate display.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

BASE = Path(__file__).resolve().parent
DATA_PATH = BASE / "data.json"
OVERRIDES_PATH = BASE / "manual_overrides.json"
ALLOWED_ACTIONS = {
    "confirm_campaign", "confirm_merchant_offer", "confirm_merchant_offers_bulk", "group_campaign",
    "link_existing", "mark_not_campaign", "mark_awareness",
}
ALLOWED_CATEGORIES = {"remittance", "musaned", "sadad", "card", "engagement", "other", "merchant"}
MAX_REVIEW_ITEMS = 50
MAX_SEPARATE_MERCHANT_ITEMS = 200


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save(path: Path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def clean(value, limit=500):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def decode_payload(value: str):
    raw = clean(value, 200_000)
    raw += "=" * (-len(raw) % 4)
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("ascii")).decode("utf-8")
        payload = json.loads(decoded)
    except Exception as exc:
        raise ValueError(f"Invalid review payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Review payload must be an object")
    return payload


def valid_http_url(value):
    if not value:
        return None
    text = clean(value, 1800)
    parts = urlsplit(text)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("Official source must be an http(s) URL")
    return text


def patch_for(item, action, campaign_id, reviewer, reviewed_at, request_id):
    patch = {
        "review_required": False,
        "review_reasons": [],
        "review_decision": action,
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at,
        "review_request_id": request_id,
    }
    if campaign_id:
        patch.update({
            "campaign_id": campaign_id,
            "linked_campaign_id": campaign_id,
            "record_role": "campaign_evidence",
            "content_type": "social_post" if item.get("source_type") == "social" else "awareness",
            "current_status": "Linked",
        })
    return patch


def choose_source(items, supplied=None):
    if supplied:
        return valid_http_url(supplied)
    for item in items:
        for field in ("official_evidence_url", "official_campaign_page_url", "primary_official_source_url", "link"):
            value = valid_http_url(item.get(field)) if item.get(field) else None
            if value:
                return value
    return None


def create_canonical(payload, items, request_id, reviewer, reviewed_at, record_type, action):
    competitor_id = items[0]["competitor_id"]
    category = clean(payload.get("campaign_category") or items[0].get("campaign_category") or "other", 40)
    if record_type == "merchant_offer":
        category = "merchant"
    if category not in ALLOWED_CATEGORIES:
        raise ValueError("Unknown campaign category")
    source = choose_source(items, payload.get("official_source_url"))
    if not source:
        raise ValueError("A specific official source URL is required")
    suffix = re.sub(r"[^0-9a-z-]", "", request_id.casefold())[:40] or str(int(datetime.now().timestamp()))
    campaign_id = f"manual:review:{competitor_id}:{suffix}"
    social_links = {}
    for item in items:
        if item.get("source_type") == "social" and item.get("platform") and item.get("link"):
            platform = item["platform"]
            existing = social_links.get(platform)
            if not existing:
                social_links[platform] = item["link"]
            elif isinstance(existing, list):
                if item["link"] not in existing:
                    existing.append(item["link"])
            elif existing != item["link"]:
                social_links[platform] = [existing, item["link"]]
    return {
        "id": campaign_id,
        "competitor_id": competitor_id,
        "content_type": record_type,
        "campaign_category": category,
        "title": clean(payload.get("title") or items[0].get("title") or "Admin-approved campaign", 280),
        "summary": clean(payload.get("summary") or items[0].get("snippet") or items[0].get("summary"), 3000),
        "official_campaign_page_url": source,
        "primary_official_source_url": source,
        "link": source,
        "social_links": social_links,
        "start_date": clean(payload.get("start_date"), 40) or None,
        "end_date": clean(payload.get("end_date"), 40) or None,
        "active": True,
        "review_approved": True,
        "review_decision": action,
        "review_required": False,
        "reviewed_by": reviewer,
        "reviewed_at": reviewed_at,
        "review_request_id": request_id,
        "evidence_ids": [item["id"] for item in items],
        "created_at": reviewed_at,
    }


def apply(payload, reviewer, request_id):
    action = clean(payload.get("action"), 60)
    if action not in ALLOWED_ACTIONS:
        raise ValueError("Unknown review action")
    raw_ids = payload.get("item_ids")
    if not isinstance(raw_ids, list):
        raise ValueError("item_ids must be an array")
    item_ids = list(dict.fromkeys(clean(value, 220) for value in raw_ids if clean(value, 220)))
    item_limit = MAX_SEPARATE_MERCHANT_ITEMS if action == "confirm_merchant_offers_bulk" else MAX_REVIEW_ITEMS
    if not 1 <= len(item_ids) <= item_limit:
        raise ValueError(f"Select between 1 and {item_limit} review items")

    data = load(DATA_PATH, {"items": []})
    overrides = load(OVERRIDES_PATH, {"schema_version": 3, "items": {}, "new_items": [], "review_history": []})
    by_id = {item.get("id"): item for item in data.get("items", []) if item.get("id")}
    missing = [item_id for item_id in item_ids if item_id not in by_id]
    if missing:
        raise ValueError(f"Unknown item ids: {', '.join(missing[:3])}")
    items = [by_id[item_id] for item_id in item_ids]
    competitors = {item.get("competitor_id") for item in items}
    if None in competitors:
        raise ValueError("Every review item must belong to a competitor")
    grouped_actions = {"link_existing", "group_campaign", "confirm_campaign", "confirm_merchant_offer"}
    if action in grouped_actions and len(competitors) != 1:
        raise ValueError("Grouped review items must belong to one competitor")

    reviewed_at = datetime.now(timezone.utc).isoformat()
    reviewer = clean(reviewer, 100) or "admin"
    request_id = clean(request_id, 120)
    campaign_id = None
    new_record = None
    approved_record_ids = []

    if action == "confirm_merchant_offers_bulk":
        ineligible = [
            item.get("id") for item in items
            if item.get("source_type") != "website" or not item.get("official_discovery")
        ]
        if ineligible:
            raise ValueError(
                "Separate Merchant Offer approval only accepts official website discoveries; "
                f"invalid items: {', '.join(ineligible[:3])}"
            )
        for item in items:
            if not choose_source([item]):
                raise ValueError(f"Merchant Offer {item['id']} is missing a specific official source URL")
            patch = {
                "content_type": "merchant_offer",
                "suggested_record_type": "merchant_offer",
                "campaign_category": "merchant",
                "primary_category": "merchant",
                "categories": ["merchant"],
                "review_required": False,
                "review_reasons": [],
                "review_decision": action,
                "review_approved": True,
                "manual_override": True,
                "classification_method": "admin_bulk_separate_merchant_v1",
                "reviewed_by": reviewer,
                "reviewed_at": reviewed_at,
                "review_request_id": request_id,
            }
            overrides.setdefault("items", {})[item["id"]] = {
                **overrides.get("items", {}).get(item["id"], {}),
                **patch,
            }
            item.update(patch)
            approved_record_ids.append(item["id"])
    elif action == "link_existing":
        campaign_id = clean(payload.get("target_campaign_id"), 240)
        target = by_id.get(campaign_id)
        if not target or target.get("content_type") not in {"campaign", "merchant_offer"}:
            raise ValueError("The target campaign does not exist")
        if target.get("competitor_id") not in competitors:
            raise ValueError("Cannot link items across competitors")
    elif action in {"group_campaign", "confirm_campaign", "confirm_merchant_offer"}:
        record_type = "merchant_offer" if action == "confirm_merchant_offer" or payload.get("record_type") == "merchant_offer" else "campaign"
        # A single verified official website row can itself be the canonical campaign.
        direct_item = len(items) == 1 and items[0].get("source_type") == "website" and action != "group_campaign"
        if direct_item:
            item = items[0]
            direct_category = "merchant" if record_type == "merchant_offer" else clean(payload.get("campaign_category") or item.get("campaign_category") or "other", 40)
            if direct_category not in ALLOWED_CATEGORIES:
                raise ValueError("Unknown campaign category")
            patch = {
                "content_type": record_type,
                "suggested_record_type": record_type,
                "campaign_category": direct_category,
                "review_required": False,
                "review_reasons": [],
                "review_decision": action,
                "review_approved": True,
                "manual_override": True,
                "reviewed_by": reviewer,
                "reviewed_at": reviewed_at,
                "review_request_id": request_id,
            }
            overrides.setdefault("items", {})[item["id"]] = {**overrides.get("items", {}).get(item["id"], {}), **patch}
            item.update(patch)
        else:
            new_record = create_canonical(payload, items, request_id, reviewer, reviewed_at, record_type, action)
            campaign_id = new_record["id"]
            overrides.setdefault("new_items", []).append(new_record)

    if action in {"mark_not_campaign", "mark_awareness"}:
        for item in items:
            patch = patch_for(item, action, None, reviewer, reviewed_at, request_id)
            patch["content_type"] = "awareness" if action == "mark_awareness" or item.get("source_type") != "social" else "social_post"
            patch["current_status"] = "Reviewed"
            overrides.setdefault("items", {})[item["id"]] = {**overrides.get("items", {}).get(item["id"], {}), **patch}
            item.update(patch)
    elif campaign_id:
        for item in items:
            patch = patch_for(item, action, campaign_id, reviewer, reviewed_at, request_id)
            overrides.setdefault("items", {})[item["id"]] = {**overrides.get("items", {}).get(item["id"], {}), **patch}
            item.update(patch)

    history = overrides.setdefault("review_history", [])
    history.append({
        "request_id": request_id,
        "reviewed_at": reviewed_at,
        "reviewed_by": reviewer,
        "action": action,
        "item_ids": item_ids,
        "campaign_id": campaign_id or (items[0]["id"] if action in {"confirm_campaign", "confirm_merchant_offer"} else None),
        "record_ids": approved_record_ids or ([items[0]["id"]] if action in {"confirm_campaign", "confirm_merchant_offer"} else []),
    })
    overrides["review_history"] = history[-500:]
    overrides["schema_version"] = 3
    overrides["updated_at"] = reviewed_at
    data["review_activity"] = overrides["review_history"][-50:]
    data["items"] = list(by_id.values())
    save(OVERRIDES_PATH, overrides)
    save(DATA_PATH, data)
    print(json.dumps({"applied": True, "action": action, "items": len(items), "campaign_id": campaign_id}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload", required=True)
    parser.add_argument("--reviewer", default="admin")
    parser.add_argument("--request-id", required=True)
    args = parser.parse_args()
    try:
        apply(decode_payload(args.payload), args.reviewer, args.request_id)
    except ValueError as exc:
        message = str(exc).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Review decision rejected::{message}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
