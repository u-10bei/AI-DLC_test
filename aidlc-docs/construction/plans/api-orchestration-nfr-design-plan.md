# NFR Design Plan — U-07 `api-orchestration`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Design（ユニット 7 / 8）
**参照**: U-07 nfr-requirements.md, tech-stack-decisions.md（FastAPI 0.115.6 / Pydantic 2.10.4）、Functional Design 全成果物

---

## 1. スコープ

確定済みの NFR を**設計パターンと論理コンポーネント**に落とす。

**核心**: U-06 と同じ問いを HTTP 層で解く——「**書き忘れ・付け忘れが fail closed になるか**」。

---

## 2. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: 認証の適用形（**核心**, SECURITY-08, US-01）

FastAPI の慣用句は「ルートごとに `Depends(authenticate)` を付ける」ですが、**新しいルートに付け忘れると、そのルートは無防備に公開される**（fail open）。

A) **認証をミドルウェアで適用し、公開ルートを明示的な許可リストで除外する** — 認証ミドルウェアが**すべての要求**に適用され、`PUBLIC_ROUTES`（ログイン、ヘルスチェックのみ）に**明示的に列挙されたパスだけ**を通す。**新しいルートは既定で保護される**——付け忘れの失敗モードが「拒否」になる。公開したいときは意識的に許可リストへ追加する（レビューで見える）**（推奨。U-06 の DP-01 と同じ思想）**

B) ルートごとに `Depends(authenticate)` を付ける — FastAPI の慣用句だが、**付け忘れたルートが無防備**になる（fail open）。「全ルートに付けたか」を人間の注意力で担保することになる

X) Other（`[Answer]:` に記述）

[Answer]:A

---

### Question 2: ジョブの取得（claim）方式（信頼性, Q4 of FD）

ワーカーがジョブを取得する方法を確定してください（**現状は単一ワーカー**, A-07）。

A) **条件付き UPDATE で claim し、rowcount で成否を判定** — `UPDATE optimization_jobs SET state='RUNNING' WHERE id=? AND state='QUEUED'` の rowcount が 1 なら取得成功、0 なら他が先に取った。**単一ワーカー前提でも、将来ワーカーが増えたときに壊れない**。SELECT してから UPDATE すると競合する **（推奨）**

B) `SELECT ... WHERE state='QUEUED' LIMIT 1` してから `UPDATE` — 単一ワーカーなら動くが、**将来の複数ワーカーで二重実行**する（300 秒の求解が二重に走る）

X) Other

[Answer]:A

---

### Question 3: ワーカーループの形（テスト容易性, Q5 of NFR Req）

ワーカーをどう構成しますか？

A) **`step()` と `run_forever()` に分離** — `step() -> bool`（キューから 1 ジョブ取得して処理し、処理したら True）と、`run_forever()`（`step()` をポーリング間隔で繰り返す）。**テストは `step()` を同期呼び出し**するだけでよく、プロセスもスレッドも起動しない（NFR Req Q5=A）。CLI（`python -m api_orchestration.worker`）は `run_forever()` を呼ぶ **（推奨）**

B) ループを 1 つの関数に閉じる — テストからプロセス/スレッドを起動する必要があり、テストが遅く不安定になる

X) Other

[Answer]:A

---

### Question 4: DTO 変換の形（保守性, Q1 of FD）

DTO ↔ ドメイン型の変換をどう実装しますか？

A) **手書きの純関数を 1 モジュールに集約** — `converters.py` に `to_domain_*` / `from_domain_*` を集める。純関数なので**ラウンドトリップをプロパティテストできる**（P-API01）。Pydantic の `model_validate` によるドメイン型への自動変換を使わない（ドメイン型に Pydantic を混ぜないため）**（推奨。U-03 の手書きマッパと同じ思想）**

B) 変換を各ルータに散らす — 重複し、ラウンドトリップの検証が難しくなる

X) Other

[Answer]:A

---

### Question 5: 該当しないパターンの確認 + 論理コンポーネント

A) **N/A 確定 + 論理コンポーネント** — (1) Resilience: リトライ/CB なし（fail closed）。(2) Scalability: 単一サーバー・単一ワーカー（A-07）。(3) 追加ミドルウェア（Redis 等）なし——キューは DB。(4) 論理コンポーネント: `app`（FastAPI + ミドルウェア）/ ルータ群 / `dto` + `converters` / `composition`（合成ルート）/ `job_queue` / `worker` / `session_store`（`SqlSessionStore`）/ `errors`（例外ハンドラ）**（推奨）**

B) 一部該当する（`[Answer]:` に記述）

X) Other

[Answer]:A

---

## 3. 実行チェックリスト（回答分析後）

### 3.1 nfr-design-patterns.md
- [x] DP: 認証はミドルウェア + 公開ルート許可リスト（Q1、fail closed）
- [x] DP: ミドルウェア順序（SEC-03→04→01→02→05）と例外→汎用応答
- [x] DP: ジョブ claim の条件付き UPDATE（Q2）
- [x] DP: `step()`/`run_forever()` 分離（Q3）
- [x] DP: DTO 変換の純関数集約（Q4）
- [x] DP: 合成ルートによる注入（U06-H2/H3）、注入忘れの検出
- [x] DP: セキュリティヘッダ、PII 非露出

### 3.2 logical-components.md
- [x] LC: app / routers / dto / converters / composition / job_queue / worker / session_store / errors
- [x] N/A（Resilience/Scalability/追加ミドルウェア）を根拠付きで記録

### 3.3 拡張適合
- [x] SECURITY-04/05/08/09/15、PBT-01/06
- [x] N/A ルール記録、レジリエンシー無効記録

### 3.4 完了処理
- [x] 2 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
