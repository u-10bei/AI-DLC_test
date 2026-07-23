# NFR Design Patterns — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Design（ユニット 5 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A

---

## 概要

U-05 の NFR 設計は **5 つのパターン**。核心は **DP-01（`metrics_for` 単一純関数）** で、削減効果が割当ルールの差のみに帰属することを構造的に保証する。

| # | パターン | 由来 |
|---|---------|------|
| DP-01 | `metrics_for` 単一純関数（同一基準評価）| Q1（核心）|
| DP-02 | 距離・費用・同一校区規則の再利用 | Q2 |
| DP-03 | 目的値優越性チェック（U-04 目的の再利用）| Q3 |
| DP-04 | fail closed（診断パススルー）| FD |
| DP-05 | 削減指標の算出（0 除算ガード）+ PII 非露出 | Q4 |

---

## DP-01: `metrics_for` 単一純関数（Q1=A、核心、FR-05.1.4）

**問題**: 差が割当ルールのみに帰属することを、どう保証するか。

**パターン**: **`metrics_for(staff, facility) -> TravelMetrics` を単一の純関数として生成し、以下すべてに使う。**

```text
metrics_for = make_metrics_for(current_master, travel_parameters)   # クロージャ

(1) 再現問題の travel_matrix = { (s,f): metrics_for(s,f) ... }   # ReplayBuilder
(2) ベースライン実績の評価  = Σ metrics_for(actual)             # BaselineEvaluator
(3) 最適化結果の評価       = Σ metrics_for(optimised)          # BaselineEvaluator
```

**根拠**: ベースラインと最適化を**物理的に同一の関数**で評価するため、両者の差は移動メトリクスの計算差ではなく**割当の差のみ**に由来する（FR-05.1.4）。純関数なので決定的・テスト容易。

---

## DP-02: 距離・費用・同一校区規則の再利用（Q2=A, FR-03.4/3.7）

**パターン**: `metrics_for` は U-02 と `TravelParameters` の既存規則を再利用する。

```text
metrics_for(staff, facility):
  if staff.residence_district == facility.district:
      return TravelMetrics(distance_km=0, time_seconds=same_district_fixed, cost_yen=0)  # FR-03.7
  great_circle = U-02.haversine(residence_point, facility_point)
  actual_distance = great_circle * detour_factor
  time = actual_distance / average_speed * 3600
  cost = cost_model.cost_for(actual_distance)     # 距離帯モデル（U-02）
  return TravelMetrics(actual_distance, time, cost)
```

**根拠**: U-05 独自の距離ロジックを作らず、FR-03 の規則（U-02 + `TravelParameters`）を一元的に再利用する。時間は秒精度（NFR-U01-R04）。

---

## DP-03: 目的値優越性チェック（Q3=A, P-CMP03, U05-H4）

**パターン**: ベースラインと最適化の目的値比較には、**U-04 の `scaling.normalised_objective` を再利用**する。

```text
baseline_obj  = U-04.normalised_objective(replay_problem, actual_assignments)
optimised_obj = U-04.normalised_objective(replay_problem, result.assignments)
# ベースラインが再現問題で実行可能なら optimised_obj <= baseline_obj（P-CMP03）
```

**根拠**: U-05 独自の目的関数を作ると U-04 と乖離しうる。同一関数を使うことで、優越性チェックが U-04 の最適化と厳密に整合する。

---

## DP-04: fail closed（診断パススルー、FD 継承）

- 再現問題が実行不可能なら、U-04 の `optimize` が返す `InfeasibilityDiagnosis` を**そのまま提示**（レポートを捏造しない、BR-CMP09, SECURITY-15）
- 実績インポートの検証エラーは U-03 のパターン（`CsvImportError`、行番号付き、PII なし）を再利用

---

## DP-05: 削減指標の算出 + PII 非露出（Q4=A）

| 項目 | 決定 |
|------|------|
| 削減量 | `baseline - optimised`（負可）|
| 削減率 | `reduction / baseline`（`baseline == 0` なら 0、0 除算ガード）|
| レポート内容 | 集計指標 + イベント ID + 注記。個人情報なし（SECURITY-03, BR-CMP11）|
| CSV 明細 | 含める場合は職員 ID・施設 ID のみ。サニタイザ注入（U03-H5）|

---

## 該当しないパターン（Q4=A、N/A）

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| Resilience（リトライ、CB）| **N/A** | fail closed。実行不可能は診断を提示 |
| Scalability | **N/A** | 単一ワーカー（A-07）|
| 追加ミドルウェア（キュー/キャッシュ/CB）| **N/A** | 求解は U-04（ワーカー）、永続化は U-03 |

---

## 拡張ルール適合サマリ

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-15**（fail closed）| ✅ | DP-04。診断パススルー |
| **SECURITY-03**（PII 非露出）| ✅ | DP-05。集計 + ID のみ |
| **SECURITY-05**（入力検証）| ✅ | 実績インポートの検証（U-03 パターン）|
| **PBT-01..10** | ✅ 検証可能 | 全パターンが P-CMP01〜05 で検証可能。DP-01/03 は特に P-CMP03/04 |
| Resiliency | スキップ | Enabled=No |

**ブロッキング所見: なし**

---

## 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| U05-H3 | `metrics_for` の実装（DP-01/02）| U-05 Code Generation |
| U05-H4 | 目的値優越性は U-04 `normalised_objective` を使用（DP-03）| U-05 Code Generation |
