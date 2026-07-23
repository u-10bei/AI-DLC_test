# Code Generation Plan — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Code Generation（ユニット 5 / 8）
**このプランが Code Generation の唯一の正典である。**

---

## 1. ユニットコンテキスト

| 項目 | 内容 |
|------|------|
| ユニット | U-05 `comparison-report`（`src/comparison_report/`）|
| 依存 | U-01, U-02 `distance_cost`, U-03 `data_management`, U-04 `optimization_engine`（U05-H1）|
| ストーリー | US-26〜US-28（実績インポート、比較レポート、CSV エクスポート）|
| プロダクション依存 | **なし**（既存ユニットの組み合わせ + 純粋集計）|

### 1.1 コンポーネント → ファイル

| 論理コンポーネント | ファイル |
|------------------|---------|
| `metrics_for`（DP-01/02）| `src/comparison_report/metrics.py` |
| ComparisonReport / ManualBaseline（U05-H5）| `src/comparison_report/report.py` |
| LC-01 ReplayBuilder | `src/comparison_report/replay.py` |
| LC-02 BaselineEvaluator | `src/comparison_report/evaluator.py` |
| LC-03 ComparisonService | `src/comparison_report/service.py` |
| LC-04 ReportExporter | `src/comparison_report/exporter.py` |
| LC-05 HistoricalRepository | `src/comparison_report/repository.py` |

---

## 2. 設計上の制約（成果物から）

- **`metrics_for` 単一純関数**（DP-01）: U-02 の `compute_travel_metrics`（同一校区は距離0/費用0/固定時間, FR-03.7 既対応）を再利用。ReplayBuilder と BaselineEvaluator が同一関数を使う
- **目的値優越性**（DP-03）: U-04 `scaling.normalised_objective` を再利用
- **fail closed**（DP-04）: 実行不可能な再現は U-04 `InfeasibilityDiagnosis` をパススルー
- **削減指標**（DP-05）: `reduction = base − opt`（負可）、`rate = reduction/base`（0 除算ガード）、PII なし
- 現在マスタ値使用（FR-05.1.5, A-09）、必要人数=実績（FR-05.1.2）、対象=従事可能集合（FR-05.1.3）

---

## 3. 生成ステップ（順次、完了ごとに [x]）

### Step 1: 構造と依存
- [x] `src/comparison_report/__init__.py`, `tests/comparison_report/__init__.py`
- [x] `pyproject.toml` の wheel packages に `comparison_report` 追加（**新規プロダクション依存なし**）
- **ストーリー**: 基盤

### Step 2: レポート型 `report.py`（U05-H5）
- [x] `ComparisonReport`（frozen, 集計 + event_id + note, PII なし）
- [x] `ManualBaseline`（frozen, event_id + actual_assignments + availability_declarations, FR-05.1.6）
- **ストーリー**: US-27

### Step 3: `metrics.py`（DP-01/02, U05-H3）
- [x] `make_metrics_for(districts_by_id, params) -> Callable[[Staff, Facility], TravelMetrics]`
- [x] U-02 `compute_travel_metrics` を再利用（同一校区規則は U-02 が対応）
- **ストーリー**: US-27

### Step 4: ReplayBuilder `replay.py`（LC-01, FR-05.1.2〜1.5）
- [x] `build_replay(record, current_staff, facilities_by_id, districts_by_id, params) -> AssignmentProblem`
- [x] 必要人数=実績割当人数、対象=従事可能申告者（現在マスタから）、travel_matrix=`metrics_for`
- **ストーリー**: US-27

### Step 5: BaselineEvaluator `evaluator.py`（LC-02, DP-01/03）
- [x] `evaluate_totals(assignments, metrics_for) -> (time_seconds, cost_yen)`
- [x] `objective_of(problem, assignments) -> float`（U-04 `normalised_objective` 再利用）
- **ストーリー**: US-27

### Step 6: ComparisonService `service.py`（LC-03, DP-04/05）
- [x] `compare(record, master, params, *, solver_service=None, now=None) -> ComparisonReport | InfeasibilityDiagnosis`
- [x] ReplayBuilder → U-04 optimize → (実行不可能なら診断パススルー) → BaselineEvaluator → 削減指標（0 除算ガード）
- [x] `note` に A-10 等の制約を記録（PII なし）
- **ストーリー**: US-26, US-27

### Step 7: ReportExporter `exporter.py`（LC-04, Q6）
- [x] `export_report_csv(report, *, sanitize=identity) -> bytes`（U-03 `serialize_csv` 再利用）
- [x] 集計指標のみ（PII なし）。明細を含める場合は ID のみ
- **ストーリー**: US-28

### Step 8: HistoricalRepository `repository.py`（LC-05, U05-H2）
- [x] `HistoricalRecord` の保存/取得（U-03 の `historical_records` 骨格 + engine/schema 再利用）
- **ストーリー**: US-26

### Step 9: `__init__.py`
- [x] 公開 API（ComparisonService, ComparisonReport, ManualBaseline, make_metrics_for, build_replay, export_report_csv）
- **ストーリー**: 基盤

### Step 10: リンタ契約 `.importlinter`（U05-H1）
- [x] `comparison_report` を root に追加
- [x] R-6: `comparison_report` は `shared_kernel`/`distance_cost`/`data_management`/`optimization_engine` のみ import 可、`security`/`api_orchestration`/`frontend` 禁止
- [x] 第三者: `pydantic`/`fastapi` 禁止
- [x] Step 12 で非空虚性確認（`import fastapi` で BROKEN）
- **ストーリー**: 基盤

### Step 11: テスト `tests/comparison_report/`
- [x] `support.py`（決定的ビルダ: HistoricalRecord + 現在マスタ）
- [x] `test_examples.py`: 削減あり/負の削減、実行不可能な再現（診断）、手動ベースライン、CSV に PII なし
- [x] `test_properties.py`: P-CMP01（一貫性）, P-CMP02（率, 0 除算）, P-CMP03（実行可能ベースラインで opt目的値 ≤ base目的値）, P-CMP04（同一基準）, P-CMP05（PII なし）
- **ストーリー**: US-26〜US-28

### Step 12: ドキュメント + 4 ゲート
- [x] `aidlc-docs/construction/comparison-report/code/implementation-summary.md`
- [x] `pytest`（U-01〜U-04 回帰なし + U-05 新規）
- [x] `mypy --strict`（clean）
- [x] `ruff`（clean）
- [x] `lint-imports`（全契約 kept）+ 非空虚性確認
- [x] すべて green まで修正
- **ストーリー**: 品質ゲート

---

## 4. ストーリートレーサビリティ（US-26〜US-28）

| ストーリー | 実装ステップ |
|-----------|------------|
| US-26 実績インポート | Step 8, 6 |
| US-27 比較レポート | Step 2〜6, 11 |
| US-28 CSV エクスポート | Step 7, 11 |

---

## 5. 想定スコープ

- **新規アプリコード**: `src/comparison_report/`（8 ファイル）
- **修正（in-place）**: `pyproject.toml`（wheel packages のみ）, `.importlinter`
- **新規テスト**: `tests/comparison_report/`
- **ドキュメント**: `implementation-summary.md`
- **12 ステップ**。4 ゲート green で完了

---

## 6. 完了基準

- 全 12 ステップ [x]、US-26〜US-28 実装
- 4 ゲート pass、import 契約が非空虚
- U-01〜U-04 の既存テストが回帰しない
- レポート/エクスポートに個人情報が出ない（SECURITY-03）を確認
- P-CMP03（優越性）をプロパティで確認
