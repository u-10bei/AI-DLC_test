# Code Generation Implementation Summary — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Code Generation（ユニット 5 / 8）
**結果**: 4 ゲートすべて green。**プロダクション依存ゼロ**。システムの価値提案（削減効果）を実証

---

## 1. 生成物

### 新規アプリコード（`src/comparison_report/`）

| ファイル | 役割 | LC |
|---------|------|----|
| `__init__.py` | 公開 API | - |
| `metrics.py` | `make_metrics_for`（単一純関数, DP-01）、`Master` | LC-01 補助 |
| `report.py` | `ComparisonReport`, `ManualBaseline`（PII なし）| - |
| `replay.py` | `build_replay`（実績→再現問題）| LC-01 |
| `evaluator.py` | `evaluate_totals`, `objective_of`（U-04 目的値）| LC-02 |
| `service.py` | `ComparisonService`（統括、fail closed）| LC-03 |
| `exporter.py` | `export_report_csv`（U-03 `serialize_csv`）| LC-04 |
| `repository.py` | `parse_historical_assignments`, `save_historical_marker` | LC-05 |

### in-place 修正

| ファイル | 変更 |
|---------|------|
| `pyproject.toml` | wheel packages に `comparison_report`（**新規プロダクション依存なし**）|
| `.importlinter` | R-6 境界契約 + web フレームワーク禁止 |

### 新規テスト（`tests/comparison_report/`）

`support.py`、`test_examples.py`（削減あり・負の削減・実行不可能な再現・手動ベースライン・PII なし・実績パース、6 例）、`test_properties.py`（P-CMP01〜05）

---

## 2. 設計判断の実装

| パターン | 実装 |
|---------|------|
| DP-01 `metrics_for` 単一純関数 | `make_metrics_for` を ReplayBuilder と BaselineEvaluator が共有。差は割当ルールに帰属（FR-05.1.4）|
| DP-02 距離・費用の再利用 | U-02 `compute_travel_metrics`（同一校区も対応）|
| DP-03 目的値優越性 | `objective_of` = U-04 `normalised_objective` |
| DP-04 fail closed | 実行不可能な再現は U-04 `InfeasibilityDiagnosis` をパススルー |
| DP-05 削減指標 + PII | 0 除算ガード、集計 + ID のみ |

---

## 3. 4 ゲートの結果

| ゲート | 結果 |
|-------|------|
| `pytest` | **119 passed**（U-01〜04 の 110 + U-05 の 9。回帰なし）|
| `mypy --strict` | **clean（65 files）** |
| `ruff` | **clean** |
| `lint-imports` | **10 契約 kept**。`import fastapi` を comparison_report に注入 → BROKEN（非空虚性確認）|

---

## 4. 価値提案の実証（スモーク + テスト）

遠方職員が割り当てられていた実績（総移動時間 11,198 秒・費用 ¥37,326）に対し、最適化は**近接職員**を選び（同一校区、900 秒・¥0）、**時間 91.96%・費用 100% 削減**を提示。これがシステム全体の目的（居住地考慮による負担・費用削減）を数値で示す（SC-01）。

**P-CMP03（メタモルフィック）**: 実行可能なベースラインに対し、最適化の目的値が常にベースライン以下であることをプロパティで確認。

---

## 5. 計画からの特記

1. **削減量は負を許す**: 最適化は重み付き目的を最小化するため、費用重視の重みでは総移動時間が増えうる（BR-CMP08、テストで確認）
2. **実績の全明細永続化は将来**: `historical_records` 骨格にマーカー行を保存。全実績割当/申告の永続化は `historical_assignments`/`historical_declarations` テーブルの追加（後続マイグレーション）が必要（U05-H6）。PoC の比較フローはインメモリ `HistoricalRecord` で動作
3. **A-10 注記**: 過去申告が一部欠落する場合、削減効果が控えめに出る旨を `ComparisonReport.note` に記録

---

## 6. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| U05-H1（解決）| `distance_cost` 依存 + リンタ契約 | （完了）|
| U05-H3（解決）| `metrics_for`（U-02 再利用）| （完了）|
| U05-H4（解決）| 目的値優越性は U-04 `normalised_objective` | （完了）|
| U05-H5（解決）| `ComparisonReport`/`ManualBaseline` 定義済み | （完了）|
| **U05-H6（新規）** | `historical_assignments`/`historical_declarations` テーブルの追加（全実績明細の永続化）| 後続マイグレーション / 運用 |

---

## 7. 拡張ルール適合サマリ

| ルール | 判定 |
|--------|------|
| SECURITY-03（PII 非露出）| ✅ レポート・CSV は集計 + ID のみ（テストで確認）|
| SECURITY-05（入力検証）| ✅ 実績パースの検証（U-03 パターン）|
| SECURITY-15（fail closed）| ✅ 実行不可能は診断パススルー |
| PBT-01〜10 | ✅ P-CMP01〜05 |
| SECURITY-10 | ✅ 新規依存なし |
| Resiliency | スキップ（無効）|

**ブロッキング所見: なし**
