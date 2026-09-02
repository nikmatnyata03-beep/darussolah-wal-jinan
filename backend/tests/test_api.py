from __future__ import annotations

import time
from uuid import UUID

from fastapi.testclient import TestClient
from jwt import encode

from app.auth import UserIdentity, current_user
from app.config import Settings
from app.db import NotFoundError
from app.main import create_app


TENANT_ID = "11111111-1111-4111-8111-111111111111"
FOUNDATION_ID = "22222222-2222-4222-8222-222222222222"
INSTITUTION_ID = "33333333-3333-4333-8333-333333333333"


class FakeStore:
    async def fetch_tenant_by_slug(self, slug: str):
        if slug != "yayasan-darussolah-wal-jinan":
            raise NotFoundError("not found")
        return {"id": TENANT_ID, "slug": slug, "name": "Yayasan", "status": "active"}

    async def fetch_public_foundation(self, tenant_id: str):
        return {"id": FOUNDATION_ID, "tenant_id": tenant_id, "name": "Yayasan Darussolah"}

    async def list_public_institutions(self, tenant_id: str):
        return [{"id": INSTITUTION_ID, "tenant_id": tenant_id, "slug": "tpq", "name": "TPQ Darul Jinan"}]

    async def fetch_public_institution(self, tenant_id: str, slug: str):
        if slug != "tpq":
            raise NotFoundError("not found")
        return {"id": INSTITUTION_ID, "tenant_id": tenant_id, "slug": slug, "name": "SDIT"}

    async def list_public_posts(self, tenant_id: str, institution_slug: str, *, limit: int = 20):
        return [{"slug": "berita-1", "title": "Berita", "limit_seen": limit}]

    async def list_public_content(self, tenant_id: str, site_kind: str, target_id: str):
        return [{"site_kind": site_kind, "target_id": target_id, "title": "Konten"}]

    async def list_public_teachers(self, tenant_id: str, institution_id: str):
        return [{"institution_id": institution_id, "display_name": "Ustadzah A"}]

    async def list_public_teachers_for_foundation(self, tenant_id: str):
        return [{"institution_id": INSTITUTION_ID, "institution_name": "TPQ", "display_name": "Ustadzah A", "is_published": True}]

    async def list_public_page_blocks(self, tenant_id: str, page_slug: str):
        return [{"page_slug": page_slug, "block_key": "testimonials-main", "block_type": "testimonials", "title": "Cerita keluarga", "settings": {}}]

    async def create_registration(self, tenant_id: str, data: dict):
        assert UUID(tenant_id) == UUID(TENANT_ID)
        assert data["institution_id"] == UUID(INSTITUTION_ID)
        return {"id": "44444444-4444-4444-8444-444444444444", "application_no": "REG-2026-000001", "status": "new"}

    async def ready(self):
        return True

    async def fetch_portal_context(self, tenant_id: str, user_id: str):
        return {
            "profile": {"id": user_id, "tenant_id": tenant_id, "full_name": "Admin Yayasan", "status": "active"},
            "roles": ["yayasan_admin"],
            "memberships": [],
        }

    async def list_portal_students(self, tenant_id: str, user_id: str):
        return [{"id": "55555555-5555-4555-8555-555555555555", "full_name": "Aisyah"}]

    async def list_portal_classes(self, tenant_id: str, user_id: str):
        return [{"id": "66666666-6666-4666-8666-666666666666", "name": "Iqra 2"}]

    async def list_learning_resources(self, tenant_id: str, user_id: str, *, class_id=None, resource_type=None):
        return [{
            "id": "99999999-9999-4999-8999-999999999999",
            "class_id": class_id or "66666666-6666-4666-8666-666666666666",
            "resource_type": resource_type or "material",
            "title": "Mengenal mad thabi'i",
        }]

    async def create_learning_resource(self, tenant_id: str, user_id: str, data: dict):
        assert data["class_id"] == UUID("66666666-6666-4666-8666-666666666666")
        return {
            "id": "99999999-9999-4999-8999-999999999999",
            "class_id": str(data["class_id"]),
            "resource_type": data["resource_type"],
            "title": data["title"],
        }

    async def list_learning_submissions(
        self, tenant_id: str, user_id: str, *, class_id=None, resource_id=None, submission_status=None
    ):
        return [{
            "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0001",
            "resource_id": resource_id or "99999999-9999-4999-8999-999999999999",
            "student_name": "Aisyah",
            "status": submission_status or "submitted",
        }]

    async def review_learning_submission(self, tenant_id: str, user_id: str, submission_id: str, data: dict):
        assert submission_id == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0001"
        assert data["status"] == "reviewed"
        return {
            "id": submission_id,
            "resource_id": "99999999-9999-4999-8999-999999999999",
            "student_name": "Aisyah",
            "status": data["status"],
            "score": data["score"],
        }

    async def create_learning_submission(self, tenant_id: str, user_id: str, data: dict):
        assert data["resource_id"] == UUID("99999999-9999-4999-8999-999999999999")
        return {
            "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
            "resource_id": str(data["resource_id"]),
            "student_id": str(data["student_id"]),
            "status": "submitted",
            "note": data["note"],
        }

    async def fetch_attendance(self, tenant_id: str, user_id: str, class_id: str, attendance_date):
        return {
            "class": {"id": class_id, "name": "Iqra 2"},
            "session": {"id": "88888888-8888-4888-8888-888888888888", "status": "open"},
            "records": [{"student_id": "55555555-5555-4555-8555-555555555555", "status": "present"}],
        }

    async def fetch_guardian_overview(self, tenant_id: str, user_id: str, student_id: str):
        return {
            "student": {"id": student_id, "full_name": "Aisyah", "class_id": "66666666-6666-4666-8666-666666666666"},
            "attendance": {"rate": 100, "days": []},
            "learning": [{"id": "99999999-9999-4999-8999-999999999999", "title": "Materi"}],
            "submissions": [],
        }

    async def save_attendance(self, tenant_id: str, user_id: str, data: dict):
        assert data["class_id"] == UUID("66666666-6666-4666-8666-666666666666")
        assert data["records"][0]["status"] == "present"
        return await self.fetch_attendance(tenant_id, user_id, str(data["class_id"]), str(data["attendance_date"]))

    async def fetch_admin_summary(self, tenant_id: str, user_id: str):
        assert UUID(tenant_id) == UUID(TENANT_ID)
        assert UUID(user_id) == UUID("77777777-7777-4777-8777-777777777777")
        return {"students_active": 1, "registrations_pending": 0, "attendance_sessions_today": 1}

    async def list_admin_students(self, tenant_id: str, user_id: str):
        assert UUID(tenant_id) == UUID(TENANT_ID)
        assert UUID(user_id) == UUID("77777777-7777-4777-8777-777777777777")
        return [{"id": "55555555-5555-4555-8555-555555555555", "full_name": "Aisyah", "status": "active"}]

    async def list_admin_page_blocks(self, tenant_id: str, user_id: str, *, page_slug=None):
        return [{"id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", "page_slug": page_slug or "home", "block_key": "hero-main"}]

    async def create_admin_page_block(self, tenant_id: str, user_id: str, data: dict):
        return {"id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", **data}

    async def update_admin_page_block(self, tenant_id: str, user_id: str, block_id: str, data: dict):
        return {"id": block_id, **data}

    async def delete_admin_page_block(self, tenant_id: str, user_id: str, block_id: str):
        return {"id": block_id, "status": "archived"}


def client() -> TestClient:
    settings = Settings(
        environment="test",
        database_url="",
        tenant_slug="yayasan-darussolah-wal-jinan",
        allowed_origins=("https://darussolah-wal-jinan.pages.bu.app",),
    )
    return TestClient(create_app(settings=settings, store=FakeStore()))


def authenticated_client() -> TestClient:
    settings = Settings(
        environment="test",
        database_url="",
        tenant_slug="yayasan-darussolah-wal-jinan",
        allowed_origins=("https://darussolah-wal-jinan.pages.bu.app",),
        jwt_secret="test-secret-with-at-least-32-bytes-long",
    )
    app = create_app(settings=settings, store=FakeStore())
    app.dependency_overrides[current_user] = lambda: UserIdentity(
        user_id=UUID("77777777-7777-4777-8777-777777777777"), email="admin@example.test"
    )
    return TestClient(app)


def test_live_and_public_foundation():
    with client() as api:
        assert api.get("/health/live").json() == {"status": "ok"}
        response = api.get("/v1/public/yayasan-darussolah-wal-jinan/foundation")
        assert response.status_code == 200
        assert response.json()["name"] == "Yayasan Darussolah"
        assert response.headers["x-request-id"]


def test_public_institutions_posts_content_and_teachers():
    with client() as api:
        assert api.get("/v1/public/yayasan-darussolah-wal-jinan/institutions").json()["items"][0]["slug"] == "tpq"
        assert api.get("/v1/public/yayasan-darussolah-wal-jinan/institutions/tpq").status_code == 200
        posts = api.get("/v1/public/yayasan-darussolah-wal-jinan/institutions/tpq/posts?limit=7")
        assert posts.json()["items"][0]["limit_seen"] == 7
        assert api.get("/v1/public/yayasan-darussolah-wal-jinan/foundation/content").status_code == 200
        teachers = api.get("/v1/public/yayasan-darussolah-wal-jinan/institutions/tpq/teachers")
        assert teachers.json()["items"][0]["display_name"] == "Ustadzah A"


def test_public_page_blocks_and_foundation_teachers_are_available():
    with client() as api:
        blocks = api.get("/v1/public/yayasan-darussolah-wal-jinan/pages/home")
        teachers = api.get("/v1/public/yayasan-darussolah-wal-jinan/teachers")
        assert blocks.status_code == 200
        assert blocks.json()["items"][0]["block_type"] == "testimonials"
        assert teachers.status_code == 200
        assert teachers.json()["items"][0]["display_name"] == "Ustadzah A"


def test_registration_validates_and_returns_public_reference():
    with client() as api:
        response = api.post(
            "/v1/public/yayasan-darussolah-wal-jinan/registrations",
            json={
                "institution_id": INSTITUTION_ID,
                "registration_type": "new",
                "academic_year": "2026/2027",
                "student_full_name": "Ahmad Darussolah",
                "idempotency_key": "application-001",
            },
        )
        assert response.status_code == 201
        assert response.json() == {
            "id": "44444444-4444-4444-8444-444444444444",
            "application_no": "REG-2026-000001",
            "status": "new",
        }


def test_registration_rejects_invalid_academic_year():
    with client() as api:
        response = api.post(
            "/v1/public/yayasan-darussolah-wal-jinan/registrations",
            json={
                "institution_id": INSTITUTION_ID,
                "academic_year": "not-a-year",
                "student_full_name": "Ahmad Darussolah",
            },
        )
        assert response.status_code == 422


def test_unknown_tenant_is_not_exposed():
    with client() as api:
        response = api.get("/v1/public/unknown/foundation")
        assert response.status_code == 404


def test_private_portal_routes_require_and_use_authenticated_identity():
    with authenticated_client() as api:
        base = "/v1/private/yayasan-darussolah-wal-jinan"
        context = api.get(f"{base}/me")
        assert context.status_code == 200
        assert context.json()["user"]["roles"] == ["yayasan_admin"]
        assert api.get(f"{base}/students").json()["items"][0]["full_name"] == "Aisyah"
        assert api.get(f"{base}/classes").json()["items"][0]["name"] == "Iqra 2"


def test_private_portal_rejects_anonymous_requests():
    with client() as api:
        response = api.get("/v1/private/yayasan-darussolah-wal-jinan/me")
        assert response.status_code == 401


def test_private_learning_lists_and_creates_resources():
    with authenticated_client() as api:
        base = "/v1/private/yayasan-darussolah-wal-jinan"
        learning = api.get(f"{base}/learning", params={"class_id": "66666666-6666-4666-8666-666666666666"})
        assert learning.status_code == 200
        assert learning.json()["items"][0]["title"] == "Mengenal mad thabi'i"
        created = api.post(
            f"{base}/learning",
            json={
                "class_id": "66666666-6666-4666-8666-666666666666",
                "resource_type": "assignment",
                "title": "Latihan surat Al-Fil",
                "due_date": "2026-08-22",
            },
        )
        assert created.status_code == 201
        assert created.json()["resource_type"] == "assignment"


def test_learning_requires_a_class_or_institution_scope():
    with authenticated_client() as api:
        response = api.post(
            "/v1/private/yayasan-darussolah-wal-jinan/learning",
            json={"resource_type": "material", "title": "Tanpa scope"},
        )
        assert response.status_code == 422


def test_private_learning_submissions_can_be_listed_and_reviewed():
    with authenticated_client() as api:
        base = "/v1/private/yayasan-darussolah-wal-jinan"
        submissions = api.get(f"{base}/learning/submissions", params={"class_id": "66666666-6666-4666-8666-666666666666"})
        assert submissions.status_code == 200
        assert submissions.json()["items"][0]["status"] == "submitted"
        reviewed = api.put(
            f"{base}/learning/submissions/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0001",
            json={"status": "reviewed", "score": 92.5, "feedback": "Bacaan sudah baik."},
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["status"] == "reviewed"

        created = api.post(
            f"{base}/learning/submissions",
            json={
                "resource_id": "99999999-9999-4999-8999-999999999999",
                "student_id": "55555555-5555-4555-8555-555555555555",
                "note": "Sudah mengerjakan latihan.",
            },
        )
        assert created.status_code == 201
        assert created.json()["status"] == "submitted"


def test_guardian_overview_uses_selected_student_scope():
    with authenticated_client() as api:
        response = api.get(
            "/v1/private/yayasan-darussolah-wal-jinan/guardian/overview",
            params={"student_id": "55555555-5555-4555-8555-555555555555"},
        )
        assert response.status_code == 200
        assert response.json()["student"]["id"] == "55555555-5555-4555-8555-555555555555"
        assert response.json()["attendance"]["rate"] == 100


def test_learning_submission_review_rejects_invalid_score():
    with authenticated_client() as api:
        response = api.put(
            "/v1/private/yayasan-darussolah-wal-jinan/learning/submissions/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaa0001",
            json={"status": "reviewed", "score": 101},
        )
        assert response.status_code == 422


def test_learning_submission_requires_file_or_note():
    with authenticated_client() as api:
        response = api.post(
            "/v1/private/yayasan-darussolah-wal-jinan/learning/submissions",
            json={
                "resource_id": "99999999-9999-4999-8999-999999999999",
                "student_id": "55555555-5555-4555-8555-555555555555",
            },
        )
        assert response.status_code == 422


def test_private_attendance_reads_and_saves_for_authenticated_user():
    with authenticated_client() as api:
        base = "/v1/private/yayasan-darussolah-wal-jinan"
        class_id = "66666666-6666-4666-8666-666666666666"
        attendance = api.get(f"{base}/attendance", params={"class_id": class_id, "attendance_date": "2026-08-12"})
        assert attendance.status_code == 200
        assert attendance.json()["records"][0]["status"] == "present"
        saved = api.put(
            f"{base}/attendance",
            json={
                "class_id": class_id,
                "attendance_date": "2026-08-12",
                "records": [{"student_id": "55555555-5555-4555-8555-555555555555", "status": "present"}],
            },
        )
        assert saved.status_code == 200
        assert saved.json()["session"]["status"] == "open"


def test_admin_summary_and_students_use_authenticated_identity():
    with authenticated_client() as api:
        base = "/v1/private/yayasan-darussolah-wal-jinan/admin"
        summary = api.get(f"{base}/summary")
        students = api.get(f"{base}/students")
        assert summary.status_code == 200
        assert summary.json()["students_active"] == 1
        assert students.status_code == 200
        assert students.json()["items"][0]["full_name"] == "Aisyah"


def test_cms_page_block_routes_use_authenticated_identity():
    with authenticated_client() as api:
        base = "/v1/private/yayasan-darussolah-wal-jinan/admin/page-blocks"
        assert api.get(base).status_code == 200
        created = api.post(base, json={"block_key": "custom-main", "block_type": "custom", "title": "Blok baru"})
        assert created.status_code == 201
        updated = api.put(f"{base}/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb", json={"title": "Blok diperbarui"})
        assert updated.status_code == 200
        deleted = api.delete(f"{base}/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        assert deleted.status_code == 200


def test_restore_requires_explicit_confirmation():
    with authenticated_client() as api:
        response = api.post(
            "/v1/private/yayasan-darussolah-wal-jinan/admin/restore",
            json={"confirmation": "YES", "backup": {}},
        )
        assert response.status_code == 422


def test_attendance_rejects_duplicate_students():
    with authenticated_client() as api:
        response = api.put(
            "/v1/private/yayasan-darussolah-wal-jinan/attendance",
            json={
                "class_id": "66666666-6666-4666-8666-666666666666",
                "attendance_date": "2026-08-12",
                "records": [
                    {"student_id": "55555555-5555-4555-8555-555555555555", "status": "present"},
                    {"student_id": "55555555-5555-4555-8555-555555555555", "status": "late"},
                ],
            },
        )
        assert response.status_code == 422


def test_private_cors_preflight_allows_authorization_header():
    with authenticated_client() as api:
        response = api.options(
            "/v1/private/yayasan-darussolah-wal-jinan/me",
            headers={
                "Origin": "https://darussolah-wal-jinan.pages.bu.app",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status_code == 200
        assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_private_cors_preflight_allows_attendance_put():
    with authenticated_client() as api:
        response = api.options(
            "/v1/private/yayasan-darussolah-wal-jinan/attendance",
            headers={
                "Origin": "https://darussolah-wal-jinan.pages.bu.app",
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert "PUT" in response.headers["access-control-allow-methods"]


def test_private_cors_preflight_allows_delete():
    with authenticated_client() as api:
        response = api.options(
            "/v1/private/yayasan-darussolah-wal-jinan/admin/page-blocks/00000000-0000-4000-8000-000000000000",
            headers={
                "Origin": "https://darussolah-wal-jinan.pages.bu.app",
                "Access-Control-Request-Method": "DELETE",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert response.status_code == 200
        assert "DELETE" in response.headers["access-control-allow-methods"]


def test_supabase_hs256_token_authenticates_private_route():
    settings = Settings(
        environment="test",
        database_url="",
        tenant_slug="yayasan-darussolah-wal-jinan",
        allowed_origins=(),
        jwt_secret="test-secret-with-at-least-32-bytes-long",
    )
    token = encode(
        {
            "sub": "77777777-7777-4777-8777-777777777777",
            "aud": "authenticated",
            "exp": int(time.time()) + 300,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    with TestClient(create_app(settings=settings, store=FakeStore())) as api:
        response = api.get(
            "/v1/private/yayasan-darussolah-wal-jinan/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


def test_supabase_jwks_url_is_derived_from_project_url(monkeypatch):
    monkeypatch.setenv("DARUSSOLAH_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("DARUSSOLAH_JWKS_URL", raising=False)
    settings = Settings.from_env(require_runtime=False)
    assert settings.jwks_url == "https://example.supabase.co/auth/v1/.well-known/jwks.json"


def test_production_hides_api_documentation_and_adds_response_hardening():
    settings = Settings(
        environment="production",
        database_url="postgresql://example.invalid/db",
        tenant_slug="yayasan-darussolah-wal-jinan",
        allowed_origins=("https://darussolah-wal-jinan.vercel.app",),
        supabase_url="https://example.supabase.co",
        jwks_url="https://example.supabase.co/auth/v1/.well-known/jwks.json",
    )
    with TestClient(create_app(settings=settings, store=FakeStore())) as api:
        assert api.get("/docs").status_code == 404
        response = api.get("/health/live")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
