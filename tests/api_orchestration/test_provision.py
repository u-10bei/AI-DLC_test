"""Account provisioning CLI (W-3, G-3).

The end-to-end property that matters: an account created by the CLI can actually
log in through the real HTTP boundary. Provisioning that produces a hash the
application cannot verify would be worse than no tool at all — the failure would
only appear at the training session.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_orchestration import build_application
from api_orchestration.provision import main as provision_main
from data_management import create_all, create_db_engine

from .support import ALLOWED_IP, BASE_URL, NOW, make_config


def _env(monkeypatch: pytest.MonkeyPatch, db_path: Path) -> None:
    monkeypatch.setenv("AIDLC_DATABASE_URL", f"sqlite:///{db_path}")
    # tiny Argon2 parameters: the test must not spend seconds hashing
    monkeypatch.setenv("AIDLC_ARGON2_MEMORY_KIB", "8")
    monkeypatch.setenv("AIDLC_ARGON2_TIME_COST", "1")
    monkeypatch.setenv("AIDLC_ARGON2_PARALLELISM", "1")


def test_provisioned_account_can_actually_log_in(monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = Path(tempfile.mkdtemp()) / "app.db"
    _env(monkeypatch, db_path)
    engine = create_db_engine(f"sqlite:///{db_path}")
    create_all(engine)

    monkeypatch.setattr("getpass.getpass", lambda *_: "training-password")
    assert provision_main(["--user-id", "C001", "--role", "COORDINATOR"]) == 0

    config = make_config(Path(tempfile.mkdtemp()), database_url=f"sqlite:///{db_path}")
    app = build_application(config, engine=engine, clock=lambda: NOW)
    client = TestClient(app, base_url=BASE_URL, headers={"X-Forwarded-For": ALLOWED_IP})

    response = client.post("/sessions", json={"user_id": "C001", "password": "training-password"})
    assert response.status_code == 204, response.text


def test_duplicate_user_id_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = Path(tempfile.mkdtemp()) / "app.db"
    _env(monkeypatch, db_path)
    create_all(create_db_engine(f"sqlite:///{db_path}"))

    monkeypatch.setattr("getpass.getpass", lambda *_: "training-password")
    assert provision_main(["--user-id", "C001"]) == 0
    assert provision_main(["--user-id", "C001"]) == 1  # second time: refused


def test_generated_password_is_printed_once_and_works(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = Path(tempfile.mkdtemp()) / "app.db"
    _env(monkeypatch, db_path)
    engine = create_db_engine(f"sqlite:///{db_path}")
    create_all(engine)

    assert provision_main(["--user-id", "C002", "--generate-password"]) == 0
    printed = capsys.readouterr().out
    assert "生成されたパスワード:" in printed
    password = printed.split("生成されたパスワード:")[1].splitlines()[0].strip()

    config = make_config(Path(tempfile.mkdtemp()), database_url=f"sqlite:///{db_path}")
    app = build_application(config, engine=engine, clock=lambda: NOW)
    client = TestClient(app, base_url=BASE_URL, headers={"X-Forwarded-For": ALLOWED_IP})
    assert client.post("/sessions", json={"user_id": "C002", "password": password}).status_code == 204


def test_mismatched_confirmation_aborts(monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = Path(tempfile.mkdtemp()) / "app.db"
    _env(monkeypatch, db_path)
    create_all(create_db_engine(f"sqlite:///{db_path}"))

    answers = iter(["first", "second"])
    monkeypatch.setattr("getpass.getpass", lambda *_: next(answers))
    with pytest.raises(SystemExit):
        provision_main(["--user-id", "C003"])
