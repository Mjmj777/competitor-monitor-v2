"""Generate grounded bilingual AI summaries for the competitor dashboard.

Designed for GitHub Actions:
- reads OPENAI_API_KEY only from the environment;
- uses GPT-5.6 Sol in standard mode with xhigh reasoning by default;
- calls OpenAI only when material campaign/offer data changes;
- ordinary social-post churn does not trigger a paid API call;
- preserves the last good summary if the API is unavailable or returns invalid output.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data.json"
OUTPUT_PATH = BASE_DIR / "ai_summary.json"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REASONING_EFFORT = "xhigh"
DEFAULT_MAX_OUTPUT_TOKENS = 8000


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
    """Return only fields that are allowed to trigger a paid AI refresh.

    Social posts are intentionally excluded: routine posts can change every monitor
    cycle and should not spend API credit unless they alter a tracked campaign/offer.
    """
    active_campaigns: list[dict[str, Any]] = []
    active_merchants: list[dict[str, Any]] = []

    for item in data.get("items", []):
        if item.get("active") is False:
            continue
        if item.get("content_type") == "campaign":
            active_campaigns.append(_campaign_fact(item))
        elif item.get("content_type") == "merchant_offer":
            active_merchants.append(_merchant_fact(item))

    active_campaigns.sort(key=lambda x: (x.get("competitor_id") or "", x.get("title") or ""))
    active_merchants.sort(key=lambda x: (x.get("competitor_id") or "", x.get("title") or ""))
    return {
        "competitors": [
            {"id": c.get("id"), "name": c.get("name_en") or c.get("name")}
            for c in data.get("competitors", [])
        ],
        "active_campaigns": active_campaigns,
        "active_merchants": active_merchants,
    }


def latest_social_context(data: dict[str, Any], limit: int = 30) -> list[dict[str, Any]]:
    """Context for analysis only; it does not participate in the material-change hash."""
    posts: list[dict[str, Any]] = []
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
    posts.sort(
        key=lambda x: (x.get("published_at") or "", x.get("competitor_id") or "", x.get("title") or ""),
        reverse=True,
    )
    return posts[:limit]


def snapshot_hash(snapshot: dict[str, Any]) -> str:
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _keyed(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = f"{row.get('competitor_id') or ''}::{row.get('title') or ''}"
        result[key] = row
    return result


def material_changes(previous: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    """Create a compact deterministic delta so the model knows what actually changed."""
    if not previous:
        return [{"type": "initial_generation", "detail": "No previous material snapshot is available."}]

    changes: list[dict[str, Any]] = []
    for section, label in (("active_campaigns", "campaign"), ("active_merchants", "merchant_offer")):
        old = _keyed(previous.get(section, []))
        new = _keyed(current.get(section, []))

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


def extract_json(text: str) -> dict[str, Any]:
    value = text.strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    start, end = value.find("{"), value.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model response did not contain a JSON object")
    return json.loads(value[start : end + 1])


def validate_summary(payload: dict[str, Any], competitor_ids: set[str]) -> None:
    for lang in ("ar", "en"):
        section = payload.get("market", {}).get(lang, {})
        if not section.get("summary") or not isinstance(section.get("bullets"), list):
            raise ValueError(f"Missing market summary for {lang}")
        if len(section["bullets"]) < 3:
            raise ValueError(f"Market summary needs at least 3 bullets for {lang}")

    comps = payload.get("competitors", {})
    for competitor_id in competitor_ids:
        for lang in ("ar", "en"):
            section = comps.get(competitor_id, {}).get(lang, {})
            if not section.get("summary") or not isinstance(section.get("bullets"), list):
                raise ValueError(f"Missing {lang} summary for {competitor_id}")
            if len(section["bullets"]) < 3:
                raise ValueError(f"Competitor summary needs at least 3 bullets for {competitor_id}/{lang}")


def build_prompt(
    snapshot: dict[str, Any],
    changes: list[dict[str, Any]],
    social_context: list[dict[str, Any]],
) -> str:
    context = {
        "material_changes_since_last_ai_summary": changes,
        "current_material_snapshot": snapshot,
        "latest_social_context": social_context,
    }
    return f"""You are the market-intelligence analyst for a Saudi digital-payments competitor dashboard.

Use ONLY the supplied JSON facts. Do not browse. Do not invent, estimate, or infer undisclosed performance, market share, customer numbers, campaign results, causality, or commercial impact. Distinguish tracked campaigns from merchant offers. Merchant offers are reference items and must not be counted as campaign KPIs. Treat an item with no stated end date as ongoing/unknown, never permanent. Use cautious wording when dates or statuses are not explicit.

The field material_changes_since_last_ai_summary is the authoritative delta. Use it to identify genuinely new, removed/inactive, extended, or updated offers. latest_social_context may add context, but routine social posts must not be described as a market change unless the material delta supports it.

Output VALID JSON ONLY with exactly this shape:
{{
  "market": {{
    "ar": {{"summary": "one concise paragraph", "bullets": ["point 1", "point 2", "point 3"]}},
    "en": {{"summary": "one concise paragraph", "bullets": ["point 1", "point 2", "point 3"]}}
  }},
  "competitors": {{
    "<competitor_id>": {{
      "ar": {{"summary": "one concise paragraph", "bullets": ["point 1", "point 2", "point 3"]}},
      "en": {{"summary": "one concise paragraph", "bullets": ["point 1", "point 2", "point 3"]}}
    }}
  }}
}}

Writing requirements:
- Arabic: clear professional Arabic suitable for a management meeting.
- English: simple professional English.
- Market summary: 55-90 Arabic words / 45-75 English words.
- Each competitor summary: 35-65 Arabic words / 30-55 English words.
- Exactly 3 short factual bullets per section.
- Lead with the most decision-relevant competitive signal, not generic marketing language.
- Focus on category intensity (especially remittance, cards, Musaned and SADAD), offer mechanics, expiry/watchpoints, meaningful changes, and visible competitive gaps supported by the facts.
- If there is no meaningful delta for a competitor, summarize its current positioning without claiming a new move.

SOURCE JSON:
{json.dumps(context, ensure_ascii=False, indent=2)}
"""


def main() -> int:
    data = load_json(DATA_PATH, {})
    if not data:
        raise SystemExit("data.json is missing or empty")

    snapshot = current_material_snapshot(data)
    digest = snapshot_hash(snapshot)
    existing = load_json(OUTPUT_PATH, {})
    force = os.getenv("AI_SUMMARY_FORCE", "").lower() in {"1", "true", "yes"}

    if not force and existing.get("snapshot_hash") == digest:
        print("AI summary unchanged: no material campaign/offer change detected.")
        return 0

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY is not configured; keeping the existing AI summary file.")
        return 0

    previous_snapshot = existing.get("material_snapshot") or {}
    changes = material_changes(previous_snapshot, snapshot)
    social_context = latest_social_context(data)

    from openai import OpenAI

    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    effort = os.getenv("OPENAI_REASONING_EFFORT", DEFAULT_REASONING_EFFORT)
    max_output_tokens = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", str(DEFAULT_MAX_OUTPUT_TOKENS)))

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            reasoning={"effort": effort},
            text={"verbosity": "low"},
            max_output_tokens=max_output_tokens,
            input=build_prompt(snapshot, changes, social_context),
        )
        generated = extract_json(response.output_text)
        competitor_ids = {c["id"] for c in snapshot["competitors"] if c.get("id")}
        validate_summary(generated, competitor_ids)
    except Exception as exc:  # Keep monitoring/deployment alive if the AI layer fails.
        print(f"AI summary generation failed; keeping last good summary: {type(exc).__name__}: {exc}")
        return 0

    usage = getattr(response, "usage", None)
    usage_payload: dict[str, Any] = {}
    if usage is not None:
        for field in ("input_tokens", "output_tokens", "total_tokens"):
            value = getattr(usage, field, None)
            if value is not None:
                usage_payload[field] = value

    output = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "reasoning_effort": effort,
        "snapshot_hash": digest,
        "material_change_count": len(changes),
        "material_snapshot": snapshot,
        "usage": usage_payload,
        "market": generated["market"],
        "competitors": generated["competitors"],
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"AI summary generated with {model} / {effort}: {digest[:12]} ({len(changes)} material changes)")
    if usage_payload:
        print(f"OpenAI usage: {usage_payload}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
