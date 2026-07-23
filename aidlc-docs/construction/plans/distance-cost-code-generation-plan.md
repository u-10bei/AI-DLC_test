# Code Generation Plan — U-02 `distance-cost`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Code Generation - Part 1 (Planning)（ユニット 2 / 8）

**本計画は Code Generation の唯一の真実の源である。** Part 2 では本計画に書かれたステップのみを、書かれた順序どおりに実行する。

---

## 1. ユニットコンテキスト（Step 1 の結果）

| 項目 | 内容 |
|------|------|
| **ユニット** | U-02 `distance-cost`（コード上 `src/distance_cost/`） |
| **ワークスペースルート** | `/home/llm-user/AI-DLC_test` |
| **プロジェクトタイプ** | Greenfield / モノリス（U-01 で骨格作成済み） |
| **依存するユニット** | U-01 `shared_kernel` のみ |
| **このユニットに依存するユニット** | U-03, U-04, U-07 |
| **主担当ストーリー** | **US-15**（距離・移動時間・移動費用の算出） |

### 1.1 このユニットの特殊性: U-01 の承認済みコードを修正する

U02-H8 により、**U-02 は U-01 の承認済みファイルを 3 つ修正する**。

| ファイル | 修正内容 |
|---------|---------|
| `src/shared_kernel/value_objects.py` | `TravelParameters.unit_price_per_km` を削除。`CostRule`, `CostBand`, `CostModel` を追加。`TravelParameters` に `cost_model` を追加 |
| `src/shared_kernel/exceptions.py` | `InvalidCostModelError`, `UnknownSchoolDistrictError` を追加 |
| `src/shared_kernel/__init__.py` | 新しい型・例外を再エクスポート |

**code-generation.md のファイル修正ルールを厳守する**: 既存ファイルは**その場で修正する**。`value_objects_new.py` のようなコピーを作らない。

これに伴い、U-01 の**既存テストと生成器**も更新する（U02-H9）。

| ファイル | 修正内容 |
|---------|---------|
| `tests/shared_kernel/generators.py` | `gen_travel_parameters()` を `cost_model` 対応に。`gen_cost_model()`, `gen_non_monotonic_cost_model()` を追加 |
| `tests/shared_kernel/test_properties.py` | `TravelParameters` を構築する箇所を `cost_model` 対応に |

---

## 2. コード配置

```text
/home/llm-user/AI-DLC_test/
├── .importlinter                          # 【修正】R-3 + 標準ライブラリ契約を追加
├── src/
│   ├── shared_kernel/                     # 【修正】U-01 の 3 ファイル
│   │   ├── value_objects.py               #   CostRule/CostBand/CostModel 追加、unit_price_per_km 削除
│   │   ├── exceptions.py                  #   2 例外追加
│   │   └── __init__.py                    #   再エクスポート
│   └── distance_cost/                     # 【新規】U-02
│       ├── __init__.py                    #   公開 API
│       ├── calculator.py                  #   距離・時間・費用の算出関数（純粋）
│       ├── matrix.py                      #   compute_district_distance_matrix()
│       ├── cache_port.py                  #   P-03 DistanceCachePort（Protocol）
│       └── entities.py                    #   DistanceCacheEntry
└── tests/
    ├── shared_kernel/                     # 【修正】生成器とテスト
    │   ├── generators.py
    │   └── test_properties.py
    └── distance_cost/                     # 【新規】U-02 のテスト
        ├── __init__.py
        ├── generators.py                  #   U-02 固有の生成器（U-01 を再利用 + 追加）
        ├── oracle_data.py                 #   既知の座標ペアと実測距離（P-D05）
        ├── test_properties.py             #   INV-07a/b, INV-08, INV-09, P-D01..P-D06
        └── test_examples.py               #   例示ベース（US-15、同一校区、費用帯）
```

---

## 3. 実行ステップ（Part 2 で実行）

**各ステップ完了時に即座に `[x]` へ更新する。**

---

### Step 1: U-01 の承認済みコードを修正（value_objects.py）

- [x] `CostRule` 列挙型を追加する（`FLAT`, `PER_KM`）
- [x] `CostBand`（frozen）を追加する。BR-D01 の生成時検証
- [x] `CostModel`（frozen）を追加する。BR-D02（帯構造）+ BR-D04（単調非減少）の生成時検証
- [x] `DEFAULT_COST_MODEL` を定義する（2km/10km、0円/300円/400円）
- [x] `TravelParameters` から `unit_price_per_km` を削除し、`cost_model: CostModel` を追加する
- [x] `TravelParameters.__post_init__` から `unit_price_per_km` の検証を削除する
- [x] `__all__` を更新する

### Step 2: U-01 の承認済みコードを修正（exceptions.py）

- [x] `InvalidCostModelError` を追加する
- [x] `UnknownSchoolDistrictError` を追加する
- [x] `__all__` を更新する

### Step 3: U-01 の承認済みコードを修正（__init__.py）

- [x] `CostRule`, `CostBand`, `CostModel`, `DEFAULT_COST_MODEL` を再エクスポートする
- [x] `InvalidCostModelError`, `UnknownSchoolDistrictError` を再エクスポートする
- [x] `__all__` を更新する

### Step 4: リンタ契約の追加（.importlinter）

- [x] R-3 契約を追加する（`distance_cost` は `shared_kernel` 以外のユニットを import してはならない）
- [x] 標準ライブラリのみ契約を追加する（`distance_cost` は `numpy`, `sqlalchemy`, `pydantic`, `fastapi`, `hypothesis` を import してはならない）
- [x] `root_packages` に `distance_cost` を追加する

### Step 5: U-02 ビジネスロジック生成（entities.py）

- [x] `DistanceCacheEntry`（frozen）を定義する（正規化済みキー + 大円距離）

### Step 6: U-02 ビジネスロジック生成（cache_port.py）

- [x] `P-03 DistanceCachePort` を `Protocol` として定義する（`get_distance`, `put_distances`, `invalidate_all`）
- [x] 実装は U-03 が行う旨を docstring に明記する

### Step 7: U-02 ビジネスロジック生成（calculator.py、純粋関数）

- [x] `EARTH_RADIUS_KM = 6371.0088`（BR-D05）
- [x] `haversine_distance_km(a, b)` — 大円距離。INV-07a, INV-08a
- [x] `actual_travel_distance_km(gc, detour)` — 迂回係数
- [x] `travel_time_seconds(km, kmh)` — `ceil`（BR-D06）
- [x] `travel_cost_yen(km, cost_model)` — 距離帯の線形探索（BR-D08）
- [x] `compute_travel_metrics(from, to, params)` — 同一校区の分岐（BR-D07）
- [x] 純粋関数のみ。標準ライブラリ `math` のみに依存

### Step 8: U-02 ビジネスロジック生成（matrix.py）

- [x] `compute_district_distance_matrix(districts)` — 全ペアの大円距離。キー正規化（U01-H1）

### Step 9: U-02 公開 API（__init__.py）

- [x] 算出関数、`compute_district_distance_matrix`, `DistanceCachePort`, `DistanceCacheEntry` を再エクスポート

### Step 10: U-01 のテストと生成器を更新（generators.py）

- [x] `gen_travel_parameters()` を `cost_model` 対応に更新する（`unit_price_per_km` を削除）
- [x] `gen_cost_model()` を追加する（単調非減少を満たす妥当なモデル）
- [x] `gen_non_monotonic_cost_model()` を追加する（否定的生成器、BR-D04 の拒否経路用）

### Step 11: U-01 のテストを更新（test_properties.py）

- [x] `TravelParameters` を構築する箇所を `cost_model` 対応にする（P-08 のテスト）

### Step 12: U-02 テスト — オラクルデータ（oracle_data.py）

- [x] 既知の座標ペアと実測距離の表を定義する（東京〜大阪 等、5〜10 ペア）。P-D05

### Step 13: U-02 テスト — 生成器（tests/distance_cost/generators.py）

- [x] U-01 の生成器を再利用する（`gen_coordinates`, `gen_school_district`, `gen_travel_parameters`）
- [x] U-02 固有の生成器を定義する（必要なら `gen_distance_pair` 等）

### Step 14: U-02 テスト — プロパティベース（test_properties.py）

- [x] **INV-07a**: `|haversine(a,b) - haversine(b,a)| < 1e-9`（Commutativity）
- [x] **INV-08a**: `haversine(a,b) >= 0`（Range constraint）
- [x] **INV-08b**: `haversine(a,a) == 0.0`（厳密）
- [x] **INV-08c**: 同一校区で `distance_km==0`, `time==fixed`, `cost==0`（Invariant）
- [x] **INV-09**: 迂回係数の単調非減少（Monotonicity）
- [x] **P-D01**: 費用の単調非減少（Monotonicity）
- [x] **P-D02**: `travel_cost_yen >= 0`（Range constraint）
- [x] **P-D03**: `travel_time_seconds >= 0`（Range constraint）
- [x] **P-D04**: 平均速度と移動時間の単調性（Monotonicity）
- [x] **P-D05**: オラクル比較（許容誤差 0.5%）（Oracle、PBT-05）
- [x] **P-D06**: `CostModel` が単調性違反を拒否する（`gen_non_monotonic_cost_model` を使用）（Invariant）

### Step 15: U-02 テスト — 例示ベース（test_examples.py、PBT-10）

- [x] US-15 の受入基準（既定パラメータでの距離・時間・費用）
- [x] 同一校区（距離 0、時間 900 秒、費用 0）
- [x] 距離帯の境界（1.9km=0円、2.0km=300円、9.9km=300円、10.0km=4000円）
- [x] 単調性違反の距離帯設定が `InvalidCostModelError` で拒否される
- [x] 無限大帯のない `CostModel` が拒否される（BR-D02）

### Step 16: N/A ステップの記録

- [x] API レイヤ / リポジトリレイヤ / フロントエンド / DB マイグレーション / デプロイ成果物を N/A として根拠付きで記録する

### Step 17: ドキュメント生成

- [x] `aidlc-docs/construction/distance-cost/code/implementation-summary.md` を作成する

---

## 4. 検証（Part 2 の最後）

- [x] `PYTHONPATH=src pytest`（U-01 と U-02 の全テスト）が通ること
- [x] `mypy`（strict）が通ること
- [x] `ruff check src tests` が通ること
- [x] `PYTHONPATH=src lint-imports` が通ること（R-3 と標準ライブラリ契約を含む）
- [x] **契約の実効性を確認**: `distance_cost` に `import numpy` を一時混入させ、契約が BROKEN になることを確認する
- [x] **U-01 の既存テストが、修正後も通ること**（回帰がないこと）

---

## 5. 拡張ルール適合確認（Part 2 の最後）

- [x] **PBT-01〜PBT-10**: 特定済みプロパティ（INV-07a/b, INV-08, INV-09, P-D01〜P-D06）の実装、オラクル（PBT-05）、否定的生成器（PBT-07）、例示ベースの併存（PBT-10）を確認する
- [x] **SECURITY-03**: U-02 が個人情報を扱わないことを確認する
- [x] **SECURITY-10**: U-02 がプロダクション依存を追加しないことを確認する（`pyproject.toml` の `dependencies` は空のまま）
- [x] **SECURITY-15**: fail closed（`CostModel` の単調性検証、`UnknownSchoolDistrictError`）を確認する
- [x] レジリエンシー拡張は無効のため適合確認を行わない旨を記録する

---

## 6. 完了処理

- [x] `aidlc-docs/aidlc-state.md` の進捗を更新する
- [ ] 標準の 2 択完了メッセージを提示し、承認を待つ

---

## 7. 計画サマリ（Step 5）

| 項目 | 内容 |
|------|------|
| **総ステップ数** | 17 |
| **U-01 の修正ファイル** | 5（value_objects.py, exceptions.py, __init__.py, generators.py, test_properties.py）— **すべてその場で修正** |
| **U-02 の新規ファイル** | 9（src 4 + tests 5）+ `.importlinter` 修正 |
| **プロダクション依存の追加** | **なし**（U-02 は標準ライブラリ `math` のみ） |
| **主担当ストーリー** | US-15 |

### 7.1 このユニットのリスク

**U-01 の承認済みコードの修正が、U-01 の既存テストを壊す可能性がある。** `TravelParameters` の署名が変わるため、`TravelParameters(...)` を呼ぶすべての箇所（生成器、P-08 テスト）を同時に更新する必要がある。Step 10, 11 でこれを行い、Step 4 の検証で「U-01 の既存テストが回帰なく通る」ことを確認する。

### 7.2 ファイル修正ルールの厳守

**既存ファイルはその場で修正する。** `value_objects_new.py` や `value_objects_modified.py` のようなコピーを作らない（code-generation.md の Brownfield File Modification Rules に相当。ここでは既存の生成済みファイルの修正に適用する）。
