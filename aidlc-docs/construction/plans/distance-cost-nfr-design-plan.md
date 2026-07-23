# NFR Design Plan — U-02 `distance-cost`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - NFR Design（ユニット 2 / 8）
**参照**: U-02 の Functional Design と NFR Requirements の全成果物

---

## 1. 必須カテゴリの適用性評価

`construction/nfr-design.md` は 5 カテゴリすべての評価を要求する。

| カテゴリ | 適用 | 根拠 |
|---------|:----:|------|
| **Resilience Patterns** | **N/A** | U-02 は外部呼び出しを一切持たない（R-3 が構造的に保証）。リトライすべき失敗がない。レジリエンシー拡張も無効 |
| **Scalability Patterns** | **N/A** | 純粋関数。稼働プロセスを持たない |
| **Performance Patterns** | **限定的に該当** | NFR-U02-P02（キャッシュによる再計算回避）。ただしキャッシュの**永続化**は U-03 の責務であり、U-02 が設計するのは「何をキャッシュするか」＝大円距離のみ（Functional Design で確定済み）。下記 Question 1 で再確認 |
| **Security Patterns** | **限定的に該当** | U-02 は個人情報を扱わない。`UnknownSchoolDistrictError` の文脈に小学校区 ID のみを含める（既に Functional Design で確定） |
| **Logical Components** | **N/A（インフラ）** | U-02 はキュー・キャッシュ実装・サーキットブレーカを持たない。距離キャッシュの**実装**は U-03。U-02 は `P-03` の**定義**のみ |

**5 カテゴリのうち 3 つが N/A、2 つが限定的該当。いずれも先行ステージでほぼ確定している。**

---

## 2. 本ステージで確定する設計パターン

U-02 の設計判断は、先行ステージでほぼ尽くされている。本ステージで新たに詰めるのは以下 2 点のみ。

### 論点 1: 距離帯の探索構造

`travel_cost_yen(distance, cost_model)` は、距離が属する帯を探す。帯数は少数（既定 3、担当者が増やしても 10 程度）。

- 線形探索（下から順に `distance < upper_bound_km` を探す）
- 二分探索

帯数が 10 程度なら線形探索で十分だが、明示しておく。→ **Question 1**

### 論点 2: 2 つ目のリンタ契約の具体形

NFR-U02-M02 は「`distance_cost` は標準ライブラリのみ」の契約を Code Generation で追加すると定めた。その具体形（禁止する import の列挙方法）を確定する。→ **Question 2**

---

## 3. 明確化質問

以下の質問に、`[Answer]:` タグの後に選択肢の記号を記入してご回答ください。すべて回答し終えたら「完了」とお知らせください。

---

### Question 1: 距離帯の探索構造（Performance Patterns）

`travel_cost_yen` が距離帯を探す方法を確定してください。帯数は既定 3、担当者が増やしても 10 程度です。

A) **線形探索** — 下から順に `distance < upper_bound_km` を満たす最初の帯を返す。帯数が少数のため十分高速。実装が単純で、境界条件（排他的上限）が読みやすい **（推奨）**

B) **二分探索** — 帯数が多い場合に有利だが、10 程度では線形探索と体感差がなく、実装が複雑になる

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 2: 2 つ目のリンタ契約の形（Security Patterns / 保守性）

U-02 が標準ライブラリのみに依存することを、`.importlinter` でどう強制しますか？

A) **`forbidden` 契約で第三者パッケージ（`numpy`, `sqlalchemy`, `pydantic`, `fastapi`, `hypothesis`）を明示的に禁止する** — U-01 の「標準ライブラリのみ」契約と同じ方式。既知の第三者依存を列挙する。将来新しいパッケージが追加された場合は契約に追記する **（推奨。U-01 と一貫）**

B) **`独立性` 契約で許可リスト方式にする** — `shared_kernel` と標準ライブラリのみを許可する。より厳密だが、import-linter の許可リスト表現は複雑

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 3: 必須カテゴリの N/A 判定の確認

セクション 1 で、Resilience / Scalability / Performance（大部分）/ Logical Components（インフラ）を **N/A** と判定しました。

| カテゴリ | N/A の根拠 |
|---------|-----------|
| Resilience | U-02 は外部呼び出しを持たない |
| Scalability | 純粋関数、稼働プロセスなし |
| Performance（インフラ面） | キャッシュの永続化は U-03。U-02 は「大円距離を保存する」ことのみ設計済み |
| Logical Components（インフラ） | U-02 はキュー・キャッシュ実装を持たない |

A) **判定は正しい** **（推奨）**

B) **判定に誤りがある** — 内容を `[Answer]:` の後に記述してください

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

## 4. 実行チェックリスト（回答の分析後に実行）

### 4.1 NFR 設計パターン

- [x] Q1 の回答に基づき、距離帯の探索構造を定義する
- [x] Q2 の回答に基づき、2 つ目のリンタ契約の形を定義する
- [x] fail closed の設計（`CostModel` の単調性検証、`UnknownSchoolDistrictError`）を再掲する
- [x] 純粋関数性の 2 層強制（R-3 + 標準ライブラリのみ契約）を定義する
- [x] Q3 に基づき、N/A カテゴリを根拠付きで記録する
- [x] `aidlc-docs/construction/distance-cost/nfr-design/nfr-design-patterns.md` を作成する

### 4.2 論理コンポーネント

- [x] U-02 が持つ論理コンポーネント（純粋関数群、`P-03` の定義、費用モデルの探索）を列挙する
- [x] U-02 がインフラコンポーネントを持たないことと根拠を記録する
- [x] U-01 の生成器に加えて U-02 が必要とする生成器（`gen_cost_model`, `gen_non_monotonic_cost_model`）を記録する
- [x] `aidlc-docs/construction/distance-cost/nfr-design/logical-components.md` を作成する

### 4.3 拡張ルールの適合確認

- [x] **SECURITY-11**: 純粋関数性の多層防御（R-3 + 標準ライブラリ契約）を確認する
- [x] **SECURITY-15**: fail closed を確認する
- [x] **PBT-08**: シード方針は U-01 の `conftest.py` を継承することを確認する
- [x] 本ステージに適用対象のない SECURITY / PBT ルールを N/A として記録する
- [x] レジリエンシー拡張は無効のため適合確認を行わない旨を記録する

### 4.4 完了処理

- [x] `aidlc-docs/aidlc-state.md` の進捗を更新する
- [x] 拡張ルール適合サマリを作成する
- [ ] 標準の 2 択完了メッセージを提示し、承認を待つ
