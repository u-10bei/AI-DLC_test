# Logical Components — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Design（ユニット 6 / 8）
**回答**: Q5=A

---

## 概要

U-06 の論理コンポーネントは **7 つ**（SEC-01〜05 + S-08 + A-05）。すべて `src/security/` 配下。**プロダクション依存は `argon2-cffi` 1 つのみ**。

```text
   U-07 がミドルウェアとして配線（順序は Application Design 準拠）
   ┌──────────────────────────────────────────────────────────┐
   │  LC-03 IpAllowlist  →  LC-04 RateLimiter  →  LC-01 Authenticator │
   │      (SEC-03)             (SEC-04)              (SEC-01)         │
   │                                                    ↓              │
   │                          LC-02 Authorizer  →  LC-05 InputSanitizer│
   │                              (SEC-02)             (SEC-05)        │
   └──────────────────────────────────────────────────────────┘
        すべて拒否は例外（DP-01）
                          │
                          ▼
              LC-06 AuditService (S-08)
                          │ AuditLogPort (P-04)
                          ▼
              LC-07 AppendOnlyFileAuditLog (A-05)
                  JSON Lines, chattr +a, flush 毎回

   注入されるポート:  SessionStorePort（U-07 が U-03 実装を注入）
                     PasswordHasherPort（U-06 の Argon2 実装が既定）
   注入される設定:    SecurityConfig（frozen dataclass）
```

---

## LC-01: Authenticator（SEC-01）

| 項目 | 内容 |
|------|------|
| 責務 | ログイン、パスワード検証、セッション発行・検証・失効、失敗記録・ロック |
| 依存 | `SessionStorePort`（注入）、`PasswordHasherPort`、`SecurityConfig` |
| 拒否 | `AuthenticationFailedError`（汎用）、`AccountLockedError`（応答は U-07 が汎用化）|
| タイミング対策 | 存在しない/ロック中もダミー検証（DP-02）|
| セッション ID | `secrets.token_urlsafe(32)`（CSPRNG）|

---

## LC-02: Authorizer（SEC-02）

| 項目 | 内容 |
|------|------|
| 責務 | ロール判定 + **オブジェクトレベル認可の関門**（MU-01/IDOR）|
| API | `authorize(...) -> AuthorizationDecision`（監査用）、**`require_authorization(...)`（拒否で例外）= 通常の呼び口** |
| 既定 | **deny by default**（未知のロール・アクション・判定不能は拒否）|
| 拡張点 | 将来（A-08）に「職員は自分の申告のみ」へ絞る |

---

## LC-03: IpAllowlist（SEC-03）

| 項目 | 内容 |
|------|------|
| 責務 | 庁内出口 IP の許可判定（US-02, NFR-S10.2）|
| 実装 | 標準ライブラリ `ipaddress`（**CIDR 対応**）|
| 設定 | `SecurityConfig.ip_allowlist`（外部化, NFR-M03）|
| 拒否 | `IpNotAllowedError`（DP-01）。監査記録 |

---

## LC-04: RateLimiter（SEC-04）

| 項目 | 内容 |
|------|------|
| 責務 | レート制限（NFR-S09, MU-03）|
| 実装 | **インメモリ固定ウィンドウ**（`(ip, kind, 分) -> 件数`, DP-04）。古いウィンドウを掃除 |
| 上限 | 一般 60 / ログイン 5 req/分/IP（`SecurityConfig`）|
| 拒否 | `RateLimitExceededError`。監査記録 |
| 性質 | 境界バースト（最大 2 倍）を許す（明記, U06-H12）|

---

## LC-05: InputSanitizer（SEC-05）

| 項目 | 内容 |
|------|------|
| 責務 | `sanitize_csv_cell`（MU-02）+ 再利用可能な検証関数 |
| 純粋性 | 純関数（状態を持たない）|
| 注入先 | **U-07 が U-03 `serialize_csv` / U-05 `export_report_csv` に注入**（U03-H5, U06-H3）|

---

## LC-06: AuditService（S-08）

| 項目 | 内容 |
|------|------|
| 責務 | `AuditEvent` の組み立てと記録（FR-07, SECURITY-13/14）|
| 依存 | `AuditLogPort`（P-04）、`SecurityConfig` |
| PII | **`AuditEvent` に PII フィールドが無い**（型による保証, DP-07）|
| 位置 | **業務トランザクションの外側**（BR-SEC18）|

---

## LC-07: AppendOnlyFileAuditLog（A-05）

| 項目 | 内容 |
|------|------|
| 責務 | `AuditLogPort` の実装。JSON Lines を追記専用ファイルへ |
| 実装 | イベントごとに追記 open → 1 行 → **flush** → close（DP-03）|
| 保護 | `chattr +a`（OS）。アプリは削除・改変不可（MU-04）。ローテーションは特権 cron（U06-H6）|
| 所有 | **U-06 が保有**（OS ファイルであり DB 依存がないため、U-03 に依存しない）|

---

## ポートと設定

| ポート / 設定 | 定義 | 実装・供給 |
|--------------|------|-----------|
| **`SessionStorePort`** | U-06 | **U-07 が注入**（U-03 の `sessions`, U03-H3, U06-H2）。**`sqlalchemy` 禁止により U-06 自身は実装不可能**（DP-06）|
| **`PasswordHasherPort`** | U-06 | **U-06 が Argon2 実装を保有**（`argon2-cffi`）。DB 依存なし |
| **`AuditLogPort`**（P-04）| U-06 | **U-06 が A-05 を保有**（LC-07）|
| **`SecurityConfig`**（Q5=A）| U-06 | **frozen dataclass**（Protocol ではない——設定は値であり振る舞いを持たない）。TTL・ロック閾値・レート上限・IP 許可リストを保持（NFR-M03）。U-07 が供給 |

---

## 該当しない論理コンポーネント（Q5=A、N/A）

| コンポーネント | 判定 | 根拠 |
|--------------|:----:|------|
| メッセージキュー | **N/A** | U-06 は同期的な関門 |
| 外部キャッシュ / セッションストア製品（Redis 等）| **N/A** | セッションは注入されるポート（U-03 の DB）。単一サーバー |
| サーキットブレーカ / リトライ | **N/A** | fail closed |
| スケールアウト層 | **N/A** | 単一ワーカー（A-07）。インメモリのレート制限で足りる |

---

## 依存とポート整合

- U-06 は **`shared_kernel` のみ**を（ユニットとして）import する
- 第三者は **`argon2-cffi` のみ**許可。**`sqlalchemy` / `pydantic` / `fastapi` を禁止**
- **`sqlalchemy` 禁止が `SessionStorePort` 注入設計を構造的に強制する**（DP-06、非空虚性は U06-H10 で確認）
- U-06 は業務エンティティ（`Staff` 等）を import しない → **PII が届かない**（DP-07）
- U-07 がミドルウェアを **SEC-03 → SEC-04 → SEC-01 → SEC-02 → SEC-05** の順で配線（U06-H4）

---

## 拡張ルール適合サマリ（論理コンポーネント観点）

| ルール | 判定 | 根拠 |
|--------|------|------|
| SECURITY-15（fail closed）| ✅ | 全 LC が例外で拒否（DP-01）|
| SECURITY-14（監査保護）| ✅ | LC-07（追記専用 + flush）|
| SECURITY-11（分離 + レート制限）| ✅ | LC-01/LC-02 は専用モジュール、LC-04 |
| SECURITY-03（PII 非露出）| ✅ | LC-06 の `AuditEvent` に PII フィールドなし |
| SECURITY-06（秘密情報）| ✅ | LC-01（CSPRNG、repr 伏せ）|
| Scalability / Resilience | N/A | Q5=A |

**ブロッキング所見: なし**
