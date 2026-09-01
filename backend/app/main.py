"""Public HTTP API for Yayasan Darussolah Wal Jinan."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from .auth import UserIdentity, current_user
from .config import Settings
from .db import ConflictError, DatabaseUnavailable, FoundationStore, NotFoundError, PermissionDeniedError


class RegistrationCreateRequest(BaseModel):
    institution_id: UUID
    registration_type: Literal["new", "re_registration"] = "new"
    academic_year: str = Field(min_length=4, max_length=20, pattern=r"^[0-9]{4}([/-][0-9]{4})?$")
    student_full_name: str = Field(min_length=2, max_length=200)
    birth_place: str | None = Field(default=None, max_length=100)
    birth_date: date | None = None
    gender: Literal["male", "female"] | None = None
    address: str | None = Field(default=None, max_length=1000)
    father_name: str | None = Field(default=None, max_length=200)
    father_phone: str | None = Field(default=None, max_length=40)
    mother_name: str | None = Field(default=None, max_length=200)
    mother_phone: str | None = Field(default=None, max_length=40)
    guardian_name: str | None = Field(default=None, max_length=200)
    guardian_phone: str | None = Field(default=None, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class AttendanceRecordRequest(BaseModel):
    student_id: UUID
    status: Literal["pending", "present", "excused", "sick", "absent", "late"]
    note: str | None = Field(default=None, max_length=500)


class AttendanceSaveRequest(BaseModel):
    class_id: UUID
    attendance_date: date
    records: list[AttendanceRecordRequest] = Field(min_length=1, max_length=200)
    close_session: bool = False

    @model_validator(mode="after")
    def unique_students(self):
        student_ids = [record.student_id for record in self.records]
        if len(student_ids) != len(set(student_ids)):
            raise ValueError("each student may appear only once")
        return self


class LearningResourceCreateRequest(BaseModel):
    institution_id: UUID | None = None
    class_id: UUID | None = None
    resource_type: Literal["material", "assignment", "announcement"]
    title: str = Field(min_length=2, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=3000)
    file_path: str | None = Field(default=None, max_length=500)
    due_date: date | None = None
    status: Literal["draft", "published"] = "published"

    @model_validator(mode="after")
    def require_scope(self):
        if self.institution_id is None and self.class_id is None:
            raise ValueError("institution_id or class_id is required")
        return self


class LearningSubmissionReviewRequest(BaseModel):
    status: Literal["reviewed", "returned"]
    score: float | None = Field(default=None, ge=0, le=100)
    feedback: str | None = Field(default=None, max_length=3000)


class LearningSubmissionCreateRequest(BaseModel):
    resource_id: UUID
    student_id: UUID
    file_path: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def require_submission_content(self):
        if not self.file_path and not (self.note and self.note.strip()):
            raise ValueError("file_path or note is required")
        return self


def _store(request: Request) -> FoundationStore:
    store = request.app.state.store
    if store is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database is not configured")
    return store


async def _public_tenant(store: FoundationStore, tenant_slug: str) -> dict:
    try:
        return await store.fetch_tenant_by_slug(tenant_slug)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "foundation not found") from exc


@asynccontextmanager
async def _lifespan(app: FastAPI):
    if app.state.settings.environment == "production":
        app.state.settings.validate_runtime()
    created_store = False
    store = app.state.store
    if store is None and app.state.settings.database_url:
        store = FoundationStore(app.state.settings.database_url)
        await store.connect()
        app.state.store = store
        created_store = True
    yield
    if created_store and store is not None:
        await store.close()


def create_app(*, settings: Settings | None = None, store: FoundationStore | None = None) -> FastAPI:
    settings = settings or Settings.from_env(require_runtime=False)
    production = settings.environment.lower() == "production"
    app = FastAPI(
        title="Darussolah Foundation API",
        version="0.1.0",
        lifespan=_lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    app.state.settings = settings
    app.state.store = store
    origins = list(settings.allowed_origins) or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=bool(settings.allowed_origins),
        allow_methods=["GET", "POST", "PUT", "OPTIONS"],
         allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID") or str(uuid4())
        if request.url.path.endswith("/registrations"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > settings.registration_max_bytes:
                return JSONResponse(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    content={"detail": "registration request is too large"},
                )
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/health/live", tags=["health"])
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request, store: FoundationStore = Depends(_store)):
        try:
            await store.ready()
        except DatabaseUnavailable as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
        return {"status": "ready"}

    @app.get("/v1/public/{tenant_slug}/foundation", tags=["public"])
    async def public_foundation(tenant_slug: str, store: FoundationStore = Depends(_store)):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return await store.fetch_public_foundation(tenant["id"])
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "published foundation profile not found") from exc

    @app.get("/v1/public/{tenant_slug}/institutions", tags=["public"])
    async def public_institutions(tenant_slug: str, store: FoundationStore = Depends(_store)):
        tenant = await _public_tenant(store, tenant_slug)
        return {"items": await store.list_public_institutions(tenant["id"])}

    @app.get("/v1/public/{tenant_slug}/institutions/{institution_slug}", tags=["public"])
    async def public_institution(tenant_slug: str, institution_slug: str, store: FoundationStore = Depends(_store)):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return await store.fetch_public_institution(tenant["id"], institution_slug)
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "published institution not found") from exc

    @app.get("/v1/public/{tenant_slug}/institutions/{institution_slug}/posts", tags=["public"])
    async def public_posts(
        tenant_slug: str,
        institution_slug: str,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        return {"items": await store.list_public_posts(tenant["id"], institution_slug, limit=limit)}

    @app.get("/v1/public/{tenant_slug}/foundation/content", tags=["public"])
    async def public_foundation_content(tenant_slug: str, store: FoundationStore = Depends(_store)):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            foundation = await store.fetch_public_foundation(tenant["id"])
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "published foundation profile not found") from exc
        return {"items": await store.list_public_content(tenant["id"], "foundation", foundation["id"])}

    @app.get("/v1/public/{tenant_slug}/institutions/{institution_slug}/content", tags=["public"])
    async def public_institution_content(tenant_slug: str, institution_slug: str, store: FoundationStore = Depends(_store)):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            institution = await store.fetch_public_institution(tenant["id"], institution_slug)
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "published institution not found") from exc
        return {"items": await store.list_public_content(tenant["id"], "institution", institution["id"])}

    @app.get("/v1/public/{tenant_slug}/institutions/{institution_slug}/teachers", tags=["public"])
    async def public_teachers(tenant_slug: str, institution_slug: str, store: FoundationStore = Depends(_store)):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            institution = await store.fetch_public_institution(tenant["id"], institution_slug)
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "published institution not found") from exc
        return {"items": await store.list_public_teachers(tenant["id"], institution["id"])}

    @app.post("/v1/public/{tenant_slug}/registrations", status_code=status.HTTP_201_CREATED, tags=["public"])
    async def create_registration(
        tenant_slug: str,
        payload: RegistrationCreateRequest,
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            result = await store.create_registration(tenant["id"], payload.model_dump())
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "institution not found in foundation") from exc
        except ConflictError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        return {
            "id": result["id"],
            "application_no": result["application_no"],
            "status": result["status"],
        }

    @app.get("/v1/private/{tenant_slug}/me", tags=["private"])
    async def private_me(
        tenant_slug: str,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            context = await store.fetch_portal_context(tenant["id"], str(user.user_id))
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "portal profile not found") from exc
        return {"tenant": tenant, "user": context}

    @app.get("/v1/private/{tenant_slug}/students", tags=["private"])
    async def private_students(
        tenant_slug: str,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        return {"items": await store.list_portal_students(tenant["id"], str(user.user_id))}

    @app.get("/v1/private/{tenant_slug}/classes", tags=["private"])
    async def private_classes(
        tenant_slug: str,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        return {"items": await store.list_portal_classes(tenant["id"], str(user.user_id))}

    @app.get("/v1/private/{tenant_slug}/learning", tags=["private", "learning"])
    async def private_learning(
        tenant_slug: str,
        class_id: UUID | None = None,
        resource_type: Literal["material", "assignment", "announcement"] | None = None,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return {
                "items": await store.list_learning_resources(
                    tenant["id"], str(user.user_id),
                    class_id=str(class_id) if class_id else None,
                    resource_type=resource_type,
                )
            }
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    @app.post("/v1/private/{tenant_slug}/learning", status_code=status.HTTP_201_CREATED, tags=["private", "learning"])
    async def create_private_learning(
        tenant_slug: str,
        payload: LearningResourceCreateRequest,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return await store.create_learning_resource(tenant["id"], str(user.user_id), payload.model_dump())
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    @app.get("/v1/private/{tenant_slug}/learning/submissions", tags=["private", "learning"])
    async def private_learning_submissions(
        tenant_slug: str,
        class_id: UUID | None = None,
        resource_id: UUID | None = None,
        submission_status: Literal["submitted", "late", "reviewed", "returned"] | None = None,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return {
                "items": await store.list_learning_submissions(
                    tenant["id"], str(user.user_id),
                    class_id=str(class_id) if class_id else None,
                    resource_id=str(resource_id) if resource_id else None,
                    submission_status=submission_status,
                )
            }
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    @app.post("/v1/private/{tenant_slug}/learning/submissions", status_code=status.HTTP_201_CREATED, tags=["private", "learning"])
    async def create_private_learning_submission(
        tenant_slug: str,
        payload: LearningSubmissionCreateRequest,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return await store.create_learning_submission(tenant["id"], str(user.user_id), payload.model_dump())
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc

    @app.put("/v1/private/{tenant_slug}/learning/submissions/{submission_id}", tags=["private", "learning"])
    async def review_private_learning_submission(
        tenant_slug: str,
        submission_id: UUID,
        payload: LearningSubmissionReviewRequest,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return await store.review_learning_submission(
                tenant["id"], str(user.user_id), str(submission_id), payload.model_dump()
            )
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        except PermissionDeniedError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc

    @app.get("/v1/private/{tenant_slug}/attendance", tags=["private", "attendance"])
    async def private_attendance(
        tenant_slug: str,
        class_id: UUID,
        attendance_date: date | None = None,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return await store.fetch_attendance(
                tenant["id"], str(user.user_id), str(class_id), attendance_date or date.today()
            )
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    @app.put("/v1/private/{tenant_slug}/attendance", tags=["private", "attendance"])
    async def save_private_attendance(
        tenant_slug: str,
        payload: AttendanceSaveRequest,
        user: UserIdentity = Depends(current_user),
        store: FoundationStore = Depends(_store),
    ):
        tenant = await _public_tenant(store, tenant_slug)
        try:
            return await store.save_attendance(tenant["id"], str(user.user_id), payload.model_dump())
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        except ConflictError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    return app


app = create_app()
