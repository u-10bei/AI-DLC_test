# Build and Test Summary

**日付**: 2026-07-24
**対象**: 全 8 ユニット（U-01〜U-08）+ フロント/バックエンド結合

## Build Status

| 対象 | ツール | 状態 | 成果物 |
|------|-------|------|--------|
| バックエンド | Python 3.12 / mypy / ruff / import-linter | **Success** | コンパイル成果物なし（型・リンタ・依存契約で担保） |
| フロントエンド | Node v22 / Vite | **Success** | `src/frontend/dist/`（JS 231 KB / gzip 73 KB、CSS 1.7 KB、index.html） |

## Test Execution Summary

### Unit Tests
- **バックエンド（pytest + Hypothesis）**: 合計 **181 / passed 181 / failed 0**
- **フロントエンド（Vitest + fast-check）**: 合計 **12 / passed 12 / failed 0**
- **PBT**: Hypothesis（ステートフル PBT-06 含む）+ fast-check（写像/検証プロパティ）— PBT 拡張ブロッキング適合
- **Status**: **Pass**

### 型・リンタ・依存契約（ビルドゲート）
- `mypy --strict`: **107 files clean** ／ `ruff`: **clean** ／ `lint-imports`: **14 契約 kept, 0 broken**
- フロント `tsc --noEmit`: **clean** ／ `eslint`: **clean**（H-5 境界 + react/no-danger）
- **H-5 非空虚性**: バックエンド import 注入 → eslint FAIL、除去 → clean（証明済み）
- **Status**: **Pass**

### Integration Tests
- **シナリオ 6 件**（integration-test-instructions.md）: 価値実証フロー（U-07→U-01〜06）、手動修正検証（→U-04）、CSV サニタイズ（→U-03/U-06）、セキュリティチェーン（→U-06）、**SPA 配信×認証（U-08↔U-07）**、ジョブ状態機械（PBT-06）
- すべて `tests/api_orchestration` の実 HTTP テストで自動化（モックなし）
- **Status**: **Pass**

### Performance Tests
- 求解の時間打ち切り・プロセス分離（求解は tx 外、API 応答性維持）は設計・テストで担保。
- バンドルサイズ実測 231 KB（gzip 73 KB）。
- 負荷/ストレス試験は PoC スコープ外（SLA なし）→ 実運用移行時の申し送り。
- **Status**: **Pass（PoC 範囲）**

### Security Tests
- 認証・認可・IP 制限・入力検証・CSV サニタイズ・エラー非開示・監査を自動テスト/構造で担保（security-test-instructions.md）。
- pip-audit/SBOM（SECURITY-10）は実運用 CI への申し送り。SECURITY-12（MFA）は N/A（管理者ロールなし）。
- **Status**: **Pass（適用可能ルール）**

## ビルド/テスト中に見つけて修正した実在の不具合

- **U08-H7（本ステージで発覚・修正）**: deny-by-default 認証ミドルウェアが SPA シェル（`GET /`）まで 401 にし、ログイン前にフロントを読み込めなかった。認証を **API ルートのみ**に適用し、静的/SPA パスは通す（IP 制限・レート制限は維持）よう修正。回帰テスト `test_static.py`（3 件）を追加。
- **U07-H15（前セッションで発覚・修正）**: ミドルウェアが注入クロックを使わずセッション期限を実時間で判定していた（再開日の変化で全認証テストが失効扱い）。単一クロック注入に修正。

## Overall Status

- **Build**: **Success**（バックエンド + フロントエンド）
- **All Tests**: **Pass**（backend 181 + frontend 12、結合 6 シナリオ）
- **Ready for Operations**: **Yes**

## Next Steps

- OPERATIONS フェーズ（現状プレースホルダ）: デプロイ計画・監視・運用手順。
- 実運用移行時の申し送り: 静的配信の本番構成（U08-H4/H7）、`trusted_proxies` 設定、pip-audit/SBOM の CI 組込、負荷試験、U05-H6（比較機能の履歴テーブル）・U08-H2（割当の移動指標）・U08-H3（比較画面）・U08-H6（CSS Modules 化の要否）・U06-H5（アカウント払い出し）。
