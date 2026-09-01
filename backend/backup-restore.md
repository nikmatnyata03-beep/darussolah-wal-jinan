# Backup and Restore

The scheduled workflow creates one private, encrypted-at-rest archive containing:

- a PostgreSQL custom-format dump;
- every object in the configured Supabase Storage bucket;
- SHA-256 checksums for the dump and every downloaded object.

## Required GitHub secrets

`SUPABASE_DB_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`, `BACKUP_S3_URI`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_DEFAULT_REGION` are required. Set `AWS_ENDPOINT_URL` only when using an S3-compatible provider such as Backblaze B2.

The destination bucket must be private and should have a lifecycle policy retaining daily backups for 30 days and monthly backups for 12 months. Never print or commit the service-role key.

## Restore drill

1. Download an archive into an isolated temporary directory.
2. Verify the archive checksum and the `checksums.txt` entries.
3. Restore the database into a new empty Supabase project or PostgreSQL database with `pg_restore --clean --if-exists --no-owner --dbname="$TARGET_DATABASE_URL" database.dump`.
4. Upload the files under `storage/` back to the configured private Storage bucket using the Supabase Storage dashboard or API.
5. Run the backend health check and submit one test registration, then remove the temporary project.

Run a restore drill at least once per quarter. A backup is not considered reliable until a restore has been verified.
