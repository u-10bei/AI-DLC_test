# ドメインエンティティ / モデル型 — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Functional Design（ユニット 7 / 8）

---

## 1. U-07 は業務ドメイン型を新規定義しない

U-07 が新規に定義するのは **DTO**（API 契約）と **ジョブ型**のみ。業務型はすべて U-01 が定義済み。

---

## 2. DTO（Pydantic、U-07 のみ, Q1=A）

### 2.1 方針

- **リクエスト DTO**: 受信 JSON を検証（SECURITY-05）→ **明示的変換**でドメイン型へ
- **レスポンス DTO**: ドメイン型 → **明示的変換** → JSON
- **ドメイン型を直接シリアライズしない**（BR-API02）

### 2.2 主な DTO

| DTO | 用途 | PII |
|-----|------|:---:|
| `LoginRequest`（user_id, password）| `POST /sessions` | パスワードは**ログに出さない** |
| `EventRequest` / `EventResponse` | イベント CRUD（US-05, US-06）| なし |
| `ImportResultResponse`（success_count / errors[line, message]）| CSV インポート（US-07）| **なし**（行番号 + ID のみ, BR-DM14）|
| `SufficiencyResponse`（available/unavailable/undeclared/required/shortage）| US-13 | なし |
| `TravelParametersRequest/Response` | US-14 |なし |
| `OptimizationRequest`（event_id, mode, weights, pinned[]）| US-16, US-23, US-24 | なし |
| `JobAcceptedResponse`（job_id）| 202 応答 | なし |
| `JobStatusResponse`（state, result? , diagnosis?, error?）| US-20 | なし |
| `AssignmentResponse`（staff_id, staff_name?, facility_id, is_pinned）| US-21 | **氏名は業務上必要な画面のみ** |
| `AssignmentPatchRequest`（staff_id, facility_id）| US-22 | なし |
| `ConstraintViolationResponse`（constraint_id, facility_id, detail）| US-22, US-18 | なし |
| `ComparisonResponse`（削減時間/費用/率, note）| US-27 | なし |

### 2.3 変換関数

```text
to_domain: EventRequest -> Event
           OptimizationRequest -> (EventId, mode, OptimizationParameters, pinned)
           AssignmentPatchRequest -> Assignment
from_domain: Event -> EventResponse
             AssignmentResult -> JobStatusResponse
             InfeasibilityDiagnosis -> JobStatusResponse
             ComparisonReport -> ComparisonResponse
             SufficiencyStatus -> SufficiencyResponse
```

**P-API01**: `dto_to_domain(domain_to_dto(x)) == x`（ラウンドトリップ）。

---

## 3. ジョブ型（U-07 が定義, Q4=A）

```text
JobState = Enum:
    QUEUED / RUNNING / SUCCEEDED / INFEASIBLE / FAILED

ReoptimizationMode = Enum:
    FULL / INCREMENTAL        # FR-06.6, US-24

@frozen
OptimizationJob:
    id: JobId                 # NewType[str]
    event_id: EventId
    mode: ReoptimizationMode
    state: JobState
    created_at: datetime      # UTC
    result_id: str | None = None      # SUCCEEDED のとき assignment_results への参照
    detail: str | None = None         # INFEASIBLE/FAILED の要約（PII なし）
```

**`INFEASIBLE` は `FAILED` と別**（BR-API15）。

---

## 4. U-07 が実装するポート実装（注入用）

| 実装 | 実装するポート | 定義元 | 申し送り |
|------|--------------|-------|---------|
| **`SqlSessionStore`** | `SessionStorePort` | **U-06** | **U07-H2 / U06-H2**。U-03 の `sessions` テーブルを使う。**U-06 は sqlalchemy を import できないため、この実装は U-07 に置かれる** |

---

## 5. 使用する既存ユニットの型

| ユニット | 型・サービス |
|---------|------------|
| U-01 | `Event`, `Staff`, `Facility`, `Assignment`, `AssignmentProblem`, `AssignmentResult`, `OptimizationParameters`, `TravelParameters`, `DomainError` ほか |
| U-02 | `compute_travel_metrics`（`build_problem` で移動行列を組む, U07-H4）|
| U-03 | `MasterDataService`, `AvailabilityService`, `EventService`, `create_db_engine`, `schema`（`sessions` / `optimization_jobs`）|
| U-04 | `OptimizationService`, `InfeasibilityDiagnosis`, `save_assignment_result`, **公開制約検証関数（U07-H1 で追加）** |
| U-05 | `ComparisonService`, `export_report_csv` |
| U-06 | `Authenticator`, `Authorizer`, `IpAllowlist`, `RateLimiter`, `AuditService`, `sanitize_csv_cell`, `SecurityConfig` |

---

## 6. データフロー

```text
HTTP → [ミドルウェア: SEC-03→04→01→02→05] → ルータ
                                              │
                                    DTO 検証 → ドメイン型へ変換
                                              │
                    ┌─────────────────────────┼──────────────────────┐
                    ▼                         ▼                      ▼
              U-03（同期）              JobQueue（非同期）        U-05（比較）
              マスタ/申告/イベント        optimization_jobs         │
                    │                         │                     │
                    │                    Worker → U-04 → 結果保存    │
                    ▼                         ▼                     ▼
              ドメイン型 → DTO → JSON（+ セキュリティヘッダ）
                    │
                    └─▶ U-06 AuditService（変更を監査、PII なし）
```

---

## 7. 後続への申し送り

business-logic-model.md 12 節（U07-H1〜H6）を参照。本ステージで新規の型定義申し送りは以下。

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U07-H7（新規）** | `JobId`（NewType）、`JobState`、`ReoptimizationMode`、`OptimizationJob` を `api_orchestration` に定義 | U-07 Code Generation |
| **U07-H8（新規）** | DTO と変換関数を定義し、**P-API01（ラウンドトリップ）** をプロパティテストで検証 | U-07 Code Generation |
