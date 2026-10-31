import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import SESSION_COOKIE, create_session_token
from app.db import crud, models
from app.db.base import Base
from app.db.session import get_session
from app.main import app


@pytest.fixture
async def ctx():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)

    async with factory() as db:
        agent = await crud.create_user(db, "Agent", "agent@example.com")
        colleague = await crud.create_user(db, "Colleague", "colleague@example.com")
        outsider = await crud.create_user(db, "Outsider", "outsider@example.com")
        await db.commit()

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        client.cookies.set(SESSION_COOKIE, create_session_token(agent.id))
        yield client, transport, agent, colleague, outsider

    app.dependency_overrides.clear()
    await engine.dispose()


def _client_for(transport: httpx.ASGITransport, user: models.User) -> httpx.AsyncClient:
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    client.cookies.set(SESSION_COOKIE, create_session_token(user.id))
    return client


@pytest.mark.asyncio
async def test_me_returns_session_user(ctx):
    client, _, agent, _, _ = ctx
    r = await client.get("/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == str(agent.id)
    assert body["email"] == "agent@example.com"
    assert body["gmail_connected"] is False


@pytest.mark.asyncio
async def test_requests_without_session_are_rejected(ctx):
    _, transport, _, _, _ = ctx
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as anon:
        assert (await anon.get("/auth/me")).status_code == 401
        assert (await anon.get("/users")).status_code == 401
        assert (await anon.get("/teams")).status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_session(monkeypatch):
    from app.api.routes import auth as auth_route

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_session():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    class FakeCredentials:
        scopes = ["https://www.googleapis.com/auth/gmail.readonly"]

        def to_json(self) -> str:
            return "{}"

    monkeypatch.setattr(
        auth_route.gmail_auth, "exchange_code", lambda code, state: FakeCredentials()
    )
    monkeypatch.setattr(
        auth_route.gmail_auth, "get_profile_email", lambda creds: "agent@example.com"
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/auth/google/redirect?code=x&state=y", follow_redirects=False
        )
        assert r.status_code in (302, 307)
        assert SESSION_COOKIE in r.cookies
        assert (await client.get("/auth/me")).status_code == 200

        r = await client.post("/auth/logout")
        assert r.status_code == 200
        assert (await client.get("/auth/me")).status_code == 401

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_cannot_read_another_users_inbox(ctx):
    client, _, _, colleague, _ = ctx
    r = await client.get(f"/emails/inbox/{colleague.id}")
    assert r.status_code == 403
    r = await client.get(f"/emails/digest/{colleague.id}")
    assert r.status_code == 403
    r = await client.get(f"/notifications/{colleague.id}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_team_create_invite_and_report(ctx):
    client, transport, _, colleague, outsider = ctx

    r = await client.post("/teams", json={"name": "Lake Team"})
    assert r.status_code == 200
    team_id = r.json()["id"]

    r = await client.get("/teams")
    assert r.status_code == 200
    assert len(r.json()["teams"]) == 1

    r = await client.post(
        f"/teams/{team_id}/members",
        json={"email": "colleague@example.com", "role": "agent"},
    )
    assert r.status_code == 200
    assert r.json()["user_id"] == str(colleague.id)

    r = await client.post(
        f"/teams/{team_id}/members",
        json={"email": "colleague@example.com"},
    )
    assert r.status_code == 400

    r = await client.get(f"/teams/{team_id}")
    assert r.status_code == 200
    assert len(r.json()["members"]) == 2

    async with _client_for(transport, colleague) as colleague_client:
        r = await colleague_client.get(f"/reports/team/{team_id}")
        assert r.status_code == 200
        assert r.json()["team_name"] == "Lake Team"
        r = await colleague_client.post(
            f"/teams/{team_id}/members",
            json={"email": "outsider@example.com"},
        )
        assert r.status_code == 403

    async with _client_for(transport, outsider) as outsider_client:
        assert (await outsider_client.get(f"/teams/{team_id}")).status_code == 403
        assert (
            await outsider_client.get(f"/reports/team/{team_id}")
        ).status_code == 403


@pytest.mark.asyncio
async def test_team_owner_cannot_be_removed(ctx):
    client, _, agent, _, _ = ctx
    r = await client.post("/teams", json={"name": "Owner Protection"})
    team_id = r.json()["id"]

    r = await client.delete(f"/teams/{team_id}/members/{agent.id}")
    assert r.status_code == 400
