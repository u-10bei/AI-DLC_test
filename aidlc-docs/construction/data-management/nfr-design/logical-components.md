# Logical Components — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Design（ユニット 3 / 8）
**回答**: Q6=A（追加インフラ論理コンポーネントは導入しない）

---

## 概要

U-03 の論理コンポーネントは **5 つ**に限る。メッセージキュー・外部キャッシュ・サーキットブレーカは導入しない（Q6=A）。すべて `src/data_management/` 配下の Python モジュールで、外部ミドルウェアを追加しない。

```
              ┌─────────────────────────────────────────────┐
              │  U-07 api-orchestration（呼び出し側）          │
              │  ポート P-* 経由でサービスを呼ぶ               │
              └───────────────────┬─────────────────────────┘
                                  │ (トランザクション管理はしない, DP-01)
                                  v
        ┌─────────────────────────────────────────────────────┐
        │  LC-04 CsvImportService / 各アプリケーションサービス   │
        │  （トランザクション境界を所有, DP-01）                 │
        └───────┬──────────────────────────┬──────────────────┘
                │ uses                      │ uses
                v                           v
        ┌───────────────┐          ┌──────────────────┐
        │ LC-02         │  uses    │ LC-03 Mapper      │
        │ Repository    │─────────>│ 行 ↔ frozen 型     │
        │ (P-* 実装)     │          │ (__post_init__)   │
        └───────┬───────┘          └──────────────────┘
                │ uses
                v
        ┌───────────────────────────────┐
        │ LC-01 Engine / SessionFactory  │
        │ シングルトン, connect で PRAGMA  │
        └───────┬───────────────────────┘
                │
                v
        ┌───────────────────────────────┐        ┌──────────────────┐
        │ SQLite (PoC) / PostgreSQL (本番)│<───────│ LC-05 Migration   │
        │ 暗号化ボリューム (SECURITY-01)   │ 適用    │ Runner (Alembic)  │
        └───────────────────────────────┘        └──────────────────┘
```

（テキスト代替: U-07 が CsvImportService/各サービスを呼ぶ。サービスは Repository を使い、Repository は Mapper と Engine/SessionFactory を使う。Engine は SQLite/PostgreSQL に接続。MigrationRunner はスキーマを DB に適用する。）

---

## LC-01: Engine / SessionFactory

| 項目 | 内容 |
|------|------|
| 責務 | SQLAlchemy `Engine` と `Session` の生成・供給。接続確立ごとの PRAGMA 発行 |
| 実装 | プロセス内シングルトン。`sessionmaker` を保持 |
| PRAGMA | `connect` イベントで方言分岐（NFR Requirements Q4=A）。SQLite でのみ WAL / `busy_timeout>=5000` / `foreign_keys=ON` を発行（U01-H15） |
| `echo` | **全環境で `False`**（DP-05, SECURITY-03） |
| コネクションプール | 既定の小サイズで固定。単一ワーカー（A-07）のためチューニングしない（Q6=A, N/A Scalability） |
| 接続文字列 | 環境変数/設定から取得。SQLite → PostgreSQL は文字列変更のみ（U01-H18） |

---

## LC-02: Repository（集約単位、P-* ポート実装）

| 項目 | 内容 |
|------|------|
| 責務 | Application Design のポート（P-01..P-07）を実装。ドメイン型を受け取り/返し、SQL を隠蔽 |
| 実装 | 集約（職員、施設、事象、従事可否申告、割当、距離キャッシュ）ごとの Repository。SQLAlchemy Core の式言語で組む |
| クエリ | パラメータ化（DP-07, SECURITY-05）。有効な申告は相関サブクエリ `MAX(declared_at)`（NFR Requirements Q3=A） |
| 一括挿入 | `executemany`（DP-03, NFR-P04） |
| トランザクション | **自身では commit しない**。呼び出し元のサービスが渡す `Session` を使う（DP-01） |
| 読み込み | LC-03 Mapper を介してドメイン型に変換。fail closed（DP-02） |

---

## LC-03: Mapper（行 ↔ frozen ドメイン型）

| 項目 | 内容 |
|------|------|
| 責務 | DB 行とドメイン型（frozen dataclass）の相互変換 |
| 書き込み | ドメイン型 → 行 dict（`executemany` 用） |
| 読み込み | 行 → ドメイン型。`__post_init__` を再実行（DP-06）。拒否されたら `DataIntegrityError`（DP-02, ID のみ、PII なし） |
| 依存 | ドメイン型（U-01 `shared_kernel`）のみ。SQLAlchemy の宣言的マッピングを使わない（手書き） |

---

## LC-04: CsvImportService / アプリケーションサービス

| 項目 | 内容 |
|------|------|
| 責務 | ユースケース（CSV インポート、マスタ更新、割当保存など）を実装。**トランザクション境界を所有**（DP-01） |
| CSV インポート | 2 相・単一パス（DP-03）。第 1 相: 標準ライブラリ `csv` で解析 + 全検証（全エラー蓄積、BR-DM02）。第 2 相: 1 トランザクションで `executemany` 保存 |
| マスタ更新 + 再計算 | 小学校区マスタ更新 + 距離キャッシュ全再計算を**同一トランザクション**で原子的に実行（DP-04）。距離計算は U-02 の純関数を呼ぶ |
| エラー | `CsvImportError`（全エラーを行番号付きで保持）。個人情報を含めない（BR-DM14, DP-05） |
| トランザクション | `session_factory.begin()` で境界を張り、正常時 commit / 例外時 rollback |

---

## LC-05: MigrationRunner（Alembic ラッパ）

| 項目 | 内容 |
|------|------|
| 責務 | Alembic マイグレーションの適用。スキーマ（10 テーブル、U-03 Functional Design）を DB に構築 |
| 初期化 | U-03 で Alembic を初期化（U-03 Functional Design で確定）。初期リビジョンを作成 |
| 本番移行 | 同一マイグレーションを PostgreSQL に適用（U01-H18）。方言固有 SQL を書かない |
| テスト | 各テストのインメモリ SQLite にマイグレーションを適用して構築（NFR Requirements Q5=A, U03-H8） |

---

## 該当しない論理コンポーネント（Q6=A、N/A）

| コンポーネント | 判定 | 根拠 |
|--------------|:----:|------|
| メッセージキュー（Redis 等）| **N/A** | 非同期ジョブキューは DB ベースで **U-07 が所有**。U-03 は外部キューを持たない |
| 外部キャッシュ層（Redis/Memcached）| **N/A** | 距離キャッシュは **DB テーブル**（`distance_cache`）。別のキャッシュミドルウェアを追加しない |
| サーキットブレーカ | **N/A** | fail closed を採用（DP-02）。保護すべき不安定な外部依存がない |
| ロードバランサ / 複数インスタンス | **N/A** | 単一サーバー・単一ワーカー（A-07） |
| コネクションプールのチューニング層 | **N/A** | 既定の小サイズで固定（Scalability N/A） |

---

## 依存とポートの整合

- U-03 は `shared_kernel`（U-01）と `distance_cost`（U-02）のみを（ユニットとして）import する（リンタ契約 R）
- U-03 は Application Design のポート P-01..P-07 を LC-02 Repository で実装する
- U-07 は P-* 経由で LC-04 サービスを呼ぶ。**トランザクションを管理しない**（DP-01、ポート境界の維持）
- プロダクション依存は `sqlalchemy`, `alembic` のみ（NFR Requirements、SECURITY-10）

---

## 拡張ルール適合サマリ（論理コンポーネント観点）

| ルール | 判定 | 根拠 |
|--------|------|------|
| SECURITY-01（保存時暗号化）| ✅ | LC-01 の接続先 DB は暗号化ボリューム上 |
| SECURITY-03（PII 非露出）| ✅ | LC-01 `echo=False`、LC-03/LC-04 のエラーは ID のみ |
| SECURITY-05（パラメータ化）| ✅ | LC-02 は Core 式言語 |
| SECURITY-10（サプライチェーン）| ✅ | 追加コンポーネントは `sqlalchemy`/`alembic` のみ（固定済み）。外部ミドルウェアを増やさない |
| SECURITY-15（fail closed）| ✅ | LC-03/LC-04 が fail closed |
| Scalability / Resilience | N/A | Q6=A |

**ブロッキング所見: なし**
