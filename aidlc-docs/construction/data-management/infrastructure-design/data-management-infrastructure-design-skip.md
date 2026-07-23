# Infrastructure Design — U-03 `data-management` — SKIP 提案

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Infrastructure Design（ユニット 3 / 8、CONDITIONAL）
**判定**: **SKIP を提案**（新規のインフラ面がない）

---

## 1. 提案の要旨

U-03 は**実永続化を持つ最初のユニット**だが、それが使うインフラ（暗号化ボリューム上の DB、単一サーバー、DB ベースジョブキュー）は **U-01 の Infrastructure Design スロットで既に確定済み**（`construction/shared-infrastructure.md`、U-01..U-07 を拘束）。U-03 は**新しいインフラサービスを一切追加しない**。したがって本ステージは skip を提案する。

これは U-02 の Infrastructure Design skip（`distance-cost-infrastructure-design-skip.md`）と同じ判断構造である。

---

## 2. 7 カテゴリの評価（すべて評価済み、根拠付き）

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| **Deployment Environment** | 確定済み（U-01）| 単一のインターネット側サーバー（A-07）。既存の公開基盤が TLS 終端・アクセスログ・WAF を提供（H-6 discharged）。U-03 は新しいデプロイ先を持たない |
| **Compute Infrastructure** | 確定済み（U-01）| API プロセス（FastAPI+uvicorn）+ 単一ジョブワーカー。U-03 のサービス（LC-04）はこの API/ワーカープロセス内で動く。新しい計算リソースを持たない |
| **Storage Infrastructure** | 確定済み（U-01）| `app.db`（SQLite、PoC）/ PostgreSQL（本番）を暗号化ボリューム上に配置（SECURITY-01、U01-H17 discharged）。**U-03 の 10 テーブルと距離キャッシュは同一の `app.db` 内**。新しいストレージサービス（別 DB、オブジェクトストア等）を追加しない |
| **Messaging Infrastructure** | 確定済み（U-01）| DB ベースのジョブキュー（Redis なし）。**キューは U-07 が所有**。U-03 はキューインフラを持たない（NFR Design Q6=A） |
| **Networking Infrastructure** | 確定済み（U-01）| ログイン制限（NFR-S10.1）+ 庁内 egress IP 許可リスト（NFR-S10.2）、QG-3 満たす。U-03 はネットワーク面を持たない（HTTP は U-07） |
| **Monitoring Infrastructure** | N/A | U-03 固有の監視インフラはない。監査ログ（OS レベル append-only ファイル）は U-01 で確定済み。可観測性は運用フェーズ/横断課題 |
| **Shared Infrastructure** | 確定済み（U-01）| `shared-infrastructure.md` を U-01 で authored。U-03 はこれを**参照するだけ**で再導出しない |

**7 カテゴリすべてが「確定済み（U-01）」または「N/A」**。U-03 に固有のインフラ設計対象は存在しない。

---

## 3. U-03 がインフラに触れる唯一の点（既に解決済み）

U-03 は**個人情報（職員の氏名・居住小学校区）を保存する最初のユニット**である。これに伴うインフラ要件は保存時暗号化（SECURITY-01）だが:

- 暗号化ボリュームのポリシーは **U-01 の shared-infrastructure.md で確定済み**（U01-H17 discharged）
- U-03 の DB（`app.db`）はそのボリューム上に置かれる
- **U-03 側で新たに設計・決定することはない**。既存ポリシーへの配置に従うのみ

したがって、この点も skip を妨げない。

---

## 4. NFR Design で確認済みの「該当なし」

NFR Design（Q6=A）で以下を既に N/A と確定しており、インフラ面でも整合する:

- メッセージキュー（Redis 等）: 導入しない（DB ベース、U-07 所有）
- 外部キャッシュ層（Redis/Memcached）: 導入しない（距離キャッシュは DB テーブル）
- サーキットブレーカ / ロードバランサ / 複数インスタンス: 導入しない（単一サーバー A-07）

---

## 5. Deployment Architecture について

U-03 は**独立してデプロイされない**（モノリスの論理モジュール、`src/data_management/`）。デプロイ単位はモノリス全体であり、U-01 の `shared-infrastructure.md` と（将来の）Build and Test / Operations が扱う。U-03 固有の deployment-architecture.md は不要。

---

## 6. 結論

**Infrastructure Design を SKIP することを提案する。**

- 7 カテゴリすべてが確定済み（U-01）または N/A
- U-03 は新しいインフラサービスを追加しない
- 個人情報の保存時暗号化は既存ポリシー（暗号化ボリューム）への配置で満たされ、新規設計はない
- ブロッキング所見なし

skip 承認後、U-03 の **Code Generation** に進む。
