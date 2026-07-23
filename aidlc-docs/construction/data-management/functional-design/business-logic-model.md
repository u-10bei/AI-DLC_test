# ビジネスロジックモデル — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 3 / 8）

---

## 1. コンポーネント構成

| コンポーネント | 役割 |
|--------------|------|
| **S-01 EventService** | イベントのライフサイクル（登録・編集・削除・ステータス遷移） |
| **S-02 MasterDataService** | 職員・施設・小学校区マスタの CSV インポートと個別修正 |
| **S-03 AvailabilityService** | 従事可否申告の登録・履歴・充足集計 |
| **P-02 RepositoryPort** | エンティティごとのリポジトリインターフェース |
| **P-07 CsvCodecPort** | CSV の解析・直列化 |
| **A-02 PersistenceAdapter** | P-02 と `P-03 DistanceCachePort`（U-02 定義）の実装。マッパ |
| **A-04 CsvAdapter** | P-07 の実装。数式インジェクション無害化（SEC-05 を注入） |

---

## 2. S-02 MasterDataService: CSV インポート（fail closed）

### 2.1 フロー（Q4=A: 全エラー一括報告）

```text
import_xxx(csv_bytes):

  # Phase 1: 解析（トランザクション外）
  rows = CsvCodecPort.parse(csv_bytes, schema)
  if rows is ParseError:
      return [ParseError with line numbers]   # DB は一切触らない

  # Phase 2: 全行を検証（トランザクション外、Q4=A）
  errors = []
  for line_no, row in enumerate(rows, start=2):   # 1 はヘッダ
      errors += validate_row(line_no, row)
      # 型、長さ上限、参照整合性、列挙値の変換（未知の値）、declared_at 重複
  if errors:
      return errors    # 全エラーを行番号付きで返す。DB は一切触らない

  # Phase 3: トランザクション内で一括保存
  with transaction():
      repository.save_all(domain_objects)
      # DB 制約違反（一意制約等）が出たら rollback
  # commit

  # Phase 4: 副作用（小学校区マスタのみ）
  if this is school-district import:
      recompute_distance_cache()   # Q7=A、下記 4 節

  # Phase 5: 監査
  AuditService.record_master_data_change(...)

  return ImportSummary(success_count)
```

### 2.2 検証項目（Phase 2）

| 項目 | 例 | 対応 |
|------|----|----|
| 型 | 緯度が数値でない | 型検査 |
| 長さ上限 | 名前が過大 | SECURITY-05 |
| 参照整合性 | 存在しない小学校区 ID | 既存 ID との照合 |
| 列挙値の変換 | `課長補佐`（未知の役職） | `from_japanese` が `UnknownEnumValueError`（U01-H24） |
| ドメイン不変条件 | 緯度 95.0、資格別必要人数 > 定員 | ドメイン型の `__post_init__` |
| `declared_at` 重複 | 同一 CSV 内の重複 | U01-H11、下記 3 節 |

### 2.3 原子性（INV: 失敗時に DB が不変）

Phase 1・2 のエラーでは DB を一切触らない。Phase 3 でエラーが出れば `rollback`。**インポートが失敗した場合、DB の状態はインポート前と完全に同一である**（US-07、SECURITY-15）。

### 2.4 個別修正（US-10）

- インポート済みデータを個別に追加・修正・削除する
- **frozen 型のため、修正は新インスタンスの構築である**（U01-H21）。`replace(staff, residence_district_id=...)` で新しい `Staff` を作り、リポジトリで UPDATE する
- 修正を監査ログに記録する（SECURITY-13）
- 割当に使用中の施設は削除できない（US-10）

---

## 3. S-03 AvailabilityService: 従事可否申告

### 3.1 登録（US-11、Q2=A）

```text
import_declarations(event_id, csv_bytes):
  # Phase 2 の検証に追加:
  #  - 職員 ID が職員マスタに存在すること
  #  - 同一 CSV 内で (staff_id, declared_at) が重複しないこと（U01-H11）
  # Phase 3:
  #  - 単一テーブルに追記（Q2=A）
  #  - DB の UNIQUE(staff_id, event_id, declared_at) が二重の防御（Q3=A）
```

### 3.2 有効な申告の取得

`(staff_id, event_id)` ごとに `declared_at` が最大の行を返す。これは U-01 の `effective_declaration_for` の DB 版である。

```sql
-- 各 (staff, event) の最新行（SQLite / PostgreSQL 両対応）
SELECT * FROM availability_declarations d1
WHERE declared_at = (
  SELECT MAX(declared_at) FROM availability_declarations d2
  WHERE d2.staff_id = d1.staff_id AND d2.event_id = d1.event_id
)
```

**UNIQUE 制約（Q3=A）により、最新 `declared_at` を持つ行はちょうど 1 つ**であることが保証される。U-01 の `AmbiguousDeclarationError` に相当する状態は、DB レベルで発生しない。

### 3.3 再申告と履歴（US-12）

- 再申告は、同一 `(staff_id, event_id)` に新しい `declared_at` の行を追記する
- 過去の行は削除しない（履歴として残る）
- 履歴の取得は `(staff_id, event_id)` の全行を `declared_at` 降順で返す

### 3.4 充足状況の集計（US-13、U01-H10、Q8=A）

**3 分類で集計する。「未申告」を漏らさない。**

```text
get_sufficiency_status(event_id):
  all_staff        = staff マスタ全体（Q8=A の母集合）
  declarations     = event_id の有効な申告
  available_ids    = {d.staff_id for d in declarations if d.is_available}
  unavailable_ids  = {d.staff_id for d in declarations if not d.is_available}
  undeclared_ids   = all_staff - available_ids - unavailable_ids

  required_total   = sum(f.required_headcount for f in facilities of event)

  return SufficiencyStatus(
      available   = len(available_ids),
      unavailable = len(unavailable_ids),
      undeclared  = len(undeclared_ids),
      required    = required_total,
      shortage    = max(0, required_total - len(available_ids)),
  )
```

**不変条件**: `available + unavailable + undeclared == len(all_staff)`（3 分類が全職員を分割する）。

**この 3 分類が業務判断を変える。** 「不足 20 名」だけでなく「従事可能 250 / 従事不可 30 / 未申告 70」と示すことで、担当者は「未申告 70 名を督促すれば充足するかもしれない」と判断できる（U01-H10）。

---

## 4. 距離キャッシュの再計算（Q7=A、U02-H10）

```text
recompute_distance_cache():
  # 小学校区マスタの変更トランザクションのコミット後に呼ぶ
  districts = SchoolDistrictRepository.find_all()
  entries   = distance_cost.compute_district_distance_matrix(districts)  # U-02 の純粋関数
  with transaction():
      DistanceCachePort.invalidate_all()
      DistanceCachePort.put_distances(entries)
```

- **全再計算**（Q7=A）。校区数は最大 200 で 1 秒未満（U-02 で確定）
- キャッシュには**大円距離のみ**を保存（U02-H4）。迂回係数の変更では無効化しない
- キーは `(min(id), max(id))` に正規化（U02-H3）。`compute_district_distance_matrix` が正規化済みのエントリを返す

**起動契機**: 小学校区マスタのインポート（US-09）と個別修正（US-10）のコミット後のみ。職員・施設マスタの変更では起動しない。

---

## 5. S-01 EventService: ステータス遷移と削除（U01-H13、Q5=A）

### 5.1 ステータス遷移

- 遷移の実行は U-01 の `Event.transition_to()` を呼ぶ（型が遷移規則を保証）
- **事前条件の検証は S-01 が行う**（U01-H13）。例: `Draft → CollectingDeclarations` は「施設が 1 件以上登録されている」ことを確認する
- **`Optimized → CollectingDeclarations` の再開遷移を実装する**（US-24、U01-H13）。追加申告のため
- すべての遷移を監査ログに記録する

### 5.2 削除（Q5=A）

| 状態 | 削除 |
|------|:----:|
| `Draft`, `CollectingDeclarations`, `Optimized` | 可能。**ON DELETE CASCADE** で申告・割当・実績を連鎖削除 |
| `Confirmed` | **不可**（US-06） |

削除操作を監査ログに記録する（SECURITY-13）。

---

## 6. トランザクション境界

| 操作 | トランザクション境界 |
|------|-------------------|
| CSV インポート | **全体が 1 トランザクション**（原子性、fail closed） |
| 距離キャッシュの再計算 | invalidate + put が 1 トランザクション。**マスタ更新トランザクションのコミット後**に別トランザクションで実行 |
| 個別修正 | 単一操作 |
| 監査ログ | **業務トランザクションの外側**（U-06、SECURITY-14。業務がロールバックされても記録は残る） |

---

## 7. Testable Properties（PBT-01、**ブロッキング制約**）

| ID | プロパティ | 分類 |
|----|-----------|------|
| **INV-10a** | CSV エクスポート → インポートのラウンドトリップ（マスタ）: `import(export(data)) == data` | Round-trip（PBT-02） |
| **INV-10b** | 距離キャッシュのラウンドトリップ: `put(entries); get(a,b)` が保存値を返す | Round-trip（PBT-02） |
| **P-DM01** | CSV インポートの原子性: 1 行でもエラーがあれば、DB の状態はインポート前と完全に同一 | Invariant |
| **P-DM02** | 有効な申告の一意性: 各 `(staff, event)` に対し、取得される有効な申告はちょうど 1 件（最新 `declared_at`） | Invariant |
| **P-DM03** | 充足の 3 分類が全職員を分割: `available + unavailable + undeclared == len(all_staff)` | Invariant |
| **P-DM04** | 距離キャッシュのキー正規化: `get(a,b) == get(b,a)`（DB レベル） | Commutativity |
| **P-DM05** | マッパのラウンドトリップ: `row_to_domain(domain_to_row(x)) == x` | Round-trip |

### 7.1 ステートフルテスト（PBT-06）の評価

**`Event` のステータス遷移はステートフルテストの対象である。**

`Event` は状態機械（`Draft → CollectingDeclarations → Optimized → Confirmed`、`Optimized → CollectingDeclarations` の再開）を持つ。Hypothesis の `RuleBasedStateMachine` で、ランダムな遷移列を生成し、以下を検証する。

- 許可されない遷移は常に拒否される
- `Confirmed` は終端（そこから遷移できない）
- 各遷移後、DB の状態とドメインモデルの状態が一致する

**S-01 EventService が状態機械を扱うため、U-03 のステートフルテストとして実装する**（U-01 Functional Design で予告済み）。

### 7.2 個人情報を扱うことへの配慮

U-03 は**職員の氏名と居住小学校区（個人情報）を保存する**。しかし:

- **エラー報告・ログに個人情報を含めない**（職員 ID のみ、SECURITY-03）
- CSV エクスポートには氏名が含まれるが、これは業務上必要な出力である
- 保存は暗号化ボリューム上（shared-infrastructure.md、SECURITY-01）

---

## 8. 後続への申し送り

セクション 7 のプロパティと、`domain-entities.md` セクション 7 の申し送り（U03-H1〜H4）を引き継ぐ。本ステージで新規の申し送りは以下。

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U03-H5（新規）** | `A-04 CsvAdapter` は、CSV エクスポート時に `SEC-05.sanitize_csv_cell()`（U-06）を**引数として受け取る**（依存性注入）。U-03 は U-06 に依存しない。注入は U-07 が行う（Units Generation の MU-02 解決策） | U-06, U-07 |
| **U03-H6（新規）** | 有効な申告を取得する SQL は、SQLite と PostgreSQL の両方で動作すること。ウィンドウ関数を使う場合は両対応を確認する | U-03 Code Generation |
