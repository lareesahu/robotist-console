# Supabase deployment

Production routing keeps the existing Robotist static service and custom domains. That service publishes only `render-edge` and rewrites `/*` to `https://robotist-platform.onrender.com/*`. Never publish the repository root: it contains backend source, and existing HTML would shadow dynamic routes. The backend accepts the two exact Robotist HTTPS origins in proxy mode while still requiring the session CSRF token. No DNS change or extra paid service is needed for this arrangement.

Use `render-supabase.yaml` for free Render compute with remote persistence. The older `render-grn.yaml` is the paid local-disk alternative, not the selected deployment.

Run `grn/supabase-schema.sql` once against the dedicated Robotist Supabase project. It creates the private application/catalog tables with RLS enabled and no grants to anonymous or signed-in Data API clients. It also creates the private `robotist-private` upload bucket. The server uses PostgreSQL and the storage API; never expose its credentials in frontend code.

Set `ROBOTIST_DATABASE_URL` to the session pooler connection string, `ROBOTIST_SUPABASE_URL` to the HTTPS project origin, and `ROBOTIST_SUPABASE_KEY` to a server-only secret key. Keep `GRN_SECRET_KEY` and `GRN_ADMIN_PASSWORD_HASH` stable. `GRN_DATA_DIR` can now be an ephemeral directory outside the repository: hosted records and uploads are remote. Omitting the database URL retains local SQLite for development. A hosted database without remote file credentials fails startup.

Existing static robot pages are imported as unreviewed drafts. Original public pages remain the fallback until a reviewed draft is published. Imports skip existing slugs on restart. Run only one worker for first import. Private source documents and unpublished images are served through the existing authorization checks; bucket URLs are not public.

Free plans have limits: Render sleeps after inactivity and shares a monthly compute allowance across free services; Supabase can pause after inactivity and has storage/egress quotas. Do not promise uninterrupted availability or automatic backups. Database and upload persistence, authentication, and real form flows must be verified on the deployed service before switching the domain.
