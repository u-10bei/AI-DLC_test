# Unit Test Execution

ユニットテストはコード生成時に各ユニットで生成済み。バックエンドは pytest（Hypothesis PBT 含む）、フロントは Vitest（fast-check PBT 含む）。

## バックエンド（Python / pytest + Hypothesis）

### 1. 全ユニットテスト実行

```bash
cd <repo-root>
PYTHONPATH=src python -m pytest -q
```

### 2. 結果（実測 2026-07-24）

- **合計 181 passed, 0 failed**（20 テストファイル、U-01〜U-07 + フロント連携の U08-H1/H4/H7）
- テスト対象ディレクトリ: `tests/shared_kernel`, `tests/distance_cost`, `tests/data_management`, `tests/optimization_engine`, `tests/comparison_report`, `tests/security`, `tests/api_orchestration`
- **PBT**: Hypothesis（`test_properties.py`）、ステートフル機械（`test_stateful.py`, PBT-06 ジョブ状態機械）

### 3. 型・リンタ・依存契約（ビルドゲート兼務）

```bash
python -m mypy --strict src tests      # Success: no issues found in 107 source files
python -m ruff check                   # All checks passed!
PYTHONPATH=src lint-imports            # Contracts: 14 kept, 0 broken.
```

### 4. 失敗時

1. `pytest -q` の出力で失敗テストを特定。
2. `PYTHONPATH=src python -m pytest tests/<unit>/<file>::<test> -q` で単体再現。
3. 修正 → 全ゲート green まで再実行。

---

## フロントエンド（TypeScript / Vitest + fast-check）

### 1. 全テスト実行

```bash
cd src/frontend
npm test                # = vitest run
```

### 2. 結果（実測 2026-07-24）

- **Test Files 5 passed, Tests 12 passed, 0 failed**
- 内訳: **PBT（fast-check）**= `converters.property.test.ts`（DTO↔ビューモデル写像のラウンドトリップ、P-FE01）+ `validation.property.test.ts`（フォーム検証、全重み 0 は常に無効=BR-02 等、P-FE02）。**コンポーネント（Testing Library）**= Login 401 汎用表示、CSV 行エラー、手動修正の制約違反表示。

### 3. 型・リンタ

```bash
npx tsc --noEmit        # clean（strict）
npx eslint .            # clean（H-5 境界 + react/no-danger）
```

### 4. H-5 境界の非空虚性（回帰確認）

```bash
# バックエンド import を注入 → eslint が no-restricted-imports で FAIL することを確認 → 除去
```

（Code Generation で確認済み。ゲートに組み込む場合はこの注入/除去を CI ステップ化する。）
