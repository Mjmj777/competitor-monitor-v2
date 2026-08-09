"""Generate one grounded AI intelligence package for the whole dashboard.

Cost controls:
- exactly one Responses API call per eligible refresh;
- refreshes only when material campaign/offer data changes, or when the prompt/schema
  version changes (one-time upgrade refresh), or when AI_SUMMARY_FORCE is set;
- routine social-post churn does not trigger a paid call;
- deterministic scores/history/expiry calculations come from intelligence.json;
- last good AI output is preserved if the API is unavailable.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.json"
INTELLIGENCE_PATH = BASE_DIR / "intelligence.json"
OUTPUT_PATH = BASE_DIR / "ai_summary.json"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_MAX_OUTPUT_TOKENS = 10000
PROMPT_VERSION = 4


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _campaign_fact(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "competitor_id": item.get("competitor_id"),
        "category": item.get("campaign_category"),
        "title": item.get("title"),
        "summary": item.get("summary") or item.get("snippet"),
        "mechanic": item.get("mechanic"),
        "mechanic_tags": item.get("mechanic_tags") or [],
        "status": item.get("current_status"),
        "start_date": item.get("start_date"),
        "end_date": item.get("end_date"),
        "social_link_count": item.get("social_link_count", 0),
    }


def _merchant_fact(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "competitor_id": item.get("competitor_id"),
        "title": item.get("title"),
        "mechanic": item.get("mechanic"),
        "status": item.get("current_status"),
        "start_date": item.get("start_date"),
        "end_date": item.get("end_date"),
    }


def current_material_snapshot(data: dict[str, Any]) -> dict[str, Any]:
    """Only fields allowed to trigger a paid refresh.

    Social posts are excluded from this hash. They can be context in a refresh that was
    already triggered by a material campaign/offer change, but cannot trigger spending.
    """
    campaigns: list[dict[str, Any]] = []
    merchants: list[dict[str, Any]] = []
    for item in data.get("items", []):
        if item.get("active") is False:
            continue
        if item.get("content_type") == "campaign":
            campaigns.append(_campaign_fact(item))
        elif item.get("content_type") == "merchant_offer":
            merchants.append(_merchant_fact(item))
    campaigns.sort(key=lambda x: (x.get("competitor_id") or "", x.get("title") or ""))
    merchants.sort(key=lambda x: (x.get("competitor_id") or "", x.get("title") or ""))
    return {
        "competitors": [
            {"id": c.get("id"), "name": c.get("name_en") or c.get("name_ar")}
            for c in data.get("competitors", [])
        ],
        "active_campaigns": campaigns,
        "active_merchants": merchants,
    }


def latest_social_context(data: dict[str, Any], limit: int = 24) -> list[dict[str, Any]]:
    posts = []
    for item in data.get("items", []):
        if item.get("source_type") != "social":
            continue
        posts.append({
            "competitor_id": item.get("competitor_id"),
            "platform": item.get("platform"),
            "title": item.get("title"),
            "published_at": item.get("published_at"),
            "content_type": item.get("content_type"),
        })
    posts.sort(key=lambda x: (x.get("published_at") or "", x.get("competitor_id") or ""), reverse=True)
    return posts[:limit]


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _keyed(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f"{row.get('competitor_id') or ''}::{row.get('title') or ''}": row for row in rows}


def material_changes(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    if not previous:
        return [{"type": "initial_generation", "detail": "No previous material snapshot is available."}]
    changes: list[dict[str, Any]] = []
    for section, label in (("active_campaigns", "campaign"), ("active_merchants", "merchant_offer")):
        old, new = _keyed(previous.get(section, [])), _keyed(current.get(section, []))
        for key in sorted(new.keys() - old.keys()):
            changes.append({"type": f"new_{label}", "current": new[key]})
        for key in sorted(old.keys() - new.keys()):
            changes.append({"type": f"removed_or_inactive_{label}", "previous": old[key]})
        for key in sorted(old.keys() & new.keys()):
            if old[key] != new[key]:
                field_changes = {
                    field: {"from": old[key].get(field), "to": new[key].get(field)}
                    for field in sorted(set(old[key]) | set(new[key]))
                    if old[key].get(field) != new[key].get(field)
                }
                changes.append({
                    "type": f"updated_{label}",
                    "competitor_id": new[key].get("competitor_id"),
                    "title": new[key].get("title"),
                    "changes": field_changes,
                })
    return changes


def localized_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary", "bullets", "what_changed", "why_it_matters",
            "management_takeaway", "weekly_brief", "opportunity_gaps", "category_insights",
        ],
        "properties": {
            "summary": {"type": "string"},
            "bullets": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
            "what_changed": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
            "why_it_matters": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
            "management_takeaway": {"type": "string"},
            "weekly_brief": {"type": "string"},
            "opportunity_gaps": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 4},
            "category_insights": {
                "type": "array",
                "minItems": 4,
                "maxItems": 6,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["category_id", "insight"],
                    "properties": {
                        "category_id": {"type": "string"},
                        "insight": {"type": "string"},
                    },
                },
            },
        },
    }


def competitor_localized_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "bullets", "positioning", "what_changed", "watchpoints"],
        "properties": {
            "summary": {"type": "string"},
            "bullets": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
            "positioning": {"type": "string"},
            "what_changed": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
            "watchpoints": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 3},
        },
    }


def output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["market", "competitors"],
        "properties": {
            "market": {
                "type": "object",
                "additionalProperties": False,
                "required": ["ar", "en"],
                "properties": {"ar": localized_schema(), "en": localized_schema()},
            },
            "competitors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["competitor_id", "ar", "en"],
                    "properties": {
                        "competitor_id": {"type": "string"},
                        "ar": competitor_localized_schema(),
                        "en": competitor_localized_schema(),
                    },
                },
            },
        },
    }


STATIC_INSTRUCTIONS = """You are the market-intelligence analyst for a Saudi digital-payments competitor dashboard.

Use ONLY the supplied JSON facts. Never browse. Never invent, estimate, or imply undisclosed market share, customer numbers, campaign performance, causality, profitability, adoption, or commercial results. Merchant offers are reference items and must not be counted as campaign KPIs. An item with no stated end date is ongoing/unknown, never permanent. A deterministic Competitive Activity Score is an activity indicator only; never describe it as market share, performance, attractiveness, or success.

The material_changes_since_last_ai_summary field is the authoritative delta. Routine social posts are context only and must not be described as a material market change unless the authoritative delta supports it. Category intensity and scores are deterministic calculations supplied by the application; explain them but do not recalculate or contradict them.

Your job is to produce concise decision-support intelligence: current competitive situation, what changed, why it matters, management takeaway, visible gaps/opportunities, category insight, and a short 7-day executive brief. For every competitor, provide a concise summary, current positioning, genuine material changes (or explicitly say no material change was detected), and watchpoints.

Arabic must be clear professional Arabic for management. English must be simple professional English. Keep claims tightly grounded in supplied facts. Prefer specific categories/mechanics/dates over generic marketing language."""


def build_input(snapshot: dict[str, Any], changes: list[dict[str, Any]], social: list[dict[str, Any]], intelligence: dict[str, Any]) -> str:
    # Keep the history compact to reduce tokens. The full history remains on the dashboard.
    history = (intelligence.get("history") or [])[-30:]
    context = {
        "material_changes_since_last_ai_summary": changes,
        "current_material_snapshot": snapshot,
        "deterministic_intelligence": {
            "score_methodology": intelligence.get("score_methodology", {}),
            "competitor_scores": intelligence.get("competitor_scores", []),
            "market": intelligence.get("market", {}),
            "history_last_30_days": history,
        },
        "latest_social_context": social,
    }
    return "SOURCE JSON:\n" + json.dumps(context, ensure_ascii=False, separators=(",", ":"))


def normalize_competitors(generated: dict[str, Any], expected_ids: set[str]) -> dict[str, Any]:
    rows = generated.get("competitors") or []
    result = {row.get("competitor_id"): {"ar": row.get("ar", {}), "en": row.get("en", {})} for row in rows if row.get("competitor_id")}
    missing = expected_ids - set(result)
    extra = set(result) - expected_ids
    if missing:
        raise ValueError(f"AI output missing competitors: {sorted(missing)}")
    if extra:
        raise ValueError(f"AI output returned unknown competitors: {sorted(extra)}")
    return result


def validate_generated(generated: dict[str, Any], expected_ids: set[str]) -> None:
    market = generated.get("market") or {}
    for lang in ("ar", "en"):
        section = market.get(lang) or {}
        if not section.get("summary") or len(section.get("bullets") or []) != 3:
            raise ValueError(f"Invalid market section: {lang}")
    normalize_competitors(generated, expected_ids)


def usage_payload(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    payload: dict[str, Any] = {}
    for field in ("input_tokens", "output_tokens", "total_tokens"):
        value = getattr(usage, field, None)
        if value is not None:
            payload[field] = value
    details = getattr(usage, "input_tokens_details", None)
    if details is not None:
        cached = getattr(details, "cached_tokens", None)
        cache_write = getattr(details, "cache_write_tokens", None)
        if cached is not None:
            payload["cached_input_tokens"] = cached
        if cache_write is not None:
            payload["cache_write_tokens"] = cache_write
    return payload


def main() -> int:
    data = load_json(DATA_PATH, {})
    intelligence = load_json(INTELLIGENCE_PATH, {})
    if not data:
        raise SystemExit("data.json is missing or empty")
    if not intelligence:
        print("intelligence.json is missing; building deterministic intelligence metrics now...")
        try:
            from build_intelligence_metrics import main as build_intelligence_metrics
            build_intelligence_metrics()
            intelligence = load_json(INTELLIGENCE_PATH, {})
        except Exception as exc:
            raise SystemExit(f"Could not build intelligence.json automatically: {type(exc).__name__}: {exc}") from exc
        if not intelligence:
            raise SystemExit("intelligence.json is still missing after automatic build")

    snapshot = current_material_snapshot(data)
    digest = snapshot_hash(snapshot)
    existing = load_json(OUTPUT_PATH, {})
    force = os.getenv("AI_SUMMARY_FORCE", "").lower() in {"1", "true", "yes"}
    current_prompt = existing.get("prompt_version") == PROMPT_VERSION
    if not force and current_prompt and existing.get("snapshot_hash") == digest:
        print("AI intelligence unchanged: no material campaign/offer change detected.")
        return 0

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not configured; keeping the existing AI file.")
        return 0

    previous_snapshot = existing.get("material_snapshot") or {}
    changes = material_changes(previous_snapshot, snapshot)
    social = latest_social_context(data)
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    effort = os.getenv("OPENAI_REASONING_EFFORT", DEFAULT_REASONING_EFFORT)
    max_output_tokens = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS)))

    from openai import OpenAI

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            reasoning={"effort": effort},
            instructions=STATIC_INSTRUCTIONS,
            input=build_input(snapshot, changes, social, intelligence),
            text={
                "verbosity": "low",
                "format": {
                    "type": "json_schema",
                    "name": "competitor_intelligence_package",
                    "strict": True,
                    "schema": output_schema(),
                },
            },
            max_output_tokens=max_output_tokens,
            store=False,
        )
        generated = json.loads(response.output_text)
        expected_ids = {c["id"] for c in snapshot["competitors"] if c.get("id")}
        validate_generated(generated, expected_ids)
        competitors = normalize_competitors(generated, expected_ids)
    except Exception as exc:
        print(f"AI intelligence generation failed; keeping last good output: {type(exc).__name__}: {exc}")
        return 0

    output = {
        "schema_version": 3,
        "prompt_version": PROMPT_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "reasoning_effort": effort,
        "call_strategy": "single_call_on_material_change",
        "snapshot_hash": digest,
        "material_change_count": len(changes),
        "material_changes": changes,
        "material_snapshot": snapshot,
        "usage": usage_payload(response),
        "market": generated["market"],
        "competitors": competitors,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"AI intelligence generated in ONE call with {model} / {effort}: {digest[:12]} ({len(changes)} material changes)")
    if output["usage"]:
        print(f"OpenAI usage: {output['usage']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
