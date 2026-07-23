"""Test support for U-07 — the real app, over the real HTTP boundary.

Nothing is mocked. Middleware order, DTO validation, the exception handlers and the
security headers only exist as HTTP behaviour, so they can only be tested through
HTTP (NFR Req Q5=A).

Two deliberate details:

  * base_url is https, because the session cookie is Secure and httpx correctly
    refuses to send a Secure cookie over plain http. Using http here would "fail"
    for the right reason and teach us nothing.
  * the client presents X-Forwarded-For and "testclient" is configured as a trusted
    proxy, mirroring the real deployment behind the exposure platform.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from api_orchestration import AppConfig, build_application
from api_orchestration.session_store import SqlSessionStore
from data_management import create_all, create_db_engine
from security import Account, Argon2PasswordHasher, Role, SecurityConfig
from security.identifiers import UserId

NOW = datetime(2026, 7, 17, 9, 0, tzinfo=UTC)
USER = "C001"
PASSWORD = "coordinator-password"  # noqa: S105
ALLOWED_IP = "203.0.113.5"
DENIED_IP = "198.51.100.9"
BASE_URL = "https://testserver"

DISTRICTS_CSV = "小学校区ID,名称,緯度,経度\nSD1,近い,35.00,139.00\nSD2,遠い,35.50,139.50\n".encode()
STAFF_CSV = (
    "職員ID,氏名,所属部署ID,職種,役職,居住小学校区ID,資格\n"
    "S1,山田,D1,事務職,一般職,SD1,\n"
    "S2,鈴木,D1,事務職,管理職,SD2,\n"
    "S3,佐藤,D1,事務職,一般職,SD1,\n"
).encode()
FACILITY_CSV = "施設ID,名称,小学校区ID,必要人数,資格要件\nF1,避難所A,SD1,2,\n".encode()
DECLARATIONS_CSV = (
    "職員ID,従事可否,申告日時,理由区分,その他理由\n"
    "S1,可,2026-07-01 09:00:00,,\n"
    "S2,可,2026-07-01 09:00:00,,\n"
    "S3,可,2026-07-01 09:00:00,,\n"
).encode()


@dataclass
class Harness:
    app_config: AppConfig
    engine: Engine
    client: TestClient  # allowed source IP
    denied_client: TestClient  # source IP outside the allowlist


def make_config(audit_dir: Path, **overrides: object) -> AppConfig:
    security = SecurityConfig(
        ip_allowlist=("203.0.113.0/24",),
        argon2_memory_kib=8,  # tiny: tests must not spend seconds hashing
        argon2_time_cost=1,
        argon2_parallelism=1,
    )
    base: dict[str, object] = {
        "database_url": "sqlite://",
        "audit_log_path": audit_dir / "audit.jsonl",
        "security": security,
        "trusted_proxies": ("testclient",),  # TestClient's peer name
    }
    base.update(overrides)
    return AppConfig(**base)  # type: ignore[arg-type]


def build_harness(**config_overrides: object) -> Harness:
    audit_dir = Path(tempfile.mkdtemp())
    config = make_config(audit_dir, **config_overrides)
    engine = create_db_engine(config.database_url)
    create_all(engine)
    app = build_application(config, engine=engine, clock=lambda: NOW)

    SqlSessionStore(engine).save_account(
        Account(
            user_id=UserId(USER),
            password_hash=Argon2PasswordHasher(config.security).hash(PASSWORD),
            role=Role.COORDINATOR,
        )
    )
    return Harness(
        app_config=config,
        engine=engine,
        client=TestClient(app, base_url=BASE_URL, headers={"X-Forwarded-For": ALLOWED_IP}),
        denied_client=TestClient(app, base_url=BASE_URL, headers={"X-Forwarded-For": DENIED_IP}),
    )


def login(harness: Harness) -> TestClient:
    response = harness.client.post("/sessions", json={"user_id": USER, "password": PASSWORD})
    assert response.status_code == 204, response.text
    return harness.client


def seed_masters(harness: Harness) -> None:
    """Master data an optimisation needs, seeded through U-03 directly.

    Only the staff master has an import endpoint in this PoC surface, so districts
    and facilities are loaded through the same services the API would use.
    """
    from data_management import MasterDataService
    from shared_kernel import Department, DepartmentId

    master = MasterDataService(harness.engine)
    master.save_departments([Department(id=DepartmentId("D1"), name="総務課")])
    master.import_school_districts(DISTRICTS_CSV)
    master.import_staff(STAFF_CSV)
    master.import_facilities(FACILITY_CSV)


def seed_event(client: TestClient, event_id: str = "E1") -> None:
    response = client.post(
        "/events",
        json={
            "id": event_id,
            "type": "災害時避難所応援",
            "name": "訓練",
            "scheduled_date": "2026-08-01",
        },
    )
    assert response.status_code == 201, response.text


__all__ = [
    "ALLOWED_IP",
    "BASE_URL",
    "DECLARATIONS_CSV",
    "DENIED_IP",
    "DISTRICTS_CSV",
    "FACILITY_CSV",
    "NOW",
    "PASSWORD",
    "STAFF_CSV",
    "USER",
    "Harness",
    "build_harness",
    "login",
    "make_config",
    "seed_event",
    "seed_masters",
]
