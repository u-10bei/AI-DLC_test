# NFR Requirements Plan — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 6 / 8）
**参照**: U-06 Functional Design 全成果物、U-01 tech-stack-decisions.md、`requirements.md` v1.4（NFR-S01〜S10）

---

## 1. スコープ

**U-01 からの持ち越し（U06-H1）を本ステージで解決する**: パスワードハッシュ製品、セッション TTL、ロック閾値、レート上限。

バックエンド全体の技術スタックは U-01 で確定済み。U-06 はこれを継承する。

---

## 2. Step 1: Functional Design の分析

| カテゴリ | 該当 | 内容 |
|---------|:----:|------|
| **Tech Stack** | **該当（U06-H1）** | パスワードハッシュ製品の選定。セッション ID 生成 |
| **セキュリティ** | **該当（中核）** | 本ユニットが SECURITY 拡張の実体 |
| 性能 | 該当（限定）| ハッシュのコスト係数（適応型ハッシュは意図的に遅い）。レート制限はインメモリ |
| 信頼性 | 該当 | fail closed、セッション失効、ロック |
| 保守性 | 該当 | 依存の固定、リンタ契約（**ポート設計の構造的強制**）|
| スケーラビリティ / 可用性 | N/A | 単一サーバー・単一ワーカー（A-07）、レジリエンシー無効 |

---

## 3. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: パスワードハッシュ製品（Tech Stack, **U06-H1**, SECURITY-12）

NFR-S05 / SECURITY-12 は「パスワードは**適応型ハッシュ**（Argon2 / bcrypt 等）で保存する」と定めます。

A) **`argon2-cffi`（Argon2id）** — **OWASP の第一推奨**。メモリハードで GPU 総当たりに強い。MIT ライセンス。パラメータ（メモリ・反復・並列度）を設定外部化できる。追加依存 1 つ **（推奨）**

B) **`bcrypt`** — 実績豊富で枯れている。ただしメモリハードではなく、**パスワードが 72 バイトで切り捨てられる**既知の制約がある

C) **`passlib`** — 複数アルゴリズムのラッパー。近年メンテナンスが停滞気味で、依存を増やす割に利点が薄い

X) Other（`[Answer]:` に記述）

[Answer]:A

---

### Question 2: セッション TTL・ロック閾値・レート上限の既定値（信頼性 / セキュリティ, NFR-M03）

具体値を確定してください（すべて**設定として外部化**します, NFR-M03）。

A) **業務実態に合わせた既定値** — (1) **セッション TTL = 8 時間（絶対期限）**: 担当者の勤務時間を想定。期限超過は再ログイン。(2) **ロック閾値 = 連続 5 回失敗で 15 分ロック**（MU-03）。成功でリセット。(3) **レート制限 = 一般 60 req/分/IP、ログインは 5 req/分/IP**（総当たり対策として厳しく）。すべて `ConfigPort` で外部化し、ハードコードしない **（推奨）**

B) 別の値（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 3: セッション ID の生成（セキュリティ, SECURITY-06）

不透明なセッション ID（Q2=A of FD）をどう生成しますか？

A) **標準ライブラリ `secrets.token_urlsafe(32)`** — 暗号論的に安全な擬似乱数（CSPRNG）。256 ビットのエントロピー。追加依存なし。推測不能 **（推奨）**

B) `uuid4()` — CSPRNG ベースだが実装依存の余地があり、セッション ID には `secrets` が明確に適切

X) Other

[Answer]:A

---

### Question 4: プロダクション依存（Tech Stack, SECURITY-10）

U-06 が追加するプロダクション依存を確定してください。

A) **ハッシュライブラリ 1 つのみ**（Q1=A なら `argon2-cffi`）— その他はすべて**標準ライブラリ**で実現する: セッション ID = `secrets`、定数時間比較 = `hmac.compare_digest`、**IP 許可リスト = `ipaddress`（CIDR 対応）**、JSON Lines = `json`。バージョン固定 + pip-audit + SBOM（SECURITY-10）**（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 5: U-06 のリンタ契約（**重要**, 保守性 / 設計の強制）

U-06 のユニット境界を確定してください。**Functional Design Q2=A（SessionStorePort を U-07 が注入）を構造的に強制できます。**

A) **`shared_kernel` のみ許可し、`sqlalchemy` を明示的に禁止** — (1) ユニット境界: `security` は `shared_kernel` のみ import 可。`distance_cost`/`data_management`/`optimization_engine`/`comparison_report`/`api_orchestration`/`frontend` を禁止。(2) 第三者: `argon2-cffi` を許可、**`sqlalchemy` を禁止**、`pydantic`/`fastapi` を禁止。**`sqlalchemy` の禁止により「U-06 はセッションを自分で DB に書けない」ことが構造的に保証**され、`SessionStorePort` の注入設計が意図ではなく**強制**になる **（推奨）**

B) 別方針（`[Answer]:` に記述）

X) Other

[Answer]:A

---

### Question 6: N/A の確認とテスト戦略

以下をまとめて確認します。

A) **N/A 確定 + 実ライブラリでのテスト** — (1) スケーラビリティ N/A（単一サーバー、レート制限はインメモリ）。(2) 可用性 N/A（レジリエンシー無効）。(3) テスト: **ハッシュは実ライブラリを使う**（モックしない——`verify(hash(p))` の往復が検証対象, P-SEC08）。**PBT-06 ステートフルテスト**でセッション/ロックの状態機械を検証。ハッシュのコスト係数はテストでは軽く（実行時間のため）、本番既定は OWASP 推奨値 **（推奨）**

B) 一部該当する（`[Answer]:` に記述）

X) Other

[Answer]:A

---

## 4. 実行チェックリスト（回答分析後）

### 4.1 nfr-requirements.md
- [x] 該当 NFR（セキュリティ中核、性能=ハッシュコスト、信頼性、保守性）を定義
- [x] N/A（スケーラビリティ、可用性）を根拠付きで記録
- [x] Q2 の既定値（TTL・ロック・レート）と外部化（NFR-M03）
- [x] テスト戦略（Q6、実ライブラリ、PBT-06）

### 4.2 tech-stack-decisions.md
- [x] U-01 継承の明記
- [x] Q1 のハッシュ製品確定（**U06-H1 解決**）と根拠
- [x] Q3 のセッション ID 生成、Q4 の依存一覧（固定, SECURITY-10）
- [x] Q5 のリンタ契約（**`sqlalchemy` 禁止でポート設計を強制**）

### 4.3 拡張ルール適合確認
- [x] SECURITY-12（適応型ハッシュ）、SECURITY-06（秘密情報）、SECURITY-10（依存固定）
- [x] PBT-09（Hypothesis 継承）、PBT-06（ステートフル）
- [x] N/A ルールの記録、レジリエンシー無効の記録

### 4.4 完了処理
- [x] 2 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
