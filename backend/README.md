# Darussolah Foundation Backend

API for `Yayasan Darussolah Wal Jinan`. The first release contains public reads, registration intake, Supabase Auth token validation, scoped profile/master-data reads, attendance, and the first learning-resource slice.

## Local test

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

## Local run

1. Copy `.env.example` to `.env` and set `DARUSSOLAH_DATABASE_URL`.
2. Run `migrations/001_initial.sql`, then `migrations/002_core_portal.sql`, `migrations/003_attendance.sql`, `migrations/004_learning.sql`, `migrations/005_learning_submissions.sql`, `migrations/006_learning_submission_storage.sql`, `migrations/007_admin_operations.sql`, `migrations/008_learning_resource_storage.sql`, `migrations/009_api_only_data_plane.sql`, and `migrations/010_cms_page_blocks.sql` against the PostgreSQL database.
3. Run `seed/001_demo_data.sql` for the initial foundation and four institutions, then `seed/002_core_demo_data.sql` for synthetic academic programs and classes, `seed/003_attendance_demo_data.sql` for synthetic students and attendance, `seed/004_learning_demo_data.sql` for synthetic materials and assignments, and `seed/005_learning_submissions_demo_data.sql` for synthetic submissions.
4. Set `DARUSSOLAH_SUPABASE_URL` so the API can derive the Supabase JWKS URL. `DARUSSOLAH_JWT_SECRET` is optional legacy fallback support.
5. Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

## Production deployment

Build and deploy the included `Dockerfile` to Google Cloud Run. Set `DARUSSOLAH_DATABASE_URL` to the Supabase transaction pooler connection string, `DARUSSOLAH_SUPABASE_URL` to the project URL, and `DARUSSOLAH_ALLOWED_ORIGINS` to the exact website origin. See `../darussolah-cloud-run.md` for the Cloud Run checklist, Secret Manager setup, and cost safeguards.

The migration intentionally keeps tenant-owned tables behind PostgreSQL row-level security. The API sets `app.tenant_id` for every tenant-scoped operation before querying.

Private routes require a Supabase Auth access token validated through the configured JWKS URL, or through the optional legacy `DARUSSOLAH_JWT_SECRET`:

- `GET /v1/private/{tenant_slug}/me`
- `GET /v1/private/{tenant_slug}/students`
- `GET /v1/private/{tenant_slug}/classes`
- `GET /v1/private/{tenant_slug}/learning?class_id={class_id}&resource_type={material|assignment|announcement}`
- `POST /v1/private/{tenant_slug}/learning`
- `GET /v1/private/{tenant_slug}/learning/submissions?class_id={class_id}&resource_id={resource_id}`
- `POST /v1/private/{tenant_slug}/learning/submissions`
- `PUT /v1/private/{tenant_slug}/learning/submissions/{submission_id}`
- `GET /v1/private/{tenant_slug}/guardian/overview?student_id={student_id}`
- `GET /v1/private/{tenant_slug}/attendance?class_id={class_id}&attendance_date={YYYY-MM-DD}`
- `PUT /v1/private/{tenant_slug}/attendance`
- `GET /v1/private/{tenant_slug}/admin/summary`
- `GET|POST /v1/private/{tenant_slug}/admin/students`
- `PUT /v1/private/{tenant_slug}/admin/students/{student_id}`
- `GET|POST /v1/private/{tenant_slug}/admin/staff`
- `PUT /v1/private/{tenant_slug}/admin/staff/{staff_id}`
- `DELETE /v1/private/{tenant_slug}/admin/staff/{staff_id}` (soft delete / hide)
- `GET|POST /v1/private/{tenant_slug}/admin/records?module={module}`
- `PUT /v1/private/{tenant_slug}/admin/records/{record_id}`
- `GET|POST /v1/private/{tenant_slug}/admin/content`
- `PUT /v1/private/{tenant_slug}/admin/content/{content_id}`
- `DELETE /v1/private/{tenant_slug}/admin/content/{content_id}` (archive)
- `GET|POST /v1/private/{tenant_slug}/admin/page-blocks`
- `PUT|DELETE /v1/private/{tenant_slug}/admin/page-blocks/{block_id}`
- `GET /v1/private/{tenant_slug}/admin/export`
- `POST /v1/private/{tenant_slug}/admin/restore` (global admin only, explicit `RESTORE` confirmation)

The attendance write payload accepts a class, date, and one or more student records with `pending`, `present`, `excused`, `sick`, `absent`, or `late` status. A closed session cannot be changed. Learning resources are scoped to an institution or class and support `material`, `assignment`, and `announcement`. Students or guardians can create one submission per assignment with a private Storage path and/or note. Teachers can list submissions and mark them `reviewed` or `returned` with an optional score and feedback. Migration `006` creates the private `learning-submissions` bucket and restricts object paths to the tenant, student, and resource scope.

The tables live in the `darussolah` schema and the API is the only application data plane. Migration `009` revokes direct table privileges from browser roles; do not expose the schema to frontend Supabase REST clients. Supabase Auth and the narrowly scoped Storage policies remain browser-facing. Migration `010` adds reversible page blocks for editable layout and seeds safe foundation/institution section keys without fabricating testimonials.
