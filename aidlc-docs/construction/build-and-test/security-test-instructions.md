# Security Test Instructions

security/baseline 拡張は**全ルールがブロッキング**で有効。以下はその検証手順。多くは既存テストで自動化済み。

## 1. 認証・認可

| 観点 | ルール | 検証 |
|------|-------|------|
| 未認証アクセス遮断 | SEC-01 / US-01 | `test_examples.py::test_protected_route_without_a_session_is_401`、`test_properties.py::test_every_protected_route_is_401_without_a_session`（P-API02） |
| deny-by-default（付け忘れも 401） | DP-01 | `PUBLIC_ROUTES` 許可リスト方式。P-API02 が全保護ルートを走査 |
| オブジェクトレベル認可 | SEC-02 | 各ルートで `require_authorization` を明示呼び出し |
| アカウント存在の非開示 | BR-SEC04 | `test_properties.py::test_login_never_reveals_whether_an_account_exists` |
| パスワードハッシュ | U06-H1 | Argon2id（argon2-cffi）。`tests/security` |
| セッション失効（単一クロック） | U07-H15 | ミドルウェアが注入クロックで期限判定。`test_examples.py` の認証フロー |

## 2. ネットワーク境界

| 観点 | ルール | 検証 |
|------|-------|------|
| 送信元 IP 制限 | NFR-S10.2 / SEC-03 | `test_examples.py::test_disallowed_source_ip_is_rejected_before_anything_else`、P-API03（全ルート 403） |
| 信頼プロキシのみ XFF 尊重 | SECURITY-15 | `source_ip()`。未設定なら fail closed |
| 静的配信にも IP 制限 | U08-H7 | `test_static.py::test_ip_allowlist_still_applies_to_static_assets` |
| セキュリティヘッダ | SECURITY-04 | `test_examples.py`、P-API06（全応答にヘッダ） |

## 3. 入力検証・インジェクション

| 観点 | ルール | 検証 |
|------|-------|------|
| DTO 検証（422） | SECURITY-05 | `test_invalid_body_is_422_not_500` |
| 未知列挙値の拒否 | BR-DM03 | `test_unknown_enum_label_is_rejected_not_coerced` |
| SQL は Core パラメータ化 | SECURITY-05 | U-03 は SQLAlchemy Core（構造的に防止） |
| CSV 数式インジェクション無害化 | MU-02 / P-API07 | `test_exported_csv_is_sanitised`、`test_masters.py::test_facility_export_is_sanitised_like_staff` |
| エラーに内部情報を出さない | SECURITY-09 | `test_error_bodies_carry_no_internals`、P-API04 |
| PII を出さない（行エラー） | BR-DM14 | `test_csv_import_errors_are_reported_with_line_numbers_and_no_pii` |
| XSS 安全描画（フロント） | NFR-FE-SEC2 | ESLint `react/no-danger`、`dangerouslySetInnerHTML` 不使用 |

## 4. 監査

| 観点 | ルール | 検証 |
|------|-------|------|
| 監査ログ記録 | US-03 | `AuditService`。`tests/security` |
| 改竄防止（削除メソッドなし） | US-04 | 追記専用ファイル + `chattr +a`（shared-infrastructure.md §3） |
| 監査ログに PII を持たない | — | `AuditEvent` は ID のみ。`tests/security` |

## 5. 依存の脆弱性・SBOM

```bash
# SECURITY-10（パッケージング）: ロックファイル + 監査 + SBOM
pip install pip-audit cyclonedx-bom   # 未導入なら
pip-audit                              # 既知脆弱性スキャン
cyclonedx-py environment -o sbom.json  # SBOM 生成

# フロント
cd src/frontend
npm audit                              # 依存脆弱性
```

- **本 PoC 環境の状態**: `pip-audit`/`cyclonedx` は未導入（任意）。実運用移行時に CI へ組み込む申し送り（SECURITY-10）。`npm audit` は導入済み依存に対して実行可能。

## 6. ペネトレーション／動的スキャン（任意）

- PoC ではスコープ外。実運用前に OWASP ZAP 等での動的スキャンを推奨（公開基盤の WAF と併用）。

## コンプライアンスまとめ

security/baseline の適用可能ルールはすべて**自動テストまたは構造で担保**。SECURITY-12（MFA）は本アプリに管理者ロールが無く、払い出しは OS レベル運用のため **N/A**（U06 で判断済み、待避ではない）。SECURITY-10 の pip-audit/SBOM は実運用 CI への申し送り。
