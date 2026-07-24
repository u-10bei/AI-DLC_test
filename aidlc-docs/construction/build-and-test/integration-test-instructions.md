# Integration Test Instructions

## 目的

ユニット間の相互作用を検証する。本システムはモノリスで、**U-07 api_orchestration が合成ルートとして U-01〜U-06 を配線する**ため、U-07 の HTTP 境界テストが実質的な結合テストになっている（実際の DB・ソルバー・セキュリティを通し、モックしない）。フロント↔バックエンドは REST 契約で結合する。

## テストシナリオ（実装済み・実行可能）

### シナリオ 1: エンドツーエンドの価値実証フロー（U-07 → U-01〜U-06）
- **内容**: ログイン → イベント作成 → マスタ取込 → 申告取込 → 充足確認 → 最適化投入（202）→ ワーカー求解 → 割当取得（SUCCEEDED）。
- **場所**: `tests/api_orchestration/test_examples.py::test_optimization_is_a_job_not_a_blocking_call`
- **経由**: U-03（永続化）、U-02（移動指標）、U-04（CP-SAT 求解）、U-06（認証・認可）を実際に通す。
- **期待**: 202 受理 → `step()` 実行 → 状態 SUCCEEDED、割当件数 = 施設必要人数。

### シナリオ 2: 手動修正の制約検証（U-07 → U-04）
- **内容**: 割当を手動変更 → U-04 の `validate_assignments` が C1〜C5 を判定 → 違反時 400 + violations。
- **場所**: `test_examples.py::test_manual_edit_rejects_a_constraint_violation`

### シナリオ 3: CSV 取込/出力のサニタイズ（U-07 → U-03 → U-06）
- **内容**: 職員/施設/小学校区の取込と、エクスポート時の数式インジェクション無害化（P-API07）。
- **場所**: `test_examples.py::test_exported_csv_is_sanitised`、`test_masters.py::test_facility_export_is_sanitised_like_staff`

### シナリオ 4: セキュリティチェーン（U-07 → U-06）
- **内容**: 未認証 401、IP 非許可 403、レート超過、ログイン/ログアウト、セキュリティヘッダ、セッション失効。
- **場所**: `test_examples.py`、`test_properties.py`（P-API02/03/06）

### シナリオ 5: フロント配信 × 認証（U-08 ↔ U-07、U08-H4/H7）
- **内容**: ビルド済み SPA を backend が配信。SPA シェルは認証なしで読み込め、API は保護され、IP 制限は静的にも適用。
- **場所**: `tests/api_orchestration/test_static.py`（3 テスト）
- **根拠**: Build and Test で発覚した実在の不具合（deny-by-default 認証が SPA シェルまで 401 にしていた）を修正（U08-H7）。

### シナリオ 6: ジョブ状態機械（U-07 内部の結合、PBT-06）
- **内容**: enqueue/claim/finish の無作為列で「終端から遷移しない・二重 claim しない」。
- **場所**: `tests/api_orchestration/test_stateful.py`

## 実行

```bash
# 全結合テスト（バックエンド）
PYTHONPATH=src python -m pytest tests/api_orchestration -q      # 全 U-07 結合テスト

# フロント↔バックエンドの REST 契約整合（型レベル）
cd src/frontend && npx tsc --noEmit    # DTO 写像の型不整合を検出
cd src/frontend && npm test            # 写像ラウンドトリップ PBT（契約ドリフト検出）
```

## サービス起動が要る手動 E2E（任意）

```bash
# 1. backend + worker を起動
uvicorn api_orchestration:build_application --factory --port 8000
python -m api_orchestration.worker            # 別プロセス（求解）
# 2. フロント（Vite dev、API を :8000 にプロキシ）
cd src/frontend && npm run dev
# 3. ブラウザで価値実証フローを手動確認（Playwright を導入すれば自動化可能、NFR Design 任意）
```

## クリーンアップ

インメモリ SQLite のためテスト後の後始末は不要。手動起動時は各プロセスを停止。
