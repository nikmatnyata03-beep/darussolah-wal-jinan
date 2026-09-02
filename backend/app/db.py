"""Tenant-filtered asyncpg repository for the foundation website."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
import json
from typing import Any
from uuid import UUID


class DatabaseUnavailable(RuntimeError):
    pass


class NotFoundError(LookupError):
    pass


class ConflictError(RuntimeError):
    pass


class PermissionDeniedError(RuntimeError):
    pass


def _uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


class FoundationStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.pool: Any = None

    async def connect(self) -> None:
        try:
            import asyncpg
        except ImportError as exc:
            raise DatabaseUnavailable("asyncpg is required for PostgreSQL runtime") from exc
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=10,
            command_timeout=10,
            statement_cache_size=0,
            max_inactive_connection_lifetime=300,
            server_settings={"search_path": "darussolah,public"},
        )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def _pool(self) -> Any:
        if self.pool is None:
            raise DatabaseUnavailable("database pool is not connected")
        return self.pool

    @asynccontextmanager
    async def _tenant_connection(self, tenant_id: str):
        async with self._pool().acquire() as connection:
            async with connection.transaction():
                await connection.execute(
                    "SELECT set_config('app.tenant_id', $1, true)",
                    str(_uuid(tenant_id)),
                )
                yield connection

    async def ready(self) -> bool:
        async with self._pool().acquire() as connection:
            return (await connection.fetchval("SELECT 1")) == 1

    async def fetch_tenant_by_slug(self, slug: str) -> dict[str, Any]:
        async with self._pool().acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT id::text AS id, slug, name, status
                FROM tenants
                WHERE slug = $1 AND status = 'active'
                """,
                slug,
            )
        if row is None:
            raise NotFoundError("foundation not found")
        return dict(row)

    async def fetch_portal_context(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            profile = await connection.fetchrow(
                """
                SELECT id::text AS id, tenant_id::text AS tenant_id, full_name, phone, status
                FROM user_profiles
                WHERE id = $1 AND tenant_id = $2 AND status = 'active'
                """,
                _uuid(user_id), _uuid(tenant_id),
            )
            roles = await connection.fetch(
                "SELECT role FROM user_roles WHERE user_id = $1 AND tenant_id = $2 ORDER BY role",
                _uuid(user_id), _uuid(tenant_id),
            )
            memberships = await connection.fetch(
                """
                SELECT im.institution_id::text AS institution_id, i.code, i.name,
                       im.membership_role AS role
                FROM institution_memberships im
                JOIN institutions i ON i.id = im.institution_id
                WHERE im.user_id = $1 AND im.tenant_id = $2 AND i.status = 'active'
                ORDER BY i.code, im.membership_role
                """,
                _uuid(user_id), _uuid(tenant_id),
            )
        if profile is None:
            raise NotFoundError("portal profile not found")
        return {
            "profile": dict(profile),
            "roles": [row["role"] for row in roles],
            "memberships": [dict(row) for row in memberships],
        }

    async def list_portal_students(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            rows = await connection.fetch(
                """
                SELECT DISTINCT s.id::text AS id, s.tenant_id::text AS tenant_id,
                       s.user_id::text AS user_id, s.nis, s.full_name,
                       enrollment.class_id::text AS class_id, enrollment.class_name,
                       enrollment.institution_id::text AS institution_id,
                       enrollment.institution_code, enrollment.institution_name,
                       s.birth_place, s.birth_date, s.gender, s.address,
                       s.status, s.photo_url
                FROM students s
                LEFT JOIN LATERAL (
                  SELECT e.class_id, c.name AS class_name, e.institution_id,
                         i.code AS institution_code, i.name AS institution_name
                  FROM enrollments e
                  JOIN institutions i ON i.id = e.institution_id
                  LEFT JOIN classes c ON c.id = e.class_id
                  WHERE e.student_id = s.id AND e.tenant_id = s.tenant_id AND e.status = 'active'
                  ORDER BY e.created_at DESC LIMIT 1
                ) enrollment ON true
                WHERE s.tenant_id = $1 AND (
                  s.user_id = $2
                  OR EXISTS (
                    SELECT 1 FROM user_roles ur
                    WHERE ur.user_id = $2 AND ur.tenant_id = $1
                      AND ur.role IN ('super_admin', 'yayasan_admin')
                  )
                  OR EXISTS (
                    SELECT 1
                    FROM guardian_students gs
                    JOIN guardians g ON g.id = gs.guardian_id
                    WHERE gs.student_id = s.id AND gs.tenant_id = $1 AND g.user_id = $2
                  )
                  OR EXISTS (
                    SELECT 1
                    FROM enrollments e
                    JOIN institution_memberships im
                      ON im.institution_id = e.institution_id AND im.tenant_id = e.tenant_id
                    WHERE e.student_id = s.id AND e.tenant_id = $1
                      AND im.user_id = $2
                  )
                  OR EXISTS (
                    SELECT 1
                    FROM enrollments e
                    JOIN class_teachers ct
                      ON ct.class_id = e.class_id AND ct.tenant_id = e.tenant_id
                    JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                    WHERE e.student_id = s.id AND e.tenant_id = $1
                      AND e.status = 'active' AND tp.user_id = $2
                  )
                )
                ORDER BY s.full_name
                """,
                _uuid(tenant_id), _uuid(user_id),
            )
        return [dict(row) for row in rows]

    async def list_portal_classes(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            rows = await connection.fetch(
                """
                SELECT c.id::text AS id, c.tenant_id::text AS tenant_id,
                       c.institution_id::text AS institution_id, i.code AS institution_code, i.name AS institution_name,
                       c.program_id::text AS program_id, p.name AS program_name,
                       c.academic_year_id::text AS academic_year_id, ay.name AS academic_year,
                       c.code, c.name, c.capacity, c.status
                FROM classes c
                JOIN institutions i ON i.id = c.institution_id
                JOIN programs p ON p.id = c.program_id
                JOIN academic_years ay ON ay.id = c.academic_year_id
                WHERE c.tenant_id = $1 AND (
                  EXISTS (
                    SELECT 1 FROM user_roles ur
                    WHERE ur.user_id = $2 AND ur.tenant_id = $1
                      AND ur.role IN ('super_admin', 'yayasan_admin')
                  )
                  OR EXISTS (
                    SELECT 1 FROM institution_memberships im
                    WHERE im.user_id = $2 AND im.tenant_id = $1
                      AND im.institution_id = c.institution_id
                  )
                  OR EXISTS (
                    SELECT 1 FROM class_teachers ct
                    JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                    WHERE ct.class_id = c.id AND tp.user_id = $2
                  )
                )
                ORDER BY i.code, c.name
                """,
                _uuid(tenant_id), _uuid(user_id),
            )
        return [dict(row) for row in rows]

    async def _class_for_user(self, connection: Any, tenant_id: str, user_id: str, class_id: str) -> dict[str, Any]:
        row = await connection.fetchrow(
            """
            SELECT c.id::text AS id, c.tenant_id::text AS tenant_id,
                   c.institution_id::text AS institution_id, i.code AS institution_code,
                   i.name AS institution_name, c.code, c.name, c.status
            FROM classes c
            JOIN institutions i ON i.id = c.institution_id
            WHERE c.id = $3 AND c.tenant_id = $1 AND c.status = 'active'
              AND (
                EXISTS (
                  SELECT 1 FROM user_roles ur
                  WHERE ur.user_id = $2 AND ur.tenant_id = $1
                    AND ur.role IN ('super_admin', 'yayasan_admin')
                )
                OR EXISTS (
                  SELECT 1 FROM institution_memberships im
                  WHERE im.user_id = $2 AND im.tenant_id = $1
                    AND im.institution_id = c.institution_id
                )
                OR EXISTS (
                  SELECT 1
                  FROM class_teachers ct
                  JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                  WHERE ct.class_id = c.id AND ct.tenant_id = $1 AND tp.user_id = $2
                )
              )
            """,
            _uuid(tenant_id), _uuid(user_id), _uuid(class_id),
        )
        if row is None:
            raise NotFoundError("class not found or not accessible")
        return dict(row)

    async def list_learning_resources(
        self,
        tenant_id: str,
        user_id: str,
        *,
        class_id: str | None = None,
        resource_type: str | None = None,
    ) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            rows = await connection.fetch(
                """
                SELECT r.id::text AS id, r.tenant_id::text AS tenant_id,
                       r.institution_id::text AS institution_id,
                       r.class_id::text AS class_id, i.code AS institution_code,
                       i.name AS institution_name, c.name AS class_name,
                       r.resource_type, r.title, r.subject, r.description,
                       r.file_path, r.due_date, r.status, r.published_at,
                       r.created_at, r.updated_at,
                       creator.full_name AS created_by_name
                FROM learning_resources r
                JOIN institutions i ON i.id = r.institution_id
                LEFT JOIN classes c ON c.id = r.class_id
                LEFT JOIN user_profiles creator ON creator.id = r.created_by
                WHERE r.tenant_id = $1
                  AND r.status <> 'archived'
                  AND ($3::uuid IS NULL OR r.class_id = $3)
                  AND ($4::text IS NULL OR r.resource_type = $4)
                  AND (
                    EXISTS (
                      SELECT 1 FROM user_roles ur
                      WHERE ur.user_id = $2 AND ur.tenant_id = $1
                        AND ur.role IN ('super_admin', 'yayasan_admin')
                    )
                    OR EXISTS (
                      SELECT 1 FROM institution_memberships im
                      WHERE im.user_id = $2 AND im.tenant_id = $1
                        AND im.institution_id = r.institution_id
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM class_teachers ct
                      JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                      WHERE ct.class_id = r.class_id AND ct.tenant_id = $1
                        AND tp.user_id = $2
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM enrollments e
                      WHERE e.tenant_id = $1 AND e.institution_id = r.institution_id
                        AND e.status = 'active'
                        AND (e.class_id = r.class_id OR r.class_id IS NULL)
                        AND (
                          EXISTS (
                            SELECT 1 FROM guardian_students gs
                            JOIN guardians g ON g.id = gs.guardian_id
                            WHERE gs.student_id = e.student_id AND gs.tenant_id = $1
                              AND g.user_id = $2
                          )
                          OR EXISTS (
                            SELECT 1 FROM students s
                            WHERE s.id = e.student_id AND s.user_id = $2
                          )
                        )
                    )
                  )
                  AND (
                    r.status = 'published'
                    OR EXISTS (
                      SELECT 1 FROM user_roles ur
                      WHERE ur.user_id = $2 AND ur.tenant_id = $1
                        AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'guru')
                    )
                  )
                ORDER BY COALESCE(r.published_at, r.created_at) DESC, r.title
                """,
                _uuid(tenant_id), _uuid(user_id), _uuid(class_id) if class_id else None, resource_type,
            )
        return [dict(row) for row in rows]

    async def create_learning_resource(self, tenant_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        institution_id = _uuid(data["institution_id"]) if data.get("institution_id") else None
        class_id = _uuid(data["class_id"]) if data.get("class_id") else None
        async with self._tenant_connection(tenant_id) as connection:
            class_info = None
            if class_id is not None:
                class_info = await self._class_for_user(connection, tenant_id, user_id, str(class_id))
                if institution_id is not None and institution_id != _uuid(class_info["institution_id"]):
                    raise NotFoundError("class does not belong to institution")
                institution_id = _uuid(class_info["institution_id"])
            if institution_id is None:
                raise NotFoundError("institution is required when class is not selected")
            allowed = await connection.fetchval(
                """
                SELECT darussolah.has_institution_access($1, $2)
                    OR EXISTS (
                      SELECT 1
                      FROM class_teachers ct
                      JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                      WHERE ct.class_id = $3 AND ct.tenant_id = $1 AND tp.user_id = $4
                    )
                """,
                _uuid(tenant_id), institution_id, class_id, _uuid(user_id),
            )
            if not allowed:
                raise PermissionDeniedError("user cannot publish learning resources for this scope")
            resource_id = await connection.fetchval(
                """
                INSERT INTO learning_resources (
                  tenant_id, institution_id, class_id, resource_type, title,
                  subject, description, file_path, due_date, status, created_by,
                  published_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                        CASE WHEN $10 = 'published' THEN now() ELSE NULL END)
                RETURNING id
                """,
                _uuid(tenant_id), institution_id, class_id, data["resource_type"],
                data["title"], data.get("subject"), data.get("description"),
                data.get("file_path"), data.get("due_date"), data["status"], _uuid(user_id),
            )
            row = await connection.fetchrow(
                """
                SELECT r.id::text AS id, r.tenant_id::text AS tenant_id,
                       r.institution_id::text AS institution_id,
                       r.class_id::text AS class_id, i.code AS institution_code,
                       i.name AS institution_name, c.name AS class_name,
                       r.resource_type, r.title, r.subject, r.description,
                       r.file_path, r.due_date, r.status, r.published_at,
                       r.created_at, r.updated_at,
                       creator.full_name AS created_by_name
                FROM learning_resources r
                JOIN institutions i ON i.id = r.institution_id
                LEFT JOIN classes c ON c.id = r.class_id
                LEFT JOIN user_profiles creator ON creator.id = r.created_by
                WHERE r.id = $1 AND r.tenant_id = $2
                """,
                resource_id, _uuid(tenant_id),
            )
        if row is None:
            raise NotFoundError("learning resource was not created")
        return dict(row)

    async def list_learning_submissions(
        self,
        tenant_id: str,
        user_id: str,
        *,
        class_id: str | None = None,
        resource_id: str | None = None,
        submission_status: str | None = None,
    ) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            rows = await connection.fetch(
                """
                SELECT ls.id::text AS id, ls.tenant_id::text AS tenant_id,
                       ls.resource_id::text AS resource_id,
                       ls.student_id::text AS student_id,
                       r.institution_id::text AS institution_id,
                       r.class_id::text AS class_id, r.title AS resource_title,
                       r.resource_type, c.name AS class_name,
                       s.nis AS student_nis, s.full_name AS student_name,
                       ls.file_path, ls.note, ls.status, ls.score, ls.feedback,
                       ls.submitted_at, ls.reviewed_at,
                       reviewer.full_name AS reviewer_name
                FROM learning_submissions ls
                JOIN learning_resources r ON r.id = ls.resource_id
                JOIN students s ON s.id = ls.student_id
                LEFT JOIN classes c ON c.id = r.class_id
                LEFT JOIN user_profiles reviewer ON reviewer.id = ls.reviewed_by
                WHERE ls.tenant_id = $1 AND r.tenant_id = $1
                  AND r.status <> 'archived'
                  AND ($3::uuid IS NULL OR r.class_id = $3)
                  AND ($4::uuid IS NULL OR r.id = $4)
                  AND ($5::text IS NULL OR ls.status = $5)
                  AND (
                    EXISTS (
                      SELECT 1 FROM user_roles ur
                      WHERE ur.user_id = $2 AND ur.tenant_id = $1
                        AND ur.role IN ('super_admin', 'yayasan_admin')
                    )
                    OR EXISTS (
                      SELECT 1 FROM institution_memberships im
                      WHERE im.user_id = $2 AND im.tenant_id = $1
                        AND im.institution_id = r.institution_id
                    )
                    OR EXISTS (
                      SELECT 1
                     FROM class_teachers ct
                     JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                     WHERE ct.class_id = r.class_id AND ct.tenant_id = $1
                        AND tp.user_id = $2
                     )
                     OR EXISTS (
                       SELECT 1
                       FROM guardian_students gs
                       JOIN guardians g ON g.id = gs.guardian_id
                       WHERE gs.student_id = ls.student_id AND gs.tenant_id = $1
                         AND g.user_id = $2
                     )
                     OR darussolah.user_has_student(ls.student_id, $1)
                    OR EXISTS (
                      SELECT 1 FROM students own_student
                      WHERE own_student.id = ls.student_id AND own_student.user_id = $2
                    )
                  )
                  AND (
                    r.status = 'published'
                    OR EXISTS (
                      SELECT 1 FROM user_roles ur
                      WHERE ur.user_id = $2 AND ur.tenant_id = $1
                        AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'guru')
                    )
                  )
                ORDER BY ls.submitted_at DESC, s.full_name
                """,
                _uuid(tenant_id), _uuid(user_id), _uuid(class_id) if class_id else None,
                _uuid(resource_id) if resource_id else None, submission_status,
            )
        return [dict(row) for row in rows]

    async def create_learning_submission(self, tenant_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        resource_id = _uuid(data["resource_id"])
        student_id = _uuid(data["student_id"])
        file_path = data.get("file_path")
        expected_prefix = f"submissions/{_uuid(tenant_id)}/{student_id}/{resource_id}/"
        if file_path and not file_path.startswith(expected_prefix):
            raise PermissionDeniedError("submission file path is outside the student resource scope")
        try:
            import asyncpg
        except ImportError as exc:
            raise DatabaseUnavailable("asyncpg is required for PostgreSQL runtime") from exc
        async with self._tenant_connection(tenant_id) as connection:
            resource = await connection.fetchrow(
                """
                SELECT r.id, r.due_date
                FROM learning_resources r
                WHERE r.id = $1 AND r.tenant_id = $2
                  AND r.resource_type = 'assignment' AND r.status = 'published'
                  AND EXISTS (
                    SELECT 1
                    FROM enrollments e
                    WHERE e.tenant_id = $2 AND e.student_id = $3
                      AND e.institution_id = r.institution_id AND e.status = 'active'
                      AND (r.class_id IS NULL OR e.class_id = r.class_id)
                  )
                  AND (
                    EXISTS (
                      SELECT 1 FROM students s
                      WHERE s.id = $3 AND s.tenant_id = $2 AND s.user_id = $4
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM guardian_students gs
                      JOIN guardians g ON g.id = gs.guardian_id
                      WHERE gs.student_id = $3 AND gs.tenant_id = $2 AND g.user_id = $4
                    )
                  )
                """,
                resource_id, _uuid(tenant_id), student_id, _uuid(user_id),
            )
            if resource is None:
                raise NotFoundError("assignment not found or student is not allowed to submit")
            submission_status = "late" if resource["due_date"] and resource["due_date"] < date.today() else "submitted"
            try:
                submission_id = await connection.fetchval(
                    """
                    INSERT INTO learning_submissions (
                      tenant_id, resource_id, student_id, file_path, note, status
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    _uuid(tenant_id), resource_id, student_id, file_path, data.get("note"), submission_status,
                )
            except asyncpg.UniqueViolationError as exc:
                raise ConflictError("student has already submitted this assignment") from exc
        submissions = await self.list_learning_submissions(
            tenant_id, user_id, resource_id=str(resource_id)
        )
        for submission in submissions:
            if submission["id"] == str(submission_id):
                return submission
        raise NotFoundError("learning submission was not returned after creation")

    async def review_learning_submission(
        self,
        tenant_id: str,
        user_id: str,
        submission_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        submission_uuid = _uuid(submission_id)
        async with self._tenant_connection(tenant_id) as connection:
            scope = await connection.fetchrow(
                """
                SELECT ls.resource_id, r.institution_id, r.class_id
                FROM learning_submissions ls
                JOIN learning_resources r ON r.id = ls.resource_id
                WHERE ls.id = $1 AND ls.tenant_id = $2 AND r.status <> 'archived'
                """,
                submission_uuid, _uuid(tenant_id),
            )
            if scope is None:
                raise NotFoundError("learning submission not found")
            allowed = await connection.fetchval(
                """
                SELECT EXISTS (
                        SELECT 1 FROM user_roles ur
                        WHERE ur.user_id = $4 AND ur.tenant_id = $1
                          AND ur.role IN ('super_admin', 'yayasan_admin')
                    )
                    OR EXISTS (
                        SELECT 1 FROM institution_memberships im
                        WHERE im.user_id = $4 AND im.tenant_id = $1
                          AND im.institution_id = $2
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM class_teachers ct
                      JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                      WHERE ct.class_id = $3 AND ct.tenant_id = $1 AND tp.user_id = $4
                    )
                """,
                _uuid(tenant_id), scope["institution_id"], scope["class_id"], _uuid(user_id),
            )
            if not allowed:
                raise PermissionDeniedError("user cannot review submissions for this scope")
            await connection.execute(
                """
                UPDATE learning_submissions
                SET status = $2, score = $3, feedback = $4,
                    reviewed_by = $5, reviewed_at = now(), updated_at = now()
                WHERE id = $1 AND tenant_id = $6
                """,
                submission_uuid, data["status"], data.get("score"), data.get("feedback"),
                _uuid(user_id), _uuid(tenant_id),
            )
        submissions = await self.list_learning_submissions(
            tenant_id, user_id, resource_id=str(scope["resource_id"])
        )
        for submission in submissions:
            if submission["id"] == str(submission_uuid):
                return submission
        raise NotFoundError("learning submission was not returned after review")

    async def fetch_attendance(self, tenant_id: str, user_id: str, class_id: str, attendance_date: date) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            class_info = await self._class_for_user(connection, tenant_id, user_id, class_id)
            session = await connection.fetchrow(
                """
                SELECT id::text AS id, tenant_id::text AS tenant_id,
                       institution_id::text AS institution_id, class_id::text AS class_id,
                       attendance_date, status, opened_at, closed_at
                FROM attendance_sessions
                WHERE tenant_id = $1 AND class_id = $2 AND attendance_date = $3
                """,
                _uuid(tenant_id), _uuid(class_id), attendance_date,
            )
            students = await connection.fetch(
                """
                SELECT DISTINCT s.id::text AS id, s.nis, s.full_name, s.status
                FROM students s
                JOIN enrollments e ON e.student_id = s.id AND e.tenant_id = s.tenant_id
                WHERE s.tenant_id = $1 AND e.class_id = $2 AND e.status = 'active'
                ORDER BY s.full_name
                """,
                _uuid(tenant_id), _uuid(class_id),
            )
            records = []
            if session is not None:
                records = await connection.fetch(
                    """
                    SELECT ar.id::text AS id, ar.student_id::text AS student_id,
                           s.nis, s.full_name, ar.status, ar.note,
                           ar.recorded_at, ar.updated_at
                    FROM attendance_records ar
                    JOIN students s ON s.id = ar.student_id
                    WHERE ar.tenant_id = $1 AND ar.session_id = $2
                    ORDER BY s.full_name
                    """,
                    _uuid(tenant_id), session["id"],
                )
        return {
            "class": class_info,
            "students": [dict(row) for row in students],
            "session": dict(session) if session is not None else None,
            "records": [dict(row) for row in records],
        }

    async def save_attendance(self, tenant_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            import asyncpg
        except ImportError as exc:
            raise DatabaseUnavailable("asyncpg is required for PostgreSQL runtime") from exc
        class_id = _uuid(data["class_id"])
        attendance_date = data["attendance_date"]
        records = data["records"]
        student_ids = [_uuid(record["student_id"]) for record in records]
        async with self._tenant_connection(tenant_id) as connection:
            class_info = await self._class_for_user(connection, tenant_id, user_id, str(class_id))
            existing = await connection.fetchrow(
                """
                SELECT id, status
                FROM attendance_sessions
                WHERE tenant_id = $1 AND class_id = $2 AND attendance_date = $3
                """,
                _uuid(tenant_id), class_id, attendance_date,
            )
            if existing is not None and existing["status"] == "closed":
                raise ConflictError("attendance session is closed")
            enrolled = await connection.fetch(
                """
                SELECT DISTINCT s.id
                FROM students s
                JOIN enrollments e ON e.student_id = s.id AND e.tenant_id = s.tenant_id
                WHERE s.tenant_id = $1 AND e.class_id = $2 AND e.status = 'active'
                  AND s.id = ANY($3::uuid[])
                """,
                _uuid(tenant_id), class_id, student_ids,
            )
            enrolled_ids = {row["id"] for row in enrolled}
            if enrolled_ids != set(student_ids):
                raise NotFoundError("one or more students are not enrolled in class")
            if existing is None:
                session_id = await connection.fetchval(
                    """
                    INSERT INTO attendance_sessions (
                      tenant_id, institution_id, class_id, attendance_date,
                      status, opened_by, closed_by, closed_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, CASE WHEN $5 = 'closed' THEN now() ELSE NULL END)
                    RETURNING id
                    """,
                    _uuid(tenant_id), _uuid(class_info["institution_id"]), class_id,
                    attendance_date, "closed" if data["close_session"] else "open",
                    _uuid(user_id), _uuid(user_id) if data["close_session"] else None,
                )
            else:
                session_id = existing["id"]
                if data["close_session"]:
                    await connection.execute(
                        """
                        UPDATE attendance_sessions
                        SET status = 'closed', closed_by = $2, closed_at = now()
                        WHERE id = $1 AND tenant_id = $3
                        """,
                        session_id, _uuid(user_id), _uuid(tenant_id),
                    )
                else:
                    await connection.execute(
                        "UPDATE attendance_sessions SET updated_at = now() WHERE id = $1 AND tenant_id = $2",
                        session_id, _uuid(tenant_id),
                    )
            await connection.executemany(
                """
                INSERT INTO attendance_records (
                  tenant_id, session_id, student_id, status, note, recorded_at, recorded_by
                )
                VALUES ($1, $2, $3, $4, $5, CASE WHEN $4 IN ('present', 'late') THEN now() ELSE NULL END, $6)
                ON CONFLICT (session_id, student_id) DO UPDATE SET
                  status = EXCLUDED.status,
                  note = EXCLUDED.note,
                  recorded_at = EXCLUDED.recorded_at,
                  recorded_by = EXCLUDED.recorded_by,
                  updated_at = now()
                """,
                [
                    (_uuid(tenant_id), session_id, _uuid(record["student_id"]),
                     record["status"], record.get("note"), _uuid(user_id))
                    for record in records
                ],
            )
        return await self.fetch_attendance(tenant_id, user_id, str(class_id), attendance_date)

    async def _require_roles(self, connection: Any, tenant_id: str, user_id: str, roles: tuple[str, ...]) -> None:
        allowed = await connection.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM user_roles
              WHERE tenant_id = $1 AND user_id = $2 AND role = ANY($3::text[])
            )
            """,
            _uuid(tenant_id), _uuid(user_id), list(roles),
        )
        if not allowed:
            raise PermissionDeniedError("user does not have access to this admin module")

    async def _require_record_access(
        self,
        connection: Any,
        tenant_id: str,
        user_id: str,
        module: str,
        entity_id: str | None = None,
        owner_id: str | None = None,
    ) -> None:
        roles = await connection.fetch(
            "SELECT role FROM user_roles WHERE tenant_id = $1 AND user_id = $2",
            _uuid(tenant_id), _uuid(user_id),
        )
        is_admin = any(row["role"] in {"super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran"} for row in roles)
        if is_admin:
            return
        if module not in {"grades", "tahfidz", "journals", "schedule"}:
            raise PermissionDeniedError("guru tidak memiliki akses ke modul ini")
        if module in {"journals", "schedule"} and owner_id and owner_id != user_id:
            raise PermissionDeniedError("guru tidak memiliki akses ke record milik pengguna lain")
        if module in {"grades", "tahfidz"}:
            if not entity_id:
                raise PermissionDeniedError("student scope is required for this module")
            allowed = await connection.fetchval(
                """
                SELECT EXISTS (
                  SELECT 1
                  FROM enrollments teacher_enrollment
                  JOIN class_teachers ct
                    ON ct.class_id = teacher_enrollment.class_id
                   AND ct.tenant_id = teacher_enrollment.tenant_id
                  JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                  WHERE teacher_enrollment.student_id = $1
                    AND teacher_enrollment.tenant_id = $2
                    AND teacher_enrollment.status = 'active'
                    AND tp.user_id = $3
                )
                """,
                _uuid(entity_id), _uuid(tenant_id), _uuid(user_id),
            )
            if not allowed:
                raise PermissionDeniedError("guru tidak memiliki akses ke student scope ini")

    async def fetch_admin_summary(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran", "guru",
            ))
            summary = await connection.fetchrow(
                """
                WITH accessible_students AS (
                  SELECT DISTINCT s.id
                  FROM students s
                  WHERE s.tenant_id = $1 AND (
                    EXISTS (
                      SELECT 1 FROM user_roles ur
                      WHERE ur.user_id = $2 AND ur.tenant_id = $1
                        AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM enrollments e
                      JOIN class_teachers ct
                        ON ct.class_id = e.class_id AND ct.tenant_id = e.tenant_id
                      JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                      WHERE e.student_id = s.id AND e.tenant_id = $1
                        AND e.status = 'active' AND tp.user_id = $2
                    )
                  )
                )
                SELECT
                  (SELECT count(*) FROM accessible_students) AS students_total,
                  (SELECT count(*) FROM accessible_students a JOIN students s ON s.id = a.id WHERE s.status = 'active') AS students_active,
                  (SELECT count(DISTINCT gs.guardian_id)
                   FROM guardian_students gs JOIN accessible_students a ON a.id = gs.student_id
                   WHERE gs.tenant_id = $1) AS guardians_total,
                  (SELECT count(*) FROM teacher_profiles tp
                   WHERE tp.tenant_id = $1 AND tp.status = 'active' AND (
                     EXISTS (
                       SELECT 1 FROM user_roles ur
                       WHERE ur.user_id = $2 AND ur.tenant_id = $1
                         AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                     ) OR tp.user_id = $2
                   )) AS teachers_active,
                  (SELECT count(*) FROM learning_resources r
                   WHERE r.tenant_id = $1 AND r.status <> 'archived' AND (
                     EXISTS (
                       SELECT 1 FROM user_roles ur
                       WHERE ur.user_id = $2 AND ur.tenant_id = $1
                         AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                     ) OR EXISTS (
                       SELECT 1 FROM institution_memberships im
                       WHERE im.user_id = $2 AND im.tenant_id = $1 AND im.institution_id = r.institution_id
                     ) OR EXISTS (
                       SELECT 1 FROM class_teachers ct
                       JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                       WHERE ct.class_id = r.class_id AND ct.tenant_id = $1 AND tp.user_id = $2
                     )
                   )) AS learning_total,
                  (SELECT count(*) FROM attendance_sessions a
                   WHERE a.tenant_id = $1 AND a.attendance_date = CURRENT_DATE AND (
                     EXISTS (
                       SELECT 1 FROM user_roles ur
                       WHERE ur.user_id = $2 AND ur.tenant_id = $1
                         AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                     ) OR EXISTS (
                       SELECT 1 FROM class_teachers ct
                       JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                       WHERE ct.class_id = a.class_id AND ct.tenant_id = $1 AND tp.user_id = $2
                     )
                   )) AS attendance_sessions_today,
                  (SELECT count(*) FROM registration_applications r
                   WHERE r.tenant_id = $1 AND r.status IN ('new', 'reviewing') AND EXISTS (
                     SELECT 1 FROM user_roles ur
                     WHERE ur.user_id = $2 AND ur.tenant_id = $1
                       AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                   )) AS registrations_pending
                """,
                _uuid(tenant_id), _uuid(user_id),
            )
            records = await connection.fetch(
                """
                SELECT module, count(*)::int AS total
                FROM admin_records
                WHERE tenant_id = $1 AND status = 'active'
                GROUP BY module
                ORDER BY module
                """,
                _uuid(tenant_id),
            )
            institutions = await connection.fetch(
                """
                WITH accessible_enrollments AS (
                  SELECT DISTINCT e.student_id, e.institution_id
                  FROM enrollments e
                  JOIN students s ON s.id = e.student_id AND s.tenant_id = e.tenant_id AND s.status = 'active'
                  WHERE e.tenant_id = $1 AND e.status = 'active' AND (
                    EXISTS (
                      SELECT 1 FROM user_roles ur
                      WHERE ur.user_id = $2 AND ur.tenant_id = $1
                        AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                    )
                    OR EXISTS (
                      SELECT 1 FROM institution_memberships im
                      WHERE im.user_id = $2 AND im.tenant_id = $1
                        AND im.institution_id = e.institution_id
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM class_teachers ct
                      JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                      WHERE ct.class_id = e.class_id AND ct.tenant_id = $1 AND tp.user_id = $2
                    )
                  )
                )
                SELECT i.id::text AS id, i.code, i.name,
                       count(a.student_id)::int AS active_students
                FROM institutions i
                LEFT JOIN accessible_enrollments a ON a.institution_id = i.id
                WHERE i.tenant_id = $1 AND i.status = 'active'
                GROUP BY i.id, i.code, i.name
                ORDER BY i.code
                """,
                _uuid(tenant_id), _uuid(user_id),
            )
            attendance_trend = await connection.fetch(
                """
                SELECT to_char(date_trunc('month', s.attendance_date), 'YYYY-MM') AS period,
                       count(*) FILTER (WHERE ar.status IN ('present', 'late'))::int AS attended,
                       count(*)::int AS total
                FROM attendance_sessions s
                JOIN attendance_records ar ON ar.session_id = s.id
                WHERE s.tenant_id = $1
                  AND s.attendance_date >= CURRENT_DATE - INTERVAL '5 months'
                  AND (
                    EXISTS (
                      SELECT 1 FROM user_roles ur
                      WHERE ur.user_id = $2 AND ur.tenant_id = $1
                        AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                    )
                    OR EXISTS (
                      SELECT 1 FROM institution_memberships im
                      WHERE im.user_id = $2 AND im.tenant_id = $1
                        AND im.institution_id = s.institution_id
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM class_teachers ct
                      JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                      WHERE ct.class_id = s.class_id AND ct.tenant_id = $1 AND tp.user_id = $2
                    )
                  )
                GROUP BY date_trunc('month', s.attendance_date)
                ORDER BY date_trunc('month', s.attendance_date)
                """,
                _uuid(tenant_id), _uuid(user_id),
            )
            registration_trend = await connection.fetch(
                """
                SELECT to_char(date_trunc('month', created_at), 'YYYY-MM') AS period,
                       count(*)::int AS total,
                       count(*) FILTER (WHERE status IN ('new', 'reviewing'))::int AS pending
                FROM registration_applications
                WHERE tenant_id = $1 AND EXISTS (
                  SELECT 1 FROM user_roles ur
                  WHERE ur.user_id = $2 AND ur.tenant_id = $1
                    AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                )
                GROUP BY date_trunc('month', created_at)
                ORDER BY date_trunc('month', created_at)
                """,
                _uuid(tenant_id), _uuid(user_id),
            )
            finance_trend = await connection.fetch(
                """
                SELECT to_char(date_trunc('month', updated_at), 'YYYY-MM') AS period,
                       COALESCE(sum(CASE WHEN payload->>'type' <> 'invoice'
                         AND (payload->>'amount') ~ '^[0-9]+(\\.[0-9]+)?$'
                         THEN (payload->>'amount')::numeric ELSE 0 END), 0) AS income,
                       COALESCE(sum(CASE WHEN payload->>'type' = 'invoice'
                         AND (payload->>'amount') ~ '^[0-9]+(\\.[0-9]+)?$'
                         THEN (payload->>'amount')::numeric ELSE 0 END), 0) AS billed
                FROM admin_records
                WHERE tenant_id = $1 AND module = 'finance' AND status = 'active'
                  AND EXISTS (
                    SELECT 1 FROM user_roles ur
                    WHERE ur.user_id = $2 AND ur.tenant_id = $1
                      AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                  )
                GROUP BY date_trunc('month', updated_at)
                ORDER BY date_trunc('month', updated_at)
                """,
                _uuid(tenant_id), _uuid(user_id),
            )
        return {
            **dict(summary),
            "modules": {row["module"]: row["total"] for row in records},
            "institution_breakdown": [dict(row) for row in institutions],
            "attendance_trend": [dict(row) for row in attendance_trend],
            "registration_trend": [dict(row) for row in registration_trend],
            "finance_trend": [dict(row) for row in finance_trend],
        }

    async def list_admin_students(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran", "guru",
            ))
            rows = await connection.fetch(
                """
                SELECT s.id::text AS id, s.tenant_id::text AS tenant_id, s.nis, s.full_name,
                       s.birth_place, s.birth_date, s.gender, s.address, s.status, s.photo_url,
                       enrollment.class_id::text AS class_id, enrollment.class_name,
                       enrollment.institution_id::text AS institution_id, enrollment.institution_name,
                       guardian.id::text AS guardian_id, guardian.full_name AS guardian_name,
                       guardian.phone AS guardian_phone, guardian.email AS guardian_email,
                       CASE WHEN guardian.id IS NULL THEN false ELSE true END AS guardian_connected
                FROM students s
                LEFT JOIN LATERAL (
                  SELECT e.class_id, c.name AS class_name, e.institution_id, i.name AS institution_name
                  FROM enrollments e
                  JOIN institutions i ON i.id = e.institution_id
                  LEFT JOIN classes c ON c.id = e.class_id
                  WHERE e.student_id = s.id AND e.tenant_id = s.tenant_id AND e.status = 'active'
                  ORDER BY e.created_at DESC LIMIT 1
                ) enrollment ON true
                LEFT JOIN LATERAL (
                  SELECT g.id, g.full_name, g.phone, g.email
                  FROM guardian_students gs
                  JOIN guardians g ON g.id = gs.guardian_id
                  WHERE gs.student_id = s.id AND gs.tenant_id = s.tenant_id
                  ORDER BY gs.is_primary DESC, g.created_at ASC LIMIT 1
                ) guardian ON true
                 WHERE s.tenant_id = $1
                   AND (
                     EXISTS (
                       SELECT 1 FROM user_roles ur
                       WHERE ur.user_id = $2 AND ur.tenant_id = $1
                         AND ur.role IN ('super_admin', 'yayasan_admin', 'lembaga_admin', 'operator_pendaftaran')
                     )
                     OR EXISTS (
                       SELECT 1
                       FROM enrollments teacher_enrollment
                       JOIN class_teachers ct
                         ON ct.class_id = teacher_enrollment.class_id
                        AND ct.tenant_id = teacher_enrollment.tenant_id
                       JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                       WHERE teacher_enrollment.student_id = s.id
                         AND teacher_enrollment.tenant_id = $1
                         AND teacher_enrollment.status = 'active'
                         AND tp.user_id = $2
                     )
                   )
                 ORDER BY s.full_name
                 """,
                 _uuid(tenant_id), _uuid(user_id),
             )
        return [dict(row) for row in rows]

    async def create_admin_student(self, tenant_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            institution_id = _uuid(data["institution_id"]) if data.get("institution_id") else await connection.fetchval(
                "SELECT id FROM institutions WHERE tenant_id = $1 AND status = 'active' ORDER BY code LIMIT 1",
                _uuid(tenant_id),
            )
            if institution_id is None:
                raise NotFoundError("no active institution is available")
            class_info = None
            if data.get("class_id"):
                class_info = await connection.fetchrow(
                    """
                    SELECT id, institution_id, program_id, academic_year_id
                    FROM classes
                    WHERE id = $1 AND tenant_id = $2 AND status = 'active'
                    """,
                    _uuid(data["class_id"]), _uuid(tenant_id),
                )
                if class_info is None:
                    raise NotFoundError("class not found")
                institution_id = class_info["institution_id"]
            student_id = await connection.fetchval(
                """
                INSERT INTO students (tenant_id, nis, full_name, birth_place, birth_date, gender, address, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                _uuid(tenant_id), data.get("nis"), data["full_name"], data.get("birth_place"),
                data.get("birth_date"), data.get("gender"), data.get("address"), data.get("status", "active"),
            )
            if class_info is not None:
                await connection.execute(
                    """
                    INSERT INTO enrollments (tenant_id, student_id, institution_id, program_id, class_id, academic_year_id, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'active')
                    ON CONFLICT (student_id, institution_id, academic_year_id) DO UPDATE
                      SET class_id = EXCLUDED.class_id, status = 'active', updated_at = now()
                    """,
                    _uuid(tenant_id), student_id, institution_id, class_info["program_id"],
                    class_info["id"], class_info["academic_year_id"],
                )
            if data.get("guardian_name"):
                guardian_id = await connection.fetchval(
                    """
                    INSERT INTO guardians (tenant_id, full_name, phone, email, relationship)
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    _uuid(tenant_id), data["guardian_name"], data.get("guardian_phone"),
                    data.get("guardian_email"), data.get("guardian_relationship", "guardian"),
                )
                await connection.execute(
                    """
                    INSERT INTO guardian_students (guardian_id, student_id, tenant_id, relationship, is_primary)
                    VALUES ($1, $2, $3, $4, true)
                    ON CONFLICT (guardian_id, student_id) DO UPDATE SET is_primary = true
                    """,
                    guardian_id, student_id, _uuid(tenant_id), data.get("guardian_relationship", "guardian"),
                )
            await connection.execute(
                """
                INSERT INTO audit_logs (tenant_id, actor_user_id, action, entity_type, entity_id, after_data)
                VALUES ($1, $2, 'create', 'student', $3, jsonb_build_object('full_name', $4, 'nis', $5))
                """,
                _uuid(tenant_id), _uuid(user_id), student_id, data["full_name"], data.get("nis"),
            )
        students = await self.list_admin_students(tenant_id, user_id)
        return next((student for student in students if student["id"] == str(student_id)), {})

    async def update_admin_student(self, tenant_id: str, user_id: str, student_id: str, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {key: data[key] for key in (
            "nis", "full_name", "birth_place", "birth_date", "gender", "address", "status", "photo_url",
        ) if key in data}
        if not allowed:
            raise ConflictError("no student fields supplied")
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            student_uuid = _uuid(student_id)
            exists = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM students WHERE id = $1 AND tenant_id = $2)",
                student_uuid, _uuid(tenant_id),
            )
            if not exists:
                raise NotFoundError("student not found")
            assignments = ", ".join(f"{column} = ${index + 2}" for index, column in enumerate(allowed))
            await connection.execute(
                f"UPDATE students SET {assignments}, updated_at = now() WHERE id = $1 AND tenant_id = ${len(allowed) + 2}",
                student_uuid, *allowed.values(), _uuid(tenant_id),
            )
        students = await self.list_admin_students(tenant_id, user_id)
        return next((student for student in students if student["id"] == str(student_uuid)), {})

    async def list_admin_staff(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            rows = await connection.fetch(
                """
                SELECT tp.id::text AS id, tp.user_id::text AS user_id, tp.institution_id::text AS institution_id,
                       i.name AS institution_name, tp.display_name, tp.role_title, tp.subject, tp.education,
                       tp.short_bio, tp.photo_url, tp.status, tp.employment_type, tp.weekly_hours,
                       COALESCE(string_agg(DISTINCT c.name, ', ' ORDER BY c.name), '') AS classes
                FROM teacher_profiles tp
                JOIN institutions i ON i.id = tp.institution_id
                LEFT JOIN class_teachers ct ON ct.teacher_id = tp.id
                LEFT JOIN classes c ON c.id = ct.class_id
                WHERE tp.tenant_id = $1
                GROUP BY tp.id, i.name
                ORDER BY tp.display_name
                """,
                _uuid(tenant_id),
            )
        return [dict(row) for row in rows]

    async def create_admin_staff(self, tenant_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            institution_id = _uuid(data["institution_id"])
            valid = await connection.fetchval(
                "SELECT EXISTS (SELECT 1 FROM institutions WHERE id = $1 AND tenant_id = $2)",
                institution_id, _uuid(tenant_id),
            )
            if not valid:
                raise NotFoundError("institution not found")
            staff_id = await connection.fetchval(
                """
                INSERT INTO teacher_profiles (
                  tenant_id, institution_id, display_name, role_title, subject, education,
                  short_bio, status, employment_type, weekly_hours
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                RETURNING id
                """,
                _uuid(tenant_id), institution_id, data["display_name"], data.get("role_title"),
                data.get("subject"), data.get("education"), data.get("short_bio"),
                data.get("status", "active"), data.get("employment_type", "fixed"), data.get("weekly_hours", 0),
            )
        staff = await self.list_admin_staff(tenant_id, user_id)
        return next((item for item in staff if item["id"] == str(staff_id)), {})

    async def update_admin_staff(self, tenant_id: str, user_id: str, staff_id: str, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {key: data[key] for key in (
            "display_name", "role_title", "subject", "education", "short_bio", "status", "employment_type", "weekly_hours",
        ) if key in data}
        if not allowed:
            raise ConflictError("no staff fields supplied")
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            staff_uuid = _uuid(staff_id)
            assignments = ", ".join(f"{column} = ${index + 2}" for index, column in enumerate(allowed))
            updated = await connection.execute(
                f"UPDATE teacher_profiles SET {assignments}, updated_at = now() WHERE id = $1 AND tenant_id = ${len(allowed) + 2}",
                staff_uuid, *allowed.values(), _uuid(tenant_id),
            )
            if updated.endswith("0"):
                raise NotFoundError("staff member not found")
        staff = await self.list_admin_staff(tenant_id, user_id)
        return next((item for item in staff if item["id"] == str(staff_uuid)), {})

    async def list_admin_records(self, tenant_id: str, user_id: str, module: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran", "guru",
            ))
            roles = await connection.fetch(
                "SELECT role FROM user_roles WHERE tenant_id = $1 AND user_id = $2",
                _uuid(tenant_id), _uuid(user_id),
            )
            is_admin = any(row["role"] in {"super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran"} for row in roles)
            if not is_admin and module not in {"grades", "tahfidz", "journals", "schedule"}:
                raise PermissionDeniedError("guru tidak memiliki akses ke modul ini")
            scope_clause = ""
            if not is_admin and module in {"grades", "tahfidz"}:
                scope_clause = """
                  AND EXISTS (
                    SELECT 1
                    FROM enrollments teacher_enrollment
                    JOIN class_teachers ct
                      ON ct.class_id = teacher_enrollment.class_id
                     AND ct.tenant_id = teacher_enrollment.tenant_id
                    JOIN teacher_profiles tp ON tp.id = ct.teacher_id
                    WHERE teacher_enrollment.student_id = ar.entity_id
                      AND teacher_enrollment.tenant_id = $1
                      AND teacher_enrollment.status = 'active'
                      AND tp.user_id = $2
                  )
                 """
            elif not is_admin and module in {"journals", "schedule"}:
                scope_clause = "AND ar.created_by = $2"
            rows = await connection.fetch(
                f"""
                SELECT ar.id::text AS id, ar.module, ar.record_key, ar.entity_id::text AS entity_id,
                       payload, status, created_by::text AS created_by, created_at, updated_at
                FROM admin_records ar
                WHERE ar.tenant_id = $1 AND ar.module = $3 AND ar.status = 'active'
                {scope_clause}
                ORDER BY updated_at DESC
                """,
                _uuid(tenant_id), _uuid(user_id), module,
            )
        result = []
        for row in rows:
            item = dict(row)
            if isinstance(item.get("payload"), str):
                item["payload"] = json.loads(item["payload"])
            result.append(item)
        return result

    async def upsert_admin_record(self, tenant_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran", "guru",
            ))
            existing_owner = await connection.fetchval(
                "SELECT created_by::text FROM admin_records WHERE tenant_id = $1 AND module = $2 AND record_key = $3",
                _uuid(tenant_id), data["module"], data.get("record_key") or str(UUID(int=0)),
            )
            await self._require_record_access(
                connection, tenant_id, user_id, data["module"],
                str(data["entity_id"]) if data.get("entity_id") else None,
                existing_owner,
            )
            row = await connection.fetchrow(
                """
                INSERT INTO admin_records (tenant_id, module, record_key, entity_id, payload, status, created_by)
                VALUES ($1, $2, $3, $4, $5::jsonb, 'active', $6)
                ON CONFLICT (tenant_id, module, record_key) DO UPDATE
                  SET entity_id = EXCLUDED.entity_id, payload = EXCLUDED.payload,
                      status = 'active', updated_at = now()
                RETURNING id::text AS id, module, record_key, entity_id::text AS entity_id,
                          payload, status, created_by::text AS created_by, created_at, updated_at
                """,
                _uuid(tenant_id), data["module"], data.get("record_key") or str(UUID(int=0)),
                _uuid(data["entity_id"]) if data.get("entity_id") else None,
                json.dumps(data.get("payload") or {}), _uuid(user_id),
            )
        item = dict(row)
        if isinstance(item.get("payload"), str):
            item["payload"] = json.loads(item["payload"])
        return item

    async def update_admin_record(self, tenant_id: str, user_id: str, record_id: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran", "guru",
            ))
            existing = await connection.fetchrow(
                "SELECT module, entity_id::text AS entity_id, created_by::text AS created_by FROM admin_records WHERE id = $1 AND tenant_id = $2",
                _uuid(record_id), _uuid(tenant_id),
            )
            if existing is None:
                raise NotFoundError("admin record not found")
            await self._require_record_access(
                connection, tenant_id, user_id, existing["module"], existing["entity_id"], existing["created_by"],
            )
            row = await connection.fetchrow(
                """
                UPDATE admin_records
                SET payload = COALESCE($2::jsonb, payload), status = COALESCE($3, status), updated_at = now()
                WHERE id = $1 AND tenant_id = $4
                RETURNING id::text AS id, module, record_key, entity_id::text AS entity_id,
                          payload, status, created_by::text AS created_by, created_at, updated_at
                """,
                _uuid(record_id), json.dumps(data.get("payload")) if "payload" in data else None,
                data.get("status"), _uuid(tenant_id),
            )
            if row is None:
                raise NotFoundError("admin record not found")
        item = dict(row)
        if isinstance(item.get("payload"), str):
            item["payload"] = json.loads(item["payload"])
        return item

    async def list_admin_content(self, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            rows = await connection.fetch(
                """
                SELECT sc.id::text AS id, sc.site_kind, sc.foundation_site_id::text AS foundation_site_id,
                       sc.institution_id::text AS institution_id, i.name AS institution_name,
                       sc.content_type, sc.slug, sc.title, sc.excerpt, sc.body, sc.cover_url,
                       sc.status, sc.sort_order, sc.published_at, sc.created_at, sc.updated_at
                FROM site_content sc
                LEFT JOIN institutions i ON i.id = sc.institution_id
                WHERE sc.tenant_id = $1
                ORDER BY sc.updated_at DESC, sc.sort_order, sc.title
                """,
                _uuid(tenant_id),
            )
        return [dict(row) for row in rows]

    async def create_admin_content(self, tenant_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            site_kind = data.get("site_kind", "foundation")
            foundation_id = None
            institution_id = None
            if site_kind == "foundation":
                foundation_id = await connection.fetchval(
                    "SELECT id FROM foundation_sites WHERE tenant_id = $1 ORDER BY created_at LIMIT 1",
                    _uuid(tenant_id),
                )
            else:
                institution_id = _uuid(data["institution_id"]) if data.get("institution_id") else await connection.fetchval(
                    "SELECT id FROM institutions WHERE tenant_id = $1 ORDER BY code LIMIT 1", _uuid(tenant_id)
                )
                if institution_id is None:
                    raise NotFoundError("institution not found")
            status = data.get("status", "draft")
            content_id = await connection.fetchval(
                """
                INSERT INTO site_content (
                  tenant_id, site_kind, foundation_site_id, institution_id, content_type, slug,
                  title, excerpt, body, cover_url, status, sort_order, published_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                          CASE WHEN $11 = 'published' THEN now() ELSE NULL END)
                RETURNING id
                """,
                _uuid(tenant_id), site_kind, foundation_id, institution_id, data.get("content_type", "article"),
                data["slug"], data["title"], data.get("excerpt"), data.get("body"), data.get("cover_url"),
                status, data.get("sort_order", 0),
            )
        content = await self.list_admin_content(tenant_id, user_id)
        return next((item for item in content if item["id"] == str(content_id)), {})

    async def update_admin_content(self, tenant_id: str, user_id: str, content_id: str, data: dict[str, Any]) -> dict[str, Any]:
        allowed = {key: data[key] for key in (
            "content_type", "slug", "title", "excerpt", "body", "cover_url", "status", "sort_order",
        ) if key in data}
        if not allowed:
            raise ConflictError("no content fields supplied")
        assignments = ", ".join(f"{column} = ${index + 2}" for index, column in enumerate(allowed))
        values = list(allowed.values())
        if "status" in allowed:
            status_placeholder = list(allowed).index("status") + 2
            assignments += f", published_at = CASE WHEN ${status_placeholder} = 'published' THEN COALESCE(published_at, now()) ELSE NULL END"
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            row = await connection.fetchrow(
                f"""
                UPDATE site_content SET {assignments}, updated_at = now()
                WHERE id = $1 AND tenant_id = ${len(values) + 2}
                RETURNING id::text AS id, site_kind, foundation_site_id::text AS foundation_site_id,
                          institution_id::text AS institution_id, content_type, slug, title, excerpt,
                          body, cover_url, status, sort_order, published_at, created_at, updated_at
                """,
                _uuid(content_id), *values, _uuid(tenant_id),
            )
            if row is None:
                raise NotFoundError("content not found")
        return dict(row)

    async def export_admin_data(self, tenant_id: str, user_id: str) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            await self._require_roles(connection, tenant_id, user_id, (
                "super_admin", "yayasan_admin", "lembaga_admin", "operator_pendaftaran",
            ))
            students = await connection.fetch(
                "SELECT id::text AS id, nis, full_name, birth_place, birth_date, gender, address, status, created_at, updated_at FROM students WHERE tenant_id = $1 ORDER BY full_name",
                _uuid(tenant_id),
            )
            staff = await connection.fetch(
                "SELECT id::text AS id, institution_id::text AS institution_id, display_name, role_title, subject, education, status, employment_type, weekly_hours, created_at, updated_at FROM teacher_profiles WHERE tenant_id = $1 ORDER BY display_name",
                _uuid(tenant_id),
            )
            records = await connection.fetch(
                "SELECT id::text AS id, module, record_key, entity_id::text AS entity_id, payload, status, created_at, updated_at FROM admin_records WHERE tenant_id = $1 ORDER BY module, updated_at DESC",
                _uuid(tenant_id),
            )
            content = await connection.fetch(
                "SELECT id::text AS id, site_kind, foundation_site_id::text AS foundation_site_id, institution_id::text AS institution_id, content_type, slug, title, excerpt, body, cover_url, status, sort_order, published_at, created_at, updated_at FROM site_content WHERE tenant_id = $1 ORDER BY updated_at DESC",
                _uuid(tenant_id),
            )
            attendance = await connection.fetch(
                "SELECT id::text AS id, class_id::text AS class_id, attendance_date, status, opened_at, closed_at FROM attendance_sessions WHERE tenant_id = $1 ORDER BY attendance_date DESC LIMIT 500",
                _uuid(tenant_id),
            )
        def serialise(rows: list[Any]) -> list[dict[str, Any]]:
            result = []
            for row in rows:
                item = dict(row)
                if isinstance(item.get("payload"), str):
                    item["payload"] = json.loads(item["payload"])
                result.append(item)
            return result
        return {
            "generated_at": datetime.now(timezone.utc),
            "tenant_id": tenant_id,
            "students": serialise(students),
            "staff": serialise(staff),
            "records": serialise(records),
            "content": serialise(content),
            "attendance_sessions": serialise(attendance),
        }

    async def fetch_public_foundation(self, tenant_id: str) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            row = await connection.fetchrow(
                """
                SELECT id::text AS id, tenant_id::text AS tenant_id, slug, name,
                       hero_title, established_year, tagline, description, logo_url,
                       phone, email::text AS email, address, is_published
                FROM foundation_sites
                WHERE tenant_id = $1 AND is_published
                """,
                _uuid(tenant_id),
            )
        if row is None:
            raise NotFoundError("published foundation not found")
        return dict(row)

    async def list_public_institutions(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            rows = await connection.fetch(
                """
                SELECT i.id::text AS id, i.tenant_id::text AS tenant_id, i.code,
                       i.name, i.institution_type, s.slug, s.name AS site_name,
                       s.hero_title, s.tagline, s.description, s.logo_url,
                       s.phone, s.email::text AS email, s.address, s.theme
                FROM institutions i
                JOIN institution_sites s ON s.institution_id = i.id
                WHERE i.tenant_id = $1 AND s.is_published
                ORDER BY i.code
                """,
                _uuid(tenant_id),
            )
        return [dict(row) for row in rows]

    async def fetch_public_institution(self, tenant_id: str, slug: str) -> dict[str, Any]:
        async with self._tenant_connection(tenant_id) as connection:
            row = await connection.fetchrow(
                """
                SELECT i.id::text AS id, i.tenant_id::text AS tenant_id, i.code,
                       i.name, i.institution_type, s.slug, s.name AS site_name,
                       s.hero_title, s.tagline, s.description, s.logo_url,
                       s.phone, s.email::text AS email, s.address, s.theme
                FROM institutions i
                JOIN institution_sites s ON s.institution_id = i.id
                WHERE i.tenant_id = $1 AND s.slug = $2 AND s.is_published
                """,
                _uuid(tenant_id), slug,
            )
        if row is None:
            raise NotFoundError("published institution not found")
        return dict(row)

    async def list_public_posts(self, tenant_id: str, institution_slug: str, *, limit: int = 20) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            rows = await connection.fetch(
                """
                SELECT c.id::text AS id, c.institution_id::text AS institution_id,
                       c.content_type AS post_type, c.slug, c.title, c.excerpt,
                       c.body, c.cover_url, c.published_at
                FROM site_content c
                JOIN institution_sites s ON s.institution_id = c.institution_id
                WHERE c.tenant_id = $1 AND s.slug = $2 AND s.is_published
                  AND c.site_kind = 'institution' AND c.status = 'published'
                ORDER BY c.published_at DESC NULLS LAST, c.created_at DESC
                LIMIT $3
                """,
                _uuid(tenant_id), institution_slug, limit,
            )
        return [dict(row) for row in rows]

    async def list_public_content(self, tenant_id: str, site_kind: str, target_id: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            rows = await connection.fetch(
                """
                SELECT id::text AS id, site_kind,
                       foundation_site_id::text AS foundation_site_id,
                       institution_id::text AS institution_id, content_type,
                       slug, title, excerpt, body, cover_url, published_at
                FROM site_content
                WHERE tenant_id = $1 AND site_kind = $2
                  AND (($2 = 'foundation' AND foundation_site_id = $3)
                    OR ($2 = 'institution' AND institution_id = $3))
                  AND status = 'published'
                ORDER BY sort_order, published_at DESC NULLS LAST, created_at DESC
                """,
                _uuid(tenant_id), site_kind, _uuid(target_id),
            )
        return [dict(row) for row in rows]

    async def list_public_teachers(self, tenant_id: str, institution_id: str) -> list[dict[str, Any]]:
        async with self._tenant_connection(tenant_id) as connection:
            rows = await connection.fetch(
                """
                SELECT id::text AS id, institution_id::text AS institution_id,
                       display_name, role_title, subject, short_bio, education,
                       photo_url, sort_order
                FROM teacher_profiles
                WHERE tenant_id = $1 AND institution_id = $2 AND is_published
                ORDER BY sort_order, display_name
                """,
                _uuid(tenant_id), _uuid(institution_id),
            )
        return [dict(row) for row in rows]

    async def create_registration(self, tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            import asyncpg
        except ImportError as exc:
            raise DatabaseUnavailable("asyncpg is required for PostgreSQL runtime") from exc
        query = """
            INSERT INTO registration_applications (
              tenant_id, institution_id, registration_type, academic_year,
              student_full_name, birth_place, birth_date, gender, address,
              father_name, father_phone, mother_name, mother_phone,
              guardian_name, guardian_phone, notes, idempotency_key
            )
            SELECT $1, i.id, $3, $4, $5, $6, $7, $8, $9,
                   $10, $11, $12, $13, $14, $15, $16, $17
            FROM institutions i
            WHERE i.id = $2 AND i.tenant_id = $1 AND i.status = 'active'
            RETURNING id::text AS id, application_no, status,
                      institution_id::text AS institution_id, student_full_name,
                      submitted_at, created_at
        """
        values = (
            _uuid(tenant_id), _uuid(data["institution_id"]), data["registration_type"],
            data["academic_year"], data["student_full_name"], data.get("birth_place"),
            data.get("birth_date"), data.get("gender"), data.get("address"),
             data.get("father_name"), data.get("father_phone"), data.get("mother_name"),
             data.get("mother_phone"), data.get("guardian_name"), data.get("guardian_phone"),
             data.get("notes"), data.get("idempotency_key"),
         )
        try:
            async with self._tenant_connection(tenant_id) as connection:
                row = await connection.fetchrow(query, *values)
        except asyncpg.exceptions.UniqueViolationError as exc:
            if data.get("idempotency_key"):
                async with self._tenant_connection(tenant_id) as connection:
                    row = await connection.fetchrow(
                        """
                        SELECT id::text AS id, application_no, status,
                               institution_id::text AS institution_id, student_full_name,
                               submitted_at, created_at
                        FROM registration_applications
                        WHERE tenant_id = $1 AND idempotency_key = $2
                        """,
                        _uuid(tenant_id), data["idempotency_key"],
                    )
                if row is not None:
                    return dict(row)
            raise ConflictError("registration could not be created twice") from exc
        if row is None:
            raise NotFoundError("institution not found in foundation")
        return dict(row)
