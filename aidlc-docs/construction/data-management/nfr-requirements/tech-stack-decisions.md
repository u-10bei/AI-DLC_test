# 技術スタック決定 — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 3 / 8）

---

## 1. U-01 からの継承

バックエンド全体の技術スタックは U-01 で確定済み。U-03 はこれを継承する（Python, FastAPI, SQLite/PostgreSQL, SQLAlchemy+Alembic, Hypothesis, 例外方式, uv/Poetry, mypy strict, ruff, import-linter）。

本文書は **U-03 固有の差分**のみを記す。

---

## 2. U-03 固有の決定

| # | 項目 | 決定 | 出典 |
|---|------|------|------|
| 1 | CSV パーサ | **標準ライブラリ `csv`**（pandas を使わない） | Q1=A |
| 2 | CSV 一括挿入 | **`executemany`（一括 INSERT）** | Q2=A |
| 3 | 有効な申告のクエリ | **相関サブクエリ `MAX(declared_at)`** | Q3=A |
| 4 | PRAGMA の適用 | **SQLAlchemy `connect` イベント（方言で分岐）** | Q4=A |
| 5 | テスト時の DB | **インメモリ SQLite（テストごとに新規）** | Q5=A |

---

## 3. プロダクション依存（プロジェクト初）

**U-03 はプロジェクトで初めてプロダクション依存を追加する。** U-01, U-02 は依存ゼロだった。

| パッケージ | 用途 | バージョン固定 |
|-----------|------|:-------------:|
| `sqlalchemy` | Core（テーブル定義、クエリ、`executemany`）+ マッパ | ○（SECURITY-10） |
| `alembic` | スキーママイグレーション | ○（SECURITY-10） |

**CSV パーサは標準ライブラリ `csv`**（Q1=A）であり、依存を増やさない。pandas は本用途（行単位の検証とマッピング）に対して過剰である。

これらを `pyproject.toml` の `dependencies` に厳密なバージョンで固定し、`pip-audit` の対象に含める。`latest` を使わない。

---

## 4. 決定 2: `executemany` による一括挿入（NFR-P04）

NFR-P04（CSV 2,000 行を 30 秒以内）を、SQLAlchemy Core の `executemany`（一括 INSERT）で達成する。

- 1 行ずつの INSERT は 2,000 行で数秒〜数十秒かかりうる
- `executemany` は数百ミリ秒で完了する
- **1 トランザクション内で実行し、fail closed の原子性を保つ**（BR-DM01）

**CSV の解析（標準ライブラリ `csv`）も 2,000 行で 1 秒未満**であり、全体で 30 秒に十分収まる。

---

## 5. 決定 3: 相関サブクエリによる有効な申告の取得（U03-H6）

各 `(staff, event)` の最新申告を、**相関サブクエリ**で取得する。

```sql
SELECT * FROM availability_declarations d1
WHERE declared_at = (
  SELECT MAX(declared_at) FROM availability_declarations d2
  WHERE d2.staff_id = d1.staff_id AND d2.event_id = d1.event_id
)
```

**ウィンドウ関数（`ROW_NUMBER() OVER`）を却下した理由**: SQLite 3.25 未満で動作しない。相関サブクエリは古い SQLite でも動作し、PostgreSQL でも同一の SQL で動く。**移植性が最も高い**（U01-H18: SQLite → PostgreSQL）。

DB の `UNIQUE(staff_id, event_id, declared_at)` 制約により、`MAX(declared_at)` を持つ行はちょうど 1 つである。

---

## 6. 決定 4: PRAGMA の適用（U01-H15）

SQLite の必須設定を、SQLAlchemy の `connect` イベントで接続確立ごとに発行する。

```python
# 概念コード（Code Generation で実装）
@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _):
    if engine.dialect.name == "sqlite":   # 方言で分岐
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
```

- **SQLite でのみ発行する。** PostgreSQL では発行しない（既定で外部キーが有効）
- **`foreign_keys=ON` が死活的である。** これがないと ON DELETE CASCADE（Q5=A の Functional Design）も参照整合性も機能しない

接続文字列のクエリパラメータでは `busy_timeout` 等を指定できないため、`connect` イベントを採用した。

---

## 7. 決定 5: テスト時のインメモリ SQLite（Q5=A）

プロパティベーステストとステートフルテスト（PBT-06）で、**テストごとに新規のインメモリ SQLite（`:memory:`）** を用意し、マイグレーションを適用して構築する。

**モックのリポジトリを却下した理由**: P-DM01〜P-DM05 は **SQL の正しさそのもの**を検証する。

| プロパティ | 検証する SQL の性質 |
|-----------|------------------|
| P-DM01（原子性） | トランザクションのロールバック |
| P-DM02（有効な申告の一意性） | UNIQUE 制約 + MAX サブクエリ |
| P-DM03（3 分類の分割） | 集計クエリ |
| P-DM04（キャッシュキー正規化） | CHECK 制約 + PK |
| P-DM05（マッパ） | 行 ↔ ドメイン型 |

**モックではこれらを一切検証できない。** 実際の SQLite を使うことで、制約・CASCADE・クエリの正しさが検証される。インメモリは高速で、テスト間で分離される。

**PRAGMA の適用**: テスト用のインメモリ DB にも `connect` イベントで PRAGMA を適用する。特に `foreign_keys=ON` がないと CASCADE のテストが無意味になる。

---

## 8. U-03 のリンタ契約

U-01/U-02 の「標準ライブラリのみ」とは異なり、U-03 は `sqlalchemy` と `alembic` を許可する。ただしユニット境界の制約は維持する。

| 契約 | 内容 |
|------|------|
| **R（U-03 のユニット境界）** | `data_management` は `shared_kernel`, `distance_cost` のみを（ユニットとして）import してよい。`optimization_engine`, `security`, `api_orchestration`, `frontend`, `comparison_report` を import してはならない |
| **許可する第三者** | `sqlalchemy`, `alembic`（プロダクション） |
| **禁止する第三者** | `pydantic`, `fastapi`（これらは U-07 の API 境界のもの。U-03 のドメイン/永続化層に持ち込まない） |

**Code Generation で `.importlinter` に追加し、契約の実効性を確認する**（`import fastapi` の混入で BROKEN になること）。

---

## 9. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U03-H7（新規）** | `sqlalchemy`, `alembic` を `pyproject.toml` の `dependencies` に追加し、バージョン固定する（SECURITY-10）。ロックファイルを更新する | U-03 Code Generation |
| **U03-H8（新規）** | テストは実インメモリ SQLite を使う。PRAGMA（特に `foreign_keys=ON`）をテスト DB にも適用する。モックのリポジトリを使わない | U-03 Code Generation |
| U03-H6 | 有効な申告のクエリは相関サブクエリ。SQLite/PostgreSQL 両対応 | U-03 Code Generation |
