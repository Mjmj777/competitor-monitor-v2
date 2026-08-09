"""Build deterministic, zero-API-cost intelligence metrics for the dashboard.

Outputs:
- intelligence.json: scores, expiry watch, category intensity and current metrics.
- market_history.json: one compact daily snapshot, retained for 180 days.

This layer is intentionally deterministic so the dashboard keeps useful analysis even
when the OpenAI API is unavailable, and so only interpretation—not counting/scoring—
consumes AI tokens.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.json"
INTELLIGENCE_PATH = BASE_DIR / "intelligence.json"
HISTORY_PATH = BASE_DIR / "market_history.json"
PRIORITY_CATEGORIES = ("remittance", "card", "musaned", "sadad")
MAX_HISTORY_DAYS = 180


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def active_campaigns(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in data.get("items", []) if i.get("active") is not False and i.get("content_type") == "campaign"]


def active_merchants(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in data.get("items", []) if i.get("active") is not False and i.get("content_type") == "merchant_offer"]


def recent_social(data: dict[str, Any], now: datetime, days: int = 7) -> list[dict[str, Any]]:
    cutoff = now.timestamp() - days * 86400
    rows = []
    for item in data.get("items", []):
        if item.get("source_type") != "social" or item.get("active") is False:
            continue
        dt = parse_dt(item.get("published_at") or item.get("first_seen") or item.get("last_seen"))
        if dt and dt.timestamp() >= cutoff:
            rows.append(item)
    return rows


def norm(value: float, max_value: float) -> int:
    if max_value <= 0:
        return 0
    return round(min(1.0, value / max_value) * 100)


def expiry_days(item: dict[str, Any], now: datetime) -> int | None:
    dt = parse_dt(item.get("end_date"))
    if not dt:
        return None
    return (dt.date() - now.date()).days


def score_competitors(data: dict[str, Any], campaigns: list[dict[str, Any]], social7: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = []
    for comp in data.get("competitors", []):
        cid = comp.get("id")
        rows = [i for i in campaigns if i.get("competitor_id") == cid]
        social = [i for i in social7 if i.get("competitor_id") == cid]
        active_count = len(rows)
        priority_categories = {i.get("campaign_category") for i in rows if i.get("campaign_category") in PRIORITY_CATEGORIES}
        priority_breadth = len(priority_categories) / len(PRIORITY_CATEGORIES)
        avg_platform_coverage = sum(float(i.get("social_link_count") or 0) for i in rows) / len(rows) if rows else 0.0
        raw.append({
            "competitor_id": cid,
            "name": comp.get("name_en") or comp.get("name_ar") or cid,
            "active_campaigns": active_count,
            "priority_category_count": len(priority_categories),
            "priority_categories": sorted(priority_categories),
            "priority_breadth": priority_breadth,
            "social_posts_7d": len(social),
            "avg_platform_coverage": round(avg_platform_coverage, 2),
        })

    max_campaigns = max((r["active_campaigns"] for r in raw), default=0)
    max_social = max((r["social_posts_7d"] for r in raw), default=0)
    for r in raw:
        components = {
            "campaign_intensity": norm(r["active_campaigns"], max_campaigns),
            "priority_category_breadth": round(r["priority_breadth"] * 100),
            "social_activity_7d": norm(r["social_posts_7d"], max_social),
            "platform_coverage": round(min(1.0, r["avg_platform_coverage"] / 4.0) * 100),
        }
        score = round(
            components["campaign_intensity"] * 0.35
            + components["priority_category_breadth"] * 0.25
            + components["social_activity_7d"] * 0.20
            + components["platform_coverage"] * 0.20
        )
        r["score"] = score
        r["components"] = components
    return sorted(raw, key=lambda r: (-r["score"], r["name"]))


def category_intensity(data: dict[str, Any], campaigns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    comps = [c.get("id") for c in data.get("competitors", []) if c.get("id")]
    result = []
    for cat in data.get("categories", []):
        cid = cat.get("id")
        if cid == "merchant":
            continue
        rows = [i for i in campaigns if i.get("campaign_category") == cid]
        comp_count = len({i.get("competitor_id") for i in rows if i.get("competitor_id")})
        ratio = comp_count / len(comps) if comps else 0
        if len(rows) >= 5 or ratio >= 0.67:
            level = "high"
        elif len(rows) >= 2 or ratio >= 0.34:
            level = "medium"
        else:
            level = "low"
        result.append({
            "category_id": cid,
            "name_ar": cat.get("name_ar"),
            "name_en": cat.get("name_en"),
            "active_campaigns": len(rows),
            "competitors_active": comp_count,
            "competitor_coverage_pct": round(ratio * 100),
            "intensity": level,
        })
    return result


def build_expiry_watch(campaigns: list[dict[str, Any]], merchants: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    def compact(item: dict[str, Any], record_type: str, days: int) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "competitor_id": item.get("competitor_id"),
            "title": item.get("title"),
            "category": item.get("campaign_category"),
            "record_type": record_type,
            "end_date": item.get("end_date"),
            "days_remaining": days,
            "link": item.get("link") or item.get("official_campaign_page_url"),
        }

    rows = []
    for item, rtype in [(i, "campaign") for i in campaigns] + [(i, "merchant_offer") for i in merchants]:
        days = expiry_days(item, now)
        if days is None or days < 0:
            continue
        rows.append(compact(item, rtype, days))
    rows.sort(key=lambda r: (r["days_remaining"], r["competitor_id"] or "", r["title"] or ""))
    return {
        "within_7_days": [r for r in rows if r["days_remaining"] <= 7],
        "within_14_days": [r for r in rows if r["days_remaining"] <= 14],
        "within_30_days": [r for r in rows if r["days_remaining"] <= 30],
    }


def build_daily_snapshot(data: dict[str, Any], campaigns: list[dict[str, Any]], scores: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    categories = {cat: len([i for i in campaigns if i.get("campaign_category") == cat]) for cat in PRIORITY_CATEGORIES}
    by_competitor = {}
    score_map = {r["competitor_id"]: r["score"] for r in scores}
    for comp in data.get("competitors", []):
        cid = comp.get("id")
        rows = [i for i in campaigns if i.get("competitor_id") == cid]
        by_competitor[cid] = {
            "active_campaigns": len(rows),
            "remittance": len([i for i in rows if i.get("campaign_category") == "remittance"]),
            "card": len([i for i in rows if i.get("campaign_category") == "card"]),
            "musaned": len([i for i in rows if i.get("campaign_category") == "musaned"]),
            "sadad": len([i for i in rows if i.get("campaign_category") == "sadad"]),
            "activity_score": score_map.get(cid, 0),
        }
    return {
        "date": now.date().isoformat(),
        "captured_at": now.isoformat(),
        "active_campaigns": len(campaigns),
        "categories": categories,
        "competitors": by_competitor,
    }


def update_history(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    history = load_json(HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []
    same_day = next((row for row in history if isinstance(row, dict) and row.get("date") == snapshot["date"]), None)
    comparable = lambda row: {k: v for k, v in row.items() if k != "captured_at"}
    if same_day and comparable(same_day) == comparable(snapshot):
        snapshot = same_day  # Avoid rewriting the same daily point every monitor cycle.
    history = [row for row in history if isinstance(row, dict) and row.get("date") != snapshot["date"]]
    history.append(snapshot)
    history.sort(key=lambda r: r.get("date") or "")
    history = history[-MAX_HISTORY_DAYS:]
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return history


def recent_change_signals(data: dict[str, Any], now: datetime, days: int = 30) -> list[dict[str, Any]]:
    cutoff = now.timestamp() - days * 86400
    rows = []
    for item in data.get("items", []):
        if item.get("content_type") not in {"campaign", "merchant_offer"}:
            continue
        dt = parse_dt(item.get("last_changed") or item.get("first_seen"))
        if not dt or dt.timestamp() < cutoff:
            continue
        rows.append({
            "id": item.get("id"),
            "competitor_id": item.get("competitor_id"),
            "title": item.get("title"),
            "record_type": item.get("content_type"),
            "category": item.get("campaign_category"),
            "last_changed": (item.get("last_changed") or item.get("first_seen")),
            "status": item.get("current_status"),
        })
    rows.sort(key=lambda r: r.get("last_changed") or "", reverse=True)
    return rows[:30]


def main() -> int:
    data = load_json(DATA_PATH, {})
    if not data:
        raise SystemExit("data.json is missing or empty")
    now = datetime.now(timezone.utc)
    campaigns = active_campaigns(data)
    merchants = active_merchants(data)
    social7 = recent_social(data, now, 7)
    scores = score_competitors(data, campaigns, social7)
    intensity = category_intensity(data, campaigns)
    expiry = build_expiry_watch(campaigns, merchants, now)
    daily = build_daily_snapshot(data, campaigns, scores, now)
    history = update_history(daily)

    output = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "score_methodology": {
            "name": "Competitive Activity Score",
            "scale": "0-100",
            "weights": {
                "campaign_intensity": 0.35,
                "priority_category_breadth": 0.25,
                "social_activity_7d": 0.20,
                "platform_coverage": 0.20,
            },
            "note": "Deterministic activity indicator; it does not measure market share, campaign performance, customer adoption, or commercial attractiveness.",
        },
        "market": {
            "active_campaigns": len(campaigns),
            "active_merchant_offers": len(merchants),
            "social_posts_7d": len(social7),
            "category_intensity": intensity,
            "expiry_watch": expiry,
            "recent_change_signals": recent_change_signals(data, now),
        },
        "competitor_scores": scores,
        "history": history,
    }
    existing = load_json(INTELLIGENCE_PATH, {})
    if isinstance(existing, dict):
        old_core = {k: v for k, v in existing.items() if k != "generated_at"}
        new_core = {k: v for k, v in output.items() if k != "generated_at"}
        if old_core == new_core and existing.get("generated_at"):
            output["generated_at"] = existing["generated_at"]
    INTELLIGENCE_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Intelligence metrics built: {len(campaigns)} campaigns, {len(scores)} competitor scores, {len(history)} history days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
