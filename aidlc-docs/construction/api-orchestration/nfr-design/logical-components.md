# Logical Components — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Design（ユニット 7 / 8）
**回答**: Q5=A

---

## 概要

U-07 の論理コンポーネントは **9 つ**。すべて `src/api_orchestration/` 配下。**業務ロジックを持たず**、下位ユニットを配線する。

```text
   HTTP
     │
┌────▼──────────────────────────────────────────────┐
│ LC-01 app（FastAPI）                               │
│  ミドルウェア: ヘッダ → SEC-03 → SEC-04 → SEC-01(DP-01)│
│                        → SEC-02 → SEC-05          │
│  LC-09 errors: 例外 → 汎用応答                      │
└────┬──────────────────────────────────────────────┘
     │
┌────▼─────────┐   ┌──────────────┐   ┌──────────────┐
│ LC-02 routers │──▶│ LC-03 dto    │──▶│ LC-04        │
│               │   │（Pydantic）   │   │ converters   │
└────┬─────────┘   └──────────────┘   │（純関数）      │
     │                                 └──────┬───────┘
     │                                        │ ドメイン型
┌────▼───────────────────────────────────────▼───────┐
│ LC-05 composition（合成ルート）                       │
│   SqlSessionStore → U-06（U06-H2）                  │
│   sanitize_csv_cell → U-03/U-05（U06-H3）           │
│   U-03/U-04/U-05/U-06 のサービスを組み立て            │
└────┬───────────────────────────────┬───────────────┘
     │                               │
┌────▼─────────┐              ┌──────▼──────────┐
│ LC-06        │              │ LC-08           │
│ job_queue    │◀─────────────│ worker          │
│（条件付き UPDATE）           │ step()/run_forever()│
└──────────────┘              └─────────────────┘
                                     │ U-04 で求解
┌──────────────┐
│ LC-07        │  SessionStorePort の実装（U-06 に注入）
│ session_store│
└──────────────┘
```

---

## LC-01: app（FastAPI + ミドルウェア）

| 項目 | 内容 |
|------|------|
| 責務 | FastAPI アプリ、ミドルウェアの配線 |
| 順序 | セキュリティヘッダ → SEC-03 IP → SEC-04 レート → **SEC-01 認証（DP-01: 許可リスト方式）** → SEC-02 認可 → SEC-05 検証 |
| 生成 | `build_application(config)`（LC-05 が組み立てる）|

---

## LC-02: routers

| 項目 | 内容 |
|------|------|
| 責務 | エンドポイント定義（認証、イベント、マスタ、申告、最適化、割当、比較）|
| 注意 | **認証は各ルータで書かない**（ミドルウェアが担う, DP-01）。認可は `require_authorization` を明示的に呼ぶ |

---

## LC-03: dto（Pydantic）

| 項目 | 内容 |
|------|------|
| 責務 | リクエスト/レスポンスの型と検証（SECURITY-05）|
| 制約 | **Pydantic は U-07 のみ**（U-01 パターン 1、リンタ契約で全ユニットに強制済み）|

---

## LC-04: converters（純関数）

| 項目 | 内容 |
|------|------|
| 責務 | DTO ↔ ドメイン型の**手書き変換**（DP-05）|
| 純粋性 | 純関数 → **P-API01（ラウンドトリップ）をプロパティテスト可能** |

---

## LC-05: composition（合成ルート）

| 項目 | 内容 |
|------|------|
| 責務 | 全ユニットの組み立てと注入（DP-06）|
| **U06-H2** | `SqlSessionStore`（LC-07）を U-06 の `Authenticator` に注入 |
| **U06-H3** | `sanitize_csv_cell`（U-06）を U-03/U-05 の CSV 出力に注入 |
| 方式 | **明示的な手組み**（DI コンテナなし）|

---

## LC-06: job_queue

| 項目 | 内容 |
|------|------|
| 責務 | `optimization_jobs`（U-03 骨格, U03-H3）への投入・claim・状態更新 |
| claim | **条件付き UPDATE + rowcount**（DP-03）|
| 状態 | `QUEUED → RUNNING → {SUCCEEDED, INFEASIBLE, FAILED}` |

---

## LC-07: session_store（`SqlSessionStore`）

| 項目 | 内容 |
|------|------|
| 責務 | U-06 の `SessionStorePort` の**実装**（U-03 の `sessions` テーブル）|
| **なぜ U-07 にあるか** | **U-06 は `sqlalchemy` を禁止**されており（契約で強制）、セッションを自分で永続化できない。したがってこの実装は U-07 に置かれ、注入される（U06-H2）。**契約が設計の配置を決めている** |

---

## LC-08: worker

| 項目 | 内容 |
|------|------|
| 責務 | ジョブをポーリングして U-04 で求解し、結果を永続化（U04-H4）|
| 形 | **`step()` / `run_forever()` に分離**（DP-04）→ テストは `step()` を同期呼び出し |
| 起動 | CLI `python -m api_orchestration.worker`（常駐は systemd/supervisor）|
| 問題構築 | `build_problem`（U-03 のデータ + U-02 の距離, U07-H4）|

---

## LC-09: errors（例外ハンドラ）

| 項目 | 内容 |
|------|------|
| 責務 | 例外 → **汎用応答**（DP-02, SECURITY-09, U01-H14）|
| fail closed | 未知の例外も **500 + 汎用**（SECURITY-15）|

---

## 該当しない論理コンポーネント（Q5=A、N/A）

| コンポーネント | 判定 | 根拠 |
|--------------|:----:|------|
| メッセージキュー製品（Redis 等）| **N/A** | キューは DB（U-01 の決定）|
| 外部キャッシュ | **N/A** | 距離キャッシュは U-03 |
| サーキットブレーカ / リトライ | **N/A** | fail closed |
| スケールアウト層 / 複数ワーカー競合制御 | **N/A** | 単一ワーカー（A-07）。ただし claim は条件付き UPDATE で将来に耐える（DP-03）|

---

## 依存とポート

- U-07 は `shared_kernel`, `distance_cost`, `data_management`, `optimization_engine`, `comparison_report`, `security` を import 可。**`frontend` は禁止**
- 第三者: `fastapi`, `uvicorn`, `pydantic`, `sqlalchemy` を許可。**`pydantic`/`fastapi` を許されるのは U-07 のみ**
- **U-08 は U-07 の HTTP 境界を呼ぶ**（NFR-M05, U07-H6）。プロセス内直接呼び出しで結合しない

---

## 拡張ルール適合サマリ（論理コンポーネント観点）

| ルール | 判定 | 根拠 |
|--------|------|------|
| SECURITY-08（既定で認証）| ✅ | LC-01（DP-01 許可リスト方式）|
| SECURITY-04（ヘッダ）| ✅ | LC-01 |
| SECURITY-05（入力検証）| ✅ | LC-03 |
| SECURITY-09/15（応答・fail closed）| ✅ | LC-09 |
| Scalability / Resilience | N/A | Q5=A |

**ブロッキング所見: なし**
