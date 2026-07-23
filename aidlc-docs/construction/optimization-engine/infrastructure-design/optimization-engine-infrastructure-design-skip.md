# Infrastructure Design — U-04 `optimization-engine` — SKIP 提案

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Infrastructure Design（ユニット 4 / 8、CONDITIONAL）
**判定**: **SKIP を提案**（U-04 に固有のインフラ面がない）

---

## 1. 要旨

U-04 は**求解ロジック（MILP + CP-SAT）のみ**を持つ論理モジュールで、独自のインフラサービスを追加しない。実行環境・計算リソース・永続化・非同期実行はすべて既存の決定に委ねられる。U-02 の Infrastructure Design skip と同じ判断構造である。

---

## 2. 7 カテゴリの評価

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| **Deployment Environment** | 確定済み（U-01）| 単一インターネット側サーバー（A-07）。U-04 は独立デプロイされないモノリスの論理モジュール |
| **Compute Infrastructure** | 確定済み（U-01）| **求解（最大 300 秒）は U-01 のジョブワーカープロセスで実行**（NFR Requirements Q5）。U-04 は新しい計算リソースを持たない。CP-SAT の探索ワーカー数は再現性のため固定（プロセス内スレッド、A-07 の単一サーバー内）|
| **Storage Infrastructure** | 確定済み（U-03/U-01）| `AssignmentResult` の永続化は **U-03 の骨格テーブル**（`assignment_results`/`constraint_violations`）を再利用（U04-H4）。新規ストレージなし |
| **Messaging Infrastructure** | 確定済み（U-01）| DB ベースジョブキュー（U-07 所有）。U-04 は求解ロジックを提供、投入・配線は U-07 |
| **Networking Infrastructure** | N/A | U-04 は HTTP を持たない。**オフライン動作**（外部 API 不要, FR-03.6）|
| **Monitoring Infrastructure** | N/A | U-04 固有の監視インフラなし。ソルバーログは抑制（DP-06）|
| **Shared Infrastructure** | 確定済み（U-01）| `shared-infrastructure.md` を参照するのみ |

**7 カテゴリすべてが「確定済み」または「N/A」**。

---

## 3. 依存パッケージ（`ortools`）はインフラ設計対象ではない

`ortools` はプロダクション依存（NFR Requirements で確定・固定）であり、**アプリケーション依存**であってインフラサービス（別プロセス・別ホスト・ミドルウェア）ではない。Code Generation でインストール・固定・pip-audit/SBOM・オフライン確認を行う（U04-H8）。インフラ設計の対象ではない。

---

## 4. NFR Design での N/A 確認との整合

NFR Design（Q5=A）で、メッセージキュー・外部キャッシュ・サーキットブレーカ・スケールアウト層を N/A と確定済み。インフラ面でも整合する。

---

## 5. 結論

**Infrastructure Design を SKIP することを提案する。**

- 7 カテゴリすべてが確定済み（U-01/U-03）または N/A
- U-04 は求解ロジックのみ。新しいインフラサービスを追加しない
- 求解実行は U-01 のワーカー、結果永続化は U-03、依存 `ortools` はアプリ依存
- ブロッキング所見なし

skip 承認後、U-04 の **Code Generation** に進む。
