# コンポーネントメソッド（Component Methods）

**作成日**: 2026-07-09
**ステージ**: INCEPTION - Application Design

---

## 表記について

- 型は**言語非依存の擬似記法**で示す。技術スタックは NFR Requirements ステージで決定する（Q12=D）
- `Result<T, E>` は成功値 `T` または失敗値 `E` を返すことを示す。例外を投げるか戻り値で返すかは実装言語に委ねる
- **本ステージで定義するのはシグネチャと高レベルな目的のみである。詳細なビジネスルールは Functional Design（CONSTRUCTION フェーズ、ユニットごと）で定義する**

---

## 1. ドメイン層

### C-01: DistanceCostCalculator

**すべて純粋関数**（NFR-M02）。副作用なし、外部依存なし。

```text
haversineDistanceKm(a: Coordinates, b: Coordinates) -> Kilometers
  目的: 2 点間の大円距離を算出する
  不変条件: INV-07（対称性）, INV-08（非負性）

actualTravelDistanceKm(straightLineKm: Kilometers, detourFactor: Ratio) -> Kilometers
  目的: 直線距離に迂回係数を乗じて実移動距離を近似する
  不変条件: INV-09（迂回係数の単調性）

travelTimeMinutes(
    fromDistrict: SchoolDistrictId,
    toDistrict:   SchoolDistrictId,
    distanceKm:   Kilometers,
    params:       TravelParameters
) -> Minutes
  目的: 実移動距離と平均移動速度から移動時間を算出する
  ビジネスルール: fromDistrict == toDistrict のとき、params.sameDistrictFixedMinutes を返す（FR-03.4）
  不変条件: INV-08（同一校区は固定値。距離 0 として扱わない）

travelCostYen(distanceKm: Kilometers, unitPricePerKm: Yen) -> Yen
  目的: 実移動距離に距離単価を乗じて移動費用を算出する
  不変条件: 移動距離に対して単調非減少
  留意: A-04（線形費用モデル）。Functional Design で距離帯モデルへの拡張を再検討する（申し送り H-1）

computeTravelMetrics(
    fromDistrict: SchoolDistrict,
    toDistrict:   SchoolDistrict,
    params:       TravelParameters
) -> TravelMetrics    // { distanceKm, timeMinutes, costYen }
  目的: 上記を組み合わせ、距離・時間・費用をまとめて返す
```

---

### C-02: AssignmentDomainModel

エンティティと値オブジェクトの定義。振る舞いは最小限に留める。

```text
// --- エンティティ ---
Event                   { id, type, name, scheduledDate, status }
Staff                   { id, name, departmentId, jobType, position, qualifications[], residenceDistrictId }
Facility                { id, name, districtId, requiredHeadcount, qualificationRequirements[] }
SchoolDistrict          { id, name, representativeCoordinates }
AvailabilityDeclaration { staffId, eventId, isAvailable, reasonCategory, declaredAt }
Assignment              { staffId, facilityId, isPinned }
AssignmentResult        { eventId, assignments[], objectiveValue, optimalityGap, violations[] }
HistoricalRecord        { eventId, actualAssignments[], availabilityDeclarations[] }

// --- 値オブジェクト ---
Coordinates             { latitude, longitude }
TravelMetrics           { distanceKm, timeMinutes, costYen }
ObjectiveWeights        { travelTime, travelCost, inequity }
TravelParameters        { detourFactor, averageSpeedKmh, unitPricePerKm, sameDistrictFixedMinutes }
OptimizationParameters  { weights, timeLimitSeconds, departmentCapLimit, allowC3Demotion }

// --- 問題の構成 ---
AssignmentProblem {
    event:              Event
    facilities:         Facility[]
    availableStaff:     Staff[]        // 従事可能と申告した職員のみ（FR-04.1）
    travelMatrix:       TravelMetrics[staffId][facilityId]
    pinnedAssignments:  Assignment[]
    parameters:         OptimizationParameters
}

// --- 唯一の重要な振る舞い ---
AvailabilityDeclaration.effectiveDeclarationFor(staffId, eventId, history[]) -> AvailabilityDeclaration
  目的: 同一の（職員, イベント）に対する複数の申告のうち、最新のものを有効な申告として返す
  不変条件: 有効な申告はちょうど 1 件（US-12）
```

---

### C-03: ConstraintValidator

**すべて純粋関数。** 副作用なし。

```text
validate(assignments: Assignment[], problem: AssignmentProblem) -> ConstraintViolation[]
  目的: 割当がハード制約 C1〜C5 を満たすかを検証し、違反を構造化して返す
  戻り値が空配列 = 全制約を満たす
  不変条件: INV-01〜INV-04

validateSingleChange(
    current:    Assignment[],
    change:     AssignmentChange,   // { staffId, fromFacilityId, toFacilityId }
    problem:    AssignmentProblem
) -> ConstraintViolation[]
  目的: 手動修正の直前に、その変更が生む違反を即座に検出する（US-22, FR-06.3）

validatePins(pins: Assignment[], problem: AssignmentProblem) -> ConstraintViolation[]
  目的: ピン留めがハード制約に違反しないかを検証する（US-23, FR-06.4）
  ビジネスルール: 違反がある場合、呼び出し元は再最適化を実行してはならず、エラーを返す

softConstraintPenalty(assignments: Assignment[], problem: AssignmentProblem) -> Penalty
  目的: ソフト制約 S1（従事履歴の平準化）の違反ペナルティを算出する

// --- 型 ---
ConstraintViolation { constraintId: "C1"|"C2"|"C3"|"C4"|"C5", facilityId?, staffId?, detail, severity }
```

---

### C-04: InfeasibilityDiagnoser

**すべて純粋関数。** 副作用なし。FR-04.5 の中核。

```text
diagnose(problem: AssignmentProblem) -> Diagnosis
  目的: 最適化が実行不可能である原因を診断し、取るべき措置を返す

// --- 診断結果 ---
Diagnosis =
  | Feasible
        // 制約を満たす解が存在する見込みである

  | TotalHeadcountShortage {
        shortageCount:      Integer          // 不足人数
        unfilledFacilities: FacilityId[]     // 不足している施設
        recommendedAction:  RequestAdditionalDeclarations
    }
        // 従事可能職員の総数 < 必要人数の総和
        // ビジネスルール: C1（定員充足）を決して緩和しない。定員割れの解を返してはならない（US-18）
        // 不変条件: INV-02

  | QualificationShortageOnly {
        shortfalls:        QualificationShortfall[]   // { facilityId, qualification, shortageCount }
        recommendedAction: DemoteC3WithBigMPenalty
    }
        // 総数は足りているが、特定施設の資格要件（C3）を満たす職員が足りない
        // ビジネスルール: C3 のみをソフト制約に降格し、ビッグMペナルティを課す（CQ1=B, CQ2=C）
        // 不変条件: INV-12（C3 を満たす実行可能解が存在するなら必ずそれが選ばれる）

  | OtherConstraintInfeasible {
        constraintIds:     ("C2"|"C4"|"C5")[]
        recommendedAction: ReportCauseOnly
    }
        // C2 は物理的に降格不可能。C4 の降格は休暇中・健康配慮が必要な職員の派遣を意味する。
        // C5 の降格は部署の業務停止を意味する。いずれも降格しない。

sufficiencyStatus(problem: AssignmentProblem) -> SufficiencyStatus
  目的: 最適化を実行する前に、充足状況（充足 / 余剰 N 名 / 不足 N 名）を返す（US-13）
```

---

### C-05: ComparisonAnalyzer

**すべて純粋関数。** **最適化ロジックを持たない**（Follow-up Q1=A）。

```text
deriveRequiredHeadcounts(record: HistoricalRecord) -> Map<FacilityId, Integer>
  目的: 過去の実績から、各施設の必要人数を導出する
  ビジネスルール: 実績でその施設に割り当てられていた職員数を必要人数とする（FR-05.1.2, R3-CQ7=A）
  不変条件: 実績の割当人数 == 導出された必要人数（定義により）

deriveAvailableStaffSet(record: HistoricalRecord) -> StaffId[]
  目的: 過去イベントで「従事可能」と申告した職員の集合を返す（FR-05.1.3, R3-CQ6=A）
  不変条件: 実績の割当職員集合 ⊆ 従事可能と申告した職員集合

buildReplayProblem(
    record:      HistoricalRecord,
    currentStaff: Staff[],          // 現在の職員マスタ（当時の値は取得不可、A-09）
    facilities:  Facility[],
    params:      OptimizationParameters
) -> AssignmentProblem
  目的: 過去イベントを再現するための AssignmentProblem を組み立てる
  留意: 居住小学校区・部署・資格は現在の職員マスタの値を使用する（A-09）。
        ベースラインと最適化結果の双方が同一の現在値で評価されるため、両者の差（削減効果）は妥当である。
        ただし絶対値は当時の実際の値と一致しない。

computeComparison(
    baseline:  Assignment[],       // 実績の割当、または手動入力されたベースライン
    optimized: Assignment[],       // 共有エンジンが生成した割当
    problem:   AssignmentProblem
) -> ComparisonReport
  目的: 総移動時間・総移動費用・最大移動時間の削減量と削減率、および移動時間の分布を算出する
  不変条件: 削減量 = ベースライン値 - 最適化後の値（符号を含めて常に成立）

// --- 型 ---
ComparisonReport {
    totalTravelTime:  Metric   // { baseline, optimized, reduction, reductionRate }
    totalTravelCost:  Metric
    maxTravelTime:    Metric
    timeDistribution: Histogram
    caveat:           String   // A-09 の注記（絶対値は当時の実際の値と一致しない）
}
```

---

## 2. ポート

```text
// --- P-01 SolverPort ---
solve(problem: AssignmentProblem, options: SolverOptions) -> SolverResult
  目的: 割当問題を解き、解と最適性ギャップを返す
  SolverOptions  { timeLimitSeconds, cancellationToken, randomSeed }
  SolverResult   { assignments[], objectiveValue, optimalityGap, status, violations[] }
  status: Optimal | TimeLimitReached | Infeasible | Cancelled
  ビジネスルール: TimeLimitReached の場合も、返される解は全ハード制約を満たす（US-20）
  不変条件: INV-11（同一入力・同一シード・同一パラメータで結果は決定的）

  実装: A-03 ExactSolverAdapter, A-03b HeuristicSolverAdapter, A-03c BruteForceSolverAdapter（テスト専用オラクル）

// --- P-02 RepositoryPort（エンティティごとに分割） ---
EventRepository        : findById, findAll, save, delete
StaffRepository        : findById, findAll, saveAll, delete
FacilityRepository     : findById, findByEventId, saveAll, delete
SchoolDistrictRepository : findById, findAll, saveAll
AvailabilityRepository : findEffectiveByEvent(eventId), findHistory(staffId, eventId), saveAll
AssignmentRepository   : findByEventId, save, delete
HistoricalRecordRepository : findByEventId, save

  ビジネスルール: saveAll はトランザクション境界内で実行し、1 行でもエラーがあれば全体をロールバックする
                （fail closed / SECURITY-15、US-07）

// --- P-03 DistanceCachePort ---
getDistance(fromDistrictId, toDistrictId) -> Kilometers | NotCached
putDistances(entries: DistanceCacheEntry[]) -> void
invalidateAll() -> void
  目的: 小学校区ペア単位の距離キャッシュ（Q4=A）
  ビジネスルール: 小学校区マスタが更新されたとき invalidateAll を呼ぶ（US-09）
  留意: 校区数を D とすると、キャッシュ要素数は D^2。D=100 なら 1 万要素であり、
        NFR-P03 の「40 万要素」より 1〜2 桁小さい

// --- P-04 AuditLogPort ---
append(entry: AuditEntry) -> void
query(criteria: AuditQuery) -> AuditEntry[]
  // 削除・更新のメソッドは定義しない（SECURITY-14、US-04）
  AuditEntry { actorId, timestamp, action, targetType, targetId, beforeValue?, afterValue? }
  ビジネスルール: entry に個人情報（氏名、居住小学校区）を含めてはならない。職員 ID のみを記録する（SECURITY-03）

// --- P-05 JobStorePort ---
enqueue(job: OptimizationJob) -> JobId
getStatus(jobId: JobId) -> JobStatus
requestCancel(jobId: JobId) -> void
findRunningByEvent(eventId: EventId) -> JobId | None
  JobStatus { state, progressSeconds, currentObjectiveValue?, currentOptimalityGap?, result? }
  state: Queued | Running | Completed | Failed | Cancelled
  ビジネスルール: 同一イベントにつき同時に実行できるジョブは 1 つのみ（Q3=A）

// --- P-06 ConfigPort ---
getTravelParameters() -> TravelParameters
getObjectiveWeights() -> ObjectiveWeights
getDepartmentCapLimit() -> Integer
getIpAllowlist() -> CidrBlock[]
updateTravelParameters(params: TravelParameters) -> void
updateObjectiveWeights(weights: ObjectiveWeights) -> void
  ビジネスルール: いずれの値もハードコードしない（NFR-M03）

// --- P-07 CsvCodecPort ---
parse(bytes: Bytes, schema: CsvSchema) -> Result<Row[], CsvError[]>
serialize(rows: Row[], schema: CsvSchema) -> Bytes
  ビジネスルール: parse はエラーを行番号とともに返す（US-07）
                serialize は数式インジェクションを無害化する（MU-02、SEC-05 を利用）
  不変条件: INV-10（parse(serialize(rows)) == rows）
```

---

## 3. アプリケーションサービス層

```text
// --- S-01 EventService ---
createEvent(input: EventInput) -> Result<Event, ValidationError>
updateEvent(eventId, input) -> Result<Event, ValidationError>
deleteEvent(eventId) -> Result<void, DeletionBlocked>
  ビジネスルール: ステータスが「確定」のイベントは削除できない（US-06）

// --- S-02 MasterDataService ---
importStaff(csv: Bytes) -> Result<ImportSummary, CsvError[]>
importFacilities(csv: Bytes) -> Result<ImportSummary, CsvError[]>
importSchoolDistricts(csv: Bytes) -> Result<ImportSummary, CsvError[]>
  ビジネスルール: 1 行でもエラーがあればインポート全体をロールバックする（fail closed、US-07）
                小学校区の更新後は DistanceCachePort.invalidateAll を呼ぶ（US-09）
  不変条件: インポート失敗時、DB の状態はインポート前と完全に同一である（原子性）

updateStaff(staffId, input) -> Result<Staff, ValidationError>
updateFacility(facilityId, input) -> Result<Facility, DeletionBlocked>
  ビジネスルール: 確定済みイベントの割当に含まれる施設は削除できない（US-10）
                すべての更新を AuditService に記録する

// --- S-03 AvailabilityService ---
importDeclarations(eventId, csv: Bytes) -> Result<ImportSummary, CsvError[]>
  目的: 従事可否申告の一括登録（US-11）。PoC では担当者が代理で登録する（A-08）
  ビジネスルール: 職員マスタに存在しない職員 ID を含む場合、全体をロールバックする

updateDeclaration(staffId, eventId, isAvailable, reasonCategory) -> Result<AvailabilityDeclaration, Error>
  目的: 再申告（US-12）。以前の申告は履歴として保持する
  不変条件: 同一の（職員, イベント）に対する有効な申告はちょうど 1 件

getDeclarationHistory(staffId, eventId) -> AvailabilityDeclaration[]
getSufficiencyStatus(eventId) -> SufficiencyStatus
  目的: 最適化実行前の充足状況を返す（US-13）。C-04 に委譲する

// --- S-04 OptimizationService ---
startOptimization(eventId, weights: ObjectiveWeights, options) -> Result<JobId, OptimizationBlocked>
  目的: 最適化ジョブを起動する（US-16, US-17）
  フロー:
    1. AvailabilityRepository から従事可能職員を取得する（FR-04.1）
    2. DistanceCachePort から距離行列を構築する
    3. C-04 InfeasibilityDiagnoser で診断する
    4. 診断結果に応じて分岐する:
         Feasible                  -> ジョブを起動する
         TotalHeadcountShortage    -> OptimizationBlocked を返す。C1 は緩和しない（US-18）
         QualificationShortageOnly -> allowC3Demotion = true としてジョブを起動する（US-19）
         OtherConstraintInfeasible -> OptimizationBlocked を返す（原因を提示）
    5. JobStorePort.enqueue でジョブを登録する
  ビジネスルール: 同一イベントに実行中のジョブがある場合、起動を拒否する（Q3=A）

getJobStatus(jobId) -> JobStatus
  目的: 進捗（経過時間、現在の目的関数値、最適性ギャップ）を返す（US-20）

cancelJob(jobId) -> Result<void, Error>
  目的: 実行中のジョブをキャンセルする（Q3=A）

// --- S-05 AssignmentAdjustmentService ---
getAssignmentsByStaff(eventId) -> StaffAssignmentView[]
getAssignmentsByFacility(eventId) -> FacilityAssignmentView[]
  目的: 双方向の一覧表示（US-21）

changeAssignment(eventId, change: AssignmentChange) -> Result<ConstraintViolation[], Error>
  目的: 手動修正。C-03 validateSingleChange で即座に違反を検証する（US-22）
  ビジネスルール: 変更を AuditService に記録する（変更前後の値を含む、US-03）

pinAssignment(eventId, staffId) -> Result<void, Error>
unpinAssignment(eventId, staffId) -> Result<void, Error>

reoptimizeWithPins(eventId) -> Result<JobId, PinConstraintViolation>
  目的: ピン留めを固定して再最適化する（US-23）
  ビジネスルール: C-03 validatePins が違反を返した場合、再最適化を実行せずエラーを返す（FR-06.4）
  不変条件: INV-13（ピン留めされた割当は変更されない）

reoptimizeAfterAdditionalDeclarations(eventId, mode: FullReopt | IncrementalReopt) -> Result<JobId, Error>
  目的: 追加申告後の再最適化（US-24, FR-06.6）
  FullReopt        : 前回の割当を破棄し、従事可能な全職員を対象に最初から最適化する
  IncrementalReopt : 前回の割当を全てピン留めし、追加で従事可能になった職員のみを未充足施設に割り当てる
  不変条件: IncrementalReopt の目的関数値 >= FullReopt の目的関数値

exportAssignments(eventId) -> Bytes
  目的: 割当結果を CSV にエクスポートする（US-25）
  不変条件: INV-10（ラウンドトリップ）

// --- S-06 ComparisonReportService ---
importHistoricalRecord(csv: Bytes) -> Result<HistoricalRecord, CsvError[]>
  目的: 過去イベントの実績を取り込む（US-26）
  ビジネスルール: 職員データは仮名化されている（氏名は職員 ID に置換済み、CQ7=B）

replayAndCompare(eventId) -> Result<JobId, Error>
  目的: 過去イベントを同一条件で再現し、比較レポートを生成する（US-26, US-27）
  フロー:
    1. C-05 deriveRequiredHeadcounts で必要人数を導出する
    2. C-05 deriveAvailableStaffSet で従事可能職員集合を特定する
    3. C-05 buildReplayProblem で AssignmentProblem を組み立てる
    4. **S-04 OptimizationService に最適化を委譲する**（Follow-up Q1=A）
       -> 実際の割当で使われるのと同一の共有エンジンが実行する
    5. C-05 computeComparison で実績と最適化結果を比較する
  設計判断: 本サービスは最適化ロジックを一切持たない。これにより、レポートが示す削減効果は
            システムが実際に生成する割当を反映する（SC-01 の妥当性）

setManualBaseline(eventId, csv: Bytes) -> Result<Assignment[], CsvError[]>
  目的: 実績のない新規イベントに、担当者がベースライン割当を手動入力する（US-28, FR-05.1.6）

exportComparisonReport(eventId) -> Bytes

// --- S-07 ConfigService ---
getTravelParameters() -> TravelParameters
updateTravelParameters(params) -> Result<void, ValidationError>
getObjectiveWeights() -> ObjectiveWeights
updateObjectiveWeights(weights) -> Result<void, ValidationError>
  不変条件: すべての重みが非負であり、少なくとも 1 つが正である（US-17）
  ビジネスルール: 迂回係数の変更後、距離キャッシュは無効化しない
                （キャッシュは大円距離を保持し、迂回係数は適用時に乗じる）

// --- S-08 AuditService ---
recordAssignmentChange(actorId, eventId, change: AssignmentChange) -> void
recordMasterDataChange(actorId, entityType, entityId, before, after) -> void
recordSecurityEvent(actorId?, eventType: AuthFailure | AuthzViolation | IpRejected | AccountLocked) -> void
  ビジネスルール: 個人情報（氏名、居住小学校区）を含めない。職員 ID のみを記録する（SECURITY-03）
  不変条件: 割当結果に対するあらゆる変更操作について、監査ログのエントリが 1 件以上生成される
```

---

## 4. セキュリティモジュール

```text
// --- SEC-01 AuthenticationModule ---
authenticate(credentials) -> Result<Session, AuthenticationFailure>
validateSession(sessionToken) -> Result<Principal, SessionInvalid>
invalidateSession(sessionToken) -> void
recordFailedAttempt(accountId) -> LockoutStatus
  ビジネスルール: 規定回数を超える連続失敗でアカウントを一時ロックする（MU-03、US-01）
                Cookie に Secure / HttpOnly / SameSite を設定する（SECURITY-12）
                パスワードは適応型ハッシュで保存する（SECURITY-12）

// --- SEC-02 AuthorizationModule ---
requireAuthentication(request) -> Result<Principal, Unauthorized>
  ビジネスルール: deny by default。明示的に公開と指定されたエンドポイント以外はすべて認証を要求する
  不変条件: 認証を要求しないエンドポイントの集合 == 明示的に定義された公開エンドポイント集合

authorizeResourceAccess(principal, resourceType, resourceId) -> Result<void, Forbidden>
  ビジネスルール: リソース ID を参照する要求では、呼び出し元の権限をサーバー側で検証する
                （オブジェクトレベル認可、MU-01 IDOR 対策、SECURITY-08）

// --- SEC-03 NetworkControlModule ---
verifySourceIp(sourceIp: IpAddress) -> Result<void, IpRejected>
  ビジネスルール: 庁内イントラネットの出口グローバル IP 以外を拒否する（NFR-S10.2、US-02）
                許可リストは ConfigPort から取得する。ハードコードしない（NFR-M03）
                拒否を AuditService に記録する

// --- SEC-04 RateLimitModule ---
checkRateLimit(principal | sourceIp, endpoint) -> Result<void, RateLimitExceeded>
  ビジネスルール: 公開エンドポイントにレート制限を課す（SECURITY-11）

// --- SEC-05 InputValidationModule ---
validateRequest(request, schema) -> Result<ValidatedRequest, ValidationError[]>
  ビジネスルール: 型検査、長さ上限、書式の許可リスト検証（SECURITY-05）
                リクエストボディのサイズ上限を課す

sanitizeCsvCell(value: String) -> String
  ビジネスルール: 値が =, +, -, @ で始まる場合、エクスポート時にエスケープする
                （数式インジェクション対策、MU-02）
  利用: A-04 CsvAdapter.serialize が呼び出す
```

---

## 5. Functional Design への引き渡し

以下は本ステージでは**シグネチャのみ**を定義した。詳細なビジネスルールは Functional Design（CONSTRUCTION フェーズ、ユニットごと）で定義する。

| 項目 | 引き渡し先ユニット（想定） | 申し送り |
|------|------------------------|---------|
| 目的関数の具体的な数式（3 項の重み付き和、不公平性の指標の定義） | 最適化エンジン | 不公平性を「最大移動時間」とするか「移動時間の分散」とするかを確定する |
| ハード制約 C1〜C5 の数理計画法上の定式化 | 最適化エンジン | |
| ソフト制約 S1（従事履歴の平準化）のペナルティ関数 | 最適化エンジン | |
| ビッグMの具体的な値の決め方 | 最適化エンジン | INV-12 を満たす下限を示すこと |
| `travelCostYen` の費用モデル | 距離・費用算出 | **H-1**: 線形モデル（距離 × 単価）は「タクシー費用の高額化」の非線形性を捉えない。距離帯モデルへの拡張を再検討する |
| CSV スキーマの具体的な列定義とバリデーション規則 | データ管理 | |
| 移動時間の分布（ヒストグラムのビン幅、分位点の取り方） | 比較レポート | |
| 13 件の不変条件のプロパティ分類と PBT 実装方針 | 全ユニット | **H-2**: PBT-01 により、設計文書に「Testable Properties」セクションを設ける |
