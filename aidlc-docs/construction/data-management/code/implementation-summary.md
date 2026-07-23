# Code Generation Implementation Summary — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Code Generation（ユニット 3 / 8）
**結果**: 4 ゲートすべて green。**プロジェクトで初めて実永続化とプロダクション依存を導入**

---

## 1. 生成物

### 新規アプリコード（`src/data_management/`）

| ファイル | 役割 | 論理コンポーネント |
|---------|------|------------------|
| `__init__.py` | 公開 API | - |
| `schema.py` | SQLAlchemy Core 全テーブル定義（所有 11 + 骨格 6）| - |
| `engine.py` | Engine/SessionFactory、PRAGMA、echo=False、インメモリ用 StaticPool | LC-01 |
| `mappers.py` | 行 ↔ frozen ドメイン型、fail-closed 復元 | LC-03 |
| `repositories.py` | P-02/P-03 実装、executemany、相関サブクエリ | LC-02 |
| `csv_codec.py` | 標準 `csv` 解析/直列化、サニタイザ注入 | P-07 / A-04 |
| `services.py` | S-01/S-02/S-03、トランザクション境界、fail-closed インポート | LC-04 |
| `migrations.py` | スキーマ適用ヘルパ（Alembic と単一出典を共有）| LC-05 |

### 新規 Alembic

`alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/0001_initial_schema.py`（全テーブルを `schema.metadata` から生成）

### in-place 修正（複製なし）

| ファイル | 変更 |
|---------|------|
| `pyproject.toml` | `sqlalchemy==2.0.36`, `alembic==1.14.0` を `dependencies` に追加（固定、SECURITY-10, U03-H7）。wheel packages に `distance_cost`, `data_management` 追加 |
| `.importlinter` | `data_management` を root に追加。R-4（ユニット境界）+ 第三者許可リスト契約を追加 |
| `src/shared_kernel/exceptions.py` | `DataIntegrityError`（PII なし、U03-H9）を追加 |
| `src/shared_kernel/__init__.py` | `DataIntegrityError` を公開 |

### 新規テスト（`tests/data_management/`）

`support.py`（インメモリ SQLite + seed）、`generators.py`（CSV 安全な dataset 生成）、`test_examples.py`（13 例）、`test_properties.py`（INV-10a/b, P-DM01〜05）、`test_stateful.py`（`Event` 状態機械の `RuleBasedStateMachine`, PBT-06）

---

## 2. 設計判断の実装（NFR Design パターンとの対応）

| パターン | 実装 |
|---------|------|
| DP-01 サービス所有トランザクション | サービスが `engine.begin()` で境界を張り、リポジトリは commit しない |
| DP-02 fail-closed 復元 | マッパが `__post_init__` を再実行、失敗を `DataIntegrityError`（ID のみ）に包む |
| DP-03 CSV 2 相・単一パス | 全ロード → 全検証（行番号付き蓄積）→ `executemany` |
| DP-04 原子的キャッシュ再計算 | 小学校区インポートと再計算を**同一 `engine.begin()`** で実行 |
| DP-05 PII 非露出 | `echo=False`、エラーは ID + 行番号のみ |
| DP-06 手書きマッパ | ORM 不使用、frozen 型維持 |
| DP-07 パラメータ化 | Core 式言語のみ。生 SQL 文字列連結なし |

---

## 3. 4 ゲートの結果

| ゲート | 結果 |
|-------|------|
| `pytest` | **96 passed**（U-01 43 + U-02 31 + U-03 22。U-01/U-02 の回帰なし）|
| `mypy --strict` | **clean（37 files）**。SQLAlchemy Core を `disallow_any_explicit` 下で扱うため、行アクセスは `_plain()` で `dict[str, object]` に正規化、集約は `_require_int` で narrow |
| `ruff` | **clean** |
| `lint-imports` | **6 契約 kept**。`import fastapi` を `data_management` に注入 → 許可リスト契約が **BROKEN**（非空虚性を確認）→ 除去で復帰 |

---

## 4. 計画からの逸脱・特記

1. **Alembic とテストのスキーマ単一出典**: 初期リビジョンとテストヘルパは、いずれも `schema.metadata` からスキーマを構築する。インメモリ SQLite に対して Alembic 環境を起動する代わりに `metadata.create_all` を使うことで、テストは高速・堅牢でありつつ**本番と同一のスキーマ**を検証する（U03-H8）。Alembic は実デプロイと SQLite→PostgreSQL 移行の機構として残る。
2. **インメモリ SQLite の共有接続**: `create_db_engine` が `sqlite://` を検出したとき StaticPool を用いる。これによりテスト専用コードを永続化層に持ち込まずにインメモリ DB を共有できる。
3. **充足の母集合**: 施設はイベント非依存のグローバルマスタ（スキーマにイベント-施設リンクなし）のため、充足の必要人数合計は施設マスタ全体で算出（business-logic-model.md 3.4 と整合）。
4. **骨格テーブル**: 他ユニット所有テーブル（assignment_results 等）は最小構成で作成。各所有ユニットが後続マイグレーションで拡張する。

---

## 5. プロパティテストが検証した不変条件

| プロパティ | 内容 |
|-----------|------|
| INV-10a | マスタの CSV エクスポート → インポートのラウンドトリップ |
| INV-10b | 距離キャッシュのラウンドトリップ |
| P-DM01 | インポート原子性（1 行の失敗で DB 不変）|
| P-DM02 | 有効な申告はちょうど 1 件（最新）|
| P-DM03 | 充足 3 分類が全職員を分割 |
| P-DM04 | キャッシュキー正規化 `get(a,b)==get(b,a)` |
| P-DM05 | マッパのラウンドトリップ |
| PBT-06 | `Event` 状態機械のステートフルテスト |

---

## 6. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| U03-H1..H3 | 骨格テーブル（assignment_results / historical / optimization_jobs / sessions）のロジックは所有ユニットが実装 | U-04, U-05, U-06 |
| U03-H4 | マッパ/リポジトリのパターンを他ユニットのリポジトリが再利用 | U-04, U-05, U-06 |
| U03-H5 | CSV エクスポートのサニタイザは注入（`identity_sanitizer` が既定）。U-07 が U-06 の `SEC-05.sanitize_csv_cell` を注入 | U-06, U-07 |
| U03-H9 | `DataIntegrityError` を追加済み（PII なし）| （完了）|
| U03-H10 | 同一トランザクション再計算は PoC 選択。実運用で行数増大時に別トランザクション + 修復経路を再検討 | 実運用移行時 |

---

## 7. 拡張ルール適合サマリ

| ルール | 判定 |
|--------|------|
| SECURITY-01（保存時暗号化）| ✅ 暗号化ボリューム（インフラ委譲）|
| SECURITY-03（ログに PII なし）| ✅ echo=False、エラーは ID のみ。CSV/例外に氏名を含めないことをテストで確認 |
| SECURITY-05（パラメータ化/入力検証）| ✅ Core 式言語、CSV Phase 2 検証 |
| SECURITY-10（サプライチェーン）| ✅ sqlalchemy/alembic 固定 |
| SECURITY-13（データ完全性）| ✅ 制約 + fail closed |
| SECURITY-15（fail closed）| ✅ 原子性・未知値拒否・DB 復元時検証 |
| PBT-01〜10 | ✅ 7 プロパティ + ステートフルテスト、Hypothesis、生成器再利用 |
| Resiliency | スキップ（無効）|

**ブロッキング所見: なし**
