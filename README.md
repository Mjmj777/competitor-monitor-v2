# Competitor Intelligence Monitor v5.12.0

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

## Cloudflare secrets

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `VIEWER_USERNAME`
- `VIEWER_PASSWORD`
- `SESSION_SECRET`
- `GITHUB_ACTIONS_TOKEN` — required for Admin refresh/review dispatch only; not required for password protection.

The fine-grained GitHub token needs repository access to `Mjmj777/competitor-monitor-v2`, `Actions: Read and write`, and automatic `Metadata: Read-only`. It does not need Contents write access.

## Safe upload

Use the final package's `UPLOAD_TO_GITHUB` directory only. It intentionally excludes existing generated/business data (`data.json`, `state.json`, `inventory.json`, `manual_overrides.json` and Excel files), so uploading the update cannot overwrite current monitoring history or manual decisions.

After GitHub Actions succeeds, copy the complete `cloudflare-worker.js` from the repository update into the Cloudflare Worker editor and Deploy. `/__session` should then report `worker_build: "5.12.0"`.
