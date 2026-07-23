# Logical Components — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Design（ユニット 4 / 8）
**回答**: Q5=A

---

## 概要

U-04 の論理コンポーネントは **5 つ**。`ortools` は **CpSatAdapter 1 箇所のみ**に閉じ込める（DP-03）。追加ミドルウェア（キュー・キャッシュ・サーキットブレーカ）はなし。

```text
        AssignmentProblem (U-01)
              │
              ▼
     ┌──────────────────┐
     │ LC-01 ModelBuilder│  純粋・ortools 非依存
     │ Problem -> MilpModel
     └────────┬─────────┘
              │ MilpModel（抽象）
              ▼
     ┌────────────────────────────────┐
     │ LC-05 OptimizationService       │  統括・ピン留め検証・時間制限
     │   ├─ LC-03 InfeasibilityDiagnoser（決定木）
     │   └─ solve via ───────────────┐ │
     └───────────────────────────────┼─┘
                                     │ SolverPort（抽象）
                                     ▼
                          ┌───────────────────────┐
                          │ LC-02 CpSatAdapter     │  ★ ortools はここだけ
                          │ MilpModel -> CpModel   │
                          │ solve -> SolveOutcome  │
                          └───────────┬───────────┘
                                     │ SolveOutcome（抽象）
                                     ▼
                          ┌───────────────────────┐
                          │ LC-04 ResultMapper     │  純粋・ortools 非依存
                          │ -> AssignmentResult    │  BR-07 通過
                          └───────────────────────┘
```

（テキスト代替: ModelBuilder が Problem を抽象 MilpModel に変換。OptimizationService が統括し、SolverPort 経由で CpSatAdapter に solve を委譲。CpSatAdapter のみが ortools を使う。SolveOutcome を ResultMapper が AssignmentResult に変換し BR-07 を通す。実行不可能時は InfeasibilityDiagnoser が決定木で診断。）

---

## LC-01: ModelBuilder（純粋・ortools 非依存）

| 項目 | 内容 |
|------|------|
| 責務 | `AssignmentProblem` → 抽象 `MilpModel`（変数索引、目的係数、制約 C1〜C5、T_max、ピン留め）|
| 目的の整数化 | 正規化 + 固定精度スケール `S`（DP-02）。整数係数と整数 big-M を算出 |
| 純粋性 | ortools 非依存。単体テスト可能 |
| エラー | `travel_matrix` 欠落等で `ModelConstructionError` |

---

## LC-02: SolverPort + CpSatAdapter（★ ortools 閉じ込め）

| 項目 | 内容 |
|------|------|
| SolverPort | 抽象 `Protocol`: `solve(MilpModel, time_limit_seconds) -> SolveOutcome` |
| CpSatAdapter | 具象実装。**唯一 `import ortools` するモジュール**（DP-03、リンタ契約）|
| 翻訳 | `MilpModel` → `cp_model.CpModel`（DP-01: NewBoolVar, AddAtMostOne, 線形制約）|
| 設定 | 時間制限、乱数シード、探索ワーカー数固定、`log_search_progress=False`（DP-06）|
| 出力 | `SolveOutcome`（feasible, assignments, objective_value, optimality_gap, status, c3_violations）|

---

## LC-03: InfeasibilityDiagnoser（決定木）

| 項目 | 内容 |
|------|------|
| 責務 | 実行不可能時の原因診断（Functional Design Q4 の決定木）|
| フロー | 全制約 → C3 緩和 solve → (feasible なら C3 降格 solve) / (総数不足チェック) / (C2C4C5) |
| 時間配分 | 各 solve に予算（DP-04）|
| 出力 | `InfeasibilityDiagnosis`（原因種別 + 施設/制約 ID、PII なし）|
| 依存 | SolverPort 経由で solve。ortools 非依存 |

---

## LC-04: ResultMapper（純粋・ortools 非依存）

| 項目 | 内容 |
|------|------|
| 責務 | `SolveOutcome` → `AssignmentResult`（U-01）|
| BR-07 | 構築時に `AssignmentResult.__post_init__` が発火。不正解（C3 以外の違反・非有限/負の目的値・重複割当）を拒否（fail closed, DP-05）|
| 純粋性 | ortools 非依存 |

---

## LC-05: OptimizationService（統括）

| 項目 | 内容 |
|------|------|
| 責務 | ModelBuilder → (ピン留め検証) → SolverPort.solve → (Diagnoser) → ResultMapper を統括 |
| ピン留め | solve 前にハード制約違反を検証、違反で `PinnedAssignmentInfeasibleError`（solve しない、DP-05）|
| 時間制限 | `OptimizationParameters.time_limit_seconds`（既定 300, NFR-P02）|
| 実行場所 | U-01 のジョブワーカープロセス（NFR Requirements Q5）。U-07 が配線 |
| 履歴フック | `ServiceHistory`（既定重み 0、Q6 of FD）|

---

## 該当しない論理コンポーネント（Q5=A、N/A）

| コンポーネント | 判定 | 根拠 |
|--------------|:----:|------|
| メッセージキュー | **N/A** | ジョブキューは DB ベースで U-07 所有 |
| 外部キャッシュ | **N/A** | 距離キャッシュは U-03。求解に外部キャッシュ不要 |
| サーキットブレーカ / リトライ層 | **N/A** | fail closed。決定的な局所計算 |
| スケールアウト層 | **N/A** | 単一ワーカー（A-07）、探索ワーカー数固定 |

---

## 依存とポート

- U-04 は `shared_kernel`, `distance_cost`, `data_management` を import 可（リンタ契約, NFR Req Q6）
- `ortools` は **LC-02 CpSatAdapter のみ**が import
- SolverPort は依存逆転: コア（LC-01/03/04/05）は抽象に依存し、製品（ortools）に依存しない
- `AssignmentResult` の永続化は `data_management`（U-03 の骨格テーブル `assignment_results`/`constraint_violations`、U03-H1/U04-H4）を再利用

---

## 拡張ルール適合サマリ（論理コンポーネント観点）

| ルール | 判定 | 根拠 |
|--------|------|------|
| SECURITY-03（PII 非露出）| ✅ | LC-02 ログ抑制 + ID のみ変数名。診断は ID のみ |
| SECURITY-10（サプライチェーン）| ✅ | ortools は LC-02 に限定・固定 |
| SECURITY-15（fail closed）| ✅ | LC-04 の BR-07、LC-05 のピン留め検証 |
| Scalability / Resilience | N/A | Q5=A |

**ブロッキング所見: なし**
