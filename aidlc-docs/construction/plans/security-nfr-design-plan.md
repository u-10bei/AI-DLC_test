# NFR Design Plan — U-06 `security`

**作成日**: 2026-07-17
**ステージ**: CONSTRUCTION - NFR Design（ユニット 6 / 8）
**参照**: U-06 nfr-requirements.md, tech-stack-decisions.md（Argon2id, sqlalchemy 禁止）、Functional Design 全成果物

---

## 1. スコープ

確定済みの NFR（Argon2id、不透明セッション、追記専用監査、deny by default、ポート注入）を**設計パターンと論理コンポーネント**に落とす。

**核心**: 「fail closed」と「PII 非露出」を、**呼び忘れ・書き忘れが起きない形**で実装すること。

---

## 2. 明確化質問

`[Answer]:` の後に記号を記入してください。すべて回答後「完了」とお知らせください。

---

### Question 1: 利用者列挙のタイミング対策（セキュリティ, SECURITY-09, MU-03）

利用者名が**存在しない**場合、ハッシュ検証を行わないと**応答が速く返り**、応答時間からアカウントの存在を推測されます（user enumeration）。

A) **存在しない場合もダミーのハッシュ検証を実行する** — 固定のダミーハッシュに対して Argon2 検証を走らせ、**応答時間を均一化**する。応答メッセージは既に汎用（BR-SEC04）だが、**タイミングでも漏らさない**。ロック中も同様に均一化 **（推奨）**

B) 存在しない場合は即座に失敗を返す — 実装は単純だが、応答時間差からアカウントの存在が漏れる

X) Other（`[Answer]:` に記述）

[Answer]:A

---

### Question 2: 監査ログの追記パターン（信頼性 / セキュリティ, SECURITY-14, MU-04）

`chattr +a`（追記専用）のファイルへ、どう書き込みますか？

A) **イベントごとに追記モードで open → 1 行書く → flush → close** — 1 イベント 1 行の JSON Lines。**書き込みごとに flush** し、プロセスクラッシュでも記録を失わない。追記モード（`"a"`）は `chattr +a` と両立する（追記専用属性のファイルは追記オープンのみ許可）。監査は低頻度（ログイン・割当変更・違反）のためコストは許容 **（推奨。永続性を優先）**

B) 長命のファイルハンドルを保持しバッファリング — 高速だが、クラッシュ時に**未フラッシュの監査記録が消える**（MU-04 の観点で望ましくない）

X) Other

[Answer]:A

---

### Question 3: レート制限のデータ構造（性能 / セキュリティ, NFR-S09, MU-03）

インメモリのレート制限をどう実装しますか？

A) **固定ウィンドウ（分単位のカウンタ）** — `(ip, 分) -> 件数` の辞書。単純・低コスト・単一ワーカーで十分。**境界でバーストしうる**（ウィンドウ跨ぎで一時的に上限の 2 倍）という既知の性質を明記する。古いウィンドウは掃除する **（推奨、PoC として妥当）**

B) **スライディングウィンドウ** — バースト問題がないが、実装とメモリのコストが上がる

X) Other

[Answer]:A

---

### Question 4: fail closed の実装形（**核心**, SECURITY-15）

「呼び忘れたら通ってしまう」設計を避ける形を確定してください。

A) **関門は例外を投げる。認可は decision を返すが `require_*` ヘルパが拒否時に例外を投げる** — (1) `SEC-03/04/01` の各関門は拒否時に**例外**（`IpNotAllowedError` 等）を送出する——戻り値を検査し忘れても素通りしない。(2) `SEC-02` は監査・説明のため `AuthorizationDecision` を返すが、**通常の呼び出し口は `require_authorization(...)` で、拒否なら例外**。(3) 例外は U-07 が捕捉し汎用応答に変換（SECURITY-09）。(4) 判定不能・設定不備・ポート未注入も**例外＝拒否** **（推奨）**

B) すべて真偽値を返す — 呼び出し側が検査を忘れると素通りする（fail open のリスク）

X) Other

[Answer]:A

---

### Question 5: 該当しないパターンの確認 + 論理コンポーネント + 設定の形

以下をまとめて確認します。

A) **N/A 確定 + 設定は frozen dataclass** — (1) Resilience: リトライ/CB なし（fail closed）。(2) Scalability: 単一ワーカー（A-07）、レート制限はインメモリ。(3) 追加ミドルウェアなし。(4) 論理コンポーネント: SEC-01 Authenticator / SEC-02 Authorizer / SEC-03 IpAllowlist / SEC-04 RateLimiter / SEC-05 InputSanitizer / S-08 AuditService / A-05 AppendOnlyFileAuditLog、ポート = SessionStorePort・PasswordHasherPort・AuditLogPort。(5) **設定は `ConfigPort`（Protocol）ではなく frozen な `SecurityConfig` dataclass を注入**する——設定は単なる値であり、振る舞いを持たないため Protocol は過剰。TTL・ロック閾値・レート上限・IP 許可リストを保持（NFR-M03）**（推奨）**

B) 一部該当する / 設定は Protocol のまま（`[Answer]:` に記述）

X) Other

[Answer]:A

---

## 3. 実行チェックリスト（回答分析後）

### 3.1 nfr-design-patterns.md
- [x] DP: 関門は例外で拒否（Q4、fail closed を呼び忘れ耐性のある形に）
- [x] DP: 利用者列挙のタイミング対策（Q1、ダミー検証）
- [x] DP: 監査の追記パターン（Q2、flush、chattr +a との両立）
- [x] DP: レート制限の固定ウィンドウ（Q3、バースト性質の明記）
- [x] DP: 秘密情報の非露出（`__repr__`、定数時間比較、CSPRNG）
- [x] DP: ポート注入（SessionStore/PasswordHasher）と `sqlalchemy` 禁止による強制
- [x] DP: PII 非露出の型による保証（`AuditEvent` に PII フィールドを持たせない）

### 3.2 logical-components.md
- [x] LC: SEC-01〜05, S-08 AuditService, A-05 AppendOnlyFileAuditLog
- [x] ポート（SessionStorePort, PasswordHasherPort, AuditLogPort）と `SecurityConfig`（Q5）
- [x] N/A（Resilience/Scalability/追加ミドルウェア）を根拠付きで記録
- [x] U-07 による配線（ミドルウェア順序 SEC-03→04→01→02→05）

### 3.3 拡張適合
- [x] SECURITY-15（fail closed）、SECURITY-09（タイミング含む情報漏洩）、SECURITY-14（監査）、SECURITY-06（秘密情報）
- [x] PBT: パターンが P-SEC01〜09 + PBT-06 ステートフルで検証可能
- [x] N/A ルール記録、レジリエンシー無効記録

### 3.4 完了処理
- [x] 2 成果物作成、`aidlc-state.md` 更新、適合サマリ
- [ ] 標準の 2 択完了メッセージを提示し承認を待つ
