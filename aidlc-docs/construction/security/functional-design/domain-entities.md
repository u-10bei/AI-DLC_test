# ドメインエンティティ / モデル型 — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Functional Design（ユニット 6 / 8）

---

## 1. U-06 が新規定義する型（`src/security/`）

U-06 は業務ドメイン型（Staff, Event 等）を扱わない。**セキュリティ固有の型のみ**を定義する。**すべて個人情報を含まない**。

### 1.1 主体とロール

```text
Role = Enum:
    COORDINATOR = "COORDINATOR"      # 担当者。本 PoC の唯一のロール（Q1=A）
    # 将来: STAFF（職員本人ログイン, A-08）、ADMIN（実運用の管理者 + MFA, U06-H5）

@frozen
Principal:
    user_id: UserId        # 利用者 ID（NewType[str]）。氏名を持たない
    role: Role
```

**`Principal` は氏名を持たない**（SECURITY-03）。利用者 ID とロールのみ。

### 1.2 アカウントとセッション

```text
@frozen
Account:
    user_id: UserId
    password_hash: str      # 適応型ハッシュ（BR-SEC03）。平文を保持しない
    role: Role
    failed_attempts: int = 0
    locked: bool = False

@frozen
Session:
    id: SessionId           # 不透明なランダム値（NewType[str]）
    principal: Principal
    issued_at: datetime     # UTC
    expires_at: datetime    # UTC

    def is_expired(now) -> bool
```

**`Account.password_hash` はハッシュのみ**。`__repr__` はハッシュを伏せる（秘密情報の非露出, SECURITY-06）。

### 1.3 認可の決定

```text
@frozen
AuthorizationDecision:
    allowed: bool
    reason: str | None = None     # 拒否理由（PII なし、監査用）
```

**deny by default**: 生成の既定は拒否側（BR-SEC08）。

### 1.4 監査イベント

```text
AuditAction = Enum:
    LOGIN_SUCCESS / AUTH_FAILURE / AUTHZ_DENIED / PRIVILEGE_ESCALATION_ATTEMPT
    ASSIGNMENT_CREATED / ASSIGNMENT_CHANGED
    MASTER_CHANGED / MASTER_DELETED
    IP_REJECTED / RATE_LIMITED

@frozen
AuditEvent:
    timestamp: datetime            # UTC（BR-SEC19）
    actor: UserId | None           # 未認証なら None
    action: AuditAction
    event_id: EventId | None = None
    staff_id: StaffId | None = None
    facility_id: FacilityId | None = None
    before: dict[str, str] | None = None    # 変更前（ID のみ, FR-07.1）
    after: dict[str, str] | None = None     # 変更後（ID のみ）
    detail: str | None = None               # PII なし

    def to_json_line() -> str
```

**PII 除外の構造的保証（BR-SEC16, U01-H22）**: `AuditEvent` は**氏名・居住小学校区・`reason_category` を格納するフィールドを持たない**。ID と列挙値のみ。型として PII を入れられない。

---

## 2. ポート（U-06 が定義）

```text
SessionStorePort (Protocol):          # 実装は U-07 が注入（Q2=A, U06-H2）
    def find_account(user_id) -> Account | None
    def save_account(account) -> None          # 失敗回数・ロック状態の更新
    def save_session(session) -> None
    def find_session(session_id) -> Session | None
    def delete_session(session_id) -> None     # ログアウト（即時失効）

PasswordHasherPort (Protocol):        # 製品は NFR Requirements（U06-H1）
    def hash(password: str) -> str
    def verify(password: str, password_hash: str) -> bool

AuditLogPort (Protocol):              # P-04。実装 A-05 は U-06 が保有
    def append(event: AuditEvent) -> None

ConfigPort (Protocol):                # 設定の供給（U-07 が注入）
    def ip_allowlist() -> tuple[str, ...]
    def session_ttl_seconds() -> int
    def lock_threshold() -> int
    def rate_limit_per_minute() -> int
```

**`SessionStorePort` の実装が U-07 側にある**ことで、U-06 は U-03 に依存せずセッションを永続化できる（Q2=A）。**MU-02 の `sanitize_csv_cell` を U-07 が U-03 に注入する構造と同型**である。

---

## 3. 新規例外（U-01 の `DomainError` を継承、PII なし）

| 例外 | 用途 |
|------|------|
| **`AuthenticationFailedError`** | 認証失敗（汎用メッセージ, BR-SEC04）。利用者名の存在有無を漏らさない |
| **`AccountLockedError`** | アカウントロック中（MU-03）。応答は汎用に丸める（U-07） |
| **`AuthorizationDeniedError`** | 認可拒否（BR-SEC08）。文脈は主体 ID・アクション・対象 ID のみ |
| **`IpNotAllowedError`** | 送信元 IP が許可リスト外（US-02） |
| **`RateLimitExceededError`** | レート制限超過（NFR-S09） |

**すべて個人情報を含まない**（文脈は ID・列挙値のみ, SECURITY-03/09）。

---

## 4. U-01 の型との関係

| 型 | 用途 |
|----|------|
| `DomainError` | 上記例外の基底 |
| `StaffId` / `EventId` / `FacilityId` | 監査イベントの対象 ID |

U-06 は `Staff` / `Event` などの**業務エンティティを import しない**——監査には ID しか要らず、業務型を持ち込むと氏名が届いてしまう。**PII が構造的に U-06 へ入らない**（U-01 NFR Design の「lint 契約で security を Staff から遠ざける」多層防御と整合）。

---

## 5. データフロー

```text
HTTP 要求 ─(U-07 ミドルウェア)─▶ SEC-03 ──▶ SEC-04 ──▶ SEC-01 ──▶ SEC-02 ──▶ SEC-05 ──▶ 業務
   ip           allowlist(Config)  RateLimiter  Session    Principal   sanitize
                     │                 │        StorePort   Decision      │
                     └────────┬────────┴───────────┬───────────┘          │
                              ▼                    ▼                      ▼
                         S-08 AuditService ──(P-04 AuditLogPort)──▶ A-05 追記専用ファイル
                                                                    （JSON Lines, chattr +a）
```

---

## 6. 後続への申し送り

business-logic-model.md 9 節（U06-H1〜H6）を参照。本ステージで新規の型定義申し送りは以下。

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U06-H7（新規）** | `Principal`, `Account`, `Session`, `Role`, `AuditEvent`, `AuthorizationDecision` と各ポート・例外を `src/security/` に定義（frozen, PII フィールドを持たない）| U-06 Code Generation |
| **U06-H8（新規）** | `UserId`, `SessionId` は `NewType[str]`。U-01 の識別子群とは別に U-06 が定義する（U-01 は利用者アカウントを知らない）| U-06 Code Generation |
