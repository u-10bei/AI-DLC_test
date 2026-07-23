# NFR Design Plan — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Design（ユニット 4 / 8）
**参照**: U-04 nfr-requirements.md, tech-stack-decisions.md（OR-Tools CP-SAT）、Functional Design 全成果物

---

## 1. スコープ

確定済みの NFR（OR-Tools CP-SAT、厳密 + 時間制限、fail closed、再現性、非同期）を**設計パターンと論理コンポーネント**に落とす。

**技術的な核心**は次の 2 点である:
1. **CP-SAT は整数ソルバー**である（変数・目的係数は整数）。Functional Design の**正規化した浮動小数点目的**を、どう整数にスケールするか
2. `ortools` をどこに閉じ込め、U-04 のコアを製品非依存に保つか

---

## 2. Step 1: NFR 要件の分析

| カテゴリ | NFR Design での扱い |
|---------|--------------------|
| 性能 | モデル構築パターン（CP-SAT ネイティブ制約）、目的の整数スケール、段階的求解の時間配分 |
| 信頼性 | ソルバーアダプタの分離（fail closed）、BR-07 通過、再現性設定 |
| 保守性 | `ortools` の閉じ込め（SolverPort）、リンタ契約 |
| N/A | スケーラビリティ・可用性・追加ミドルウェア |

---

## 3. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: CP-SAT モデル構築パターン（性能）

`MilpModel` → CP-SAT の翻訳をどう組みますか？

A) **CP-SAT のネイティブ制約ヘルパを使う** — C2 一意割当は `AddAtMostOne`、C1 定員は `Add(sum(x_ij)==headcount)`、C3/C5 は線形和制約、公平性は `T_max >= t_ij` を各割当に線形で追加。0-1 変数は `NewBoolVar`。ソルバーが最も最適化しやすい表現 **（推奨）**

B) 汎用の線形制約のみで手組み — ヘルパを使わず全て `Add(linear)`。冗長でソルバーの前処理が効きにくい

X) Other

[Answer]:A

---

### Question 2: 正規化した目的関数の整数スケール（性能 / 正しさ、**核心**）

CP-SAT は**整数の目的係数**しか扱えません。Functional Design の目的は正規化により浮動小数点です。どう整数化しますか？

A) **固定精度でスケールして整数化** — 各正規化項に固定スケール係数 `S`（例: 10^6）を掛けて四捨五入し整数係数にする。`t_ij`（秒）は既に整数、`c_ij`（円）と正規化除算はスケール後に整数化。big-M も同じスケールで整数の上界として計算（`M_int = S·U_obj + 1`）。**スケール後も INV-12 が厳密に成り立つ**ように `S` を十分大きく取る。丸め誤差の範囲を明記 **（推奨）**

B) 目的を秒・円の生値の整数線形和にする（正規化しない）— 整数化は自明だが、NFR Requirements Q2=A の正規化方針（担当者の重みが意味を持つ）と矛盾する

X) Other（`[Answer]:` に記述）

[Answer]:A

---

### Question 3: `ortools` の閉じ込め（保守性 / 信頼性）

ソルバー製品への依存をどう局所化しますか？

A) **`ortools` を単一のアダプタモジュールに閉じ込める** — `SolverPort` の具象 `CpSatAdapter`（`solver_adapter.py`）**のみ**が `import ortools`。`ModelBuilder`（`AssignmentProblem`→`MilpModel`）、`InfeasibilityDiagnoser`、`ResultMapper` は **ortools 非依存**で、抽象 `MilpModel`/`SolveOutcome` 上で動く。将来のソルバー差し替えはアダプタ 1 ファイルの交換で済む **（推奨）**

B) U-04 全体で直接 `ortools` を使う — 分離の利点を失い、SolverPort 抽象が形骸化

X) Other

[Answer]:A

---

### Question 4: 段階的求解の時間配分（性能 / 信頼性、FR-04.5 決定木）

実行不可能診断は最大 3 回 solve します（全制約 / C3 緩和 / C3 降格）。300 秒の時間制限をどう配分しますか？

A) **主 solve に設定時間、緩和・降格 solve にも各自の予算（既定は同一上限）、総ワーストケースを明記** — 通常は主 solve のみで完結。実行不可能時のみ追加 solve が走る。各 solve に時間制限を渡し、緩和・降格 solve は必要時のみ。**総所要時間の上限（最悪 3×制限）を担当者に明記**し、必要なら緩和・降格の予算を短く設定可能にする **（推奨、単純かつ明示的）**

B) 300 秒を 3 分割して各 solve に配分 — 主 solve の時間が削られ、通常ケース（feasible）の解品質が落ちる

X) Other

[Answer]:A

---

### Question 5: 該当しないパターンの確認 + ソルバーログの PII（Resilience/Scalability/Logical Components + SECURITY-03）

以下をまとめて確認します。

A) **N/A 確定 + ソルバーログ抑制** — (1) Resilience: リトライ/サーキットブレーカなし（fail closed）。(2) Scalability: 単一ワーカー（A-07）、CP-SAT の探索ワーカー数は固定（再現性、Q4=A of NFR Req）。(3) 追加ミドルウェアなし。U-04 の論理コンポーネントは ModelBuilder / SolverPort + CpSatAdapter / InfeasibilityDiagnoser / ResultMapper / OptimizationService。(4) **CP-SAT のソルバーログは既定で抑制**（`log_search_progress=False`）。変数名に個人情報を使わない（職員 ID のみ、SECURITY-03）**（推奨）**

B) 一部該当する（`[Answer]:` に記述）

X) Other

[Answer]:A

---

## 4. 実行チェックリスト（回答分析後）

### 4.1 nfr-design-patterns.md
- [x] DP: CP-SAT モデル構築（Q1 ネイティブ制約ヘルパ、変数・目的・C1〜C5・T_max の翻訳）
- [x] DP: 目的の整数スケール（Q2、big-M の整数上界、INV-12 の保存、丸め誤差範囲）
- [x] DP: ソルバーアダプタ分離（Q3、ortools 閉じ込め、SolverPort）
- [x] DP: 段階的求解の時間配分（Q4、ワーストケース明記）
- [x] DP: fail closed（BR-07 通過、実行不可能診断は戻り値）
- [x] DP: 再現性（シード + ワーカー数固定、保証範囲）、ソルバーログ抑制（Q5, SECURITY-03）

### 4.2 logical-components.md
- [x] LC: ModelBuilder（純粋, ortools 非依存）
- [x] LC: SolverPort（抽象）+ CpSatAdapter（ortools 閉じ込め）
- [x] LC: InfeasibilityDiagnoser（決定木）
- [x] LC: ResultMapper（SolveOutcome→AssignmentResult, BR-07）
- [x] LC: OptimizationService（統括、ピン留め検証、時間制限）
- [x] N/A（Resilience/Scalability/キュー・キャッシュ・サーキットブレーカ）を根拠付きで記録（Q5）

### 4.3 拡張適合
- [x] SECURITY-15（fail closed）、SECURITY-03（PII 非露出 + ソルバーログ抑制）、SECURITY-10（ortools 固定）
- [x] PBT: パターンが P-OPT01〜12 で検証可能
- [x] N/A ルール記録、レジリエンシー無効記録

### 4.4 完了処理
- [x] 2 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
