# ドメインエンティティ / モデル型 — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 5 / 8）

---

## 1. U-05 が新規定義する型（`src/comparison_report/`）

入力の `HistoricalRecord`、再現問題の `AssignmentProblem`、最適化結果の `AssignmentResult` は **U-01 が定義済み**。U-05 が新規に定義するのは**比較レポート型**のみ。

### 1.1 ComparisonReport（PII なし）

```text
@frozen
ComparisonReport:
    event_id: EventId
    baseline_time_seconds: int
    optimized_time_seconds: int
    time_reduction_seconds: int          # baseline - optimized（負可）
    time_reduction_rate: float           # reduction / baseline（baseline==0 なら 0）
    baseline_cost_yen: float
    optimized_cost_yen: float
    cost_reduction_yen: float
    cost_reduction_rate: float
    assigned_count: int                  # 最適化結果の割当人数
    note: str | None = None              # A-10 等の制約注記（PII なし）
```

**個人情報を含まない**（集計 + イベント ID + 注記のみ、SECURITY-03, BR-CMP11）。

### 1.2 ManualBaseline（FR-05.1.6, Q5）

```text
@frozen
ManualBaseline:
    event_id: EventId
    actual_assignments: tuple[Assignment, ...]
    availability_declarations: tuple[AvailabilityDeclaration, ...]
```

担当者入力から `HistoricalRecord` を構築するための入力型。実質 `HistoricalRecord` と同形であり、`HistoricalRecord` を直接構築してもよい。

---

## 2. 使用する U-01 の型

| 型 | 用途 |
|----|------|
| `HistoricalRecord` | ベースライン（実績割当 + 当時の申告）|
| `AssignmentProblem` | 再現問題（ReplayBuilder が構築）|
| `AssignmentResult` | 最適化結果（U-04）|
| `Assignment` | 実績・最適化の割当要素 |
| `AvailabilityDeclaration` | 当時の従事可否申告 |
| `Staff` / `Facility` / `SchoolDistrict` | 現在マスタ（U-03 から取得）|
| `TravelMetrics` | `metrics_for` の出力（U-02 で算出）|
| `TravelParameters` / `OptimizationParameters` | 迂回・速度・距離帯費用・目的重み |

---

## 3. 依存とポート

- **新規依存: U-02 `distance_cost`**（Q1=A, U05-H1）。移動行列の構築とベースライン評価に必要
- U-05 は `shared_kernel`(U-01), `distance_cost`(U-02), `data_management`(U-03), `optimization_engine`(U-04) を import 可
- 依存グラフは**非巡回**（U-02 は下層、U-04 は既に U-02 に依存）
- 実績の永続化は U-03 の `historical_records` 骨格（U03-H2, U05-H2）

---

## 4. データフロー

```text
HistoricalRecord + 現在マスタ(Staff/Facility/SchoolDistrict)
        │  ReplayBuilder（U-02 で travel_matrix）
        ▼
   AssignmentProblem ──(U-04 optimize)──▶ AssignmentResult | InfeasibilityDiagnosis
        │                                      │
        │  BaselineEvaluator（同一 metrics_for）│
        ▼                                      ▼
   baseline_time/cost                     optimized_time/cost
        └──────────────┬───────────────────────┘
                       ▼
                ComparisonReport（削減指標, PII なし）
```

---

## 5. 永続化との関係

U-05 は永続化を持たない（U-03 が担う）。実績データ（`historical_records` 系）の取り込み・保存は U-03 のパターン（U03-H4）を再利用して U-05 Code Generation で実装する（U05-H2）。`ComparisonReport` 自体の永続化は本 PoC では任意（画面表示 + CSV エクスポートが主, FR-05.3）。

---

## 6. 後続への申し送り

business-logic-model.md 10 節（U05-H1〜H4）を参照。本ステージで新規の型定義申し送りは以下。

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U05-H5（新規）** | `ComparisonReport`, `ManualBaseline` を `comparison_report` に定義（frozen, PII なし）| U-05 Code Generation |
