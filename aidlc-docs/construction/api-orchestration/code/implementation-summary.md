# U-07 api-orchestration — 実装サマリ

**ユニット**: U-07 api-orchestration（HTTP 境界・ジョブ・合成ルート）
**日付**: 2026-07-17
**状態**: 4 ゲート green（pytest 173 / mypy 105 files clean / ruff clean / lint-imports 14 契約 kept）

---

## 1. 何を作ったか

`src/api_orchestration/`（16 ファイル）。U-01〜U-06 を HTTP に露出させ、最適化をジョブとして実行する層。

| モジュール | 役割 |
|-----------|------|
| `identifiers.py` / `jobs.py` | `JobId`、`JobState`、`ReoptimizationMode`、`OptimizationJob`（frozen） |
| `config.py` | `AppConfig`（DB、監査ログ、`SecurityConfig`、`trusted_proxies`、既定パラメータ） |
| `dto.py` | Pydantic DTO。**pydantic を置いてよい唯一のモジュール** |
| `converters.py` | DTO ↔ ドメインの純関数。Pydantic はドメイン型を構築しない |
| `session_store.py` | `SqlSessionStore`（U-06 の `SessionStorePort` 実装、U06-H2） |
| `job_queue.py` | 条件付き UPDATE で claim。全関数が短いトランザクション |
| `problem_builder.py` | U-03 のデータ + U-02 の移動指標 → `AssignmentProblem` |
| `worker.py` | claim（短 tx）→ **求解（tx 外）** → 保存（短 tx） |
| `errors.py` | 例外 → 汎用応答。内部を漏らさない |
| `middleware.py` | ヘッダ → IP → レート → 認証。`PUBLIC_ROUTES` 許可リスト方式 |
| `routers.py` / `services.py` / `composition.py` | エンドポイントと手組みの合成ルート |

テストは `tests/api_orchestration/`（examples 15 + properties 6 + stateful 1 = **23 件**、U-01〜U-06 に回帰なし）。

---

## 2. 設計上、意図的に守ったこと

### 認証は `Depends()` ではなくミドルウェア（DP-01, Q1=A）
FastAPI の定石は per-route の `Depends()` だが、その**失敗様式は「デコレータを付け忘れたルートが公開される」**こと。ここでは `PUBLIC_ROUTES` にないパスは全て認証されるので、**忘れた場合の失敗様式は 401**。公開するには許可リストの編集が要り、レビュアーの目に入る。

これは「構造であって規律ではない」という本プロジェクトの一貫した原則の適用であり、P-API02（全保護ルートが未認証で 401）はこの構造をテストしている。

### 求解はトランザクションの外（U07-H13）
SQLite は単一ライタ。300 秒の求解を `engine.begin()` の中で回せば API プロセスが停止する。`worker.step()` は claim / 求解 / 保存を3つに割り、求解の間はどのトランザクションも開いていない。

### claim は条件付き UPDATE + rowcount（DP-03）
今日ワーカーは 1 プロセス（A-07）なので SELECT → UPDATE でも動く。**動くが、2 つ目のワーカーが増えた日に二重実行のバグに静かに変わる** — 二重に走るのは 300 秒の求解である。条件付き UPDATE は今のコストがゼロで、その日に壊れない。`test_stateful.py` が無作為な enqueue/claim/finish 列に対して「二重 claim なし・終端から遷移しない」を検査する（PBT-06）。

### 手動修正の検証は U-04 を呼ぶ（U07-H1）
`PATCH /events/{id}/assignments` の制約検査を U-07 に書けば、制約の解釈が 2 つになる。U-04 に `check_assignments(...)` を公開し、`OptimizationService._validate_pins` も**それを呼ぶよう書き換えた**（重複させない）。C1〜C5 の解釈は 1 箇所。

---

## 3. 生成中に見つけた逸脱・不具合（4 件）

### (1) 送信元 IP の設計欠陥（設計にはなかった / 実装で発覚）
テストで**全リクエストが 403** になったことから発覚した実在の欠陥。当初の実装は `request.client.host` を NFR-S10.2 の許可リストに掛けていたが、**既存の公開基盤（TLS 終端・WAF）の背後では `request.client.host` はプロキシのアドレス**であり、庁内 PC の送信元を判定できない — 許可リストが無意味になる。

対処: `X-Forwarded-For` を見るが、**そのヘッダは誰でも詐称できる**ので、`AppConfig.trusted_proxies` に運用者が列挙したプロキシが直接のピアである場合に**限って**信用する。信頼できるピアがヘッダを付けてこなかった場合は推測せず `""` を返し、`IpAllowlist` が拒否する（SECURITY-15、fail closed）。

```python
peer = request.client.host if request.client is not None else ""
if peer not in trusted_proxies:
    return peer  # 信頼できるホップではない: ヘッダは証拠にならない
forwarded = request.headers.get(header)
if not forwarded:
    return ""  # 信頼できるプロキシがヘッダを付けなかった -> 拒否。推測しない
return forwarded.split(",")[0].strip()
```

**運用への申し送り**: `trusted_proxies` の設定は本 PoC のデプロイ時に**必須**。空のまま公開基盤の背後に置くと、ピア（プロキシ）のアドレスが許可リストに掛かるため全遮断になる（fail closed なので、誤って全開放にはならない）。

### (2) リクエストのパラメータがワーカーに届いていなかった（実在のバグ）
ジョブが `INFEASIBLE` になることから発覚。`POST /optimizations` で受け取った `OptimizationParameters` が**永続化されておらず**、ワーカーは `AppConfig` の既定値（`department_cap_limit=1`）で解いていた。コーディネータが指定した重みや上限が黙って無視される — 出力は妥当に見えるので、テストがなければ気付けない類のバグ。

対処: `optimization_jobs` に `params_json` 列を追加、`OptimizationJob.parameters` を持たせ、ワーカーは**ジョブのパラメータを優先**し、無い場合のみ設定既定にフォールバックする。

### (3) 比較エンドポイントは未公開（U05-H6 に依存、繰り越し）
`GET /events/{id}/comparison` は**露出していない**。U-05 の `ComparisonService` は完成しテスト済みだが、呼ぶには `HistoricalRecord` が要り、過去イベントの実績を永続化するには U-05 が既に繰り越した `historical_assignments` / `historical_declarations` テーブル（U05-H6）が要る。**このエンドポイントは U-07 ではなく U05-H6 に閊えている。** `converters.from_domain_comparison` と `dto.ComparisonResponse` は実装済みなので、テーブルが入れば配線のみ。

### (4) U-03 のスキーマ骨格を in-place 拡張（Step 7、計画済み）
`accounts` テーブル（新規）、`sessions` に user_id/role、`optimization_jobs` に mode/params_json/result_id/detail を追加。`data_management/schema.py` を直接修正し、`alembic/versions/0002_accounts_sessions_jobs.py` を追加。

---

## 4. 品質ゲートの waiver（1 件、新規）

`[[tool.mypy.overrides]] module = "api_orchestration.dto"` で `disallow_any_explicit = false`。

**理由**: pydantic の `BaseModel` 自体が `__init__(**data: Any)` を宣言しているため、**自前の Any を一切含まない 3 行のモデルでも同じエラーが出る**（実際に確認済み）。この Any は我々のものではなくフレームワークのもの。

**封じ込め**（cp_sat_adapter の前例と同じ構造）: import-linter が pydantic を U-01〜U-06 から締め出し、この override は**1 モジュールにのみ**効く。したがって **U-07 内であっても dto.py 以外に `BaseModel` を定義すれば mypy が落ちる**。`converters.py` / `routers.py` は完全な strict のまま。

**非空虚性を確認済み**: `converters.py` に `class _Probe(BaseModel)` を注入 → mypy が 1 error を報告、除去 → clean。

---

## 5. 契約の非空虚性（Step 14）

- **R-8**（`api_orchestration` は frontend を import しない）: `routers.py` に `import frontend` を注入 → **BROKEN（13 kept, 1 broken）**、除去 → 14 kept。契約は実際に効いている。
- 第三者制約: fastapi / uvicorn / pydantic は U-07 のみ許可（U-01〜U-06 側の禁止契約は既存で確認済み）。

---

## 6. 文書修正

`aidlc-docs/construction/shared-infrastructure.md` セクション 2 の**ジョブワーカープロセスの所有ユニットを U-04 → U-07 に訂正**（U07-H14）。当初 U-04 と記載していたが、U-04 NFR Requirements Q5=A で「U-04 は求解ロジックと `SolverPort` を提供し、ジョブ実行の配線は U-07 が行う」と確定し、U-07 Functional Design Q4=A でキューとワーカーのコードを U-07 に置いた。プロセスの存在と分離の根拠は不変で、所有ユニットの記載のみの訂正。

---

## 7. ゲート結果

| ゲート | 結果 |
|-------|------|
| `pytest` | **173 passed**（U-01〜U-06 の 150 に回帰なし + U-07 の 23） |
| `mypy --strict` | **105 source files, clean** |
| `ruff check` | **clean** |
| `lint-imports` | **14 契約 kept, 0 broken**（R-8 非空虚性を確認） |
