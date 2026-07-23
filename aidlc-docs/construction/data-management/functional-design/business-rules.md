# ビジネスルール — U-03 `data-management`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Functional Design（ユニット 3 / 8）

---

## 1. CSV インポートのルール

### BR-DM01: fail closed の原子性（US-07、SECURITY-15）

1 行でもエラーがあれば、**インポート全体をロールバックする**。DB の状態はインポート前と完全に同一になる。

エラー検出のフェーズ:
- **Phase 1（解析）**: CSV として不正 → DB を触らず、行番号付きエラーを返す
- **Phase 2（検証）**: 型・参照整合性・列挙値・不変条件・重複 → DB を触らず、**全エラーを一括で**返す（Q4=A）
- **Phase 3（保存）**: DB 制約違反 → ロールバック

### BR-DM02: 全エラーの一括報告（Q4=A、US-07）

Phase 2 では、最初のエラーで停止せず、**全行を検証してすべてのエラーを収集する**。担当者は 1 回の修正で全エラーを直せる。

エラーには**行番号**を付す（US-07 の受入基準）。

### BR-DM03: 列挙値の未知の値は拒否（U01-H24、SECURITY-15）

CSV の日本語表記を `from_japanese()` で英語識別子へ変換する。**変換表にない値（例: `課長補佐`）は `UnknownEnumValueError` とし、インポートを失敗させる。** サイレントに `OTHER` へ丸めない。

### BR-DM04: 数式インジェクションの無害化（MU-02、SECURITY-05）

CSV **エクスポート**時、値が `=`, `+`, `-`, `@` で始まる場合にエスケープする。

**実装**: `A-04 CsvAdapter.serialize()` は、サニタイズ関数を**引数として受け取る**（依存性注入、U03-H5）。U-06 の `SEC-05.sanitize_csv_cell()` を U-07 が注入する。**U-03 は U-06 に依存しない**（Units Generation の MU-02 解決策）。

---

## 2. 従事可否申告のルール

### BR-DM05: `declared_at` の一意性（U01-H11、Q3=A）

同一 `(staff_id, event_id, declared_at)` の申告は 1 件のみ。

**二重の防御**:
- DB の `UNIQUE(staff_id, event_id, declared_at)` 制約
- インポート時、同一 CSV 内での `(staff_id, declared_at)` 重複を Phase 2 で検出

これにより、U-01 の `AmbiguousDeclarationError`（同一時刻の申告が 2 件）に相当する状態が、DB レベルで発生しない。

### BR-DM06: 有効な申告はちょうど 1 件

各 `(staff_id, event_id)` について、有効な申告は `declared_at` が最大の 1 件。BR-DM05 の一意制約により、最大値を持つ行はちょうど 1 つ。

### BR-DM07: 申告の追記のみ（US-12）

再申告は新しい行の追記であり、過去の行を変更・削除しない。履歴が保持される。

---

## 3. 充足状況のルール

### BR-DM08: 3 分類集計（U01-H10、Q8=A、US-13）

充足状況は「従事可能 / 従事不可 / 未申告」の 3 分類で集計する。

- 母集合は**職員マスタ全体**（Q8=A）
- **未申告 = 全職員 − 従事可能申告者 − 従事不可申告者**
- 不変条件: `available + unavailable + undeclared == len(all_staff)`

**「未申告」を「従事不可」と混同しない。** 未申告は督促の対象、従事不可は休暇・介護・健康配慮であり督促しない。

---

## 4. イベントのルール

### BR-DM09: ステータス遷移の事前条件（U01-H13）

遷移規則そのものは U-01 の `Event.transition_to()` が保証する（型レベル）。**事前条件は S-01 EventService が検証する。**

| 遷移 | 事前条件 |
|------|---------|
| `Draft → CollectingDeclarations` | 施設が 1 件以上登録されている |
| `CollectingDeclarations → Optimized` | 最適化ジョブが正常完了した（U-04 が起動） |
| `Optimized → CollectingDeclarations`（再開） | 追加申告のため。US-24 |
| `Optimized → Confirmed` | 担当者の明示的確定 |

### BR-DM10: イベント削除の連鎖（Q5=A、US-06）

- `Confirmed` のイベントは削除不可
- それ以外は削除可能。**ON DELETE CASCADE** で、紐づく従事可否申告・割当・過去実績を連鎖削除
- **`foreign_keys = ON`（U01-H15）がないと CASCADE が機能しない**ため、SQLite の PRAGMA 設定が前提

---

## 5. データ整合性のルール

### BR-DM11: 距離キャッシュの正規化（U02-H3）

`distance_cache` テーブルは `CHECK(district_a <= district_b)` を課す。正規化されていないエントリの挿入は DB レベルで拒否される。

### BR-DM12: frozen 型の更新（U01-H21）

ドメイン型は frozen であり、属性を直接変更できない。更新は `dataclasses.replace()` で新インスタンスを構築し、リポジトリで UPDATE する。**ORM のダーティチェックに依存しない**（Q1=A の SQLAlchemy Core 方式）。

### BR-DM13: DB からの復元時の fail closed（Q1=A、SECURITY-15）

行からドメイン型を再構築する際、`__post_init__` が再実行される。DB に不正データ（緯度 95.0 等）が混入していれば、その場で例外を送出する。**DB の破損が下流へ伝播しない。**

---

## 6. 日時のルール（U01-H12）

| データ | 保存形式 |
|-------|---------|
| `availability_declarations.declared_at` | UTC |
| 監査ログのタイムスタンプ | UTC |
| **`events.scheduled_date`** | **JST の暦日**（`DATE` 型、時刻なし） |

CSV インポート時、日時列は JST として解釈し UTC へ変換して保存する。`scheduled_date` は JST の暦日のまま保存する。

---

## 7. エラー処理

### BR-DM14: エラーに個人情報を含めない（SECURITY-03）

CSV インポートのエラー報告、ログ、例外の文脈に、職員の**氏名・居住小学校区を含めない**。職員 ID と行番号のみを含める。

**例**:
- ✅ `Row 15: staff_id S001 references unknown school district SD99`
- ❌ `Row 15: 鈴木太郎（第三小学校区）の参照先が不正です`

---

## 8. 拡張ルール適合サマリ

### 8.1 PBT Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| **PBT-01 プロパティ特定（ブロッキング）** | **適合** | `business-logic-model.md` セクション 7 に 7 プロパティ（INV-10a/b, P-DM01〜P-DM05）を分類付きで列挙 |
| **PBT-02 ラウンドトリップ** | **適合**（先行） | INV-10a（CSV）、INV-10b（キャッシュ）、P-DM05（マッパ） |
| **PBT-06 ステートフルテスト** | **適合（要と判定）** | `Event` の状態機械を `RuleBasedStateMachine` で検証する（セクション 7.1）。**U-03 が状態遷移を扱う最初のユニットである** |
| PBT-03 不変条件 | **適合**（先行） | P-DM01, P-DM02, P-DM03, P-DM04 |
| PBT-07 生成器 | 方針 | U-01 の生成器を再利用。CSV バイト列の生成器を追加 |
| PBT-04, 05, 08, 09, 10 | Code Generation / 継承 | |

**ブロッキング所見: なし**

### 8.2 Security Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-05 入力検証** | **適合** | CSV インポートの Phase 2 検証（型・長さ・書式・参照整合性）。ドメイン型の生成時検証 |
| **SECURITY-15 fail closed** | **適合** | BR-DM01（原子性）、BR-DM03（未知の値の拒否）、BR-DM13（DB 復元時の検証） |
| **SECURITY-03 ログに PII を含めない** | **適合** | BR-DM14。エラーに職員 ID と行番号のみ |
| **SECURITY-01 保存時暗号化** | **適合（インフラで対応）** | 個人情報を保存する。暗号化ボリューム上に配置（shared-infrastructure.md） |
| **SECURITY-13 データ完全性** | **適合** | マスタ変更・削除を監査ログに記録（S-08 に委譲） |
| SECURITY-02, 04, 06, 07, 08, 09, 10, 11, 12, 14 | **N/A** | ネットワーク・HTTP・認証・認可は U-06/U-07。監査ログの改竄防止は U-06 |

**ブロッキング所見: なし**

**重要**: U-03 は個人情報（氏名・居住小学校区）を保存する最初のユニットである。SECURITY-01（保存時暗号化）と SECURITY-03（ログに含めない）が本ユニットで実効的に問われる。前者は shared-infrastructure.md の暗号化ボリュームで、後者は BR-DM14 で対応する。

### 8.3 Resiliency Extension

**スキップ**（Enabled = No）。

---

## 9. 解決した申し送り

| ID | 状態 |
|----|------|
| U01-H10（3 分類集計） | ✅ BR-DM08 |
| U01-H11（declared_at 一意性） | ✅ BR-DM05 |
| U01-H12（日時 UTC/JST） | ✅ セクション 6 |
| U01-H13（ステータス遷移の検証） | ✅ BR-DM09 |
| U01-H21（frozen 型の更新） | ✅ BR-DM12 |
| U01-H24（列挙値の変換） | ✅ BR-DM03 |
| U02-H3（キャッシュキー正規化） | ✅ BR-DM11 |
| U02-H4（大円距離のみ保存） | ✅ business-logic-model.md 4 節 |
| U02-H10（キャッシュ再計算） | ✅ business-logic-model.md 4 節 |

**U01-H15（SQLite PRAGMA）、U01-H18（Alembic）は Code Generation で実装する。**
