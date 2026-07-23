# U-08 frontend — ドメインエンティティ（ビューモデル）

**方針**: フロントエンドのビューモデルは U-07 の DTO を**写像**したもの。U-07 の DTO が唯一の契約であり、フロントはこれを再定義せず、REST 応答をそのまま受けて表示する（NFR-M05、BR-API02）。フロントに固有のドメインロジックは持たない（距離・費用・制約の解釈はすべてバックエンド）。

以下は U-07 の DTO（`src/api_orchestration/dto.py`）と、フロントでの用途の対応表。**フィールドはバックエンドの定義に一致させる（乖離させない）。**

---

## 1. セッション

### LoginRequest（送信）
| フィールド | 型 | 制約 | UI |
|-----------|----|----|----|
| `user_id` | string | 1–64 文字 | ログインフォーム |
| `password` | string | 1–256 文字 | ログインフォーム（マスク表示） |

ログイン成功は `204 No Content` + HttpOnly Cookie。フロントは応答ボディを持たない。

---

## 2. イベント

### EventRequest（送信）／ EventResponse（受信）
| フィールド | 型 | 備考 |
|-----------|----|----|
| `id` | string | 1–32 文字 |
| `type` | string | **日本語ラベル**（US-05）。バックエンドで `from_japanese` により列挙へ変換。未知ラベルは 400 |
| `name` | string | 1–100 文字 |
| `scheduled_date` | date | `YYYY-MM-DD` |
| `status` | string | Response のみ。日本語ラベル |

`type` の選択肢はバックエンドの列挙に対応する日本語ラベルを固定リストとして持つ（例: 災害避難所応援 等）。フロントは列挙値を再実装せず、ラベル文字列を送る。

---

## 3. マスタ取込結果

### ImportResultResponse（受信）
| フィールド | 型 | UI |
|-----------|----|----|
| `success_count` | int | 「N 件取り込みました」 |

取込エラー時は `200` ではなく `400` + `ErrorResponse.errors[]`（下記）。

---

## 4. 充足状況

### SufficiencyResponse（受信）
| フィールド | 型 | UI |
|-----------|----|----|
| `available` | int | 従事可 |
| `unavailable` | int | 従事不可 |
| `undeclared` | int | 未申告 |
| `required` | int | 必要数 |
| `shortage` | int | 不足数（> 0 で警告表示） |

---

## 5. 最適化

### OptimizationRequest（送信）
| フィールド | 型 | 既定 | 制約 |
|-----------|----|----|----|
| `event_id` | string | — | 1–32 文字 |
| `mode` | string | `FULL` | `FULL` \| `INCREMENTAL`（US-24） |
| `travel_time_weight` | float | 1.0 | ≥ 0 |
| `travel_cost_weight` | float | 1.0 | ≥ 0 |
| `inequity_weight` | float | 0.5 | ≥ 0 |
| `time_limit_seconds` | int | 300 | > 0 |
| `department_cap_limit` | int | 100 | > 0 |

### JobAcceptedResponse（受信、202）
| フィールド | 型 |
|-----------|----|
| `job_id` | string |
| `state` | string（QUEUED） |

### JobStatusResponse（受信、ポーリング）
| フィールド | 型 | UI |
|-----------|----|----|
| `job_id` | string | — |
| `state` | string | QUEUED / RUNNING / SUCCEEDED / INFEASIBLE / FAILED |
| `assignments` | `AssignmentResponse[]` \| null | SUCCEEDED 時のみ |
| `objective_value` | float \| null | 目的関数値 |
| `optimality_gap` | float \| null | 最適性ギャップ（US-20） |
| `solver_status` | string \| null | ソルバー状態 |
| `violations` | `ConstraintViolationResponse[]` \| null | 通常 null |
| `detail` | string \| null | INFEASIBLE の不足診断 / FAILED の要約（PII なし） |

---

## 6. 割当

### AssignmentResponse（受信）
| フィールド | 型 | UI |
|-----------|----|----|
| `staff_id` | string | 職員 ID |
| `facility_id` | string | 施設 ID |
| `is_pinned` | bool | ピン留め（手動確定）表示 |

> **注（U08-H2）**: 移動時間・費用のフィールドは**現状存在しない**。V-07 で移動負担を数値提示するには、この応答へ `travel_seconds` / `cost_yen` の追加が必要（機能設計の承認時に確認）。

### AssignmentPatchRequest（送信、手動修正）
| フィールド | 型 | 制約 |
|-----------|----|----|
| `staff_id` | string | 1–32 文字 |
| `facility_id` | string | 1–32 文字 |

`200` = 反映後の割当一覧、`400` = ハード制約違反（`violations` に制約 ID・詳細）。

---

## 7. エラー

### ErrorResponse（受信、共通エラーボディ）
| フィールド | 型 | UI |
|-----------|----|----|
| `message` | string | 主メッセージ（そのまま表示） |
| `violated_rule` | string \| null | 違反規則 |
| `errors` | `RowErrorResponse[]` \| null | CSV 取込の行別エラー（`line`, `message`、PII なし） |
| `violations` | `ConstraintViolationResponse[]` \| null | 手動修正のハード制約違反 |

### ConstraintViolationResponse
| フィールド | 型 |
|-----------|----|
| `constraint_id` | string（例: C1, C5） |
| `detail` | string |
| `facility_id` | string \| null |
| `staff_id` | string \| null |

---

## 8. ヘルス

### HealthResponse（受信）
| フィールド | 型 |
|-----------|----|
| `status` | string |
| `checked_at` | datetime |

（起動確認用。UI 上は明示画面を持たなくてよい。）
