# 論理コンポーネント — U-01 `shared-kernel`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - NFR Design（ユニット 1 / 8）

---

## 1. U-01 はインフラコンポーネントを持たない

**これが本文書の最も重要な記述である。**

`construction/nfr-design.md` は「Logical Components — インフラコンポーネント（キュー、キャッシュ、サーキットブレーカ等）とその統合パターン」の設計を求める。

**U-01 はこれらを一切持たない。** 判定はユーザーの確認を得ている（Q7=A）。

| インフラコンポーネント | U-01 が持つか | 実際の所有ユニット |
|---------------------|:-----------:|------------------|
| ジョブキュー | **持たない** | **U-04** optimization-engine（`P-05 JobStorePort`、`A-06 JobRunnerAdapter`） |
| キャッシュ | **持たない** | **U-02** distance-cost（`P-03 DistanceCachePort` の定義）、**U-03** data-management（実装） |
| サーキットブレーカ / リトライ | **持たない** | どのユニットも持たない。外部サービスへの依存がないため（レジリエンシー拡張は無効） |
| メッセージブローカ | **持たない** | どのユニットも持たない（Redis を導入しない。NFR Requirements Q5=A） |
| セッションストア | **持たない** | **U-06** security |
| 監査ログの追記専用ファイル | **持たない** | **U-06** security（`P-04 AuditLogPort`、`A-05 AuditLogAdapter`） |
| データベース接続プール | **持たない** | **U-03** data-management（`A-02 PersistenceAdapter`） |

### 1.1 U-01 が何も持たないことの根拠

U-01 は**依存グラフの根**であり、何にも依存しない（`unit-of-work-dependency.md`）。インフラコンポーネントを持つということは、そのコンポーネントのライブラリに依存するということである。それは U-01 の位置づけと矛盾する。

**この「何も持たない」という性質が、U-01 を安全に共有できる理由である。** 6 ユニットが U-01 に依存しても、インフラの選択が伝播しない。SQLite を PostgreSQL に替えても、U-01 は変わらない。

---

## 2. U-01 が持つ論理コンポーネント

U-01 が持つのは、以下の 3 種のみである。いずれも標準ライブラリのみに依存する。

```text
+-------------------------------------------------------------------+
|  U-01 shared-kernel                                               |
|                                                                   |
|  +-------------------------------------------------------------+  |
|  |  LC-01: ドメイン型                                          |  |
|  |    エンティティ 9 種、値オブジェクト 6 種                   |  |
|  |    すべて frozen dataclass                                  |  |
|  |    __post_init__ による生成時バリデーション                 |  |
|  +-------------------------------------------------------------+  |
|                                                                   |
|  +-------------------------------------------------------------+  |
|  |  LC-02: 例外階層                                            |  |
|  |    DomainError を基底とする 9 種の例外                      |  |
|  |    構造化された文脈属性を持つ                                |  |
|  +-------------------------------------------------------------+  |
|                                                                   |
|  +-------------------------------------------------------------+  |
|  |  LC-03: 列挙値の変換表                                       |  |
|  |    英語識別子 <-> 日本語表記                                |  |
|  |    U-03（CSV）と U-07（API DTO）の双方が利用する            |  |
|  +-------------------------------------------------------------+  |
|                                                                   |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
|  tests/shared-kernel/                                             |
|                                                                   |
|  +-------------------------------------------------------------+  |
|  |  LC-04: ドメイン生成器（テストユーティリティ）              |  |
|  |    8 種の Hypothesis 生成器                                 |  |
|  |    全ユニットのテストから再利用される（PBT-07）             |  |
|  +-------------------------------------------------------------+  |
|                                                                   |
+-------------------------------------------------------------------+
```

---

### LC-01: ドメイン型

| 種別 | 型 |
|------|----|
| エンティティ（9） | `Department`, `SchoolDistrict`, `Staff`, `Facility`, `Event`, `AvailabilityDeclaration`, `Assignment`, `AssignmentResult`, `HistoricalRecord` |
| 値オブジェクト（6） | `Coordinates`, `TravelMetrics`, `ObjectiveWeights`, `TravelParameters`, `OptimizationParameters`, `AssignmentProblem` |
| 補助的な値オブジェクト | `QualificationRequirement`, `ConstraintViolation` |
| 識別子型（`NewType`、5） | `StaffId`, `FacilityId`, `SchoolDistrictId`, `DepartmentId`, `EventId` |
| 列挙型（7） | `JobType`, `Position`, `Qualification`, `EventType`, `EventStatus`, `ReasonCategory`, `SolverStatus` |

**依存**: 標準ライブラリのみ（`dataclasses`, `enum`, `typing`, `datetime`, `math`）。

**特性**:
- すべて `@dataclass(frozen=True)`
- `__post_init__` で生成時バリデーション（BR-01〜BR-07）
- `Staff` のみ `__repr__` / `__str__` を伏字化（個人情報の保護）

---

### LC-02: 例外階層

```text
DomainError（基底）
  属性: staff_id?, event_id?, facility_id?, violated_rule
  制約: メッセージ・属性のいずれにも個人情報を含めない

├── InvalidCoordinatesError                        （BR-01）
├── AllWeightsZeroError / NegativeWeightError      （BR-02）
├── QualificationRequirementExceedsHeadcountError  （BR-03）
├── DuplicateQualificationRequirementError         （BR-03）
├── InvalidTravelParametersError                   （BR-04）
├── InconsistentDeclarationError                   （BR-05）
├── NonDemotableConstraintViolationError           （BR-07）
├── InvalidStateTransitionError                    （Event 状態機械）
└── AmbiguousDeclarationError                      （effectiveDeclarationFor）
```

**依存**: 標準ライブラリのみ。

**統合パターン**: `U-07 api-orchestration` のグローバルエラーハンドラが `DomainError` を捕捉し、構造化ログへ文脈属性を記録し、利用者には汎用メッセージを返す（申し送り U01-H25、SECURITY-15）。

---

### LC-03: 列挙値の変換表

| 列挙型 | コード上の識別子 | CSV / API の表記 |
|--------|----------------|----------------|
| `Position` | `MANAGER` | 管理職 |
| | `GENERAL` | 一般職 |
| `JobType` | `CLERICAL` | 事務職 |
| | `TECHNICAL` | 技術職 |
| | `NURSERY_TEACHER` | 保育士 |
| | `PUBLIC_HEALTH_NURSE` | 保健師 |
| `Qualification` | `DISASTER_PREVENTION_SPECIALIST` | 防災士 |
| | `EMERGENCY_LIFESAVING_TECHNICIAN` | 救急救命士 |
| `EventType` | `DISASTER_SHELTER_SUPPORT` | 災害時避難所応援 |
| | `ELECTION_ADMINISTRATION` | 選挙事務 |
| | `OTHER` | その他 |
| `EventStatus` | `DRAFT` | 準備中 |
| | `COLLECTING_DECLARATIONS` | 申告受付中 |
| | `OPTIMIZED` | 割当計算済 |
| | `CONFIRMED` | 確定 |
| `ReasonCategory` | `LEAVE` | 休暇 |
| | `CHILD_OR_ELDER_CARE` | 育児・介護 |
| | `HEALTH_CONSIDERATION` | 健康上の配慮 |
| | `OTHER` | その他 |
| `SolverStatus` | `OPTIMAL` / `TIME_LIMIT_REACHED` / `CANCELLED` | （内部用。日本語表記は UI が持つ） |

**依存**: 標準ライブラリのみ。

**統合パターン**:

| 利用者 | 方向 | 用途 |
|-------|------|------|
| **U-03** `A-04 CsvAdapter` | 日本語 → 英語識別子 | CSV インポート |
| **U-03** `A-04 CsvAdapter` | 英語識別子 → 日本語 | CSV エクスポート |
| **U-07** DTO 変換 | 双方向 | API の JSON |

**未知の値は fail closed で拒否する**（SECURITY-15）。`課長補佐` のような変換表にない値が CSV に現れた場合、行番号とともにエラーを報告し、インポート全体をロールバックする。サイレントに `OTHER` へ丸めない。

**変換表を U-01 に置く根拠**: 変換は列挙型自身の性質であり、永続化にも API にも依存しない。U-03 と U-07 が同一の表を使うことで、表記の不整合が起こらない。

**暫定性**: `JobType`, `Position`, `Qualification` の値は暫定である。実際の職種・役職・資格の一覧が提供された時点で更新する（NFR Requirements 決定 8）。

---

### LC-04: ドメイン生成器（テストユーティリティ、PBT-07）

**配置**: `tests/shared-kernel/generators.py`

**PBT-07 の要求**: 「ドメインオブジェクトのカスタム生成器を作成し、業務制約を尊重すること」「生成器の定義を集約し、複数のテストが同じドメイン型を共有する場合は再利用可能にすること」。

| 生成器 | 生成する値が満たす制約 |
|-------|---------------------|
| `gen_coordinates()` | 緯度 `[-90, 90]`、経度 `[-180, 180]`。境界値（±90, ±180, 0）を含む |
| `gen_school_district()` | 妥当な `Coordinates` を持つ |
| `gen_staff()` | 職種 1、役職 1、資格 0 個以上。既存の `DepartmentId`, `SchoolDistrictId` を参照する |
| `gen_facility()` | 資格別必要人数の合計 ≤ 必要人数（BR-03） |
| `gen_availability_declaration()` | `isAvailable = false` なら `reason_category` が非 `None`。`reason_category = OTHER` なら `other_reason_note` が非 `None`（BR-05） |
| `gen_objective_weights()` | 全重みが非負、少なくとも 1 つが正（BR-02） |
| `gen_travel_parameters()` | `detour_factor >= 1.0`, `average_speed_kmh > 0`（BR-04） |
| `gen_assignment_problem()` | 上記を組み合わせ、構造的に妥当な問題を生成する |

**依存**: `hypothesis`（テスト時のみ）。**プロダクションコードは `hypothesis` に依存しない。**

**利用者**: U-02 〜 U-07 のすべてのプロパティベーステスト。

**PBT-07 が禁じること**: 「ドメイン型のパラメータに、生の primitive 生成器（`st.integers()` 単独など）のみを使ってはならない」。上記 8 種を用いることで、業務制約を満たさない無意味なテストケースの生成を避ける。

**設計上の含意**: `gen_facility()` が BR-03 を満たす値のみを生成するため、「資格別必要人数の合計が必要人数を超える施設」は**生成されない**。この制約の**違反**をテストするには、専用の否定的生成器を別途用意する（`gen_invalid_facility()`）。これは Code Generation ステージで実装する。

---

## 3. 論理コンポーネント間の依存

```text
  LC-01 ドメイン型
     |
     |  生成時バリデーション失敗で送出する
     v
  LC-02 例外階層
     ^
     |
  LC-03 列挙値の変換表（未知の値で例外を送出する）


  LC-04 ドメイン生成器（テスト時のみ）
     |
     |  生成する
     v
  LC-01 ドメイン型
```

**循環依存はない。** LC-01 は LC-02 に依存する（例外を送出するため）。LC-02 は何にも依存しない。LC-03 は LC-01（列挙型）と LC-02（例外）に依存する。LC-04 はテスト時のみ存在し、プロダクションコードから参照されない。

---

## 4. 他ユニットのインフラコンポーネントとの関係

U-01 はインフラコンポーネントを持たないが、他ユニットのインフラコンポーネントは U-01 の型を**運ぶ**。

| 他ユニットのコンポーネント | 運ぶ U-01 の型 | 備考 |
|------------------------|--------------|------|
| **U-03** DB 接続（`A-02 PersistenceAdapter`） | 全エンティティ | frozen であるため、ORM のダーティチェックを使えない（申し送り U01-H21） |
| **U-02/U-03** 距離キャッシュ（`P-03`） | `SchoolDistrictId`, `Kilometers` | キーは `(min(id), max(id))` に正規化する（U01-H1） |
| **U-04** ジョブキュー（`P-05 JobStorePort`） | `AssignmentProblem`, `AssignmentResult` | ジョブ状態は DB に永続化される。frozen 型の直列化が必要 |
| **U-06** 監査ログ（`P-04 AuditLogPort`） | `StaffId`, `EventId`, `FacilityId` **のみ** | **`Staff` エンティティ全体は運ばない。** これが個人情報の流出を構造的に防ぐ（NFR-U01-R03） |
| **U-07** HTTP（`A-01 RestApiAdapter`） | 全エンティティ（DTO 経由） | Pydantic DTO ↔ ドメイン型の変換（申し送り U01-H23） |

### 4.1 直列化に関する申し送り（新規）

`U-04` のジョブキューは、`AssignmentProblem` と `AssignmentResult` を DB に永続化する。frozen dataclass の直列化・復元が必要になる。

**復元時に `__post_init__` が再実行される**ため、DB に不正なデータが混入していれば、その時点で例外が送出される（fail closed）。これは望ましい挙動である。

**新たな申し送り（U01-H26）**: `U-04` は frozen dataclass の直列化方式を決定すること。復元時に生成時バリデーションが働くことを確認すること。

---

## 5. まとめ

| 項目 | U-01 の状態 |
|------|-----------|
| インフラコンポーネント | **持たない**（ジョブキュー、キャッシュ、サーキットブレーカ、ブローカ、セッションストア、接続プールのいずれも） |
| 論理コンポーネント | 4 種（ドメイン型、例外階層、列挙値変換表、ドメイン生成器） |
| プロダクションコードの依存 | **標準ライブラリのみ** |
| テストコードの依存 | `hypothesis`, `pytest` |
| 循環依存 | **なし** |

**U-01 が標準ライブラリのみに依存することが、6 ユニットが安全に U-01 を共有できる理由である。**
