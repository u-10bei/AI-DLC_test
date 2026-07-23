# 実装サマリ — U-02 `distance-cost`

**作成日**: 2026-07-16
**ステージ**: CONSTRUCTION - Code Generation - Part 2（ユニット 2 / 8）

**本文書はマークダウンのサマリのみである。アプリケーションコードはワークスペースルート配下にある。**

---

## 1. 生成・修正したファイル

### 1.1 U-01 の承認済みコードの修正（その場で修正、U02-H8）

| ファイル | 修正内容 |
|---------|---------|
| `src/shared_kernel/value_objects.py` | `CostRule`, `CostBand`, `CostModel`, `DEFAULT_COST_MODEL` を追加。`TravelParameters.unit_price_per_km` を削除し `cost_model` を追加。`_MONOTONIC_TOLERANCE_YEN` を追加 |
| `src/shared_kernel/exceptions.py` | `InvalidCostModelError`, `UnknownSchoolDistrictError` を追加 |
| `src/shared_kernel/__init__.py` | 新しい型・例外を再エクスポート |
| `tests/shared_kernel/generators.py` | `gen_travel_parameters` を `cost_model` 対応に。`gen_cost_model`, `gen_non_monotonic_cost_model_kwargs` を追加 |

**すべてその場で修正した。コピー（`value_objects_new.py` 等）は作っていない。**

### 1.2 U-02 の新規ファイル（アプリケーションコード）

| ファイル | 内容 |
|---------|------|
| `src/distance_cost/__init__.py` | 公開 API |
| `src/distance_cost/entities.py` | `DistanceCacheEntry`, `canonical_key()` |
| `src/distance_cost/cache_port.py` | `DistanceCachePort`（Protocol） |
| `src/distance_cost/calculator.py` | 距離・時間・費用の算出関数（純粋） |
| `src/distance_cost/matrix.py` | `compute_district_distance_matrix()` |
| `.importlinter` | R-3 契約 + 標準ライブラリのみ契約を追加 |

### 1.3 U-02 のテスト

| ファイル | 内容 |
|---------|------|
| `tests/distance_cost/oracle_data.py` | 既知の座標ペアと大円距離（P-D05） |
| `tests/distance_cost/test_properties.py` | INV-07a, INV-08a/b/c, INV-09, P-D01〜P-D06 |
| `tests/distance_cost/test_examples.py` | US-15、距離帯境界、費用モデルの拒否、行列 |

### 1.4 ドキュメント

`aidlc-docs/construction/distance-cost/code/implementation-summary.md`（本文書）

---

## 2. 検証結果

**4 つのゲートすべて通過。** Build and Test ステージで再実行する。

| ゲート | コマンド | 結果 |
|-------|---------|------|
| 単体テスト | `PYTHONPATH=src pytest` | **74 passed**（U-01 の 43 + U-02 の 31） |
| 単体テスト（CI プロファイル、max_examples=500） | `CI=true ... pytest` | **74 passed** |
| 型検査 | `mypy`（strict） | **Success: 23 files** |
| リンタ | `ruff check` | **All checks passed** |
| ユニット境界 | `lint-imports` | **Contracts: 4 kept, 0 broken** |

### 2.1 契約の実効性の確認

`distance_cost/calculator.py` に `import numpy` を意図的に混入 → `distance_cost uses the standard library only` **BROKEN**（exit 1）。削除 → **4 kept**。

**U-02 の純粋関数性は機械的に強制されている。** R-3（ユニット境界）だけでは `import numpy` を防げないため、標準ライブラリのみ契約が第 2 層として機能する。

### 2.2 U-01 の既存テストが回帰していないこと

`TravelParameters` の署名変更（`unit_price_per_km` 削除、`cost_model` 追加）にもかかわらず、U-01 の既存 43 テストは修正後も全て通過した。生成器と P-08 テストを同じステージで更新したため。

---

## 3. プロパティベーステストが発見した 2 件の実バグ

**これが本ユニットで最も重要な出来事である。** プロパティテストが、実装と生成器の欠陥を捕まえた。

### 3.1 バグ 1: `gen_cost_model` が自身の検証に拒否されるモデルを生成した

`gen_cost_model` は境界で `slope * boundary >= running_cost` を満たすよう `min_slope = running_cost / last_boundary` を計算していた。しかし浮動小数点の丸めで `0.5263... * 1.9 = 0.9999999999999999 < 1.0` となり、**生成器が作った「妥当なはずのモデル」が `CostModel` の生成時に `InvalidCostModelError` で拒否された**。

`test_pd01_cost_monotone_in_distance` と `test_pd06_valid_cost_model_is_accepted` が捕捉。

**修正**: 生成器の `min_slope` にマージン（`* 1.001 + 0.001`）を加え、検証の許容誤差境界にちょうど乗らないようにした。

### 3.2 バグ 2: `CostModel._validate_monotonic` が許容誤差なしの厳密不等号だった（実運用リスク）

`_validate_monotonic` は `cost_below > cost_above` で判定していた。これは**実運用リスク**である。担当者が境界で連続な距離帯（例: 公共交通 300 円 → タクシー 30 円/km で 10 km 境界がちょうど 300 円）を設定したとき、浮動小数点の丸めで `cost_below` が `cost_above` をわずかに上回り、**不当に拒否される**。

**修正**: 許容誤差 `_MONOTONIC_TOLERANCE_YEN = 1e-6` を導入。`cost_below - cost_above > EPS` で判定する。単調性の趣旨は「費用が**減少しない**こと」であり、ナノ円未満の差は実質的な減少ではない。1 円を大きく下回る許容値なので、真に「遠いほど安い」設定は依然として拒否される。

**この修正は、テストがなければ実運用で初めて顕在化していた。** プロパティテストが設計段階で捕まえた。

---

## 4. 近距離データの精度に関する確認（ユーザーからの指摘）

ユーザーから「近距離ペアで丸め誤差が相対的に大きく出るなら、小学校区というごく近距離のデータが多い本アプリは大丈夫か」との指摘があった。

**検証の結果、問題ないことを確認した。**

| 距離 | Haversine の相対誤差 |
|------|-------------------|
| 10 m | 0.1757% |
| 100 m | 0.1757% |
| 1 km | 0.1757% |
| 5 km | 0.1757% |

**Haversine の相対誤差は距離に依存せず一定である。** これは球体近似（地球の扁平を無視すること）による系統誤差であり、0.5% 以内。距離が近いほど誤差が拡大することはない。

（当初「近距離ペアで誤差が大きい」と説明したのは誤りだった。Tokyo-Yokohama の 1.43% ずれは、オラクル表の参考値「27.7 km」が営業キロ寄りの不正確な値だったためで、Haversine の精度でも近距離特有の問題でもなかった。参考値を Tokyo-Sendai に差し替えて解消した。）

**本アプリへの含意**: 小学校区間の距離（数百 m〜十数 km）の Haversine 誤差は約 0.2% であり、しかも迂回係数（既定 1.3）の近似誤差に比べれば無視できる。精度上の問題はない。

---

## 5. 実装の要点

### 5.1 距離帯モデルが課題②を直接モデル化する

`test_the_taxi_threshold_is_a_real_step`: 既定モデルで 9.9 km は 300 円、10.0 km は 4,000 円。この段差が、最適化に「タクシーの閾値を越えさせない」インセンティブを与える。線形モデルでは存在しない。

### 5.2 キーの正規化で INV-07b が構造的に厳密

`canonical_key(x, y) = (min, max)`。`test_distance_matrix_keys_are_canonicalised` で、順序を入れ替えた入力でも同一のキーになることを確認。

### 5.3 同一校区の移動時間は 0 でなく 900 秒

`test_us15_same_district`: 距離 0、費用 0、しかし時間は 900 秒（FR-03.7）。距離 0 として扱うと、最適化が同一校区割当を無条件に優先する。

---

## 6. 拡張ルール適合サマリ

### 6.1 PBT Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| PBT-01 | **適合** | INV-07a, INV-08a/b/c, INV-09, P-D01〜P-D06 を実装 |
| PBT-03 | **適合** | 不変条件のプロパティ |
| **PBT-05 オラクル** | **適合** | `oracle_data.py` の 5 ペアと 0.5% 許容で比較。対称性・非負性では捕まらない実装誤りを検出する |
| PBT-07 | **適合** | U-01 の生成器を再利用。`gen_cost_model`, `gen_non_monotonic_cost_model_kwargs`（否定的生成器）を追加 |
| PBT-08 | **適合** | U-01 の `conftest.py` を継承。ランダムシード、失敗時に出力 |
| PBT-09 | **適合** | Hypothesis を継承。U-02 で追加なし |
| PBT-10 | **適合** | `test_examples.py` に US-15・距離帯・費用モデル拒否の例示テスト |
| PBT-02, 04, 06 | **N/A** | 純粋関数、状態なし、直列化なし |

**ブロッキング所見: なし**

### 6.2 Security Compliance

| ルール | 判定 | 根拠 |
|--------|------|------|
| SECURITY-03 | **適合** | U-02 は個人情報を扱わない。`UnknownSchoolDistrictError` の文脈は小学校区 ID のみ |
| SECURITY-10 | **適合** | **U-02 はプロダクション依存を追加しない**（`math` のみ）。脆弱性スキャン対象を増やさない |
| SECURITY-11 | **適合** | 純粋関数性を 2 層のリンタ契約で強制 |
| SECURITY-15 | **適合** | `CostModel` の単調性検証、`UnknownSchoolDistrictError`（`None` を返さない） |
| SECURITY-01, 02, 04〜09, 12〜14 | **N/A** | 純粋関数。R-3 + 標準ライブラリ契約が永続化・ネットワーク・ログを構造的に到達不能にする |

**ブロッキング所見: なし**

### 6.3 Resiliency Extension

**スキップ**（Enabled = No）。

---

## 7. N/A とした標準ステップ

| ステップ | 根拠 |
|---------|------|
| API レイヤ | U-07 が所有 |
| リポジトリレイヤ | `P-03` の実装は U-03 |
| フロントエンド | U-08 |
| DB マイグレーション | U-02 は永続化を持たない |
| デプロイ成果物 | U-02 は独立デプロイされない |

---

## 8. 後続への申し送り

前ステージからの申し送り（U02-H1〜H10）は各設計文書に記録済み。本ステージで解決したもの。

| ID | 状態 |
|----|------|
| U02-H8（U-01 コード修正） | **✅ 完了**。その場で修正 |
| U02-H9（U-01 テスト更新） | **✅ 完了**。回帰なし |
| U01-H28（R-3 契約追加） | **✅ 完了**。契約の実効性も確認 |
| U01-H29（生成器の再利用） | **✅ 完了** |

**新規の申し送り**: なし。U02-H1〜H7, H10 は後続ユニット（U-03, U-04, U-07）が引き続き参照する。
