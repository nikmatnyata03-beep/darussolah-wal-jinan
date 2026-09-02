# Darussolah Production Verification

Date: 2026-09-02 09:19 UTC

Project: Supabase `aura` (`kvapcykpscswsqsylzly`)

## Live changes applied

- Created or enforced the private `learning-resources` Storage bucket.
- Created the learning-resource authorization functions.
- Added authenticated insert, select, and delete policies for learning resources.
- Added the authenticated delete policy for `learning-submissions` cleanup.
- Re-applied the API-only table privilege lockdown for `anon` and `authenticated`.
- Added `darussolah.page_blocks` through migration `010_cms_page_blocks.sql` and seeded 36 editable foundation/institution blocks.

No existing application rows were changed; the migration added only the CMS table and its 36 seed block rows.

## Verification results

- `learning-resources`: present, private.
- `learning-submissions`: present, private.
- `site-media`: present, public as intended.
- Learning Storage policies: six present, authenticated-only.
- Direct table grants in schema `darussolah`: none for `anon` or `authenticated`.
- RLS: enabled on the 24 main application tables.
- Public site: loaded successfully at `https://darussolah-wal-jinan.vercel.app/`.
- API liveness: `/health/live` returned `{"status":"ok"}`.
- API readiness: `/health/ready` returned `{"status":"ready"}`.
- Authorization hardening commit `50ff21e68701ea1b392540e9bc63e05c25f25def` deployed automatically through the Cloud Build trigger.
- Cloud Run revision `darussolah-api-00038-dt7` is serving 100% traffic.
- Live API checks on revision `00038`: liveness `200`, readiness `200`, public institutions `200`, anonymous private route `401`.
- Admin record queries had a PostgreSQL `IndeterminateDatatypeError` for an untyped unused parameter; commit `2ab0fad4b014d84b23497b0194fa41e68bf5bfc1` explicitly types it as `uuid`.
- Cloud Build completed successfully and Cloud Run revision `darussolah-api-00039-5j9` is serving 100% traffic.
- Live API checks on revision `00039`: liveness `200`, readiness `200`, public institutions `200`, anonymous admin-record route `401`.
- CMS follow-up is live: public page blocks returned `200` with 12 foundation blocks, public teachers returned `200` with an empty list, and anonymous restore returned `401`.
- Anonymous page-block administration returned `401`; Vercel served the updated `cms.html`, `darussolah-admin.js`, `index.html`, and institution-site assets.
- GitHub `main` now ends at CMS commit `73961d6963a598606bc0600d8759e3792acc8d18`.

## Remaining risks

- The `darussolah.tenants` table has RLS disabled, although direct browser table grants are currently absent. Keep it behind the API and review whether defense-in-depth RLS is required.
- Supabase migration history is from the Nexus track, so it is not a reliable record of the primary migration filenames. The live schema was inspected before applying the targeted fixes.
- Updated frontend source is live on Vercel; updated backend CMS endpoints are live on the Cloud Run service.
- The automatic deployment integration propagated the follow-up commits; the public API smoke tests passed after rollout.
- Final GitHub `main` commit: `73961d6963a598606bc0600d8759e3792acc8d18`.
- The scheduled backup workflow is now present, but the repository has no Actions secrets yet; a private archive destination and restore drill are still pending.
- Payment, messaging, and generated-report providers are not connected.
