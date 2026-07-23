# NFR Requirements Plan — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 7 / 8）
**参照**: U-07 Functional Design 全成果物、U-01 tech-stack-decisions.md、`requirements.md` v1.4（NFR-P01〜P04, NFR-M05, NFR-S03/S04/S08/S09）

---

## 1. スコープ

U-01 で「Web フレームワーク = FastAPI（+ Pydantic）」は確定済み。本ステージでは**バージョンの確定**（U07-H5）と、**ワーカーのプロセス分離方式**（U07-H4）を決める。

---

## 2. Step 1: Functional Design の分析

| カテゴリ | 該当 | 内容 |
|---------|:----:|------|
| **Tech Stack** | **該当（U07-H5）** | FastAPI / uvicorn / Pydantic のバージョン。テスト用 HTTP クライアント |
| **性能** | 該当 | API は即応（求解はジョブ）。ポーリング間隔 |
| 信頼性 | 該当 | ワーカーの分離、fail closed |
| 保守性 | 該当 | リンタ契約（**U-07 のみ Pydantic 可**）、NFR-M05 |
| セキュリティ | 該当 | SECURITY-04 ヘッダ、DTO 検証 |
| スケーラビリティ / 可用性 | N/A | 単一サーバー・単一ワーカー（A-07）、レジリエンシー無効 |

---

## 3. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: FastAPI / uvicorn / Pydantic のバージョン（Tech Stack, **U07-H5**, SECURITY-10）

U-01 で FastAPI + Pydantic は確定済み。バージョンを固定します。

A) **`fastapi==0.115.6`, `uvicorn==0.34.0`, `pydantic==2.10.4` を固定** — 既存の依存固定（late-2024 基準: sqlalchemy 2.0.36 / ortools 9.11 / argon2-cffi 23.1）と整合する。Pydantic v2（v1 は EOL）。テスト用に `httpx==0.28.1`（FastAPI の TestClient が要求）を dev 依存に追加。**導入可否は生成前に検証する** **（推奨）**

B) 別のバージョン（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 2: ワーカーのプロセス分離方式（信頼性 / 性能, **U07-H4**, A-07）

最大 300 秒の求解を API から切り離すワーカーを、どう起動しますか？

A) **CLI エントリポイント + プロセス管理は運用に委ねる** — `python -m api_orchestration.worker` で起動する CLI を提供し、実運用では systemd / supervisor が常駐させる（U-01 の shared-infrastructure が「API プロセス + 単一ジョブワーカープロセス」と規定済み）。**ポーリング間隔は設定外部化**（既定 2 秒）。ワーカーは 1 ジョブずつ処理する **（推奨）**

B) API プロセス内のバックグラウンドスレッド/タスクで実行 — プロセス分離が崩れ、300 秒の求解が API プロセスの資源を占有する（U-01 の決定に反する）

X) Other

[Answer]:A

---

### Question 3: 性能要件（性能, NFR-P01/P02）

U-07 固有の性能要件を確定してください。

A) **API は即応、重い処理はジョブへ** — (1) `POST /optimizations` は**投入して 202 を即返す**（求解を待たない）。(2) 同期エンドポイント（イベント CRUD、割当一覧、充足集計）は NFR-P01 の規模（職員 2,000 / 施設 200）で**実用的な応答**を返す。**U-07 固有の数値目標は設けない**——重い処理は既に U-03（NFR-P04）と U-04（NFR-P02）が目標を持つ。(3) 性能検証は **Build and Test** で行う **（推奨）**

B) U-07 固有の応答時間目標を設ける（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 4: U-07 のリンタ契約（保守性）

U-07 のユニット境界を確定してください。

A) **全ユニット import 可。第三者は fastapi/uvicorn/pydantic/sqlalchemy を許可** — (1) `api_orchestration` は `shared_kernel`, `distance_cost`, `data_management`, `optimization_engine`, `comparison_report`, `security` を import 可（統合点）。`frontend` は禁止。(2) 第三者: **`pydantic` と `fastapi` を許可するのは U-07 のみ**（他ユニットの契約が禁止している＝境界が守られていることの裏返し）。**`sqlalchemy` も許可**（`SqlSessionStore` と `optimization_jobs` キューを実装するため、U07-H2/H3）**（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 5: テスト戦略（信頼性）

U-07 のテスト方針を確定してください。

A) **FastAPI TestClient で HTTP 境界を実際に叩く** — (1) **モックしない**。TestClient（httpx）で**実際の HTTP 要求**を送り、ミドルウェア・DTO 検証・例外ハンドラ・セキュリティヘッダを**通しで**検証する（P-API02/03/04/06 は HTTP を通してしか検証できない）。(2) DB はインメモリ SQLite（U-03 のパターン）。(3) ワーカーはテスト内で**同期的に 1 ステップ実行**（プロセスを起動しない）。(4) **PBT-06** でジョブ状態機械を検証 **（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 6: 該当しないカテゴリの確認

A) **N/A 確定** — (1) スケーラビリティ: 単一サーバー・単一ワーカー（A-07）。水平スケール・複数ワーカーの競合制御は対象外。(2) 可用性: レジリエンシー無効、SLA なし。(3) 追加ミドルウェア（Redis 等）なし——キューは DB **（推奨）**

B) 一部該当する（`[Answer]:` に記述）

X) Other

[Answer]:A

---

## 4. 実行チェックリスト（回答分析後）

### 4.1 nfr-requirements.md
- [x] 該当 NFR（性能・信頼性・保守性・セキュリティ）を定義
- [x] N/A（スケーラビリティ、可用性）を根拠付きで記録
- [x] ワーカーのプロセス分離（Q2）、ポーリング間隔の外部化（NFR-M03）
- [x] テスト戦略（Q5）

### 4.2 tech-stack-decisions.md
- [x] U-01 継承の明記
- [x] Q1 のバージョン確定（**U07-H5 解決**）、導入検証
- [x] プロダクション依存の一覧・固定（SECURITY-10）
- [x] Q4 のリンタ契約（**U-07 のみ pydantic/fastapi 可**）

### 4.3 拡張ルール適合確認
- [x] SECURITY-10（依存固定、pip-audit、SBOM）、SECURITY-04/05
- [x] PBT-09（Hypothesis 継承）、PBT-06（ジョブ状態機械）
- [x] N/A ルールの記録、レジリエンシー無効の記録

### 4.4 完了処理
- [x] 2 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
