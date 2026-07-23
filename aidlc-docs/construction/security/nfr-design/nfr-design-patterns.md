# NFR Design Patterns — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Design（ユニット 6 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A

---

## 概要

U-06 の NFR 設計は **7 つのパターン**。貫く思想は「**規律ではなく構造で守る**」——呼び忘れ・書き忘れ・注入し忘れが、すべて**拒否側**に倒れるようにする。

| # | パターン | 由来 |
|---|---------|------|
| DP-01 | 関門は例外で拒否（fail closed の実装形）| Q4（核心）|
| DP-02 | 利用者列挙のタイミング対策（ダミー検証）| Q1 |
| DP-03 | 監査はイベントごとに追記 + flush | Q2 |
| DP-04 | レート制限は固定ウィンドウ | Q3 |
| DP-05 | 秘密情報の非露出 | NFR-U06-S02 |
| DP-06 | ポート注入と `sqlalchemy` 禁止による強制 | NFR Req Q5 |
| DP-07 | PII 非露出の型による保証 | FD Q4, U01-H22 |

---

## DP-01: 関門は例外で拒否（Q4=A、核心、SECURITY-15）

**問題**: 真偽値を返す関門は、**呼び出し側が検査を忘れると素通り**する（fail open）。

**パターン**: **拒否を例外で表す。**

```text
SEC-03 check_source_ip(ip, config)      -> None。非許可なら IpNotAllowedError
SEC-04 check_rate_limit(ip, kind)       -> None。超過なら RateLimitExceededError
SEC-01 authenticate(session_id)         -> Principal。無効/期限切れなら AuthenticationFailedError
SEC-02 authorize(principal, action, resource) -> AuthorizationDecision   # 監査・説明用
       require_authorization(...)       -> None。拒否なら AuthorizationDeniedError  ← 通常の呼び口
```

- **戻り値を検査し忘れても通らない**。失敗の既定が「拒否」になる
- `SEC-02` のみ `AuthorizationDecision` を返す（拒否理由を監査に残すため）が、**通常の呼び口は `require_authorization`** で、拒否なら例外
- **判定不能・設定不備・ポート未注入も例外＝拒否**（「検証できないので通す」分岐を作らない）
- 例外は **U-07 が捕捉して汎用応答に変換**（SECURITY-09）

**根拠**: fail closed を「開発者が正しく書くこと」に依存させない。**書き忘れの失敗モードが拒否**になる。

---

## DP-02: 利用者列挙のタイミング対策（Q1=A, SECURITY-09）

**問題**: 利用者が存在しないとハッシュ検証をスキップし、**応答が速く返る**。メッセージが汎用でも、**タイミングでアカウントの存在が漏れる**。

**パターン**: **存在しない場合・ロック中も、ダミーのハッシュ検証を実行する。**

```text
DUMMY_HASH = <起動時に固定のダミーパスワードから生成した Argon2 ハッシュ>

login(username, password):
    account = store.find_account(username)
    if account is None:
        hasher.verify(DUMMY_HASH, password)   # 結果は捨てる。時間を均一化するためだけ
        raise AuthenticationFailedError(汎用)
    if account.locked:
        hasher.verify(DUMMY_HASH, password)   # ロック中も均一化
        raise AuthenticationFailedError(汎用)
    if not hasher.verify(account.password_hash, password):
        record_failure(...)
        raise AuthenticationFailedError(汎用)
```

**根拠**: 汎用メッセージ（BR-SEC04）だけでは**タイミングチャネル**が塞がらない。Argon2 は意図的に遅いため、検証の有無の差は特に大きい。

---

## DP-03: 監査はイベントごとに追記 + flush（Q2=A, SECURITY-14, MU-04）

**パターン**: **1 イベント = 追記モードで open → 1 行 JSON → flush → close。**

```text
append(event):
    with open(path, "a", encoding="utf-8") as f:   # "a" は chattr +a と両立
        f.write(event.to_json_line() + "\n")
        f.flush()
```

| 決定 | 根拠 |
|------|------|
| 追記モード（`"a"`）| `chattr +a` のファイルは**追記オープンのみ許可**される。上書き・切り詰めは OS が拒否 |
| イベントごとに flush | **クラッシュで監査記録を失わない**。監査記録の消失は MU-04 が狙うもの |
| 長命ハンドル + バッファを却下 | 高速だが未フラッシュ分が消える。監査は低頻度でありコストは許容 |

**根拠**: 永続性 > スループット。監査は低頻度（ログイン・割当変更・違反）である。

---

## DP-04: レート制限は固定ウィンドウ（Q3=A, NFR-S09, MU-03）

**パターン**: `(ip, 分) -> 件数` のインメモリ辞書。古いウィンドウは掃除する。

```text
check_rate_limit(ip, kind):
    window = current_minute()
    key = (ip, kind, window)
    counts[key] += 1
    if counts[key] > limit_for(kind):     # 一般 60 / ログイン 5
        raise RateLimitExceededError
    prune_old_windows()
```

**既知の性質（明記する）**: 固定ウィンドウは**境界でバースト**しうる——ウィンドウ跨ぎで一時的に上限の最大 2 倍を許す。単一サーバー・PoC の規模では許容し、必要ならスライディングウィンドウへ置換する（設計は差し替え可能）。

**根拠**: 単純・低コスト・単一ワーカーで十分。**性質を隠さず明記する**。

---

## DP-05: 秘密情報の非露出（SECURITY-06）

| 項目 | 決定 |
|------|------|
| セッション ID | `secrets.token_urlsafe(32)`（CSPRNG, 256 bit）|
| ハッシュ比較 | Argon2 の `verify`（内部で定数時間）。その他の秘密比較は `hmac.compare_digest` |
| `Account.__repr__` | **`password_hash` を伏せる**（`<redacted>`）|
| `Session.__repr__` | **セッション ID を伏せる** |
| ログ | パスワード・ハッシュ・セッション ID を**出さない** |

**根拠**: U-01 の `Staff.__repr__` が PII を redact する多層防御と同じ発想を、秘密情報に適用する。

---

## DP-06: ポート注入と `sqlalchemy` 禁止による強制（NFR Req Q5=A）

- U-06 は `SessionStorePort` / `PasswordHasherPort` を**定義**し、実装は**注入**される
- **リンタ契約が `sqlalchemy` を禁止**するため、**U-06 は物理的にセッションを DB へ書けない**
- したがって「ポートを注入する」設計は**意図ではなく強制**である（U06-H10 で非空虚性を確認）
- `PasswordHasherPort` の実装（Argon2）は U-06 が保有してよい（DB 依存がないため）。`AuditLogPort` の実装 A-05 も U-06 が保有（OS ファイル）

---

## DP-07: PII 非露出の型による保証（FD Q4, U01-H22, SECURITY-03）

- **`AuditEvent` は PII を格納するフィールドを持たない**（ID と列挙値のみ）。型として入れられない
- **U-06 は `Staff` / `Event` などの業務エンティティを import しない**——監査には ID しか要らず、業務型を持ち込むと氏名が届く
- **`reason_category` を監査ログに出さない**（U01-H22）。`AuditEvent` にそのフィールドが無い
- U-01 のリンタ契約（`shared_kernel` は `security` を import しない）と本契約により、**PII が U-06 に届かない多層防御**が完成する

---

## 該当しないパターン（Q5=A、N/A）

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| Resilience（リトライ、CB）| **N/A** | fail closed。リトライすべき外部依存がない |
| Scalability | **N/A** | 単一サーバー・単一ワーカー（A-07）。レート制限はインメモリで足りる |
| 追加ミドルウェア | **N/A** | セッションは注入されるポート、監査は OS ファイル |

---

## 拡張ルール適合サマリ

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-15**（fail closed）| ✅ | DP-01。関門は例外。未注入・判定不能も拒否 |
| **SECURITY-09**（情報漏洩）| ✅ | DP-01（汎用応答は U-07）、**DP-02（タイミング）** |
| **SECURITY-14**（監査保護）| ✅ | DP-03。追記専用 + flush |
| **SECURITY-06**（秘密情報）| ✅ | DP-05 |
| **SECURITY-03**（PII 非露出）| ✅ | DP-07。型による保証 |
| **SECURITY-12**（ハッシュ）| ✅ | Argon2id（NFR Req）。DP-02 のダミー検証も同じ hasher |
| **SECURITY-11**（レート制限・モジュール分離）| ✅ | DP-04。SEC-01/02 は専用モジュール |
| **PBT-01..10** | ✅ 検証可能 | 全パターンが P-SEC01〜09 + PBT-06 ステートフルで検証可能 |
| Resiliency | スキップ | Enabled=No |

**ブロッキング所見: なし**

---

## 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U06-H11（新規）** | `DUMMY_HASH`（タイミング均一化用、DP-02）をモジュール初期化時に生成する。ダミーパスワードは秘密ではないが、ハッシュ生成コストは起動時に一度だけ | U-06 Code Generation |
| **U06-H12（新規）** | レート制限の固定ウィンドウは**境界バースト**（最大 2 倍）を許す。必要ならスライディングウィンドウへ差し替え | 運用 / 将来 |
| U06-H9/H10 | 依存固定、リンタ契約と非空虚性確認 | U-06 Code Generation |
