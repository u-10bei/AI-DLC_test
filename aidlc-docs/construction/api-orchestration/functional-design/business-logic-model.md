# ビジネスロジックモデル — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Functional Design（ユニット 7 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A, Q7=A

---

## 1. 概要

U-07 は**統合点**——全ユニット（U-01〜U-06）を知る唯一のユニット。HTTP 境界、DTO、ミドルウェア配線、非同期ジョブ、合成ルートを担う。**業務ロジックを持たない**（それは U-03〜U-06 にある）。

```text
        HTTP（庁内イントラネット PC から）
              │
   ┌──────────▼───────────────────────────────────┐
   │ A-01 RestApiAdapter（FastAPI）                │
   │  ミドルウェア（U06-H4 の順序）:               │
   │   SEC-03 IP → SEC-04 レート → SEC-01 認証     │
   │            → SEC-02 認可 → SEC-05 入力検証     │
   │  グローバル例外ハンドラ → 汎用応答（U01-H14）  │
   │  セキュリティヘッダ（SECURITY-04）             │
   └──────────┬───────────────────────────────────┘
              │ DTO ↔ ドメイン型の明示的変換（Q1）
   ┌──────────▼───────────────────────────────────┐
   │ 合成ルート（Q2）: 全ユニットを手組みし注入     │
   │   SessionStorePort 実装 → U-06（U06-H2）      │
   │   sanitize_csv_cell → U-03/U-05（U06-H3）     │
   └──────────┬───────────────────────────────────┘
              │
   ┌──────────▼──────────┐   ┌─────────────────────┐
   │ 同期: U-03/U-05/U-06 │   │ 非同期: ジョブキュー  │
   │（マスタ/申告/比較）   │   │  optimization_jobs   │
   └─────────────────────┘   └──────────┬──────────┘
                                        │ ポーリング
                              ┌─────────▼──────────┐
                              │ ワーカープロセス     │
                              │  U-04 で求解（300s）│
                              │  結果を U-03 に永続化│
                              └────────────────────┘
```

---

## 2. コンポーネント構成

| コンポーネント | 役割 |
|--------------|------|
| **A-01 RestApiAdapter** | FastAPI アプリ、ルーティング、ミドルウェア |
| **DTO 層** | Pydantic のリクエスト/レスポンス型 + ドメイン型との変換（Q1）|
| **合成ルート** | 全ユニットの組み立てと注入（Q2、U06-H2/H3）|
| **例外ハンドラ** | 例外 → 汎用応答（Q3、U01-H14、SECURITY-09）|
| **JobQueue** | `optimization_jobs` への投入・取得（Q4）|
| **Worker** | ジョブをポーリングし U-04 を実行（Q4）|

---

## 3. DTO 境界（Q1=A, NFR-M05, U-01 パターン 1）

```text
受信: JSON → Pydantic DTO（検証, SECURITY-05）→ [明示的変換] → ドメイン型 → 業務ユニット
送信: ドメイン型 → [明示的変換] → Pydantic DTO → JSON
```

- **Pydantic は U-07 のみ**（U-01 の決定の履行。ドメイン層はフレームワークを知らない）
- **ドメイン型を直接シリアライズしない**——内部構造が API 契約に漏れ、ドメインの変更が API を壊す
- 変換は**手書きで明示的**（U-03 の手書きマッパと同じ思想）
- **PII の扱い**: 応答 DTO に氏名を含めるのは業務上必要な画面のみ。**ログ・エラー応答には含めない**（SECURITY-03）

---

## 4. ミドルウェアと例外（Q3=A, U06-H4, U01-H14）

### 4.1 順序（Application Design 準拠）

**SEC-03 IP 許可リスト → SEC-04 レート制限 → SEC-01 認証 → SEC-02 認可 → SEC-05 入力検証**

安価で広範な拒否を先に置く。**すべて deny by default**。

### 4.2 例外 → 汎用応答（SECURITY-09）

| 例外 | HTTP | 応答 |
|------|:----:|------|
| `IpNotAllowedError` | **403** | 汎用メッセージ |
| `RateLimitExceededError` | **429** | 汎用メッセージ |
| `AuthenticationFailedError` | **401** | 汎用メッセージ（利用者の存在を漏らさない）|
| `AuthorizationDeniedError` | **403** | 汎用メッセージ |
| `CsvImportError` | **400** | **行番号付きの全エラー**（BR-DM02。PII なし）|
| `DomainError`（その他）| **400** | 汎用メッセージ + `violated_rule` |
| **予期しない例外** | **500** | 汎用メッセージのみ（**fail closed**）|

**スタックトレース・内部パス・フレームワークバージョンを応答に含めない**。詳細は構造化ログ（PII なし）へ。

### 4.3 セキュリティヘッダ（SECURITY-04）

`Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`。

---

## 5. 合成ルートと注入（Q2=A, U06-H2/H3）

```text
build_application(config):
    engine = create_db_engine(config.database_url)          # U-03
    session_store = SqlSessionStore(engine)                 # U-07 が実装（U-03 の sessions）
    hasher = Argon2PasswordHasher(security_config)          # U-06
    audit = AuditService(AppendOnlyFileAuditLog(path))      # U-06
    authenticator = Authenticator(session_store, hasher, audit, security_config)   # ← U06-H2 注入
    authorizer = Authorizer(audit)
    ip_allowlist = IpAllowlist(security_config)
    rate_limiter = RateLimiter(security_config)
    master = MasterDataService(engine)                      # U-03
    availability = AvailabilityService(engine)              # U-03
    events = EventService(engine)                           # U-03
    optimizer = OptimizationService()                       # U-04
    comparison = ComparisonService(optimizer)               # U-05
    # U06-H3: CSV 出力にサニタイザを注入
    export_staff = lambda: master.export_staff(sanitize=sanitize_csv_cell)
    ...
```

- **単一の合成ルート**が全てを手組みする。**DI コンテナを使わない**（依存を増やす価値がない）
- **U06-H2**: `SessionStorePort` の DB 実装（`SqlSessionStore`）は **U-07 が実装**し、U-06 に注入する。U-06 は `sqlalchemy` を import できない（契約で強制）
- **U06-H3**: `sanitize_csv_cell`（U-06）を U-03/U-05 の CSV 出力に注入する（MU-02）。U-03/U-05 は U-06 に依存しない

---

## 6. エンドポイント（ストーリー対応）

| エンドポイント | ストーリー |
|--------------|-----------|
| `POST /sessions` / `DELETE /sessions` | US-01（認証）|
| `POST|GET|PATCH|DELETE /events` | US-05, US-06 |
| `POST /masters/{kind}/import` / `GET /masters/{kind}/export` | US-07〜US-10, US-25 |
| `POST /events/{id}/declarations/import` / `GET .../history` | US-11, US-12 |
| `GET /events/{id}/sufficiency` | US-13 |
| `GET|PUT /parameters` | US-14 |
| `POST /optimizations` → 202 `job_id` / `GET /optimizations/{job_id}` | US-16〜US-20 |
| `GET /events/{id}/assignments` | US-21 |
| `PATCH /events/{id}/assignments`（手動修正 + 即時検証）| US-22, FR-06.3 |
| `POST /optimizations`（`mode`, `pinned`）| US-23, US-24, FR-06.4/6.6 |
| `GET /events/{id}/comparison` / `.../comparison.csv` | US-26〜US-28 |

---

## 7. 非同期ジョブ（Q4=A, NFR-P02）

### 7.1 フロー

```text
POST /optimizations {event_id, mode, parameters}
   → 認可 → ジョブを optimization_jobs に QUEUED で投入
   → 202 {job_id}                       # 即座に返す（API をブロックしない）

Worker（別プロセス、単一, A-07）:
   loop:
     job = claim_next_queued()          # RUNNING に遷移
     problem = build_problem(job)       # U-03 のデータ + U-02 の距離
     result = OptimizationService.optimize(problem)     # U-04（最大 300 秒）
     if result is InfeasibilityDiagnosis: job → INFEASIBLE（診断を保存）
     else: save_assignment_result(...)（U04-H4）; job → SUCCEEDED
     例外時: job → FAILED（原因は監査/ログへ、PII なし）

GET /optimizations/{job_id}
   → {state, result | diagnosis | error}
```

### 7.2 ジョブ状態

```text
QUEUED ──▶ RUNNING ──▶ SUCCEEDED
                  ├──▶ INFEASIBLE   （U-04 の診断。エラーではない）
                  └──▶ FAILED       （予期しない失敗）
```

**`INFEASIBLE` を `FAILED` と区別する**——実行不可能は「担当者が行動すべき状態」であってシステム障害ではない（U-04 の設計と整合）。

---

## 8. 再最適化モード（Q5=A, FR-06.6, US-24）

| モード | 動作 | トレードオフ（担当者に明示）|
|-------|------|--------------------------|
| **FULL** | 前回の割当を破棄し、従事可能な全職員で解く | 最適だが、**既に内示を受けた職員の割当先が変わりうる** |
| **INCREMENTAL** | **前回の割当をピン留め**して U-04 に渡し、追加で従事可能になった職員のみを未充足施設へ | 既存割当は不変だが、**全体最適にはならない** |

- INCREMENTAL は `AssignmentProblem.pinned_assignments` に前回割当を設定する（U-04 が既に実装）
- ピン留めがハード制約に違反する場合、U-04 は **solve せずエラー**（FR-06.4）→ U-07 は 400 + 該当制約を返す

---

## 9. 手動修正と即時検証（Q6=A, US-22, FR-06.3）

```text
PATCH /events/{id}/assignments {staff_id, facility_id}
   → 認可 → 変更後の割当集合を構築
   → U-04 の【公開】制約検証関数を呼ぶ            ← Q6=A（U-04 を in-place 修正）
   → 違反があれば 400 + 違反一覧（施設/制約 ID、PII なし）
   → 無ければ保存 + 監査（変更前後の施設 ID, FR-07.1）
```

**なぜ U-04 に公開関数を追加するのか**: U-07 が独自に C1〜C5 を検証すると、**同じ制約の解釈が 2 ユニットに存在し、いずれ乖離する**。U-04 を制約の唯一の権威に保つ。U-02 が U-01 の承認済みコードを in-place 修正した判断と同型。

---

## 10. 認証 API（Q7=A）

- `POST /sessions`（ログイン）→ **HttpOnly + Secure + SameSite=Strict Cookie** にセッション ID
- `DELETE /sessions`（ログアウト）→ U-06 の `logout`（即時失効）
- **Cookie は JavaScript から読めない**（XSS でのセッション窃取を防ぐ）
- U-06 の `Authenticator` に `SqlSessionStore` を注入（U06-H2）

---

## 11. Testable Properties（PBT-01, ブロッキング）

| ID | プロパティ | 分類 |
|----|-----------|------|
| **P-API01** | **DTO ラウンドトリップ**: `dto_to_domain(domain_to_dto(x)) == x` | Round-trip |
| **P-API02** | **未認証は必ず拒否**: セッション無し/無効の要求は 401、業務ロジックに到達しない | Invariant（Security）|
| **P-API03** | **非許可 IP は必ず拒否**: 403、業務ロジックに到達しない | Invariant |
| **P-API04** | **エラー応答に内部情報が出ない**: 任意の例外に対し、応答にスタックトレース・内部パス・フレームワーク名が含まれない | Security |
| **P-API05** | **ジョブ状態遷移**: `QUEUED → RUNNING → {SUCCEEDED, INFEASIBLE, FAILED}` のみ。終端から遷移しない | Invariant |
| **P-API06** | **セキュリティヘッダ**: すべての応答に SECURITY-04 のヘッダが付く | Invariant |
| **P-API07** | **CSV エクスポートがサニタイズされている**: 数式文字で始まるセルが出力に現れない（U06-H3 の注入が効いている）| Security |

### 11.1 ステートフルテスト（PBT-06）の評価

**ジョブの状態機械は対象**（`QUEUED → RUNNING → 終端`）。ただし U-06 のセッション状態機械は既に U-06 で検証済み。**U-07 では job の状態遷移を `RuleBasedStateMachine` で検証する**（終端から遷移しない、二重 claim しない）。

---

## 12. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U07-H1** | **U-04 に公開の制約検証関数を追加**（in-place 修正, Q6=A）| U-07 Code Generation |
| **U07-H2** | `SqlSessionStore`（`SessionStorePort` の DB 実装）を U-07 が実装（U-03 の `sessions`, U03-H3）| U-07 Code Generation |
| **U07-H3** | `optimization_jobs`（U-03 骨格）のキュー操作を U-07 が実装（U03-H3）| U-07 Code Generation |
| **U07-H4** | ワーカープロセスの起動方法（プロセス分離）と `build_problem`（U-03 のデータ + U-02 の距離から `AssignmentProblem` を組む）| U-07 Code Generation |
| **U07-H5** | 全ユニットのプロダクション依存に FastAPI/uvicorn/Pydantic を追加（U-07 のみ）| U-07 NFR Requirements |
| **U07-H6** | フロントエンドは U-07 の API を**明示的な HTTP 境界**として呼ぶ（NFR-M05）。バックエンド URL は設定外部化 | U-08 |
