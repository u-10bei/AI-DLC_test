# Operations — 説明書

**フェーズ**: OPERATIONS（ペルソナ別説明書）
**作成日**: 2026-07-24
**方針**: **要件定義に忠実に**、各ペルソナの責務ごとに「何を・どの画面／手段で・どう実現するか」を記述する。要件 ID（US-xx）と実装状況を併記し、本 PoC で未提供の機能は申し送りとして明示する。

---

## ペルソナ別説明書

| ペルソナ | 説明書 | 区分 | 主な担当（エピック） |
|---------|--------|------|-------------------|
| P-01 割当担当者 | [manual-P-01-coordinator.md](manual-P-01-coordinator.md) | 直接利用者（主要） | E2 イベント / E4 申告 / E5 パラメータ / E6 最適化 / E7 確認調整 / E8 比較 |
| P-02 システム管理者 | [manual-P-02-admin.md](manual-P-02-admin.md) | 直接利用者 | E1 認証・認可・監査 / E3 マスタ / E5 パラメータ |
| P-03 従事職員 | [manual-P-03-staff.md](manual-P-03-staff.md) | 間接的受益者（非操作） | E4 申告の当事者（代理登録） |

---

## デプロイ

| 文書 | 内容 |
|------|------|
| [deployment-plan.md](deployment-plan.md) | デプロイ計画（決定事項・前提変更 DEP-H1・作業項目・受け入れ確認） |
| [deployment-runbook.md](deployment-runbook.md) | Azure VM への手順書（リソース作成→配備→受け入れ確認→運用） |

デプロイ用資材は [`deploy/`](../../deploy/)（systemd unit、Caddyfile、環境変数サンプル、cron スクリプト）。

---

## 関連ドキュメント

- **要件・ストーリー**: `aidlc-docs/inception/requirements/`、`aidlc-docs/inception/user-stories/stories.md`、`personas.md`
- **ビルド・起動・テスト**: `aidlc-docs/construction/build-and-test/`
- **画面別説明書**: [screens/](screens/) — 各画面のボタン・入力欄単位の操作手順（実装済み UI に忠実）。
  - [00-common.md](screens/00-common.md) 共通（画面枠・ナビ・エラー）
  - [01-login.md](screens/01-login.md) ログイン ／ [02-event.md](screens/02-event.md) イベント ／ [03-masters.md](screens/03-masters.md) マスタ
  - [04-declarations.md](screens/04-declarations.md) 申告取込 ／ [05-sufficiency.md](screens/05-sufficiency.md) 充足状況
  - [06-optimize.md](screens/06-optimize.md) 最適化 ／ [07-assignments.md](screens/07-assignments.md) 割当結果

---

## 凡例（実装状況）

- **実装済み**: 本 PoC で画面・機能を提供。
- **設定で反映 / 運用作業**: 画面はないが設定値や OS レベル運用で実現。
- **PoC対象外（申し送り）**: 要件としては定義済みだが本 PoC では未提供。実運用フェーズで順次提供。
