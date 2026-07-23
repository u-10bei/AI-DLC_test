# NFR Design Plan — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Design（ユニット 5 / 8）
**参照**: U-05 nfr-requirements.md, tech-stack-decisions.md, Functional Design 全成果物

---

## 1. スコープ

確定済みの NFR（依存追加なし、fail closed、再現性は U-04 継承）を**設計パターンと論理コンポーネント**に落とす。核心は「ベースラインと最適化を**同一基準**で評価する」ことの実装形。

---

## 2. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: `metrics_for` の単一純関数化（信頼性 / 正しさ、FR-05.1.4）

再現問題の移動行列と、ベースライン評価の移動時間・費用を、どう一貫させますか？

A) **`metrics_for` を単一の純関数（クロージャ）とし、ReplayBuilder と BaselineEvaluator の両方が同一のものを使う** — 現在マスタと `TravelParameters` を束ねた `metrics_for(staff, facility) -> TravelMetrics` を 1 つ生成し、(1) 再現問題の `travel_matrix` の構築、(2) ベースライン実績の評価、(3) 最適化結果の評価、すべてに同一関数を使う。**差が割当ルールのみに帰属することを構造的に保証**（FR-05.1.4）**（推奨）**

B) それぞれ別に算出する — 実装がずれると差の妥当性が崩れる

X) Other

[Answer]:A

---

### Question 2: `metrics_for` の同一小学校区の扱い（FR-03.4/3.7）

`metrics_for` の距離・費用・時間の算出規則を確定してください。

A) **U-02 の距離 + `TravelParameters` の規則をそのまま適用** — 大円距離（U-02）× 迂回係数 → 平均速度で時間、距離帯モデルで費用。**同一小学校区は距離 0・費用 0、移動時間は固定値**（FR-03.4/3.7）。既存の FR-03 規則を再利用し、U-05 独自の距離ロジックを作らない **（推奨）**

B) 別規則（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 3: 目的値の優越性チェック（信頼性, P-CMP03）

「実行可能なベースラインなら最適化目的値 ≤ ベースライン目的値」を、どう評価しますか？

A) **U-04 の正規化目的（`scaling.normalised_objective`）を再利用** — ベースライン実績と最適化結果の双方を、U-04 と同一の正規化目的関数で評価して比較する（P-CMP03）。U-05 独自の目的関数を作らない（U-04 と乖離しない）**（推奨、U05-H4）**

B) 別方法（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 4: 該当しないパターンの確認 + 論理コンポーネント + PII（Resilience/Scalability/Logical Components + SECURITY-03）

以下をまとめて確認します。

A) **N/A 確定 + PII 非露出** — (1) Resilience: リトライ/CB なし（fail closed、実行不可能は U-04 診断を提示）。(2) Scalability: 単一ワーカー（A-07）。(3) 追加ミドルウェアなし。U-05 の論理コンポーネントは ReplayBuilder / BaselineEvaluator / ComparisonService / ReportExporter / HistoricalRepository。(4) レポート・エクスポートは集計 + ID のみ（氏名・居住小学校区を含めない、SECURITY-03）**（推奨）**

B) 一部該当する（`[Answer]:` に記述）

X) Other

[Answer]:A

---

## 3. 実行チェックリスト（回答分析後）

### 3.1 nfr-design-patterns.md
- [x] DP: `metrics_for` 単一純関数（Q1、同一基準評価）
- [x] DP: 距離・費用・同一校区規則（Q2、U-02 + TravelParameters 再利用）
- [x] DP: 目的値優越性チェック（Q3、U-04 正規化目的の再利用）
- [x] DP: fail closed（実行不可能は U-04 診断のパススルー）
- [x] DP: 削減指標の算出（0 除算ガード）、PII 非露出（Q4）

### 3.2 logical-components.md
- [x] LC: ReplayBuilder / BaselineEvaluator / ComparisonService / ReportExporter / HistoricalRepository
- [x] N/A（Resilience/Scalability/キュー・キャッシュ・CB）を根拠付きで記録（Q4）

### 3.3 拡張適合
- [x] SECURITY-15（fail closed）、SECURITY-03（PII 非露出）
- [x] PBT: パターンが P-CMP01〜05 で検証可能
- [x] N/A ルール記録、レジリエンシー無効記録

### 3.4 完了処理
- [x] 2 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
