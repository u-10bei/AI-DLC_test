# NFR Design Patterns — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Design（ユニット 4 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A

---

## 概要

OR-Tools CP-SAT の選定を **6 つの設計パターン**に落とす。核心は **DP-02（正規化目的の整数スケール）** と **DP-03（ortools の閉じ込め）**。

| # | パターン | 由来 |
|---|---------|------|
| DP-01 | CP-SAT ネイティブ制約でのモデル構築 | Q1 |
| DP-02 | 正規化目的の整数スケール + 整数 big-M | Q2（核心）|
| DP-03 | ソルバーアダプタ分離（ortools 閉じ込め）| Q3 |
| DP-04 | 段階的求解の時間配分 | Q4 |
| DP-05 | fail closed（BR-07 + 診断は戻り値）| Functional Design |
| DP-06 | 再現性 + ソルバーログ抑制 | Q5, NFR-Req Q4 |

---

## DP-01: CP-SAT ネイティブ制約でのモデル構築（Q1=A）

`MilpModel` を CP-SAT の `CpModel` に翻訳する（アダプタ内、DP-03）。

| 要素 | CP-SAT 表現 |
|------|------------|
| `x_ij` | `NewBoolVar(f"x_{staff_id}_{facility_id}")`（変数名は ID のみ、SECURITY-03）|
| C1 定員（等号）| 各施設 j: `Add(sum(x_ij for i) == required_headcount_j)` |
| C2 一意割当 | 各職員 i: `AddAtMostOne(x_ij for j)` |
| C3 資格 | 各 (j, r): `Add(sum(x_ij for i in 適格(r)) >= required_count_jr)` |
| C5 部署上限 | 各部署 d: `Add(sum(x_ij for i in d, j) <= dept_cap_d)` |
| 公平性 `T_max` | `NewIntVar` の `T_max`、各割当に `Add(T_max >= t_ij) .OnlyEnforceIf(x_ij)`（または線形化）|
| ピン留め | `Add(x_ij == 1)` |
| 目的 | `Minimize(整数化した線形和)`（DP-02）|

**根拠**: ネイティブヘルパ（`AddAtMostOne` 等）は CP-SAT の前処理・伝播が最も効く表現であり、40 万変数の求解性能に寄与する。

---

## DP-02: 正規化目的の整数スケール + 整数 big-M（Q2=A、核心）

**問題**: CP-SAT は整数目的係数のみ。Functional Design の目的は正規化により浮動小数点。

**パターン**: **固定精度スケール `S` で整数化する。**

```text
整数化した係数:
  coeff_time_ij = round(S · w1 · t_ij / N_t)
  coeff_cost_ij = round(S · w2 · c_ij / N_c)
  coeff_tmax    = round(S · w3 / N_t_single)
  # t_ij は既に整数（秒）。c_ij（円）・正規化除算はスケール後に整数化

目的:
  Minimize( Σ coeff_time_ij·x_ij + Σ coeff_cost_ij·x_ij + coeff_tmax·T_max
            [ + M_int · Σ s_jr ] )   # C3 降格時のみ

整数 big-M:
  M_int = S · U_obj + 1
    U_obj = 正規化後の目的が取りうる上界（各正規化項は設計上 [0,1] に収まる）
```

**INV-12 の保存**: `S` を十分大きく取り、**丸め後も「C3 違反 1 件減少の利得（M_int）> 他項の最大変動」が厳密に成り立つ**ようにする。`M_int = S·U_obj + 1` は、スケール済み目的の全変動幅より大きい。**丸め誤差は 1/S 未満**であり、`S = 10^6` なら実務上無視できる。この範囲を明記する。

**根拠**: CP-SAT の整数要件を満たしつつ、NFR Requirements Q2=A の正規化方針（担当者の重みが意味を持つ）と INV-12（H-10）を両立する。生値の整数線形和（却下 B）は正規化方針に反する。

---

## DP-03: ソルバーアダプタ分離（Q3=A）

**パターン**: **`ortools` を単一の `CpSatAdapter` に閉じ込める。**

```text
ortools 非依存（コア）:
  ModelBuilder        AssignmentProblem -> MilpModel（抽象）
  InfeasibilityDiagnoser  決定木（solve をポート経由で呼ぶ）
  ResultMapper        SolveOutcome -> AssignmentResult（BR-07）

ortools 依存（アダプタ 1 ファイル）:
  CpSatAdapter(SolverPort):
    solve(MilpModel, time_limit) -> SolveOutcome
    # ここでのみ import ortools。MilpModel を CpModel に翻訳（DP-01, DP-02）
```

**根拠**:
- **将来のソルバー差し替えはアダプタ 1 ファイルの交換**で済む（SolverPort 抽象）
- **コアが製品非依存**なので、`ModelBuilder`/`Diagnoser`/`ResultMapper` はソルバーなしでも単体テスト可能
- **リンタ契約**で `ortools` の import 箇所を実質アダプタに限定（NFR Requirements Q6）

---

## DP-04: 段階的求解の時間配分（Q4=A）

**パターン**: **各 solve に独立の時間予算。緩和・降格は実行不可能時のみ。**

```text
optimize:
  outcome = solve(full, budget=primary_limit)          # 通常はここで完結
  if infeasible:
      outcome_relaxed = solve(without_C3, budget=relaxed_limit)
      if feasible: outcome = solve(demoted_C3, budget=demoted_limit)
      else: diagnose(total-shortage / C2C4C5)
```

- 既定では `relaxed_limit = demoted_limit = primary_limit`
- **総所要時間の最悪ケース = 3 × primary_limit** を担当者に明記
- 緩和・降格の予算は短く設定可能（設定外部化）

**根拠**: 通常ケース（feasible）で主 solve の時間を削らない。300 秒 3 分割（却下 B）は通常ケースの解品質を落とす。

---

## DP-05: fail closed（Functional Design 継承）

- すべての結果は `AssignmentResult.__post_init__`（BR-07）を通す（DP: ResultMapper が最後に構築）
- **実行不可能は例外でなく戻り値**（`InfeasibilityDiagnosis`）。担当者が行動すべき状態であり、エラーではない
- ピン留め違反・モデル不整合は専用例外（`PinnedAssignmentInfeasibleError`, `ModelConstructionError`、PII なし）

---

## DP-06: 再現性 + ソルバーログ抑制（Q5=A, SECURITY-03）

| 項目 | 設定 |
|------|------|
| 乱数シード | `OptimizationParameters.random_seed` を CP-SAT に渡す |
| 探索ワーカー数 | 固定（再現性、単一ワーカー A-07 と整合）|
| 保証範囲 | `OPTIMAL`/完了結果は再現可能。タイムアウト時の最良解は保証外（明記）|
| **ソルバーログ** | **`log_search_progress = False`**（既定抑制）|
| 変数名 | 職員 ID・施設 ID のみ（氏名・居住小学校区を使わない、SECURITY-03）|

**根拠**: CP-SAT のログは探索の詳細を出力しうる。既定抑制 + ID のみの変数名で、個人情報の露出経路を塞ぐ。

---

## 該当しないパターン（Q5=A、N/A）

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| Resilience（リトライ、サーキットブレーカ）| **N/A** | fail closed。ソルバーは決定的な局所計算で、リトライすべき外部呼び出しがない |
| Scalability（スケールアウト）| **N/A** | 単一ワーカー（A-07）。CP-SAT の探索ワーカー数は再現性のため固定 |
| 追加ミドルウェア（キュー/キャッシュ/CB）| **N/A** | ジョブキューは U-07 所有。U-04 は求解ロジックのみ |

---

## 拡張ルール適合サマリ

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-15**（fail closed）| ✅ | DP-05。BR-07 + 診断は戻り値 |
| **SECURITY-03**（PII 非露出）| ✅ | DP-06。ログ抑制 + ID のみ変数名 |
| **SECURITY-10**（サプライチェーン）| ✅ | DP-03。ortools 閉じ込め + 固定 |
| **PBT-01..10** | ✅ 検証可能 | 全パターンが P-OPT01〜12 で検証可能。DP-02 は特に P-OPT12（INV-12）|
| Resiliency | スキップ | Enabled=No |

**ブロッキング所見: なし**

---

## 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U04-H9（新規）** | 整数スケール係数 `S` の既定値（例 10^6）と、正規化定数 `N_*`・時間予算・ワーカー数を設定外部化（NFR-M03）| U-04 Code Generation |
| U04-H6 | `CpSatAdapter`（`MilpModel`→CpModel、DP-01/02）を実装。ortools はこのファイルに限定 | U-04 Code Generation |
| U04-H8 | ortools 固定・監査・オフライン確認 | U-04 Code Generation |
