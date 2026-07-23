# NFR Requirements Plan — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 3 / 8）
**参照**: U-03 Functional Design の全成果物、U-01 `tech-stack-decisions.md`、`requirements.md` v1.4

---

## 1. 本ステージのスコープ

**バックエンド全体の技術スタックは U-01 で確定済み**（Python, FastAPI, SQLite/PostgreSQL, SQLAlchemy+Alembic, Hypothesis, 例外方式）。U-03 はこれを継承する。

**ただし U-03 は実際の永続化を持つ最初のユニットである。** したがって:

- **プロジェクトで初めてプロダクション依存を追加する**（`sqlalchemy`, `alembic`）。U-01, U-02 は依存ゼロだった
- **性能要件 NFR-P04（CSV 2,000 行を 30 秒以内）が本ユニットで問われる**

---

## 2. Step 1: 機能設計の分析結果

### 2.1 該当する NFR

| カテゴリ | 該当 | 内容 |
|---------|:----:|------|
| **性能** | **該当** | NFR-P04（CSV 2,000 行を 30 秒以内）、NFR-P03（距離キャッシュ、U-02 で確定済み） |
| **信頼性** | **該当** | fail closed の CSV インポート（原子性）、DB 復元時の再検証 |
| **セキュリティ** | **該当** | 個人情報の保存（SECURITY-01）、ログに含めない（SECURITY-03）、パラメータ化クエリ（SECURITY-05） |
| **保守性** | **該当** | SQLite → PostgreSQL 移行（U01-H18）、SQLAlchemy Core の抽象化 |
| スケーラビリティ | **N/A** | 単一サーバー、単一ワーカー（A-07）。スケールアウトしない |
| 可用性 | **N/A** | レジリエンシー拡張は無効。SLA を定めない |

### 2.2 本ステージで追加するプロダクション依存

| パッケージ | 用途 | SECURITY-10 |
|-----------|------|-------------|
| `sqlalchemy` | Core（テーブル定義、クエリ）+ マッパ | バージョン固定 |
| `alembic` | スキーママイグレーション | バージョン固定 |

**これがプロジェクト初のプロダクション依存である。** U-03 のリンタ契約は、U-01/U-02 の「標準ライブラリのみ」とは異なり、これらを許可する。

---

## 3. 明確化質問

以下の質問に、`[Answer]:` タグの後に選択肢の記号を記入してご回答ください。すべて回答し終えたら「完了」とお知らせください。

---

### Question 1: CSV パーサ（Tech Stack / 性能）

CSV の解析に何を使いますか？ NFR-P04 は 2,000 行を 30 秒以内です。

A) **標準ライブラリの `csv` モジュール** — 追加依存なし。2,000 行の解析は 1 秒未満。日本語（UTF-8）に対応 **（推奨。プロダクション依存を最小に保つ）**

B) **`pandas`** — 高機能だが、重量級の依存を 1 つ追加する。本ユニットの用途（行単位の検証とマッピング）には過剰

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 2: CSV の一括挿入方式（性能、NFR-P04）

2,000 行を DB に保存する方式を確定してください。

A) **SQLAlchemy Core の `executemany`（一括 INSERT）** — 1 行ずつの INSERT より大幅に速い。2,000 行を数百ミリ秒で挿入できる。1 トランザクション内で実行し、fail closed を保つ **（推奨）**

B) **1 行ずつ INSERT** — 単純だが、2,000 行で数秒〜数十秒かかりうる。NFR-P04 を満たせない可能性

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 3: 有効な申告を取得するクエリ方式（保守性、U03-H6）

各 `(staff, event)` の最新申告を取得するクエリを、SQLite と PostgreSQL の両方で動作させる必要があります。

A) **相関サブクエリ（`MAX(declared_at)`）** — SQLite の古いバージョンでも動作する。SQLAlchemy Core で表現でき、方言差がない **（推奨。移植性が最も高い）**

B) **ウィンドウ関数（`ROW_NUMBER() OVER`）** — モダンな SQL。SQLite 3.25+ と PostgreSQL で動作するが、古い SQLite では使えない

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 4: 接続プールとトランザクション管理（信頼性、U01-H15）

SQLite の必須設定（WAL, busy_timeout, foreign_keys=ON）をどう適用しますか？

A) **SQLAlchemy の `connect` イベントで、接続確立ごとに PRAGMA を発行する** — すべての接続に確実に適用される。SQLite でのみ発行し、PostgreSQL では発行しない（方言で分岐） **（推奨）**

B) **接続文字列のクエリパラメータで指定する** — 一部の PRAGMA は接続文字列で指定できない（busy_timeout 等）

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 5: テスト時の DB（信頼性 / テスト戦略）

プロパティベーステストとステートフルテスト（PBT-06）で、DB をどう用意しますか？

A) **インメモリ SQLite（`:memory:`）をテストごとに新規作成する** — 高速で分離される。本番と同じ SQLite 方言。マイグレーションを適用して構築する **（推奨）**

B) **一時ファイルの SQLite** — テストごとにファイルを作る。`:memory:` より遅いが、複数接続の検証に使える

C) **モックのリポジトリ** — DB を使わない。ただし SQL の正しさ（クエリ、制約、CASCADE）を検証できず、P-DM01〜P-DM05 の意味が薄れる

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

## 4. 実行チェックリスト（回答の分析後に実行）

### 4.1 NFR 要件の文書化

- [x] U-03 固有の NFR（性能、信頼性、セキュリティ、保守性）を定義する
- [x] N/A カテゴリ（スケーラビリティ、可用性）を根拠付きで記録する
- [x] Q1, Q2 の回答に基づき、NFR-P04（CSV 2,000 行を 30 秒以内）の達成手段を定義する
- [x] Q5 の回答に基づき、テスト時の DB 方針を定義する
- [x] `aidlc-docs/construction/data-management/nfr-requirements/nfr-requirements.md` を作成する

### 4.2 技術スタック決定（U-03 固有の差分）

- [x] U-01 の技術スタックを継承することを明記する
- [x] Q1 の回答に基づき、CSV パーサを確定する
- [x] Q3 の回答に基づき、有効な申告のクエリ方式を確定する（移植性）
- [x] Q4 の回答に基づき、PRAGMA の適用方法を確定する（U01-H15）
- [x] プロダクション依存（`sqlalchemy`, `alembic`, その他）を一覧化し、バージョン固定する（SECURITY-10）
- [x] U-03 のリンタ契約（`data_management` が許可する import）を定義する
- [x] `aidlc-docs/construction/data-management/nfr-requirements/tech-stack-decisions.md` を作成する

### 4.3 拡張ルールの適合確認

- [x] **PBT-09**: Hypothesis を継承。ステートフルテスト（PBT-06）に `RuleBasedStateMachine` を使うことを確認する
- [x] **SECURITY-10**: 追加するプロダクション依存をバージョン固定する。`pip-audit` の対象に含める
- [x] **SECURITY-05**: SQLAlchemy Core がパラメータ化クエリを使う（文字列連結をしない）ことを確認する
- [x] **SECURITY-01**: 個人情報の保存先が暗号化ボリューム（shared-infrastructure.md）であることを再確認する
- [x] 本ステージに適用対象のない SECURITY / PBT ルールを N/A として記録する
- [x] レジリエンシー拡張は無効のため適合確認を行わない旨を記録する

### 4.4 完了処理

- [x] `aidlc-docs/aidlc-state.md` の進捗を更新する
- [x] 拡張ルール適合サマリを作成する
- [ ] 標準の 2 択完了メッセージを提示し、承認を待つ
