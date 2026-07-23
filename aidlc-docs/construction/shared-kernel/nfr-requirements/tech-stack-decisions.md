# 技術スタック決定 — U-01 `shared-kernel`（バックエンド全体を拘束）

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - NFR Requirements（ユニット 1 / 8）

---

## 0. 拘束範囲

本システムは**モノリス**（Units Generation Q1=A）であり、バックエンドの全ユニットが同一の実行環境を共有する。したがって、以下の決定は **U-01 〜 U-07 のすべてを拘束する**。

**本文書で決定しないもの**:

| 決定事項 | 決定するユニット |
|---------|----------------|
| MILP ソルバーの具体的な製品、発見的解法の要否 | **U-04** optimization-engine（申し送り H-3） |
| セッションストア、パスワードハッシュアルゴリズム | **U-06** security |
| フロントエンドの言語・フレームワーク・PBT フレームワーク | **U-08** frontend |

---

## 1. 決定一覧

| # | 項目 | 決定 | 出典 |
|---|------|------|------|
| 1 | 言語 | **Python** | Q1=A |
| 2 | Web フレームワーク | **FastAPI** | Q2=A |
| 3 | データベース（PoC） | **SQLite** | Q3 |
| 3' | データベース（実運用） | **PostgreSQL** | Q3 |
| 4 | PBT フレームワーク | **Hypothesis** | Q4=A（PBT-09、ブロッキング） |
| 5 | 非同期ジョブ基盤 | **DB バックエンドのジョブキュー** | Q5=A, Follow-up Q2=A |
| 6 | エラー処理 | **例外を送出する** | Q6=A（U01-H14 の解消） |
| 7 | `costYen` の数値型 | **倍精度浮動小数点（`float`）** | Q7=A |
| 8 | 列挙値 | **最小限の値を定義し、未知の値を拒否する** | Q8=A（U01-H9 の解消） |
| 9 | パッケージ管理 | **`uv` または `Poetry` + ロックファイル** | Q9=A |
| 10 | 監査ログの保存先 | **OS レベルの追記専用ファイル（JSON Lines + `chattr +a`）** | Follow-up Q1=A |
| 11 | 保存時暗号化 | **ファイルシステム / ディスクレベル** | Follow-up Q3=A |
| 12 | DB 抽象化 | **SQLAlchemy Core / ORM + Alembic** | Follow-up Q4=A |
| 13 | 型チェック・リンタ | **`mypy` strict + リンタ規則 R-1〜R-6 を CI で強制** | Q11=A |

---

## 2. 決定 1: 言語 — Python

### 選定理由

**第一の選定基準は MILP ソルバーの利用可能性である。** NFR-P02 は最大 40 万の 0-1 決定変数を制限時間 300 秒内に解くことを要求する。**この要件を満たせない言語は失格である。**

| 言語 | MILP ソルバー | 判定 |
|------|-------------|------|
| Python | OR-Tools（CP-SAT / SCIP）、PuLP、Pyomo、python-mip | **合格。選択肢が最も豊富で、NFR-M01 の差し替えが容易** |
| Java | OR-Tools（Java バインディング）、OptaPlanner | 合格 |
| TypeScript / Node.js | javascript-lp-solver は小規模問題向け | **失格。40 万変数は現実的でない** |
| Go | gonum に MILP なし | **失格** |

**第二の選定基準は PBT フレームワークの成熟度である。** PBT-09 はブロッキング制約であり、カスタム生成器・自動シュリンキング・シード再現性を備えたフレームワークが必須である。

Python の **Hypothesis** は、シュリンキング品質とステートフルテスト対応において最高水準にある。Java の jqwik も良好だが一段落ちる。

### 却下した代替案

- **Java**: OR-Tools と OptaPlanner が利用可能であり、真剣な候補だった。庁内に Java の保守経験がある場合は再考の余地がある。PBT フレームワーク（jqwik）と数理最適化エコシステムの厚みで Python に劣ると判断した
- **TypeScript / Go**: NFR-P02 を満たす MILP ソルバーが存在しない

### 「Python は遅い」という懸念について

**本案件には当たらない。**

1. **最適化計算の実体は OR-Tools の C++ コアが実行する。** Python はモデルの構築とソルバーの呼び出しのみを担う
2. **距離行列の事前計算は最大 1 万要素**である。距離キャッシュを `(小学校区, 小学校区)` でキーするため（Application Design Q4=A）、想定されていた 40 万要素より 1〜2 桁小さい。NumPy でベクトル化すれば一瞬で終わる
3. **CSV 2,000 行の処理（NFR-P04、30 秒以内）**は、標準ライブラリで十分に達成できる

**NFR-P02 のボトルネックは言語ではなくソルバーである。** ソルバーの選定と実測は U-04 の責務である（H-3）。

### バージョン

**サポート中の Python バージョンを使用する**（SECURITY-09: 「ランタイム、フレームワーク、OS イメージは現行のサポート中バージョンを使用すること」）。具体的なパッチバージョンはロックファイルで固定する（SECURITY-10）。

---

## 3. 決定 2: Web フレームワーク — FastAPI

### 選定理由

- **型注釈に基づく自動バリデーション**（Pydantic）が SECURITY-05（入力検証）と親和的である。型検査・長さ上限・書式検証を宣言的に記述でき、検証漏れが起こりにくい
- OpenAPI スキーマを自動生成する。U-08 frontend が API 契約を機械的に取得できる（NFR-M05）
- REST（JSON over HTTP）に特化しており、本システムの要件（Application Design Q8=A）と一致する

### 却下した代替案

- **Django + DRF**: 管理画面・ORM・認証を同梱するが、本 PoC には不要な部分が多い。加えて、認証を Django の仕組みに委ねると `SEC-01 AuthenticationModule` の隔離（SECURITY-11）が曖昧になる
- **Flask**: 最小構成だが、SECURITY-04（HTTP セキュリティヘッダ）や入力検証を自前で積み上げる必要があり、検証漏れのリスクが高い

### SECURITY-04 への対応

FastAPI はセキュリティヘッダを既定で設定しない。**ミドルウェアで明示的に設定する必要がある**（`Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`）。**U-07 api-orchestration の NFR Design で具体化する。**

---

## 4. 決定 3: データベース — SQLite（PoC）/ PostgreSQL（実運用）

### PoC で SQLite を採用することの帰結

SQLite の選択は、3 つの統制の実現手段を変更する。**いずれも解決済みである。**

| 統制 | PostgreSQL での実現 | **SQLite での実現（採用）** |
|------|-------------------|--------------------------|
| **SECURITY-14** 監査ログの改竄防止 | ロールと権限（`REVOKE DELETE, UPDATE`） | **OS レベルの追記専用ファイル**（決定 10） |
| **SECURITY-01** 保存時暗号化 | クラスタレベル / カラムレベル暗号化 | **ファイルシステム / ディスクレベル暗号化**（決定 11） |
| **ジョブキューの同時書き込み** | MVCC により競合しにくい | **WAL モード + `busy_timeout`**（決定 5、必須設定） |

**SQLite にはユーザーもロールも存在しない。** ファイルを開ける者は、その中のあらゆるテーブルを `DELETE` も `DROP` もできる。したがって「アプリケーションのアカウントに削除権限を与えない」という Application Design Q6=A の統制は、**DB 内では実現できない**。決定 10 がこれを解決する。

### 移行方針（Follow-up Q4=A）

SQLite → PostgreSQL の移行を安価に保つため、以下を**必須**とする。

- **SQLAlchemy Core / ORM** を用い、生の SQL を直接記述しない
- **Alembic** でスキーマのマイグレーションを管理する
- **SQLite 固有の SQL を使わない**
- **SQLite の動的型付けに依存しない**（型を明示する）

これにより、移行は**接続文字列の変更とマイグレーションの再適用**で済む。

**この方針は U-03 data-management を拘束する**（申し送り U01-H18）。

---

## 5. 決定 4: PBT フレームワーク — Hypothesis（PBT-09、ブロッキング制約）

### PBT-09 の要求と、Hypothesis の適合

| PBT-09 の要求 | Hypothesis の対応 |
|--------------|------------------|
| ドメイン型のカスタム生成器 | `@st.composite` によるカスタム戦略。U-01 の 8 種のドメイン生成器を実装できる |
| 失敗ケースの自動シュリンキング | 内蔵。最小の反例まで縮約する |
| シードによる再現性 | `--hypothesis-seed` オプション。失敗時にシードを出力する |
| 既存のテストランナとの統合 | pytest と統合 |

**プロジェクトの依存関係に含める**（PBT-09 の要求）。

### U-01 が提供する 8 種のドメイン生成器（PBT-07）

`genCoordinates`, `genSchoolDistrict`, `genStaff`, `genFacility`, `genAvailabilityDeclaration`, `genObjectiveWeights`, `genTravelParameters`, `genAssignmentProblem`。

すべて `@st.composite` で実装し、`tests/shared-kernel/generators.py` に集約して**全ユニットのテストから再利用する**。PBT-07 は「生成器の定義を集約し、再利用可能にすること」を要求する。

### ステートフルテスト（PBT-06）

Hypothesis の `RuleBasedStateMachine` を用いる。`Event` のステータス遷移（U-03）とジョブのライフサイクル（U-04）が対象になりうる。**該当ユニットの Functional Design で判断する。**

### フロントエンド

U-08 frontend の PBT フレームワークは、U-08 の NFR Requirements で選定する（申し送り U01-H20）。PBT-09 は「複数言語を用いる場合、PBT 適用対象のコードを持つ各言語でフレームワークを選定すること」を要求する。

---

## 6. 決定 5: 非同期ジョブ基盤 — DB バックエンドのジョブキュー

ジョブ状態を DB のテーブルに保持し、ワーカープロセスがポーリングする。**追加のミドルウェア（Redis 等）を導入しない。**

### SQLite 上での必須設定（Follow-up Q2=A）

**推奨ではなく必須である。**

| 設定 | 値 | 理由 |
|------|----|------|
| `PRAGMA journal_mode` | `WAL` | 読み取りと書き込みを並行させる |
| `PRAGMA busy_timeout` | 5000 ms 以上 | 書き込み競合時に即座に失敗せず待機する |
| `PRAGMA foreign_keys` | `ON` | SQLite は既定で外部キー制約を強制しない |

**加えて**: 最適化の計算は**トランザクション外で実行する**。300 秒の書き込みトランザクションは、SQLite の単一ライタ制約により API を停止させる（申し送り U01-H19）。

### 却下した代替案

- **Celery + Redis**: 実績ある構成だが、単一サーバー（A-07）の PoC に Redis の運用を追加する必要がない
- **プロセス内スレッド**: プロセス再起動でジョブが失われ、US-20（進捗のポーリング）が脆くなる

---

## 7. 決定 6: エラー処理 — 例外を送出する（U01-H14 の解消）

生成時バリデーションの失敗（BR-01〜BR-07）で、`ValueError` のサブクラスを送出する。

```text
DomainError（基底）
├── InvalidCoordinatesError
├── AllWeightsZeroError / NegativeWeightError
├── QualificationRequirementExceedsHeadcountError
├── DuplicateQualificationRequirementError
├── InvalidTravelParametersError
├── InconsistentDeclarationError
├── NonDemotableConstraintViolationError
├── InvalidStateTransitionError
└── AmbiguousDeclarationError
```

**SECURITY-15 への対応**: `U-07 api-orchestration` にグローバルエラーハンドラを設置し、`DomainError` を捕捉して**汎用エラーメッセージ**を返す。スタックトレース・内部パス・フレームワークバージョンを含めない（SECURITY-09）。**エラーメッセージに職員の氏名・居住小学校区を含めない**（SECURITY-03）。

### 却下した代替案

**結果型（`Result<T, E>`）**: 明示的だが、Python の慣用に馴染まない。型チェッカで網羅性を強制する必要があり、記述が冗長になる。

---

## 8. 決定 8: 列挙値（U01-H9 の解消）

Q8=A により、**最小限の値を定義し、CSV インポート時に未知の値を拒否する**（fail closed、SECURITY-15）。

| 型 | 値 |
|----|----|
| `Position`（役職） | `管理職`, `一般職` |
| `JobType`（職種） | `事務職`, `技術職`, `保育士`, `保健師` |
| `Qualification`（保有資格） | `防災士`, `救急救命士` |
| `EventType`（イベント種別） | `災害時避難所応援`, `選挙事務`, `その他` |
| `ReasonCategory`（従事可否の理由区分） | `休暇`, `育児・介護`, `健康上の配慮`, `その他` |
| `EventStatus`（イベント状態） | `準備中`, `申告受付中`, `割当計算済`, `確定` |
| `SolverStatus` | `Optimal`, `TimeLimitReached`, `Cancelled` |

**制約 C3 との関係**: 「責任者は管理職に限る」という要件は、`Facility.qualificationRequirements` に `(管理職, N)` を指定することで表現する。

**実データとの突合**: 上記は暫定値である。**実際の職種・役職・資格の一覧が提供された時点で更新する。** 列挙型であるため、未知の値は CSV インポート時に拒否され、サイレントに取り込まれることはない。

---

## 9. 決定 9: パッケージ管理と依存の固定（SECURITY-10）

| 要求（SECURITY-10） | 実現手段 |
|-------------------|---------|
| 依存をロックファイルで固定し、バージョン管理にコミットする | `uv.lock` または `poetry.lock` |
| 脆弱性スキャンを CI に組み込む | `pip-audit` |
| SBOM を生成する | `cyclonedx-py` |
| `latest` タグを使わない | すべての依存を厳密なバージョンで固定する |
| 未使用の依存を含めない | 定期的に棚卸しする |
| 信頼できるレジストリのみを使う | PyPI（公式）のみ |

---

## 10. 決定 10: 監査ログの保存先 — OS レベルの追記専用ファイル

**JSON Lines 形式のファイルに追記し、Linux の追記専用属性（`chattr +a`）を付与する。**

| 操作 | `chattr +a` を付与したファイル |
|------|---------------------------|
| 末尾への追記 | **可能** |
| 既存行の書き換え | 不可 |
| 切り詰め（truncate） | 不可 |
| 削除・改名 | 不可 |

`CAP_LINUX_IMMUTABLE` を持たないアプリケーションプロセスは、**追記のみ可能**である。

### この設計の利点

1. **二重の防御**（SECURITY-11、defense in depth）: `P-04 AuditLogPort` が削除・更新のメソッドを定義しない（型レベル）ことに加え、OS が強制する
2. **PoC と実運用で同一の仕組みが使える**。DB を PostgreSQL へ移行しても、監査ログの統制を再設計しなくてよい

### 制約と、それに伴う要件

- 追記専用ファイルは、アプリケーションからローテーション・切り詰めができない
- **SECURITY-14 は最低 90 日の保持を要求する。** 保持期間の管理は、アプリケーション外の特権プロセス（cron 等）が行う
- ファイルシステムが `chattr +a` に対応すること（ext4, XFS 等）。属性の付与には root 権限が必要

**Infrastructure Design の対象**（申し送り U01-H16）。

---

## 11. 依存関係の一覧（暫定）

**具体的なバージョンは Code Generation ステージでロックファイルに固定する。`latest` は使わない（SECURITY-10）。**

| 用途 | パッケージ | 備考 |
|------|-----------|------|
| Web フレームワーク | `fastapi` | 決定 2 |
| ASGI サーバー | `uvicorn` | |
| バリデーション | `pydantic` | SECURITY-05 |
| DB 抽象化 | `sqlalchemy` | 決定 12 |
| マイグレーション | `alembic` | 決定 12 |
| ~~数値計算~~ | ~~`numpy`~~ | ~~距離行列の事前計算~~ **← U-02 NFR Requirements Q1=A で不採用。距離行列は最大約2万回の計算で素朴なループでも1秒未満のため、numpy は不要。U-02 のプロダクション依存はゼロを維持する** |
| テストランナ | `pytest` | |
| **PBT フレームワーク** | **`hypothesis`** | **PBT-09（ブロッキング）** |
| 型チェッカ | `mypy` | 決定 13 |
| リンタ・フォーマッタ | `ruff` | 決定 13、リンタ規則 R-1〜R-6 |
| 脆弱性スキャン | `pip-audit` | SECURITY-10 |
| SBOM 生成 | `cyclonedx-py` | SECURITY-10 |
| **MILP ソルバー** | **未決定** | **U-04 が選定する（H-3）** |
| **パスワードハッシュ** | **未決定** | **U-06 が選定する** |

---

## 12. 未決定事項（後続ユニットが決定する）

| 決定事項 | 決定するユニット | 理由 |
|---------|----------------|------|
| MILP ソルバーの製品（OR-Tools CP-SAT / SCIP / PuLP + CBC など） | **U-04** | 40 万変数に対する実測が必要（H-3）。本ステージでは「選択肢が豊富な言語を選ぶ」ところまで |
| 発見的解法（`A-03b HeuristicSolverAdapter`）の要否 | **U-04** | 厳密解法の実測結果に依存する |
| セッションストア（DB / インメモリ） | **U-06** | |
| パスワードハッシュアルゴリズム（Argon2 / bcrypt） | **U-06** | SECURITY-12 |
| フロントエンドの言語・フレームワーク | **U-08** | |
| フロントエンドの PBT フレームワーク | **U-08** | PBT-09 は言語ごとに適用される（U01-H20） |
