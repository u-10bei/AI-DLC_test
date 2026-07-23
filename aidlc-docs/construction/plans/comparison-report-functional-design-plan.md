# Functional Design Plan — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 5 / 8）
**参照**: `requirements.md` v1.4（FR-05, A-09, A-10, SC-01）、`shared_kernel/problem.py`（HistoricalRecord, AssignmentProblem, AssignmentResult）、U-04（OptimizationService）、U-03（historical_records 骨格）、US-26〜US-28

---

## 1. ユニットコンテキスト

| 項目 | 内容 |
|------|------|
| ユニット | U-05 `comparison-report`（`src/comparison_report/`）|
| 依存（宣言）| U-01 shared_kernel, U-03 data_management, U-04 optimization_engine |
| ストーリー | US-26〜US-28（実績インポート、比較レポート、CSV エクスポート）|
| 中核 | **過去イベントの再現による現行方式との比較**。削減効果（総移動時間・総移動費用）を提示 |

**FR-05.1 の再現方法論**:
- ベースライン = 過去イベントの**実際の割当実績**（`HistoricalRecord`）
- 各施設の必要人数 = 実績で割り当てられていた人数（FR-05.1.2）
- 最適化対象職員 = 当該イベントに「従事可能」と申告した集合（実際の割当より広い、FR-05.1.3）
- **同一条件で最適化を実行**し実績と比較 → 削減効果は**割当ルールの差のみに帰属**（FR-05.1.4）
- 居住小学校区・部署・資格は**現在の職員マスタの値**を使用（当時値は取得不可、FR-05.1.5, A-09）

---

## 2. Step 1: 設計対象の分析

| 領域 | 設計内容 |
|------|---------|
| 実績インポート | `HistoricalRecord`（実績割当 + 当時の申告）を CSV から取り込み、historical_records に保存（U03-H2）|
| 再現問題の構築 | `HistoricalRecord` + 現在マスタ → `AssignmentProblem`（施設・必要人数・従事可能集合・移動行列）|
| 最適化 | U-04 `OptimizationService.optimize` で再現問題を解く |
| ベースライン評価 | 実績割当の総移動時間・総費用を**同一の移動行列**で算出（FR-05.1.4）|
| 比較指標 | 削減時間・削減率、削減額・削減率（FR-05.2）|
| 出力 | 画面表示 + CSV エクスポート（FR-05.3）|

---

## 3. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: 移動時間・費用行列の構築と U-02 依存（依存関係）

再現問題の `travel_matrix` と、ベースライン実績の移動時間・費用の算出には、距離・費用計算（U-02 `distance_cost`）が必要です。U-05 の宣言依存は U-01/U-03/U-04 ですが、U-02 の関数を使います。

A) **U-05 の依存に U-02 `distance_cost` を加える** — 現在マスタ（居住小学校区・施設所在）から U-02 で大円距離 → 迂回・速度・距離帯費用で `TravelMetrics` を算出し、`travel_matrix` を構築。ベースラインと最適化の**双方を同一行列で評価**（FR-05.1.4/1.5）。依存グラフは非巡回のまま（U-02 は下層）**（推奨）**

B) U-04 / U-03 に移動行列構築のヘルパを設け U-05 はそれを呼ぶ — U-02 直接依存を避けるが、行列構築の責務が曖昧になり、U-04（求解専用）や U-03（永続化専用）の責務を越える

X) Other（`[Answer]:` に記述）

[Answer]:A

---

### Question 2: 再現問題の構築方法（FR-05.1.2〜1.5）

`HistoricalRecord` から `AssignmentProblem` をどう導出しますか？

A) **要件の方法論どおり導出** — (1) 施設ごとの必要人数 = 実績割当人数（FR-05.1.2）。(2) 従事可能職員集合 = 当時「従事可能」と申告した職員（FR-05.1.3、`HistoricalRecord.availability_declarations`）。(3) 居住・部署・資格は**現在の職員マスタ**（FR-05.1.5, A-09）。(4) 目的関数の重み・パラメータは担当者指定（既定は現行設定）**（推奨、確認）**

B) 別方法（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 3: 削減指標の定義（FR-05.2）

削減時間・費用と削減率をどう定義しますか？

A) **削減量 = ベースライン − 最適化、削減率 = 削減量 / ベースライン** — 総移動時間・総移動費用の各々。**ベースラインが 0 の場合、削減率は 0（または N/A）**として明示。削減量は負にもなりうる（重み次第で片方の指標が増えることがある、SC-01 は経験的目標）**（推奨）**

B) 別定義（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 4: ベースライン評価の一貫性（FR-05.1.4、削減の妥当性）

実績割当の移動時間・費用を、どの移動行列で評価しますか？

A) **最適化と同一の移動行列（現在マスタ由来）で評価** — ベースラインも最適化結果も**同じ `travel_matrix`** で総移動時間・費用を算出する。これにより差は**割当ルールの差のみ**に帰属する（FR-05.1.4）。絶対値は当時と一致しないが、差は妥当（A-09）**（推奨、確認）**

B) 別方法（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 5: 実績のないイベントの手動ベースライン（FR-05.1.6）

過去実績が存在しない新規イベントの扱いは？

A) **担当者が手動でベースライン割当を入力できる経路を用意** — `HistoricalRecord` 相当（実績割当 + 従事可能申告）を担当者が直接指定し、以降は同一フローで比較する **（推奨）**

B) 手動ベースラインは本 PoC では非対応（実績があるイベントのみ比較）

X) Other

[Answer]:A

---

### Question 6: CSV エクスポートと個人情報（FR-05.3, SECURITY-03, MU-02）

比較レポートの CSV エクスポート方針を確定してください。

A) **U-03 の `serialize_csv`（サニタイザ注入）を再利用** — 集計指標（削減時間・費用・率）は個人情報なし。割当明細を含める場合は**職員 ID のみ**（氏名・居住小学校区を含めない、SECURITY-03）。数式インジェクション無害化のサニタイザは U-07 が注入（U03-H5）**（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

## 4. 実行チェックリスト（回答分析後）

### 4.1 business-logic-model.md
- [x] 実績インポート → `HistoricalRecord` → 再現 `AssignmentProblem` 構築（Q2）
- [x] 移動行列の構築（Q1 の U-02 依存, Q4 の一貫評価）
- [x] 最適化（U-04）→ ベースライン評価 → `ComparisonReport`
- [x] 削減指標の算出（Q3）、手動ベースライン（Q5）、CSV エクスポート（Q6）
- [x] コンポーネント構成（ReplayBuilder / BaselineEvaluator / ComparisonService / ReportExporter）

### 4.2 business-rules.md
- [x] BR-CMP01.. （必要人数導出、従事可能集合、現在マスタ使用、同一行列評価、削減率の 0 除算、PII 非露出）
- [x] FR-05.1.4 の妥当性（差は割当ルールに帰属）、A-09/A-10 の明記

### 4.3 domain-entities.md
- [x] `ComparisonReport`（削減指標、PII なし）を新規定義。`HistoricalRecord` は U-01 定義を使用
- [x] 手動ベースライン入力の型

### 4.4 PBT / Security 適合
- [x] Testable Properties: 削減指標の一貫性（reduction = base − opt, rate 定義）、**ベースラインが再現問題で実行可能なら最適化の目的値 ≤ ベースライン目的値**（メタモルフィック）、レポートに PII なし
- [x] SECURITY-03（PII 非露出）、SECURITY-15（fail closed）

### 4.5 完了処理
- [x] 3 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
