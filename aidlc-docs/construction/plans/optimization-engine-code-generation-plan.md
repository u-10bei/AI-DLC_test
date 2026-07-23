# Code Generation Plan — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Code Generation（ユニット 4 / 8）
**このプランが Code Generation の唯一の正典である。**

---

## 1. ユニットコンテキスト

| 項目 | 内容 |
|------|------|
| ユニット | U-04 `optimization-engine`（`src/optimization_engine/`）|
| 依存 | U-01 shared_kernel, U-02 distance_cost, U-03 data_management |
| ストーリー | US-16〜US-20（最適化実行、目的調整、実行不可能診断、時間制限内の最良解、再最適化）|
| プロダクション依存 | `ortools==9.11.4210`（CP-SAT、Apache-2.0、検証済み）|
| ソルバー | OR-Tools CP-SAT（H-3 解決）。`ortools` は CpSatAdapter に閉じ込め |

### 1.1 コンポーネント → ファイル

| 論理コンポーネント | ファイル |
|------------------|---------|
| MilpModel / SolveOutcome / 索引 / 整数スケール | `src/optimization_engine/model.py` |
| LC-01 ModelBuilder（純粋）| `src/optimization_engine/builder.py` |
| SolverPort（抽象）| `src/optimization_engine/solver_port.py` |
| LC-02 CpSatAdapter（★ ortools 閉じ込め）| `src/optimization_engine/cp_sat_adapter.py` |
| LC-03 InfeasibilityDiagnoser | `src/optimization_engine/diagnoser.py` |
| LC-04 ResultMapper | `src/optimization_engine/result_mapper.py` |
| LC-05 OptimizationService | `src/optimization_engine/service.py` |
| 例外（U04-H7）| `src/optimization_engine/exceptions.py` |
| 結果永続化（U04-H4）| `src/optimization_engine/repository.py` |

---

## 2. 設計上の制約（成果物から）

- **CP-SAT ネイティブ制約**（DP-01）: C1 `Add(sum==headcount)`, C2 `AddAtMostOne`, C3/C5 線形, T_max 線形, ピン `Add(x==1)`
- **整数スケール目的**（DP-02）: 正規化 + 固定精度 `S`、整数 big-M `M_int = S·U_obj + 1`、INV-12 保存
- **ortools 閉じ込め**（DP-03）: `import ortools` は `cp_sat_adapter.py` のみ
- **段階的求解**（DP-04）: 各 solve に予算、最悪 3×
- **fail closed**（DP-05）: BR-07 通過、実行不可能は `InfeasibilityDiagnosis` 戻り値、ピン違反は例外
- **再現性 + ログ抑制**（DP-06）: シード/ワーカー数固定、`log_search_progress=False`、変数名は ID のみ
- C1 等号（Q1）、C4 は available_staff のみ変数化（構造保証）

---

## 3. 生成ステップ（順次、完了ごとに [x]）

### Step 1: 構造と依存
- [x] `src/optimization_engine/__init__.py`, `tests/optimization_engine/__init__.py`
- [x] `pyproject.toml`: `dependencies` に `ortools==9.11.4210` 追加。wheel packages に `optimization_engine` 追加（SECURITY-10, U04-H8）
- **ストーリー**: 基盤

### Step 2: 例外（U04-H7）
- [x] `exceptions.py`: `PinnedAssignmentInfeasibleError`, `ModelConstructionError`（`DomainError` 継承、文脈は制約/施設/部署 ID のみ、PII なし）
- **ストーリー**: US-19, US-20

### Step 3: 抽象モデル型 `model.py`（DP-02）
- [x] `DecisionVariableIndex`（(StaffId, FacilityId)）、`MilpModel`（変数集合・整数目的係数・制約・T_max・ピン・big-M）
- [x] 整数スケール: 正規化 + 固定精度 `S`（既定 10^6, 外部化 U04-H9）。`M_int = S·U_obj + 1`
- [x] `SolveOutcome`（feasible, assignments, objective_value, optimality_gap, status, c3_violations）
- [x] `ServiceHistory`（履歴フック、既定 weight=0）
- **ストーリー**: US-16, US-17

### Step 4: ソルバーポート `solver_port.py`
- [x] `SolverPort`（Protocol）: `solve(MilpModel, time_limit_seconds, seed, workers) -> SolveOutcome`
- **ストーリー**: 基盤（依存逆転）

### Step 5: ModelBuilder `builder.py`（LC-01, 純粋・ortools 非依存）
- [x] `AssignmentProblem` → `MilpModel`。変数（available_staff × facilities）、C1〜C5、T_max、ピン、整数スケール目的（DP-02）、履歴フック
- [x] 適格判定（C3: job_type/position/qualifications と要件の照合）
- [x] `travel_matrix` 欠落で `ModelConstructionError`
- **ストーリー**: US-16, US-17

### Step 6: CpSatAdapter `cp_sat_adapter.py`（LC-02, ★ ortools 閉じ込め）
- [x] `SolverPort` 実装。**唯一 `from ortools.sat.python import cp_model`**
- [x] `MilpModel` → `CpModel`（DP-01 ネイティブ制約）。変数名は ID のみ
- [x] ソルバー設定: `max_time_in_seconds`, `random_seed`, `num_search_workers`（固定）, `log_search_progress=False`（DP-06）
- [x] 結果 → `SolveOutcome`（status→SolverStatus, best objective, gap）
- **ストーリー**: US-16, US-20

### Step 7: InfeasibilityDiagnoser `diagnoser.py`（LC-03, 決定木）
- [x] Functional Design Q4 の決定木。全制約→C3 緩和→(C3 降格 / 総数不足 / C2C4C5)
- [x] `InfeasibilityCause`, `InfeasibilityDiagnosis`（原因 + 施設/制約 ID, PII なし）
- [x] 各 solve に時間予算（DP-04）
- **ストーリー**: US-18

### Step 8: ResultMapper `result_mapper.py`（LC-04）
- [x] `SolveOutcome` → `AssignmentResult`（BR-07 通過、fail closed, DP-05）
- [x] C3 降格の `violations` を `ConstraintViolation` で表現
- **ストーリー**: US-16, US-18

### Step 9: OptimizationService `service.py`（LC-05, 統括）
- [x] `optimize(problem, history=ServiceHistory())`: build → (ピン検証) → solve → (診断) → map
- [x] ピン留め事前検証（C1〜C5、違反で `PinnedAssignmentInfeasibleError`、solve しない, DP-05）
- [x] 時間制限（`OptimizationParameters.time_limit_seconds`）、SolverPort を注入（既定 CpSatAdapter）
- **ストーリー**: US-16〜US-20

### Step 10: 結果永続化 `repository.py`（U04-H4）
- [x] `AssignmentResult` を U-03 の `assignment_results`/`constraint_violations` 骨格テーブルに保存（data_management の engine/schema 再利用、U03-H4 パターン）
- **ストーリー**: US-16

### Step 11: リンタ契約 `.importlinter`
- [x] `optimization_engine` を root に追加
- [x] R-5: `optimization_engine` は `shared_kernel`/`distance_cost`/`data_management` のみ import 可、`security`/`comparison_report`/`api_orchestration`/`frontend` 禁止
- [x] 第三者: `ortools` 許可、`pydantic`/`fastapi` 禁止
- [x] Step 15 で非空虚性確認（`import fastapi` で BROKEN）
- **ストーリー**: 基盤

### Step 12: テスト基盤 + 生成器 `tests/optimization_engine/`
- [x] `generators.py`: 求解可能な小規模問題の生成器（feasible 保証）+ 実行不可能ケース生成器。U-01 の `gen_assignment_problem` を活用
- **ストーリー**: 検証基盤

### Step 13: 例示テスト `test_examples.py`
- [x] 小規模の既知最適解、目的値の一致（オラクル）
- [x] 実行不可能診断の各分岐（総数不足 / C3 のみ→降格 / C2C4C5）
- [x] ピン留め検証（違反で solve せずエラー）、ピン留め保存
- [x] 時間制限（極小 time_limit で TIME_LIMIT_REACHED + gap）
- [x] 診断・エラーに PII なし
- **ストーリー**: US-16〜US-20

### Step 14: プロパティテスト `test_properties.py`（PBT-01）
- [x] P-OPT01〜05（C1 等号, C2 一意, C3 資格, C4 従事不可非割当, C5 部署上限）
- [x] P-OPT06（目的有限非負, INV-06）, P-OPT07（gap∈[0,1]）, P-OPT08（ピン保存）
- [x] **P-OPT12（INV-12）**: C3 充足解が存在する問題で降格 solve が C3 違反 0（メタモルフィック）
- [x] P-OPT10（オラクル）: 極小問題を総当たりし CP-SAT の最適値と一致
- [x] P-OPT09（PII なし）
- **ストーリー**: US-16〜US-20

### Step 15: ドキュメント + 4 ゲート
- [x] `aidlc-docs/construction/optimization-engine/code/implementation-summary.md`
- [x] `pytest`（U-01〜U-03 回帰なし + U-04 新規）
- [x] `mypy --strict`（clean）
- [x] `ruff`（clean）
- [x] `lint-imports`（全契約 kept）+ 非空虚性確認（`import fastapi` → BROKEN）
- [x] すべて green まで修正
- **ストーリー**: 品質ゲート

---

## 4. ストーリートレーサビリティ（US-16〜US-20）

| ストーリー | 実装ステップ |
|-----------|------------|
| US-16 最適化実行 | Step 3,5,6,8,9,10,13,14 |
| US-17 目的関数調整（重み）| Step 3,5,13 |
| US-18 実行不可能診断 | Step 7,8,13,14 |
| US-19 ピン留め検証 | Step 2,9,13 |
| US-20 時間制限内の最良解 | Step 6,8,9,13,14 |

---

## 5. 想定スコープ

- **新規アプリコード**: `src/optimization_engine/`（9 ファイル）
- **修正（in-place）**: `pyproject.toml`, `.importlinter`
- **新規テスト**: `tests/optimization_engine/`（generators, test_examples, test_properties）
- **ドキュメント**: `implementation-summary.md`
- **15 ステップ**。4 ゲート green で完了

---

## 6. 完了基準

- 全 15 ステップ [x]、US-16〜US-20 実装
- 4 ゲート pass、import 契約が非空虚（`ortools` は cp_sat_adapter に限定）
- U-01〜U-03 の既存テストが回帰しない
- 個人情報が診断/ログ/変数名に出ない（SECURITY-03）を確認
- INV-12（big-M の正しさ）をプロパティで確認
