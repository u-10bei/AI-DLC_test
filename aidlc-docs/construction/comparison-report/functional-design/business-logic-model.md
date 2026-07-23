# ビジネスロジックモデル — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 5 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A

---

## 1. 概要

U-05 は**過去イベントの実績（現行の職場単位割当）を再現**し、同一条件で最適化を実行して比較する。削減効果（総移動時間・総移動費用）は**割当ルールの差のみに帰属**する（FR-05.1.4）。

```text
HistoricalRecord (実績割当 + 当時の申告)  +  現在の職員/施設マスタ (U-03)
        │
        ▼  ReplayBuilder（Q2, U-02 で移動行列を構築）
   AssignmentProblem（再現問題）
        │                              │
        ▼ U-04 OptimizationService     ▼ BaselineEvaluator（同一行列, Q4）
   最適化 AssignmentResult          実績の総移動時間・費用
        │                              │
        └──────────┬───────────────────┘
                   ▼  ComparisonService
             ComparisonReport（削減時間/費用/率, Q3）
                   │
                   ▼ ReportExporter（U-03 serialize_csv, Q6）
                 画面表示 + CSV
```

---

## 2. コンポーネント構成

| コンポーネント | 役割 |
|--------------|------|
| **ReplayBuilder** | `HistoricalRecord` + 現在マスタ → 再現 `AssignmentProblem`（Q2）。移動行列を U-02 で構築（Q1）|
| **BaselineEvaluator** | 実績割当の総移動時間・費用を**同一の移動行列**で算出（Q4）|
| **ComparisonService** | 再現 → U-04 で最適化 → ベースライン評価 → `ComparisonReport` を統括 |
| **ReportExporter** | `ComparisonReport` を CSV 化（U-03 `serialize_csv`、サニタイザ注入, Q6）|
| **HistoricalRepository** | 実績データの取り込み・保存（U-03 `historical_records` 骨格, U03-H2）|

---

## 3. 再現問題の構築（ReplayBuilder, Q2, FR-05.1.2〜1.5）

```text
build_replay(record: HistoricalRecord, master, parameters) -> AssignmentProblem:
  # (1) 施設と必要人数（FR-05.1.2）
  facilities = {}
  for a in record.actual_assignments:
      facilities[a.facility_id] のカウント += 1
  # 各施設は現在マスタの Facility を用い、required_headcount を実績人数で置換
  #   qualification_requirements は現在マスタの値を用いる（C3）

  # (2) 従事可能職員集合（FR-05.1.3）
  available = [ 現在マスタの Staff |
                staff_id が record.availability_declarations で is_available=True ]

  # (3) 移動行列（Q1, U-02。現在マスタの居住・所在で算出, FR-05.1.5/A-09）
  travel_matrix = { (s.id, f.id): metrics_for(s, f) for s in available for f in facilities }
    # metrics_for: U-02 で大円距離 → 迂回×速度で時間、距離帯で費用（同一校区は距離0/費用0/固定時間, FR-03.4/3.7）

  # (4) パラメータ（重み等）は担当者指定（既定は現行設定）
  return AssignmentProblem(event, facilities, available, travel_matrix, parameters)
```

**現在マスタ値の使用（A-09）**: 当時の居住・部署・資格は取得できないため、ベースラインと最適化の**双方を現在値で評価**する。絶対値は当時と一致しないが、**差（削減効果）は妥当**。

**A-10**: 過去の従事可否申告が提供されない場合、従事可能集合を「実際に割り当てられた職員」に縮小せざるをえず、削減効果は控えめに出る（明記）。

---

## 4. ベースライン評価（BaselineEvaluator, Q4, FR-05.1.4）

```text
evaluate_baseline(record.actual_assignments, metrics_for) -> (total_time, total_cost):
  total_time = Σ metrics_for(a.staff_id, a.facility_id).time_seconds
  total_cost = Σ metrics_for(a.staff_id, a.facility_id).cost_yen
```

- **最適化と同一の `metrics_for`（同一移動行列）** で評価する。差は割当ルールの差のみに帰属（FR-05.1.4）
- 実績で割り当てられた職員は、原則として従事可能集合に含まれる。含まれない場合も `metrics_for` を同一関数で計算し一貫性を保つ

---

## 5. 削減指標（ComparisonReport, Q3, FR-05.2）

```text
time_reduction      = baseline_time - optimized_time      # 負にもなりうる
time_reduction_rate = time_reduction / baseline_time      # baseline_time == 0 なら 0
cost_reduction      = baseline_cost - optimized_cost
cost_reduction_rate = cost_reduction / baseline_cost      # baseline_cost == 0 なら 0
```

- **最適化は重み付き目的を最小化**するため、重み次第で総移動時間・総費用の**片方が増える**ことがある（SC-01「両方削減」は経験的目標）。削減量は負を許す
- optimized_time/cost は最適化結果の割当を**同一 `metrics_for`** で評価して算出（ベースラインと同一基準）

---

## 6. 統括フロー（ComparisonService）と fail closed

```text
compare(record, master, parameters) -> ComparisonReport | InfeasibilityDiagnosis:
  problem = ReplayBuilder.build_replay(record, master, parameters)
  result  = U-04.OptimizationService.optimize(problem)
  if result is InfeasibilityDiagnosis:
      return result   # 再現問題が実行不可能 → 診断をそのまま提示（fail closed, 捏造しない）
  baseline_time, baseline_cost = BaselineEvaluator.evaluate(record.actual_assignments, metrics_for)
  optimized_time, optimized_cost = evaluate(result.assignments, metrics_for)
  return ComparisonReport(...)
```

**fail closed（SECURITY-15）**: 再現問題が実行不可能なら、レポートを捏造せず U-04 の `InfeasibilityDiagnosis` を提示する。

---

## 7. 手動ベースライン（Q5, FR-05.1.6）

過去実績のない新規イベントは、担当者が**実績相当（割当 + 従事可能申告）を直接入力**して `HistoricalRecord` を構築し、同一フローで比較する。

---

## 8. CSV エクスポート（ReportExporter, Q6, FR-05.3）

- U-03 の `serialize_csv`（サニタイザ注入）を再利用
- 集計指標（削減時間・費用・率）は**個人情報なし**
- 割当明細を含める場合は**職員 ID・施設 ID のみ**（氏名・居住小学校区を含めない, SECURITY-03）
- 数式インジェクション無害化のサニタイザは U-07 が注入（U03-H5）

---

## 9. Testable Properties（PBT-01, ブロッキング）

| ID | プロパティ | 分類 |
|----|-----------|------|
| **P-CMP01** | 削減量の一貫性: `time_reduction == baseline_time - optimized_time`（費用も同様）| Invariant |
| **P-CMP02** | 削減率の定義: `rate == reduction / baseline`（baseline==0 なら rate==0）| Invariant |
| **P-CMP03（メタモルフィック）** | **ベースライン実績が再現問題で実行可能なら、最適化の目的値 ≤ ベースラインの目的値**（同一正規化目的で評価）| Metamorphic |
| **P-CMP04** | 同一基準評価: optimized/baseline の time/cost は同一 `metrics_for` で算出される | Invariant |
| **P-CMP05** | レポート・エクスポートに個人情報を含まない（ID・集計のみ）| Security（SECURITY-03）|

**ステートフルテスト（PBT-06）**: 該当なし（比較は純粋な入出力）。

---

## 10. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U05-H1** | U-05 の依存に `distance_cost`（U-02）を加える。リンタ契約に反映（非巡回維持）| U-05 NFR Requirements / Code Generation |
| **U05-H2** | `historical_records` 系テーブル（U-03 骨格, U03-H2）の取り込み・保存ロジックを実装 | U-05 Code Generation |
| **U05-H3** | `metrics_for`（U-02 の距離 + `TravelParameters` の迂回・速度・距離帯費用・同一校区固定）で `TravelMetrics` を組み立てる純関数を実装 | U-05 Code Generation |
| **U05-H4** | ベースライン/最適化の目的値比較には U-04 の正規化目的（`scaling.normalised_objective`）を用いる | U-05 Code Generation |
