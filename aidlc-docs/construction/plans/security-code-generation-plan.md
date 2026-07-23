# Code Generation Plan — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Code Generation（ユニット 6 / 8）
**このプランが Code Generation の唯一の正典である。**

---

## 1. ユニットコンテキスト

| 項目 | 内容 |
|------|------|
| ユニット | U-06 `security`（`src/security/`）|
| 依存 | **U-01 `shared_kernel` のみ** |
| ストーリー | US-01（未認証遮断）、US-02（IP 制限）、US-03（割当変更の監査）、US-04（監査ログ改竄防止）|
| 悪用ケース | MU-01（IDOR）、MU-02（CSV 注入）、MU-03（総当たり）、MU-04（監査隠蔽）|
| プロダクション依存 | `argon2-cffi==23.1.0`（**検証済み**）のみ。他は標準ライブラリ |

### 1.1 コンポーネント → ファイル

| 論理コンポーネント | ファイル |
|------------------|---------|
| 識別子（U06-H8）| `src/security/identifiers.py`（`UserId`, `SessionId`）|
| 例外（DP-01）| `src/security/exceptions.py` |
| 設定（Q5）| `src/security/config.py`（frozen `SecurityConfig`）|
| 型（U06-H7）| `src/security/entities.py`（`Role`, `Principal`, `Account`, `Session`, `AuthorizationDecision`）|
| ポート | `src/security/ports.py`（`SessionStorePort`, `PasswordHasherPort`, `AuditLogPort`）|
| ハッシュ | `src/security/hasher.py`（`Argon2PasswordHasher`）|
| 監査（LC-06）| `src/security/audit.py`（`AuditAction`, `AuditEvent`, `AuditService`）|
| 監査アダプタ（LC-07/A-05）| `src/security/audit_adapter.py`（`AppendOnlyFileAuditLog`）|
| SEC-01（LC-01）| `src/security/authentication.py`（`Authenticator`）|
| SEC-02（LC-02）| `src/security/authorization.py`（`Authorizer`）|
| SEC-03（LC-03）| `src/security/network.py`（`IpAllowlist`）|
| SEC-04（LC-04）| `src/security/rate_limit.py`（`RateLimiter`）|
| SEC-05（LC-05）| `src/security/sanitizer.py`（`sanitize_csv_cell`）|

---

## 2. 設計上の制約（成果物から）

- **DP-01 関門は例外で拒否**: `check_source_ip` / `check_rate_limit` / `authenticate` は拒否時に例外。`Authorizer.authorize` は `AuthorizationDecision` を返すが **`require_authorization` は例外**
- **DP-02 ダミー検証**: 利用者不在・ロック中も `DUMMY_HASH` に対し Argon2 検証を実行（U06-H11）
- **DP-03 監査**: イベントごとに追記 open → 1 行 JSON → **flush** → close
- **DP-04 レート制限**: `(ip, kind, 分)` の固定ウィンドウ。古いウィンドウを掃除
- **DP-05 秘密情報**: `secrets.token_urlsafe(32)`、`hmac.compare_digest`、`__repr__` で伏せる
- **DP-07 PII 非露出**: `AuditEvent` に PII フィールドを持たせない。**業務エンティティを import しない**
- **時刻は引数で注入**（`now: datetime`）——テストの決定性のため。`datetime.now()` を内部で呼ばない

---

## 3. 生成ステップ（順次、完了ごとに [x]）

### Step 1: 構造と依存
- [x] `src/security/__init__.py`, `tests/security/__init__.py`
- [x] `pyproject.toml`: `dependencies` に `argon2-cffi==23.1.0` 追加、wheel packages に `security` 追加（U06-H9, SECURITY-10）
- **ストーリー**: 基盤

### Step 2: 識別子と例外（U06-H7/H8, DP-01）
- [x] `identifiers.py`: `UserId`, `SessionId`（`NewType[str]`）
- [x] `exceptions.py`: `AuthenticationFailedError`, `AccountLockedError`, `AuthorizationDeniedError`, `IpNotAllowedError`, `RateLimitExceededError`（`DomainError` 継承、**PII なし**）
- **ストーリー**: US-01, US-02

### Step 3: 設定 `config.py`（Q5）
- [x] frozen `SecurityConfig`: `ip_allowlist`（CIDR 文字列）、`session_ttl_seconds`(28800)、`lock_threshold`(5)、`lock_duration_seconds`(900)、`rate_limit_per_minute`(60)、`login_rate_limit_per_minute`(5)
- **ストーリー**: 基盤（NFR-M03）

### Step 4: 型 `entities.py`（U06-H7, DP-05）
- [x] `Role`（`COORDINATOR`。将来 STAFF/ADMIN）
- [x] `Principal`（`user_id` + `role`、**氏名なし**）
- [x] `Account`（`user_id`, `password_hash`, `role`, `failed_attempts`, `locked_until`）。**`__repr__` でハッシュを伏せる**
- [x] `Session`（`id`, `principal`, `issued_at`, `expires_at`, `is_expired(now)`）。**`__repr__` で ID を伏せる**
- [x] `AuthorizationDecision`（`allowed`, `reason`）
- **ストーリー**: US-01, US-03

### Step 5: ポート `ports.py`
- [x] `SessionStorePort`（`find_account`, `save_account`, `save_session`, `find_session`, `delete_session`）——**U-07 が注入**（U06-H2）
- [x] `PasswordHasherPort`（`hash`, `verify`）
- [x] `AuditLogPort`（`append`）
- **ストーリー**: 基盤（依存逆転）

### Step 6: ハッシュ `hasher.py`（SECURITY-12）
- [x] `Argon2PasswordHasher`（`PasswordHasherPort` 実装）。`argon2-cffi` の `PasswordHasher`
- [x] パラメータは `SecurityConfig` 由来（本番 OWASP 推奨 / テスト軽量）
- [x] `verify` は誤りで `False` を返す（例外を握り潰さず変換）
- **ストーリー**: US-01

### Step 7: 監査 `audit.py`（LC-06, DP-07, U01-H22）
- [x] `AuditAction`（LOGIN_SUCCESS / AUTH_FAILURE / AUTHZ_DENIED / ASSIGNMENT_CREATED / ASSIGNMENT_CHANGED / MASTER_CHANGED / MASTER_DELETED / IP_REJECTED / RATE_LIMITED ...）
- [x] `AuditEvent`（frozen、**PII フィールドを持たない**: ts/actor/action/event_id/staff_id/facility_id/before/after/detail）、`to_json_line()`
- [x] `AuditService`（`AuditLogPort` を注入、`record(...)`）
- **ストーリー**: US-03

### Step 8: 監査アダプタ `audit_adapter.py`（LC-07/A-05, DP-03）
- [x] `AppendOnlyFileAuditLog`: イベントごとに `open(path, "a")` → 1 行 → **flush** → close
- [x] `chattr +a` と両立（追記モードのみ）。ディレクトリ作成はしない（運用が用意, U06-H6）
- **ストーリー**: US-04

### Step 9: SEC-01 `authentication.py`（LC-01, DP-01/02）
- [x] `Authenticator(store, hasher, audit, config)`
- [x] `login(username, password, now) -> Session`。**ダミー検証**（不在・ロック中, U06-H11）、失敗記録、ロック、汎用例外
- [x] `authenticate(session_id, now) -> Principal`。無効/期限切れは `AuthenticationFailedError`
- [x] `logout(session_id)`（即時失効）
- **ストーリー**: US-01, MU-03

### Step 10: SEC-02 `authorization.py`（LC-02, MU-01）
- [x] `Authorizer(audit)`。`authorize(principal, action, resource) -> AuthorizationDecision`
- [x] **`require_authorization(...)`（拒否で `AuthorizationDeniedError`）= 通常の呼び口**
- [x] **deny by default**（未知のロール・アクションは拒否）。拒否を監査
- **ストーリー**: US-01, MU-01

### Step 11: SEC-03/04 `network.py`, `rate_limit.py`（LC-03/04, DP-04）
- [x] `IpAllowlist(config)`: `check(ip)` → 非許可で `IpNotAllowedError`。`ipaddress` で **CIDR** 判定
- [x] `RateLimiter(config)`: `check(ip, kind, now)` → 超過で `RateLimitExceededError`。固定ウィンドウ + 掃除
- **ストーリー**: US-02, MU-03

### Step 12: SEC-05 `sanitizer.py`（LC-05, MU-02）
- [x] `sanitize_csv_cell(value)`: `=`, `+`, `-`, `@` 始まりに `'` を付す
- **ストーリー**: MU-02

### Step 13: `__init__.py` + リンタ契約（U06-H10）
- [x] 公開 API
- [x] `.importlinter`: `security` を root に追加。R-7: `shared_kernel` のみ許可、他ユニット禁止。第三者: `argon2` 許可、**`sqlalchemy` 禁止**、`pydantic`/`fastapi` 禁止
- [x] Step 15 で**非空虚性を確認**（**`import sqlalchemy` の混入で BROKEN**）
- **ストーリー**: 基盤（設計の強制）

### Step 14: テスト `tests/security/`
- [x] `support.py`（インメモリ `SessionStorePort` 実装、軽量 Argon2、一時ファイル監査ログ）
- [x] `test_examples.py`: 未認証拒否、IP 非許可拒否、レート超過、ロック、ログアウト即時失効、監査 JSON に PII なし、サニタイズ、`__repr__` の秘密伏せ
- [x] `test_properties.py`: P-SEC01〜09（**実ハッシュ**、モックしない）
- [x] `test_stateful.py`: **PBT-06** セッション/ロックの `RuleBasedStateMachine`（「失効後は必ず拒否」「ロック中は必ず拒否」）
- **ストーリー**: US-01〜US-04, MU-01〜MU-04

### Step 15: ドキュメント + 4 ゲート
- [x] `aidlc-docs/construction/security/code/implementation-summary.md`
- [x] `pytest`（U-01〜U-05 回帰なし + U-06 新規）
- [x] `mypy --strict`（clean）
- [x] `ruff`（clean）
- [x] `lint-imports`（全契約 kept）+ **非空虚性確認（`import sqlalchemy` → BROKEN）**
- [x] すべて green まで修正
- **ストーリー**: 品質ゲート

---

## 4. ストーリートレーサビリティ

| ストーリー / 悪用ケース | 実装ステップ |
|-----------------------|------------|
| US-01 未認証遮断 | Step 9, 10, 14 |
| US-02 IP 制限 | Step 11, 14 |
| US-03 割当変更の監査 | Step 7, 14 |
| US-04 監査ログ改竄防止 | Step 8, 14 |
| MU-01 IDOR | Step 10 |
| MU-02 CSV 注入 | Step 12 |
| MU-03 総当たり | Step 9, 11 |
| MU-04 監査隠蔽 | Step 8 |

---

## 5. 想定スコープ

- **新規アプリコード**: `src/security/`（13 ファイル）
- **修正（in-place）**: `pyproject.toml`, `.importlinter`
- **新規テスト**: `tests/security/`（support, examples, properties, **stateful**）
- **ドキュメント**: `implementation-summary.md`
- **15 ステップ**。4 ゲート green で完了

---

## 6. 完了基準

- 全 15 ステップ [x]、US-01〜US-04 / MU-01〜MU-04 実装
- 4 ゲート pass、**`import sqlalchemy` で契約が BROKEN になること**を確認（設計の強制を実証）
- U-01〜U-05 の既存テストが回帰しない
- 監査ログに PII が出ないことをテストで確認
- PBT-06 ステートフルテストで「失効後は必ず拒否」を確認
