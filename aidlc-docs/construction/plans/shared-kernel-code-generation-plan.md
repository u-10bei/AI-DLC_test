# Code Generation Plan — U-01 `shared-kernel`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - Code Generation - Part 1 (Planning)（ユニット 1 / 8）

**本計画は Code Generation の唯一の真実の源（single source of truth）である。** Part 2 では本計画に書かれたステップのみを、書かれた順序どおりに実行する。逸脱してはならない。

---

## 1. ユニットコンテキスト（Step 1 の結果）

### 1.1 ユニット概要

| 項目 | 内容 |
|------|------|
| **ユニット** | U-01 `shared-kernel`（依存グラフの根） |
| **ワークスペースルート** | `/home/llm-user/AI-DLC_test`（`aidlc-state.md` より） |
| **プロジェクトタイプ** | Greenfield / モノリス（複数ユニット） |
| **依存するユニット** | **なし** |
| **このユニットに依存するユニット** | U-02, U-03, U-04, U-05, U-06, U-07 |

### 1.2 このユニットが実装するストーリー

`unit-of-work-story-map.md` より、**U-01 は主担当ストーリーを持たない**。全ユニットの型基盤である。

ただし、以下のストーリーの**不変条件**に対する検証責任を持つ。

| ストーリー | U-01 の責務 |
|-----------|-----------|
| US-12（追加の従事可否申告と申告履歴） | `effective_declaration_for()` の不変条件（有効な申告はちょうど 1 件） |
| US-09（小学校区マスタの CSV 一括インポート） | `Coordinates` の範囲検証（緯度 `[-90, 90]`、経度 `[-180, 180]`） |
| US-08（施設マスタの CSV 一括インポート） | `Facility` の資格別必要人数の合計 ≤ 必要人数 |
| US-17（目的関数の重み調整） | `ObjectiveWeights` の非負性と非ゼロ性 |
| US-16, US-19, US-20（割当最適化） | `AssignmentResult` の生成時検証（C3 以外の違反を拒否、INV-01, INV-06） |

### 1.3 期待されるインターフェースと契約

U-01 は**型と例外と変換表のみ**を公開する。関数は `effective_declaration_for()` の 1 つのみ。

### 1.4 このユニットが所有する DB エンティティ

**なし。** U-01 は永続化を持たない。エンティティ**の型**を定義するが、テーブルは U-03 が定義する。

### 1.5 生成の準備完了の確認

| 前提 | 状態 |
|------|:----:|
| Functional Design 完了 | ✅ |
| NFR Requirements 完了（技術スタック確定） | ✅ |
| NFR Design 完了（実装パターン確定） | ✅ |
| Infrastructure Design 完了 | ✅ |
| 依存ユニットの完了 | ✅（依存なし） |

---

## 2. コード配置（Step 2 の結果）

### 2.1 構造パターン

`code-generation.md` の Critical Rules より、**Greenfield multi-unit (monolith)** のパターンを適用する。

```text
src/{unit-name}/     と  tests/{unit-name}/
```

### 2.2 ⚠️ 発見した問題: ディレクトリ名と Python のモジュール名

`unit-of-work.md` は `src/shared-kernel/` を定めた。しかし **Python のモジュール名にハイフンは使えない。**

```python
import shared-kernel        # SyntaxError
from shared-kernel import   # SyntaxError
```

**採用する解決策**: ディレクトリ名を **`src/shared_kernel/`**（アンダースコア）とする。

| 概念 | 表記 |
|------|------|
| ユニット名（文書上） | `shared-kernel` |
| ディレクトリ名・パッケージ名（コード上） | `shared_kernel` |

`unit-of-work.md` のディレクトリ構造は、この Python 固有の制約に合わせて読み替える。**同じ読み替えを U-02 〜 U-08 にも適用する**（`distance-cost` → `distance_cost` 等）。

この決定を `aidlc-docs/construction/shared-kernel/code/` の実装サマリに記録し、後続ユニットへ申し送る。

### 2.3 正確なパス

**アプリケーションコード（ワークスペースルート配下。`aidlc-docs/` には決して置かない）**:

```text
/home/llm-user/AI-DLC_test/
├── pyproject.toml                          # 依存とツール設定
├── .importlinter                           # ユニット境界の強制（R-1〜R-6）
├── README.md
├── config/
│   └── .gitkeep                            # 設定の外部化（NFR-M03）。中身は U-07 が置く
├── src/
│   └── shared_kernel/
│       ├── __init__.py                     # 公開 API
│       ├── identifiers.py                  # NewType による識別子（5 種）
│       ├── enums.py                        # 列挙型（7 種）+ 日本語変換表
│       ├── exceptions.py                   # DomainError 階層（9 種）
│       ├── value_objects.py                # Coordinates, TravelMetrics, ObjectiveWeights, TravelParameters, OptimizationParameters
│       ├── entities.py                     # Department, SchoolDistrict, Staff, Facility, Event, AvailabilityDeclaration, Assignment
│       ├── problem.py                      # AssignmentProblem, AssignmentResult, ConstraintViolation, HistoricalRecord
│       └── availability.py                 # effective_declaration_for()
└── tests/
    └── shared_kernel/
        ├── __init__.py
        ├── generators.py                   # 8 種のドメイン生成器（PBT-07）
        ├── test_properties.py              # プロパティベーステスト（P-01〜P-08）
        └── test_examples.py                # 例示ベーステスト（PBT-10）
```

**ドキュメント（`aidlc-docs/` のみ。マークダウンのサマリ）**:

```text
aidlc-docs/construction/shared-kernel/code/
└── implementation-summary.md
```

---

## 3. 実行ステップ（Part 2 で実行）

**各ステップ完了時に即座に `[x]` へ更新する。**

---

### Step 1: プロジェクト構造セットアップ（Greenfield、最初のユニット）

- [x] `pyproject.toml` を作成する
  - [x] プロジェクトメタデータ、Python バージョン制約
  - [x] **プロダクション依存**: なし（U-01 は標準ライブラリのみ）。他ユニットの依存はプレースホルダとして記載しない
  - [x] **開発依存**: `pytest`, `hypothesis`, `mypy`, `ruff`, `import-linter`
  - [x] `[tool.mypy]` strict モード（NFR Requirements Q11=A）
  - [x] `[tool.ruff]` リンタ設定
  - [x] `[tool.pytest.ini_options]` テスト設定
  - [x] **SECURITY-10**: バージョンを固定する。`latest` を使わない
- [x] `.importlinter` を作成し、リンタ規則 R-2, R-3 を定義する
  - [x] R-2: `shared_kernel` は他のいかなるユニットも import してはならない
  - [x] R-3 以降の規則は、対象ユニットが存在してから追加する（現時点では `shared_kernel` のみ存在）
- [x] ディレクトリ構造を作成する（`src/shared_kernel/`, `tests/shared_kernel/`, `config/`）
- [x] `.gitignore` に Python 用のエントリを追加する

**根拠**: `code-generation.md` は Greenfield で Project Structure Setup を求める。U-01 は最初のユニットであるため、プロジェクト全体の骨格をここで作る。

---

### Step 2: ビジネスロジック生成 — 識別子（`identifiers.py`）

- [x] `NewType` による 5 種の識別子を定義する: `StaffId`, `FacilityId`, `SchoolDistrictId`, `DepartmentId`, `EventId`

**設計参照**: `nfr-design-patterns.md` パターン 4（Q4=A）
**根拠**: `mypy` strict が識別子の取り違えを検出する。実行時オーバーヘッドはゼロ。

---

### Step 3: ビジネスロジック生成 — 列挙型と変換表（`enums.py`）

- [x] 7 種の列挙型を英語識別子で定義する: `JobType`, `Position`, `Qualification`, `EventType`, `EventStatus`, `ReasonCategory`, `SolverStatus`
- [x] 日本語表記との相互変換表を定義する（LC-03）
- [x] `from_japanese()` / `to_japanese()` を実装する
- [x] **未知の値は例外を送出する**（fail closed。`OTHER` へサイレントに丸めない）
- [x] `Event` のステータス遷移表を定義する（許可される遷移のみ）

**設計参照**: `nfr-design-patterns.md` パターン 3（Q3=A）、`logical-components.md` LC-03、`business-rules.md` セクション 2

---

### Step 4: ビジネスロジック生成 — 例外階層（`exceptions.py`）

- [x] `DomainError` を基底として定義する
  - [x] 構造化された文脈属性: `staff_id`, `event_id`, `facility_id`, `violated_rule`
  - [x] **メッセージにも属性にも個人情報（氏名、居住小学校区）を含めない**（SECURITY-03）
- [x] 9 種のサブクラスを定義する（`business-rules.md` セクション 4.2 の一覧）
- [x] 列挙値の変換失敗を表す `UnknownEnumValueError` を追加する（Step 3 が使用）

**設計参照**: `nfr-design-patterns.md` パターン 5（Q5=A）、`logical-components.md` LC-02

---

### Step 5: ビジネスロジック生成 — 値オブジェクト（`value_objects.py`）

- [x] すべて `@dataclass(frozen=True)` とする（NFR Design Q2=A）
- [x] `Coordinates` — BR-01（緯度 `[-90, 90]`、経度 `[-180, 180]`、NaN / 無限大の拒否）
- [x] `TravelMetrics` — `distance_km: float`, `time_seconds: int`, `cost_yen: float`
- [x] `ObjectiveWeights` — BR-02（全重み非負、少なくとも 1 つが正）
- [x] `TravelParameters` — BR-04（`detour_factor >= 1.0`, `average_speed_kmh > 0`）
- [x] `OptimizationParameters`
- [x] `QualificationRequirement`
- [x] すべて `__post_init__` で生成時バリデーションを行う（fail closed）

**設計参照**: `domain-entities.md` セクション 4、`business-rules.md` BR-01, BR-02, BR-04

---

### Step 6: ビジネスロジック生成 — エンティティ（`entities.py`）

- [x] すべて `@dataclass(frozen=True)` とする
- [x] `Department`, `SchoolDistrict`, `Staff`, `Facility`, `Event`, `AvailabilityDeclaration`, `Assignment`
- [x] `Facility` — BR-03（資格別必要人数の合計 ≤ 必要人数、要件の重複禁止）
- [x] `AvailabilityDeclaration` — BR-05（`is_available` と `reason_category` / `other_reason_note` の整合）
- [x] `Staff` — BR-06、および **`__repr__` / `__str__` の伏字化**（氏名と居住小学校区。SECURITY-03、NFR Design Q6=A）
- [x] `Event` — ステータス遷移メソッド（`start_collecting_declarations`, `mark_optimized`, `reopen_declarations`, `confirm`）。許可されない遷移は `InvalidStateTransitionError`

**設計参照**: `domain-entities.md` セクション 3、`business-rules.md` BR-03, BR-05, BR-06、セクション 2.2

---

### Step 7: ビジネスロジック生成 — 問題と結果（`problem.py`）

- [x] `ConstraintViolation`（frozen）
- [x] `AssignmentProblem`（frozen）
- [x] `AssignmentResult`（frozen）— **BR-07**
  - [x] `objective_value` が有限かつ非負（INV-06）
  - [x] `0 <= optimality_gap <= 1`
  - [x] **`violations` に `C1`, `C2`, `C4`, `C5` が現れたら拒否する**（降格されるのは C3 のみ）
  - [x] `assignments` に同一 `(event_id, staff_id)` が 2 件以上あれば拒否する（INV-01）
- [x] `HistoricalRecord`（frozen）

**設計参照**: `domain-entities.md` セクション 3.8、`business-rules.md` BR-07
**重要**: BR-07 は**ソルバーのバグに対する型レベルの防波堤**である（`business-logic-model.md` セクション 6.1）。

---

### Step 8: ビジネスロジック生成 — 唯一の振る舞い（`availability.py`）

- [x] `effective_declaration_for(staff_id, event_id, history) -> AvailabilityDeclaration | None`
  - [x] 該当 0 件 → `None`（**未申告。従事可能とはみなさない**）
  - [x] 該当 1 件以上 → `declared_at` が最大のもの
  - [x] `declared_at` が同値で複数 → `AmbiguousDeclarationError`（fail closed）

**設計参照**: `business-rules.md` セクション 3、`business-logic-model.md` セクション 2
**重要**: 「未申告」と「従事不可」は区別される（申し送り U01-H10）。

---

### Step 9: ビジネスロジック生成 — 公開 API（`__init__.py`）

- [x] U-01 が公開する型・例外・関数を明示的に再エクスポートする
- [x] `__all__` を定義する

---

### Step 10: ビジネスロジック単体テスト — ドメイン生成器（`tests/shared_kernel/generators.py`）

**PBT-07（生成器の品質）を満たす。全ユニットのテストから再利用される。**

- [x] `gen_coordinates()` — 緯度経度の範囲内。境界値（±90, ±180, 0）を含む
- [x] `gen_school_district()`
- [x] `gen_staff()` — 職種 1、役職 1、資格 0 個以上
- [x] `gen_facility()` — BR-03 を満たす（資格別必要人数の合計 ≤ 必要人数）
- [x] `gen_availability_declaration()` — BR-05 を満たす
- [x] `gen_objective_weights()` — BR-02 を満たす
- [x] `gen_travel_parameters()` — BR-04 を満たす
- [x] `gen_assignment_problem()` — 上記を組み合わせる
- [x] **否定的生成器** `gen_invalid_facility()` — BR-03 に**違反する**施設を生成する（NFR Design セクション 2 の申し送り）

**根拠**: PBT-07 は「生の primitive 生成器のみを使ってはならない」「生成器を集約し再利用可能にすること」と定める。`gen_facility()` は妥当な施設しか生成しないため、違反経路のテストには専用の否定的生成器が必要である。

---

### Step 11: ビジネスロジック単体テスト — プロパティベーステスト（`test_properties.py`）

**PBT-03（不変条件）、PBT-04（冪等性）を満たす。**

- [x] **P-01**（Invariant）: `effective_declaration_for()` が返すのはちょうど 1 件であり、最大の `declared_at` を持つ
- [x] **P-02**（Idempotence）: `effective_declaration_for()` は冪等である
- [x] **P-03**（Range constraint）: `Coordinates` は範囲内の入力でのみ生成に成功する
- [x] **P-04**（Range constraint）: `ObjectiveWeights` は非負かつ少なくとも 1 つが正の入力でのみ成功する
- [x] **P-05**（Invariant）: `Facility` は BR-03 を満たす入力でのみ成功する。`gen_invalid_facility()` の出力では失敗する
- [x] **P-06**（Invariant）: `Assignment` の集合で同一 `(event_id, staff_id)` は高々 1 つ
- [x] **P-07**（Invariant）: `AssignmentResult.violations` に `C3` 以外が現れない
- [x] **P-08**（Range constraint）: `TravelParameters` は範囲内の入力でのみ成功する
- [x] **追加**: 列挙値の変換ラウンドトリップ（`from_japanese(to_japanese(e)) == e`）— PBT-02
- [x] **追加**: 未申告と従事不可の区別（`effective_declaration_for` が `None` を返す場合と `is_available=False` を返す場合）

**PBT-08 の設定**: シュリンキングを無効化しない。シードは CI で実行ごとにランダム。失敗時にシードを出力する（`pyproject.toml` の pytest 設定で担保）。

---

### Step 12: ビジネスロジック単体テスト — 例示ベーステスト（`test_examples.py`）

**PBT-10（相補的テスト戦略）を満たす。「PBT を唯一のテストとしてはならない」。**

- [x] `Event` のステータス遷移: 許可される 4 遷移と、禁止される遷移の代表例
- [x] `Staff.__repr__` が氏名と居住小学校区を伏字にすること（SECURITY-03）
- [x] `effective_declaration_for()`: 未申告（`None`）、従事可能、従事不可、再申告の 4 ケース
- [x] `AmbiguousDeclarationError`: 同時刻の申告が 2 件
- [x] `AssignmentResult`: C3 違反を含む結果は生成できる。C1 違反を含む結果は拒否される
- [x] 列挙値の変換: 未知の日本語値（`課長補佐`）で `UnknownEnumValueError`
- [x] `Coordinates`: 緯度 95.0 で `InvalidCoordinatesError`（US-09 の受入基準）
- [x] `Facility`: 必要人数 5 名に対し管理職 6 名で `QualificationRequirementExceedsHeadcountError`（US-08 の受入基準）

**根拠**: PBT-10 は「業務上重要なシナリオは、PBT が同じ性質を扱っていても、明示的な例示ベーステストを持たなければならない」と定める。

---

### Step 13: API レイヤ生成 — **N/A**

- [x] **N/A の根拠を記録する**: U-01 は API を公開しない。REST エンドポイントは U-07 `api-orchestration` が所有する。U-01 はネットワークに触れない（`infrastructure-design.md` セクション 3）

### Step 14: リポジトリレイヤ生成 — **N/A**

- [x] **N/A の根拠を記録する**: U-01 は永続化を持たない。`P-02 RepositoryPort` とその実装は U-03 `data-management` が所有する

### Step 15: フロントエンドコンポーネント生成 — **N/A**

- [x] **N/A の根拠を記録する**: U-01 は UI を持たない。U-08 `frontend` が所有する

### Step 16: DB マイグレーションスクリプト — **N/A**

- [x] **N/A の根拠を記録する**: U-01 は**エンティティの型**を定義するが、**テーブル**は定義しない。Alembic マイグレーションは U-03 が所有する（申し送り U01-H18）

### Step 17: デプロイ成果物生成 — **部分的に N/A**

- [x] **N/A の根拠を記録する**: U-01 は独立してデプロイされない（`deployment-architecture.md`）。独自のコンテナイメージ、プロセス、ヘルスチェック、環境変数を持たない
- [x] ただし Step 1 で作成する `pyproject.toml` は、プロジェクト全体のビルド成果物定義である

---

### Step 18: ドキュメント生成

- [x] `README.md` をワークスペースルートに作成する
  - [x] プロジェクト概要、ディレクトリ構造、ユニット一覧
  - [x] セットアップ手順、テスト実行手順
  - [x] **ハイフン → アンダースコアの読み替え規則**を明記する
- [x] `aidlc-docs/construction/shared-kernel/code/implementation-summary.md` を作成する（マークダウンのサマリのみ）
  - [x] 生成したファイルの一覧とパス
  - [x] 設計判断の実装への対応
  - [x] 拡張ルール適合サマリ
  - [x] 後続ユニットへの申し送り

---

## 4. 拡張ルールの適合確認（Part 2 の最後に実施）

### 4.1 PBT

- [x] **PBT-01**: 特定済みプロパティ（P-01〜P-08）がすべて実装されていることを確認する
- [x] **PBT-02**: 列挙値の変換ラウンドトリップテストが存在することを確認する
- [x] **PBT-03**: 不変条件のプロパティテストが存在することを確認する
- [x] **PBT-04**: `effective_declaration_for()` の冪等性テストが存在することを確認する
- [x] **PBT-05**: **N/A**。U-01 に参照実装（オラクル）が存在しない。オラクル検証は U-04 の責務（INV-12）
- [x] **PBT-06**: **N/A**。U-01 は可変状態を持たない（全型 frozen）。`Event` のステータス遷移の状態機械テストは U-03（`S-01 EventService`）が担う
- [x] **PBT-07**: 9 種の生成器（8 種の正常系 + 1 種の否定的生成器）が集約され、再利用可能であることを確認する
- [x] **PBT-08**: シュリンキングが有効であり、シードが失敗時に出力されることを確認する
- [x] **PBT-09**: `hypothesis` が `pyproject.toml` の依存に含まれることを確認する
- [x] **PBT-10**: 例示ベーステストが存在し、PBT が唯一のテストになっていないことを確認する

### 4.2 SECURITY

- [x] **SECURITY-03**: 例外の属性・メッセージ・`Staff.__repr__` のいずれにも個人情報が含まれないことを確認する
- [x] **SECURITY-05**: 全値オブジェクト・エンティティに生成時バリデーションが実装されていることを確認する
- [x] **SECURITY-09**: エラーメッセージにスタックトレース・内部パスが含まれないことを確認する
- [x] **SECURITY-10**: `pyproject.toml` の依存がバージョン固定されており、`latest` を使っていないことを確認する
- [x] **SECURITY-11**: 個人情報保護の多層防御（`__repr__` 伏字化 + `.importlinter` の規則）を確認する
- [x] **SECURITY-15**: すべてのバリデーション失敗が生成を拒否する（fail closed）ことを確認する
- [x] **SECURITY-01, 02, 04, 06, 07, 08, 12, 13, 14**: **N/A**。U-01 は型定義のみ。根拠付きで記録する

### 4.3 Resiliency

- [x] レジリエンシー拡張は無効（Enabled = No）のため適合確認を行わない旨を記録する

---

## 5. 完了処理

- [x] `aidlc-docs/aidlc-state.md` の進捗を更新する
- [x] ハイフン → アンダースコアの読み替え規則を、後続ユニットへの申し送りとして記録する
- [ ] 標準の 2 択完了メッセージ（Request Changes / Continue to Next Stage）を提示し、承認を待つ

---

## 6. 計画サマリ（Step 5）

| 項目 | 内容 |
|------|------|
| **総ステップ数** | 18（うち実質的な生成は 12、N/A の記録が 5、ドキュメントが 1） |
| **生成するアプリケーションファイル** | 12（`pyproject.toml`, `.importlinter`, `README.md`, `src/shared_kernel/` 8 ファイル, `tests/shared_kernel/` 4 ファイル） |
| **生成するドキュメント** | 1（`aidlc-docs/construction/shared-kernel/code/implementation-summary.md`） |
| **ストーリーカバレッジ** | 主担当ストーリーなし。5 ストーリー（US-08, US-09, US-12, US-16/19/20, US-17）の不変条件を検証する |
| **プロダクション依存** | **なし**（標準ライブラリのみ） |
| **開発依存** | `pytest`, `hypothesis`, `mypy`, `ruff`, `import-linter` |

### 6.1 生成アプローチ

1. **プロジェクト骨格を先に作る**（Step 1）。U-01 は最初のユニットであり、`pyproject.toml` と `.importlinter` はプロジェクト全体の基盤となる
2. **依存の少ない順に生成する**（Step 2 → 9）。識別子 → 列挙型 → 例外 → 値オブジェクト → エンティティ → 問題 → 振る舞い → 公開 API
3. **生成器を先に作ってからテストを書く**（Step 10 → 11 → 12）。PBT-07 の生成器がテストの前提になる
4. **N/A のステップも明示的に記録する**（Step 13 → 17）。`code-generation.md` が列挙する標準ステップを黙って飛ばさない

### 6.2 ⚠️ 計画上の重要な注記

**ディレクトリ名の読み替え**: `unit-of-work.md` は `src/shared-kernel/` を定めたが、**Python のモジュール名にハイフンは使えない**。`src/shared_kernel/` を採用する。同じ読み替えを U-02 〜 U-08 に適用する（セクション 2.2）。
