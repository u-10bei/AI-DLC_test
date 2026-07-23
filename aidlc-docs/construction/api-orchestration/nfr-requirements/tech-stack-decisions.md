# 技術スタック決定 — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 7 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A

---

## 1. U-01 からの継承

「Web フレームワーク = FastAPI（+ Pydantic による入力検証, SECURITY-05）」は U-01 で確定済み。U-07 はこれを継承し、**バージョンを確定する**（U07-H5）。

---

## 2. U07-H5 の解決: バージョン確定（Q1=A）

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| `fastapi` | **0.115.6** | HTTP フレームワーク、ルーティング、ミドルウェア |
| `uvicorn` | **0.34.0** | ASGI サーバー |
| `pydantic` | **2.10.4** | DTO と入力検証（**v2**。v1 は EOL）|
| `httpx` | **0.28.1**（dev）| FastAPI TestClient が要求 |

**既存の依存固定の基準（late-2024: sqlalchemy 2.0.36 / ortools 9.11.4210 / argon2-cffi 23.1.0）と整合する。** すべて `pip-audit` 対象、SBOM に含める（SECURITY-10）。

### 2.1 導入検証（決定前に実施）

```text
fastapi 0.115.6 | pydantic 2.10.4 | uvicorn 0.34.0 | httpx 0.28.1
有効な要求   -> 200 {"echo": 42}
不正な要求   -> 422        ← DTO 検証が拒否（SECURITY-05 の証跡）
```

**環境上の注記**: 本共有環境には pydantic 2.11+ を要求する無関係なパッケージ（litellm, mcp 等）が存在し、2.10.4 の導入で警告が出る。**本プロジェクトの依存集合は内部的に整合**しており、これらは本 PoC の構成要素ではない（U-04 の ortools/protobuf と同種の状況）。

---

## 3. ワーカーのプロセス分離（Q2=A, U07-H4）

| 項目 | 決定 |
|------|------|
| 起動 | **CLI エントリポイント** `python -m api_orchestration.worker` |
| 常駐 | **systemd / supervisor**（運用）。U-01 の shared-infrastructure が「API プロセス + **単一ジョブワーカープロセス**」と規定済み |
| ポーリング間隔 | **設定として外部化**（既定 2 秒、NFR-M03）|
| 並行度 | **1 ジョブずつ**（単一ワーカー, A-07）|

**API プロセス内のバックグラウンド実行を却下した理由**: 300 秒の求解が API プロセスの資源を占有し、U-01 のプロセス分離の決定に反する。

---

## 4. U-07 のリンタ契約（Q4=A）

| 契約 | 内容 |
|------|------|
| **R（U-07 のユニット境界）** | `api_orchestration` は `shared_kernel`, `distance_cost`, `data_management`, `optimization_engine`, `comparison_report`, `security` を import 可（**統合点**）。`frontend` を import してはならない |
| **許可する第三者** | `fastapi`, `uvicorn`, `pydantic`, **`sqlalchemy`**（`SqlSessionStore` と `optimization_jobs` キューのため, U07-H2/H3）|

### 4.1 この契約が意味すること

**`pydantic` / `fastapi` を許可されるのは U-07 だけ**である。これは、U-01〜U-06 のすべての契約がそれらを**禁止してきたこと**の裏返しであり、**「Pydantic を API 境界に閉じ込める」という U-01 の決定が全ユニットで守られてきたことの確認**である。

`sqlalchemy` の許可も同様に意味を持つ: **U-06 は `sqlalchemy` を禁止**されているため `SessionStorePort` の実装を持てず、**U-07 がそれを実装して注入する**（U06-H2）。契約が設計の配置を決めている。

---

## 5. 性能（Q3=A）

- `POST /optimizations` は**投入して 202 を即返す**（求解を待たない）
- **U-07 固有の数値目標は設けない**——重い処理は U-03（NFR-P04: CSV 2,000 行 30 秒）と U-04（NFR-P02: 300 秒）が既に目標を持つ
- 検証は **Build and Test**

---

## 6. テスト（Q5=A）

- **FastAPI TestClient（httpx）で実際に HTTP を叩く。モックしない**——ミドルウェア順序・DTO 検証・例外ハンドラ・セキュリティヘッダは **HTTP を通してしか検証できない**
- DB はインメモリ SQLite（U-03 のパターン）
- ワーカーは**同期的に 1 ステップ実行**（プロセスを起動しない）
- **PBT-06** でジョブ状態機械を検証

---

## 7. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U07-H5（解決）** | fastapi 0.115.6 / uvicorn 0.34.0 / pydantic 2.10.4 / httpx 0.28.1（dev）| （本ステージで解決）|
| **U07-H9（新規）** | 上記を `pyproject.toml` に固定（`httpx` は dev）、pip-audit/SBOM 対象に含める | U-07 Code Generation |
| **U07-H10（新規）** | `.importlinter` に U-07 契約を追加。**`frontend` の import が BROKEN になること**を確認（非空虚性）| U-07 Code Generation |
| U07-H1〜H4, H6〜H8 | Functional Design より継続 | U-07 Code Generation / U-08 |
