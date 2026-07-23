# ビジネスルール — U-01 `shared-kernel`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - Functional Design（ユニット 1 / 8）

---

## 0. 本文書の範囲

U-01 は**型基盤**であり、業務上の意思決定ロジックを持たない。したがって本文書が定めるのは以下に限られる。

1. **生成時バリデーション** — 不正な値を持つオブジェクトを、そもそも生成させないルール
2. **`Event` のステータス遷移規則**
3. **`effectiveDeclarationFor()` のルール** — U-01 が持つ唯一の振る舞い
4. **エラー処理の方針**

制約 C1〜C5 の検証（`ConstraintValidator`）、実行不可能性の診断（`InfeasibilityDiagnoser`）、最適化の定式化は **U-04 optimization-engine** の責務である。距離・費用の算出ルールは **U-02 distance-cost** の責務である。

---

## 1. 生成時バリデーション（fail closed / SECURITY-15）

**原則**: 不変条件を満たさない値オブジェクト・エンティティは、**生成そのものを拒否する**。生成後に検証するのではない。これにより、後続ユニットは「型が存在する = 不変条件が成立している」と仮定できる。

エラー時は必ず拒否側に倒す（fail closed）。部分的に構築されたオブジェクトを返してはならない。

---

### BR-01: `Coordinates` の生成

| 条件 | 判定 |
|------|------|
| `-90 <= latitude <= 90` かつ `-180 <= longitude <= 180` | 生成する |
| 上記以外 | **生成を拒否する**（`InvalidCoordinatesError`） |
| `latitude` または `longitude` が NaN または無限大 | **生成を拒否する** |

**根拠**: US-09 の受入基準「緯度 95.0 の行が含まれる場合、バリデーションエラーとなりインポート全体をロールバックする」。
**プロパティ**: P-03

---

### BR-02: `ObjectiveWeights` の生成

| 条件 | 判定 |
|------|------|
| `travelTime >= 0` かつ `travelCost >= 0` かつ `inequity >= 0` かつ、**少なくとも 1 つが正** | 生成する |
| すべての重みが 0 | **生成を拒否する**（`AllWeightsZeroError`） |
| いずれかの重みが負 | **生成を拒否する**（`NegativeWeightError`） |

**根拠**: すべての重みが 0 の場合、目的関数が定数となり最適化が意味を失う（US-17）。
**プロパティ**: P-04

---

### BR-03: `Facility` の生成

| 条件 | 判定 |
|------|------|
| `requiredHeadcount >= 1` | |
| `sum(qualificationRequirements[].requiredCount) <= requiredHeadcount` | 生成する |
| 資格別必要人数の合計が必要人数を超える | **生成を拒否する**（`QualificationRequirementExceedsHeadcountError`） |
| 同一の `requirement` が `qualificationRequirements` に重複して現れる | **生成を拒否する**（`DuplicateQualificationRequirementError`） |

**根拠**: US-08 の受入基準「施設 F001 の必要人数が 5 名、うち管理職が 6 名必要と指定されている場合、バリデーションエラーとなる」。
**プロパティ**: P-05

---

### BR-04: `TravelParameters` の生成

| 条件 | 判定 |
|------|------|
| `detourFactor >= 1.0` | 生成する。**1.0 未満は物理的に不合理**（直線距離より短い経路は存在しない） |
| `averageSpeedKmh > 0` | 生成する。0 以下は移動時間が無限大または負になる |
| `unitPricePerKm >= 0` | 生成する |
| `sameDistrictFixedSeconds >= 0` | 生成する |
| 上記のいずれかに違反 | **生成を拒否する**（`InvalidTravelParametersError`） |

**プロパティ**: P-08

---

### BR-05: `AvailabilityDeclaration` の生成

| 条件 | 判定 |
|------|------|
| `isAvailable = true` | `reasonCategory` は `null` でなければならない |
| `isAvailable = false` | `reasonCategory` は非 `null` でなければならない |
| `reasonCategory = Other` | `otherReasonNote` は非 `null` かつ非空でなければならない |
| `reasonCategory != Other` | `otherReasonNote` は `null` でなければならない |
| 上記のいずれかに違反 | **生成を拒否する**（`InconsistentDeclarationError`） |

**根拠**: Q9=A。理由区分を列挙型としつつ、`Other` にのみ自由記述を許す。

---

### BR-06: `Staff` の生成

| 条件 | 判定 |
|------|------|
| `jobType` は 1 つ、`position` は 1 つ | 型により保証される（Q8=A） |
| `qualifications` は集合（重複なし）。空集合を許す | 型により保証される |
| `name` が空文字列 | **生成を拒否する** |

---

### BR-07: `AssignmentResult` の生成

| 条件 | 判定 |
|------|------|
| `objectiveValue` が有限かつ非負 | 生成する。NaN・無限大・負値は拒否する（INV-06） |
| `0 <= optimalityGap <= 1` | 生成する |
| `violations` に含まれる `constraintId` が `"C3"` のみ | 生成する |
| `violations` に `"C1"`, `"C2"`, `"C4"`, `"C5"` が含まれる | **生成を拒否する**（`NonDemotableConstraintViolationError`） |
| `assignments` に同一 `(eventId, staffId)` が 2 件以上含まれる | **生成を拒否する**（INV-01） |

**根拠**: FR-04.5 により、降格されるのは C3 のみである。他の制約の違反を含む結果は、システムのバグを意味する。**型レベルで拒否することで、バグが下流へ伝播しない。**
**プロパティ**: P-06, P-07

---

## 2. `Event` のステータス遷移規則（Q6=A）

### 2.1 遷移図

```text
   +-----------+
   |   Draft   |  準備中
   +-----------+
        |
        |  startCollectingDeclarations()
        |  条件: 施設が 1 件以上登録されている
        v
   +---------------------------+
   |  CollectingDeclarations   |  申告受付中
   +---------------------------+
        |            ^
        |            |  reopenDeclarations()
        |            |  条件: 割当が確定していない（US-24 の追加申告）
        |            |
        |  markOptimized()
        |  条件: 最適化ジョブが正常に完了した
        v            |
   +-----------+     |
   | Optimized |-----+  割当計算済
   +-----------+
        |
        |  confirm()
        |  条件: 担当者が明示的に確定する
        v
   +-----------+
   | Confirmed |  確定
   +-----------+
        |
        |  （遷移なし。終端状態）
```

### 2.2 遷移規則

| 現在の状態 | 操作 | 遷移先 | 事前条件 |
|-----------|------|--------|---------|
| `Draft` | `startCollectingDeclarations()` | `CollectingDeclarations` | 施設が 1 件以上登録されている |
| `CollectingDeclarations` | `markOptimized()` | `Optimized` | 最適化ジョブが正常に完了した |
| `Optimized` | `reopenDeclarations()` | `CollectingDeclarations` | 追加の従事可否申告を受け付ける（US-24） |
| `Optimized` | `confirm()` | `Confirmed` | 担当者が明示的に確定する |
| `Confirmed` | （なし） | — | **終端状態** |

**上記以外のすべての遷移は禁止する**（`InvalidStateTransitionError`）。

### 2.3 削除の可否（US-06）

| 状態 | 削除 | 根拠 |
|------|:----:|------|
| `Draft` | ○ | 割当結果が存在しない |
| `CollectingDeclarations` | ○ | 削除時、紐づく `AvailabilityDeclaration` も削除する |
| `Optimized` | ○ | 削除時、`AssignmentResult` も削除する |
| `Confirmed` | **×** | US-06「ステータスが『確定』のイベントは削除できない」 |

**削除は必ず監査ログに記録する**（U-06、SECURITY-13）。

### 2.4 `reopenDeclarations()` が必要な理由

US-24（追加申告後の再最適化）では、最適化が完了した後に追加の従事可否申告を登録する。`Optimized` から `CollectingDeclarations` へ戻る遷移がなければ、この業務フローを表現できない。

**注意**: `Confirmed` からは戻れない。確定後に割当を変更するには、イベントを新規に作り直す必要がある。これは意図した設計である（確定した内示を覆さない）。

---

## 3. `effectiveDeclarationFor()` のルール

**U-01 が持つ唯一の振る舞いである。**

### 3.1 仕様

```text
effectiveDeclarationFor(
    staffId: StaffId,
    eventId: EventId,
    history: List<AvailabilityDeclaration>
) -> AvailabilityDeclaration | None
```

**ルール**:

1. `history` から `(staffId, eventId)` に一致する申告を抽出する
2. 該当が 0 件なら `None` を返す（**未申告**。従事可能とはみなさない）
3. 該当が 1 件以上なら、**`declaredAt` が最大のもの**を返す
4. `declaredAt` が同値の申告が複数存在する場合、**エラーとする**（`AmbiguousDeclarationError`）

### 3.2 ルール 2 の重要性（未申告の扱い）

**未申告は「従事不可」でも「従事可能」でもない。`None` である。**

最適化の対象となるのは「**従事可能と明示的に申告した職員**」のみである（FR-04.1）。未申告の職員は対象に含まれない。これは以下の理由による。

- 未申告を「従事可能」とみなすと、休暇中の職員が割り当てられうる（C4 違反、US-16 の受入基準に反する）
- 未申告を「従事不可」とみなすと、単に回答が遅れているだけの職員が最適化から除外される

**したがって、`S-03 AvailabilityService.getSufficiencyStatus()`（U-03）は「従事可能」「従事不可」「未申告」の 3 分類で集計しなければならない。** この点を U-03 へ申し送る。

### 3.3 ルール 4 の重要性（同時刻の申告）

`declaredAt` が同値の申告が 2 件あると、どちらが有効かを決定できない。**曖昧なまま最新の 1 件を選ぶのではなく、エラーとする**（fail closed / SECURITY-15）。

実装上、`declaredAt` にマイクロ秒以上の精度を持たせることで、実際にはほぼ発生しない。ただし CSV 一括インポート（US-11）では同一のタイムスタンプが付与されうるため、**インポート時にタイムスタンプの一意性を保証する責務は U-03 にある**。

### 3.4 プロパティ

- **P-01**（Invariant）: 返される申告はちょうど 1 件であり、それは最大の `declaredAt` を持つ
- **P-02**（Idempotence）: 同一の `history` に対し何度呼んでも同じ結果を返す

---

## 4. エラー処理の方針（SECURITY-15）

### 4.1 fail closed

すべてのバリデーション失敗は、**オブジェクトの生成を拒否する**。部分的に構築されたオブジェクトや、既定値で埋めたオブジェクトを返してはならない。

### 4.2 エラーの型

| エラー | 発生源 |
|-------|-------|
| `InvalidCoordinatesError` | BR-01 |
| `AllWeightsZeroError`, `NegativeWeightError` | BR-02 |
| `QualificationRequirementExceedsHeadcountError`, `DuplicateQualificationRequirementError` | BR-03 |
| `InvalidTravelParametersError` | BR-04 |
| `InconsistentDeclarationError` | BR-05 |
| `NonDemotableConstraintViolationError` | BR-07 |
| `InvalidStateTransitionError` | セクション 2.2 |
| `AmbiguousDeclarationError` | セクション 3.1 ルール 4 |

### 4.3 エラーメッセージに含めてはならない情報（SECURITY-03, SECURITY-09）

- 職員の**氏名**
- 職員の**居住小学校区**
- スタックトレース、内部パス、フレームワークバージョン

エラーメッセージには**職員 ID のみ**を含める。

**例**:
- ✅ `InconsistentDeclarationError: staffId=S001, eventId=E001 — isAvailable=false but reasonCategory is null`
- ❌ `InconsistentDeclarationError: 鈴木太郎（第三小学校区）の申告が不整合です`

### 4.4 U-01 は例外を投げるか、結果型を返すか

**技術非依存の設計として、いずれかを NFR Requirements ステージで決定する。** 本文書は「生成を拒否する」とのみ定める。

どちらを採用する場合も、SECURITY-15 の要求「すべての外部呼び出しに明示的なエラー処理を持つ」「エラー経路が認可や検証を迂回しない」を満たすこと。

---

## 5. 日時の扱い（Q10=A）

| ルール | 内容 |
|-------|------|
| **保持** | すべての `Timestamp` と `Date` は **UTC** で保持する |
| **表示** | 画面表示・CSV エクスポート時に **日本標準時（JST, UTC+9）** へ変換する |
| **入力** | CSV インポート時、日時は JST として解釈し、UTC へ変換して保持する |
| **比較** | `declaredAt` の比較は UTC 上で行う（タイムゾーン変換を経ない） |

**根拠**: タイムゾーンの誤りを防ぐ標準的な手法。監査ログのタイムスタンプも UTC（ISO 8601）で記録する。

**注意**: `Event.scheduledDate` は日付であり時刻を持たない。JST の暦日として解釈する。UTC で保持すると日付がずれうるため、**`scheduledDate` のみは JST の暦日として保持し、時刻成分を持たない型を用いる**。

この例外を明示的に記録する。他のすべての日時は UTC である。

---

## 6. 拡張ルール適合サマリ

### 6.1 Security Compliance（security/baseline — 有効）

| ルール | 判定 | 根拠 |
|--------|------|------|
| SECURITY-03 アプリケーションログ | **適合** | エラーメッセージに氏名・居住小学校区を含めない（セクション 4.3）。`Staff.name` と `residenceDistrictId` を個人情報として明示（申し送り U01-H8） |
| SECURITY-05 入力検証 | **適合** | 全値オブジェクト・エンティティに生成時バリデーションを定義（BR-01〜BR-07）。不正な値を型レベルで排除する |
| SECURITY-09 ハードニング | **適合** | エラーメッセージにスタックトレース・内部パス・フレームワークバージョンを含めない（セクション 4.3） |
| SECURITY-15 例外処理と fail-safe | **適合** | すべてのバリデーション失敗で生成を拒否する（fail closed）。部分構築オブジェクトを返さない（セクション 4.1） |
| SECURITY-01, 02, 04, 06, 07, 08, 10, 11, 12, 13, 14 | **N/A** | U-01 は型定義のみを持ち、永続化・ネットワーク・認証・認可・ログ出力・依存管理のいずれの表出も持たない。これらは U-03, U-06, U-07 および Infrastructure Design / Code Generation で検証する |

**ブロッキング所見: なし**

### 6.2 PBT Compliance（testing/property-based — 有効）

| ルール | 判定 | 根拠 |
|--------|------|------|
| **PBT-01 プロパティ特定** | **適合** | `domain-entities.md` セクション 7 に「Testable Properties」を設け、8 件のプロパティ（P-01〜P-08）を分類付きで列挙した。プロパティを持たないコンポーネントは「No PBT properties identified」と根拠付きで明記した |
| **PBT-07 生成器の品質**（先行準備） | **適合** | 8 種のドメイン生成器を U-01 のテストユーティリティとして定義し、全ユニットから再利用する方針を記録した（申し送り U01-H7） |
| PBT-02 ラウンドトリップ | **N/A** | U-01 は直列化・符号化・解析を持たない。CSV ラウンドトリップ（INV-10）は U-03 の責務 |
| PBT-03 不変条件 | **適合**（先行） | P-01, P-03〜P-08 が該当 |
| PBT-04 冪等性 | **適合** | P-02（`effectiveDeclarationFor` の冪等性） |
| PBT-05 オラクル | **N/A** | 参照実装が存在しない。オラクル検証は U-04 の責務（INV-12） |
| PBT-06 ステートフルテスト | **N/A** | U-01 は可変状態を持たない。`Event` のステータス遷移は状態機械だが、遷移規則の検証は U-03（`S-01 EventService`）が担う |
| PBT-08 シュリンキングと再現性 | **N/A**（Code Generation が対象） | |
| PBT-09 フレームワーク選定 | **N/A**（NFR Requirements が対象、申し送り H-4） | |
| PBT-10 相補的テスト戦略 | **N/A**（Code Generation が対象） | |

**ブロッキング所見: なし**

### 6.3 Resiliency Extension

**スキップ**（Enabled = No。CQ4=A により次フェーズへ延期）。ルールファイルは未ロード。

---

## 7. 本ステージで発見した設計上の論点（後続への申し送り）

| ID | 論点 | 引き渡し先 |
|----|------|-----------|
| **U01-H10** | **「未申告」は「従事不可」ではない。** `getSufficiencyStatus()` は「従事可能」「従事不可」「未申告」の 3 分類で集計しなければならない。未申告を従事不可とみなすと、回答が遅れているだけの職員が最適化から除外される | **U-03** data-management |
| **U01-H11** | CSV 一括インポート時、`declaredAt` の一意性を保証すること。同時刻の申告が 2 件あると `AmbiguousDeclarationError` となる | **U-03** data-management |
| **U01-H12** | `Event.scheduledDate` のみ JST の暦日として保持する（時刻成分を持たない）。他のすべての日時は UTC | **U-03** data-management, **U-07** api-orchestration |
| **U01-H13** | `Event` のステータス遷移規則の検証（許可されない遷移を拒否する）は `S-01 EventService` が担う。`Optimized` → `CollectingDeclarations` の再開遷移を忘れないこと（US-24） | **U-03** data-management |
| **U01-H14** | 例外を投げるか結果型を返すかを決定すること | **U-01** NFR Requirements |
