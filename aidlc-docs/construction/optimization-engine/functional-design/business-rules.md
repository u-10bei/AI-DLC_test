# ビジネスルール — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 4 / 8）

---

## 1. モデル定式化のルール

### BR-OPT01: C1 定員充足は等号（Q1）
各施設 j に対し `Σ_i x_ij == required_headcount_j`。過剰派遣も不足派遣も許さない。総数が不足する場合は実行不可能とし、FR-04.5 の総数不足パスへ（**C1 は緩和しない**）。

### BR-OPT02: C2 一意割当
各職員 i に対し `Σ_j x_ij ≤ 1`。加えて結果側で INV-01（`AssignmentResult` の型）が二重に保証する。

### BR-OPT03: C3 資格充足
各施設 j・各資格要件 r に対し `Σ_{i∈適格(r)} x_ij ≥ required_count_jr`。適格判定は職員の `job_type` / `position` / `qualifications` と要件の照合による。

### BR-OPT04: C4 従事可否は構造的に保証
`available_staff` は「従事可能」と申告した職員のみ（FR-04.1）。従事不可者は変数化しない。**従事不可者を割り当てる解は構造的に生成されえない**。

### BR-OPT05: C5 部署継続性
各部署 d に対し `Σ_{i∈d,j} x_ij ≤ dept_cap_d`。`dept_cap_d` は `Department.concurrent_assignment_cap`（None は上限なし）または `OptimizationParameters.department_cap_limit`。

### BR-OPT06: 公平性はミニマックス（Q3, U01-H5）
`T_max ≥ t_ij·x_ij` を全 (i,j) に課し、目的に `w3·T_max/N_t_single` を加える。**分散（二次）を使わない**——MILP の線形性を壊すため。

### BR-OPT07: 目的関数の正規化（Q2）
3 項は正規化してから重み付き和をとる。正規化定数は設定として外部化（NFR-M03）。生の秒・円を混ぜた重み付き和にしない。

---

## 2. 実行不可能診断のルール（FR-04.5, Q4）

### BR-OPT08: 段階的求解の決定木
第 4 節（business-logic-model.md）の順序で診断する。**C3 を除いた緩和問題が実行可能なら「C3 のみが原因」**と判定する。

### BR-OPT09: 総数不足で C1 を緩和しない
`Σ available < Σ required` のとき、定員充足を緩和した解を出さない。不足人数と不足施設を明示し、担当者に追加申告を促す（FR-06.6）。

### BR-OPT10: C3 のみ降格可能
C3 が唯一の原因のときのみ、C3 を big-M ソフト制約に降格する。**C2/C4/C5 は決して降格しない**（物理的不可能 / 休暇者派遣 / 部署業務停止を意味するため）。降格結果の `violations` には C3 のみが含まれる（BR-07 と整合）。

### BR-OPT11: big-M の下限（Q5, INV-12）
C3 降格の各違反ペナルティ `M` は、正規化後の目的関数が取りうる理論上限より大きく設定する（`M = U_obj + 1`）。これにより **C3 違反を 1 件減らせる解が常に優先**される。恣意的な巨大定数（1e9 等）を使わない。

---

## 3. 再最適化と時間制限のルール

### BR-OPT12: ピン留めの事前検証（FR-06.4, Q7）
再最適化では、**solve 前に**ピン留め割当がハード制約 C1〜C5 に違反しないか検証する。違反があれば **solve せず** `PinnedAssignmentInfeasibleError` を送出する。担当者はピン留めを解除してから再実行する。

### BR-OPT13: ピン留めは固定変数
検証を通過したピン留め `(i,j)` は `x_ij == 1` に固定して solve する。**ピン留めした割当は必ず結果に含まれる**（P-OPT08）。

### BR-OPT14: 時間制限内の最良解（FR-04.6, US-20）
時間制限（既定 300 秒）内に厳密最適解が出なければ、その時点の**最良実行可能解**と**最適性ギャップ**を返す（`TIME_LIMIT_REACHED`, `optimality_gap ∈ (0,1]`）。実行可能解が皆無なら診断へ。

---

## 4. 結果の健全性（fail closed）

### BR-OPT15: BR-07 ファイアウォールの通過
すべての結果は `AssignmentResult.__post_init__`（BR-07, U-01）を通す。**C3 以外の違反・非有限/負の目的値・重複割当（INV-01 違反）を持つ結果は拒否**される。ソルバーのバグが下流（U-05/U-07）へ伝播しない（SECURITY-15）。

### BR-OPT16: 履歴平準化フックの既定無効（Q6）
履歴ペナルティ項は構造のみ用意し、既定重み `w_hist = 0`。U-04 は U-05 に依存しない。

---

## 5. エラー処理と個人情報

### BR-OPT17: 診断・エラーに個人情報を含めない（SECURITY-03）
実行不可能診断、ピン留め検証エラー、ログには、職員の**氏名・居住小学校区を含めない**。職員 ID・施設 ID・部署 ID・制約 ID・行/件数のみ。

**例**:
- ✅ `Infeasible: total shortage 12 at facilities [F03, F07]`
- ✅ `Pinned assignment violates C5 for department D02`
- ❌ `鈴木太郎を第三小学校区の避難所に固定できません`

### BR-OPT18: fail closed（SECURITY-15）
実行不可能・ピン留め違反・不正解のいずれも、**推測で解を作らず**、原因を明示して停止する。

---

## 6. 拡張ルール適合サマリ

### 6.1 PBT Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| **PBT-01 プロパティ特定（ブロッキング）** | **適合** | business-logic-model.md 10 節に P-OPT01〜P-OPT12 を分類付きで列挙 |
| PBT-02 ラウンドトリップ | 該当薄 | 最適化は変換ではない。オラクル（P-OPT10）とメタモルフィック（P-OPT12）が中心 |
| PBT-03 不変条件 | 適合（先行）| C1〜C5、INV-06、ギャップ範囲 |
| PBT-06 ステートフル | **任意と判定** | 各 solve は純粋。再最適化は例示 + プロパティで検証 |
| PBT-07 生成器 | 方針 | U-01 の `gen_assignment_problem` を再利用・拡張 |
| PBT-04, 05, 08, 09, 10 | Code Generation / 継承 | |

**ブロッキング所見: なし**

### 6.2 Security Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-03 ログに PII を含めない** | **適合** | BR-OPT17。診断・エラーは ID のみ |
| **SECURITY-15 fail closed** | **適合** | BR-OPT15/18。BR-07 が不正解を拒否。実行不可能は推測で解を作らない |
| **SECURITY-05 入力検証** | **適合** | `AssignmentProblem` は U-01 の型で検証済み。ModelBuilder は不整合（travel_matrix 欠落等）を検出 |
| SECURITY-01, 02, 04, 06〜14 | **N/A** | 永続化は U-03、ネットワーク・認証は U-06/U-07 |

**ブロッキング所見: なし**

### 6.3 Resiliency Extension
**スキップ**（Enabled = No）。

---

## 7. 解決した申し送り

| ID | 状態 |
|----|------|
| H-9（C3 のみ実行不可能の判定に緩和部分問題を解く）| ✅ BR-OPT08（決定木）|
| H-10（big-M 下限が INV-12 を満たす）| ✅ BR-OPT11（`M = U_obj + 1`）|
| U01-H5（公平性は minimax で線形）| ✅ BR-OPT06 |
| H-2（13 不変条件のプロパティ化）| ✅ P-OPT01〜12 |

**H-3（ソルバー製品選定）は NFR Requirements で決定する。**
