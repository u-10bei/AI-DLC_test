# 技術スタック決定 — U-04 `optimization-engine`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 4 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A

---

## 1. U-01 からの継承

バックエンド全体の技術スタックは U-01 で確定済み（Python, FastAPI, SQLite/PostgreSQL, SQLAlchemy+Alembic, Hypothesis, DB ベースジョブキュー, mypy strict, ruff, import-linter, uv/Poetry + pip-audit + SBOM）。U-04 はこれを継承する。本文書は **U-04 固有の差分**のみを記す。

---

## 2. H-3 の解決: MILP ソルバー製品（Q1=A）

**OR-Tools CP-SAT（Google, Apache-2.0）を採用する。** 申し送り H-3 を解決する。

| 観点 | OR-Tools CP-SAT | PuLP+CBC（却下 B）| 商用 Gurobi/CPLEX（却下 C）|
|------|----------------|------------------|--------------------------|
| 0-1 割当性能 | ◎（ポートフォリオ並列探索）| △（40 万変数で 300 秒に収まらない懸念）| ◎ |
| 時間制限 + 最良解 + ギャップ | ◎ ネイティブ（FR-04.6/US-20）| ○ | ◎ |
| ライセンス費用 | **なし（Apache-2.0）** | なし | **あり（不採用の決定打）** |
| オンプレミス | ◎ | ◎ | ○ |
| オフライン動作（FR-03.6）| ◎ 外部 API 不要 | ◎ | ◎ |
| 乱数シード | ◎ | △ | ◎ |

**採用理由**: 0-1 割当・スケジューリング問題に対する求解力、FR-04.6（時間制限内の最良解 + 最適性ギャップ）へのネイティブ対応、ライセンス費用なし・庁内オンプレミス・オフライン動作。

**SolverPort との関係**: Functional Design で `SolverPort`（抽象）を定義済み。CP-SAT アダプタ（`MilpModel` → CP-SAT API の翻訳）が具象実装（U04-H6）。将来別ソルバーへ差し替えても U-04 のロジックは不変。

---

## 3. プロダクション依存（U-04 固有）

| パッケージ | 用途 | バージョン固定 |
|-----------|------|:-------------:|
| `ortools` | CP-SAT ソルバー（`MilpModel` の求解）| ○（SECURITY-10、Code Generation で最新安定版に固定）|

- `dependencies` に厳密固定（SECURITY-10）。`latest` を使わない
- `pip-audit` の対象、SBOM に含める
- **オフライン動作を確認**（外部 API を呼ばない、FR-03.6）
- `ortools` は C++ バックエンドを含む大きめのバイナリ依存である点を留意（Code Generation でインストール可否を検証）

---

## 4. 性能戦略（Q2=A, Q3=A, NFR-P02）

- **厳密ソルバー + 時間制限**。タイムアウト時は**最良実行可能解 + 最適性ギャップ**を返す（`TIME_LIMIT_REACHED`、FR-04.6）。**別途の発見的アルゴリズムは本 PoC では実装しない**（CP-SAT が時間制限で自然に劣化）
- **変数枝刈りはしない**（正しさ優先, Q3=A）。最適解を除外しない。枝刈り（近傍施設への候補限定）は性能不足時の将来レバー、既定無効
- **性能検証は Build & Test** で代表データ（規模上限に近い）により実測（NFR-P02: 300 秒以内）

---

## 5. 再現性（Q4=A）

- `OptimizationParameters.random_seed` を CP-SAT の乱数シードに渡す。探索ワーカー数も固定する
- **保証範囲**: `OPTIMAL` 結果、または完了まで走った結果は再現可能。**壁時計タイムアウトに依存する最良解は再現保証の対象外**（実行環境の速度で変わりうる）。この限界を明記する

---

## 6. 非同期実行（Q5=A）

- 求解（最大 300 秒）は **U-01 の DB ベースジョブキューのワーカープロセス**で実行する。API をブロックしない
- U-04 は求解ロジックと `SolverPort` を提供する。ジョブ投入・ワーカー配線は U-07 が行う

---

## 7. U-04 のリンタ契約（Q6=A）

| 契約 | 内容 |
|------|------|
| **R（U-04 のユニット境界）** | `optimization_engine` は `shared_kernel`, `distance_cost`, `data_management` を（ユニットとして）import 可。`security`, `comparison_report`, `api_orchestration`, `frontend` を import してはならない |
| **許可する第三者** | `ortools`（プロダクション）|
| **禁止する第三者** | `pydantic`, `fastapi`（U-07 の API 境界のもの。求解層に持ち込まない）|

**Code Generation で `.importlinter` に追加し、非空虚性を確認する**（`import fastapi` の混入で BROKEN）。

---

## 8. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U04-H1（解決）** | ソルバー製品 = OR-Tools CP-SAT | （本ステージで解決）|
| **U04-H6** | `MilpModel` → CP-SAT API のアダプタ実装。乱数シード・ワーカー数・時間制限の設定 | U-04 Code Generation |
| **U04-H8（新規）** | `ortools` を `pyproject.toml` に追加・固定、pip-audit/SBOM、オフライン動作確認 | U-04 Code Generation |
| **U04-H2** | 正規化定数の既定値・外部化 | U-04 Code Generation |
