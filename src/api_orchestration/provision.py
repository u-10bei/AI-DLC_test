"""W-3: account provisioning CLI (U06-H5, deployment blocker G-3).

    python -m api_orchestration.provision --user-id C001 --role COORDINATOR

Without this, a freshly deployed instance has no accounts and nobody can log in.
The application deliberately has no account-management UI (Q6=A at U-08 Functional
Design), so provisioning is an operational task — this is that task's tool.

The password is never taken from the command line (it would land in shell history
and in `ps` output). It is prompted for, or generated and printed once.

Hashing goes through U-06's Argon2id hasher, so provisioned accounts are identical
to what the application expects — no second hashing implementation.
"""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys

from data_management import create_db_engine
from security import Account, Argon2PasswordHasher, Role
from security.identifiers import UserId

from .session_store import SqlSessionStore
from .settings import load_config_from_env

_GENERATED_PASSWORD_BYTES = 18  # ~24 chars base64url


def _resolve_password(generate: bool) -> tuple[str, bool]:
    """Return (password, was_generated)."""
    if generate:
        return secrets.token_urlsafe(_GENERATED_PASSWORD_BYTES), True
    first = getpass.getpass("パスワード: ")
    if not first:
        raise SystemExit("パスワードが空です。中止しました。")
    second = getpass.getpass("パスワード(確認): ")
    if first != second:
        raise SystemExit("パスワードが一致しません。中止しました。")
    return first, False


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m api_orchestration.provision",
        description="利用者アカウントを払い出します(初期セットアップ用)。",
    )
    parser.add_argument("--user-id", required=True, help="ユーザーID")
    parser.add_argument(
        "--role",
        default=Role.COORDINATOR.name,
        choices=[role.name for role in Role],
        help="ロール(既定: COORDINATOR)",
    )
    parser.add_argument(
        "--generate-password",
        action="store_true",
        help="パスワードを自動生成して一度だけ表示する(対話入力の代わり)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    config = load_config_from_env()
    engine = create_db_engine(config.database_url)
    store = SqlSessionStore(engine)

    user_id = UserId(str(args.user_id))
    if store.find_account(user_id) is not None:
        print(f"エラー: ユーザーID '{user_id}' は既に存在します。", file=sys.stderr)
        return 1

    password, generated = _resolve_password(bool(args.generate_password))
    hasher = Argon2PasswordHasher(config.security)
    store.save_account(
        Account(
            user_id=user_id,
            password_hash=hasher.hash(password),
            role=Role[str(args.role)],
        )
    )

    print(f"アカウントを作成しました: {user_id} (ロール: {args.role})")
    if generated:
        # Printed once, never stored in plaintext. Hand it over securely.
        print(f"生成されたパスワード: {password}")
        print("※ この値は再表示できません。安全に控えてください。")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["main"]
