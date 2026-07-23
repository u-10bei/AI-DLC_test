# Code Generation Plan — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Code Generation（ユニット 7 / 8）
**このプランが Code Generation の唯一の正典である。**

---

## 1. ユニットコンテキスト

| 項目 | 内容 |
|------|------|
| ユニット | U-07 `api-orchestration`（`src/api_orchestration/`）|
| 依存 | **U-01〜U-06 のすべて**（統合点）。`frontend` は禁止 |
| プロダクション依存 | `fastapi==0.115.6`, `uvicorn==0.34.0`, `pydantic==2.10.4`（**検証済み**）+ `sqlalchemy`（既存）|
| dev 依存 | `httpx==0.28.1`（TestClient）|

### 1.1 コンポーネント → ファイル

| LC | ファイル |
|----|---------|
| 識別子・ジョブ型（U07-H7）| `identifiers.py`, `jobs.py` |
| 設定 | `config.py`（`AppConfig`）|
| LC-03 dto | `dto.py`（Pydantic）|
| LC-04 converters | `converters.py`（純関数, U07-H8）|
| LC-07 session_store | `session_store.py`（`SqlSessionStore`, U07-H2）|
| LC-06 job_queue | `job_queue.py`（条件付き UPDATE, U07-H3）|
| 問題構築 | `problem_builder.py`（U-03 + U-02 → `AssignmentProblem`, U07-H4）|
| LC-08 worker | `worker.py`（`step()`/`run_forever()` + `__main__`）|
| LC-09 errors | `errors.py`（例外 → 汎用応答）|
| LC-01 app | `middleware.py`（ヘッダ・IP・レート・**認証 DP-01**・認可）|
| LC-02 routers | `routers.py` |
| LC-05 composition | `composition.py`（`build_application`）|

---

## 2. 設計上の制約（成果物から）

- **DP-01**: 認証は**ミドルウェア + `PUBLIC_ROUTES` 許可リスト**（ログイン・ヘルスのみ）。新ルートは既定で保護
- **DP-02**: 順序 = ヘッダ → SEC-03 → SEC-04 → SEC-01 → SEC-02 → SEC-05。例外 → 汎用応答、未知は 500
- **DP-03**: claim は `UPDATE ... WHERE state='QUEUED'` + rowcount
- **U07-H13（重要）**: **求解を書き込みトランザクションの外で実行**。claim/save は短いトランザクション。`engine.begin()` の中で `optimize()` を呼ばない（**API が 300 秒停止する**）
- **DP-04**: `step()`/`run_forever()` 分離
- **DP-05**: DTO 変換は純関数（ラウンドトリップ検証）
- **DP-06**: 合成ルートで `SqlSessionStore`（U06-H2）と `sanitize_csv_cell`（U06-H3）を注入
- **DP-07**: セキュリティヘッダ、HttpOnly Cookie、PII は必要な画面のみ

---

## 3. 生成ステップ（順次、完了ごとに [x]）

### Step 1: 構造と依存（U07-H9）
- [x] `src/api_orchestration/__init__.py`, `tests/api_orchestration/__init__.py`
- [x] `pyproject.toml`: `fastapi==0.115.6`, `uvicorn==0.34.0`, `pydantic==2.10.4` を `dependencies` に、`httpx==0.28.1` を dev に追加。wheel packages に `api_orchestration`
- **ストーリー**: 基盤

### Step 2: **U-04 に公開の制約検証関数を追加（in-place, U07-H1）**
- [x] `optimization_engine` に `validate_assignments(problem, assignments) -> tuple[ConstraintViolation, ...]` を公開（C1〜C5 を検証）
- [x] 既存の `OptimizationService._validate_pins` と**ロジックを共有**（重複させない）
- [x] `optimization_engine/__init__.py` からエクスポート。U-04 の既存テストが回帰しないこと
- **ストーリー**: US-22, FR-06.3

### Step 3: 識別子・ジョブ型・設定（U07-H7）
- [x] `identifiers.py`: `JobId`（NewType）
- [x] `jobs.py`: `JobState`（QUEUED/RUNNING/SUCCEEDED/INFEASIBLE/FAILED）、`ReoptimizationMode`（FULL/INCREMENTAL）、`OptimizationJob`（frozen）
- [x] `config.py`: `AppConfig`（database_url, audit_log_path, security: `SecurityConfig`, worker_poll_seconds=2, travel/optimization の既定）
- **ストーリー**: US-16, US-24

### Step 4: DTO `dto.py`（LC-03, SECURITY-05）
- [x] `LoginRequest`, `EventRequest/Response`, `ImportResultResponse`, `SufficiencyResponse`, `OptimizationRequest`, `JobAcceptedResponse`, `JobStatusResponse`, `AssignmentResponse`, `AssignmentPatchRequest`, `ConstraintViolationResponse`, `ComparisonResponse`
- **ストーリー**: 全般

### Step 5: converters `converters.py`（LC-04, U07-H8）
- [x] `to_domain_*` / `from_domain_*` の**純関数**
- [x] **P-API01（ラウンドトリップ）** を満たす設計
- **ストーリー**: 全般

### Step 6: `session_store.py`（LC-07, U07-H2, U06-H2）
- [x] `SqlSessionStore`（`SessionStorePort` 実装）。U-03 の `sessions` テーブル + `accounts` を扱う
- [x] **注**: U-03 の `sessions` 骨格は id/created_at/expires_at のみ。**アカウントとセッションの列を追加するマイグレーションが必要**（下記 Step 7）
- **ストーリー**: US-01

### Step 7: スキーマ拡張マイグレーション（U-03 の骨格を実用化）
- [x] `accounts` テーブル（user_id, password_hash, role, failed_attempts, locked_until）を追加
- [x] `sessions` に user_id/role 列を追加（骨格は id/created_at/expires_at のみのため）
- [x] `optimization_jobs` に mode/result_id/detail 列を追加
- [x] `data_management/schema.py` を **in-place 修正** + Alembic リビジョン追加
- **ストーリー**: US-01, US-16

### Step 8: `job_queue.py`（LC-06, DP-03, U07-H3）
- [x] `enqueue(engine, job)`（短いトランザクション）
- [x] `claim_next(engine, now) -> OptimizationJob | None`（**条件付き UPDATE + rowcount**）
- [x] `mark_succeeded/mark_infeasible/mark_failed`（短いトランザクション）
- [x] `get_job(engine, job_id)`
- **ストーリー**: US-16, US-20

### Step 9: `problem_builder.py`（U07-H4）
- [x] `build_problem(engine, event_id, params, travel_params, mode, previous_assignments) -> AssignmentProblem`
- [x] U-03 から職員/施設/小学校区/有効申告を取得 → **U-02 で移動行列**（U-05 の `metrics_for` と同じ規則）
- [x] INCREMENTAL のとき前回割当を `pinned_assignments` に
- **ストーリー**: US-16, US-24

### Step 10: `worker.py`（LC-08, DP-04, **U07-H13**）
- [x] `step(engine, now) -> bool`: claim（短 tx）→ **求解（tx 外）** → 保存（短 tx）
- [x] `run_forever(...)`: `step()` をポーリング（間隔は設定）
- [x] `__main__`: CLI エントリポイント
- [x] **`engine.begin()` の中で `optimize()` を呼ばない**（U07-H13）
- **ストーリー**: US-16, US-20

### Step 11: `errors.py`（LC-09, DP-02, U01-H14）
- [x] 例外 → 汎用応答（403/429/401/403/400/500）。**スタックトレース・内部パスを出さない**
- [x] `CsvImportError` は行番号付き全エラー（PII なし）
- **ストーリー**: US-07, 全般

### Step 12: `middleware.py`（LC-01, **DP-01**）
- [x] セキュリティヘッダ（SECURITY-04）
- [x] SEC-03 IP → SEC-04 レート → **SEC-01 認証（`PUBLIC_ROUTES` 許可リスト方式）**
- [x] `PUBLIC_ROUTES` = `{("POST","/sessions"), ("GET","/health")}` のみ（U07-H11）
- **ストーリー**: US-01, US-02

### Step 13: `routers.py`（LC-02）+ `composition.py`（LC-05, DP-06）
- [x] エンドポイント: `/health`, `POST|DELETE /sessions`, `POST|GET /events`, `POST /masters/staff/import`, `GET /masters/staff/export`, `POST /events/{id}/declarations/import`, `GET /events/{id}/sufficiency`, `POST /optimizations`, `GET /optimizations/{job_id}`, `GET /events/{id}/assignments`, `PATCH /events/{id}/assignments`, `GET /events/{id}/comparison`
- [x] 認可は `require_authorization` を明示的に呼ぶ
- [x] `PATCH` は **U-04 の公開検証関数**を呼ぶ（Step 2, FR-06.3）
- [x] `build_application(config) -> FastAPI`: 全ユニットを手組み。**`SqlSessionStore` を U-06 に注入**（U06-H2）、**`sanitize_csv_cell` を CSV 出力に注入**（U06-H3）
- **ストーリー**: US-01〜US-28 の API 公開

### Step 14: リンタ契約 `.importlinter`（U07-H10）
- [x] `api_orchestration` を root に追加。R-8: `frontend` を禁止（他ユニットは許可）
- [x] 第三者: `fastapi`/`uvicorn`/`pydantic`/`sqlalchemy` を許可（**U-07 のみ**）
- [x] Step 16 で**非空虚性を確認**（`import frontend` で BROKEN）
- **ストーリー**: 基盤

### Step 15: テスト `tests/api_orchestration/`
- [x] `support.py`: インメモリ SQLite + `build_application` + TestClient、ログイン済みクライアント
- [x] `test_examples.py`: **未認証は 401**、**IP 非許可は 403**、レート超過 429、ログイン/ログアウト、**セキュリティヘッダ**、DTO 検証 422、CSV エクスポートがサニタイズ済み（**P-API07**）、手動修正の制約検証、ジョブ投入 202 → worker step → 完了
- [x] `test_properties.py`: **P-API01**（DTO ラウンドトリップ）、P-API02/03/04/06
- [x] `test_stateful.py`: **PBT-06** ジョブ状態機械（終端から遷移しない、二重 claim しない）
- **ストーリー**: 全般

### Step 16: ドキュメント + 文書修正 + 4 ゲート
- [x] `shared-infrastructure.md` セクション 2 のワーカー所有ユニットを **U-04 → U-07** に修正（**U07-H14**）
- [x] `aidlc-docs/construction/api-orchestration/code/implementation-summary.md`
- [x] `pytest`（U-01〜U-06 回帰なし + U-07 新規）
- [x] `mypy --strict`（clean）
- [x] `ruff`（clean）
- [x] `lint-imports`（全契約 kept）+ 非空虚性確認
- [x] すべて green まで修正
- **ストーリー**: 品質ゲート

---

## 4. 想定スコープ

- **新規アプリコード**: `src/api_orchestration/`（12 ファイル）
- **修正（in-place）**: `pyproject.toml`, `.importlinter`, **`optimization_engine`（公開検証関数, U07-H1）**, **`data_management/schema.py` + Alembic（accounts/sessions/jobs 列, Step 7）**, `shared-infrastructure.md`（U07-H14）
- **新規テスト**: `tests/api_orchestration/`（support, examples, properties, **stateful**）
- **16 ステップ**。4 ゲート green で完了

---

## 5. 完了基準

- 全 16 ステップ [x]
- 4 ゲート pass、`import frontend` で契約が BROKEN
- U-01〜U-06 の既存テストが回帰しない
- **未認証が 401、非許可 IP が 403** をテストで確認（DP-01 の実証）
- **CSV エクスポートがサニタイズされている**（P-API07 = 注入忘れの検出）
- **求解が書き込みトランザクション外**（U07-H13）
