# ビジネスロジックモデル — U-02 `distance-cost`

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - Functional Design（ユニット 2 / 8）

---

## 1. このユニットの本質

**U-02 のプロダクションコードは、すべて純粋関数である。** 副作用を持たず、DB もファイルも時刻も乱数も参照しない。

これは規約ではなく、**リンタ規則 R-3 により機械的に強制される**。

```text
R-3: src/distance_cost/ は src/shared_kernel/ 以外を import してはならない
```

`sqlalchemy` も `datetime.now()` も `random` も import できない構造である。

**帰結**: INV-07 〜 INV-09 のプロパティベーステストが、**モックを一切必要とせずに書ける**。

---

## 2. 計算の全体フロー

```text
  SchoolDistrict(職員の居住校区)      SchoolDistrict(施設の所在校区)
            |                                    |
            |  representative_point              |  representative_point
            v                                    v
      Coordinates                          Coordinates
            |                                    |
            +----------------+-------------------+
                             |
                             v
              +--------------------------------+
              |  haversine_distance_km()       |   大円距離（キャッシュ対象）
              |  地球半径 6371.0088 km         |
              +--------------------------------+
                             |  great_circle_km
                             v
              +--------------------------------+
              |  actual_travel_distance_km()   |   実移動距離
              |  = great_circle_km * detour    |
              +--------------------------------+
                             |  distance_km
              +--------------+--------------+
              |                             |
              v                             v
  +------------------------+   +--------------------------+
  |  travel_time_seconds() |   |  travel_cost_yen()       |
  |  = ceil(km / kmh *3600)|   |  距離帯モデル             |
  +------------------------+   +--------------------------+
              |                             |
              +--------------+--------------+
                             v
                      TravelMetrics
              (distance_km, time_seconds, cost_yen)
```

**同一小学校区の場合は、この経路を通らない**（セクション 4）。

---

## 3. 各関数の仕様

### 3.1 `haversine_distance_km(a: Coordinates, b: Coordinates) -> float`

2 点間の大円距離（球面上の最短距離）。

**地球半径**: `6371.0088 km`（IUGG 平均半径、Q4=A）。定数として明示する。値の選択で結果が数十メートル変わるため、プロパティテストの再現性のために固定する。

**特性**:
- **純粋関数**
- 返り値は非負（INV-08）
- **INV-07a**: `|haversine(a,b) - haversine(b,a)| < ε`（ε = 1e-9 km）

**なぜ厳密等価ではないのか**: 浮動小数点の演算順序が引数の順序で変わりうるため、丸め誤差が対称でない場合がある。生の関数レベルでは許容誤差付きの対称性しか主張できない（申し送り U01-H2）。

**厳密な対称性は、キャッシュのキー正規化によって別途達成する**（セクション 5）。

---

### 3.2 `actual_travel_distance_km(great_circle_km: float, detour_factor: float) -> float`

直線距離に迂回係数を乗じて、実移動距離を近似する。

```text
actual = great_circle_km * detour_factor
```

**前提 A-03**: 直線距離 × 迂回係数で実移動距離を十分に近似できる。河川・山地・鉄道などの地理的障壁がある地域では誤差が大きくなる。

---

### 3.3 `travel_time_seconds(distance_km: float, average_speed_kmh: float) -> int`

```text
seconds = ceil(distance_km / average_speed_kmh * 3600)
```

**丸め方は切り上げ（`ceil`）**（Q5=A）。移動時間を過小評価しない。災害時の参集計画としては安全側である。

**INV-09（単調非減少）**: `detour_1 <= detour_2` ならば `travel_time_seconds(d * detour_1, v) <= travel_time_seconds(d * detour_2, v)`。

**厳密な単調増加ではない**（申し送り U01-H3、Q7=A）。秒単位に丸めるため、迂回係数をごくわずかに増やしても丸め後の値が変わらないことがある。

---

### 3.4 `travel_cost_yen(distance_km: float, cost_model: CostModel) -> float`

**距離帯モデル**（Q1=A、FR-03.5、申し送り H-1 の決着）。

```text
travel_cost_yen(distance_km, cost_model):
    band = 距離が属する帯を、下から順に探す
        （upper_bound_km が None の帯が最後にあり、必ずどれかに属する）

    if band.rule == FLAT:
        return band.amount_yen
    if band.rule == PER_KM:
        return distance_km * band.amount_yen
```

**帯の選択**: `upper_bound_km` は**排他的**である。距離 `d` が属する帯は、`d < upper_bound_km` を満たす最初の帯。最後の帯は `upper_bound_km = None`（無限大）であり、必ず該当する。

#### 既定値での挙動

| 距離 | 帯 | 交通手段 | 費用 |
|------|----|---------|------|
| 0.0 km | 帯 1（< 2 km） | 徒歩 | 0 円 |
| 1.9 km | 帯 1 | 徒歩 | 0 円 |
| 2.0 km | 帯 2（< 10 km） | 公共交通機関 | 300 円 |
| 9.9 km | 帯 2 | 公共交通機関 | 300 円 |
| 10.0 km | 帯 3（∞） | タクシー | 4,000 円 |
| 25.0 km | 帯 3 | タクシー | 10,000 円 |

**この関数が、本プロジェクトの課題②「タクシーなど移動にかかる費用の高額化」を直接モデル化する。** 9.9 km と 10.0 km の間に 300 円 → 4,000 円 の段差があり、**最適化はこの段差を越えないことに強いインセンティブを持つ**。

線形モデル（`距離 × 単価`）では、この段差が存在しない。

#### なぜ MILP の線形性が保たれるのか

目的関数の費用項は `Σ c_ij · x_ij` である。`c_ij = travel_cost_yen(d_ij, cost_model)` は職員 `i` と施設 `j` の組に対する**定数**であり、**ソルバーを走らせる前に計算される**。

```text
  距離 d_ij --(任意の関数 f)--> 費用 c_ij --(定数係数として)--> Σ c_ij · x_ij
                                                                  ^
                                                        決定変数 x_ij について線形
```

`f` が階段関数であっても、`x_ij` について線形であることに変わりはない。**「距離帯モデルは非線形だから MILP で扱えない」という懸念は成立しない。**

**この事実が、要件 v1.3 の A-04（線形費用モデル）を v1.4 で覆した根拠である。**

---

### 3.5 `compute_travel_metrics(from_district, to_district, params) -> TravelMetrics`

上記を組み合わせ、`TravelMetrics` を返す。

```text
compute_travel_metrics(from_district, to_district, params):

    # 同一小学校区（Q2=A、FR-03.7）
    if from_district.id == to_district.id:
        return TravelMetrics(
            distance_km  = 0.0,
            time_seconds = params.same_district_fixed_seconds,   # 既定 900 秒
            cost_yen     = 0.0,
        )

    great_circle = haversine_distance_km(
        from_district.representative_point,
        to_district.representative_point,
    )
    distance = actual_travel_distance_km(great_circle, params.detour_factor)

    return TravelMetrics(
        distance_km  = distance,
        time_seconds = travel_time_seconds(distance, params.average_speed_kmh),
        cost_yen     = travel_cost_yen(distance, params.cost_model),
    )
```

**同一校区の扱い（Q2=A）**: 距離 0 km、費用 0 円、移動時間のみ固定値。代表点が同一なので距離は 0 である。徒歩圏内とみなし費用も 0 とする。

**距離 0 として扱わないのは移動時間だけである**（FR-03.4）。距離 0・費用 0 は素直な帰結であり、既定の距離帯モデルでも「2 km 未満 = 徒歩 = 0 円」と一致する。

---

## 4. `P-03 DistanceCachePort`（インターフェース定義）

**U-02 はポートを定義するのみ。実装（DB への読み書き）は U-03 が行う。**

```text
get_distance(district_a: SchoolDistrictId, district_b: SchoolDistrictId) -> float | None
    目的: 大円距離をキャッシュから取得する
    返り値: キャッシュミスなら None
    ビジネスルール: 呼び出し前にキーを正規化する

put_distances(entries: Iterable[DistanceCacheEntry]) -> None
    目的: 大円距離をキャッシュに保存する
    ビジネスルール: entries は正規化済みのキーを持つ

invalidate_all() -> None
    目的: キャッシュを全消去する
    呼び出し契機: 小学校区マスタの更新時のみ（US-09）
```

### 4.1 依存性逆転

```text
  U-02 distance-cost          U-03 data-management
  +--------------------+      +---------------------------+
  |  P-03（定義）      |<-----|  A-02 PersistenceAdapter  |
  |  DistanceCachePort |      |  （実装）                 |
  +--------------------+      +---------------------------+
```

**U-02 は U-03 を知らない。** U-03 が U-02 のポートを実装する。したがって依存は U-03 → U-02 の一方向であり、循環しない（`unit-of-work-dependency.md` セクション 2.2 の (a)）。

---

## 5. キーの正規化と INV-07b（申し送り U01-H1）

### 5.1 問題

`haversine_distance_km(a, b)` と `haversine_distance_km(b, a)` は、浮動小数点の丸め誤差により、**ビット単位では一致しないことがある**（INV-07a は許容誤差付き）。

さらに、この距離から秒単位の移動時間を計算すると、**丸め境界をまたいで 1 秒ずれうる**。

移動時間の対称性まで許容誤差付きになるのは望ましくない。

### 5.2 解決

**キャッシュキーを `(min(id_1, id_2), max(id_1, id_2))` に正規化する。**

```text
  cached_distance(SD_A, SD_B)  ─┐
                                ├─→  同一のキー (SD_A, SD_B)  →  同一のエントリ  →  同一の float
  cached_distance(SD_B, SD_A)  ─┘
```

両方向が**同一のキャッシュエントリを引く**ため、返る値はビット単位で同一である。

### 5.3 帰結: INV-07 の分割（申し送り U01-H2）

| ID | 不変条件 | 検証 |
|----|---------|------|
| **INV-07a** | `\|haversine(a,b) - haversine(b,a)\| < ε`（ε = 1e-9 km） | 許容誤差付きのプロパティテスト |
| **INV-07b** | `cached_distance(a,b) == cached_distance(b,a)` | **厳密等価**のプロパティテスト |

**INV-07b は、キーの正規化により構造的に成立する。** 計算の性質ではなく、データ構造の性質である。

---

## 6. 三角不等式は保証されない

**記録として明示する。**

大円距離（Haversine 距離）は球面上の距離であり、数学的に三角不等式を満たす。

しかし本システムが扱うのは、**迂回係数を乗じた実移動距離の近似**である。

```text
  actual(A, C)  <=  actual(A, B) + actual(B, C)   ← 保証されない
```

迂回係数は一律の定数であるため、実際には `great_circle * 1.3` の三角不等式は成立する。**しかし、これは実際の道路網における三角不等式を意味しない。**

さらに**同一小学校区の距離を 0 km、移動時間を 900 秒とする規則**（FR-03.4、FR-03.7）により、**移動時間については三角不等式が明確に破れる**。

```text
  time(A, A) = 900 秒
  time(A, B) + time(B, A) は 900 秒より小さくなりうるか? → いいえ（各項が正）
  しかし time(A, A) = 900 > 0 = time(A, A) が距離ベースなら期待される値
```

**したがって、三角不等式を前提とするアルゴリズム（一部の近似解法、距離行列の圧縮）を U-04 で使ってはならない。**

**U-04 への申し送り（U02-H6）。**

---

## 7. Testable Properties（PBT-01、**ブロッキング制約**）

| ID | プロパティ | 分類 | 対象関数 |
|----|-----------|------|---------|
| **INV-07a** | `\|haversine(a,b) - haversine(b,a)\| < 1e-9` | **Commutativity** | `haversine_distance_km` |
| **INV-07b** | `cached_distance(a,b) == cached_distance(b,a)`（厳密等価） | **Commutativity** | キャッシュキーの正規化 |
| **INV-08a** | `haversine(a,b) >= 0` | **Range constraint** | `haversine_distance_km` |
| **INV-08b** | `haversine(a,a) == 0.0`（厳密） | **Range constraint** | `haversine_distance_km` |
| **INV-08c** | 同一校区なら `distance_km == 0.0` かつ `time_seconds == same_district_fixed_seconds` かつ `cost_yen == 0.0` | **Invariant** | `compute_travel_metrics` |
| **INV-09** | `detour_1 <= detour_2` ⇒ `travel_time_seconds(d*detour_1, v) <= travel_time_seconds(d*detour_2, v)`（**単調非減少**） | **Monotonicity** | `travel_time_seconds` |
| **P-D01** | `d1 <= d2` ⇒ `travel_cost_yen(d1, m) <= travel_cost_yen(d2, m)`（**単調非減少**） | **Monotonicity** | `travel_cost_yen` |
| **P-D02** | `travel_cost_yen(d, m) >= 0` | **Range constraint** | `travel_cost_yen` |
| **P-D03** | `travel_time_seconds(d, v) >= 0` | **Range constraint** | `travel_time_seconds` |
| **P-D04** | 平均速度が増加すれば移動時間は単調非減少に減少する: `v1 <= v2` ⇒ `travel_time_seconds(d, v2) <= travel_time_seconds(d, v1)` | **Monotonicity** | `travel_time_seconds` |
| **P-D05** | `haversine` は既知の測地線距離実装（オラクル）と ±0.5% 以内で一致する | **Oracle**（PBT-05） | `haversine_distance_km` |
| **P-D06** | `CostModel` の生成は、費用関数が単調非減少となる帯設定に対してのみ成功する | **Invariant** | `CostModel` |

### 7.1 P-D01（費用の単調非減少性）が最も重要である理由

これを検証しないと、**「遠くへ行くほど安くなる」費用設定を担当者が作れてしまう**。

```text
帯 2: 2 km 以上 10 km 未満、FLAT 300 円
帯 3: 10 km 以上、       PER_KM 20 円/km

9.9 km → 300 円
10.0 km → 200 円   ← 安くなる
```

最適化は総費用を最小化するため、**より遠い施設へ職員を送ることを選ぶ**。プロジェクトの目的に真っ向から反する。

**P-D06 が `CostModel` の生成時に単調非減少性を検証し、P-D01 が `travel_cost_yen` の出力を検証する。二重の防御である。**

### 7.2 P-D05（オラクル検証、PBT-05）

Haversine 距離の実装が正しいことを、**独立した測地線距離の実装**（例: Vincenty 法、または既知の座標ペアの実測値表）と比較して検証する。

Haversine は球体近似であり、扁平な地球の測地線距離とは最大 0.5% 程度ずれる。**許容誤差を 0.5% と定める。**

**この検証がないと、Haversine の公式の実装誤り（例: `atan2` の引数順序の誤り、緯度と経度の取り違え）を検出できない。** プロパティ（対称性、非負性）は誤った実装でも成立しうる。

### 7.3 プロパティを持たないコンポーネント

| コンポーネント | 判定 | 根拠 |
|--------------|------|------|
| `DistanceCacheEntry` | **No PBT properties identified** | 単なるデータ保持。振る舞いを持たない。キーの正規化は `P-03` の呼び出し側の責務であり、INV-07b で検証する |
| `P-03 DistanceCachePort` | **No PBT properties identified（U-02 として）** | インターフェース定義のみ。実装は U-03 が持ち、ラウンドトリップ性（`put` → `get`）は U-03 が検証する |

---

## 8. 後続への申し送り

| ID | 事項 | 引き渡し先 |
|----|------|-----------|
| **U02-H6（新規）** | **三角不等式を前提とするアルゴリズムを使ってはならない。** 同一小学校区の移動時間を固定値 900 秒とする規則により、移動時間の三角不等式は破れる | **U-04** optimization-engine |
| **U02-H7（新規）** | 費用関数は階段関数である。目的関数の費用項 `Σ c_ij · x_ij` の `c_ij` は最適化の**前に**計算される定数係数であり、MILP の線形性は保たれる | **U-04** optimization-engine |
| U02-H1 | `TravelParameters.unit_price_per_km` は削除された。`cost_model` を使うこと | U-04, U-07 |
| U02-H3 | 距離キャッシュのキーは `(min(id), max(id))` に正規化する | U-03 |
| U02-H4 | キャッシュに保存するのは大円距離のみ。無効化は小学校区マスタ更新時のみ | U-03 |
