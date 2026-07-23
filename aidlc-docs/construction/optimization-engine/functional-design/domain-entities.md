# ドメインエンティティ / モデル型 — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 4 / 8）

---

## 1. U-04 は業務ドメイン型を新規定義しない

最適化の入出力ドメイン型は **U-01 が定義済み**である。U-04 が新規に定義するのは、**ソルバー内部モデル型**と**診断結果型**のみ。

| 型 | 定義元 | U-04 での用途 |
|----|-------|--------------|
| `AssignmentProblem` | U-01 | 入力 |
| `AssignmentResult` | U-01 | 出力（BR-07 通過）|
| `Assignment` | U-01 | 結果の要素 |
| `ConstraintViolation` / `ConstraintId` | U-01 | C3 降格の違反 |
| `ObjectiveWeights` / `OptimizationParameters` | U-01 | 目的の重み・時間制限 |
| `TravelMetrics` | U-01（U-02 が算出）| `travel_matrix` の値（定数 `t_ij, c_ij`）|
| `SolverStatus` | U-01 | OPTIMAL / TIME_LIMIT_REACHED / CANCELLED |

---

## 2. U-04 が新規定義する型（`src/optimization_engine/`）

### 2.1 ソルバー内部モデル（ソルバー製品非依存）

| 型 | 内容 |
|----|------|
| **`DecisionVariableIndex`** | `(StaffId, FacilityId)` の索引。`x_ij` の同定 |
| **`MilpModel`** | 変数集合・目的係数・制約（C1〜C5, 公平性補助, ピン留め固定）を抽象表現。製品非依存。SolverPort が消費 |
| **`SolveOutcome`** | ソルバーの生出力: `feasible: bool`, `assignments: tuple[Assignment,...]`, `objective_value: float`, `optimality_gap: float`, `status: SolverStatus`, `c3_violations: tuple[ConstraintViolation,...]` |

`MilpModel` は「決定変数・線形目的・線形制約」の抽象データ構造であり、特定の MILP ライブラリの API に縛られない。具象ソルバーアダプタ（NFR Requirements で製品選定, H-3）がこれを製品の API に翻訳する。

### 2.2 診断結果型

```text
InfeasibilityCause = Enum:
    TOTAL_SHORTAGE       # 従事可能職員の総数不足（C1 は緩和しない）
    C3_DEMOTED           # C3 のみが原因 → big-M 降格で解を得た
    HARD_CONSTRAINT      # C2 / C4 / C5 が原因（降格しない）

@frozen
InfeasibilityDiagnosis:
    cause: InfeasibilityCause
    shortage_count: int | None            # TOTAL_SHORTAGE のとき不足人数
    affected_facilities: tuple[FacilityId, ...]   # 不足施設
    blocking_constraints: tuple[ConstraintId, ...] # HARD_CONSTRAINT のとき該当制約
```

**`InfeasibilityDiagnosis` は個人情報を含まない**（施設 ID・制約 ID・件数のみ、SECURITY-03, BR-OPT17）。

### 2.3 ソルバーポート（抽象、P-OPT）

```text
SolverPort (Protocol):
    def solve(model: MilpModel, time_limit_seconds: int) -> SolveOutcome: ...
```

- U-04 が**定義**し、具象アダプタ（製品）は NFR Requirements/Code Generation で実装（H-3, U04-H1）
- 依存逆転: U-04 のサービスは `SolverPort` に依存し、製品には依存しない

### 2.4 履歴平準化フックの入力（Q6, 既定無効）

```text
@frozen
ServiceHistory:
    past_service_counts: dict[StaffId, int] = {}   # 過去従事回数（既定 空）
    weight: float = 0.0                            # w_hist（既定 0 = 無効）
```

`OptimizationService.optimize(problem, history=ServiceHistory())` の任意引数として受け取る。既定は無効。**U-05 連携は将来**（U04-H3）。

---

## 3. 新規例外（`src/optimization_engine/`、U-01 の DomainError 階層を継承）

| 例外 | 用途 |
|------|------|
| **`PinnedAssignmentInfeasibleError`** | ピン留めがハード制約に違反（FR-06.4, BR-OPT12）。文脈は制約 ID・施設/部署 ID のみ（PII なし）|
| **`ModelConstructionError`** | `travel_matrix` の欠落など、モデル構築時の不整合（SECURITY-05）|

`InfeasibilityDiagnosis` は**例外ではなく戻り値**（実行不可能は「エラー」ではなく「担当者が行動すべき状態」であるため）。

---

## 4. データ関連（入出力）

```text
AssignmentProblem (U-01)
  ├─ event: Event
  ├─ facilities: tuple[Facility]        # required_headcount, 資格要件
  ├─ available_staff: tuple[Staff]      # 従事可能者のみ（C4 構造保証）
  ├─ travel_matrix: {(StaffId,FacilityId): TravelMetrics}   # t_ij, c_ij 定数
  ├─ parameters: OptimizationParameters # weights, time_limit, dept_cap
  └─ pinned_assignments: tuple[Assignment]  # 再最適化のピン留め

        │  ModelBuilder
        ▼
     MilpModel  ──(SolverPort.solve)──▶  SolveOutcome
        │                                   │
        │  (infeasible)                     │ (feasible)
        ▼                                   ▼
InfeasibilityDiagnosis                ResultMapper
                                            ▼
                                   AssignmentResult (U-01, BR-07 通過)
```

---

## 5. 永続化との関係

U-04 は永続化を持たない（U-03 が担う）。`AssignmentResult` の保存は `assignment_results` / `constraint_violations` テーブル（**骨格は U-03 が作成済み**, U03-H1）に対して U-04 Code Generation で実装する（U04-H4）。マッパは U-03 のパターン（U03-H4）を再利用する。

---

## 6. 後続への申し送り

business-logic-model.md 11 節（U04-H1〜H5）を参照。本ステージで新規の型定義申し送りは以下。

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U04-H6（新規）** | `MilpModel` の抽象表現を具象ソルバー製品の API に翻訳するアダプタを実装 | U-04 Code Generation（製品は NFR Requirements で選定）|
| **U04-H7（新規）** | `PinnedAssignmentInfeasibleError`, `ModelConstructionError` を `optimization_engine` の例外モジュールに追加（U-01 の DomainError を継承、PII なし）| U-04 Code Generation |
