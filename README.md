# Competitor Intelligence Monitor v5.15.0

This hotfix improves Merchant Offer classification and adds safe separate-record bulk approval while preserving the v5.9 Admin review center.

## What changed

- Verified official campaigns no longer remain stuck behind a stale AI/classification cache.
- The rule covers STC Bank, barq, Mobily Pay, tiqmo, urpay and alinma Pay.
- Named retailer, restaurant, hotel, clinic, store and partner pages are surfaced first as potential Merchant Offers; currency/rate, remittance, cashback, prize and draw mechanics remain campaigns.
- barq, urpay and alinma Pay use source-specific timeouts and browser fallback where needed.
- urpay's official Cashback and Prize Games terms page is monitored as a first-party campaign source.
- Official competitor URLs embedded in social RSS posts are retained as campaign evidence.
- `review.html` is a dedicated Admin-only review center.
- One or many review items can be confirmed, rejected, marked Awareness, linked to an existing campaign, or grouped into one canonical campaign.
- Admin can filter potential Merchant Offers, select all visible official-page results, and approve each selection as a separate Merchant Offer record without merging them.
- Review submissions now queue safely through GitHub concurrency instead of being rejected by a stale “Another review decision is being saved” lock.
- Grouped posts remain evidence; they never inflate Campaign KPIs as separate campaigns.
- Review decisions are stored in `manual_overrides.json` with reviewer, timestamp, request ID and evidence IDs.
- Cloudflare dispatches the dedicated `review.yml` workflow using the existing `GITHUB_ACTIONS_TOKEN`.

## Security

The Worker remains the security boundary. Viewer requests to `/__refresh`, `/__review` and their status endpoints receive HTTP 403. `review.html` hides its content from non-Admin sessions, while the server-side Worker role check is authoritative.

## Hosting architecture

Cloudflare now hosts the authenticated website, `data.json`, logos/assets and the generated Excel report directly through the existing Worker. GitHub remains responsible for scheduled collection, review persistence and version history; it no longer deploys GitHub Pages. The old Pages origin is retained only as a temporary no-downtime fallback until the first successful Cloudflare deployment.

`run_worker_first = true` is intentional: every static file passes through the existing Admin/Viewer authentication before Cloudflare serves it.

## Cloudflare Worker secrets

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `VIEWER_USERNAME`
- `VIEWER_PASSWORD`
- `SESSION_SECRET`
- `GITHUB_ACTIONS_TOKEN` — required for Admin refresh/review dispatch only; not required for password protection.

The fine-grained GitHub token needs repository access to `Mjmj777/competitor-monitor-v2`, `Actions: Read and write`, and automatic `Metadata: Read-only`. It does not need Contents write access.

## GitHub deployment settings

Create these repository settings before the first v5.15.0 run:

- Actions variable `CLOUDFLARE_WORKER_NAME`: the exact name of the existing Worker currently connected to `competitor-monitors.com`.
- Actions secret `CLOUDFLARE_ACCOUNT_ID`: the Cloudflare account ID.
- Actions secret `CLOUDFLARE_API_TOKEN`: a scoped token with permission to edit Workers Scripts for this account.

The workflows deliberately stop before deployment if any setting is missing. They never fall back to the placeholder name in `wrangler.toml`, preventing accidental creation of a second Worker. Deploying to the same Worker name preserves its custom domain and existing runtime secrets.

## Safe upload

Use the final package's `UPLOAD_TO_GITHUB` directory only. It intentionally excludes existing generated/business data (`data.json`, `state.json`, `inventory.json`, `manual_overrides.json` and Excel files), so uploading the update cannot overwrite current monitoring history or manual decisions.

After the three repository settings are present, run **Competitor Intelligence Monitor** once for `all`. The workflow tests the project, refreshes the data, builds the Excel file, then deploys the Worker and static site together. `/__session` should report `worker_build: "5.15.0"`. Future hourly refreshes and Admin reviews deploy automatically; manual Worker copying is no longer required.
