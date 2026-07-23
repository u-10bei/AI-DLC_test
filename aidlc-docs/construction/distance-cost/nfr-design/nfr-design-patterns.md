# NFR 設計パターン — U-02 `distance-cost`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - NFR Design（ユニット 2 / 8）

---

## 1. 確定した設計パターン

| # | パターン | 決定 | 対応する NFR |
|---|---------|------|-------------|
| 1 | 距離帯の探索 | **線形探索** | NFR-U02-P01 |
| 2 | 純粋関数性の強制 | **2 層のリンタ契約**（R-3 + 標準ライブラリのみ） | NFR-U02-M02, SECURITY-11 |
| 3 | fail closed | 生成時検証 + 例外送出 | NFR-U02-R01, R02, SECURITY-15 |

---

## 2. パターン 1: 距離帯の線形探索（Q1=A）

`travel_cost_yen(distance, cost_model)` は、距離が属する帯を**下から順に線形探索**する。

```text
travel_cost_yen(distance_km, cost_model):
    for band in cost_model.bands:            # 下から順（BR-D02 で単調増加が保証済み）
        if band.upper_bound_km is None or distance_km < band.upper_bound_km:
            return _apply(band, distance_km)
    # BR-D02 により最後の帯は upper_bound_km=None のため、ここには到達しない
```

**根拠**: 帯数は既定 3、担当者が増やしても 10 程度。二分探索の利点が出る規模ではない。線形探索は境界条件（排他的上限、`business-logic-model.md` BR-D08）が読みやすく、`None`（無限大）の最上帯を自然に扱える。

**性能への影響**: 距離行列の各要素に対し高々 10 回の比較。2 万要素でも 20 万回の比較であり、無視できる。

---

## 3. パターン 2: 純粋関数性の 2 層強制（Q2=A、SECURITY-11）

U-02 が純粋関数のみで構成されることを、**2 つのリンタ契約で機械的に強制する**。多層防御である。

| 層 | 契約 | 防ぐもの |
|----|------|---------|
| **層 1: ユニット境界** | R-3: `distance_cost` は `shared_kernel` 以外のユニットを import してはならない | U-03（DB）や U-04（ソルバー）への依存 |
| **層 2: 第三者依存** | `distance_cost` は `numpy`, `sqlalchemy`, `pydantic`, `fastapi`, `hypothesis` を import してはならない | 副作用を持ちうる第三者ライブラリへの依存 |

### 3.1 なぜ 2 層必要か

R-3 だけでは、`import numpy` を防げない。`numpy` はユニットではないため、ユニット境界の契約に引っかからない。

層 2 が、`distance_cost` を標準ライブラリのみに閉じ込める。これにより `distance_cost` は DB もネットワークも時刻も乱数も参照できない構造になる。

### 3.2 契約の実効性の確認（Code Generation で実施）

U-01 で `import pydantic` の混入により契約が BROKEN になることを確認したのと同様に、U-02 でも `import numpy` を一時的に混入させ、層 2 の契約が BROKEN になることを確認する。

**契約が空振りしていないことを、実際に破って確かめる。**

### 3.3 この強制がテストにもたらす利益

`distance_cost` が構造的に純粋であるため、INV-07 〜 INV-09 のプロパティテストは**モックを一切必要としない**。DB のスタブも、時刻の固定も、乱数シードの制御（計算部分では）も不要である。

---

## 4. パターン 3: fail closed（SECURITY-15）

U-01 と同じ規律。

| 契機 | 挙動 |
|------|------|
| 不正な `CostBand`（負の費用、非正の上限） | 生成を拒否（BR-D01） |
| 不正な `CostModel`（帯が単調増加でない、無限大帯がない/複数） | 生成を拒否（BR-D02） |
| **費用関数が単調非減少でない距離帯設定** | 生成を拒否（BR-D04） |
| 存在しない小学校区への参照 | `UnknownSchoolDistrictError` を送出（BR-D09） |

**`None` を返さない**（BR-D09）。呼び出し元（U-04）が `None` を無視すると、その職員が最適化から静かに脱落する。

---

## 5. 必須カテゴリの N/A 判定（Q3=A で確認済み）

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| **Resilience Patterns** | **N/A** | U-02 は外部呼び出しを一切持たない（層 1・層 2 の契約が構造的に保証）。リトライ・サーキットブレーカ・フォールバックの対象がない。レジリエンシー拡張も無効 |
| **Scalability Patterns** | **N/A** | 純粋関数。稼働プロセスを持たない |
| **Performance Patterns** | **限定的に該当** | パターン 1（線形探索）。キャッシュの**永続化**は U-03 の責務。U-02 は「大円距離を保存する」という設計判断（Functional Design Q3=A）を提供済み |
| **Security Patterns** | **限定的に該当** | パターン 2（純粋関数性の強制）。`UnknownSchoolDistrictError` の文脈に小学校区 ID のみ |
| **Logical Components（インフラ）** | **N/A** | `logical-components.md` を参照 |

---

## 6. 拡張ルール適合サマリ

### 6.1 Security Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| **SECURITY-11** セキュアデザイン（多層防御） | **適合** | 純粋関数性を 2 層のリンタ契約で強制（パターン 2） |
| **SECURITY-15** fail closed | **適合** | パターン 3 |
| **SECURITY-03** アプリケーションログ | **適合** | U-02 は個人情報を扱わない。例外の文脈は小学校区 ID のみ |
| SECURITY-01, 02, 04〜10, 12〜14 | **N/A** | 純粋関数。永続化・ネットワーク・認証・認可・ログ・依存管理の表出を持たない |

**ブロッキング所見: なし**

### 6.2 PBT Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| **PBT-08** シュリンキングと再現性 | **適合（継承）** | U-01 の `conftest.py` を継承。CI はランダムシード、失敗時にシード出力 |
| PBT-01, 05 | 特定済み（Functional Design、NFR Requirements） | |
| PBT-03, 07, 10 | Code Generation が対象 | |
| PBT-02, 04, 06, 09 | N/A / 継承 | |

**ブロッキング所見: なし**

### 6.3 Resiliency Extension

**スキップ**（Enabled = No）。U-02 は外部呼び出しを持たないため、レジリエンスパターンの適用対象がない。

---

## 7. 新規の申し送り

なし。本ステージの決定（線形探索、2 層契約）は Code Generation で実装する。契約の追加は既に U02-H28 相当として NFR-U02-M02 に記録済み。
