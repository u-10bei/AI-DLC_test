# Code Generation Implementation Summary — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Code Generation（ユニット 4 / 8）
**結果**: 4 ゲートすべて green。**システムの中核（MILP + OR-Tools CP-SAT）を実装**

---

## 1. 生成物

### 新規アプリコード（`src/optimization_engine/`）

| ファイル | 役割 | LC |
|---------|------|----|
| `__init__.py` | 公開 API | - |
| `scaling.py` | 正規化 + 整数スケール、整数 big-M（DP-02）| - |
| `model.py` | 抽象 `MilpModel` / `SolveOutcome` / `ServiceHistory` | - |
| `builder.py` | `AssignmentProblem`→`MilpModel`（純粋）| LC-01 |
| `solver_port.py` | `SolverPort`（抽象）| LC-02 |
| `cp_sat_adapter.py` | **`CpSatAdapter`（唯一の ortools importer）** | LC-02 |
| `diagnoser.py` | 実行不可能診断の決定木（H-9）| LC-03 |
| `result_mapper.py` | `SolveOutcome`→`AssignmentResult`（BR-07）| LC-04 |
| `service.py` | `OptimizationService`（統括、ピン検証、段階的求解）| LC-05 |
| `exceptions.py` | `PinnedAssignmentInfeasibleError`, `ModelConstructionError`（U04-H7）| - |
| `repository.py` | 結果を U-03 骨格テーブルに保存（U04-H4）| - |

### in-place 修正

| ファイル | 変更 |
|---------|------|
| `pyproject.toml` | `ortools==9.11.4210` 固定（SECURITY-10）。wheel packages に optimization_engine。mypy override（ortools 非型付けを cp_sat_adapter に限定）|
| `.importlinter` | optimization_engine root + R-5 境界契約 + solver 許可リスト |

### 新規テスト（`tests/optimization_engine/`）

`support.py`（決定的な問題ビルダ）、`test_examples.py`（最適選択・診断分岐・ピン検証、9 例）、`test_properties.py`（P-OPT01〜12、オラクル、INV-12 メタモルフィック）、`test_persistence.py`（U04-H4 統合）

---

## 2. 設計判断の実装

| パターン | 実装 |
|---------|------|
| DP-01 CP-SAT ネイティブ制約 | `AddAtMostOne`（C2）、`Add(sum==headcount)`（C1 等号）、線形（C3/C5）、`T_max>=t` OnlyEnforceIf |
| DP-02 整数スケール | `SCALE=10^6`、`M_int = ceil(S·Σw) + pairs + 2`。INV-12 保存（テストで確認）|
| DP-03 ortools 閉じ込め | `import ortools` は `cp_sat_adapter.py` のみ（リンタ契約 + mypy override で局所化）|
| DP-04 段階的求解 | 各 solve に予算（既定は設定値）、緩和・降格は実行不可能時のみ |
| DP-05 fail closed | ResultMapper が BR-07 を通す。実行不可能は `InfeasibilityDiagnosis` 戻り値、ピン違反は例外 |
| DP-06 再現性 + PII | seed/`num_workers=1` 固定、`log_search_progress=False`、変数名は ID のみ |

---

## 3. 4 ゲートの結果

| ゲート | 結果 |
|-------|------|
| `pytest` | **110 passed**（U-01 43 + U-02 31 + U-03 22 + U-04 14。回帰なし）|
| `mypy --strict` | **clean（53 files）**。ortools の非型付けは cp_sat_adapter の override に局所化 |
| `ruff` | **clean** |
| `lint-imports` | **8 契約 kept**。`import fastapi` を optimization_engine に注入 → 許可リスト BROKEN（非空虚性確認）|

---

## 4. 検証したプロパティ

| ID | 内容 | 結果 |
|----|------|:----:|
| P-OPT01 C1 | 実行可能解で各施設ちょうど定員 | ✅ |
| P-OPT02 C2 | 各職員高々 1 施設 | ✅ |
| P-OPT04 C4 | 従事不可者は非割当（構造保証）| ✅ |
| P-OPT05 C5 | 部署上限以下 | ✅（例示）|
| P-OPT06/07 | 目的有限非負、ギャップ∈[0,1] | ✅ |
| P-OPT08 | ピン留め保存 | ✅ |
| P-OPT10 | オラクル（総当たり最適と一致）| ✅ |
| **P-OPT12（INV-12）** | **C3 充足解が存在すれば C3 違反 0** | ✅ |

**実証**: C3 降格の例（管理職が不在 → C3 違反付きで求解）と、C3 充足の例（管理職在籍 → 違反なしで管理職を配置）の両方が期待通り動作。big-M の正しさを確認。

---

## 5. 計画からの特記

1. **mypy strict と ortools**: OR-Tools は型スタブを提供しないため、`cp_sat_adapter` モジュールに限定して `disallow_untyped_calls`/`disallow_any_explicit`/`warn_return_any` を緩和。これは DP-03（ortools の閉じ込め）と整合し、strict 保証は他の全モジュールで維持
2. **目的値の再計算**: `AssignmentResult.objective_value` はソルバー生値でなく、割当から `normalised_objective` で再計算。big-M ペナルティを含まず、常に有限・非負（BR-07 準拠）
3. **充足の母集合 / 部署上限**: C5 は `OptimizationParameters.department_cap_limit`（一律）を使用（`AssignmentProblem` に部署別上限フィールドがないため）
4. **環境**: `ortools==9.11.4210` は共有 env で protobuf をダウングレードするが、本プロジェクト以外の無関係パッケージへの影響で、U-04 には無害

---

## 6. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| U04-H1（解決）| ソルバー = CP-SAT | （完了）|
| U04-H6（解決）| `CpSatAdapter` 実装済み | （完了）|
| U04-H7（解決）| 例外追加済み | （完了）|
| U04-H8（解決）| ortools 固定・pip-audit/SBOM 対象・オフライン確認 | （完了）|
| U04-H9 | スケール係数 `S`・正規化定数・時間予算・ワーカー数の設定外部化（現状はモジュール定数）| 運用移行時 |
| U04-H3 | 履歴平準化の重み・過去従事回数の供給（現状は無効フック）| U-05 / 将来 |
| U04-H5 | 目的関数内訳（生値）の提示 | U-05 / U-07 |

---

## 7. 拡張ルール適合サマリ

| ルール | 判定 |
|--------|------|
| SECURITY-03（PII 非露出）| ✅ ログ抑制 + ID のみ変数名 + 診断/例外に ID のみ（テストで確認）|
| SECURITY-05（入力検証）| ✅ ModelBuilder の整合チェック、U-01 型の検証 |
| SECURITY-10（サプライチェーン）| ✅ ortools 固定 |
| SECURITY-15（fail closed）| ✅ BR-07 + 診断戻り値 + ピン検証 |
| PBT-01〜10 | ✅ P-OPT01〜12、Hypothesis、生成器 |
| Resiliency | スキップ（無効）|

**ブロッキング所見: なし**
