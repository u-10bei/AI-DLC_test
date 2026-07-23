# Code Generation Plan — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Code Generation（ユニット 3 / 8）
**このプランが Code Generation の唯一の正典（single source of truth）である。**

---

## 1. ユニットコンテキスト

| 項目 | 内容 |
|------|------|
| ユニット | U-03 `data-management`（`src/data_management/`） |
| 依存 | U-01 `shared_kernel`, U-02 `distance_cost`（ユニットとして import 可） |
| 実装するストーリー | US-05〜US-13（イベント登録/削除、マスタ CSV インポート、個別修正、従事可否申告、再申告/履歴、充足集計） |
| 所有するテーブル | departments, school_districts, staff(+staff_qualifications), facilities(+facility_qualification_requirements), events, availability_declarations, assignments, distance_cache（+ 他ユニット用の骨格テーブル） |
| プロダクション依存（プロジェクト初）| `sqlalchemy`, `alembic`（バージョン固定、SECURITY-10、U03-H7） |
| 契約 | P-02 RepositoryPort, P-07 CsvCodecPort, P-03 DistanceCachePort（U-02 定義）を実装 |

### 1.1 コンポーネント → ファイルの対応

| 論理コンポーネント（NFR Design）| ファイル |
|-------------------------------|---------|
| LC-01 Engine/SessionFactory | `src/data_management/engine.py` |
| （テーブル定義）| `src/data_management/schema.py` |
| LC-03 Mapper（A-02）| `src/data_management/mappers.py` |
| LC-02 Repository（P-02, P-03 実装、A-02）| `src/data_management/repositories.py` |
| P-07 CsvCodec（A-04）| `src/data_management/csv_codec.py` |
| LC-04 Services（S-01, S-02, S-03）| `src/data_management/services.py` |
| LC-05 MigrationRunner | `alembic/`, `alembic.ini` |

---

## 2. 設計上の制約（成果物から）

- **fail closed**（BR-DM01, DP-01/02, SECURITY-15）: CSV は 2 相（解析+全検証 / 保存）。1 行でもエラーで全ロールバック
- **全エラー一括報告**（BR-DM02）: 行番号付き。個人情報を含めない（BR-DM14, DP-05）
- **SQLAlchemy Core + 手書きマッパ**（DP-06）。frozen 型、`__post_init__` 再実行、失敗で `DataIntegrityError`（DP-02, U03-H9）
- **executemany**（DP-03, NFR-P04）、**相関サブクエリ**で有効な申告（U03-H6）、**PRAGMA connect イベント**（U01-H15）、**echo=False**（DP-05）
- **距離キャッシュ全再計算**はマスタ更新と同一トランザクション（DP-04）。`distance_cost.compute_district_distance_matrix` を呼ぶ
- **数式インジェクション無害化**（BR-DM04, MU-02）はエクスポート時、サニタイズ関数を**注入**（U03-H5、U-06 に依存しない）
- **パラメータ化クエリ**（DP-07, SECURITY-05）、**ON DELETE CASCADE**（Q5=A, BR-DM10）
- 日時は UTC 保存、`events.scheduled_date` のみ JST 暦日（BR-DM 6 節, U01-H12）

---

## 3. 生成ステップ（順次実行、完了ごとに [x]）

### Step 1: プロジェクト構造と依存の設定
- [x] `src/data_management/__init__.py`, `tests/data_management/__init__.py` を作成
- [x] `pyproject.toml` を編集: `dependencies` に `sqlalchemy==2.0.36`, `alembic==1.14.0` を追加（固定、SECURITY-10, U03-H7）
- [x] `pyproject.toml` の wheel packages に `src/data_management` を追加
- [x] 依存ロック/`pip-audit` 対象への追加を明記（コメント）
- **ストーリー**: 基盤（全 US 共通）

### Step 2: `DataIntegrityError` を U-01 に追加（in-place、U03-H9）
- [x] `src/shared_kernel/exceptions.py` に `DataIntegrityError(DomainError)` を追加。文脈は `entity` + `entity_id` のみ（PII なし、DP-02, SECURITY-03）
- [x] `src/shared_kernel/__init__.py` の公開エクスポートに追加
- [x] U-01 の既存テストが壊れないこと（追加のみ、変更なし）
- **注**: U-01 の承認済みファイルを in-place 修正（複製を作らない）

### Step 3: テーブルスキーマ `schema.py`
- [x] SQLAlchemy Core `MetaData` + 全テーブルを定義（domain-entities.md 3 節）
- [x] 所有テーブル: departments, school_districts, staff, staff_qualifications, facilities, facility_qualification_requirements, events, availability_declarations, assignments, distance_cache
- [x] 骨格テーブル（他ユニット用、Q6=A）: assignment_results, constraint_violations, historical_records(+関連), optimization_jobs, sessions
- [x] 制約: FK, `ON DELETE CASCADE`（events/facilities 系）, `UNIQUE(staff_id, event_id, declared_at)`, `PK(event_id, staff_id)`（assignments）, `CHECK(district_a <= district_b)`, `CHECK(required_headcount >= 1)`, INDEX(申告の最新取得)
- **ストーリー**: US-05, US-06, US-08〜US-13（スキーマ基盤）

### Step 4: Engine / SessionFactory `engine.py`（LC-01）
- [x] `create_engine` + `sessionmaker`（プロセス内シングルトン）。**`echo=False`（全環境、DP-05）**
- [x] `connect` イベントで PRAGMA を方言分岐発行: SQLite のみ `WAL` / `busy_timeout=5000` / `foreign_keys=ON`（U01-H15）
- [x] 接続文字列を設定から取得（SQLite→PostgreSQL は文字列変更のみ、U01-H18）
- **ストーリー**: 基盤

### Step 5: マッパ `mappers.py`（LC-03, A-02, DP-06/02）
- [x] 各ドメイン型の `*_to_row` / `row_to_*`（Department, SchoolDistrict, Staff, Facility+QualificationRequirement, Event, AvailabilityDeclaration, Assignment, DistanceCacheEntry）
- [x] 読み込み時に `__post_init__` を再実行。拒否されたら `DataIntegrityError`（ID のみ、PII なし、BR-DM13, DP-02）
- [x] 更新は `dataclasses.replace()` 前提（BR-DM12）
- [x] 列挙値は英語識別子で保存（U01-H24, from/to_japanese は CSV 境界で）
- **ストーリー**: US-08〜US-13

### Step 6: CSV コーデック `csv_codec.py`（P-07, A-04）
- [x] 標準ライブラリ `csv` で解析（Phase 1）。UTF-8。ヘッダ行考慮
- [x] 直列化（エクスポート）: 数式インジェクション無害化（BR-DM04, MU-02）。**サニタイズ関数を引数注入**（U03-H5、U-06 非依存）
- [x] 日時: JST 解釈 → UTC 保存、`scheduled_date` は JST 暦日（U01-H12）
- **ストーリー**: US-07（インポート）, US-09（エクスポート）

### Step 7: リポジトリ `repositories.py`（LC-02, P-02/P-03, DP-07）
- [x] 集約ごとのリポジトリ（Department/SchoolDistrict/Staff/Facility/Event/Availability/Assignment/DistanceCache）
- [x] `executemany` 一括挿入（DP-03, NFR-P04）
- [x] 有効な申告 = 相関サブクエリ `MAX(declared_at)`（U03-H6, BR-DM06、SQLite/PostgreSQL 両対応）
- [x] `P-03 DistanceCachePort` 実装: `put_distances`, `get`, `invalidate_all`（U-02 のポート）
- [x] **自身では commit しない**。呼び出し元のサービスの `Session` を使う（DP-01）
- [x] すべて Core 式言語（パラメータ化、DP-07, SECURITY-05）
- **ストーリー**: US-08〜US-13

### Step 8: サービス `services.py`（LC-04, S-01/S-02/S-03, DP-01/03/04）
- [x] **S-02 MasterDataService**: `import_*`（2 相・単一パス・全エラー蓄積・1 トランザクション保存、BR-DM01/02/03）。個別修正（`replace` + UPDATE、BR-DM12, US-10）。小学校区インポート/修正のコミット後に距離キャッシュ全再計算を**同一トランザクション**（DP-04, 4 節）
- [x] **S-03 AvailabilityService**: 申告登録（追記のみ、BR-DM05/07, US-11）、履歴取得（降順, US-12）、充足 3 分類集計（`available+unavailable+undeclared==len(all_staff)`, BR-DM08, US-13）
- [x] **S-01 EventService**: 登録/編集（US-05）、ステータス遷移（事前条件検証 + `Event.transition_to()`, BR-DM09, 再開遷移含む）、削除（Confirmed 不可、CASCADE, BR-DM10, US-06）
- [x] トランザクション境界を所有（DP-01）。エラーに PII を含めない（BR-DM14）
- **ストーリー**: US-05, US-06, US-10, US-11, US-12, US-13

### Step 9: Alembic 初期化 + 初期マイグレーション（LC-05, U01-H18）
- [x] `alembic.ini`, `alembic/env.py`（`schema.py` の MetaData を参照、PRAGMA 適用）, `alembic/versions/` 初期リビジョン
- [x] 初期マイグレーションで全テーブル作成（骨格含む）。SQLite 固有 SQL を書かない
- [x] 接続文字列変更で PostgreSQL にも適用可能
- **ストーリー**: 基盤

### Step 10: リンタ契約 `.importlinter` の更新
- [x] `root_packages` に `data_management` を追加
- [x] 契約追加（R-4 相当）: `data_management` は `shared_kernel`, `distance_cost` のみ import 可、他ユニット禁止
- [x] 第三者契約: `data_management` は `sqlalchemy`, `alembic` を許可、`pydantic`, `fastapi`, `numpy` を禁止
- [x] Step 16 で**非空虚性を確認**（`import fastapi` の混入で BROKEN になること）
- **ストーリー**: 基盤（境界維持）

### Step 11: テスト基盤 `tests/data_management/`（U03-H8）
- [x] フィクスチャ: **テストごとに新規インメモリ SQLite**（`:memory:`）+ マイグレーション適用 + PRAGMA（特に `foreign_keys=ON`）。モック不使用
- [x] `generators.py`: U-01 の生成器を再利用。CSV バイト列生成器を追加（PBT-07）
- **ストーリー**: 検証基盤

### Step 12: 例示ベースの単体テスト `test_examples.py`
- [x] スキーマ制約（UNIQUE, CHECK, FK）、ON DELETE CASCADE（BR-DM10）
- [x] イベント遷移の事前条件（BR-DM09）、Confirmed 削除不可
- [x] 充足 3 分類（未申告を漏らさない、BR-DM08）
- [x] CSV 全エラー一括報告（行番号付き、PII なし、BR-DM02/14）、未知の列挙値拒否（BR-DM03）
- [x] 数式インジェクション無害化（BR-DM04、注入したサニタイザで）
- [x] DB 破損行で `DataIntegrityError`（BR-DM13, DP-02）
- **ストーリー**: US-05〜US-13

### Step 13: プロパティベーステスト `test_properties.py`（PBT-01〜05）
- [x] INV-10a（CSV ラウンドトリップ）, INV-10b（キャッシュラウンドトリップ）
- [x] P-DM01（インポート原子性）, P-DM02（有効申告の一意性）, P-DM03（3 分類の分割）, P-DM04（キャッシュキー正規化 `get(a,b)==get(b,a)`）, P-DM05（マッパラウンドトリップ）
- **ストーリー**: US-07, US-11, US-13, US-15（キャッシュ）

### Step 14: ステートフルテスト `test_stateful.py`（PBT-06）
- [x] `Event` 状態機械の `RuleBasedStateMachine`: ランダム遷移列、許可されない遷移は拒否、`Confirmed` は終端、各遷移後に DB とドメインの状態一致
- **ストーリー**: US-05, US-24（再開遷移）

### Step 15: ドキュメント要約
- [x] `aidlc-docs/construction/data-management/code/implementation-summary.md`（生成物一覧、設計判断、テスト結果、申し送り）
- **ストーリー**: -

### Step 16: 4 ゲートの実行と修正
- [x] `pytest`（U-01/U-02 の既存テストが回帰しないこと + U-03 の新規テスト）
- [x] `mypy --strict`（clean）
- [x] `ruff check`（clean）
- [x] `lint-imports`（全契約 kept）+ **非空虚性の確認**（`import fastapi` を data_management に注入 → BROKEN → 除去で復帰）
- [x] すべて green になるまで修正
- **ストーリー**: 品質ゲート

---

## 4. ストーリートレーサビリティ（US-05〜US-13）

| ストーリー | 実装ステップ |
|-----------|------------|
| US-05 イベント登録/編集 | Step 3, 8, 12, 14 |
| US-06 イベント削除（Confirmed 不可, CASCADE）| Step 3, 8, 12 |
| US-07 CSV インポート（fail closed, 全エラー）| Step 6, 8, 12, 13 |
| US-08/09 マスタ CSV（職員/施設/小学校区）| Step 5, 6, 7, 8 |
| US-10 個別修正（frozen replace）| Step 8, 12 |
| US-11 従事可否申告登録 | Step 7, 8, 13 |
| US-12 再申告/履歴 | Step 7, 8 |
| US-13 充足 3 分類集計 | Step 8, 12, 13 |
| US-15 距離キャッシュ（U-02 連携）| Step 7, 8, 13 |

---

## 5. 想定スコープ

- **新規アプリコード**: `src/data_management/`（7 ファイル）+ `alembic/`（env.py + 初期リビジョン）+ `alembic.ini`
- **修正（in-place）**: `pyproject.toml`, `.importlinter`, `src/shared_kernel/exceptions.py`, `src/shared_kernel/__init__.py`
- **新規テスト**: `tests/data_management/`（フィクスチャ, generators, test_examples, test_properties, test_stateful）
- **ドキュメント**: `implementation-summary.md`
- **合計 16 ステップ**。4 ゲート green で完了

---

## 6. 完了基準

- 全 16 ステップ [x]
- US-05〜US-13 実装
- 4 ゲートすべて pass、import 契約が非空虚
- U-01/U-02 の既存テストが回帰しない
- 個人情報がログ/エラーに出ない（BR-DM14, DP-05）を確認
