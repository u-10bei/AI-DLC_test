# U-08 frontend — ビジネスロジックモデル（機能設計）

**ユニット**: U-08 frontend（`src/frontend/`）
**技術非依存**: フレームワークは NFR Requirements で決定。本書は画面・フロー・状態・API 連携を論理レベルで定義する。
**確定スコープ**（機能設計計画の回答 Q1=A / Q2=A / Q3=A / Q4=A / Q5=A / Q6=A）。

---

## 1. 画面（ビュー）一覧とルート

| # | 画面 | ルート | 主ペルソナ | 対応ストーリー | 消費エンドポイント |
|---|------|--------|-----------|--------------|------------------|
| V-01 | ログイン | `/login` | P-01, P-02 | US-01 | `POST /sessions` |
| V-02 | イベント作成／閲覧 | `/events`（作成フォーム + 直近作成の表示） | P-01 | US-05 | `POST /events`, `GET /events/{id}` |
| V-03 | マスタ管理（職員・施設・小学校区の CSV 取込／書出） | `/masters` | P-01 | US-07, **US-08, US-09**, US-25(職員のみ) | `POST/GET /masters/{staff,facilities,districts}/import,export` ※施設・小学校区は U08-H1 で U-07 に追加 |
| V-04 | 従事可否申告の取込 | `/events/{id}/declarations` | P-01 | US-11 | `POST /events/{id}/declarations/import` |
| V-05 | 充足状況 | `/events/{id}/sufficiency` | P-01 | US-13 | `GET /events/{id}/sufficiency` |
| V-06 | 最適化の実行と進捗 | `/events/{id}/optimize` | P-01 | US-16, US-17, US-20, US-24 | `POST /optimizations`, `GET /optimizations/{job_id}` |
| V-07 | 割当結果の閲覧・手動修正 | `/events/{id}/assignments` | P-01 | US-21, US-22 | `GET/PATCH /events/{id}/assignments` |

**共通レイアウト**: L-00 アプリシェル（ヘッダ = ログイン中ユーザ表示 + ログアウト、左ナビ = イベント選択と画面遷移、メイン領域 = 現在の画面）。

**繰り越し（画面を作らない）**:
- **比較／削減効果レポート（US-27）** — Q2=A により本 PoC では画面化しない。`GET /events/{id}/comparison` が U05-H6 に依存し未接続のため。→ 申し送り U08-H3。
- イベント編集／削除（US-06）、追加申告履歴（US-12）、ベースライン手動入力（US-28）、アカウント管理（Q6=A）— エンドポイント未公開のため対象外。

---

## 2. エンドツーエンドの価値実証フロー（正常系）

```text
[V-01 ログイン]
   │ POST /sessions → 204 + HttpOnly Cookie
   ▼
[V-02 イベント作成]  POST /events → 201
   ▼
[V-03 マスタ取込]  職員・施設・小学校区 CSV を取込（各 import → success_count）
   ▼
[V-04 申告取込]  POST /events/{id}/declarations/import → success_count
   ▼
[V-05 充足確認]  GET /events/{id}/sufficiency → 充足/不足を表示（不足なら警告）
   ▼
[V-06 最適化実行]  POST /optimizations → 202 {job_id, state:QUEUED}
   │ 約2秒間隔で GET /optimizations/{job_id} をポーリング（Q4=A）
   │   state: QUEUED → RUNNING → SUCCEEDED / INFEASIBLE / FAILED
   ▼
[V-07 割当閲覧]  GET /events/{id}/assignments → 一覧表示
   │ 手動修正 PATCH /events/{id}/assignments
   │   200 = 反映後の一覧 / 400 = ハード制約違反（違反内容を表示）
   ▼
（価値の提示: 最適化結果の目的関数値・最適性ギャップ、および割当ごとの移動負担 ※U08-H2）
```

---

## 3. クライアント状態モデル

状態は 3 種に分類する（ステップ C）。

| 種別 | 内容 | 例 |
|------|------|-----|
| **ローカル状態** | フォーム入力・UI 開閉・選択 | ログインフォーム、最適化パラメータ入力、選択中イベント ID |
| **フェッチ状態** | バックエンドから 1 回取得して表示 | イベント、充足状況、割当一覧 |
| **ポーリング状態** | 終端まで反復取得 | 最適化ジョブの状態（V-06） |

- **認証状態**: フロントはトークンを保持しない（Cookie は HttpOnly）。「ログイン済みか」は最後のリクエスト結果で判断し、任意のリクエストが `401` を返したら V-01 へ遷移する（Q6=A）。
- **選択中イベント**: 多くの画面が `event_id` を必要とするため、アプリシェルで選択中イベントを 1 つ保持し、V-04〜V-07 に渡す。

---

## 4. 最適化ジョブのポーリングロジック（V-06、Q4=A）

```text
enqueue():
  POST /optimizations {event_id, mode, weights, time_limit, dept_cap}
  → 202 {job_id, state}
  ジョブ状態 = QUEUED、経過タイマ開始

poll()（約2秒間隔）:
  GET /optimizations/{job_id}
  state が終端(SUCCEEDED/INFEASIBLE/FAILED)でなければ継続
  終端に達したら停止し、下記を表示:
    SUCCEEDED  → 割当件数、objective_value、optimality_gap、経過時間 → V-07 へ誘導
    INFEASIBLE → detail（不足診断、BR-API15、PII なし）
    FAILED     → 汎用エラーメッセージ（内部を出さない、SECURITY-09）
```

- **多重投入の防止**: ジョブが非終端の間は「実行」ボタンを無効化する。
- **画面離脱**: ポーリングは画面のライフサイクルに紐づけ、離脱時に停止する。再訪時は `job_id` があれば再開できる。

---

## 5. エラー処理方針（ステップ H）

| バックエンド応答 | フロントの挙動 |
|----------------|--------------|
| `401` | セッション失効とみなし V-01 ログインへ遷移（現在操作は破棄、再ログイン後に案内） |
| `403` | 「この操作は許可されていません」を表示（SEC-02 認可失敗、内容は出さない） |
| `400`（ドメイン規則違反 / 手動修正のハード制約違反） | `ErrorResponse.message` と `violations`（あれば制約 ID・詳細）をそのまま表示 |
| `422`（DTO 検証） | 該当フォーム項目にバックエンドのメッセージを表示 |
| `400` + `errors[]`（CSV 取込） | 行番号付きエラー一覧を表示（PII なし、BR-DM14） |
| `404` | 「対象が見つかりません」 |
| `5xx` / ネットワーク | 汎用エラーと再試行導線。スタックトレース等は存在しない（SECURITY-09） |

- **原則**: バックエンドが真実の源。フロントはメッセージを**加工せず**表示する（内部情報は元々含まれない）。

---

## 6. 申し送り（U-08 handoffs）

- **U08-H1**（Q3=A、Code Generation で実施）: U-07 に施設・小学校区の import/export エンドポイントを追加する。U-03 の `MasterDataService.import_facilities` / `export_facilities` / `import_school_districts` / `export_school_districts` は**既存**なので、U-07 側のルータ + サービス配線のみ（職員と対称）。V-03 はこれに依存する。
- **U08-H2**（Q2=A の価値提示に必要）: 現状の `AssignmentResponse` は `staff_id` / `facility_id` / `is_pinned` のみで**移動時間・費用を持たない**。割当画面（V-07）で「遠い→近い」の移動負担（SC-01 の見せ場）を数値で示すには、割当一覧エンドポイントに**割当ごとの移動時間（秒）・費用（円）を追加**する必要がある（U-02 の距離モデルからバックエンドで算出可能）。追加しない場合、V-07 で提示できる価値指標は最適化結果の `objective_value` と `optimality_gap`（V-06 由来）に限られる。**この判断は機能設計の承認時に確認する。**
- **U08-H3**（Q2=A）: 比較／削減効果レポート画面は U05-H6（`historical_assignments` / `historical_declarations` テーブル）解消後に別途実装する。`ComparisonResponse` DTO と `converters.from_domain_comparison` は U-07 に実装済みのため、テーブルとエンドポイントが入れば画面追加のみ。
- **H-5**（Application Design、Code Generation で実施）: `src/frontend/` がバックエンドユニット（`src/` 配下）を import していないことをリンタ／ビルド規則で機械的に検証する。
