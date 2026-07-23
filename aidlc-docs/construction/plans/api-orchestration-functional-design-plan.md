# Functional Design Plan — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - Functional Design（ユニット 7 / 8）
**参照**: `requirements.md` v1.4（FR-06, FR-07, NFR-M05, NFR-S03/S04/S08/S09, A-07）、`stories.md`（US-14, US-21〜US-25）、Application Design（A-01 RestApiAdapter）、U-01〜U-06 の全成果物

---

## 1. ユニットコンテキスト

| 項目 | 内容 |
|------|------|
| ユニット | U-07 `api-orchestration`（`src/api_orchestration/`）|
| 依存 | **U-01〜U-06 のすべて**（唯一、全ユニットを知るユニット）|
| ストーリー | US-14（パラメータ設定）、US-21（一覧）、US-22（手動修正）、US-23（ピン留め再最適化）、US-24（追加申告後のモード選択）、US-25（CSV エクスポート）+ 全ストーリーの API 公開 |
| 役割 | **統合点**。HTTP 境界、DTO、ミドルウェア配線、ジョブキュー、合成ルート |

### 1.1 U-07 が引き受ける申し送り

| ID | 事項 |
|----|------|
| **U06-H2** | `SessionStorePort` の DB 実装を U-06 に**注入**（U-03 の `sessions`）|
| **U06-H3** | `sanitize_csv_cell` を U-03 / U-05 の CSV 出力に**注入**（U03-H5, MU-02）|
| **U06-H4** | ミドルウェア順序 **SEC-03→04→01→02→05** の配線と、例外→**汎用応答**への変換 |
| **U01-H14** | グローバル例外ハンドラ（汎用応答、SECURITY-09）|
| **U04-H5** | 目的関数内訳の提示 |
| **H-5 / NFR-M05** | **明示的な API 境界**（同一ホストでもプロセス内直接呼び出しで結合しない）|

---

## 2. Step 1: 設計対象の分析

| 領域 | 設計内容 |
|------|---------|
| API 境界 | エンドポイント、DTO（Pydantic は U-07 に閉じ込め）、ドメイン型との変換 |
| ミドルウェア | SEC-03→04→01→02→05、セキュリティヘッダ、例外→汎用応答 |
| 合成ルート | 全ユニットの組み立て、U-06 のポート/サニタイザ注入 |
| 非同期ジョブ | 最大 300 秒の最適化（NFR-P02）。DB ベースキュー + ワーカー |
| 再最適化 | FR-06.6 の 2 モード（全体 / 増分）|
| 手動修正 | US-22/23、FR-06.3（即時のハード制約検証）、FR-06.4（ピン留め）|

---

## 3. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: DTO 境界（NFR-M05, U-01 NFR Design パターン 1）

U-01 は「**Pydantic を U-07 の API 境界に限定する**」と決めました（ドメイン層をフレームワークから守るため）。その履行方法を確定してください。

A) **Pydantic DTO を U-07 に閉じ込め、ドメイン型との明示的な変換関数を書く** — 受信: DTO で検証（SECURITY-05）→ ドメイン型へ変換。送信: ドメイン型 → DTO → JSON。**ドメイン型を直接シリアライズしない**（内部構造が API 契約に漏れるのを防ぐ）。変換は手書きで明示的 **（推奨、U-01 の決定の履行）**

B) ドメイン型を直接シリアライズする — 変換コードは減るが、ドメインの変更が API 契約を壊し、U-01 の決定に反する

X) Other（`[Answer]:` に記述）

[Answer]:A

---

### Question 2: 合成ルート（統合点の設計）

全ユニットの組み立てと、U-06 のポート/サニタイザの注入（U06-H2/H3）をどこで行いますか？

A) **単一の合成ルート（composition root）モジュールが明示的に手組みする** — `SessionStorePort` の DB 実装、`sanitize_csv_cell`、各サービスを 1 箇所で組み立て、FastAPI の依存として供給する。**DI コンテナライブラリを使わない**（依存を 1 つ増やす価値がなく、明示的な手組みの方が読める）**（推奨）**

B) DI コンテナライブラリを導入する — 追加依存。本規模では過剰

X) Other

[Answer]:A

---

### Question 3: ミドルウェア順序・例外→応答・セキュリティヘッダ（U06-H4, U01-H14, SECURITY-04/09）

HTTP 境界の統制を確定してください。

A) **順序どおり配線 + グローバル例外ハンドラ + セキュリティヘッダ** — (1) **SEC-03 IP → SEC-04 レート制限 → SEC-01 認証 → SEC-02 認可 → SEC-05 入力検証**（Application Design 準拠）。(2) **グローバル例外ハンドラ**が U-06 / ドメインの例外を**汎用応答**に変換する——`IpNotAllowedError`/`RateLimitExceededError`/`AuthenticationFailedError`/`AuthorizationDeniedError` は種別に応じた HTTP ステータス（403/429/401/403）と**汎用メッセージ**。**スタックトレース・内部パス・フレームワークバージョンを出さない**（SECURITY-09）。予期しない例外は 500 + 汎用メッセージ（fail closed）。(3) **セキュリティヘッダ**（CSP, HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy）を付与（SECURITY-04）**（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 4: 非同期ジョブとワーカー（NFR-P02, U-01 の DB ベースキュー）

最大 300 秒の最適化を API から切り離す設計を確定してください。

A) **DB ベースのジョブキュー + ワーカープロセス** — (1) API は `POST /optimizations` でジョブを **`optimization_jobs`**（U-03 骨格, U03-H3）に投入し、**即座に `job_id` を返す**（202）。(2) **ワーカープロセス**がポーリングしてジョブを取得し、U-04 を実行して結果を永続化（U04-H4）。(3) 状態: `QUEUED` / `RUNNING` / `SUCCEEDED` / `FAILED` / `INFEASIBLE`。(4) `GET /optimizations/{job_id}` で状態と結果（または `InfeasibilityDiagnosis`）を返す。(5) ジョブ取得は競合しないよう**単一ワーカー**前提（A-07）**（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 5: 再最適化モード（FR-06.6, US-24）

追加申告後の再最適化の 2 モードを確定してください。

A) **API でモードを選択** — (1) **全体再最適化（FULL）**: 前回の割当を破棄し、従事可能な全職員で最初から解く。最適だが**既に内示を受けた職員の割当先が変わりうる**。(2) **増分再最適化（INCREMENTAL）**: **前回の割当をピン留め**して U-04 に渡し、追加で従事可能になった職員のみを未充足施設に割り当てる。既存割当は不変だが全体最適にはならない。(3) **トレードオフを応答/画面で明示**する（担当者が選ぶ, US-24）**（推奨、要件どおり）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 6: 手動修正時のハード制約検証（**設計上の論点**, US-22, FR-06.3）

FR-06.3 は「手動変更後、ハード制約（C1〜C5）への違反を**即座に検証**し、違反があれば警告する」と定めます。U-04 には既にピン留め検証がありますが、**private（`_validate_pins`）**です。

A) **U-04 に公開の検証関数を追加し、U-07 が呼ぶ（U-04 を in-place 修正）** — `optimization_engine` に `validate_assignments_against_constraints(problem, assignments) -> tuple[ConstraintViolation, ...]` 相当を公開し、U-07 の手動修正 API がそれを呼ぶ。**検証ロジックを一箇所に保つ**（U-04 が制約の唯一の権威）**（推奨）**

B) U-07 が独自に C1〜C5 検証を実装する — U-04 と**ロジックが二重化**し、いずれ乖離する（制約の解釈が 2 箇所に）

X) Other（`[Answer]:` に記述）

[Answer]:A

---

### Question 7: 認証 API とセッションの受け渡し（US-01, SECURITY-06/08）

ログインとセッションの扱いを確定してください。

A) **ログイン/ログアウトのエンドポイント + HttpOnly Cookie** — `POST /sessions`（ログイン）、`DELETE /sessions`（ログアウト）。セッション ID は **HttpOnly + Secure + SameSite=Strict の Cookie** で受け渡す（JavaScript から読めない＝XSS でのセッション窃取を防ぐ）。`SessionStorePort` の DB 実装を U-06 に注入（U06-H2）**（推奨）**

B) セッション ID を レスポンスボディ/ヘッダで返し、フロントが保持 — JS から読めるため XSS 耐性が落ちる

X) Other

[Answer]:A

---

## 4. 実行チェックリスト（回答分析後）

### 4.1 business-logic-model.md
- [x] コンポーネント構成（A-01 RestApiAdapter、DTO 層、合成ルート、ワーカー）
- [x] エンドポイント一覧（認証、イベント、マスタ、申告、最適化ジョブ、割当、比較、エクスポート）とストーリー対応
- [x] ミドルウェア順序・例外→汎用応答・セキュリティヘッダ（Q3）
- [x] ジョブキューとワーカー（Q4、状態遷移）
- [x] 再最適化モード（Q5）、手動修正の検証（Q6）
- [x] 合成ルートによる注入（Q2、U06-H2/H3）
- [x] DTO ↔ ドメイン型の変換方針（Q1）

### 4.2 business-rules.md
- [x] BR-API01.. （DTO 境界、deny by default、汎用応答、ジョブ状態、再最適化モード、手動修正の検証、PII 非露出）
- [x] NFR-M05（API 境界の明示化）の遵守
- [x] SECURITY-04/05/08/09 の適合

### 4.3 domain-entities.md
- [x] DTO（リクエスト/レスポンス）と `OptimizationJob` の型を定義
- [x] ドメイン型との変換関数の一覧
- [x] U-01〜U-06 の型の利用関係

### 4.4 PBT / Security 適合
- [x] Testable Properties: DTO ↔ ドメインのラウンドトリップ、未認証は必ず拒否、エラー応答に内部情報が出ない、ジョブ状態遷移の妥当性
- [x] ステートフルテスト（PBT-06）の要否評価（ジョブの状態機械）
- [x] SECURITY-04/05/08/09/15

### 4.5 完了処理
- [x] 3 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
