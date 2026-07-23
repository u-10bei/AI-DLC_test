# Unit of Work Plan（ユニット分解計画）

**作成日**: 2026-07-09
**ステージ**: INCEPTION - Units Generation - Part 1 (Planning)
**参照**: `requirements.md` v1.3, `stories.md`（28 ストーリー）, `application-design.md`, `components.md`, `component-dependency.md`, `execution-plan.md`

---

## 1. 目的とスコープ

本ステージでは、システムを**開発上の管理単位（ユニット・オブ・ワーク）**に分解する。

**用語**（`common/terminology.md` に準拠）:
- **Service**: 独立してデプロイ可能なコンポーネント
- **Module**: サービス内の論理的なグループ
- **Unit of Work**: 計画上の開発単位

各ユニットは、CONSTRUCTION フェーズで **Functional Design → NFR Requirements → NFR Design → Infrastructure Design → Code Generation** のループを 1 周する。したがって、ユニットの境界は「異なる非機能要件・テスト戦略・技術スタックを必要とするか」で引くのが自然である。

---

## 2. Application Design からの入力

### 2.1 コンポーネント一覧（再掲）

| 分類 | コンポーネント |
|------|--------------|
| ドメイン | C-01 DistanceCostCalculator（純粋）、C-02 AssignmentDomainModel、C-03 ConstraintValidator（純粋）、C-04 InfeasibilityDiagnoser（純粋）、C-05 ComparisonAnalyzer（純粋） |
| ポート | P-01 SolverPort、P-02 RepositoryPort、P-03 DistanceCachePort、P-04 AuditLogPort、P-05 JobStorePort、P-06 ConfigPort、P-07 CsvCodecPort |
| サービス | S-01 Event、S-02 MasterData、S-03 Availability、S-04 Optimization、S-05 AssignmentAdjustment、S-06 ComparisonReport、S-07 Config、S-08 Audit |
| アダプタ | A-01 RestApi、A-02 Persistence、A-03 ExactSolver、A-03b HeuristicSolver、A-03c BruteForceSolver（テスト専用）、A-04 Csv、A-05 AuditLog、A-06 JobRunner、A-07 Config |
| セキュリティ | SEC-01 Authentication、SEC-02 Authorization、SEC-03 NetworkControl、SEC-04 RateLimit、SEC-05 InputValidation |
| フロントエンド | F-01 WebFrontend |

### 2.2 Application Design が示唆したユニット候補

`application-design.md` セクション 6 は、以下の 5 ユニットを候補として示した。

1. 距離・費用算出
2. 最適化エンジン
3. データ管理
4. 比較レポート
5. Web UI / API・セキュリティ

---

## 3. 検討すべき論点（本計画で提起する）

Application Design の候補には、確定前に解決すべき論点が 3 つある。

### 論点 1: 「Web UI / API・セキュリティ」ユニットが過大である

候補 5 は、フロントエンド（F-01）、REST アダプタ（A-01）、セキュリティモジュール 5 件（SEC-01〜05）、サービス 4 件（S-04, S-05, S-07, S-08）、ポート 3 件、アダプタ 4 件を含む。これは他の 4 ユニットの合計に匹敵する規模である。

さらに、**フロントエンドとバックエンドを同一ユニットに含めることは NFR-M05（明示的な API 境界）の趣旨に反する**。両者は異なる技術スタック（NFR Requirements ステージで決定）を持ちうる。

→ **Question 2, Question 3 で確認する。**

### 論点 2: `C-02 AssignmentDomainModel` はほぼ全ユニットから参照される

依存マトリクス（`component-dependency.md` セクション 2）によれば、`C-02` は C-03, C-04, C-05, S-01〜S-07, A-01, A-02, A-03, A-04, A-06 から参照される。どのユニットに帰属させるかを決めないと、ユニット間に循環依存が生じる。

→ **Question 4 で確認する。**

### 論点 3: `S-04 OptimizationService` の帰属

`S-04` は最適化ジョブのオーケストレーションを担う。ドメイン層の `C-04 InfeasibilityDiagnoser` と、ポート `P-01 SolverPort`、`P-05 JobStorePort` に依存する。また `S-05` と `S-06` から呼ばれる。

「最適化エンジン」ユニットに含めるか、「API・オーケストレーション」ユニットに含めるかで、ユニット間の依存の形が変わる。

→ **Question 5 で確認する。**

---

## 4. 明確化質問

以下の質問に、`[Answer]:` タグの後に選択肢の記号を記入してご回答ください。当てはまる選択肢がない場合は最後の「Other」を選び、内容を記述してください。すべて回答し終えたら「完了」とお知らせください。

---

### Question 1: デプロイモデル（Technical Considerations / Code Organization）

**この回答がディレクトリ構造を決定します**（`code-generation.md` の構造パターン）。

A) **モノリス（論理モジュール分割）** — 単一のデプロイ単位の中に、ユニットを論理モジュールとして配置する。ディレクトリ構造は `src/{unit-name}/`, `tests/{unit-name}/`。PoC の規模と、単一チームでの開発に適する。実運用でバックエンドをオンプレミスへ分離する際も、モジュール境界がそのまま移行の単位になる **（推奨）**

B) **マイクロサービス** — 各ユニットを独立してデプロイ可能なサービスとする。ディレクトリ構造は `{unit-name}/src/`, `{unit-name}/tests/`。ユニット間はネットワーク越しに通信する。PoC の規模に対して運用負荷が過大であり、A-07（PoC は単一サーバー）とも整合しない

C) **単一ユニット（分解しない）** — システム全体を 1 ユニットとして扱う。ディレクトリ構造は `src/`, `tests/`。CONSTRUCTION フェーズのループは 1 周のみ。ただし、最適化エンジン（PBT のオラクル検証が必要）とデータ管理（トランザクション整合性が必要）が同じ NFR Requirements / NFR Design を共有することになり、Execution Plan の判断（ユニット分解を実行する）と矛盾する

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 2: フロントエンドを独立したユニットとするか（Story Grouping / Technical Considerations）

**論点 1 への対応です。**

NFR-M05 により、フロントエンドとバックエンドは明示的な API 境界で分離されます。両者は異なる技術スタックを持ちうるため、必要とする NFR Requirements / NFR Design も異なります。

A) **フロントエンドを独立したユニットとする** — フロントエンド（F-01）は独自の Functional Design / NFR Requirements / NFR Design / Code Generation ループを持つ。NFR-M05 の境界がユニット境界と一致し、実運用での分離時に構造が変わらない **（推奨）**

B) **フロントエンドをバックエンドの API ユニットに含める** — 1 ユニットとして扱う。NFR-M05 はコード内の規約で担保する

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 3: セキュリティモジュールの配置（Business Domain / Dependencies）

セキュリティモジュール群（SEC-01〜SEC-05）は、SECURITY-11 に基づき専用モジュールに隔離することが確定しています。開発単位としてどう扱いますか？

A) **独立したユニットとする** — セキュリティは独自の Functional Design（認証フロー、認可ポリシー、レート制限の閾値）と NFR Requirements（暗号化アルゴリズム、セッション管理）を必要とする。他ユニットは横断的にこれを利用する **（推奨。SECURITY-11 の隔離をユニット境界としても表現できる）**

B) **API・オーケストレーションユニットに含める** — セキュリティモジュールは REST アダプタのミドルウェアとして適用されるため、同一ユニットとする

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 4: 共有ドメインモデル（`C-02`）の扱い（Dependencies）

**論点 2 への対応です。**

`C-02 AssignmentDomainModel`（Event, Staff, Facility, SchoolDistrict, AvailabilityDeclaration, Assignment など）は、ほぼ全ユニットから参照されます。

A) **「共有カーネル（Shared Kernel）」ユニットとして独立させる** — エンティティと値オブジェクトのみを含む。ビジネスロジックを持たない。全ユニットがこれに依存するが、これは何にも依存しない（依存グラフの根）。ユニット間の循環依存を構造的に防ぐ **（推奨）**

B) **「データ管理」ユニットに含める** — データ管理ユニットがドメインモデルを所有し、他ユニットはそれに依存する。データ管理ユニットが実質的に共有カーネルになる

C) **各ユニットが独自のモデルを持ち、境界で変換する** — 完全な独立性が得られるが、変換コードの重複が生じる。PoC の規模には過剰

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 5: `S-04 OptimizationService` の帰属（Dependencies）

**論点 3 への対応です。**

`S-04` は最適化ジョブのオーケストレーション（診断分岐、ジョブ起動、キャンセル）を担います。`S-05` と `S-06` から呼ばれます。

A) **「最適化エンジン」ユニットに含める** — 最適化に関する責務（診断、ソルバー呼び出し、ジョブ管理）を 1 ユニットに集約する。`S-05` と `S-06` は最適化エンジンユニットに依存する **（推奨。最適化に関する Functional Design と NFR Requirements が 1 ユニットに収まる）**

B) **「API・オーケストレーション」ユニットに含める** — サービス層はすべて API ユニットに置き、最適化エンジンユニットはドメイン（C-02, C-03, C-04）とポート（P-01）とアダプタ（A-03）のみを含む

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 6: 「データ管理」ユニットの分割（Story Grouping / Business Domain）

「データ管理」候補は、マスタデータ（職員・施設・小学校区）、イベント、従事可否申告、過去実績の 4 種を扱います。エピックでは E2（イベント管理）、E3（マスタデータ管理）、E4（従事可否申告）に対応します。

A) **1 ユニットにまとめる** — いずれも「CRUD + CSV 一括インポート + fail closed トランザクション」という同一の技術的性質を持つ。NFR Requirements / NFR Design が共通である **（推奨）**

B) **マスタデータと従事可否申告を分ける** — 従事可否申告は実運用で職員本人が入力する（A-08）ため、将来的に独立した認証・認可要件を持つ

C) **エピック単位（E2 / E3 / E4）で 3 ユニットに分ける** — ユニット数が増え、CONSTRUCTION フェーズのループが 3 周増える

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 7: ユニットの開発順序と並行性（Team Alignment）

`component-dependency.md` の依存関係から、以下の順序が導かれます。

```text
共有カーネル
     |
     +--> 距離・費用算出 ---+
     |                      |
     |                      v
     +--> データ管理 -----> 最適化エンジン ---> 比較レポート
     |                      |                        |
     |                      v                        v
     +--> セキュリティ ---> API・オーケストレーション
                                    |
                                    v
                              フロントエンド
```

A) **依存順に逐次開発する** — 上流ユニットが完成してから下流に進む。手戻りが少ないが、時間がかかる **（推奨。単一チームでの開発を想定）**

B) **並行開発する** — 独立したユニット（距離・費用算出、データ管理、セキュリティ）を並行して開発する。インターフェースを先に固定する必要がある

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 8: チーム構成と所有権（Team Alignment）

A) **単一チームがすべてのユニットを担当する** — PoC の規模に適する。所有権の境界を設ける必要がない **（推奨）**

B) **ユニットごとに担当を分ける** — 所有権とレビュー責任をユニット境界に沿って定める

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: A

---

### Question 9: 実運用移行時のユニット境界（Technical Considerations、申し送り H-8）

実運用では、バックエンドを庁内オンプレミスへ分離します（A-07）。この移行が、ユニット境界とどう関係すべきですか？

A) **フロントエンドユニット以外のすべてがオンプレミスへ移動する** — ユニット境界が、そのままデプロイ境界の移行単位になる。モノリス（Q1=A）であっても、フロントエンドとバックエンドは別のデプロイ成果物として生成する **（推奨）**

B) **実運用の構成は本 PoC のユニット境界と無関係とする** — 移行時に再構成する

X) Other（`[Answer]:` の後に自由に記述してください）

[Answer]: B

---

## 5. 実行チェックリスト（Part 2: Generation で実行）

**注意**: 本計画の承認後に実行する。各ステップ完了時に即座に `[x]` へ更新する。

### 5.1 ユニット定義

- [x] Q1〜Q6 の回答に基づき、ユニットの一覧と境界を確定する（8 ユニット: U-01〜U-08）
- [x] 各ユニットについて、名称・目的・責務・含まれるコンポーネントを定義する
- [x] 各ユニットが必要とする NFR とテスト戦略の差異を記述する（ユニット境界の妥当性の根拠）
- [x] Q9 の回答に基づき、実運用移行時のデプロイ境界との関係を記述する（unit-of-work.md セクション 5。Q9=B により PoC のユニット境界とは無関係。ただし NFR-M05 は引き続き必須）
- [x] **Greenfield**: Q1 の回答に基づき、コード構成戦略（ディレクトリ構造）を `unit-of-work.md` に記述する（`src/{unit-name}/`, `tests/{unit-name}/`）
- [x] `aidlc-docs/inception/application-design/unit-of-work.md` を作成する

### 5.2 ユニット依存関係

- [x] Q4 の回答に基づき、共有カーネルの位置づけを確定する（U-01。依存グラフの根。何にも依存しない）
- [x] Q5 の回答に基づき、`S-04 OptimizationService` の帰属を確定する（U-04 optimization-engine）
- [x] ユニット間の依存マトリクスを作成する
- [x] **循環依存が存在しないことを検証する**（マトリクスの上三角がすべて `-`。U-01 → U-08 の番号順に依存が向かう DAG）
- [x] Q7 の回答に基づき、開発順序（クリティカルパス）を記述する（U-01 → U-02 → U-03 → U-04 → U-05 → U-06 → U-07 → U-08）
- [x] ユニット間の通信パターンを記述する（モノリスのためプロセス内呼び出し。U-07 ↔ U-08 のみ REST）
- [x] 依存関係図を作成する（Mermaid + テキスト代替、content-validation.md に従う）
- [x] `aidlc-docs/inception/application-design/unit-of-work-dependency.md` を作成する

### 5.3 ストーリーマッピング

- [x] 全 28 ストーリー（US-01〜US-28）を、いずれかのユニットに割り当てる
- [x] 複数ユニットにまたがるストーリーは、主担当ユニットと協力ユニットを明示する
- [x] **すべてのストーリーが割り当てられていることを検証する**（漏れゼロ。主担当の内訳: U-02=1, U-03=9, U-04=5, U-05=3, U-06=4, U-07=6、合計 28）
- [x] 13 件の不変条件（INV-01〜INV-13）を、検証責任を持つユニットに割り当てる（PBT-01 への引き渡し）
- [x] 4 件の誤用シナリオ（MU-01〜MU-04）を、統制を実装するユニットに割り当てる
- [x] `aidlc-docs/inception/application-design/unit-of-work-story-map.md` を作成する

### 5.4 検証

- [x] ユニット境界の妥当性を検証する（各ユニットが異なる NFR / テスト戦略 / 技術スタックを必要とすること）— U-02 は純粋関数の数学的性質、U-03 はトランザクション原子性、U-04 は MILP ソルバーとオラクル検証、U-06 はセキュリティテスト。いずれも異なる
- [x] ユニット間の依存に循環がないことを再検証する（注意を要する 2 依存 U-03→U-02、U-05→U-04 を個別に検証。逆向き依存なし）
- [x] 全ストーリーがユニットに割り当てられていることを再検証する（28/28）
- [x] 全コンポーネント（C-*, P-*, S-*, A-*, SEC-*, F-*）がいずれかのユニットに帰属することを検証する（35 コンポーネント、重複帰属なし）
- [x] 申し送り事項（H-1〜H-10）を、対応するユニットに割り当てる（unit-of-work-dependency.md セクション 7）

### 5.5 拡張ルールの適合確認

- [x] **SECURITY-11**: セキュリティモジュールの隔離が、ユニット境界としても表現されていることを確認する → **適合**。U-06 security が独立ユニット（Q3=A）
- [x] **PBT-05**: `A-03c BruteForceSolverAdapter`（オラクル）が最適化エンジンユニットに含まれることを確認する → **適合**。U-04 に帰属。INV-12 の検証責任も U-04
- [x] **NFR-M05**: フロントエンドとバックエンドの境界が、ユニット境界と一致することを確認する → **適合**。U-08 frontend が独立ユニット（Q2=A）。リンタ規則 R-1 で機械的に強制する
- [x] レジリエンシー拡張は無効のため適合確認を行わない旨を記録する → **記録済み**
- [x] 本ステージに直接適用される SECURITY / PBT ルールがない場合、その旨を記録する → **記録済み**。Units Generation は成果物がユニット境界の定義であり、SECURITY / PBT のいずれのルールも直接の検証対象を持たない。ただし境界の引き方が SECURITY-11、PBT-05、NFR-M05 を構造的に支える

### 5.6 完了処理

- [x] `aidlc-docs/aidlc-state.md` の進捗を更新する（ユニット一覧と CONSTRUCTION フェーズのループ計画を含む）
- [x] 拡張ルール適合サマリを作成する
- [ ] 完了メッセージを提示し、ユーザーの明示的承認を待つ

### 5.7 生成中に発見した設計上の論点（Functional Design へ申し送る）

- [x] **MU-02（CSV 数式インジェクション）の統制がユニット境界をまたぐ問題を解決した**。`A-04 CsvAdapter`（U-03）が `SEC-05.sanitizeCsvCell()`（U-06）を必要とするが、依存マトリクスでは U-03 は U-06 に依存しない。**採用した解決策**: `serialize()` がサニタイズ関数を引数として受け取る（依存性注入）。呼び出し元の U-07 が U-06 の関数を注入する。これにより依存マトリクスは変更不要。**U-03 と U-06 の Functional Design に申し送る**
