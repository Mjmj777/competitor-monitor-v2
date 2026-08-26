# Competitor Intelligence Monitor v5.8.0

This release combines the v5.7.3 safe Admin refresh and source-reliability work with a redesigned analytics experience.

## Analytics

- Active campaigns by competitor, sorted from highest to lowest.
- Campaign changes over the last 30 days: new, updated and recently expired.
- Normalized campaign mix by competitor.
- Interactive category coverage heatmap.
- Remittance campaigns, merchant offers, offer mechanics and expiry risk.
- Social-media comparison for rolling 7-day or 30-day periods.
- Current social period compared with the equivalent previous period.
- Social platform filter for Instagram, Facebook, X and TikTok.
- Fixed competitor colors across charts.
- Chart drill-down to filtered inventory.
- Scroll-triggered chart animation with reduced-motion support.

## Safe Admin refresh

- Admin-only refresh for one competitor or all competitors.
- Unique `request_id` for every refresh.
- `/__refresh-status` completion tracking.
- Active-run detection prevents duplicate refresh requests.
- New/updated/unchanged/source-failure summary after completion.
- Last 20 refresh summaries for Admin only.
- Failed and zero-item sources preserve last-known-good data.
- Viewer refresh attempts return HTTP 403.

## Runtime checks

GitHub Actions validates JavaScript syntax, chart renderer behavior, Worker refresh behavior, project consistency and semantic output before deployment.

## Data files

Do not overwrite the repository's current `data.json`, `state.json`, `inventory.json`, `manual_overrides.json`, or generated Excel files when applying this code-only package.

## Secrets

- Cloudflare Worker: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `VIEWER_USERNAME`, `VIEWER_PASSWORD`, `SESSION_SECRET`, `GITHUB_ACTIONS_TOKEN`.
- GitHub Actions: `OPENAI_API_KEY` if AI enrichment is enabled.
- `GITHUB_ACTIONS_TOKEN` is required only for Admin manual refresh, not password protection.
