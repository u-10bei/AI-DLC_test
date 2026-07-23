# 論理コンポーネント — U-02 `distance-cost`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - NFR Design（ユニット 2 / 8）

---

## 1. U-02 はインフラコンポーネントを持たない

U-01 と同じく、U-02 は**キュー・キャッシュ実装・サーキットブレーカ・ブローカ・セッションストア・DB 接続プールをひとつも持たない**。

| インフラコンポーネント | U-02 が持つか | 実際の所有 |
|---------------------|:-----------:|-----------|
| 距離キャッシュ（**実装**） | **持たない** | **U-03**（`A-02 PersistenceAdapter` が `P-03` を実装） |
| ジョブキュー | 持たない | U-04 |
| その他 | 持たない | — |

**U-02 が持つのは `P-03 DistanceCachePort` の「定義」のみである。** キャッシュの実装（DB への読み書き）は U-03 が行う。これは依存性逆転の原則である（`business-logic-model.md` セクション 4.1）。

---

## 2. U-02 が持つ論理コンポーネント

すべて**純粋関数**であり、標準ライブラリの `math` のみに依存する。

```text
+-------------------------------------------------------------------+
|  U-02 distance-cost                                              |
|                                                                   |
|  +-------------------------------------------------------------+  |
|  |  LC-D01: 距離・時間・費用の算出関数（純粋）                 |  |
|  |    haversine_distance_km()                                  |  |
|  |    actual_travel_distance_km()                              |  |
|  |    travel_time_seconds()                                    |  |
|  |    travel_cost_yen()          （距離帯の線形探索）          |  |
|  |    compute_travel_metrics()   （同一校区の分岐を含む）      |  |
|  +-------------------------------------------------------------+  |
|                                                                   |
|  +-------------------------------------------------------------+  |
|  |  LC-D02: 距離行列の事前計算関数（純粋）                     |  |
|  |    compute_district_distance_matrix()                       |  |
|  |      -> list[DistanceCacheEntry]                            |  |
|  |    キーの正規化 (min(id), max(id)) を適用                   |  |
|  +-------------------------------------------------------------+  |
|                                                                   |
|  +-------------------------------------------------------------+  |
|  |  LC-D03: P-03 DistanceCachePort（インターフェース定義）     |  |
|  |    get_distance / put_distances / invalidate_all           |  |
|  |    実装は U-03                                              |  |
|  +-------------------------------------------------------------+  |
|                                                                   |
+-------------------------------------------------------------------+

  U-01 に追加する型（U-02 Code Generation で修正）:
    CostRule, CostBand, CostModel（value_objects.py）
    InvalidCostModelError, UnknownSchoolDistrictError（exceptions.py）
    DistanceCacheEntry は U-02 に定義
```

**依存**: 標準ライブラリ（`math`）と U-01 のみ。

---

## 3. LC-D01: 算出関数

| 関数 | 純粋性 | 依存 |
|------|:------:|------|
| `haversine_distance_km(a, b)` | 純粋 | `math`（`sin`, `cos`, `asin`, `sqrt`, `radians`） |
| `actual_travel_distance_km(gc, detour)` | 純粋 | なし |
| `travel_time_seconds(km, kmh)` | 純粋 | `math.ceil` |
| `travel_cost_yen(km, cost_model)` | 純粋 | なし（線形探索） |
| `compute_travel_metrics(from, to, params)` | 純粋 | 上記 |

**地球半径定数**: `EARTH_RADIUS_KM = 6371.0088`（BR-D05）。

---

## 4. LC-D02: 事前計算関数

```text
compute_district_distance_matrix(districts: Iterable[SchoolDistrict]) -> list[DistanceCacheEntry]
```

- **純粋関数**。与えられた小学校区群から、全ペアの大円距離を計算する
- キーを `(min(id), max(id))` に正規化する（U01-H1）
- 対角成分（同一校区）も含む（距離 0）
- **U-03 がこれを呼び、結果を永続化する**（Q3=A、申し送り U02-H10）

**U-02 は「いつ再計算するか」を知らない。** 再計算の起動（小学校区マスタ更新時）は U-03 の責務である。

---

## 5. LC-D03: `P-03 DistanceCachePort`（インターフェース定義）

U-02 は**定義のみ**を持つ。実装は U-03。

```text
get_distance(district_a, district_b) -> float | None    # 大円距離。ミスなら None
put_distances(entries) -> None
invalidate_all() -> None                                 # 小学校区マスタ更新時のみ
```

**保存する値は大円距離のみ**（Q3=A）。迂回係数・平均速度・費用モデルの変更では無効化しない。

---

## 6. U-02 が必要とするテスト生成器

U-01 の 13 生成器（`tests/shared_kernel/generators.py`）を再利用する（U01-H29）。加えて、U-02 が新たに必要とする生成器。

| 生成器 | 生成する値 | 配置 |
|-------|----------|------|
| `gen_cost_model()` | **単調非減少**を満たす妥当な `CostModel` | U-01 の generators.py に追加 |
| `gen_non_monotonic_cost_model()` | **単調非減少に違反する**帯設定（否定的生成器） | 同上 |

**`gen_non_monotonic_cost_model()` の必要性**: `gen_cost_model()` は妥当なモデルしか生成しないため、BR-D04（単調性検証）の**拒否経路**を通れない。P-D06（`CostModel` が単調性違反を拒否する）のテストには、意図的に違反するモデルを生成する否定的生成器が必要である。

**U-01 で `gen_invalid_facility()` を追加したのと同じパターンである。**

---

## 7. 他ユニットとの関係

| 他ユニットのコンポーネント | U-02 との関係 |
|------------------------|-------------|
| **U-03** `A-02 PersistenceAdapter` | `P-03`（U-02 定義）を実装する。`compute_district_distance_matrix()`（U-02）を呼んで結果を永続化する |
| **U-04** 最適化エンジン | `compute_travel_metrics()` を呼んで距離行列を構築する。**三角不等式を前提とするアルゴリズムを使ってはならない**（U02-H6） |
| **U-07** `S-07 ConfigService` | `CostModel` と `TravelParameters` の設定 UI を提供する（U02-H2） |

---

## 8. まとめ

| 項目 | U-02 の状態 |
|------|-----------|
| インフラコンポーネント | **持たない** |
| 論理コンポーネント | 3 種（算出関数、事前計算関数、`P-03` 定義） |
| プロダクションコードの依存 | **標準ライブラリ `math` と U-01 のみ** |
| テストコードの依存 | `pytest`, `hypothesis`（U-01 から継承） |
| 純粋性の強制 | **2 層のリンタ契約**（R-3 + 標準ライブラリのみ） |
