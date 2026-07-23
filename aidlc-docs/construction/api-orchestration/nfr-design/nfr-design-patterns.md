# NFR Design Patterns — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Design（ユニット 7 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A

---

## 概要

U-06 と同じ思想を HTTP 層に適用する——**規律ではなく構造で守る**。書き忘れ・付け忘れ・注入し忘れが、すべて**拒否側**に倒れる。

| # | パターン | 由来 |
|---|---------|------|
| DP-01 | 認証はミドルウェア + 公開ルート許可リスト | Q1（核心）|
| DP-02 | ミドルウェア順序と例外→汎用応答 | FD Q3 |
| DP-03 | ジョブ claim は条件付き UPDATE | Q2 |
| DP-04 | ワーカーは `step()` / `run_forever()` に分離 | Q3 |
| DP-05 | DTO 変換は純関数を 1 モジュールに集約 | Q4 |
| DP-06 | 合成ルートによる注入 | FD Q2 |
| DP-07 | セキュリティヘッダと PII 非露出 | SECURITY-04/03 |

---

## DP-01: 認証はミドルウェア + 公開ルート許可リスト（Q1=A、核心、SECURITY-08）

**問題**: FastAPI の慣用句「ルートごとに `Depends(authenticate)`」は、**付け忘れたルートが黙って公開される**（fail open）。「全ルートに付けたか」を人間の注意力に依存させることになる。

**パターン**: **認証を全要求に適用し、公開ルートだけを明示的に列挙する。**

```text
PUBLIC_ROUTES = frozenset({
    ("POST", "/sessions"),      # ログイン（認証前でないと使えない）
    ("GET",  "/health"),        # ヘルスチェック
})

authentication_middleware(request):
    if (request.method, request.url.path) in PUBLIC_ROUTES:
        return call_next(request)
    principal = authenticator.authenticate(session_id_from_cookie(request), now)  # 失敗で例外
    request.state.principal = principal
    return call_next(request)
```

**根拠**:
- **新しいルートは既定で保護される**。付け忘れの失敗モードが「**拒否**」になる
- 公開したいときは **`PUBLIC_ROUTES` への意識的な追加**が必要——**レビューで見える**
- U-06 の DP-01（関門は例外で拒否）と同じ思想。**deny by default**（SECURITY-08, US-01）

---

## DP-02: ミドルウェア順序と例外→汎用応答（FD Q3, U06-H4, U01-H14）

```text
要求 → [セキュリティヘッダ] → SEC-03 IP → SEC-04 レート → SEC-01 認証(DP-01)
                                              → SEC-02 認可 → SEC-05 検証(DTO) → ルータ
```

- 安価で広範な拒否を先に置く（Application Design 準拠）
- **グローバル例外ハンドラ**が例外を汎用応答に変換:

| 例外 | HTTP |
|------|:----:|
| `IpNotAllowedError` | 403 |
| `RateLimitExceededError` | 429 |
| `AuthenticationFailedError` | 401 |
| `AuthorizationDeniedError` | 403 |
| `CsvImportError` | 400（行番号付き全エラー、PII なし）|
| `DomainError` | 400 |
| **その他すべて** | **500 + 汎用メッセージ**（fail closed, SECURITY-15）|

**スタックトレース・内部パス・フレームワーク名を応答に含めない**（SECURITY-09）。

---

## DP-03: ジョブ claim は条件付き UPDATE（Q2=A）

```sql
UPDATE optimization_jobs SET state='RUNNING' WHERE id=? AND state='QUEUED'
-- rowcount == 1 なら取得成功。0 なら他が先に取った（または状態が変わった）
```

**根拠**: 現状は単一ワーカー（A-07）だが、`SELECT` してから `UPDATE` すると**将来ワーカーが増えたときに二重実行**する——**300 秒の求解が二重に走るのは高くつく**。条件付き UPDATE は今のコストがゼロで、その事故を構造的に防ぐ。

---

## DP-04: ワーカーは `step()` / `run_forever()` に分離（Q3=A）

```text
step() -> bool:          # 1 ジョブを取得して処理。処理したら True
run_forever():           # step() をポーリング間隔で繰り返す（CLI が呼ぶ）
    while True:
        if not step():
            sleep(poll_interval)
```

**根拠**: **テストは `step()` を同期呼び出しするだけ**でよく、プロセスもスレッドも起動しない（NFR Req Q5=A）。テストが速く、決定的になる。

---

## DP-05: DTO 変換は純関数を 1 モジュールに集約（Q4=A）

- `converters.py` に `to_domain_*` / `from_domain_*` を集める
- **純関数**なので **P-API01（ラウンドトリップ）をプロパティテストできる**
- Pydantic の自動変換でドメイン型を作らない——**ドメイン型に Pydantic を混ぜない**（U-01 パターン 1）
- U-03 の手書きマッパと同じ思想

---

## DP-06: 合成ルートによる注入（FD Q2, U06-H2/H3）

```text
build_application(config) -> FastAPI:
    engine = create_db_engine(config.database_url)
    session_store = SqlSessionStore(engine)                    # U-07 が実装
    authenticator = Authenticator(session_store, hasher, audit, sec_config)   # U06-H2 注入
    ...
    exporters = build_exporters(sanitize=sanitize_csv_cell)    # U06-H3 注入
    app = FastAPI(); wire_middleware(app, ...); wire_routers(app, ...)
    return app
```

- **単一の合成ルート**が全ユニットを手組みする（DI コンテナなし）
- **注入忘れの検出**: `sanitize_csv_cell` の注入は **P-API07**（エクスポートに数式文字で始まるセルが出ない）で検証する——**忘れると MU-02 の対策が無効**になるため、テストで担保する

---

## DP-07: セキュリティヘッダと PII 非露出（SECURITY-04/03）

| 項目 | 決定 |
|------|------|
| ヘッダ | CSP, HSTS, X-Content-Type-Options: nosniff, X-Frame-Options: DENY, Referrer-Policy を**全応答**に付与（ミドルウェア）|
| セッション Cookie | **HttpOnly + Secure + SameSite=Strict**（JS から読めない）|
| 応答 DTO | 氏名を含めるのは**業務上必要な画面のみ**。**エラー応答・ログには含めない** |

---

## 該当しないパターン（Q5=A、N/A）

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| Resilience（リトライ、CB）| **N/A** | fail closed。ジョブ失敗は `FAILED` として提示 |
| Scalability | **N/A** | 単一サーバー・単一ワーカー（A-07）|
| 追加ミドルウェア（Redis 等）| **N/A** | キューは DB（U-01 の決定）|

---

## 拡張ルール適合サマリ

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-08**（既定で認証）| ✅ | **DP-01**。ミドルウェア + 許可リスト。**新ルートは既定で保護** |
| **SECURITY-04**（ヘッダ）| ✅ | DP-07 |
| **SECURITY-05**（入力検証）| ✅ | DP-02（DTO）|
| **SECURITY-09**（エラー応答）| ✅ | DP-02 |
| **SECURITY-15**（fail closed）| ✅ | DP-01/02。未知の例外も 500 |
| **SECURITY-03**（PII 非露出）| ✅ | DP-07 |
| **PBT-01..10** | ✅ 検証可能 | P-API01〜07 + PBT-06（ジョブ状態機械）|
| Resiliency | スキップ | Enabled=No |

**ブロッキング所見: なし**

---

## 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U07-H11（新規）** | `PUBLIC_ROUTES` は**ログインとヘルスチェックのみ**。追加する際はセキュリティレビューを要する（DP-01）| U-07 Code Generation / 運用 |
| **U07-H12（新規）** | `sanitize_csv_cell` の注入忘れを **P-API07** で検証する（合成ルートのテスト）| U-07 Code Generation |
