# Functional Design Plan — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 3 / 8）
**参照**: `unit-of-work.md`, `unit-of-work-story-map.md`, `component-methods.md`, `services.md`, `requirements.md` v1.4, U-01・U-02 の全成果物

---

## 1. ユニットコンテキスト（Step 1 の結果）

| 項目 | 内容 |
|------|------|
| **ユニット** | U-03 `data-management`（コード上 `src/data_management/`） |
| **含まれるコンポーネント** | S-01 EventService, S-02 MasterDataService, S-03 AvailabilityService, P-02 RepositoryPort, P-07 CsvCodecPort, A-02 PersistenceAdapter, A-04 CsvAdapter |
| **依存** | U-01 `shared_kernel`, U-02 `distance_cost`（`P-03` の実装、`compute_district_distance_matrix` の呼び出し） |
| **このユニットに依存するユニット** | U-04, U-05, U-07 |
| **主担当ストーリー** | **US-05〜US-13**（9 件） |

### 1.1 このユニットの性質

**これまでで最も大きく複雑なユニットである。** 実際の永続化を持つ最初のユニットであり、トランザクション整合性・CSV 一括処理・fail closed が中核となる。

### 1.2 主担当ストーリー（9 件）

| ストーリー | 内容 |
|-----------|------|
| US-05 | イベントの登録 |
| US-06 | イベントの編集・削除とステータス管理 |
| US-07 | 職員マスタの CSV 一括インポート |
| US-08 | 施設マスタの CSV 一括インポート |
| US-09 | 小学校区マスタの CSV 一括インポート（キャッシュ無効化を含む） |
| US-10 | マスタデータの個別修正 |
| US-11 | 従事可否申告の CSV 一括登録 |
| US-12 | 追加の従事可否申告と申告履歴 |
| US-13 | 従事可能職員数と必要人数の充足状況の可視化 |

### 1.3 届いている申し送り（多数）

| ID | 事項 |
|----|------|
| **U01-H10** | 「未申告」は「従事不可」ではない。`getSufficiencyStatus()` は 3 分類（従事可能 / 従事不可 / 未申告）で集計する |
| **U01-H11** | CSV 一括インポート時、`declared_at` の一意性を保証する |
| **U01-H12** | `Event.scheduled_date` は JST の暦日。他の日時は UTC |
| **U01-H13** | `Event` のステータス遷移規則を `S-01 EventService` が検証する。`Optimized → CollectingDeclarations` の再開遷移を忘れない |
| **U01-H15** | SQLite の必須設定（WAL, busy_timeout>=5000, foreign_keys=ON） |
| **U01-H18** | SQLAlchemy + Alembic。SQLite 固有 SQL を使わない。動的型付けに依存しない |
| **U01-H21** | frozen ドメイン型。ORM のダーティチェックに依存する更新パターンは使えない |
| **U01-H24** | 列挙値の変換表（`from_japanese`/`to_japanese`）を使う。未知の値は fail closed |
| **U02-H3** | 距離キャッシュのキーを `(min(id), max(id))` に正規化する |
| **U02-H4** | キャッシュに保存するのは大円距離のみ。無効化は小学校区マスタ更新時のみ |
| **U02-H10** | `compute_district_distance_matrix()` を呼び、結果を永続化する。再計算の起動は小学校区マスタ更新時のみ |
| **SI-H2** | 監査ログファイルへの追記権限のみを持つよう、デプロイ手順で権限を設定する（Build and Test） |

---

## 2. 本ステージで解決すべき論点

### 論点 1: frozen ドメイン型と ORM の統合（U01-H21）

U-01 のドメイン型はすべて frozen である。SQLAlchemy の ORM は通常、可変オブジェクトの属性変更を追跡する（ダーティチェック）。**frozen 型ではこれが使えない。**

選択肢:
- **SQLAlchemy Core（テーブル定義 + 明示的な SELECT/INSERT）+ 手書きのマッパ**（ドメイン型 ↔ 行）
- **SQLAlchemy ORM の imperative mapping**（frozen dataclass にマッピング）

→ **Question 1 で確認する。**

### 論点 2: 従事可否の「有効な申告」の永続化と集計（U01-H10, U01-H11）

`AvailabilityDeclaration` は `(staff_id, event_id, declared_at)` で識別され、履歴が残る。有効な申告は最新の `declared_at`（U-01 の `effective_declaration_for`）。

**論点 2a**: 履歴をすべて保存するか、有効な申告のみを保存し履歴を別テーブルに持つか。
**論点 2b**: `declared_at` の一意性（U01-H11）を、DB 制約で保証するか、アプリケーションで保証するか。
**論点 2c**: `getSufficiencyStatus()` の 3 分類集計（U01-H10）。「未申告」は「従事可能職員でも従事不可申告者でもない職員」＝ 全職員から申告者を引いた集合。

→ **Question 2, 3 で確認する。**

### 論点 3: CSV インポートの検証順序（US-07, fail closed）

`services.md` セクション 3.5 は、CSV インポートを「解析 → 検証 → トランザクション内で保存」の順で行い、1 行でもエラーがあれば全体をロールバックすると定めた。

**検証すべき項目**: 型、長さ上限、参照整合性（存在しない小学校区 ID 等）、列挙値の変換（未知の値）、`declared_at` の一意性。

→ **Question 4 で確認する。**

### 論点 4: イベント削除時の連鎖（US-06）

`business-rules.md`（U-01）セクション 2.3 は、`Draft`/`CollectingDeclarations`/`Optimized` のイベントは削除可能、`Confirmed` は削除不可と定めた。削除時、紐づく従事可否申告・割当結果をどうするか。

→ **Question 5 で確認する。**

---

## 3. 明確化質問

以下の質問に、`[Answer]:` タグの後に選択肢の記号を記入してご回答ください。すべて回答し終えたら「完了」とお知らせください。

---

### Question 1: frozen ドメイン型の永続化方式（Data Flow / 論点 1）

U-01 のドメイン型はすべて frozen です。SQLAlchemy とどう統合しますか？

A) **SQLAlchemy Core（テーブル定義）+ 手書きのマッパ関数（行 ↔ ドメイン型）** — リポジトリが SELECT して行を受け取り、`Coordinates(...)` 等でドメイン型を再構築する。保存時はドメイン型を分解して INSERT/UPDATE する。ドメイン型が ORM を一切知らず、ヘキサゴナルの純粋性が保たれる。復元時にドメイン型の `__post_init__` が再実行され、DB の不正データで fail closed になる **（推奨）**

B) **SQLAlchemy ORM の imperative（classical）mapping** — frozen dataclass を ORM にマッピングする。ボイラープレートは減るが、frozen とダーティチェックの相性問題を回避する設定が必要で、ドメイン型が ORM のライフサイクルに縛られる

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 2: 従事可否申告の保存構造（Domain Model / 論点 2a）

`AvailabilityDeclaration` は再申告の履歴を持ちます（US-12）。どう保存しますか？

A) **単一テーブルに全申告を追記し、有効な申告はクエリ時に `(staff_id, event_id)` ごとの最新 `declared_at` で決める** — 履歴が自然に残る。`effective_declaration_for`（U-01）のロジックと一致する。集計時は最新行のみを対象にする **（推奨）**

B) **「有効な申告」テーブルと「履歴」テーブルを分ける** — 有効な申告の取得は速いが、再申告のたびに 2 テーブルを更新する必要があり、整合性維持が複雑

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 3: `declared_at` の一意性の保証（Business Rules / 論点 2b、U01-H11）

同一の `(staff_id, event_id)` に同一時刻の申告が 2 件あると `AmbiguousDeclarationError`（U-01）になります。CSV 一括インポート時にどう防ぎますか？

A) **DB の一意制約 `UNIQUE(staff_id, event_id, declared_at)` を課し、加えてインポート時に同一 CSV 内の重複を検出する** — 二重の防御。同一時刻の重複を DB とアプリの両方で拒否する **（推奨）**

B) **インポート時に、同一 `(staff_id, event_id)` の複数行に対し、`declared_at` に連番のマイクロ秒を付与して一意化する** — 重複を拒否せず自動調整する。ただし「どちらが本当に新しいか」の情報は CSV の行順に依存する

C) **アプリケーションでのみ一意性を検証する** — DB 制約は課さない

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 4: CSV インポートのエラー報告（Error Handling / 論点 3、US-07）

1 行でもエラーがあればインポート全体をロールバックします（fail closed）。エラーの報告方法を確定してください。

A) **全行を検証し、すべてのエラーを行番号付きで一括報告する** — 担当者は 1 回の修正で全エラーを直せる。2,000 行の CSV で 50 個のエラーがあっても、1 回で全部わかる **（推奨）**

B) **最初のエラーで停止し、そのエラーのみ報告する** — 実装は単純だが、担当者はエラーを 1 個ずつ潰す必要があり、2,000 行を何度も往復する

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 5: イベント削除時の連鎖（Business Rules / 論点 4、US-06）

`Confirmed` でないイベントは削除可能です。削除時、紐づくデータをどうしますか？

A) **紐づく従事可否申告・割当結果・過去実績を連鎖削除する（CASCADE）** — イベントが消えれば関連データも消える。DB の外部キー制約 ON DELETE CASCADE で実現。削除操作は監査ログに記録する **（推奨）**

B) **紐づくデータがある場合は削除を拒否し、先に手動削除を求める** — 誤削除を防ぐが、操作が煩雑

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 6: マイグレーションツールの初期化（Data Flow、U01-H18）

Alembic でスキーマのマイグレーションを管理します。U-03 が最初にテーブルを定義するユニットです。

A) **U-03 で Alembic を初期化し、U-01 のドメイン型に対応する全テーブルの初期マイグレーションを作成する** — 職員・施設・小学校区・部署・イベント・従事可否申告・割当結果・過去実績・距離キャッシュ・ジョブ・セッション・監査（該当するもの）。以降のユニットはマイグレーションを追加する **（推奨）**

B) **各ユニットが自分のテーブルのマイグレーションを持つ** — U-03 は自分の担当分のみ。ただしテーブル間に外部キーがあるため、順序管理が複雑

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 7: 距離キャッシュの再計算の起動（Data Flow、U02-H10, U02-H4）

小学校区マスタの更新時に距離キャッシュを再計算します。どのタイミングで起動しますか？

A) **小学校区マスタのインポート／個別修正のトランザクションのコミット後に、`compute_district_distance_matrix()` を呼んで全再計算し、キャッシュを置き換える** — 校区数は最大 200 で計算は 1 秒未満（U-02 で確定）。全再計算が単純で確実 **（推奨）**

B) **変更された小学校区に関わるペアのみ再計算する** — 差分計算。効率的だが、実装が複雑で、1 秒未満の計算には過剰

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 8: 充足状況の集計対象（Business Rules、U01-H10、US-13）

`getSufficiencyStatus()` は「従事可能 / 従事不可 / 未申告」の 3 分類で集計します（U01-H10）。「未申告」を数えるには「全職員」の母集合が必要です。何を母集合としますか？

A) **職員マスタ全体を母集合とする** — 「未申告 = 全職員 − 申告者」。全職員が対象イベントに申告しうる前提。単純で、督促対象が明確 **（推奨）**

B) **イベントごとに対象職員を別途指定できるようにする** — 一部の職員のみが対象のイベント（特定部署のみ等）に対応できるが、対象職員の管理が追加で必要

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

## 4. 実行チェックリスト（回答の分析と曖昧さの解消後に実行）

### 4.1 ドメインエンティティ / データモデル

- [x] Q1 の回答に基づき、frozen ドメイン型と DB 行のマッピング方式を定義する
- [x] Q2 の回答に基づき、従事可否申告の保存構造を定義する
- [x] Q6 の回答に基づき、テーブル定義とマイグレーションの方針を定義する
- [x] 全テーブルのスキーマ（列、型、外部キー、一意制約、インデックス）を定義する
- [x] U01-H12（日時の UTC/JST）を DB の型定義に反映する
- [x] 距離キャッシュテーブルの構造を定義する（正規化キー、大円距離。U02-H3, H4）
- [x] エンティティ関連図を作成する（Mermaid + テキスト代替）
- [x] `aidlc-docs/construction/data-management/functional-design/domain-entities.md` を作成する

### 4.2 ビジネスロジックモデル

- [x] S-01 EventService のオーケストレーション（ステータス遷移、削除連鎖）を定義する（U01-H13, Q5）
- [x] S-02 MasterDataService の CSV インポートフロー（fail closed）を定義する（Q4）
- [x] S-03 AvailabilityService の申告登録・履歴・充足集計を定義する（Q2, Q3, Q8）
- [x] 距離キャッシュの再計算フローを定義する（Q7、U02-H10）
- [x] `P-02 RepositoryPort` の各リポジトリのインターフェースを定義する
- [x] `P-03 DistanceCachePort` の実装方針を定義する（U-02 が定義、U-03 が実装）
- [x] トランザクション境界を定義する（fail closed / SECURITY-15）
- [x] `aidlc-docs/construction/data-management/functional-design/business-logic-model.md` を作成する

### 4.3 ビジネスルール

- [x] Q3 の回答に基づき、`declared_at` の一意性ルールを定義する（U01-H11）
- [x] Q4 の回答に基づき、CSV インポートのエラー報告ルールを定義する
- [x] Q5 の回答に基づき、イベント削除の連鎖ルールを定義する
- [x] Q8 の回答に基づき、充足状況の 3 分類集計ルールを定義する（U01-H10）
- [x] 列挙値の変換（`from_japanese`、未知の値の拒否）を CSV フローに組み込む（U01-H24）
- [x] U01-H21（frozen 型の更新は新インスタンス構築）を明記する
- [x] `aidlc-docs/construction/data-management/functional-design/business-rules.md` を作成する

### 4.4 Testable Properties（PBT-01、**ブロッキング制約**）

- [x] **INV-10**（CSV エクスポート → インポートのラウンドトリップ）— Round-trip（PBT-02）
- [x] CSV インポートの原子性（失敗時に DB が不変）— Invariant
- [x] 有効な申告の一意性（`effective_declaration_for` の DB 版）— Invariant
- [x] 充足状況の 3 分類が全職員を分割する（従事可能 + 従事不可 + 未申告 = 全職員）— Invariant
- [x] 距離キャッシュのラウンドトリップ（`put` → `get`）— Round-trip（PBT-02）
- [x] 各プロパティにプロパティ分類を付与する
- [x] **ステートフルテスト（PBT-06）の要否を評価する**（`Event` のステータス遷移の状態機械）

### 4.5 拡張ルールの適合確認

- [x] **PBT-01**: 「Testable Properties」セクションと分類を確認する
- [x] **PBT-06**: `Event` の状態機械に対するステートフルテストの要否を記録する
- [x] **SECURITY-05**: CSV インポートの入力検証を確認する
- [x] **SECURITY-15**: fail closed（原子性、未知の値の拒否）を確認する
- [x] **SECURITY-03**: 職員の氏名・居住小学校区を扱うが、ログには職員 ID のみ。エラー報告に個人情報を含めない
- [x] **SECURITY-01**: 個人情報を保存する。暗号化ボリューム上への配置（shared-infrastructure.md）を再確認する
- [x] 本ステージに適用対象のない SECURITY / PBT ルールを N/A として記録する
- [x] レジリエンシー拡張は無効のため適合確認を行わない旨を記録する

### 4.6 完了処理

- [x] `aidlc-docs/aidlc-state.md` の進捗を更新する
- [x] 拡張ルール適合サマリを作成する
- [ ] 標準の 2 択完了メッセージを提示し、承認を待つ
