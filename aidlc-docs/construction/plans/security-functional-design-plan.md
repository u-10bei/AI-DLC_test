# Functional Design Plan — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Functional Design（ユニット 6 / 8）
**参照**: `requirements.md` v1.4（FR-07, NFR-S01〜S10）、`stories.md`（US-01〜US-04, MU-01〜MU-04）、Application Design（SEC-01〜05, S-08, P-04, A-05）、`shared-infrastructure.md`（追記専用監査ログ）

---

## 1. ユニットコンテキスト

| 項目 | 内容 |
|------|------|
| ユニット | U-06 `security`（`src/security/`）|
| 依存（宣言）| **U-01 shared_kernel のみ** |
| ストーリー | US-01（未認証遮断）、US-02（送信元 IP 制限）、US-03（割当変更の監査）、US-04（監査ログ改竄防止）|
| 悪用ケース | MU-01（IDOR）、MU-02（CSV 数式インジェクション）、MU-03（総当たりログイン）、MU-04（監査ログ隠蔽）|
| コンポーネント | SEC-01 Authentication / SEC-02 Authorization / SEC-03 NetworkControl / SEC-04 RateLimit / SEC-05 InputValidation / S-08 AuditService / P-04 AuditLogPort / A-05 監査アダプタ |

**U-06 は SECURITY 拡張ルールの実体を担うユニット**である。他ユニットは各所で SECURITY-xx に適合してきたが、認証・認可・監査・ネットワーク統制の実装は本ユニットが持つ。

**U-01 からの持ち越し**: セッションストアとパスワードハッシュの選定は U-06 の NFR Requirements に委ねられている。

**重要な制約**: U-06 は **U-01 にのみ依存**する。`src/security/` は `shared_kernel` を import できず（R-2 により shared_kernel 側が security を禁止）—— 正確には U-06 は U-01 を import できるが、**U-03（永続化）には依存しない**。セッション永続化をどう実現するかが論点（Q2）。

---

## 2. Step 1: 設計対象の分析

| 領域 | 設計内容 |
|------|---------|
| 認証（SEC-01）| ログイン、パスワード検証、セッション発行、失敗回数の記録（MU-03）|
| 認可（SEC-02）| ロールベース + オブジェクトレベル（MU-01/IDOR, NFR-S04）|
| ネットワーク統制（SEC-03）| 庁内出口 IP 許可リスト（NFR-S10.2, US-02）|
| レート制限（SEC-04）| 公開エンドポイントのレート制限（NFR-S09, MU-03）|
| 入力検証（SEC-05）| CSV 数式インジェクション無害化（MU-02, U03-H5）ほか |
| 監査（S-08/P-04/A-05）| FR-07.1/7.2/7.3、追記専用（SECURITY-13/14, US-03/US-04, MU-04）|

---

## 3. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: ロールとアカウント、MFA のスコープ（**重要**, NFR-S05 / SECURITY-12）

NFR-S05 は「**管理者アカウントは MFA を必須**とする。パスワードは適応型ハッシュで保存する」と定めます。セキュリティ拡張は全ルールがブロッキングです。本 PoC の利用者は担当者のみ（職員本人のログインは対象外, A-08）。

A) **担当者ロールのみ。アプリ内に管理者アカウントを作らない** — アカウント発行は運用作業（CLI / 初期投入、OS 権限を持つ運用者が実施）とし、アプリケーションに管理者ロールを設けない。したがって **SECURITY-12 の MFA 要件は「管理者アカウントが存在しない」ため N/A**（適用対象なし）。パスワードの適応型ハッシュ（Argon2/bcrypt）は担当者アカウントに適用する。ロールは将来（職員本人ログイン, A-08）に備え拡張可能に設計 **（推奨、PoC スコープとして誠実）**

B) **担当者 + 管理者の 2 ロール。管理者に MFA（TOTP）を実装** — SECURITY-12 を完全適用するが、TOTP の登録・検証・リカバリコードまで PoC スコープに入る

X) Other（`[Answer]:` に記述）

[Answer]:A

---

### Question 2: セッション方式と永続化（**重要**, U-01 からの持ち越し）

U-06 は **U-03（永続化）に依存しません**。しかしセッションは永続化が必要です（U-03 に `sessions` 骨格テーブルあり, U03-H3）。

A) **サーバー側の不透明なセッション ID + `SessionStorePort`（U-06 が定義、実装は注入）** — U-06 は `SessionStorePort`（保存・取得・失効）を**抽象ポートとして定義**するのみ。DB 実装は **U-07 が注入**する（U-07 は U-03 と U-06 の双方に依存）。**MU-02 で採用済みの依存性注入パターンと同型**であり、U-06 → U-01 のみという依存を保つ。不透明なセッション ID により失効・ログアウトが即時 **（推奨）**

B) **JWT（ステートレス）** — 永続化不要だが、失効（ログアウト・権限変更）が即時に効かない

C) U-06 が U-03 に依存してセッションを直接永続化 — 依存グラフを変更する

X) Other

[Answer]:A

---

### Question 3: 認可モデル（SEC-02, MU-01/IDOR, NFR-S04）

オブジェクトレベル認可（IDOR 防止）を PoC でどう扱いますか？

A) **ロールベース + オブジェクトレベル認可の関門を必ず通す** — PoC では担当者ロールが全業務データにアクセスするため、オブジェクトレベル判定は実質「担当者は全イベントにアクセス可」。ただし `authorize_resource_access(principal, resource)` を**必ず経由する設計**とし、将来（職員本人ログイン, A-08）に「本人の申告のみ」へ絞る拡張点を用意する。**deny by default**（既定は拒否）**（推奨）**

B) PoC ではロールチェックのみ、オブジェクトレベル認可の関門を設けない — MU-01 の対策が将来まで空白になり、後付けは漏れやすい

X) Other

[Answer]:A

---

### Question 4: 監査ログの記録対象と内容（FR-07.1/7.2, SECURITY-13/14, **U01-H22**）

監査ログに何を、どう記録しますか？

A) **要件どおり記録し、個人情報を含めない** — 記録対象: (1) 割当結果の作成・変更（**誰が / いつ / 何を / 変更前後の値**, FR-07.1）、(2) マスタの変更・削除（SECURITY-13）、(3) 認証失敗・認可違反・権限昇格の試行（FR-07.2）。形式: **JSON Lines、UTC タイムスタンプ**。**個人情報を含めない**——職員 ID のみを記録し、氏名・居住小学校区は出さない（SECURITY-03）。特に **`reason_category`（休暇・育児介護・健康上の配慮）は要配慮個人情報に近く、監査ログに出さない（U01-H22）** **（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 5: 監査ログの改竄防止（US-04, MU-04, SECURITY-14）

追記専用の実現方法を確定してください。

A) **OS レベルの追記専用ファイル（`chattr +a`）へ `AuditLogPort` 経由で追記** — U-01 の `shared-infrastructure.md` で確定済み（SQLite にロールがないため DB では実現できない）。アプリアカウントは**追記のみ可能で削除・変更は不可**。ローテーションは特権 cron（別アカウント）。U-06 は `AuditLogPort`（P-04）を定義し、A-05 アダプタが追記する **（推奨、確認）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 6: ネットワーク統制・レート制限とパイプライン順序（SEC-03/04, NFR-S10.2, NFR-S09, MU-03）

IP 許可リスト・レート制限・アカウントロックの設計を確定してください。

A) **U-06 が判定ロジックを提供し、U-07 がミドルウェアとして配線** — (1) **IP 許可リスト**（SEC-03）: 庁内出口グローバル IP のみ許可、**設定として外部化**（NFR-M03）、非許可は拒否（US-02, NFR-S10.2）。(2) **レート制限**（SEC-04）: 単一サーバーのため**インメモリ**カウンタ。(3) **認証失敗の連続でアカウントロックまたは漸増遅延**（MU-03, SECURITY-12）。(4) **パイプライン順序 = SEC-03 IP → SEC-04 レート制限 → SEC-01 認証 → SEC-02 認可 → SEC-05 入力検証**（Application Design 準拠）。すべて **deny by default / fail closed** **（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 7: 入力検証と CSV サニタイズ（SEC-05, MU-02, U03-H5）

`SEC-05` の責務を確定してください。

A) **`sanitize_csv_cell` + 汎用入力検証** — `sanitize_csv_cell(value)` は `=`, `+`, `-`, `@` で始まる値の先頭に `'` を付してエスケープする（MU-02）。**U-03/U-05 の `serialize_csv` には既に注入口が実装済み**であり、**U-07 が SEC-05 の関数を注入する**（U03-H5）。その他の入力検証（長さ・書式）は U-07 の Pydantic 境界（SECURITY-05）と併用し、U-06 は再利用可能な検証関数を提供する **（推奨、確認）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

## 4. 実行チェックリスト（回答分析後）

### 4.1 business-logic-model.md
- [x] コンポーネント構成（SEC-01〜05, S-08 AuditService, P-04 AuditLogPort, A-05 アダプタ）
- [x] 認証フロー（ログイン、ハッシュ検証、セッション発行、失敗記録・ロック）（Q1, Q2, Q6）
- [x] 認可フロー（ロール + オブジェクトレベル、deny by default）（Q3）
- [x] 監査フロー（記録対象・内容・PII 除外）（Q4）と追記専用（Q5）
- [x] ネットワーク統制・レート制限・パイプライン順序（Q6）
- [x] 入力検証・CSV サニタイズ（Q7）
- [x] ポート（SessionStorePort, AuditLogPort, ConfigPort）と U-07 による注入

### 4.2 business-rules.md
- [x] BR-SEC01.. （deny by default、MFA の適用範囲、セッション失効、ロック閾値、監査の PII 除外、IP 許可リスト、サニタイズ規則）
- [x] MU-01〜MU-04 の対策の明記
- [x] SECURITY-01〜15 の適合サマリ（**U-06 は本拡張の実体を担うため詳細に**）

### 4.3 domain-entities.md
- [x] `Principal`（利用者 ID + ロール、PII なし）、`Session`、`Role`、`AuditEvent`、`AuthorizationDecision` を定義
- [x] 新規例外（`AuthenticationFailedError`, `AuthorizationDeniedError`, `RateLimitExceededError`, `IpNotAllowedError` 等、PII なし）
- [x] U-01 の型との関係

### 4.4 PBT / Security 適合（PBT-01 ブロッキング）
- [x] Testable Properties: deny by default（未認証・非許可 IP は必ず拒否）、セッション失効後は必ず拒否、監査ログに PII が出ない、サニタイズの不動点/エスケープ性、ロック閾値の単調性
- [x] ステートフルテスト（PBT-06）の要否評価（セッションのライフサイクル、ロック状態）
- [x] SECURITY-15（fail closed）

### 4.5 完了処理
- [x] 3 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
