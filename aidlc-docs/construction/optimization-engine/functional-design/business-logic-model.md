# ビジネスロジックモデル — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 4 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A, Q7=A

---

## 1. 概要

U-04 は**一般化割当問題（GAP）を MILP として定式化し求解する**。入力は U-01 の `AssignmentProblem`、出力は `AssignmentResult`（BR-07 のファイアウォールを通過）。**ソルバー製品には非依存**（H-3 は NFR Requirements で選定）。

```text
AssignmentProblem
   │ (U-03 が構築、U-02 の TravelMetrics を含む)
   ▼
[ModelBuilder]  決定変数・目的関数・制約を組み立てる（純粋、製品非依存）
   ▼
[SolverPort]    抽象ポート。solve(model, time_limit) -> SolveOutcome
   ▼
[InfeasibilityDiagnoser]  実行不可能なら原因を診断（Q4 決定木）
   ▼
[ResultMapper]  SolveOutcome -> AssignmentResult（BR-07 通過）
   ▼
AssignmentResult
```

---

## 2. コンポーネント構成

| コンポーネント | 役割 | 純粋性 |
|--------------|------|:-----:|
| **ModelBuilder** | `AssignmentProblem` から MILP モデル（変数・目的・制約）を構築 | 純粋 |
| **SolverPort**（抽象）| `solve(model, time_limit_seconds) -> SolveOutcome`。製品は NFR Requirements で選定（H-3）| インターフェース |
| **InfeasibilityDiagnoser** | 実行不可能時の原因診断（決定木、Q4）| ソルバーを呼ぶ |
| **ResultMapper** | ソルバー出力 → `AssignmentResult`。BR-07 を通す | 純粋 |
| **OptimizationService** | 上記を統括。ピン留め事前検証、再最適化、時間制限 | オーケストレーション |

---

## 3. MILP 定式化

### 3.1 決定変数

- `x_ij ∈ {0, 1}`: 職員 `i`（`available_staff`）を施設 `j`（`facilities`）に割り当てるとき 1。最大 2,000 × 200 = 40 万
- `T_max ≥ 0`: 公平性（ミニマックス）の補助変数（Q3, U01-H5）
- （C3 降格時のみ）`s_jr ≥ 0`: 施設 `j` の資格要件 `r` の不足数（ソフト化された C3 の違反量）

### 3.2 目的関数（最小化、Q2 正規化 + Q3 ミニマックス）

```text
minimize  w1·(Σ_ij t_ij·x_ij / N_t)          # 総移動時間（正規化）
        + w2·(Σ_ij c_ij·x_ij / N_c)          # 総移動費用（正規化）
        + w3·(T_max / N_t_single)            # 公平性（最大移動時間、正規化）
        + w_hist·(Σ 履歴ペナルティ)           # 履歴平準化フック（既定 w_hist=0, Q6）
        [ + M·Σ_jr s_jr ]                     # C3 降格時のみ（Q5）
```

- `t_ij`, `c_ij` は `travel_matrix[(i,j)]`（U-02 が最適化**前**に計算した定数）。**目的は決定変数について線形**
- **正規化定数** `N_t, N_c, N_t_single` は設定として外部化（NFR-M03）。既定は代表スケール（例: `N_t = 割当対象人数 × 代表移動時間`）。各項を無次元化し、`w1,w2,w3` の相対値が意味を持つ（Q2）
- `w1,w2,w3` = `ObjectiveWeights`（担当者が画面から調整、FR-04.2）

### 3.3 ハード制約

| ID | 定式 | 由来 |
|----|------|------|
| **C1 定員充足** | `Σ_i x_ij == required_headcount_j`（**等号**, Q1）| FR-04.3 |
| **C2 一意割当** | `Σ_j x_ij ≤ 1`（各職員は高々 1 施設）| FR-04.3, INV-01 |
| **C3 資格充足** | 各施設 j・各要件 r: `Σ_{i∈適格(r)} x_ij ≥ required_count_jr` | FR-04.3 |
| **C4 従事可否** | `available_staff` のみを変数化（従事不可者は問題に含めない）| FR-04.1, FR-04.3 |
| **C5 部署継続性** | 各部署 d: `Σ_{i∈d, j} x_ij ≤ dept_cap_d` | FR-04.3 |
| **公平性補助** | 各割当職員 i, 施設 j: `T_max ≥ t_ij·x_ij` | Q3, U01-H5 |
| **ピン留め** | ピン留め `(i,j)`: `x_ij == 1`（固定）| FR-06.4, Q7 |

**C4 の実装**: `AssignmentProblem.available_staff` は「従事可能」と申告した職員のみ（FR-04.1）。従事不可者はそもそも変数に含まれないため、C4 は構造的に満たされる。

**C5 の `dept_cap_d`**: `Department.concurrent_assignment_cap`（None なら上限なし）。`OptimizationParameters.department_cap_limit` は既定上限。

### 3.4 目的関数値の報告（AssignmentResult）

`AssignmentResult.objective_value` には**正規化後の重み付き和**（非負・有限、INV-06）を格納。担当者向けの内訳（総移動時間・総費用・最大移動時間の生値）は別途 U-05/U-07 が提示。

---

## 4. 実行不可能（infeasible）診断の決定木（Q4, 申し送り H-9 解決）

```text
solve(全ハード制約, time_limit):
  outcome = SolverPort.solve(model_full)
  if outcome.feasible:
      return 通常解  # OPTIMAL または TIME_LIMIT_REACHED（最良解 + ギャップ）

  # --- 実行不可能。原因を診断 ---
  # (2) C3 を除いた緩和問題を解く
  outcome_relaxed = SolverPort.solve(model_without_C3)
  if outcome_relaxed.feasible:
      # (2a) 原因は C3 のみ → C3 を big-M ソフトに降格して再 solve
      outcome_demoted = SolverPort.solve(model_with_C3_softened)   # 3.2 の M·Σ s_jr
      return C3降格解  # violations に C3 のみ（BR-07 は C3 降格を許可）
  else:
      # (2b) 緩和問題も実行不可能
      if Σ available_staff < Σ required_headcount:
          # (3) 総数不足 → C1 は降格しない。追加申告を促す
          return InfeasibilityDiagnosis(cause=TOTAL_SHORTAGE, shortage=..., facilities=[...])
      else:
          # (4) C2 / C4 / C5 が原因 → 該当制約を明示、降格しない
          return InfeasibilityDiagnosis(cause=HARD_CONSTRAINT, constraints=[C2|C4|C5...])
```

**根拠（FR-04.5）**:
- **総数不足で C1 を緩和しない**: 定員を満たさない割当を出すのは誤り。担当者が追加申告を集めて再最適化（FR-06.6）
- **C3 のみ降格可**: 資格不足は「誰かを配置しないより、資格を満たさなくても配置する方がまし」な唯一のケース
- **C2/C4/C5 は降格不可**: C2 は物理的に不可能、C4 降格は休暇・健康配慮者の派遣、C5 降格は部署の業務停止を意味する

**診断は原因の**種別と該当施設/制約**のみを返す。個人情報を含めない**（SECURITY-03）。

---

## 5. C3 降格時の big-M（Q5, 申し送り H-10 / INV-12 解決）

C3 をソフト化するとき、目的に `M · Σ_jr s_jr` を加える（`s_jr` = 資格要件 r の不足数）。

**big-M の下限**: `M` を**正規化後の目的関数が取りうる理論上限より大きく**設定する。

```text
M = U_obj + 1
  U_obj = w1·1 + w2·1 + w3·1 + w_hist·(履歴項の上界)   # 各正規化項は [0,1] に収まる設計
        （正規化により各項の最大寄与が既知。安全側に上界を取る）
```

これにより、**C3 違反を 1 件でも減らせる解は、他のどんな目的悪化（移動時間・費用・公平性）よりも常に優先される**（INV-12）。すなわち「C3 を満たす解が存在するなら必ずそれが選ばれ、存在しない場合のみ最小限の違反を許す」（FR-04.5）。

**INV-12 の検証**（プロパティ）: C3 充足解が存在する問題では、降格 solve の結果は必ず C3 違反 0 になる。

---

## 6. ピン留め再最適化（Q7, FR-06.4）

```text
reoptimize(problem_with_pins):
  # (1) solve 前にピン留めの整合性を検証（solve しない）
  violation = validate_pins_against_hard_constraints(pins)   # C1..C5
  if violation:
      raise PinnedAssignmentInfeasibleError(該当制約)   # 担当者はピン解除後に再実行
  # (2) ピン留め x_ij を 1 に固定して solve
  fix x_ij = 1 for (i,j) in pins
  return solve(...)
```

- ピン留め検証は U-04 が行う（C1〜C5 に対する即時チェック、FR-06.3/6.4）
- 検証失敗時は**solve せずエラー**。エラーは該当制約と施設/職員 ID のみ（PII なし）

---

## 7. 時間制限と最適性ギャップ（Q7, FR-04.6, US-20）

- 時間制限（既定 300 秒, NFR-P02, `OptimizationParameters.time_limit_seconds`）
- 制限内に厳密最適解が出れば `SolverStatus.OPTIMAL`, `optimality_gap = 0`
- 出なければ**その時点の最良実行可能解**と最適性ギャップを返す（`TIME_LIMIT_REACHED`, `optimality_gap ∈ (0, 1]`）
- 実行可能解が 1 つも出ない場合は診断（第 4 節）へ

---

## 8. 履歴平準化フック（Q6, FR-04.4）

- 目的関数に履歴ペナルティ項の**構造だけ**用意し、**既定重み `w_hist = 0`**（無効）
- 過去従事回数の入力インターフェースを定義（`OptimizationParameters` への追加 or 別パラメータ。詳細は domain-entities.md）
- **U-04 は U-05 に依存しない**（依存は U-01/02/03）。履歴の供給は将来（U-05/運用）が担う。本 PoC は拡張点のみ提供

---

## 9. データフロー（fail closed）

```text
OptimizationService.optimize(problem):
  1. build model (ModelBuilder)          # 純粋
  2. (再最適化なら) validate pins         # 違反で即エラー
  3. solve (SolverPort)                   # 時間制限付き
  4. if infeasible: diagnose (Q4)         # 原因診断
  5. map to AssignmentResult (ResultMapper)
     # BR-07 が発火: C3 以外の違反、非有限/負の目的値、重複割当を拒否
  6. return AssignmentResult
```

**BR-07（U-01 の型レベルファイアウォール）が最後の砦**。ソルバーのバグで不正な解（C1/C2/C4/C5 違反、負の目的値、重複割当）が出れば、`AssignmentResult.__post_init__` が拒否する。**不正解が比較レポート（U-05）や担当者の画面に到達しない**（SECURITY-15）。

---

## 10. Testable Properties（PBT-01, ブロッキング）

| ID | プロパティ | 分類 |
|----|-----------|------|
| **P-OPT01（C1）** | 実行可能解では各施設 j に対し割当数 == required_headcount_j | Invariant |
| **P-OPT02（C2）** | 各職員は高々 1 施設（INV-01 は `AssignmentResult` の型で保証、二重防御）| Invariant |
| **P-OPT03（C3）** | C3 充足解が存在する問題では、返る解は資格要件を満たす | Invariant |
| **P-OPT04（C4）** | 従事不可の職員はいかなる施設にも割り当てられない | Invariant |
| **P-OPT05（C5）** | 各部署の同時割当数は上限以下 | Invariant |
| **P-OPT06（INV-06）** | 目的関数値は有限かつ非負 | Invariant |
| **P-OPT12（INV-12）** | **C3 充足解が存在するなら、降格 solve は C3 違反 0 の解を返す**（big-M の正しさ）| Metamorphic |
| **P-OPT07** | `optimality_gap ∈ [0, 1]` | Invariant |
| **P-OPT08** | ピン留めした割当は結果に必ず含まれる（固定の保存）| Invariant |
| **P-OPT09** | 診断結果・エラーに個人情報を含まない（ID のみ）| Security（SECURITY-03）|
| **P-OPT10（最適性）** | `OPTIMAL` 解の目的値 ≤ 任意の実行可能解の目的値（オラクル: 総当たり小規模）| Oracle |

**ステートフルテスト（PBT-06）の評価**: 再最適化ループ（solve → ピン留め → 再 solve）は状態遷移を持つが、各 solve は純粋な入出力であり、U-03 の `Event` 状態機械のような永続状態機械ではない。**PBT-06 は U-04 では任意**とし、再最適化は例示 + プロパティで検証する。

---

## 11. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U04-H1** | ソルバー製品の選定（厳密 MILP vs 発見的）。抽象 SolverPort の具象実装 | U-04 NFR Requirements（H-3）|
| **U04-H2** | 正規化定数 `N_t, N_c, N_t_single` の既定値と設定外部化（NFR-M03）| U-04 NFR Requirements / Code Generation |
| **U04-H3** | 履歴平準化の重み・過去従事回数の供給 | U-05 / 運用（将来）|
| **U04-H4** | `AssignmentResult` の永続化（`assignment_results`, `constraint_violations` 骨格は U-03 が作成済み、U03-H1）| U-04 Code Generation |
| **U04-H5** | 目的関数内訳（生値）の提示 | U-05 comparison-report / U-07 |
