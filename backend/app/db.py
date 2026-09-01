"""Tenant-filtered asyncpg repository for the foundation website."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
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
                       s.birth_place, s.birth_date, s.gender, s.address,
                       s.status, s.photo_url
                FROM students s
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
                       c.institution_id::text AS institution_id, i.code AS institution_code,
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
            WHERE i.id = $2 AND i.tenant_id = $1
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
            raise ConflictError("registration could not be created twice") from exc
        if row is None:
            raise NotFoundError("institution not found in foundation")
        return dict(row)
