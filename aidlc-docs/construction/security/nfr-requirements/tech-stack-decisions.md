# 技術スタック決定 — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 6 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A

---

## 1. U-01 からの継承

バックエンド全体の技術スタックは U-01 で確定済み。U-06 はこれを継承する。本文書は **U-06 固有の差分**のみを記す。

**U-01 からの持ち越し（U06-H1）を本ステージで解決する。**

---

## 2. U06-H1 の解決: パスワードハッシュ製品（Q1=A）

**`argon2-cffi`（Argon2id）を採用する。**

| 観点 | argon2-cffi（採用）| bcrypt（却下 B）| passlib（却下 C）|
|------|------------------|----------------|-----------------|
| OWASP 推奨度 | **第一推奨** | 次点 | ラッパー |
| メモリハード性 | **あり**（GPU 総当たりに強い）| なし | - |
| 入力長の制約 | なし | **72 バイトで切り捨て** | - |
| パラメータの外部化 | メモリ・反復・並列度 | コスト係数 | - |
| メンテナンス | 活発 | 活発 | **停滞気味** |
| ライセンス | MIT | Apache-2.0 | BSD |

**採用理由**: SECURITY-12 の「適応型ハッシュ」を最も強く満たす。メモリハードにより GPU による総当たりに強く、bcrypt の 72 バイト切り捨て問題がない。

**検証済み**: `argon2-cffi==23.1.0` のインストールと Argon2id のハッシュ/検証（正しいパスワードは真、誤りは `VerifyMismatchError`）を本環境で確認済み。

---

## 3. プロダクション依存（Q4=A, SECURITY-10）

| パッケージ | 用途 | バージョン固定 |
|-----------|------|:-------------:|
| `argon2-cffi` | Argon2id パスワードハッシュ | ○（`==23.1.0`）|

**これ 1 つのみ。** その他はすべて**標準ライブラリ**で実現する:

| 用途 | 標準ライブラリ |
|------|--------------|
| セッション ID 生成 | `secrets.token_urlsafe(32)`（CSPRNG, 256 bit, Q3=A）|
| 定数時間比較 | `hmac.compare_digest`（タイミング攻撃対策）|
| **IP 許可リスト（CIDR）** | `ipaddress` |
| 監査ログ（JSON Lines）| `json` |

`pip-audit` の対象、SBOM に含める（SECURITY-10）。

---

## 4. 運用パラメータの既定値（Q2=A, すべて外部化: NFR-M03）

| 項目 | 既定値 | 根拠 |
|------|-------|------|
| **セッション TTL** | **8 時間**（絶対期限）| 担当者の勤務時間。超過は再ログイン |
| **ロック閾値** | **連続 5 回失敗 → 15 分ロック** | MU-03（総当たり）。成功でリセット |
| **レート制限（一般）** | **60 req/分/IP** | NFR-S09 |
| **レート制限（ログイン）** | **5 req/分/IP** | MU-03 対策として厳しく |
| Argon2 パラメータ | OWASP 推奨値（本番）／軽量（テスト）| 実行時間の都合（Q6=A）|

**すべて `ConfigPort` で外部化し、ハードコードしない**（NFR-M03）。

---

## 5. U-06 のリンタ契約（Q5=A、**設計の構造的強制**）

| 契約 | 内容 |
|------|------|
| **R（U-06 のユニット境界）** | `security` は `shared_kernel` **のみ** import 可。`distance_cost`, `data_management`, `optimization_engine`, `comparison_report`, `api_orchestration`, `frontend` を import してはならない |
| **許可する第三者** | `argon2-cffi` |
| **禁止する第三者** | **`sqlalchemy`**, `pydantic`, `fastapi` |

### 5.1 `sqlalchemy` を禁止する理由（重要）

Functional Design Q2=A で「U-06 は `SessionStorePort` を定義するのみ、DB 実装は U-07 が注入する」と決めた。**`sqlalchemy` を禁止することで、この設計が意図ではなく強制になる**——U-06 は物理的にセッションを DB へ書けない。

これは U-02（`numpy` 禁止で純粋性を強制）、U-03（`pydantic`/`fastapi` 禁止でドメイン層を守る）と同じ規律であり、**Code Generation で非空虚性を確認する**（`import sqlalchemy` の混入で BROKEN になること）。

さらに、`security` が `Staff` を import できない構造（U-01 の R-2 と本契約）により、**個人情報が U-06 に届かない**多層防御が完成する。

---

## 6. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U06-H1（解決）** | ハッシュ = Argon2id（`argon2-cffi==23.1.0`）、TTL/ロック/レートの既定値を確定 | （本ステージで解決）|
| **U06-H9（新規）** | `argon2-cffi==23.1.0` を `pyproject.toml` に追加・固定、pip-audit/SBOM 対象に含める | U-06 Code Generation |
| **U06-H10（新規）** | `.importlinter` に U-06 契約を追加し、**`import sqlalchemy` の混入で BROKEN になること**を確認する（非空虚性）| U-06 Code Generation |
| U06-H2/H3/H4 | U-07 が SessionStore・サニタイザ・ミドルウェア順序を注入/配線 | U-07 |
