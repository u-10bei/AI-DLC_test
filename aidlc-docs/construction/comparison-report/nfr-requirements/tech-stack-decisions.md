# 技術スタック決定 — U-05 `comparison-report`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 5 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A

---

## 1. U-01 からの継承

バックエンド全体の技術スタックは U-01 で確定済み。U-05 はこれを継承する。本文書は **U-05 固有の差分**のみを記す。

---

## 2. プロダクション依存: なし（Q1=A）

**U-05 は新たなプロダクション依存を追加しない。** これまでで最も軽量なユニット。

- 距離・費用: U-02 `distance_cost`
- 永続化・CSV: U-03 `data_management`（`serialize_csv` を再利用）
- 最適化: U-04 `optimization_engine`
- 集計（削減指標）: 標準ライブラリのみの純関数

CSV エクスポートは U-03 の `serialize_csv`（サニタイザ注入）を再利用する（新規 CSV ライブラリを追加しない）。

---

## 3. U-05 のリンタ契約（Q2=A, U05-H1）

| 契約 | 内容 |
|------|------|
| **R（U-05 のユニット境界）** | `comparison_report` は `shared_kernel`, `distance_cost`, `data_management`, `optimization_engine` を import 可。`security`, `api_orchestration`, `frontend` を import してはならない |
| **禁止する第三者** | `pydantic`, `fastapi`（U-07 の API 境界のもの）|

**Functional Design Q1=A の U-02 依存を反映**（`distance_cost` を許可リストに追加）。依存グラフは**非巡回**（U-04 も U-02 に依存済み、U-05 → U-02/U-04 は下向き）。

**Code Generation で `.importlinter` に追加し、非空虚性を確認する**（`import fastapi` の混入で BROKEN）。

---

## 4. 性能・非同期（Q3=A）

- 比較は **U-04 の求解 1 回**（最大 300 秒）+ ベースライン/最適化の集計（O(割当数)、線形）
- **U-05 固有の性能目標は設けない**（U-04 の NFR-P02 に従う）
- 求解を含むため、比較は **U-01 のジョブワーカープロセス**で実行（U-07 が配線）

---

## 5. 再現性（Q4=A）

- 最適化部分の再現性は **U-04 に従う**（シード・ワーカー数固定、保証範囲も U-04 準拠）
- 集計は決定的

---

## 6. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U05-H1** | `comparison_report` のリンタ契約（`distance_cost` 追加）を `.importlinter` に反映 | U-05 Code Generation |
| U05-H2 | `historical_records` 取り込み・保存（U-03 パターン再利用）| U-05 Code Generation |
| U05-H3 | `metrics_for`（U-02 + TravelParameters）で `TravelMetrics` を組み立てる | U-05 Code Generation |
| U05-H4 | 目的値比較は U-04 `scaling.normalised_objective` を使用 | U-05 Code Generation |
