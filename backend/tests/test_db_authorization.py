from __future__ import annotations

import asyncio

import pytest

from app.db import FoundationStore, PermissionDeniedError


class RoleConnection:
    def __init__(self, roles: list[str], scoped: bool = False) -> None:
        self.roles = roles
        self.scoped = scoped
        self.fetchval_calls = 0

    async def fetch(self, *_args):
        return [{"role": role} for role in self.roles]

    async def fetchval(self, *_args):
        self.fetchval_calls += 1
        return self.scoped


def test_lembaga_admin_requires_membership() -> None:
    connection = RoleConnection(["lembaga_admin"])

    with pytest.raises(PermissionDeniedError, match="requires an institution membership"):
        asyncio.run(
            FoundationStore("")._require_roles(
                connection,
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
                ("lembaga_admin",),
            )
        )

    assert connection.fetchval_calls == 1


def test_global_admin_does_not_need_institution_membership() -> None:
    connection = RoleConnection(["yayasan_admin"])

    roles = asyncio.run(
        FoundationStore("")._require_roles(
            connection,
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
            ("yayasan_admin",),
        )
    )

    assert roles == {"yayasan_admin"}
    assert connection.fetchval_calls == 0
