# NFR Design Patterns — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - NFR Design（ユニット 3 / 8）
**回答**: Q1=A, Q2=A, Q3=A, Q4=A, Q5=A, Q6=A

---

## 概要

NFR Design は、U-03 の NFR 要件を **7 つの設計パターン**に落とし込む。すべてのパターンは **fail closed**（誤ったデータで続行しない）と **個人情報の非露出**を貫く。

| # | パターン | 由来する NFR | 主根拠 |
|---|---------|-------------|--------|
| DP-01 | サービス所有のトランザクション境界 | 信頼性（原子性）| Q1=A, BR-DM01 |
| DP-02 | DB 復元時の fail-closed 再検証 | 信頼性 / セキュリティ | Q2=A, SECURITY-15 |
| DP-03 | CSV 2 相・単一パス・一括挿入 | 性能 | Q3=A, NFR-P04, BR-DM02 |
| DP-04 | 距離キャッシュの原子的全再計算 | 一貫性 | Q4=A |
| DP-05 | 永続化層の個人情報非露出 | セキュリティ | Q5=A, SECURITY-03 |
| DP-06 | 手書きマッパ（行 ↔ frozen ドメイン型）| 信頼性 | U03 Functional Design |
| DP-07 | パラメータ化クエリの構造的保証 | セキュリティ | SECURITY-05 |

---

## DP-01: サービス所有のトランザクション境界（Q1=A）

**問題**: 書き込み操作の原子性（BR-DM01）を、どこで保証するか。

**パターン**: **アプリケーションサービスのメソッドがトランザクションを所有する。**

- 各サービスメソッドが 1 つの `Session` を開き、正常終了で `commit`、例外で `rollback` する
- CSV インポートサービスは「解析 + 検証 + 保存」を **1 トランザクション**に包む
- 呼び出し側（U-07）は**トランザクションを管理しない**。サービスメソッドを呼ぶだけ

```
# 概念（Code Generation で実装）
def import_staff_csv(raw_bytes) -> ImportResult:
    rows = parse(raw_bytes)                 # DB に触れない
    errors = validate_all(rows)             # DB に触れない、全エラー蓄積
    if errors:
        raise CsvImportError(errors)        # 保存前に fail closed
    with session_factory.begin() as session:   # ← トランザクション境界
        repo.bulk_insert_staff(session, rows)   # executemany
    # ブロックを抜けると commit。例外なら自動 rollback
```

**根拠**:
- **原子性が構造的**になる。`with ... begin()` を抜けるまで commit されない。1 行でも保存で失敗すれば全体がロールバックし、DB はインポート前と完全に同一（BR-DM01）
- U-07 がトランザクションを持たないため、**ヘキサゴナルのポート境界（P-*）が保たれる**。U-07 は「何をするか」を呼ぶだけで「どう永続化するか」を知らない

**却下**: Unit-of-Work を U-07 が制御する案（B）は U-07 と永続化層を結合させポート境界を壊す。文ごとの自動コミット（C）は原子性を壊す。

---

## DP-02: DB 復元時の fail-closed 再検証（Q2=A）

**問題**: DB から読んだ行が不正（例: 緯度 95.0）だったとき、どう振る舞うか。

**パターン**: **`DataIntegrityError`（`DomainError` サブクラス）を送出する。**

- マッパは行からドメイン型を構築する際、frozen dataclass の `__post_init__` を必ず再実行する（DP-06）
- `__post_init__` が拒否したら、その例外を捕捉し、**行の識別子（ID のみ）**を文脈に付した `DataIntegrityError` に包んで送出する
- 不正・部分的なドメインオブジェクトを**決して返さない**

```
# 概念
def to_staff(row) -> Staff:
    try:
        return Staff(id=row.id, name=row.name, district=row.district, ...)
    except DomainError as e:
        raise DataIntegrityError(entity="staff", entity_id=row.id) from e
        # 文脈は ID のみ。氏名・居住小学校区（PII）を含めない
```

**根拠**:
- **fail closed（SECURITY-15）**: DB の破損が、無言のうちに下流（最適化エンジン U-04）へ伝播しない。破損はその場で例外になる
- **PII 非露出（SECURITY-03）**: エラー文脈は ID のみ。氏名・居住小学校区を含めない
- `from e` で原因を連鎖させ、デバッグ可能性を保つ（ただし PII は含めない）

**新規例外**: `DataIntegrityError`（`exceptions.py` に追加、U03-H9）。

**却下**: ログしてスキップ（B）はデータを黙って落とす。`Optional` 返却（C）は検査を全呼び出し側に押し付ける。

---

## DP-03: CSV 2 相・単一パス・一括挿入（Q3=A）

**問題**: NFR-P04（2,000 行を 30 秒以内）と BR-DM02（全エラーを行番号付きで一括報告）を両立させる。

**パターン**: **単一のメモリ内パスで「全ロード → 全検証 → 一括保存」。**

```
第 1 相（DB に触れない）:
  1. 標準ライブラリ csv で全行をロード（2,000 行、< 1 秒）
  2. 全行を検証。エラーは (行番号, 理由) で蓄積し、最後まで続ける
  3. エラーが 1 件でもあれば CsvImportError(all_errors) を送出（保存しない）

第 2 相（1 トランザクション、DP-01）:
  4. executemany で一括 INSERT（数百ミリ秒）
```

**根拠**:
- **性能**: 2,000 行はメモリ上で微小。解析 < 1 秒 + 一括挿入数百ミリ秒で 30 秒に十分収まる（NFR-P04）
- **全エラー一括報告（BR-DM02）**: 第 1 相で最初のエラーで止めず、全行を検証しきる。利用者は 1 回の修正で全問題を直せる
- **fail closed**: 検証相と保存相を分離。1 件でもエラーがあれば保存相に入らない（DP-01 と合わせ、DB は無変更）

**却下**: ストリーミング/チャンク（B）は 2,000 行に過剰で、全エラー蓄積を複雑にする。

---

## DP-04: 距離キャッシュの原子的全再計算（Q4=A）

**問題**: 小学校区マスタ更新後の距離キャッシュ全再計算を、マスタ更新に対してどう順序づけるか。

**パターン**: **マスタ更新と全再計算を同一トランザクションで原子的に行う。**

```
# 概念
with session_factory.begin() as session:
    repo.update_school_districts(session, new_master)     # マスタ更新
    session.execute(delete(distance_cache_table))          # 旧キャッシュ全削除
    matrix = compute_district_distance_matrix(...)         # U-02 の純関数
    repo.bulk_insert_distance_cache(session, matrix)       # 新キャッシュ保存
    # 抜けると commit。途中の例外なら全ロールバック
```

**根拠**:
- **一貫性が最も強い**: いずれかが失敗すれば**両方ロールバック**。commit 済みのマスタと古いキャッシュが共存する状態が**構造的に発生しえない**（fail closed）
- 距離計算は U-02 の純関数（`compute_district_distance_matrix`）を呼ぶだけで、DB 内で計算しない。再計算は大円距離のみ（迂回係数・速度・費用は含めない、U02-H4）で、キャッシュ再計算は小学校区マスタ変更時のみ（NFR-P03）
- PoC 規模（小学校区数 × 施設数）では 1 トランザクションで完結する。実運用で行数が増える場合は別トランザクション + 修復経路を検討（U03-H10 に申し送り）

**却下**: 別トランザクション（B）は古いキャッシュが残る窓を作る。遅延（C）は最初の最適化実行がコストを払う（許容できるが、一貫性の明快さで A を採る）。

---

## DP-05: 永続化層の個人情報非露出（Q5=A）

**問題**: 職員マッパは DB から氏名・居住小学校区（個人情報）を読む。ログ/エラーに漏らさない。

**パターン**: **永続化層は行の内容をログに出さない。**

| 項目 | 決定 |
|------|------|
| SQLAlchemy `echo` | **全環境で `False`**（開発でも有効化しない）。SQL の値ログを無効にする |
| マッパのエラー | 職員 ID と行番号のみ（DP-02, BR-DM14）。氏名・居住小学校区を含めない |
| 例外の `__str__` | ID・行番号のみ。DP-02 の `DataIntegrityError` は entity + entity_id のみ |
| `Staff.__repr__` | U-01 で既に PII を redact 済み（多層防御）|

**根拠**:
- **SECURITY-03**: SQL echo を有効にすると、バインドされた値（個人情報）がログに出る。全環境で `False` に固定し、この経路を塞ぐ
- U-01 の `Staff.__repr__` redaction（多層防御）と合わせ、**永続化層のどの経路からも個人情報がログに出ない**

**却下**: 開発でのみ echo 有効（B）は SECURITY-03 違反。

---

## DP-06: 手書きマッパ（行 ↔ frozen ドメイン型）

**問題**: ORM を使わず、DB 行とドメイン型（frozen dataclass）を相互変換する。

**パターン**: **SQLAlchemy Core + 手書きマッパ関数**（U-03 Functional Design で確定）。

- 書き込み: ドメイン型 → 行の dict（`executemany` 用）
- 読み込み: 行 → ドメイン型。`__post_init__` を再実行し、fail closed（DP-02）

**根拠**:
- frozen dataclass（U-01）を ORM の可変モデルに置き換えない。ドメイン層の不変性を保つ
- 読み込み時に必ず検証が走る（DP-02）。ORM の遅延ロードや自動マッピングによる検証迂回がない

---

## DP-07: パラメータ化クエリの構造的保証（SECURITY-05）

**問題**: SQL インジェクション（MU-02 の親戚）を防ぐ。

**パターン**: **SQLAlchemy Core が値をバインドパラメータとして扱う。生の SQL 文字列に値を連結しない。**

- クエリは Core の式言語（`select()`, `insert()`, `text()` + バインドパラメータ）で組む
- 文字列連結・f-string で値を SQL に埋め込むことを**禁止**する
- 相関サブクエリ（有効な申告の取得）も Core の式で表現する

**根拠**:
- **SECURITY-05**: Core は値を必ずパラメータ化する。CSV 由来の文字列（施設名等）が SQL として解釈される余地が構造的にない
- CSV の入力検証（第 1 相、DP-03）と合わせ、多層で防御する

---

## 該当しないパターン（Q6=A、N/A）

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| **Resilience**（リトライ、サーキットブレーカ）| **N/A** | fail closed を採用。誤ったデータでリトライ/続行しない。単一プロセス内の DB アクセスで、リトライすべき外部呼び出しがない |
| **Scalability**（スケールアウト、プールサイズ調整）| **N/A** | 単一サーバー・単一ワーカー（A-07）。コネクションプールは既定の小サイズで固定。水平スケールしない |
| **追加 Logical Components**（メッセージキュー、外部キャッシュ、サーキットブレーカ）| **N/A** | ジョブキューは DB ベースで U-07 が所有。距離キャッシュは DB テーブル（外部キャッシュ層を持たない）。U-03 は Engine/SessionFactory・Repository・Mapper・CsvImportService・MigrationRunner のみ（logical-components.md 参照）|

---

## 拡張ルール適合サマリ

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-15**（fail closed）| ✅ 適合 | DP-01（原子性）、DP-02（DB 破損で送出）、DP-03（検証失敗で保存しない）、DP-04（再計算失敗で両ロールバック）|
| **SECURITY-05**（パラメータ化クエリ）| ✅ 適合 | DP-07。Core による構造的保証 |
| **SECURITY-03**（ログに PII を含めない）| ✅ 適合 | DP-05（echo=False、ID のみログ）、DP-02（エラー文脈は ID のみ）|
| **SECURITY-01**（保存時暗号化）| ✅ 適合（インフラ委譲）| 暗号化ボリューム（shared-infrastructure.md）|
| **PBT-01..08, 10** | ✅ 検証可能 | 全パターンが P-DM01..05 / INV-10a/b / PBT-06 ステートフルテストで検証可能（下記）|
| SECURITY-02, 04, 06〜14 | N/A | ネットワーク・認証・認可・監査は U-06/U-07/インフラ |
| Resiliency 拡張 | スキップ | Enabled=No |

**ブロッキング所見: なし**

### パターンと PBT の対応

| パターン | 検証するプロパティ/テスト |
|---------|------------------------|
| DP-01（原子性）| P-DM01（トランザクションのロールバック）|
| DP-02（fail-closed 再検証）| P-DM05（マッパの往復）+ 不正行注入テスト |
| DP-03（2 相インポート）| INV-10a/b（全エラー報告 + 部分保存なし）|
| DP-04（原子的再計算）| P-DM04（キャッシュキー正規化）+ ステートフルテスト（PBT-06）|
| DP-07（パラメータ化）| CSV に SQL メタ文字を注入しても被害がないことを確認 |

---

## 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U03-H9（新規）** | `DataIntegrityError`（`DomainError` サブクラス、文脈は entity + entity_id のみ、PII なし）を `exceptions.py` に追加 | U-03 Code Generation |
| **U03-H10（新規）** | 距離キャッシュ再計算は同一トランザクション（PoC）。実運用で行数増大時は別トランザクション + 修復経路を再検討 | 実運用移行時 / OPERATIONS |
| U03-H7, H8 | 依存追加・固定、実インメモリ SQLite テスト（NFR Requirements より継続）| U-03 Code Generation |
