# 実装サマリ — U-01 `shared-kernel`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - Code Generation - Part 2 (Generation)（ユニット 1 / 8）

**本文書はマークダウンのサマリのみである。アプリケーションコードはワークスペースルート配下にある。**

---

## 1. 生成したファイル

### 1.1 アプリケーションコード（ワークスペースルート）

| パス | 内容 | 行数の目安 |
|------|------|----------|
| `pyproject.toml` | 依存、mypy strict、ruff、pytest の設定 | 80 |
| `.importlinter` | ユニット境界の契約（R-2 + 標準ライブラリのみ） | 55 |
| `.gitignore` | Python、ツールキャッシュ、**実行時データ（`*.db`, `audit/`）** を除外 | — |
| `README.md` | プロジェクト概要、読み替え規則、セットアップ、検証手順 | 130 |
| `config/.gitkeep` | 設定の外部化用ディレクトリ（NFR-M03）。中身は U-07 が置く | — |
| `src/shared_kernel/__init__.py` | 公開 API（55 シンボル） | 135 |
| `src/shared_kernel/identifiers.py` | `NewType` による識別子 5 種 | 25 |
| `src/shared_kernel/enums.py` | 列挙型 7 種、日本語変換表、`Event` 遷移表 | 135 |
| `src/shared_kernel/exceptions.py` | `DomainError` 階層 14 種 | 170 |
| `src/shared_kernel/value_objects.py` | 値オブジェクト 6 種（すべて frozen） | 160 |
| `src/shared_kernel/entities.py` | エンティティ 7 種（すべて frozen） | 250 |
| `src/shared_kernel/problem.py` | `AssignmentProblem`, `AssignmentResult`, `ConstraintViolation`, `HistoricalRecord` | 145 |
| `src/shared_kernel/availability.py` | `effective_declaration_for()`（U-01 唯一の振る舞い） | 65 |

### 1.2 テストコード

| パス | 内容 |
|------|------|
| `tests/conftest.py` | Hypothesis プロファイル（CI はランダムシード、`max_examples=500`） |
| `tests/shared_kernel/generators.py` | ドメイン生成器 **13 種**（うち 1 種は否定的生成器） |
| `tests/shared_kernel/test_properties.py` | プロパティベーステスト（P-01〜P-08 + ラウンドトリップ + frozen） |
| `tests/shared_kernel/test_examples.py` | 例示ベーステスト（受入基準由来） |

### 1.3 ドキュメント（`aidlc-docs/`）

| パス | 内容 |
|------|------|
| `aidlc-docs/construction/shared-kernel/code/implementation-summary.md` | 本文書 |

---

## 2. 検証結果

**4 つのゲートすべてが通過している。** Build and Test ステージで再実行する。

| ゲート | コマンド | 結果 |
|-------|---------|------|
| 単体テスト | `PYTHONPATH=src pytest` | **43 passed** |
| 型検査 | `mypy`（strict） | **Success: no issues found in 14 source files** |
| リンタ | `ruff check src tests` | **All checks passed** |
| ユニット境界 | `PYTHONPATH=src lint-imports` | **Contracts: 2 kept, 0 broken** |

### 2.1 契約が空振りしていないことの確認

`lint-imports` の契約が実効的であることを、**意図的に違反を混入させて確認した**。

```text
src/shared_kernel/identifiers.py に `import pydantic` を追加
  -> "shared_kernel uses the standard library only" BROKEN
  -> Contracts: 1 kept, 1 broken.  exit=1

削除後
  -> Contracts: 2 kept, 0 broken.  exit=0
```

**ドメイン層の純粋性は、規約ではなく機械的に強制されている。**

### 2.2 CI プロファイルでの実行

`CI=true` でプロファイルが切り替わり、`max_examples=500`、実行ごとのランダムシードとなる。19 のプロパティテストが 19.3 秒で通過した。

---

## 3. 設計判断の実装への対応

| 設計判断 | 出典 | 実装 |
|---------|------|------|
| ドメイン層は標準ライブラリのみ。Pydantic は U-07 の API 境界に限定 | NFR Design Q1=A | `.importlinter` の契約で強制。`pyproject.toml` の `dependencies = []` |
| 値オブジェクトとエンティティをすべて frozen とする | NFR Design Q2=A | `@dataclass(frozen=True, slots=True)`。`test_value_objects_are_frozen` / `test_entities_are_frozen` で検証 |
| 列挙値は英語識別子。境界で日本語に変換 | NFR Design Q3=A | `enums.py` の `_JapaneseEnum`、`from_japanese()` / `to_japanese()` |
| 識別子を `NewType` で区別 | NFR Design Q4=A | `identifiers.py`。`mypy strict` が取り違えを検出 |
| 例外は構造化された文脈属性を持つ。個人情報を含めない | NFR Design Q5=A | `DomainError.context()`。属性は `staff_id`, `event_id`, `facility_id`, `violated_rule` のみ |
| `Staff.__repr__` の伏字化（多層防御） | NFR Design Q6=A | `entities.py`。`.importlinter` の R-2 と併せて 2 層 |
| PBT のシードは実行ごとにランダム。失敗時に出力 | NFR Design Q8=A、PBT-08 | `tests/conftest.py` の `ci` プロファイル |
| 移動時間は秒単位の整数 | NFR Requirements Q4=C | `TravelMetrics.time_seconds: int` |
| 移動費用は内部で実数 | NFR Requirements Q5=B, Q7=A | `TravelMetrics.cost_yen: float` |
| 例外を送出する（結果型ではない） | NFR Requirements Q6=A | `DomainError` 階層 |
| 不公平性の指標は最大移動時間（ミニマックス） | Functional Design Q12=A | `ObjectiveWeights.inequity` の docstring に定式化を記載（U-04 へ引き渡し） |

---

## 4. 実装で特に効いている点

### 4.1 BR-07 — ソルバーのバグに対する型レベルの防波堤

`AssignmentResult.__post_init__` は以下を**拒否する**。

- `violations` に `C1`, `C2`, `C4`, `C5` が含まれる（FR-04.5 により降格されるのは C3 のみ）
- `objective_value` が NaN・無限大・負値（INV-06）
- `assignments` に同一 `(event_id, staff_id)` が 2 件以上（INV-01）

**降格されない制約の違反を含む結果は、U-04 のバグを意味する。** それが比較レポートを経て上長の机に届く前に、型の境界で失敗する。

プロパティ `test_p07_non_demotable_violation_is_refused` が C1, C2, C4, C5 のすべてで検証している。

### 4.2 frozen + 生成時バリデーション

この 2 つは分離できない。可変オブジェクトへの生成時バリデーションは無意味である。

```python
c = Coordinates(latitude=35.0, longitude=139.0)   # 検証される
c.latitude = 999.0                                # 可変なら 1 行後に壊れる
```

frozen であることで、**「型が存在する = 不変条件が成立している」が生涯にわたって保証される。**

### 4.3 「未申告」と「従事不可」の区別

`effective_declaration_for()` は 3 つの結果を返す。

| 返り値 | 意味 | 担当者の行動 |
|-------|------|------------|
| `None` | 未申告 | **督促すべき** |
| `is_available=True` | 従事可能 | 最適化の対象 |
| `is_available=False` | 従事不可（休暇・育児介護・健康配慮） | 督促してはならない |

両者とも最適化の対象外だが、業務上の意味が異なる。**「不足20名」とだけ表示すると、「未申告70名を督促すれば充足するかもしれない」という判断材料が隠れる。**

`test_undeclared_is_distinct_from_unavailable` がこれを検証している。**U-03 への申し送り U01-H10。**

### 4.4 同時刻の申告は fail closed

`declared_at` が同値の申告が 2 件あると、どちらが有効かを決定できない。**曖昧なまま最新の 1 件を選ばず、`AmbiguousDeclarationError` を送出する。**

CSV 一括インポート時にタイムスタンプの一意性を保証する責務は U-03 にある（申し送り U01-H11）。

### 4.5 否定的生成器の必要性

`gen_facility()` は BR-03 を満たす施設しか生成しない。したがって**拒否経路を一度も通らない**。

`gen_invalid_facility()` は、資格別必要人数の合計が必要人数を**超える**施設のコンストラクタ引数を生成する。これにより `test_p05_overspecified_facility_is_refused` が実際に BR-03 の拒否を検証できる。

**当初この否定的テストは `pytest.raises(Exception, ...)` と書かれていたが、どんな例外でも通ってしまい回帰を検出できないため、`QualificationRequirementExceedsHeadcountError` に絞った。**

---

## 5. 計画からの逸脱（2 件）

| # | 逸脱 | 理由 |
|---|------|------|
| 1 | **ディレクトリ名を `src/shared_kernel/`（アンダースコア）とした** | `unit-of-work.md` は `src/shared-kernel/` を定めたが、**Python のモジュール名にハイフンは使えない**（`import shared-kernel` は SyntaxError）。同じ読み替えを U-02 〜 U-08 に適用する |
| 2 | **Step 4（例外階層）を Step 3（列挙型）より先に実装した** | 列挙値の変換失敗が `UnknownEnumValueError` を送出するため、例外を先に定義しないと import できない。**計画の順序に誤りがあった** |

いずれも `aidlc-docs/audit.md` に記録済み。

---

## 6. 拡張ルール適合サマリ

### 6.1 PBT Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| **PBT-01** プロパティ特定 | **適合** | P-01〜P-08 のすべてが `test_properties.py` に実装されている |
| **PBT-02** ラウンドトリップ | **適合** | `test_enum_conversion_round_trips`: `from_japanese(to_japanese(x)) == x` を全列挙型の全メンバーで検証 |
| **PBT-03** 不変条件 | **適合** | P-01, P-03〜P-08 |
| **PBT-04** 冪等性 | **適合** | `test_p02_effective_declaration_is_idempotent` |
| **PBT-05** オラクル | **N/A** | U-01 に参照実装が存在しない。総当たり法によるオラクル検証は U-04 の責務（INV-12） |
| **PBT-06** ステートフルテスト | **N/A** | U-01 は可変状態を持たない（全型 frozen）。`Event` の状態遷移は純粋関数であり、遷移の実行と永続化は U-03 が担う |
| **PBT-07** 生成器の品質 | **適合** | 13 種のドメイン生成器を `tests/shared_kernel/generators.py` に集約。生の primitive 生成器のみを使うテストは存在しない。全ユニットから再利用可能 |
| **PBT-08** シュリンキングと再現性 | **適合** | シュリンキングを無効化していない。`derandomize=False`。`print_blob=True` により失敗時にシードを出力 |
| **PBT-09** フレームワーク選定 | **適合** | `hypothesis==6.122.3` が `pyproject.toml` の開発依存に含まれる |
| **PBT-10** 相補的テスト戦略 | **適合** | `test_examples.py` に 24 件の例示ベーステスト。US-08, US-09, US-12 の受入基準を具体値で固定。PBT が唯一のテストになっているパスは存在しない |

**ブロッキング所見: なし**

### 6.2 Security Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-03** アプリケーションログ | **適合** | `DomainError.context()` は職員 ID のみを返す。`Staff.__repr__` が氏名と居住小学校区を伏字にする。`test_staff_repr_redacts_personal_information` で検証 |
| **SECURITY-05** 入力検証 | **適合** | 全値オブジェクト・エンティティが `__post_init__` で生成時バリデーションを行う（BR-01〜BR-07） |
| **SECURITY-09** ハードニング | **適合** | 例外メッセージにスタックトレース・内部パス・フレームワークバージョンを含めない |
| **SECURITY-10** サプライチェーン | **適合** | `pyproject.toml` の依存はすべて厳密なバージョン固定。`latest` を使っていない。**プロダクション依存はゼロ**であり、U-01 は脆弱性スキャンの対象を 1 件も増やさない |
| **SECURITY-11** セキュアデザイン（多層防御） | **適合** | 個人情報の保護に 2 層: `.importlinter` の R-2（`src/security/` は `Staff` に到達できない）と `__repr__` の伏字化 |
| **SECURITY-15** fail closed | **適合** | すべてのバリデーション失敗が生成を拒否する。部分構築オブジェクトを返さない。未知の列挙値を `OTHER` へ丸めない |
| SECURITY-01, 02, 04, 06, 07, 08, 12, 13, 14 | **N/A** | U-01 は型定義のみ。暗号化・ネットワーク・HTTP ヘッダ・IAM・認証・認可・監査ログの表出を持たない。共有インフラ（`shared-infrastructure.md`）と U-03, U-06, U-07 が対象 |

**ブロッキング所見: なし**

### 6.3 Resiliency Extension

**スキップ**（Enabled = No。CQ4=A により次フェーズへ延期）。ルールファイルは未ロード。

---

## 7. `code-generation.md` の標準ステップのうち N/A としたもの

| ステップ | 判定 | 根拠 |
|---------|:----:|------|
| API レイヤ生成 | **N/A** | U-01 は API を公開しない。REST エンドポイントは U-07 が所有する |
| リポジトリレイヤ生成 | **N/A** | U-01 は永続化を持たない。`P-02 RepositoryPort` とその実装は U-03 が所有する |
| フロントエンドコンポーネント生成 | **N/A** | U-01 は UI を持たない。U-08 が所有する |
| DB マイグレーションスクリプト | **N/A** | U-01 は**エンティティの型**を定義するが**テーブル**は定義しない。Alembic マイグレーションは U-03 が所有する（U01-H18） |
| デプロイ成果物生成 | **部分的に N/A** | U-01 は独立してデプロイされない。独自のコンテナイメージ・プロセス・ヘルスチェック・環境変数を持たない。`pyproject.toml` はプロジェクト全体のビルド定義である |

**黙って飛ばさず、根拠付きで記録した。**

---

## 8. 後続ユニットへの申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U01-H27（新規）** | **ディレクトリ名の読み替え規則**: 文書上の `distance-cost` は、コード上 `src/distance_cost/` となる。Python のモジュール名にハイフンは使えない | **U-02 〜 U-08** |
| **U01-H28（新規）** | `.importlinter` に契約を追加すること。ユニットが増えるたびに R-1, R-3 〜 R-6 を追加する。特に **R-3（`distance_cost` は `shared_kernel` 以外を import してはならない）** が `C-01` の純粋関数性を機械的に保証する | **U-02** distance-cost |
| **U01-H29（新規）** | `tests/shared_kernel/generators.py` の 13 種の生成器を再利用すること（PBT-07 の集約要件）。新たなドメイン型を追加する場合、生成器も同ファイルに追加する | **U-02 〜 U-07** |
| **U01-H30（新規）** | `pyproject.toml` の `dependencies` にプロダクション依存を追加する際、バージョンを厳密に固定すること（SECURITY-10） | **U-02 〜 U-08** |
| U01-H5 | 目的関数の定式化は `min( w1*Σt_i + w2*Σc_i + w3*T_max )`、制約 `T_max >= t_i (∀i)`。`ObjectiveWeights.inequity` の docstring に記載済み | **U-04** |
| U01-H6 | `AssignmentResult.violations` に現れうる制約 ID は `C3` のみ。`DEMOTABLE_CONSTRAINTS` として定数化済み | **U-04** |
| U01-H10 | 「未申告」は「従事不可」ではない。`getSufficiencyStatus()` は 3 分類で集計すること | **U-03** |
| U01-H11 | CSV 一括インポート時、`declared_at` の一意性を保証すること。同時刻の申告は `AmbiguousDeclarationError` となる | **U-03** |
| U01-H21 | ドメイン型はすべて frozen。ORM のダーティチェックに依存する更新パターンは使えない | **U-03** |
| U01-H22 | `AvailabilityDeclaration.reason_category` は要配慮個人情報に近い。**監査ログに理由区分を記録しない** | **U-06** |
| U01-H23 | DTO ↔ ドメイン型の変換を実装すること。ドメイン層は Pydantic に依存しない | **U-07** |
| U01-H24 | 列挙値の変換表は U-01 にある。`from_japanese()` / `to_japanese()` を使うこと。未知の値は fail closed で拒否される | **U-03**, **U-07** |
| U01-H25 | グローバルエラーハンドラを設置し、`DomainError` を捕捉すること。`context()` を構造化ログへ、利用者には汎用メッセージを返す | **U-07** |
| U01-H26 | frozen dataclass の直列化方式を決定すること。復元時に `__post_init__` が再実行され、DB の不正データで fail closed になる | **U-04** |
