# Infrastructure Design — U-02 `distance-cost`（スキップの判断）

**作成日**: 2026-07-09
**ステージ**: CONSTRUCTION - Infrastructure Design（ユニット 2 / 8）
**判断**: **スキップを提案する**

---

## 1. 判断の根拠

Infrastructure Design は**条件付き（CONDITIONAL）ステージ**である（CLAUDE.md）。CLAUDE.md は各ユニットのステージ開始時に、そのステージがユニットにとって価値を持つかを再評価し、価値がなければスキップを提案してよいと定めている。

**U-02 はインフラ表出を一切持たない。**

### 1.1 必須 7 カテゴリの適用性（すべて N/A）

| カテゴリ | 判定 | 根拠 |
|---------|:----:|------|
| Deployment Environment | **N/A** | U-02 は独立してデプロイされない。バックエンドプロセスにインポートされる純粋関数群 |
| Compute Infrastructure | **N/A** | 稼働するプロセスを持たない |
| Storage Infrastructure | **N/A** | 永続化を持たない。距離キャッシュは U-02 が**定義**するが、**永続化は U-03**（`P-03` の実装は `A-02 PersistenceAdapter`）。そのインフラは U-03 の Infrastructure Design が扱う |
| Messaging Infrastructure | **N/A** | キューもブローカも持たない |
| Networking Infrastructure | **N/A** | ネットワークに触れない（リンタ契約が構造的に保証） |
| Monitoring Infrastructure | **N/A** | ログを出力しない。例外を送出するのみ |
| Shared Infrastructure | **N/A** | **バックエンド全体の共有インフラは U-01 の Infrastructure Design スロットで作成済み**（`construction/shared-infrastructure.md`）。U-02 はそれに何も追加しない |

**7 カテゴリすべてが N/A である。**

### 1.2 U-02 の距離キャッシュのインフラは U-03 に属する

U-02 は `P-03 DistanceCachePort` を**定義**するが、その**実装と永続化**は U-03 が行う（依存性逆転の原則）。

したがって、距離キャッシュのインフラ（DB テーブル、暗号化ボリューム上の配置、無効化の運用）は、**U-03 の Infrastructure Design で扱う**。U-02 の Infrastructure Design で扱うものではない。

---

## 2. スキップした場合に失われるもの

**何も失われない。**

- U-02 に固有のデプロイ成果物はない
- U-02 に固有のインフラ設定はない
- 共有インフラは既に `shared-infrastructure.md` に記述済み
- 距離キャッシュのインフラは U-03 で扱われる

**スキップは、内容のないステージを走らせないための合理的な判断である。** これは INCEPTION フェーズで Reverse Engineering をスキップしたのと同種の判断である。

---

## 3. スキップした場合の記録

`aidlc-docs/aidlc-state.md` に、U-02 Infrastructure Design を SKIPPED と記録し、根拠（純粋関数、インフラ表出ゼロ、距離キャッシュのインフラは U-03 が所有）を残す。

---

## 4. ユーザーへの確認

**この判断を独断で確定しない。** ユーザーの決定を仰ぐ。

- **スキップに同意する** → U-02 Infrastructure Design を SKIPPED として記録し、U-02 Code Generation へ進む
- **ステージを実行する** → U-02 に対する Infrastructure Design の質問を作成する（ただし上記のとおり、扱う内容は乏しい）
