# ビジネスロジックモデル — U-01 `shared-kernel`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - Functional Design（ユニット 1 / 8）

---

## 1. このユニットの本質

**U-01 は、ビジネスロジックを持たないユニットである。**

これは欠陥ではなく、意図した設計である。U-01 は依存グラフの根であり、他の 7 ユニットすべてが依存する。ここにビジネスロジックが混入すると、以下が起こる。

- ロジックの変更が全ユニットの再テストを要求する
- 「どのユニットがこのルールを所有しているか」が曖昧になる
- ユニット間の責務分割が形骸化する

したがって U-01 が持つのは、**型の定義**と、**型が成立するための最小限の規則**（生成時バリデーション）、そして**唯一の振る舞い**（`effectiveDeclarationFor`）のみである。

---

## 2. U-01 が持つ唯一の振る舞い: `effectiveDeclarationFor()`

### 2.1 なぜこれだけが U-01 に属するのか

`AvailabilityDeclaration` は `(staffId, eventId, declaredAt)` で識別される。同一の `(staffId, eventId)` に対して複数の申告が履歴として残る（US-12、再申告）。

**「どの申告が有効か」は、エンティティの識別そのものに関わる問い**である。永続化の方法にも、最適化にも、UI にも依存しない。したがってこれは U-01 の責務である。

これを U-03 `data-management` に置くと、U-04 や U-05 が「有効な申告」を得るために U-03 に依存することになり、依存グラフが不必要に複雑になる。

### 2.2 処理フロー

```text
effectiveDeclarationFor(staffId, eventId, history):

    matching = history.filter(d => d.staffId == staffId && d.eventId == eventId)

    if matching.isEmpty():
        return None                       // 未申告。従事可能とはみなさない

    maxDeclaredAt = max(matching.map(d => d.declaredAt))
    candidates    = matching.filter(d => d.declaredAt == maxDeclaredAt)

    if candidates.size() > 1:
        raise AmbiguousDeclarationError    // 同時刻の申告が複数。fail closed

    return candidates[0]
```

### 2.3 3 つの返り値の意味

| 返り値 | 意味 | 最適化での扱い |
|-------|------|--------------|
| `None` | **未申告** | 最適化の対象に**含めない** |
| `AvailabilityDeclaration(isAvailable = true)` | 従事可能と申告した | 最適化の対象に**含める**（FR-04.1） |
| `AvailabilityDeclaration(isAvailable = false)` | 従事不可と申告した | 最適化の対象に**含めない**（制約 C4） |

**「未申告」と「従事不可」は区別される。** 両者とも最適化の対象外だが、業務上の意味が異なる。

- **未申告**: まだ回答していない。担当者は督促すべきである
- **従事不可**: 明示的に不可と回答した。休暇・育児介護・健康上の配慮がある

**U-03 への申し送り（U01-H10）**: `getSufficiencyStatus()`（US-13）は、この 3 分類で集計しなければならない。「従事可能 250 名 / 従事不可 30 名 / 未申告 70 名」と提示することで、担当者は「70 名の督促で充足するかもしれない」と判断できる。単に「不足 20 名」とだけ表示するより、行動につながる情報になる。

---

## 3. 他ユニットが U-01 の型をどう利用するか

```text
                    +-------------------------+
                    |   U-01 shared-kernel    |
                    |   型定義のみ            |
                    +-------------------------+
                       |    |    |    |    |
      +----------------+    |    |    |    +----------------+
      |                     |    |    |                     |
      v                     v    |    v                     v
+-------------+  +----------------+  +----------------+  +-------------+
| U-02        |  | U-03           |  | U-04           |  | U-06        |
| distance-   |  | data-          |  | optimization-  |  | security    |
| cost        |  | management     |  | engine         |  |             |
+-------------+  +----------------+  +----------------+  +-------------+
      |                  |                   |                  |
      | Coordinates      | 全エンティティ    | Assignment       | StaffId
      | TravelMetrics    | の永続化          | Problem          | EventId
      | TravelParameters | AvailabilityDecl  | AssignmentResult | （監査ログ用）
      |                  | の履歴管理        | ObjectiveWeights |
      |                  |                   | ConstraintViol.  |
      v                  v                   v                  v
   純粋関数の         トランザクション     制約検証と         個人情報を
   入出力型           境界での型           最適化の型         含まない ID のみ
```

| ユニット | U-01 から利用する主な型 | 用途 |
|---------|---------------------|------|
| **U-02** distance-cost | `Coordinates`, `TravelMetrics`, `TravelParameters`, `SchoolDistrict` | 純粋関数の入出力 |
| **U-03** data-management | 全エンティティ | 永続化と CSV 変換の対象 |
| **U-04** optimization-engine | `AssignmentProblem`, `AssignmentResult`, `ObjectiveWeights`, `ConstraintViolation`, `OptimizationParameters` | 制約検証、診断、最適化 |
| **U-05** comparison-report | `HistoricalRecord`, `Assignment`, `TravelMetrics` | ベースライン再現と比較 |
| **U-06** security | `StaffId`, `EventId`, `FacilityId` のみ | 監査ログの記録。**エンティティ全体は参照しない**（個人情報を扱わないため） |
| **U-07** api-orchestration | 全エンティティ | REST API の入出力（DTO へ変換する） |

### 3.1 U-06 が ID しか使わないことの意味

`U-06 security` は `Staff` エンティティ全体を参照しない。監査ログには職員 ID のみを記録するため（SECURITY-03、NFR-S02）、`Staff.name` や `Staff.residenceDistrictId` にアクセスする必要がない。

**この依存の狭さが、個人情報のログ流出を構造的に防ぐ。** U-06 のコードから `Staff.name` を読む経路が存在しない。

---

## 4. U-01 にビジネスロジックを持ち込まないための境界

以下は **U-01 に置いてはならない**。それぞれの正しい所有ユニットを示す。

| 誤って U-01 に置きたくなるもの | 正しい所有ユニット | 理由 |
|---------------------------|-----------------|------|
| `Staff.distanceTo(Facility)` | **U-02** distance-cost | 距離算出は `TravelParameters` を要する。エンティティが計算方法を知るべきではない |
| `AssignmentResult.isValid()` | **U-04** optimization-engine | 制約 C1〜C5 の検証は `ConstraintValidator` の責務。問題全体の文脈を要する |
| `Event.canBeDeleted()` | **U-03** data-management | 削除可否は永続化された割当結果の有無に依存する。`S-01 EventService` が判断する |
| `Facility.isSatisfiedBy(staff[])` | **U-04** optimization-engine | C3 の検証。`ConstraintValidator` の責務 |
| `AvailabilityDeclaration.save()` | **U-03** data-management | 永続化は `P-02 RepositoryPort` の責務。エンティティが DB を知るべきではない |
| `ObjectiveWeights.normalize()` | **U-04** optimization-engine | 正規化は目的関数の定式化に属する |

### 4.1 判定基準

**U-01 に置いてよいのは、次の 2 条件を**両方**満たすものだけである。**

1. **その型自身の内部状態のみで完結する**（他のエンティティやパラメータを要しない）
2. **その型が「存在してよいか」を決める**（識別、または生成時の妥当性）

`effectiveDeclarationFor()` は、条件 1 を満たす（申告の履歴のみを見る）。条件 2 も満たす（どの申告が「有効に存在する」かを決める）。したがって U-01 に属する。

`Staff.distanceTo(Facility)` は条件 1 に違反する（`TravelParameters` と `SchoolDistrict` を要する）。したがって U-01 に属さない。

---

## 5. 状態機械: `Event.status`

`Event` のステータスは状態機械である。**遷移規則の定義は U-01 が持つが、遷移の実行と事前条件の検証は `S-01 EventService`（U-03）が担う。**

| 責務 | 所有ユニット |
|------|------------|
| どの状態が存在するか（`Draft`, `CollectingDeclarations`, `Optimized`, `Confirmed`） | **U-01** |
| どの遷移が許可されるか（遷移表） | **U-01** |
| 遷移の事前条件の検証（例:「施設が 1 件以上登録されているか」） | **U-03** |
| 遷移の実行と永続化 | **U-03** |
| 遷移の監査ログ記録 | **U-06** |

**根拠**: 「施設が 1 件以上登録されているか」の検証には `FacilityRepository` が必要であり、U-01 は永続化を知らない。一方、「`Confirmed` から `Draft` へは戻れない」という規則は、型のみで表現できる。

**U-03 への申し送り（U01-H13）**: `Optimized` → `CollectingDeclarations` の再開遷移（`reopenDeclarations()`）を実装すること。US-24（追加申告後の再最適化）がこれを要求する。

---

## 6. データフロー: U-01 の型が流れる経路

### 6.1 従事可否申告の登録から最適化まで

```text
  CSV ファイル
       |
       |  U-03: A-04 CsvAdapter.parse()
       v
  Row[]（生の行データ）
       |
       |  U-03: S-03 AvailabilityService
       |    - 職員 ID の存在検証
       |    - declaredAt の一意性保証（U01-H11）
       |    - BR-05 の生成時バリデーション
       v
  AvailabilityDeclaration[]   <--- U-01 の型
       |
       |  U-03: P-02 AvailabilityRepository.saveAll()（トランザクション）
       v
  永続化
       |
       |  U-04: S-04 OptimizationService.startOptimization()
       |    - AvailabilityRepository.findEffectiveByEvent(eventId)
       |    - U-01: effectiveDeclarationFor() で有効な申告を特定
       |    - isAvailable = true の職員のみを抽出（FR-04.1）
       v
  availableStaff: Staff[]     <--- U-01 の型
       |
       |  U-04: AssignmentProblem を構成
       v
  AssignmentProblem           <--- U-01 の型
       |
       |  U-04: P-01 SolverPort.solve()
       v
  AssignmentResult            <--- U-01 の型
       |
       |  BR-07 の生成時バリデーション
       |    - violations に C3 以外が含まれないこと
       |    - objectiveValue が有限かつ非負であること（INV-06）
       v
  永続化 / UI 表示
```

**要点**: `AssignmentResult` の生成時バリデーション（BR-07）が、**ソルバーのバグを下流へ伝播させない防波堤**として機能する。ソルバーが誤って C1 違反を含む結果を返した場合、型の生成が拒否され、その場で失敗する（fail closed）。

---

## 7. Testable Properties の要約（PBT-01）

詳細は `domain-entities.md` セクション 7 を参照。U-01 は 8 件のプロパティ（P-01〜P-08）を持つ。

**最も重要なのは P-01 と P-02** である。`effectiveDeclarationFor()` は U-01 唯一の振る舞いであり、その正しさが最適化の対象職員集合を決める。誤れば、休暇中の職員が災害時に派遣されうる。

| プロパティ | 分類 | 重要度 |
|-----------|------|:------:|
| P-01 有効な申告はちょうど 1 件（最大の `declaredAt`） | Invariant | **最高** |
| P-02 `effectiveDeclarationFor()` は冪等 | Idempotence | 高 |
| P-03 `Coordinates` の範囲検証 | Range constraint | 中 |
| P-04 `ObjectiveWeights` の非負性と非ゼロ性 | Range constraint | 中 |
| P-05 `Facility` の資格別必要人数の合計 ≤ 必要人数 | Invariant | 中 |
| P-06 `Assignment` の一意性（INV-01 の型レベル保証） | Invariant | 高 |
| P-07 `violations` に C3 以外が現れない | Invariant | **高** |
| P-08 `TravelParameters` の範囲検証 | Range constraint | 中 |

**P-07 の重要性**: これは「最適化エンジンが C1, C2, C4, C5 を決して緩和しない」という業務ルール（FR-04.5）を、**型の生成時に検証する**プロパティである。U-04 のバグを U-01 が捕捉する。

---

## 8. 次ステージ（NFR Requirements）への入力

| 決定事項 | 内容 |
|---------|------|
| **技術スタック（バックエンド全体）** | 言語、フレームワーク、DB。U-01 の NFR Requirements で決定し、U-02〜U-07 を拘束する |
| **PBT フレームワーク（バックエンド）** | PBT-09。申し送り H-4 |
| **エラー処理の方式** | 例外を投げるか、結果型（`Result<T, E>`）を返すか。申し送り U01-H14 |
| **列挙値の確定** | `JobType`, `Position`, `Qualification` の具体値。申し送り U01-H9 |
| **数値型の実装** | `Real` を倍精度浮動小数点とするか、任意精度十進数とするか。`costYen` の集計精度に影響する |

**注意**: 本システムはモノリスであり、バックエンドの全ユニットが同一の実行環境を共有する。**U-01 の NFR Requirements ステージがバックエンド全体の技術基盤を決める。** この決定は後続 6 ユニットを拘束するため、慎重な検討と明示的な承認を要する。
