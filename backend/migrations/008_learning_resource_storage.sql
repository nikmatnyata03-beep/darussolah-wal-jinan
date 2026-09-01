-- Private Supabase Storage for teacher materials and assignments.
-- Run after 007_admin_operations.sql in Supabase.

BEGIN;

INSERT INTO storage.buckets (id, name, public)
VALUES ('learning-resources', 'learning-resources', false)
ON CONFLICT (id) DO UPDATE SET public = false;

CREATE OR REPLACE FUNCTION darussolah.user_can_manage_learning_resource(
  target_tenant uuid, target_class uuid
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM darussolah.classes c
    WHERE c.id = target_class
      AND c.tenant_id = target_tenant
      AND (
        darussolah.has_tenant_role(target_tenant, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin'])
        OR darussolah.has_institution_access(target_tenant, c.institution_id)
        OR EXISTS (
          SELECT 1
          FROM darussolah.class_teachers ct
          JOIN darussolah.teacher_profiles tp ON tp.id = ct.teacher_id
          WHERE ct.class_id = c.id
            AND ct.tenant_id = target_tenant
            AND tp.user_id = auth.uid()
        )
      )
  );
$$;

CREATE OR REPLACE FUNCTION darussolah.user_can_view_learning_resource(
  target_tenant uuid, target_class uuid, target_path text
)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = darussolah, public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM darussolah.learning_resources r
    WHERE r.tenant_id = target_tenant
      AND r.class_id = target_class
      AND r.file_path = target_path
      AND r.status <> 'archived'
      AND (
        darussolah.has_tenant_role(target_tenant, ARRAY['super_admin', 'yayasan_admin', 'lembaga_admin'])
        OR darussolah.has_institution_access(target_tenant, r.institution_id)
        OR EXISTS (
          SELECT 1
          FROM darussolah.class_teachers ct
          JOIN darussolah.teacher_profiles tp ON tp.id = ct.teacher_id
          WHERE ct.class_id = r.class_id
            AND ct.tenant_id = target_tenant
            AND tp.user_id = auth.uid()
        )
        OR EXISTS (
          SELECT 1
          FROM darussolah.enrollments e
          WHERE e.tenant_id = target_tenant
            AND e.institution_id = r.institution_id
            AND e.class_id = r.class_id
            AND e.status = 'active'
            AND (
              darussolah.user_has_student(e.student_id, target_tenant)
              OR darussolah.user_is_student(e.student_id, target_tenant)
            )
        )
      )
  );
$$;

DROP POLICY IF EXISTS learning_resource_objects_insert ON storage.objects;
CREATE POLICY learning_resource_objects_insert ON storage.objects
  FOR INSERT TO authenticated WITH CHECK (
    bucket_id = 'learning-resources'
    AND array_length(storage.foldername(name), 1) >= 3
    AND (storage.foldername(name))[1] = 'resources'
    AND CASE WHEN name ~ '^resources/[0-9a-fA-F-]{36}/[0-9a-fA-F-]{36}/[^/]+$'
      THEN darussolah.user_can_manage_learning_resource(
        ((storage.foldername(name))[2])::uuid,
        ((storage.foldername(name))[3])::uuid
      )
      ELSE false
    END
  );

DROP POLICY IF EXISTS learning_resource_objects_select ON storage.objects;
CREATE POLICY learning_resource_objects_select ON storage.objects
  FOR SELECT TO authenticated USING (
    bucket_id = 'learning-resources'
    AND array_length(storage.foldername(name), 1) >= 3
    AND (storage.foldername(name))[1] = 'resources'
    AND CASE WHEN name ~ '^resources/[0-9a-fA-F-]{36}/[0-9a-fA-F-]{36}/[^/]+$'
      THEN darussolah.user_can_view_learning_resource(
        ((storage.foldername(name))[2])::uuid,
        ((storage.foldername(name))[3])::uuid,
        name
      )
      ELSE false
    END
  );

DROP POLICY IF EXISTS learning_resource_objects_delete ON storage.objects;
CREATE POLICY learning_resource_objects_delete ON storage.objects
  FOR DELETE TO authenticated USING (
    bucket_id = 'learning-resources'
    AND name ~ '^resources/[0-9a-fA-F-]{36}/[0-9a-fA-F-]{36}/[^/]+$'
    AND darussolah.user_can_manage_learning_resource(
      ((storage.foldername(name))[2])::uuid,
      ((storage.foldername(name))[3])::uuid
    )
  );

GRANT EXECUTE ON FUNCTION darussolah.user_can_manage_learning_resource(uuid, uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION darussolah.user_can_view_learning_resource(uuid, uuid, text) TO authenticated;

COMMIT;
