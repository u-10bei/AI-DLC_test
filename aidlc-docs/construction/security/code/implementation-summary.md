# Code Generation Implementation Summary — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Code Generation（ユニット 6 / 8）
**結果**: 4 ゲートすべて green。**SECURITY 拡張の実体を実装**し、**設計の強制を実証**

---

## 1. 生成物

### 新規アプリコード（`src/security/`、13 ファイル）

| ファイル | 役割 | LC |
|---------|------|----|
| `identifiers.py` | `UserId`, `SessionId`（NewType）| - |
| `exceptions.py` | `SecurityError` 基底 + 4 例外（**PII なし**）| - |
| `config.py` | frozen `SecurityConfig`（**既定の許可リストは空 = 全拒否**）| - |
| `entities.py` | `Role`/`Principal`/`Account`/`Session`/`AuthorizationDecision`（**repr で秘密を伏せる**）| - |
| `ports.py` | `SessionStorePort`（U-07 注入）, `PasswordHasherPort` | - |
| `hasher.py` | `Argon2PasswordHasher`（Argon2id）| - |
| `audit.py` | `AuditAction`/`AuditEvent`（**PII フィールドなし**）/`AuditLogPort`/`AuditService` | LC-06 |
| `audit_adapter.py` | `AppendOnlyFileAuditLog`（追記 + flush）| LC-07/A-05 |
| `authentication.py` | `Authenticator`（ダミー検証・ロック・即時失効）| LC-01/SEC-01 |
| `authorization.py` | `Authorizer`（`require_authorization` は例外）| LC-02/SEC-02 |
| `network.py` | `IpAllowlist`（CIDR, 不正 IP は拒否）| LC-03/SEC-03 |
| `rate_limit.py` | `RateLimiter`（固定ウィンドウ）| LC-04/SEC-04 |
| `sanitizer.py` | `sanitize_csv_cell`（MU-02）| LC-05/SEC-05 |

### in-place 修正

| ファイル | 変更 |
|---------|------|
| `pyproject.toml` | `argon2-cffi==23.1.0` 追加（固定, U06-H9）、wheel packages に `security` |
| `.importlinter` | **R-7**（`shared_kernel` のみ）+ **`security cannot persist anything`**（`sqlalchemy`/`alembic`/`pydantic`/`fastapi` 禁止）|

### 新規テスト（`tests/security/`）

`support.py`（インメモリ `SessionStorePort` + 軽量 Argon2）、`test_examples.py`（21 例）、`test_properties.py`（P-SEC01〜09）、**`test_stateful.py`（PBT-06）**

---

## 2. ⭐ 設計の強制を実証（本ユニットの中核）

**`import sqlalchemy` を `security` に注入すると、契約が BROKEN になる**ことを確認した:

```text
security cannot persist anything (SessionStorePort must be injected)  BROKEN
security is not allowed to import sqlalchemy:
-   security.authentication -> sqlalchemy
```

これは単なる契約チェックではない。**「U-06 はセッションを自分で DB に書けない」という NFR Design Q2=A の決定が、意図ではなく構造として保証されている**ことの実証である。将来の開発者が「ここに簡単なクエリを足す」ことはビルドが拒否する。

同様に **R-7 + U-01 の R-2** により、**PII は双方向に移動できない**——U-06 は `Staff` を見ることがなく、氏名が監査ログに届く経路が存在しない。

---

## 3. 4 ゲートの結果

| ゲート | 結果 |
|-------|------|
| `pytest` | **150 passed**（U-01〜U-05 の 119 + U-06 の 31。回帰なし）|
| `mypy --strict` | **clean（84 files）**。`argon2-cffi` は py.typed 付きのため override 不要 |
| `ruff` | **clean** |
| `lint-imports` | **12 契約 kept**。**`import sqlalchemy` 注入で BROKEN**（非空虚性確認）|

---

## 4. 実装した防御と検証

| 防御 | 実装 | テスト |
|------|------|-------|
| **US-01 未認証遮断** | セッション検証、deny by default | 未知/期限切れ/ログアウト後は必ず拒否（P-SEC01/03 + ステートフル）|
| **US-02 IP 制限** | `ipaddress` CIDR、**不正 IP も空許可リストも拒否** | P-SEC02（`203.0.113.0/24` のみ通過）|
| **US-03 割当変更の監査** | `AuditEvent`（before/after は ID のみ）| JSON Lines 検証 |
| **US-04 監査改竄防止** | 追記 + flush、`chattr +a` 前提 | 監査行数・パスワード非含有 |
| **MU-01 IDOR** | オブジェクトレベル認可の関門必須 | 未知アクションは拒否（deny by default）|
| **MU-02 CSV 注入** | `sanitize_csv_cell` | P-SEC05（結果は決して数式文字で始まらない）/ P-SEC06（不動点）|
| **MU-03 総当たり** | ロック + レート制限 + ダミー検証 | **ロック中は正しいパスワードでも拒否**、レート上限 |
| **MU-04 監査隠蔽** | OS 追記専用（アプリに削除権限なし）| 追記のみ |
| **タイミング攻撃** | 不在・ロック中もダミー Argon2 検証 | 未知/誤りの応答が同一 |

**PBT-06 ステートフルテスト**: セッション（発行→検証→ログアウト/期限切れ→拒否）とロック（蓄積→ロック→解除）のランダム操作列で、**「モデルが有効と言うときのみ authenticate が成功する」**を不変条件として検証。

---

## 5. 計画からの特記

1. **`AccountLockedError` を実装しなかった**（計画では定義予定）: ロック状態を例外型で表すと、U-07 が汎用化を**忘れうる**。`login` は常に汎用 `AuthenticationFailedError` を投げ、真の理由は監査ログにのみ残す——**構造で守る**方針と整合（BR-SEC04）
2. **`Role` の到達不能分岐**: mypy が「`COORDINATOR` しかないため deny 分岐が到達不能」と正しく指摘。**集合 `_UNRESTRICTED_ROLES` による判定**に変更し、将来ロール用の deny-by-default を実際に残した
3. **`argon2-cffi` は py.typed 付き**のため、U-04 の ortools と違い mypy override は不要だった
4. **テストの `make_config`**: `test_` 接頭辞だと pytest が収集してしまうため改名

---

## 6. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| U06-H1/H7/H8/H9/H10/H11（解決）| ハッシュ・型・依存・契約・ダミーハッシュ | （完了）|
| **U06-H2** | `SessionStorePort` の DB 実装を **U-07 が注入**（U-03 の `sessions`）| U-07 |
| **U06-H3** | `sanitize_csv_cell` を U-03/U-05 の CSV 出力に **U-07 が注入** | U-07 |
| **U06-H4** | ミドルウェア順序 **SEC-03→04→01→02→05** を U-07 が配線。例外を汎用応答へ変換 | U-07 |
| **U06-H5** | **アプリ内に管理者ロールなし**。実運用では管理者ロール + MFA（SECURITY-12）が必須 | 実運用移行時 |
| **U06-H6** | `chattr +a` 付与・ext4/XFS・**アプリが `chattr` 不可**・ローテーション cron | インフラ / 運用 |
| U06-H12 | 固定ウィンドウの境界バースト（最大 2 倍）| 運用 / 将来 |

---

## 7. 拡張ルール適合サマリ

| ルール | 判定 |
|--------|------|
| SECURITY-03（PII 非露出）| ✅ `AuditEvent` に PII フィールドなし。業務型を import しない |
| SECURITY-06（秘密情報）| ✅ CSPRNG、repr 伏せ、監査にパスワード非記録（テスト確認）|
| SECURITY-07（境界）| ✅ IP 許可リスト（代償統制）|
| SECURITY-08（既定で認証・認可）| ✅ deny by default、関門は例外 |
| SECURITY-09（情報漏洩）| ✅ 汎用メッセージ + **タイミング均一化** |
| SECURITY-10（サプライチェーン）| ✅ `argon2-cffi` 固定 |
| SECURITY-11（分離 + レート制限）| ✅ 専用モジュール、レート制限 |
| SECURITY-12（ハッシュ + MFA）| ✅ Argon2id。**MFA は管理者アカウント不在のため N/A**（U06-H5）|
| SECURITY-13/14（監査）| ✅ before/after、追記専用 |
| SECURITY-15（fail closed）| ✅ 関門は例外、空許可リストは全拒否、未注入も拒否 |
| PBT-01〜10 | ✅ P-SEC01〜09 + **PBT-06 ステートフル** |
| Resiliency | スキップ（無効）|

**ブロッキング所見: なし**
