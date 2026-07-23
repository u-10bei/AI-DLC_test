# Logical Components — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Design（ユニット 5 / 8）
**回答**: Q4=A

---

## 概要

U-05 の論理コンポーネントは **5 つ**。すべて `src/comparison_report/` 配下の Python モジュールで、外部ミドルウェアを追加しない。核心は `metrics_for`（DP-01）を ReplayBuilder と BaselineEvaluator が共有すること。

```text
        HistoricalRecord + 現在マスタ(U-03)
              │
              ▼  make_metrics_for(master, params)  →  metrics_for（共有純関数, DP-01）
     ┌─────────────────────┐
     │ LC-01 ReplayBuilder  │  travel_matrix = metrics_for(...)
     └──────────┬──────────┘
                │ AssignmentProblem
                ▼
     ┌───────────────────────────────┐
     │ LC-03 ComparisonService        │  統括
     │   ├─ U-04.optimize ───────────┼──▶ AssignmentResult | InfeasibilityDiagnosis
     │   └─ LC-02 BaselineEvaluator ──┼──▶ base/opt の time/cost（同一 metrics_for）
     └──────────┬────────────────────┘
                │ ComparisonReport（PII なし）
                ▼
     ┌───────────────────────┐        ┌──────────────────────┐
     │ LC-04 ReportExporter   │        │ LC-05 HistoricalRepo  │
     │ U-03 serialize_csv     │        │ historical_records    │
     └───────────────────────┘        └──────────────────────┘
```

---

## LC-01: ReplayBuilder

| 項目 | 内容 |
|------|------|
| 責務 | `HistoricalRecord` + 現在マスタ → 再現 `AssignmentProblem`（FR-05.1.2〜1.5）|
| 移動行列 | `metrics_for`（DP-01/02、U-02 使用）|
| 純粋性 | 純関数（現在マスタとパラメータを入力）|

---

## LC-02: BaselineEvaluator

| 項目 | 内容 |
|------|------|
| 責務 | 実績・最適化結果の総移動時間・費用を **同一 `metrics_for`** で算出（DP-01, FR-05.1.4）|
| 目的値 | U-04 `normalised_objective` で優越性チェック（DP-03）|
| 純粋性 | 純関数 |

---

## LC-03: ComparisonService（統括）

| 項目 | 内容 |
|------|------|
| 責務 | ReplayBuilder → U-04 optimize → BaselineEvaluator → `ComparisonReport` |
| fail closed | 実行不可能は U-04 `InfeasibilityDiagnosis` をパススルー（DP-04）|
| 削減指標 | 0 除算ガード（DP-05）|
| 実行場所 | 求解を含むため U-01 のジョブワーカー（U-07 が配線）|

---

## LC-04: ReportExporter

| 項目 | 内容 |
|------|------|
| 責務 | `ComparisonReport` → CSV |
| 実装 | U-03 `serialize_csv`（サニタイザ注入、U03-H5）を再利用 |
| PII | 集計 + ID のみ（SECURITY-03, DP-05）|

---

## LC-05: HistoricalRepository

| 項目 | 内容 |
|------|------|
| 責務 | 実績データ（`HistoricalRecord`）の取り込み・保存 |
| 実装 | U-03 の `historical_records` 骨格テーブル（U03-H2）+ マッパパターン（U03-H4）|

---

## 該当しない論理コンポーネント（Q4=A、N/A）

| コンポーネント | 判定 | 根拠 |
|--------------|:----:|------|
| メッセージキュー | **N/A** | 求解ジョブは U-07/U-01 のキュー |
| 外部キャッシュ | **N/A** | 距離キャッシュは U-03 |
| サーキットブレーカ / リトライ | **N/A** | fail closed |
| スケールアウト層 | **N/A** | 単一ワーカー（A-07）|

---

## 依存とポート

- U-05 は `shared_kernel`, `distance_cost`, `data_management`, `optimization_engine` を import 可（リンタ契約, U05-H1）
- **プロダクション依存ゼロ**。既存ユニットの組み合わせ
- 依存グラフは非巡回（U-05 は上位、下向きにのみ依存）

---

## 拡張ルール適合サマリ（論理コンポーネント観点）

| ルール | 判定 | 根拠 |
|--------|------|------|
| SECURITY-03（PII 非露出）| ✅ | LC-03/04 は集計 + ID のみ |
| SECURITY-15（fail closed）| ✅ | LC-03 の診断パススルー |
| Scalability / Resilience | N/A | Q4=A |

**ブロッキング所見: なし**
