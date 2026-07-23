# ユニット・オブ・ワーク定義（Unit of Work）

**作成日**: 2026-07-09
**ステージ**: INCEPTION - Units Generation - Part 2 (Generation)
**参照**: `application-design.md`, `component-dependency.md`, `unit-of-work-plan.md`

---

## 1. 分解方針（確定事項）

| 項目 | 決定 | 出典 |
|------|------|------|
| デプロイモデル | **モノリス（論理モジュール分割）** | Q1=A |
| ディレクトリ構造 | `src/{unit-name}/`, `tests/{unit-name}/` | code-generation.md（Greenfield multi-unit monolith） |
| フロントエンド | **独立ユニット** | Q2=A |
| セキュリティモジュール | **独立ユニット** | Q3=A |
| 共有ドメインモデル（C-02） | **共有カーネルユニット**（依存グラフの根） | Q4=A |
| S-04 OptimizationService | **最適化エンジンユニットに帰属** | Q5=A |
| データ管理 | **1 ユニット**（マスタ・イベント・従事可否・実績を統合） | Q6=A |
| 開発順序 | **依存順に逐次** | Q7=A |
| 所有権 | **単一チームが全ユニットを担当** | Q8=A |
| 実運用移行 | **PoC のユニット境界とは無関係。移行時に再構成する** | Q9=B |

**用語**: 本 PoC はモノリスであるため、各ユニットは**モジュール**（単一サービス内の論理的グループ）である。「ユニット・オブ・ワーク」は計画上の開発単位を指す。

---

## 2. ユニット一覧

**全 8 ユニット**。CONSTRUCTION フェーズは、依存順に 8 周のループを実行する。

| # | ユニット名 | ディレクトリ | 責務 | 依存 |
|---|-----------|------------|------|------|
| U-01 | `shared-kernel` | `src/shared-kernel/` | エンティティと値オブジェクトの定義 | なし（根） |
| U-02 | `distance-cost` | `src/distance-cost/` | 距離・移動時間・移動費用の算出（純粋関数） | U-01 |
| U-03 | `data-management` | `src/data-management/` | マスタ・イベント・従事可否申告・実績の永続化と CSV 一括処理 | U-01, U-02 |
| U-04 | `optimization-engine` | `src/optimization-engine/` | 割当最適化、制約検証、実行不可能性の診断、ジョブ管理 | U-01, U-02, U-03 |
| U-05 | `comparison-report` | `src/comparison-report/` | ベースライン再現と削減効果の算出 | U-01, U-03, U-04 |
| U-06 | `security` | `src/security/` | 認証・認可・ネットワーク統制・レート制限・入力検証・監査ログ | U-01 |
| U-07 | `api-orchestration` | `src/api-orchestration/` | REST API、割当結果の調整、設定管理、ジョブの公開 | U-01〜U-06 |
| U-08 | `frontend` | `src/frontend/` | Web UI | U-07（REST API 経由のみ） |

---

## 3. ユニット詳細

---

### U-01: `shared-kernel`（共有カーネル）

**目的**: 全ユニットが共有するエンティティと値オブジェクトを定義する。

**含まれるコンポーネント**: `C-02 AssignmentDomainModel`

**責務**:
- エンティティの定義: `Event`, `Staff`, `Facility`, `SchoolDistrict`, `AvailabilityDeclaration`, `Assignment`, `AssignmentResult`, `HistoricalRecord`
- 値オブジェクトの定義: `Coordinates`, `TravelMetrics`, `ObjectiveWeights`, `TravelParameters`, `OptimizationParameters`
- 問題の構成: `AssignmentProblem`
- `AvailabilityDeclaration.effectiveDeclarationFor()`（最新の申告を返す唯一の振る舞い）

**責務ではないこと**: ビジネスロジック、永続化、外部との通信。**このユニットは何にも依存しない。**

**この境界の根拠**: `C-02` は 14 のコンポーネントから参照される。独立させることで、ユニット間の循環依存を構造的に防ぐ。

**NFR / テスト戦略の特性**:
- NFR: なし（純粋な型定義）
- テスト: `effectiveDeclarationFor()` の不変条件（有効な申告はちょうど 1 件）に対する PBT

**関連ストーリー**: なし（全ユニットの基盤）
**関連不変条件**: US-12 の「同一の（職員, イベント）に対する有効な申告はちょうど 1 件」

---

### U-02: `distance-cost`（距離・費用算出）

**目的**: 小学校区の代表点間の距離、移動時間、移動費用を算出する。

**含まれるコンポーネント**: `C-01 DistanceCostCalculator`, `P-03 DistanceCachePort`（インターフェース定義のみ）

**責務**:
- Haversine 距離の算出
- 迂回係数を乗じた実移動距離の近似
- 平均移動速度による移動時間の算出、同一校区の固定時間
- 距離単価による移動費用の算出
- 距離キャッシュのポート定義（実装は U-03）

**この境界の根拠**: **すべて純粋関数である**（NFR-M02）。外部依存を持たないため、DB もモックも不要でテストできる。数学的性質（対称性、非負性、単調性）の検証が中心であり、他ユニットとテスト戦略が根本的に異なる。

**NFR / テスト戦略の特性**:
- NFR: NFR-M02（純粋関数）、外部 API 非依存（オフライン動作）
- テスト: **プロパティベーステスト中心**。INV-07（対称性）、INV-08（非負性・同一校区固定値）、INV-09（迂回係数の単調性）
- 技術スタック: 数値計算。特殊なライブラリを要さない

**関連ストーリー**: US-15
**関連不変条件**: INV-07, INV-08, INV-09
**申し送り**: **H-1**（`travelCostYen` の線形費用モデルは「タクシー費用の高額化」の非線形性を捉えない。距離帯モデルへの拡張を Functional Design で再検討する）

---

### U-03: `data-management`（データ管理）

**目的**: エンティティの永続化と、CSV 一括インポート／エクスポート。

**含まれるコンポーネント**: `S-01 EventService`, `S-02 MasterDataService`, `S-03 AvailabilityService`, `P-02 RepositoryPort`, `P-07 CsvCodecPort`, `A-02 PersistenceAdapter`（`P-03 DistanceCachePort` の実装を含む）, `A-04 CsvAdapter`

**責務**:
- イベントのライフサイクル管理（US-05, US-06）
- 職員・施設・小学校区マスタの CSV 一括インポートと個別修正（US-07〜US-10）
- 従事可否申告の一括登録、再申告と履歴管理、充足状況の集計（US-11〜US-13）
- 過去実績データの取り込み（US-26 の一部）
- 距離キャッシュの永続化（`P-03` の実装）
- **fail closed トランザクション**: 1 行でもエラーがあればインポート全体をロールバックする

**この境界の根拠**: いずれも「CRUD + CSV 一括処理 + トランザクション整合性」という同一の技術的性質を持つ（Q6=A）。NFR Requirements（DB 製品、トランザクション分離レベル）と NFR Design（SECURITY-05 パラメータ化クエリ、SECURITY-15 fail closed）が共通である。

**NFR / テスト戦略の特性**:
- NFR: NFR-P04（2,000 行を 30 秒以内）、SECURITY-05、SECURITY-15、トランザクション原子性
- テスト: **ラウンドトリップ性質**（INV-10）と**原子性**（インポート失敗時に DB が不変）。統合テストの比重が高い
- 技術スタック: DB、ORM またはクエリビルダ、CSV パーサ

**関連ストーリー**: US-05〜US-13、US-26（実績取り込み部分）
**関連不変条件**: INV-10（CSV ラウンドトリップ）、および原子性、施設の資格別必要人数 ≤ 必要人数、緯度経度の範囲

**注**: `A-02 PersistenceAdapter` は `P-02`（本ユニットが定義）と `P-03`（U-02 が定義）の双方を実装する。したがって U-03 は U-02 に依存する。

---

### U-04: `optimization-engine`（最適化エンジン）

**目的**: 割当最適化の実行、制約検証、実行不可能性の診断、ジョブ管理。**システムのアルゴリズム的中核。**

**含まれるコンポーネント**: `C-03 ConstraintValidator`, `C-04 InfeasibilityDiagnoser`, `S-04 OptimizationService`, `P-01 SolverPort`, `P-05 JobStorePort`, `A-03 ExactSolverAdapter`, `A-03b HeuristicSolverAdapter`, `A-03c BruteForceSolverAdapter`（テスト専用）, `A-06 JobRunnerAdapter`

**責務**:
- 割当問題の求解（一般化割当問題、最大 40 万の 0-1 決定変数）
- ハード制約 C1〜C5 の検証、ソフト制約 S1 のペナルティ算出
- 実行不可能時の原因診断と分岐（総数不足 → 追加申告を要求し C1 は緩和しない / C3 不足のみ → ビッグMでソフト化 / その他 → 原因提示のみ）
- 非同期ジョブの起動・監視・キャンセル（同一イベントにつき同時 1 ジョブ）

**この境界の根拠**: 最適化に関するすべての責務（診断、求解、ジョブ管理）が 1 ユニットに収まる（Q5=A）。ソルバーが `P-01 SolverPort` の背後にあるため、**厳密解法 ↔ 発見的解法 ↔ 総当たり法（オラクル）の差し替えがユニット内で完結する**（NFR-M01）。

**NFR / テスト戦略の特性**:
- NFR: **NFR-P02**（最大 40 万の 0-1 変数、制限時間 300 秒）、NFR-M01（アルゴリズム差し替え可能性）
- テスト: **オラクル検証（PBT-05）**が中核。`A-03c BruteForceSolverAdapter` に差し替え、小規模インスタンス（職員 10 名、施設 3 か所）で厳密解法の出力と比較する。プロダクションコードは変更しない
- 技術スタック: **MILP ソルバー**。他のユニットとは根本的に異なる依存を持つ

**関連ストーリー**: US-16〜US-20、US-23（ピン留め検証）
**関連不変条件**: INV-01（一意割当）、INV-02（定員充足）、INV-03（従事不可者の除外）、INV-04（資格・役職の充足）、INV-05（割当集合 ⊆ 従事可能集合）、INV-06（目的関数値は有限かつ非負）、INV-11（再現性）、INV-12（ビッグMによる C3 優先）、INV-13（ピン留めの不変性）
**申し送り**:
- **H-2**（13 件の不変条件を「Testable Properties」セクションへ転記する。PBT-01）
- **H-3**（厳密解法の実用性を評価し、不十分なら `A-03b` を実装する）
- **H-9**（「C3 不足のみ」の判定を厳密に行うか近似するか）
- **H-10**（ビッグMの下限が INV-12 を満たすことを示す）

---

### U-05: `comparison-report`（比較レポート）

**目的**: 過去イベントを同一条件で再現し、削減効果を算出する。**成功基準 SC-01 に直結する。**

**含まれるコンポーネント**: `C-05 ComparisonAnalyzer`, `S-06 ComparisonReportService`

**責務**:
- 過去実績から各施設の必要人数を導出する（実績の割当人数）
- 過去イベントの従事可能職員集合を特定する
- 再現用の `AssignmentProblem` を組み立てる（職員属性は現在の値。A-09）
- **最適化を U-04 に委譲する**（独自の最適化ロジックを持たない。Follow-up Q1=A）
- 総移動時間・総移動費用・最大移動時間の削減量と削減率、および移動時間の分布を算出する
- 実績のない新規イベントに対する手動ベースライン入力

**この境界の根拠**: 集計と出力が中心であり、最適化とはテスト戦略が異なる。**最適化ロジックを持たないことを、ユニット境界としても明示する。** これにより、レポートが示す削減効果はシステムが実際に生成する割当を反映する（SC-01 の妥当性）。

**NFR / テスト戦略の特性**:
- NFR: なし（集計処理）
- テスト: 導出の正確性（実績の割当人数 == 導出された必要人数）に対する PBT。削減量の符号一貫性
- 技術スタック: 集計、ヒストグラム算出

**関連ストーリー**: US-26, US-27, US-28
**関連不変条件**: 実績の割当人数 == 導出された必要人数、実績の割当職員集合 ⊆ 従事可能職員集合、削減量 = ベースライン値 − 最適化後の値

---

### U-06: `security`（セキュリティ）

**目的**: 認証・認可・ネットワーク統制・レート制限・入力検証・監査ログ。**横断的関心事。**

**含まれるコンポーネント**: `SEC-01 AuthenticationModule`, `SEC-02 AuthorizationModule`, `SEC-03 NetworkControlModule`, `SEC-04 RateLimitModule`, `SEC-05 InputValidationModule`, `S-08 AuditService`, `P-04 AuditLogPort`, `A-05 AuditLogAdapter`

**責務**:
- サーバー側セッションの発行・検証・失効、アカウントロック（US-01）
- deny by default の認可ガード、オブジェクトレベル認可（US-01、MU-01）
- 庁内出口 IP の許可リスト検証（US-02）
- 公開エンドポイントのレート制限（MU-03）
- 型・長さ・書式・サイズ上限の検証、CSV 数式インジェクションの無害化（MU-02）
- 監査ログの記録と改竄防止（US-03, US-04、MU-04）

**この境界の根拠**: SECURITY-11「セキュリティ上重要なロジックを専用モジュールに隔離する」を、**ユニット境界としても表現する**（Q3=A）。独自の Functional Design（認証フロー、認可ポリシー、レート制限の閾値）と NFR Requirements（ハッシュアルゴリズム、セッション管理）を必要とする。

**NFR / テスト戦略の特性**:
- NFR: SECURITY-03, 04, 05, 07, 08, 09, 11, 12, 13, 14, 15、NFR-S10.1, NFR-S10.2
- テスト: **セキュリティテスト中心**。誤用シナリオ（MU-01〜MU-04）に対する攻撃的テスト。deny by default の網羅検証
- 技術スタック: 暗号ライブラリ、セッションストア

**関連ストーリー**: US-01, US-02, US-03, US-04
**関連誤用シナリオ**: MU-01, MU-02, MU-03, MU-04
**関連不変条件**: 認証を要求しないエンドポイントの集合 == 明示的に定義された公開エンドポイント集合、変更操作数 ≤ 監査ログエントリ数

**重要**: `P-04 AuditLogPort` は削除・更新のメソッドを**定義しない**（SECURITY-14）。監査ログの書き込みは業務トランザクションの外側で行う。

---

### U-07: `api-orchestration`（API・オーケストレーション）

**目的**: REST API の公開と、割当結果の調整・設定管理のオーケストレーション。

**含まれるコンポーネント**: `A-01 RestApiAdapter`, `S-05 AssignmentAdjustmentService`, `S-07 ConfigService`, `P-06 ConfigPort`, `A-07 ConfigAdapter`

**責務**:
- HTTP エンドポイントの公開。セキュリティモジュール（U-06）をミドルウェアとして適用する
- HTTP セキュリティヘッダの設定（SECURITY-04）
- 割当結果の一覧表示、手動修正、ピン留め、再最適化モードの選択（US-21〜US-25）
- 算出パラメータと目的関数の重みの取得・更新（US-14）
- 最適化ジョブの状態を REST で公開する（ポーリング用）
- 設定値の外部化（NFR-M03）

**この境界の根拠**: フロントエンドとバックエンドの API 境界（NFR-M05）を担う。他のユニットを統合する層であり、単独では機能しない。

**NFR / テスト戦略の特性**:
- NFR: SECURITY-04（HTTP ヘッダ）、SECURITY-09（エラー応答）、NFR-M03（設定の外部化）、NFR-M05（API 境界）
- テスト: API 契約テスト、ミドルウェア連鎖の順序検証
- 技術スタック: Web フレームワーク

**関連ストーリー**: US-14, US-21, US-22, US-23, US-24, US-25

---

### U-08: `frontend`（フロントエンド）

**目的**: 割当担当者（P-01）とシステム管理者（P-02）が操作する Web UI。

**含まれるコンポーネント**: `F-01 WebFrontend`

**責務**:
- 画面の描画と操作
- **REST API（JSON over HTTP）経由でのみバックエンドと通信する**（NFR-M05）
- バックエンドのエンドポイント URL を設定として外部化する
- 最適化ジョブの進捗をポーリングで取得する

**この境界の根拠**: NFR-M05 の境界がユニット境界と一致する（Q2=A）。バックエンドとは異なる技術スタックを持ちうる。

**禁止事項**: バックエンドのサービス層（S-01〜S-08）やドメイン層（C-01〜C-05）を直接呼び出すこと。同一のメモリ空間上のオブジェクトを共有すること。

**NFR / テスト戦略の特性**:
- NFR: NFR-M05（API 境界）
- テスト: UI テスト、API モックを用いたコンポーネントテスト
- 技術スタック: フロントエンドフレームワーク（NFR Requirements で決定）

**関連ストーリー**: 全ストーリーの UI 部分（主担当は各バックエンドユニット）
**申し送り**: **H-5**（Code Generation ステージで、フロントエンドがバックエンドの型やモジュールを import していないことを、ビルド設定またはリンタ規則で機械的に検証する）

---

## 4. コード構成戦略（Greenfield、Q1=A）

`code-generation.md` の Critical Rules に従う。**Greenfield multi-unit (monolith)** のパターンを適用する。

```text
<WORKSPACE-ROOT>/                    # /home/llm-user/AI-DLC_test
├── src/
│   ├── shared-kernel/               # U-01
│   ├── distance-cost/               # U-02
│   ├── data-management/             # U-03
│   ├── optimization-engine/         # U-04
│   ├── comparison-report/           # U-05
│   ├── security/                    # U-06
│   ├── api-orchestration/           # U-07
│   └── frontend/                    # U-08
│
├── tests/
│   ├── shared-kernel/
│   ├── distance-cost/
│   ├── data-management/
│   ├── optimization-engine/
│   ├── comparison-report/
│   ├── security/
│   ├── api-orchestration/
│   └── frontend/
│
├── config/                          # NFR-M03: 外部化された設定
│
└── aidlc-docs/                      # ドキュメントのみ。アプリケーションコードを置かない
```

**CRITICAL**: アプリケーションコードはワークスペースルート配下にのみ配置する。`aidlc-docs/` には**決して配置しない**。`aidlc-docs/construction/{unit-name}/code/` にはマークダウンのサマリのみを置く。

**モジュール境界の強制**: モノリスであっても、ユニット間の依存は依存マトリクス（`unit-of-work-dependency.md`）に従う。ビルド設定またはリンタ規則で、許可されていない import を検出する。特に:
- `src/frontend/` は `src/` 配下のバックエンドユニットを import してはならない（NFR-M05）
- `src/shared-kernel/` は他のいかなるユニットも import してはならない（依存グラフの根）
- `src/distance-cost/` は `src/shared-kernel/` 以外を import してはならない（純粋関数、NFR-M02）

---

## 5. 実運用移行との関係（Q9=B）

Q9=B により、**実運用のデプロイ構成は本 PoC のユニット境界とは無関係**とし、移行時に再構成する。

したがって、本 PoC では以下を**約束しない**。
- フロントエンドとバックエンドを別のデプロイ成果物として生成すること
- ユニット境界がそのままデプロイ境界の移行単位になること

**ただし、以下は引き続き必須である**（承認済みの要件であり、本ステージの決定では覆らない）。

| 要件 | 内容 |
|------|------|
| **NFR-M05** | フロントエンドとバックエンドは明示的な API 境界（REST/JSON over HTTP）で分離する。プロセス内の直接呼び出しを禁止する。バックエンドのエンドポイント URL は設定として外部化する |
| **A-07** | PoC ではフロントエンドとバックエンドを同一のインターネット側サーバー上で稼働させる |
| **A-08** | PoC では従事可否申告を担当者が代理で CSV 一括登録する。実運用では職員本人が入力する |

**Infrastructure Design への申し送り（H-8 の更新）**: 実運用のデプロイトポロジは PoC のユニット境界の対象外である。一方、NFR-M05 の API 境界と、エンドポイント URL の外部化は必須である。

---

## 6. CONSTRUCTION フェーズのループ計画

各ユニットについて、以下の 5 ステージを実行する（Functional Design 〜 Code Generation）。全ユニット完了後に Build and Test を 1 回実行する。

| 周回 | ユニット | Functional Design | NFR Requirements | NFR Design | Infrastructure Design | Code Generation |
|:----:|---------|:-----------------:|:----------------:|:----------:|:---------------------:|:---------------:|
| 1 | U-01 shared-kernel | 実行 | 実行 | 実行 | 実行 | 実行 |
| 2 | U-02 distance-cost | 実行 | 実行 | 実行 | 実行 | 実行 |
| 3 | U-03 data-management | 実行 | 実行 | 実行 | 実行 | 実行 |
| 4 | U-04 optimization-engine | 実行 | 実行 | 実行 | 実行 | 実行 |
| 5 | U-05 comparison-report | 実行 | 実行 | 実行 | 実行 | 実行 |
| 6 | U-06 security | 実行 | 実行 | 実行 | 実行 | 実行 |
| 7 | U-07 api-orchestration | 実行 | 実行 | 実行 | 実行 | 実行 |
| 8 | U-08 frontend | 実行 | 実行 | 実行 | 実行 | 実行 |

**注**: `execution-plan.md` は Functional Design / NFR Requirements / NFR Design / Infrastructure Design を「EXECUTE（per unit）」と定めた。ただし各ステージは条件付きであり、ユニットによっては該当する内容が乏しい場合がある（例: U-01 shared-kernel の Infrastructure Design）。各ユニットのステージ開始時に、そのユニットにとって当該ステージが価値を持つかを再評価し、価値がなければスキップを提案する。

**技術スタックの決定**: `execution-plan.md` の申し送り H-3, H-4 により、技術スタックは NFR Requirements ステージで決定する。ただし本システムはモノリスであり、全ユニットが同一の実行環境を共有する。したがって、**最初のユニット（U-01）の NFR Requirements ステージで、バックエンド全体の技術スタック（言語、フレームワーク、DB、ソルバー、PBT フレームワーク）を決定する**。U-08 frontend のみ、独自のフロントエンド技術スタックを決定する。
