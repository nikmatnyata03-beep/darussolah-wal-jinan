# Backup and Restore

The scheduled workflow creates one private, encrypted-at-rest archive containing:

- a PostgreSQL custom-format dump;
- every object in the configured Supabase Storage bucket;
- SHA-256 checksums for the dump and every downloaded object.

The PostgreSQL dump includes page layout blocks, published/draft content,
testimonial slider entries, teacher biographies, and their ordering/status.
The admin CMS export additionally produces a portable JSON snapshot containing
those records for a targeted restore without replacing the whole database.

## Required GitHub secrets

`SUPABASE_DB_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `BACKUP_S3_URI`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION` are required. Set either `SUPABASE_STORAGE_BUCKET` for one bucket or `SUPABASE_STORAGE_BUCKETS` for a comma-separated list such as `learning-submissions,learning-resources,site-media`. Set `AWS_ENDPOINT_URL` only when using an S3-compatible provider such as Backblaze B2.

The destination bucket must be private and should have a lifecycle policy retaining daily backups for 30 days and monthly backups for 12 months. Never print or commit the service-role key.

## Restore drill

1. Download an archive into an isolated temporary directory.
2. Verify the archive checksum and the `checksums.txt` entries.
3. Restore the database into a new empty Supabase project or PostgreSQL database with `pg_restore --clean --if-exists --no-owner --dbname="$TARGET_DATABASE_URL" database.dump`.
4. Upload the files under `storage/` back to the configured private Storage bucket using the Supabase Storage dashboard or API.
5. Run the backend health check and submit one test registration, then remove the temporary project.

## CMS snapshot restore

The CMS can restore a JSON file downloaded from `GET /v1/private/{tenant_slug}/admin/export` through `POST /v1/private/{tenant_slug}/admin/restore`. The request must include `confirmation: "RESTORE"`, the tenant must match, and only `super_admin` or `yayasan_admin` may run it. Restore is an audited merge: it updates matching content, page blocks, teacher biographies, and admin records without deleting unrelated operational rows. Archived content and hidden biographies remain restorable.

Run a restore drill at least once per quarter. A backup is not considered reliable until a restore has been verified.
