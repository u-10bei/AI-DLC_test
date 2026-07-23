# サービス層設計（Services）

**作成日**: 2026-07-09
**ステージ**: INCEPTION - Application Design

---

## 1. サービス層の位置づけと責務

サービス層は、ドメイン層とアダプタ層の間に位置し、以下を担う。

- **オーケストレーション**: 複数のドメインコンポーネントとポートを協調させる
- **トランザクション境界**: どこからどこまでが原子的な操作かを定める
- **ジョブ調整**: 非同期の最適化ジョブの起動・監視・キャンセル

**サービス層はビジネスルールそのものを持たない。** 制約の検証は C-03 ConstraintValidator に、実行不可能性の診断は C-04 InfeasibilityDiagnoser に、比較の算出は C-05 ComparisonAnalyzer に委譲する。

---

## 2. サービス一覧

| ID | サービス | 主たる責務 | トランザクション境界 |
|----|---------|-----------|-------------------|
| S-01 | EventService | イベントのライフサイクル管理 | 単一操作 |
| S-02 | MasterDataService | マスタの一括インポートと個別修正 | **インポート全体が 1 トランザクション** |
| S-03 | AvailabilityService | 従事可否申告の登録と履歴管理 | **インポート全体が 1 トランザクション** |
| S-04 | OptimizationService | 最適化ジョブの起動・監視・キャンセル | ジョブ起動は単一操作。計算自体はトランザクション外 |
| S-05 | AssignmentAdjustmentService | 割当結果の参照・手動修正・再最適化 | 単一操作 |
| S-06 | ComparisonReportService | ベースライン再現と比較レポート生成 | 最適化を S-04 に委譲 |
| S-07 | ConfigService | 設定値の取得と更新 | 単一操作 |
| S-08 | AuditService | 監査ログの記録 | **業務トランザクションとは独立**（後述） |

---

## 3. 業務フローのオーケストレーション

### 3.1 主要フロー: イベント登録から割当確定まで

```text
  +-------------------------------------------------------------------+
  |  1. イベント登録                                                  |
  |     S-01 EventService.createEvent()                               |
  +-------------------------------------------------------------------+
                                |
                                v
  +-------------------------------------------------------------------+
  |  2. 従事可否申告の一括登録（PoC: 担当者が代理登録）               |
  |     S-03 AvailabilityService.importDeclarations()                 |
  +-------------------------------------------------------------------+
                                |
                                v
  +-------------------------------------------------------------------+
  |  3. 充足状況の確認（最適化の実行前）                              |
  |     S-03 AvailabilityService.getSufficiencyStatus()               |
  |       -> C-04 InfeasibilityDiagnoser.sufficiencyStatus()          |
  +-------------------------------------------------------------------+
                                |
                                v
  +-------------------------------------------------------------------+
  |  4. 最適化ジョブの起動                                            |
  |     S-04 OptimizationService.startOptimization()                  |
  +-------------------------------------------------------------------+
                                |
                                v
                      +-------------------+
                      |  C-04 で原因診断  |
                      +-------------------+
                       |        |        |
          Feasible     |        |        |   TotalHeadcountShortage
          または       |        |        |
    QualificationOnly  |        |        |   OtherConstraintInfeasible
                       v        |        v
  +--------------------------+  |  +----------------------------------+
  |  5a. ジョブを起動        |  |  |  5b. 起動を拒否し原因を提示      |
  |      進捗をポーリング    |  |  |      C1 は緩和しない             |
  +--------------------------+  |  +----------------------------------+
                       |        |                    |
                       v        |                    v
  +--------------------------+  |  +----------------------------------+
  |  6a. 割当結果を確認・調整|  |  |  6b. 人手による調整              |
  |      S-05                |  |  |      追加の従事可否申告を登録    |
  +--------------------------+  |  |      S-03.updateDeclaration()    |
                       |        |  +----------------------------------+
                       |        |                    |
                       |        +--------------------+
                       |          （4 へ戻る: 再最適化）
                       v
  +-------------------------------------------------------------------+
  |  7. 割当を確定し、CSV にエクスポートする                          |
  |     S-05 AssignmentAdjustmentService.exportAssignments()          |
  +-------------------------------------------------------------------+
```

---

### 3.2 S-04 OptimizationService.startOptimization() の詳細フロー

**これがシステムの中核となるオーケストレーションである。** FR-04.5 の原因診断分岐を実装する。

```text
startOptimization(eventId, weights, options):

  Step 1. 同時実行の検査（Q3=A）
      running = JobStorePort.findRunningByEvent(eventId)
      if running exists:
          return Error("このイベントには実行中のジョブがあります")

  Step 2. 問題の構築
      event          = EventRepository.findById(eventId)
      facilities     = FacilityRepository.findByEventId(eventId)
      declarations   = AvailabilityRepository.findEffectiveByEvent(eventId)
      availableStaff = declarations.filter(isAvailable).map(toStaff)   // FR-04.1
      travelMatrix   = buildTravelMatrix(availableStaff, facilities)   // DistanceCachePort + C-01
      params         = ConfigPort.getTravelParameters()
      problem        = AssignmentProblem(event, facilities, availableStaff, travelMatrix, pins=[], params)

  Step 3. 原因診断（C-04 に委譲）
      diagnosis = InfeasibilityDiagnoser.diagnose(problem)

  Step 4. 診断結果による分岐（FR-04.5）
      case Feasible:
          problem.parameters.allowC3Demotion = false
          jobId = JobStorePort.enqueue(OptimizationJob(problem, options))
          return jobId

      case QualificationShortageOnly(shortfalls):
          // C3 のみをソフト制約に降格し、ビッグMペナルティを課す（CQ1=B, CQ2=C）
          problem.parameters.allowC3Demotion = true
          jobId = JobStorePort.enqueue(OptimizationJob(problem, options))
          return jobId
          // 結果には violations[] が含まれ、UI が違反行をハイライトする（FR-04.5.1, US-19）

      case TotalHeadcountShortage(shortageCount, unfilledFacilities):
          // C1 は決して緩和しない。定員割れの解を返してはならない（US-18, INV-02）
          return OptimizationBlocked(
              reason  = "従事可能職員が {shortageCount} 名不足しています",
              details = unfilledFacilities,
              action  = "追加の従事可否申告を登録してください"
          )

      case OtherConstraintInfeasible(constraintIds):
          // C2, C4, C5 は降格しない
          return OptimizationBlocked(
              reason = "制約 {constraintIds} により解が存在しません",
              action = "入力データを修正してください"
          )
```

**設計上の要点**: 診断（C-04、純粋関数）と、診断結果に応じた振る舞い（S-04、オーケストレーション）を分離している。これにより、診断ロジックは DB もジョブキューも持たずにテストできる。

---

### 3.3 非同期ジョブのライフサイクル（Q2=B, Q3=A）

```text
  Client                    S-04 OptimizationService        A-06 JobRunnerAdapter
    |                                  |                              |
    |-- POST /optimizations ---------->|                              |
    |                                  |-- enqueue(job) ------------->|
    |<------ 202 Accepted { jobId } ---|                              |
    |                                  |                              |-- SolverPort.solve()
    |                                  |                              |   (最大 300 秒)
    |-- GET /jobs/{jobId} ------------>|                              |
    |                                  |-- getStatus(jobId) --------->|
    |<-- 200 { state: Running,         |                              |
    |          progressSeconds: 45,    |                              |
    |          optimalityGap: 8.2% } --|                              |
    |                                  |                              |
    |   （ポーリングを継続）           |                              |
    |                                  |                              |
    |-- GET /jobs/{jobId} ------------>|                              |
    |<-- 200 { state: Completed,       |                              |
    |          result: {...},          |                              |
    |          optimalityGap: 0% } ----|                              |
    |                                  |                              |
    |   （または、途中でキャンセル）   |                              |
    |-- DELETE /jobs/{jobId} --------->|                              |
    |                                  |-- requestCancel(jobId) ----->|
    |<-- 204 No Content ---------------|                              |
```

**US-20（制限時間と最適性ギャップ）の実現**: `JobStatus` が `progressSeconds`、`currentObjectiveValue`、`currentOptimalityGap` を含むため、制限時間に達した時点で `state = Completed` とし、`result` にその時点での最良の実行可能解と最適性ギャップを載せる。返される解は全ハード制約を満たす。

---

### 3.4 S-06 ComparisonReportService.replayAndCompare() のフロー

**最適化を S-04 に委譲する**（Follow-up Q1=A）。比較レポートは独自の最適化ロジックを持たない。

```text
replayAndCompare(eventId):

  Step 1. 過去実績の取得
      record = HistoricalRecordRepository.findByEventId(eventId)

  Step 2. 条件の導出（C-05 に委譲、すべて純粋関数）
      requiredHeadcounts = ComparisonAnalyzer.deriveRequiredHeadcounts(record)
          // 実績でその施設に割り当てられていた職員数 = 必要人数（FR-05.1.2）
      availableStaffIds  = ComparisonAnalyzer.deriveAvailableStaffSet(record)
          // 過去イベントで「従事可能」と申告した職員の集合（FR-05.1.3）
          // 実際に割り当てられた職員の集合より広い
      currentStaff       = StaffRepository.findAll()
          // 居住小学校区・部署・資格は現在の値を使用する（A-09）
      problem            = ComparisonAnalyzer.buildReplayProblem(
                               record, currentStaff, facilities, params)

  Step 3. 最適化を共有エンジンに委譲（Follow-up Q1=A）
      jobId = OptimizationService.startOptimizationForProblem(problem)
      // 実際の割当で使われるのと同一のエンジンが実行する
      // これにより、レポートが示す削減効果はシステムが実際に生成する割当を反映する（SC-01）

  Step 4. ジョブ完了後、比較を算出（C-05 に委譲、純粋関数）
      optimized = JobStorePort.getStatus(jobId).result.assignments
      baseline  = record.actualAssignments
      report    = ComparisonAnalyzer.computeComparison(baseline, optimized, problem)
      report.caveat = "居住小学校区・部署・資格は現在の値を使用しているため、" +
                      "移動時間・費用の絶対値は当時の実際の値と一致しません。" +
                      "ベースラインと最適化結果の双方が同一の現在値で評価されるため、" +
                      "両者の差（削減効果）は妥当です。"   // A-09
      return report
```

---

### 3.5 S-02 / S-03 の CSV インポート（fail closed、SECURITY-15）

```text
importXxx(csv):

  Step 1. 解析
      rows = CsvCodecPort.parse(csv, schema)
      if rows is Error:
          return CsvError[]   // 行番号付きのエラー一覧を返す。DB は一切変更しない

  Step 2. 検証（SEC-05 InputValidationModule を利用）
      errors = validate(rows)   // 型、長さ上限、参照整合性（存在しない小学校区 ID など）
      if errors is not empty:
          return errors         // DB は一切変更しない

  Step 3. トランザクション内で一括保存
      begin transaction
          Repository.saveAll(rows)
          if any error:
              rollback          // 1 行でもエラーがあれば全体をロールバック
              return CsvError[]
      commit

  Step 4. 副作用（小学校区マスタの場合のみ）
      DistanceCachePort.invalidateAll()   // US-09

  Step 5. 監査
      AuditService.recordMasterDataChange(...)

  return ImportSummary { successCount }

不変条件: インポートが失敗した場合、DB の状態はインポート前と完全に同一である（原子性、US-07）
```

**同期処理である**（Q7=A）。NFR-P04 により 2,000 行を 30 秒以内に処理する見込みであり、HTTP のタイムアウト内に収まる。

---

## 4. トランザクション境界の設計判断

### 4.1 監査ログは業務トランザクションと独立させる

**S-08 AuditService の書き込みは、業務トランザクションの内側に含めない。**

理由:

1. 監査ログは業務 DB とは**別の追記専用ストレージ**に書き込まれる（Q6=A）。分散トランザクションを避ける
2. 業務トランザクションがロールバックされても、**「変更を試みた」という事実は記録に残すべき**である
3. SECURITY-14 は「アプリケーションが自身のログを削除・改変できないこと」を要求する。業務トランザクションのロールバックによって監査ログが消えるのは、この趣旨に反する

**帰結**: 監査ログの書き込みは、業務操作の成否とは独立に、必ず実行される。監査ログには操作の結果（成功 / 失敗）も記録する。

### 4.2 最適化の計算はトランザクション外で実行する

最大 300 秒を要する計算をトランザクション内で保持すると、DB の接続とロックを長時間占有する。ジョブの起動（`enqueue`）は短いトランザクションで完結させ、計算そのものはトランザクション外のバックグラウンドで実行する。計算完了後、結果の保存を別の短いトランザクションで行う。

---

## 5. サービス間の依存

**サービス層内の依存は、以下の 2 本のみに限定する。循環依存は存在しない。**

| 依存元 | 依存先 | 理由 |
|-------|-------|------|
| S-03 AvailabilityService | C-04 InfeasibilityDiagnoser | 充足状況の算出（US-13）。ドメイン層への依存であり、サービス間依存ではない |
| S-05 AssignmentAdjustmentService | S-04 OptimizationService | 再最適化の起動（US-23, US-24） |
| S-06 ComparisonReportService | S-04 OptimizationService | ベースライン再現時の最適化の委譲（Follow-up Q1=A） |

すべてのサービスが **S-08 AuditService** を利用するが、S-08 は他のサービスに依存しないため循環は生じない。

---

## 6. セキュリティモジュールの適用点

セキュリティモジュールは **A-01 RestApiAdapter のミドルウェアとして適用**し、サービス層に到達する前にリクエストを検証する。

```text
  HTTP Request
       |
       v
  +--------------------------------------+
  |  SEC-03 NetworkControlModule         |  送信元 IP の許可リスト検証（US-02）
  |  verifySourceIp()                    |  拒否 -> 403 Forbidden、監査ログに記録
  +--------------------------------------+
       |
       v
  +--------------------------------------+
  |  SEC-04 RateLimitModule              |  レート制限（SECURITY-11）
  |  checkRateLimit()                    |  超過 -> 429 Too Many Requests
  +--------------------------------------+
       |
       v
  +--------------------------------------+
  |  SEC-01 AuthenticationModule         |  セッション検証（US-01）
  |  validateSession()                   |  無効 -> 401 Unauthorized
  +--------------------------------------+
       |
       v
  +--------------------------------------+
  |  SEC-02 AuthorizationModule          |  deny by default の認可ガード
  |  requireAuthentication()             |  オブジェクトレベル認可（MU-01）
  |  authorizeResourceAccess()           |  拒否 -> 403 Forbidden、監査ログに記録
  +--------------------------------------+
       |
       v
  +--------------------------------------+
  |  SEC-05 InputValidationModule        |  型・長さ・書式・サイズ上限（SECURITY-05）
  |  validateRequest()                   |  不正 -> 400 Bad Request
  +--------------------------------------+
       |
       v
  +--------------------------------------+
  |  Application Services (S-01 .. S-08) |
  +--------------------------------------+
```

**設計判断**: すべてのエンドポイントがこのミドルウェア連鎖を通過する。公開エンドポイント（ログイン画面、ヘルスチェック）のみ、SEC-01 と SEC-02 を明示的に免除する。免除リストはコード上の 1 か所に集約し、US-01 の不変条件「認証を要求しないエンドポイントの集合 == 明示的に定義された公開エンドポイント集合」を検証可能にする。

**エラー応答**: いずれの拒否も、スタックトレース・内部パス・フレームワークバージョンを含まない汎用メッセージを返す（SECURITY-09、NFR-S06）。失敗時は必ず拒否側に倒す（fail closed、SECURITY-15）。
