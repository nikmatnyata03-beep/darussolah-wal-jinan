-- Private Supabase Storage for assignment submissions.
-- Run after 005_learning_submissions.sql in Supabase.

BEGIN;

INSERT INTO storage.buckets (id, name, public)
VALUES ('learning-submissions', 'learning-submissions', false)
ON CONFLICT (id) DO UPDATE SET public = false;

CREATE OR REPLACE FUNCTION darussolah.user_can_view_learning_submission(
  target_tenant uuid, target_resource uuid, target_student uuid
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM darussolah.learning_submissions ls
    JOIN darussolah.learning_resources r ON r.id = ls.resource_id
    WHERE ls.tenant_id = target_tenant AND ls.resource_id = target_resource
      AND ls.student_id = target_student AND r.status <> 'archived'
      AND (
        darussolah.has_tenant_role(target_tenant, ARRAY['super_admin', 'yayasan_admin'])
        OR darussolah.has_institution_access(target_tenant, r.institution_id)
        OR EXISTS (
          SELECT 1
          FROM darussolah.class_teachers ct
          JOIN darussolah.teacher_profiles tp ON tp.id = ct.teacher_id
          WHERE ct.class_id = r.class_id AND ct.tenant_id = target_tenant
            AND tp.user_id = auth.uid()
        )
        OR darussolah.user_has_student(target_student, target_tenant)
        OR darussolah.user_is_student(target_student, target_tenant)
      )
  );
$$;

DROP POLICY IF EXISTS learning_submission_objects_insert ON storage.objects;
CREATE POLICY learning_submission_objects_insert ON storage.objects
  FOR INSERT TO authenticated WITH CHECK (
    bucket_id = 'learning-submissions'
    AND array_length(storage.foldername(name), 1) >= 4
    AND (storage.foldername(name))[1] = 'submissions'
    AND CASE WHEN name ~ '^submissions/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[^/]+$'
      THEN darussolah.user_can_submit_learning_resource(
        ((storage.foldername(name))[2])::uuid,
        ((storage.foldername(name))[4])::uuid,
        ((storage.foldername(name))[3])::uuid
      )
      ELSE false
    END
  );

DROP POLICY IF EXISTS learning_submission_objects_select ON storage.objects;
CREATE POLICY learning_submission_objects_select ON storage.objects
  FOR SELECT TO authenticated USING (
    bucket_id = 'learning-submissions'
    AND array_length(storage.foldername(name), 1) >= 4
    AND (storage.foldername(name))[1] = 'submissions'
    AND CASE WHEN name ~ '^submissions/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}/[^/]+$'
      THEN darussolah.user_can_view_learning_submission(
        ((storage.foldername(name))[2])::uuid,
        ((storage.foldername(name))[4])::uuid,
        ((storage.foldername(name))[3])::uuid
      )
      ELSE false
    END
  );

GRANT EXECUTE ON FUNCTION darussolah.user_can_view_learning_submission(uuid, uuid, uuid)
  TO authenticated;

COMMIT;
