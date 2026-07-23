# ビジネスロジックモデル — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Functional Design（ユニット 6 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A, Q7=A

---

## 1. 概要

U-06 は **SECURITY 拡張ルールの実体**を担う。認証・認可・ネットワーク統制・レート制限・入力検証・監査を提供し、**U-01 にのみ依存**する。永続化が必要なもの（セッション）は**ポートとして定義し、U-07 が実装を注入**する（Q2、MU-02/SEC-05 と同型のパターン）。

```text
   HTTP 要求（U-07 が受ける）
        │
        ▼  U-07 がミドルウェアとして配線（Q6 の順序）
   SEC-03 IP 許可リスト   → 非許可なら拒否（US-02, NFR-S10.2）
        ▼
   SEC-04 レート制限      → 超過なら拒否（NFR-S09, MU-03）
        ▼
   SEC-01 認証            → 未認証なら拒否（US-01, deny by default）
        ▼                    ロック判定（MU-03）
   SEC-02 認可            → ロール + オブジェクトレベル（MU-01/IDOR）
        ▼
   SEC-05 入力検証        → 検証・サニタイズ（MU-02, SECURITY-05）
        ▼
   業務ロジック（U-03/U-04/U-05）
        │
        └─▶ S-08 AuditService ─(P-04 AuditLogPort)─▶ A-05 追記専用ファイル
                                                      （chattr +a, MU-04）
```

**すべての関門は deny by default / fail closed**（SECURITY-15）。

---

## 2. コンポーネント構成

| コンポーネント | 役割 | 依存 |
|--------------|------|------|
| **SEC-01 AuthenticationModule** | ログイン、パスワード検証（適応型ハッシュ）、セッション発行・検証・失効、失敗記録・ロック | `SessionStorePort`, `PasswordHasherPort` |
| **SEC-02 AuthorizationModule** | ロール判定 + **オブジェクトレベル認可の関門**（MU-01）| - |
| **SEC-03 NetworkControl** | 庁内出口 IP 許可リストの判定（US-02, NFR-S10.2）| `ConfigPort` |
| **SEC-04 RateLimiter** | インメモリのレート制限（NFR-S09, MU-03）| - |
| **SEC-05 InputValidation** | `sanitize_csv_cell`（MU-02）ほか再利用可能な検証関数 | - |
| **S-08 AuditService** | 監査イベントの組み立てと記録（FR-07, SECURITY-13/14）| `AuditLogPort` |
| **P-04 AuditLogPort** | 監査ログ追記の抽象ポート | - |
| **A-05 AppendOnlyFileAuditAdapter** | JSON Lines を追記専用ファイルへ（Q5）| - |

### 2.1 ポートと注入（Q2）

| ポート | 定義 | 実装 |
|-------|------|------|
| **`SessionStorePort`** | U-06 | **U-07 が注入**（U-03 の `sessions` テーブル, U03-H3）|
| **`PasswordHasherPort`** | U-06 | U-06 NFR Requirements で製品選定（Argon2/bcrypt）|
| **`AuditLogPort`**（P-04）| U-06 | **A-05（U-06 が保有）**——OS ファイルであり DB 依存がないため U-06 内で完結 |
| **`ConfigPort`** | U-06 | 設定（IP 許可リスト等）の供給。U-07 が注入 |

**依存規則の維持**: U-06 は U-03 に依存しない。セッション永続化は `SessionStorePort` の注入で実現する（**MU-02 で `sanitize_csv_cell` を U-07 が注入する構造と同型**）。

---

## 3. SEC-01 認証（Q1, Q2, Q6）

### 3.1 ロールとアカウント（Q1=A）

- **担当者（COORDINATOR）ロールのみ。アプリ内に管理者ロールを設けない**
- アカウント発行は**運用作業**（OS 権限を持つ運用者による CLI / 初期投入）
- したがって **SECURITY-12 の「管理者アカウントは MFA 必須」は適用対象が存在せず N/A**
- **パスワードは適応型ハッシュで保存**（SECURITY-12 の前段は適用）。製品は NFR Requirements で選定
- ロールは列挙型として定義し、将来（職員本人ログイン, A-08）に `STAFF` を追加できる形にする

### 3.2 ログインフロー

```text
login(username, password, source_ip):
  # SEC-03 / SEC-04 は U-07 のミドルウェアで先に通過済み
  if is_locked(username):                      # MU-03
      audit(AUTH_FAILURE, reason=LOCKED); raise AuthenticationFailedError  # 汎用メッセージ
  account = SessionStorePort.find_account(username)   # 見つからなくても同じ応答（列挙防止）
  if account is None or not PasswordHasherPort.verify(password, account.password_hash):
      record_failed_attempt(username)          # ロック閾値に達したらロック
      audit(AUTH_FAILURE)                      # FR-07.2、PII なし
      raise AuthenticationFailedError          # 汎用メッセージ（SECURITY-09）
  reset_failed_attempts(username)
  session = Session(id=<不透明なランダム ID>, principal=..., expires_at=now+TTL)
  SessionStorePort.save(session)
  audit(LOGIN_SUCCESS)
  return session
```

- **セッション ID は不透明なランダム値**（Q2=A）。JWT を使わない → **ログアウト・失効が即時**
- 認証失敗の応答は**汎用メッセージ**（利用者名の存在有無を漏らさない、SECURITY-09）
- `authenticate(session_id)`: セッションを取得し、期限切れ/失効なら**拒否**（deny by default）

### 3.3 アカウントロック（MU-03, SECURITY-12）

- 連続失敗が閾値に達したらアカウントをロック（または漸増遅延）
- ロック状態と失敗回数は `SessionStorePort`（注入実装）に保持
- 連続失敗は監査ログに記録し、アラート対象とする（US-04, FR-07.2）

---

## 4. SEC-02 認可（Q3=A, MU-01, NFR-S04）

```text
authorize(principal, action) -> AuthorizationDecision:        # ロールベース
authorize_resource_access(principal, resource) -> AuthorizationDecision:  # オブジェクトレベル
```

- **すべてのリソース参照は `authorize_resource_access` を必ず経由する**（MU-01/IDOR 防止）
- PoC では担当者ロールが全イベントにアクセス可（判定は常に許可）だが、**関門は存在する**
- 将来（A-08）に「職員は自分の申告のみ」へ絞る拡張点
- **deny by default**: 未知のロール・未知のアクション・判定不能はすべて**拒否**
- 認可違反は監査ログに記録（FR-07.2）

---

## 5. SEC-03 ネットワーク統制 / SEC-04 レート制限（Q6=A）

### SEC-03 IP 許可リスト（US-02, NFR-S10.2, SECURITY-07 の代償統制）

```text
is_allowed_source(ip, allowlist) -> bool     # 純関数
```
- 庁内イントラネットの**出口グローバル IP のみ許可**。それ以外は拒否
- 許可リストは**設定として外部化**（NFR-M03）。ハードコードしない
- 非許可は業務ロジックに到達させない（deny by default）。拒否を監査記録

### SEC-04 レート制限（NFR-S09, MU-03）

- **インメモリ**のカウンタ（単一サーバー・単一ワーカー, A-07）
- 超過は拒否し監査記録

### パイプライン順序（Application Design 準拠）

**SEC-03 IP → SEC-04 レート制限 → SEC-01 認証 → SEC-02 認可 → SEC-05 入力検証**

安価で広範な拒否（IP）を先に、高価な検証（入力）を後に置く。**U-07 がこの順序でミドルウェアを配線する**。

---

## 6. SEC-05 入力検証（Q7=A, MU-02）

```text
sanitize_csv_cell(value: str) -> str:
    return "'" + value if value[:1] in {"=", "+", "-", "@"} else value
```

- **CSV 数式インジェクション（MU-02）の無害化**。エクスポート時に適用
- **注入口は U-03 `serialize_csv` / U-05 `export_report_csv` に実装済み**（U03-H5）。**U-07 がこの関数を注入する**
- その他の再利用可能な検証関数（長さ・書式）を提供。API 境界の検証は U-07 の Pydantic と併用（SECURITY-05）

---

## 7. 監査（S-08 / P-04 / A-05, Q4=A, Q5=A）

### 7.1 記録対象（FR-07.1/7.2, SECURITY-13/14）

| 種別 | 内容 |
|------|------|
| 割当結果の作成・変更 | **誰が / いつ / 何を / 変更前後の値**（FR-07.1, US-03）|
| マスタの変更・削除 | 対象・操作者・日時（SECURITY-13）|
| 認証失敗 | 利用者名は記録するが**パスワードは記録しない**（FR-07.2, MU-03）|
| 認可違反・権限昇格の試行 | 主体・アクション・対象 ID（FR-07.2）|

### 7.2 内容の規則（**PII 除外**）

- **形式**: JSON Lines、**UTC** タイムスタンプ
- **個人情報を含めない**（SECURITY-03）: 職員 ID・イベント ID・施設 ID のみ。**氏名・居住小学校区は出さない**
- **`reason_category`（休暇・育児介護・健康上の配慮）は監査ログに出さない**（**U01-H22**）。要配慮個人情報に近く、監査の目的にも不要
- 割当変更の「変更前後の値」は**施設 ID の変化**として記録（氏名を含めない）

### 7.3 改竄防止（Q5=A, US-04, MU-04, SECURITY-14）

- **OS レベルの追記専用ファイル**（`chattr +a`）。U-01 の `shared-infrastructure.md` で確定済み（SQLite にロールがないため DB では実現不可）
- **アプリアカウントは追記のみ可能、削除・変更は不可**
- ローテーションは**特権 cron**（別アカウント）が実施。90 日超を削除し属性を再付与
- U-06 は `AuditLogPort` 経由で追記するのみ。A-05 が JSON Lines を追記
- **監査は業務トランザクションの外側**（業務がロールバックされても記録は残る）

---

## 8. Testable Properties（PBT-01, ブロッキング）

| ID | プロパティ | 分類 |
|----|-----------|------|
| **P-SEC01** | **deny by default**: 未認証のセッション ID／未知のロール／判定不能は常に拒否 | Invariant（Security）|
| **P-SEC02** | **IP 非許可は常に拒否**: 許可リストに無い送信元は、いかなる要求でも拒否される | Invariant |
| **P-SEC03** | **セッション失効**: 期限切れ・ログアウト後のセッション ID は常に拒否 | Invariant |
| **P-SEC04** | **監査ログに PII が出ない**: 任意の入力に対し、出力 JSON に氏名・居住小学校区・`reason_category` が含まれない | Security |
| **P-SEC05** | **サニタイズのエスケープ性**: `=+-@` で始まる任意の値は、サニタイズ後に数式として解釈されない先頭文字を持つ | Invariant |
| **P-SEC06** | **サニタイズの非破壊性**: 危険な先頭文字を持たない値は不変（不動点）| Invariant |
| **P-SEC07** | **ロックの単調性**: 失敗回数が閾値以上ならロック状態。成功でリセット | Invariant |
| **P-SEC08** | **パスワードハッシュの検証**: `verify(password, hash(password))` は真、異なるパスワードは偽 | Round-trip |
| **P-SEC09** | **レート制限**: 上限超過の要求は必ず拒否 | Invariant |

### 8.1 ステートフルテスト（PBT-06）の評価

**必要と判定**。セッションのライフサイクル（発行 → 検証 → 失効/ログアウト → 拒否）と、ロック状態（失敗蓄積 → ロック → リセット）は**状態機械**である。`RuleBasedStateMachine` でランダムな操作列を生成し、**「失効後は必ず拒否」「ロック中は必ず拒否」**を不変条件として検証する。

---

## 9. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U06-H1** | パスワードハッシュ製品（Argon2 / bcrypt）とセッション TTL・ロック閾値・レート上限の選定 | U-06 NFR Requirements |
| **U06-H2** | `SessionStorePort` の DB 実装（U-03 の `sessions` 骨格, U03-H3）を **U-07 が注入**する | U-07 |
| **U06-H3** | `sanitize_csv_cell` を U-03 `serialize_csv` / U-05 `export_report_csv` に **U-07 が注入**する（U03-H5）| U-07 |
| **U06-H4** | ミドルウェアの配線順序（SEC-03→04→01→02→05）は **U-07 が実装** | U-07 |
| **U06-H5** | **アプリ内に管理者ロールを設けない**（Q1=A）。アカウント発行は運用作業。実運用では管理者ロール + MFA（SECURITY-12）の実装が必要 | 実運用移行時 |
| **U06-H6** | 監査ログの追記専用属性（`chattr +a`）とローテーション cron の設定 | インフラ / 運用 |
