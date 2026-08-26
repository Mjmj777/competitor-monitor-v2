# Competitor Intelligence Monitor v5.7.1 — UTF-8 + Admin Refresh

Unified clean release for the six Saudi fintech competitors.

## Runtime flow
GitHub Actions runs hourly:

1. Preflight consistency check
2. Validate monitor configuration
3. Discover official offers + social RSS
4. Browser fallback for JS/modal sources when required
5. Enrich official detail pages, dates, source verification and social linking
6. Deduplicate / normalize lifecycle / apply manual overrides and deletions
7. Postflight semantic validation
8. Refresh the approved Excel report
9. Deploy GitHub Pages

## Important
- `manual_overrides.json` contains persistent manual additions, edits and deletions. Preserve your current copy before a clean repository reset if you want to keep those changes.
- `state.json` and `data.json` can be regenerated.
- Authentication secrets are stored in Cloudflare and are **not** stored in this repository.
- `OPENAI_API_KEY` remains a GitHub Actions secret.
- Password protection does not need a GitHub token. The optional Admin-only manual refresh feature needs a Cloudflare Worker secret named `GITHUB_ACTIONS_TOKEN`; use a fine-grained token limited to this repository with `Actions: Read and write`.

## Roles
- Admin: full dashboard, alerts, source health, verification timing, Add/Edit/Delete Campaign, Needs Review, Admin Tools, per-competitor refresh and refresh-all.
- Viewer: dashboard, campaigns, analytics, official/social links and Full Report. No alerts, source health, verification timing, review queue or editing tools.

## Manual refresh
- `Check now` on a competitor card or competitor page runs only that competitor's discovery and detail verification.
- `Check all competitors` on the home page runs the complete monitor.
- The Worker validates the signed session again and returns `403` for Viewer requests, including direct API attempts.
- Scheduled hourly runs continue to refresh all competitors.

## Verification cadence
- Official offer indexes and social sources: hourly.
- Manual/new official campaign URLs: immediate verification on the next run.
- Offers missing dates / near expiry: priority rechecks.
- Stable fully-dated detail pages: reduced-frequency verification to keep hourly Actions fast.
