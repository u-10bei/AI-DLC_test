# AI-DLC State Tracking

## Project Information
- **Project Type**: Greenfield
- **Start Date**: 2026-07-09T06:50:25Z
- **Current Stage**: OPERATIONS - per-persona + per-screen manuals authored (aidlc-docs/operations/)
- **Per-Unit Loop**: iteration 8 of 8 (U-01..U-07 COMPLETE)
- **Session note (2026-07-23T18:55:00Z)**: user approved U-08 Code Generation and paused. **ALL 8 UNITS COMPLETE (U-01..U-08).** Only Build and Test remains, then OPERATIONS (placeholder). Gates at pause: backend pytest 178 / mypy 106 clean / ruff clean / lint-imports 14 kept; frontend tsc clean / eslint clean / vitest 12 passed; H-5 non-vacuity proven. Carry-ins for Build and Test: build the frontend (npm run build in src/frontend so the U08-H4 dist mount serves it), set trusted_proxies for deploy; open items U08-H2/H3/H6, U05-H6, U06-H5, U07-H15.
- **Session note (2026-07-23T14:00:00Z)**: session RESUMED on 2026-07-23 (paused 2026-07-17 after U-07). U-08 Functional Design and NFR Requirements completed & approved this session. Doc dates: U-08 artifacts + audit entries from the resume onward are dated 2026-07-23 (initially mis-stamped 2026-07-17, corrected per user). U-01..U-07 dates (2026-07-17 and earlier) are unchanged — that work genuinely predates the resume.
- **Session note (2026-07-17T13:35:00Z)**: user paused here after approving U-07. **7 of 8 units done.** Remaining: U-08 frontend (5 stages), then Build and Test. All four CI gates green at pause: pytest 173 passed, mypy --strict clean (105 files), ruff clean, lint-imports 14 contracts kept. **Open items to carry into U-08 / Build and Test**: (a) U05-H6 - the historical_assignments / historical_declarations tables are still deferred; they are the ONLY thing blocking `GET /events/{id}/comparison`, whose DTO and converter already exist, so U-08's comparison screen has no backend endpoint until this lands; (b) U06-H5 - production account provisioning is an OS-level operational task; (c) deployment MUST set `AppConfig.trusted_proxies` behind the exposure platform, or the IP allowlist denies everything (fail closed).
- **Session note (2026-07-16T17:00:00Z)**: user paused here after approving U-05. 5 of 8 units done. Remaining: U-06 security, U-07 api-orchestration, U-08 frontend, then Build and Test. All four CI gates green at pause: pytest 119 passed, mypy strict clean (65 files), ruff clean, lint-imports 10 contracts kept.

## Code Naming Convention (established at U-01 Code Generation)
Documentation names units with hyphens (`shared-kernel`); **Python module names cannot contain hyphens**.
Code therefore uses underscores: `src/shared_kernel/`, `src/distance_cost/`, and so on. Applies to U-02..U-08 (handoff U01-H27).

## Shared Infrastructure (authored at U-01's Infrastructure Design slot — binds U-01..U-07)
See `aidlc-docs/construction/shared-infrastructure.md`. U-02..U-07 reference it; they do not re-derive infrastructure.
- Deployment: single internet-side server (A-07). Existing exposure platform provides TLS termination, access logging, and WAF (H-6 discharged; SECURITY-02 compliant)
- Compute: API process (FastAPI+uvicorn) + single job worker process (300s optimization must not block HTTP)
- Storage: `app.db` (SQLite) and `audit/*.jsonl` on an ENCRYPTED VOLUME (SECURITY-01; U01-H17 discharged)
- Audit log: append-only file with `chattr +a`; privileged cron rotates daily, deletes >90d, re-applies the attribute (SECURITY-14; U01-H16 discharged)
- Messaging: DB-backed job queue, no Redis. SQLite MANDATORY pragmas: WAL, busy_timeout>=5000, foreign_keys=ON
- Networking: SECURITY-07 documented exception; compensating controls NFR-S10.1 (login restriction) + NFR-S10.2 (municipal egress IP allowlist) — **QG-3 satisfied**
- Least privilege: OS filesystem permissions. App account can append to audit but not delete; cron account manages audit but cannot touch business data

## Tech Stack (decided at U-01 NFR Requirements — binds U-01..U-07)
- **Language**: Python (chosen because MILP solver availability for NFR-P02's 400k binary variables eliminates TypeScript and Go; Hypothesis beats jqwik on PBT quality)
- **Web framework**: FastAPI (+ Pydantic for SECURITY-05 input validation)
- **Database**: SQLite for the PoC, PostgreSQL for production. SQLAlchemy + Alembic so migration is a connection-string change (U01-H18)
- **PBT framework**: Hypothesis (PBT-09 satisfied — blocking rule discharged). Frontend PBT framework deferred to U-08 (U01-H20)
- **Async jobs**: DB-backed job queue. SQLite requires WAL + busy_timeout>=5000 + foreign_keys=ON as MANDATORY settings (U01-H15)
- **Error handling**: exceptions (DomainError hierarchy), global handler returns generic errors (U01-H14 resolved)
- **Audit log**: OS-level append-only file (JSON Lines + `chattr +a`) — this is how SECURITY-14 is satisfied without DB roles, which SQLite lacks (U01-H16)
- **Encryption at rest**: filesystem/disk level (U01-H17)
- **Packaging**: uv/Poetry lockfile + pip-audit + cyclonedx-py SBOM (SECURITY-10)
- **Quality gates**: mypy strict + ruff, lint rules R-1..R-6 enforced in CI
- **Still undecided**: MILP solver product (U-04, H-3), session store & password hashing (U-06), frontend stack (U-08)
- **Domain**: 居住地考慮型 従事者割当最適化システム（災害時避難所応援）

## Execution Plan Summary
- **Total Stages**: 14 (including placeholders)
- **Stages Completed**: Workspace Detection, Requirements Analysis, User Stories
- **Stages to Execute**: Workflow Planning, Application Design, Units Generation, Functional Design (per unit), NFR Requirements (per unit), NFR Design (per unit), Infrastructure Design (per unit), Code Generation (per unit), Build and Test
- **Stages to Skip**: Reverse Engineering (greenfield - no existing code to analyze)
- **Placeholder**: Operations
- **Risk Level**: Medium (rollback easy - greenfield; testing complexity high - optimization correctness)
- **Estimated Units**: ~5 (confirmed at Units Generation)

## Workspace State
- **Existing Code**: No
- **Reverse Engineering Needed**: No
- **Workspace Root**: /home/llm-user/AI-DLC_test
- **Rule Details Directory**: `.aidlc-rule-details/`

## Code Location Rules
- **Application Code**: Workspace root (NEVER in aidlc-docs/)
- **Documentation**: aidlc-docs/ only
- **Structure patterns**: See code-generation.md Critical Rules

## Extension Configuration

| Extension | Enabled | Enforcement Mode | Decided At |
|-----------|---------|------------------|------------|
| security/baseline | Yes | Full (all rules blocking) | Requirements Analysis |
| resiliency/baseline | No | N/A - deferred to next phase per Clarification Q4=A | Requirements Analysis |
| testing/property-based | Yes | Full (all rules blocking) | Requirements Analysis |

**Rule files loaded**: `extensions/security/baseline/security-baseline.md`, `extensions/testing/property-based/property-based-testing.md`
**Rule files NOT loaded** (opted out): `extensions/resiliency/baseline/resiliency-baseline.md`

## Stage Progress

### INCEPTION PHASE
- [x] Workspace Detection - COMPLETED (2026-07-09T06:50:25Z) - Greenfield
- [ ] Reverse Engineering - SKIPPED (Greenfield project)
- [x] Requirements Analysis - COMPLETED & APPROVED (2026-07-09T07:40:00Z) - Comprehensive depth
  - **requirements.md is now at v1.3** - revised during User Stories planning to correct a data-model error (従事可否 moved from staff master to an independent (staff, event) entity). See audit.md 2026-07-09T08:22:00Z.
  - [x] Step 2: Intent analysis (Clear / New Project / Multiple Components / Complex)
  - [x] Step 3: Depth determined = Comprehensive
  - [x] Step 5: Completeness analysis
  - [x] Step 5.1: Extension opt-in recorded, enabled rule files loaded
  - [x] Step 6: requirement-verification-questions.md (17 Q) + requirement-clarification-questions.md (8 Q) - all answered, contradictions resolved
  - [x] Step 7: requirements.md generated
  - [x] Step 8: State tracking updated
  - [x] Step 9: User approval - APPROVED 2026-07-09T07:40:00Z
- [x] User Stories - COMPLETED & APPROVED (2026-07-09T09:00:00Z)
  - [x] Step 1: Validate user stories need (assessment documented)
  - [x] Step 2-7: Create story plan with embedded questions (10 questions)
  - [x] Step 8-10: Collect and analyze answers - 3 clarification rounds (7 + 7 questions) - ALL AMBIGUITIES RESOLVED
  - [x] Step 11-14: Plan approval - APPROVED 2026-07-09T08:35:00Z
  - [x] Step 15-18: PART 2 - Generated personas.md (3 personas) and stories.md (28 stories / 8 epics / 13 invariants / 4 misuse cases)
  - [x] Step 19-23: Stories approval - APPROVED 2026-07-09T09:00:00Z
- [x] Workflow Planning - COMPLETED & APPROVED (2026-07-09T09:20:00Z) - execution-plan.md
- [x] Application Design - COMPLETED & APPROVED (2026-07-09T10:12:00Z)
  - Architecture: Hexagonal (ports & adapters). Domain C-01..C-05 (4 of 5 are pure functions), Ports P-01..P-07, Services S-01..S-08, Adapters A-01..A-07, Security modules SEC-01..SEC-05, Frontend F-01
  - Artifacts: components.md, component-methods.md, services.md, component-dependency.md, application-design.md
  - Extension compliance: SECURITY 10 compliant / 5 N/A, zero blocking findings. PBT N/A at this stage (PBT-01 due at Functional Design)
  - New handoffs raised: H-9 (C3-only infeasibility detection may require solving a relaxed subproblem), H-10 (big-M lower bound must satisfy INV-12)
- [x] Units Generation - COMPLETED & APPROVED (2026-07-09T10:55:00Z)
  - Part 1 (Planning) approved 2026-07-09T10:40:00Z; Part 2 (Generation) complete

**INCEPTION PHASE COMPLETE** (2026-07-09T10:55:00Z)
  - Artifacts: unit-of-work.md, unit-of-work-dependency.md, unit-of-work-story-map.md
  - Deployment model: monolith with logical modules. Code layout `src/{unit-name}/`, `tests/{unit-name}/`
  - 8 units defined, acyclic dependency graph, all 28 stories and all 35 components assigned

## Units of Work

| # | Unit | Directory | Depends on | Primary stories |
|---|------|-----------|------------|-----------------|
| U-01 | shared-kernel | `src/shared-kernel/` | (none - root) | 0 (foundation) |
| U-02 | distance-cost | `src/distance-cost/` | U-01 | US-15 |
| U-03 | data-management | `src/data-management/` | U-01, U-02 | US-05..US-13 |
| U-04 | optimization-engine | `src/optimization-engine/` | U-01, U-02, U-03 | US-16..US-20 |
| U-05 | comparison-report | `src/comparison-report/` | U-01, U-03, U-04 | US-26..US-28 |
| U-06 | security | `src/security/` | U-01 | US-01..US-04 |
| U-07 | api-orchestration | `src/api-orchestration/` | U-01..U-06 | US-14, US-21..US-25 |
| U-08 | frontend | `src/frontend/` | U-07 (REST contract only) | 0 (UI for all) |

**Tech stack coordination**: monolith backend shares one runtime. U-01's NFR Requirements decides the backend language/framework/DB and the PBT framework (PBT-09) for all backend units. U-04's NFR Requirements decides the MILP solver (H-3). U-06's decides session store and hashing. U-08's decides the frontend stack.

### CONSTRUCTION PHASE (per-unit loop x 8, in dependency order)
- [x] **U-01 shared-kernel — COMPLETE & APPROVED (2026-07-09T15:20:00Z), all 5 stages**
  - [x] Functional Design - COMPLETED (2026-07-09T11:30:00Z) - AWAITING USER APPROVAL
    - Artifacts: domain-entities.md, business-rules.md, business-logic-model.md (no frontend-components.md - U-01 has no UI)
    - PBT-01 satisfied: 8 testable properties P-01..P-08 with categories; 8 domain generators specified for PBT-07
    - Extension compliance: SECURITY 4 compliant / 11 N/A; PBT-01, PBT-03, PBT-04, PBT-07 compliant, rest N/A. Zero blocking findings
    - New handoffs: U01-H1..U01-H14
  - [x] NFR Requirements - COMPLETED & APPROVED (2026-07-09T12:45:00Z)
    - Artifacts: nfr-requirements.md, tech-stack-decisions.md
    - PBT-09 (blocking) satisfied: Hypothesis selected, documented, added to dependencies
    - SECURITY-14 blocking finding AVOIDED: SQLite has no roles, so the control moved to an OS-level append-only file
    - Extension compliance: SECURITY 6 compliant / 9 N/A; PBT-09 compliant. Zero blocking findings
    - New handoffs: U01-H15..U01-H20
  - [x] NFR Design - COMPLETED & APPROVED (2026-07-09T13:35:00Z)
    - Artifacts: nfr-design-patterns.md, logical-components.md
    - 7 patterns: stdlib-only domain (Pydantic confined to U-07), all types frozen, English enum identifiers with boundary conversion, NewType identifiers, structured exception context, PII repr redaction + lint rule (defense in depth), random PBT seed with failure logging
    - Resilience / Scalability / Performance / infra Logical Components confirmed N/A by the user (Q7=A)
    - Extension compliance: SECURITY 5 compliant / 10 N/A; PBT-07, PBT-08, PBT-10 compliant. Zero blocking findings
    - New handoffs: U01-H21..U01-H26
  - [x] Infrastructure Design - COMPLETED (2026-07-09T14:05:00Z) - AWAITING USER APPROVAL
    - Assessment: 6 of 7 mandated categories are N/A for U-01 itself (confirmed by user, Q2=A). U-01 has no infrastructure surface.
    - The 7th category (Shared Infrastructure) was the live issue. Q1=A: authored shared-infrastructure.md here, because U-03 (the first unit touching real infrastructure) cannot be designed until encryption-volume policy and audit-file placement are settled, and U-01/U-02 have no infrastructure.
    - Artifacts: shared-kernel/infrastructure-design/infrastructure-design.md (N/A record), deployment-architecture.md (U-01 is not independently deployed), and **construction/shared-infrastructure.md** (backend-wide)
    - Handoffs discharged: H-6, U01-H16, U01-H17. Quality gate QG-3 satisfied.
    - Extension compliance: SECURITY-01, 02, 06, 07, 11, 14 compliant; rest N/A. Zero blocking findings
    - New handoffs: SI-H1..SI-H4
  - [x] Code Generation - COMPLETED & APPROVED (2026-07-09T15:20:00Z)
    - Part 1 (Planning) approved 2026-07-09T14:30:00Z; Part 2 (Generation) complete, all 18 steps [x]
    - Application code: pyproject.toml, .importlinter, .gitignore, README.md, config/, src/shared_kernel/ (8 files), tests/ (5 files)
    - Documentation: aidlc-docs/construction/shared-kernel/code/implementation-summary.md
    - **All four CI gates pass**: pytest 43 passed; mypy strict clean over 14 files; ruff clean; lint-imports 2 contracts kept
    - Import contracts verified NON-VACUOUS: injecting `import pydantic` breaks the contract (exit 1); removing it restores it
    - Extension compliance: PBT 8 compliant / 2 N/A; SECURITY 6 compliant / 9 N/A. Zero blocking findings
    - Two deviations from the plan recorded: hyphen->underscore directory name; exceptions.py implemented before enums.py (plan had a forward-dependency error)
    - New handoffs: U01-H27..U01-H30
- [ ] U-02 distance-cost
  - [x] Functional Design - COMPLETED & APPROVED (2026-07-09T16:05:00Z)
    - Artifacts: domain-entities.md, business-logic-model.md, business-rules.md
    - **Handoff H-1 RESOLVED**: cost model changed from linear to distance-band (Q1=A). requirements.md revised to **v1.4** (FR-03.5 rewritten, FR-03.7 added, A-04 replaced, NFR-M03 updated)
    - PBT-01 satisfied: 12 testable properties (INV-07a/07b, INV-08a/b/c, INV-09, P-D01..P-D06) with categories
    - **Requires modifying U-01's APPROVED code** at U-02 Code Generation (U02-H8): remove TravelParameters.unit_price_per_km; add CostRule/CostBand/CostModel to value_objects.py; add InvalidCostModelError/UnknownSchoolDistrictError to exceptions.py. In-place edits, no duplicate files
    - New handoffs: U02-H1..U02-H9
  - [x] NFR Requirements - COMPLETED & APPROVED (2026-07-09T16:45:00Z)
    - Inherits the backend-wide stack from U-01. U-02-specific decisions: no numpy (Q1=A), embed an oracle table not geopy (Q2=A), U-02 provides the precompute pure function / U-03 persists (Q3=A), INV-07b exact within one process (Q4=A)
    - **U-02 keeps ZERO production dependencies** (math only), enforced by a new lint contract at Code Generation
    - Corrected U-01's approved tech-stack-decisions.md: struck the numpy entry (unnecessary per this unit's analysis)
    - Artifacts: nfr-requirements.md, tech-stack-decisions.md. Zero blocking findings
    - New handoff: U02-H10 (U-03 calls compute_district_distance_matrix and persists)
  - [x] NFR Design - COMPLETED (2026-07-09T17:02:00Z) - AWAITING USER APPROVAL
    - Patterns: linear scan over cost bands (Q1=A), purity enforced by TWO lint contracts - R-3 + standard-library-only (Q2=A), fail closed
    - Resilience/Scalability/Performance-infra/Logical-Components confirmed N/A (Q3=A)
    - Artifacts: nfr-design-patterns.md, logical-components.md. Zero blocking findings. No new handoffs
  - [x] NFR Design - COMPLETED & APPROVED (2026-07-09T17:10:00Z)
  - [x] Infrastructure Design - **SKIPPED & user-approved (2026-07-09T17:20:00Z)**. U-02 is pure functions, zero infrastructure surface; distance cache is persisted by U-03; shared infra authored at U-01. See distance-cost-infrastructure-design-skip.md
  - [x] Code Generation - COMPLETED (2026-07-16T11:00:00Z) - AWAITING USER APPROVAL
    - Modified U-01's approved files IN PLACE (value_objects.py, exceptions.py, __init__.py, generators.py) to add the distance-band cost model. No duplicate files
    - Created src/distance_cost/ (5 files) + tests/distance_cost/ (3 files). **U-02 production deps: zero (math only)**
    - **All four gates pass**: 74 tests (43 U-01 + 31 U-02), mypy strict clean over 23 files, ruff clean, lint-imports 4 contracts. Import contracts verified non-vacuous (inject numpy -> BROKEN)
    - **Property tests caught TWO real defects**: gen_cost_model produced a model its own validator rejected (float rounding); CostModel._validate_monotonic used a strict `>` with no tolerance, a real production risk for continuous-at-boundary cost tables. Both fixed (added _MONOTONIC_TOLERANCE_YEN, gave the generator a margin)
    - User's near-distance precision question addressed: Haversine relative error is constant with distance (~0.18%), no near-distance problem; the earlier "near pairs have larger error" claim was wrong and the Tokyo-Yokohama discrepancy was a bad oracle reference value, now Tokyo-Sendai
    - U-01's 43 existing tests pass unchanged after the TravelParameters signature change (no regression)
- [x] **U-02 distance-cost — COMPLETE & APPROVED (2026-07-16T11:15:00Z), all stages (Infra Design SKIPPED)**
- [ ] U-03 data-management
  - [x] Functional Design - COMPLETED & APPROVED (2026-07-16T12:20:00Z)
    - Artifacts: domain-entities.md (10 tables + schema), business-logic-model.md, business-rules.md (BR-DM01..14)
    - Decisions: SQLAlchemy Core + hand-written mappers (frozen types, fail-closed on DB load), single append-only availability table, DB UNIQUE(staff,event,declared_at), all-errors-with-line-numbers CSV import, ON DELETE CASCADE, Alembic initialised here, full distance-cache recompute after school-district commit, staff-master as the sufficiency denominator
    - PBT-01 satisfied: 7 properties (INV-10a/b, P-DM01..05). **PBT-06 stateful testing assessed as REQUIRED** for the Event state machine (RuleBasedStateMachine) - U-03 is the first unit that owns state transitions
    - First unit that STORES PII (staff name, residence district): SECURITY-01 via encrypted volume, SECURITY-03 via BR-DM14 (IDs and line numbers only in errors)
    - Twelve inbound handoffs resolved; new handoffs U03-H1..H6
  - [x] NFR Requirements - COMPLETED (2026-07-16T12:45:00Z) - AWAITING USER APPROVAL
    - Artifacts: nfr-requirements.md, tech-stack-decisions.md
    - Inherits the backend-wide stack from U-01. U-03-specific decisions (all Q=A): stdlib `csv` (no pandas), `executemany` bulk INSERT for NFR-P04, correlated `MAX(declared_at)` subquery (SQLite/PostgreSQL portable), PRAGMAs via SQLAlchemy `connect` event, in-memory SQLite per test (no mocks)
    - **First unit to add PRODUCTION dependencies: `sqlalchemy`, `alembic` (version-pinned, SECURITY-10)**. U-01/U-02 were dependency-free
    - U-03 lint contract: allows `sqlalchemy`/`alembic`, forbids `pydantic`/`fastapi` (those belong to U-07's API boundary)
    - Extension compliance: SECURITY-01/03/05/10/13/15 compliant, rest N/A; PBT-09 compliant. Zero blocking findings
    - Scalability / Availability confirmed N/A (single server A-07, resiliency disabled)
    - New handoffs: U03-H7 (add+pin sqlalchemy/alembic in pyproject.toml), U03-H8 (real in-memory SQLite tests with PRAGMAs, no mock repos)
  - [x] NFR Design - COMPLETED & APPROVED (2026-07-16T13:05:00Z)
    - Artifacts: nfr-design-patterns.md (7 patterns DP-01..07), logical-components.md (5 components LC-01..05)
    - All answers option A: DP-01 service-owned transaction boundary (fail-closed atomicity, BR-DM01; U-07 does not manage transactions), DP-02 fail-closed DB-load re-validation raising DataIntegrityError with ID-only context (SECURITY-15+03), DP-03 CSV two-phase single-pass load+validate-all+executemany (NFR-P04/BR-DM02), DP-04 distance-cache full recompute in the SAME transaction as the school-district master update (strongest consistency, no stale-cache window), DP-05 persistence-layer PII non-exposure (echo=False all environments, ID-only logs, SECURITY-03), DP-06 hand-written mapper re-running __post_init__, DP-07 parameterised queries structural via Core (SECURITY-05)
    - Logical components: LC-01 Engine/SessionFactory, LC-02 Repository (P-* ports), LC-03 Mapper, LC-04 CsvImportService (owns transaction), LC-05 MigrationRunner (Alembic). NO message queue / external cache / circuit breaker (Q6=A)
    - Resilience / Scalability / extra logical components confirmed N/A (Q6=A): fail closed instead of retries, single server A-07, DB-backed job queue owned by U-07, distance cache is a DB table
    - Extension compliance: SECURITY-01/03/05/15 compliant, rest N/A; PBT patterns verifiable via P-DM01..05 / INV-10a/b / PBT-06. Zero blocking findings
    - New handoffs: U03-H9 (add DataIntegrityError to exceptions.py, ID-only context, no PII), U03-H10 (same-transaction cache recompute is a PoC choice; revisit separate-transaction + repair path if row counts grow in production)
  - [x] Infrastructure Design - **SKIPPED & user-approved (2026-07-16T13:12:00Z)**. All 7 categories settled at U-01 or N/A; U-03 adds no new infrastructure service. First unit to store PII, but encryption-at-rest (encrypted volume, SECURITY-01, U01-H17) was authored in shared-infrastructure.md at U-01 - U-03 only places app.db there. See data-management-infrastructure-design-skip.md
  - [x] Code Generation - COMPLETED (2026-07-16T13:55:00Z) - AWAITING USER APPROVAL
    - Part 1 (Planning) approved 2026-07-16T13:25:00Z; Part 2 (Generation) complete, all 16 steps [x]
    - Application code: src/data_management/ (8 files: __init__, schema, engine, mappers, repositories, csv_codec, services, migrations) + alembic/ (env.py, script.py.mako, versions/0001_initial_schema.py) + alembic.ini
    - **First unit with PRODUCTION dependencies: sqlalchemy==2.0.36, alembic==1.14.0 (pinned, SECURITY-10)**. wheel packages updated to include distance_cost + data_management
    - Modified U-01's approved files IN PLACE: shared_kernel/exceptions.py (+DataIntegrityError, PII-free, U03-H9), shared_kernel/__init__.py (export). pyproject.toml, .importlinter
    - Tests: tests/data_management/ (support, generators, test_examples 13 cases, test_properties INV-10a/b + P-DM01..05, test_stateful RuleBasedStateMachine for the Event state machine PBT-06)
    - **All four gates pass**: pytest 96 passed (43 U-01 + 31 U-02 + 22 U-03, no regression), mypy strict clean over 37 files, ruff clean, lint-imports 6 contracts kept. New contracts verified NON-VACUOUS (inject `import fastapi` into data_management -> allowlist BROKEN; remove -> restored)
    - Patterns implemented: DP-01 service-owned transactions, DP-02 fail-closed DataIntegrityError on corrupt-row load, DP-03 two-phase CSV import, DP-04 same-transaction distance-cache recompute, DP-05 echo=False + ID-only errors, DP-06 hand-written mappers, DP-07 parameterised Core queries
    - Deviations recorded: Alembic + test helper share schema.metadata as single source (metadata.create_all rather than booting Alembic per test); create_db_engine uses StaticPool for in-memory sqlite (no test-only code in persistence layer); sufficiency denominator is the whole facility master (no event-facility link in schema)
    - New handoffs discharged: U03-H9 (DataIntegrityError added). Carried: U03-H1..H5, H10
- [x] **U-03 data-management — COMPLETE & APPROVED (2026-07-16T14:05:00Z), all stages (Infra Design SKIPPED)**
- [ ] U-04 optimization-engine: (same 5 stages)
  - [x] Functional Design - COMPLETED & APPROVED (2026-07-16T14:30:00Z)
    - Artifacts: business-logic-model.md, business-rules.md, domain-entities.md
    - All answers option A. MILP formulation, solver-product-agnostic (H-3 deferred to NFR Requirements)
    - Q1 C1 exact equality; Q2 objective normalisation (constants externalised NFR-M03); Q3 inequity=minimax T_max (U01-H5); Q4 infeasibility decision tree resolving H-9 (relax-C3 solve isolates a C3-only cause); Q5 big-M = U_obj+1 resolving H-10/guaranteeing INV-12; Q6 history-levelling weight-0 hook (no U-05 dependency); Q7 pinned re-opt with pre-solve validation + time-limit best-solution/gap
    - New types: MilpModel, SolveOutcome, InfeasibilityDiagnosis (cause + facilities/constraints, no PII), SolverPort (abstract), ServiceHistory hook. New exceptions PinnedAssignmentInfeasibleError, ModelConstructionError
    - PBT-01: P-OPT01..12 (incl. P-OPT12/INV-12 metamorphic, P-OPT10 oracle). PBT-06 assessed OPTIONAL (each solve is pure). SECURITY-03/05/15 compliant. Zero blocking findings
    - Handoffs resolved: H-9, H-10, U01-H5, H-2. New: U04-H1 (solver product, NFR Requirements/H-3), U04-H2 (normalisation constants), U04-H3 (history wiring, future), U04-H4 (persist result via U-03 skeletons), U04-H5 (objective breakdown), U04-H6 (solver adapter), U04-H7 (new exceptions)
  - [x] NFR Requirements - COMPLETED & APPROVED (2026-07-16T14:48:00Z)
    - Artifacts: nfr-requirements.md, tech-stack-decisions.md
    - **H-3 RESOLVED: OR-Tools CP-SAT** (Apache-2.0, open source, on-prem, no licence; native time-limit/best-solution/optimality-gap matching FR-04.6 and the SolverPort abstraction)
    - All answers A: Q1 CP-SAT, Q2 exact+time-limit degrading to best-feasible+gap (no separate heuristic), Q3 no variable pruning (correctness first), Q4 reproducibility for OPTIMAL/run-to-completion only (timeout best-solution not guaranteed), Q5 solve runs in the U-01 job worker, Q6 pin ortools + pip-audit/SBOM/offline + lint contract
    - U-04 lint contract: may import shared_kernel/distance_cost/data_management + ortools; forbids security/comparison_report/api_orchestration/frontend and pydantic/fastapi
    - NFR-P02 (400k vars in 300s) validated in Build & Test with representative data
    - Extension compliance: SECURITY-10 (ortools pinned/audited/SBOM), SECURITY-03 (carried), PBT-09 compliant. Scalability/Availability N/A. Zero blocking findings
    - New handoffs: U04-H8 (add+pin ortools, pip-audit/SBOM, verify offline)
  - [x] NFR Design - COMPLETED & APPROVED (2026-07-16T15:02:00Z)
    - Artifacts: nfr-design-patterns.md (DP-01..06), logical-components.md (LC-01..05)
    - All answers A: DP-01 CP-SAT native constraint helpers (AddAtMostOne, linear sums, NewBoolVar), DP-02 integer scaling of the normalised float objective with integer big-M (M_int = S*U_obj+1, S large enough that INV-12 survives rounding - the key pattern; CP-SAT is an integer solver), DP-03 ortools confined to a single CpSatAdapter (SolverPort; core stays product-agnostic), DP-04 per-solve time budgets with documented 3x worst case, DP-05 fail closed (BR-07 + diagnosis-as-return-value), DP-06 reproducibility (fixed seed+workers) + solver-log suppression + ID-only variable names (SECURITY-03)
    - Logical components: LC-01 ModelBuilder (pure), LC-02 SolverPort+CpSatAdapter (ortools confined), LC-03 InfeasibilityDiagnoser, LC-04 ResultMapper (BR-07), LC-05 OptimizationService. No queue/cache/circuit-breaker (Q5=A)
    - Extension compliance: SECURITY-03/10/15 compliant; PBT verifiable via P-OPT01..12. Scalability/Availability N/A. Zero blocking findings
    - New handoffs: U04-H9 (externalise scale factor S, normalisation constants, time budgets, worker count)
  - [x] Infrastructure Design - **SKIPPED & user-approved (2026-07-16T15:08:00Z)**. All 7 categories settled at U-01/U-03 or N/A; U-04 is pure solving logic, compute runs in U-01's job worker, result persistence reuses U-03 skeletons, ortools is an app dependency, U-04 is offline (FR-03.6). See optimization-engine-infrastructure-design-skip.md
  - [x] Code Generation - COMPLETED (2026-07-16T15:40:00Z) - AWAITING USER APPROVAL
    - Part 1 (Planning) approved 2026-07-16T15:15:00Z; Part 2 (Generation) complete, all 15 steps [x]
    - Application code: src/optimization_engine/ (11 files: __init__, scaling, model, builder, solver_port, cp_sat_adapter, diagnoser, result_mapper, service, exceptions, repository)
    - **Production dependency ortools==9.11.4210 (CP-SAT, pinned, SECURITY-10)**; verified installable + solves. In-place: pyproject.toml (dep, wheel packages, mypy override confining ortools's untyped API to cp_sat_adapter), .importlinter (R-5 + solver allowlist)
    - Tests: tests/optimization_engine/ (support, test_examples 9, test_properties P-OPT01..12 incl. INV-12 metamorphic + brute-force oracle, test_persistence U04-H4)
    - **All four gates pass**: pytest 110 passed (43 U-01 + 31 U-02 + 22 U-03 + 14 U-04, no regression), mypy strict clean over 53 files, ruff clean, lint-imports 8 contracts kept. New contracts verified NON-VACUOUS (inject `import fastapi` into optimization_engine -> allowlist BROKEN)
    - Patterns: DP-01 CP-SAT native constraints, DP-02 integer scaling + integer big-M (INV-12 verified by property), DP-03 ortools confined to cp_sat_adapter, DP-04 staged solve, DP-05 fail closed (BR-07 + diagnosis-as-return-value + pin validation), DP-06 fixed seed/workers + log suppression + ID-only variable names
    - Handoffs discharged: U04-H1, H6, H7, H8. Carried: U04-H3 (history), U04-H5 (objective breakdown), U04-H9 (externalise S/constants)
    - Deviations: mypy strict relaxed only for cp_sat_adapter (ortools has no stubs); objective_value recomputed from assignments (BR-07-safe, penalty-free); C5 uses uniform department_cap_limit
- [x] **U-04 optimization-engine — COMPLETE & APPROVED (2026-07-16T15:45:00Z), all stages (Infra Design SKIPPED)**
- [ ] U-05 comparison-report: (same 5 stages)
  - [x] Functional Design - COMPLETED & APPROVED (2026-07-16T16:02:00Z)
    - Artifacts: business-logic-model.md, business-rules.md, domain-entities.md
    - All answers A. Baseline comparison (FR-05): replay a past event under identical conditions; the difference is attributed to the assignment rule alone
    - Components: ReplayBuilder (HistoricalRecord + current master -> AssignmentProblem, headcount from actuals, available=declared-available, current master values, travel matrix via U-02), BaselineEvaluator (same travel matrix), ComparisonService (optimise via U-04), ReportExporter (U-03 serialize_csv)
    - New types: ComparisonReport (aggregates + event ID + note, no PII), ManualBaseline (FR-05.1.6). Uses U-01's HistoricalRecord
    - **New dependency U-05 -> U-02 distance_cost (Q1=A, acyclic, U05-H1)** to build the travel matrix and evaluate metrics
    - Reduction may be negative (optimiser minimises the weighted objective, not either metric alone; SC-01 both-reduce is empirical). fail closed: infeasible replay surfaces U-04's InfeasibilityDiagnosis
    - PBT-01: P-CMP01..05 (metric consistency, feasible-baseline objective-dominance metamorphic, no PII). SECURITY-03/15 compliant. Zero blocking findings
    - New handoffs: U05-H1 (add distance_cost dep + lint contract), U05-H2 (historical_records ingestion via U-03), U05-H3 (metrics_for TravelMetrics assembly), U05-H4 (use U-04 normalised_objective for the dominance check), U05-H5 (define ComparisonReport/ManualBaseline)
  - [x] NFR Requirements - COMPLETED & APPROVED (2026-07-16T16:14:00Z)
    - Artifacts: nfr-requirements.md, tech-stack-decisions.md
    - All answers A. **Zero new production dependencies** (lightest unit; composes U-02/U-03/U-04 + pure aggregation; CSV via U-03 serialize_csv)
    - U-05 lint contract: may import shared_kernel/distance_cost/data_management/optimization_engine; forbids security/api_orchestration/frontend + pydantic/fastapi (U05-H1, acyclic)
    - fail-closed comparison (infeasible replay -> U-04 diagnosis), reproducibility inherited from U-04, PII non-exposure carried, no U-05-specific perf target (follows U-04 NFR-P02, runs in job worker)
    - Extension compliance: SECURITY-03/15, PBT-09 compliant; SECURITY-10 no added scope. Scalability/Availability N/A. Zero blocking findings
  - [x] NFR Design - COMPLETED & APPROVED (2026-07-16T16:26:00Z)
    - Artifacts: nfr-design-patterns.md (DP-01..05), logical-components.md (LC-01..05)
    - All answers A: DP-01 single shared metrics_for pure function (structural guarantee of FR-05.1.4 - baseline and optimised scored on identical metrics), DP-02 reuse U-02 + TravelParameters (same-district 0/0/fixed), DP-03 objective dominance via U-04 normalised_objective (U05-H4), DP-04 fail-closed diagnosis pass-through, DP-05 reduction with zero-guard + PII non-exposure
    - Logical components: LC-01 ReplayBuilder, LC-02 BaselineEvaluator, LC-03 ComparisonService, LC-04 ReportExporter (U-03 serialize_csv), LC-05 HistoricalRepository. No queue/cache/CB (Q4=A)
    - Extension compliance: SECURITY-03/15 compliant; PBT verifiable via P-CMP01..05. Scalability/Availability N/A. Zero blocking findings
  - [x] Infrastructure Design - **SKIPPED & user-approved (2026-07-16T16:32:00Z)**. All 7 categories settled at U-01/U-03/U-04 or N/A; U-05 has zero production deps and no infrastructure surface (composes existing units; solve in U-01 worker via U-04; persistence/CSV via U-03). See comparison-report-infrastructure-design-skip.md
  - [x] Code Generation - COMPLETED (2026-07-16T16:55:00Z) - AWAITING USER APPROVAL
    - Part 1 (Planning) approved 2026-07-16T16:40:00Z; Part 2 (Generation) complete, all 12 steps [x]
    - Application code: src/comparison_report/ (8 files: __init__, metrics, report, replay, evaluator, service, exporter, repository). **Zero new production dependency**
    - In-place: pyproject.toml (wheel packages only), .importlinter (R-6 + no-web-framework, adds distance_cost to U-05's allowed imports, U05-H1)
    - Tests: tests/comparison_report/ (support, test_examples 6, test_properties P-CMP01..05 incl. the objective-dominance metamorphic property)
    - **All four gates pass**: pytest 119 passed (110 U-01..U-04 + 9 U-05, no regression), mypy strict clean over 65 files, ruff clean, lint-imports 10 contracts kept. New contracts verified NON-VACUOUS (inject `import fastapi` -> BROKEN)
    - Value proposition demonstrated: a baseline that assigned a FAR staff member (11,198 s / 37,326 yen) optimises to a NEAR staff member (900 s / 0 yen) = 91.96% time / 100% cost reduction (SC-01)
    - Patterns: DP-01 single shared metrics_for, DP-02 reuse U-02 compute_travel_metrics, DP-03 objective via U-04 normalised_objective, DP-04 fail-closed diagnosis pass-through, DP-05 zero-guarded reduction + PII-free report
    - Handoffs discharged: U05-H1, H3, H4, H5. New: U05-H6 (historical_assignments/declarations tables for full-detail persistence, later migration)
    - Deviations: historical_records marker only (full-detail persistence deferred, U05-H6); reduction may be negative (BR-CMP08, tested)
- [x] **U-05 comparison-report — COMPLETE & APPROVED (2026-07-16T17:00:00Z), all stages (Infra Design SKIPPED)**
- [ ] U-06 security: (same 5 stages)
  - [x] Functional Design - COMPLETED & APPROVED (2026-07-17T09:30:00Z)
    - Artifacts: business-logic-model.md, business-rules.md (BR-SEC01..21 + full SECURITY-01..15 assessment), domain-entities.md
    - All answers A. U-06 is where the SECURITY extension is actually implemented
    - **Q1=A: coordinator role ONLY, no in-app admin role** -> SECURITY-12's MFA requirement is N/A (no admin accounts exist; provisioning is an OS-level operational task). Adaptive password hashing still applies. Recorded as U06-H5 for production
    - **Q2=A: SessionStorePort defined by U-06, DB implementation injected by U-07** -> U-06 keeps its U-01-only dependency; same DI pattern as MU-02/SEC-05 (U06-H2)
    - Q3 object-level authz gate always traversed (MU-01/IDOR, deny by default); Q4 audit = who/when/what/before-after + master changes + auth failures, JSON Lines UTC, **no PII and reason_category explicitly excluded (U01-H22)**; Q5 OS append-only file (chattr +a, MU-04); Q6 IP allowlist + in-memory rate limit + account lock, pipeline SEC-03->04->01->02->05; Q7 sanitize_csv_cell (MU-02), injection points already built in U-03/U-05
    - AuditEvent has NO fields that could hold PII - structural guarantee. U-06 does not import Staff/Event business types (only IDs)
    - PBT-01: P-SEC01..09. **PBT-06 stateful assessed REQUIRED** (session lifecycle + lock state machine)
    - SECURITY-01..15 all addressed; MU-01..MU-04 countermeasures mapped. Zero blocking findings
    - New handoffs: U06-H1 (hasher product + TTL/threshold/rate limits -> NFR Requirements), U06-H2/H3/H4 (U-07 injects SessionStore, sanitizer, middleware order), U06-H5 (no admin role; production needs admin+MFA), U06-H6 (chattr +a + rotation cron), U06-H7/H8 (define types/NewTypes)
  - [x] NFR Requirements - COMPLETED & APPROVED (2026-07-17T09:52:00Z)
    - Artifacts: nfr-requirements.md, tech-stack-decisions.md
    - **U06-H1 RESOLVED: Argon2id via argon2-cffi==23.1.0** (OWASP first recommendation, memory-hard, no bcrypt 72-byte truncation). Verified installable + hash/verify correct before committing
    - Operational defaults (all externalised, NFR-M03): session TTL 8h absolute, lock 5 failures/15 min, rate limit 60 req/min/IP general and 5 req/min/IP login, Argon2 params OWASP in prod / light in tests
    - Session IDs from secrets.token_urlsafe(32) (CSPRNG 256-bit); hmac.compare_digest for constant-time comparison; ipaddress for CIDR allowlists; all stdlib
    - **Production dependency: argon2-cffi ONLY** (everything else stdlib)
    - **Q5 lint contract FORBIDS sqlalchemy** -> U-06 physically cannot persist sessions, making the SessionStorePort injection design a structural guarantee rather than an intention (non-vacuity to be verified at Code Generation, U06-H10)
    - Tests use the REAL hasher (no mocks); PBT-06 stateful required for session/lock state machines
    - Extension compliance: SECURITY-12 (Argon2id; MFA N/A), SECURITY-06/08/03/14/10/11/15, PBT-06/09 compliant. Scalability/Availability N/A. Zero blocking findings
    - New handoffs: U06-H9 (pin argon2-cffi + pip-audit/SBOM), U06-H10 (add lint contract; verify `import sqlalchemy` -> BROKEN)
  - [x] NFR Design - COMPLETED & APPROVED (2026-07-17T10:12:00Z)
    - Artifacts: nfr-design-patterns.md (DP-01..07), logical-components.md (LC-01..07)
    - All answers A. Guiding idea: protect by structure, not discipline - forgetting a check must fail CLOSED
    - **DP-01 gates raise on denial** (a forgotten return-value check cannot let a request through); SEC-02 returns a decision for audit but require_authorization raises; un-injected ports and undecidable state also raise = deny
    - **DP-02 dummy Argon2 verify** when the account is absent/locked, closing the user-enumeration TIMING channel a generic message alone leaves open
    - DP-03 audit append per event + flush (durability over throughput; a lost audit record is what MU-04 wants); DP-04 fixed-window rate limiter with its boundary-burst property documented honestly; DP-05 secrets non-exposure (CSPRNG, constant-time, repr redaction); DP-06 sqlalchemy ban makes port injection structural; DP-07 AuditEvent has no PII-capable fields and U-06 never imports business entities
    - Logical components: LC-01 Authenticator, LC-02 Authorizer, LC-03 IpAllowlist (ipaddress/CIDR), LC-04 RateLimiter, LC-05 InputSanitizer, LC-06 AuditService, LC-07 AppendOnlyFileAuditLog. Config is a frozen SecurityConfig dataclass (not a Protocol - config is data)
    - Extension compliance: SECURITY-15/09/14/06/03/12/11 compliant; PBT verifiable via P-SEC01..09 + PBT-06. Scalability/Availability N/A. Zero blocking findings
    - New handoffs: U06-H11 (build DUMMY_HASH at init for timing uniformity), U06-H12 (fixed-window boundary burst; swap to sliding window if needed)
  - [x] Infrastructure Design - **SKIPPED & user-approved (2026-07-17T10:20:00Z)** - a VERIFIED skip, not an assumed one. U-06 plausibly had its own infra (the audit log's append-only storage), so shared-infrastructure.md was actually read: sections 3.3/7 already specify location, chattr +a, ext4/XFS, the privileged separate-account rotation cron with 90-day retention, and the least-privilege split (app may only append to current.jsonl, cannot chattr) - and that document already attributes the audit log to U-06. Nothing left for U-06 to design. IP allowlist is application logic, sessions are an injected port, argon2-cffi is an app dependency. See security-infrastructure-design-skip.md
  - [x] Code Generation - COMPLETED (2026-07-17T10:50:00Z) - AWAITING USER APPROVAL
    - Part 1 (Planning) approved 2026-07-17T10:28:00Z; Part 2 (Generation) complete, all 15 steps [x]
    - Application code: src/security/ (13 files: identifiers, exceptions, config, entities, ports, hasher, audit, audit_adapter, authentication, authorization, network, rate_limit, sanitizer, __init__)
    - Production dependency argon2-cffi==23.1.0 (pinned; ships py.typed so no mypy override needed, unlike ortools). In-place: pyproject.toml, .importlinter (R-7 + "security cannot persist anything")
    - Tests: tests/security/ (support with in-memory SessionStorePort + light Argon2, test_examples 21, test_properties P-SEC01..09 with the REAL hasher, test_stateful PBT-06 session/lock machine)
    - **All four gates pass**: pytest 150 passed (119 U-01..U-05 + 31 U-06, no regression), mypy strict clean over 84 files, ruff clean, lint-imports 12 contracts kept
    - **DESIGN ENFORCEMENT PROVEN**: injecting `import sqlalchemy` into security -> "security cannot persist anything (SessionStorePort must be injected)" BROKEN. The NFR Design Q2=A decision is structurally guaranteed, not merely intended - a future contributor cannot add a quick session query without failing the build. Together with U-01's R-2, PII cannot travel in either direction
    - Defences verified by test: locked account denied even with the correct password; empty/garbage IP allowlist denies everything; unknown vs wrong-password responses identical (+ dummy Argon2 verify closes the timing channel); audit JSON has no password and no PII-capable keys; sanitiser never emits a formula-leading cell; PBT-06 confirms authenticate succeeds iff the model says the session is valid
    - Deviations recorded: AccountLockedError NOT implemented (login always raises the generic error so U-07 cannot forget to round it - structure over discipline); _UNRESTRICTED_ROLES set replaces an is-check that mypy correctly flagged unreachable, keeping a real deny-by-default branch for future roles
    - Handoffs discharged: U06-H1/H7/H8/H9/H10/H11. Carried to U-07: U06-H2 (inject SessionStore), U06-H3 (inject sanitizer), U06-H4 (middleware order + generic responses). To ops: U06-H5 (no admin role; prod needs admin+MFA), U06-H6 (chattr +a, rotation cron), U06-H12 (window burst)
- [x] **U-06 security — COMPLETE & APPROVED (2026-07-17T10:55:00Z), all stages (Infra Design SKIPPED - verified)**
- [x] U-07 api-orchestration: **COMPLETE & APPROVED (2026-07-17T13:35:00Z)**
  - [x] Functional Design - COMPLETED & APPROVED (2026-07-17T11:16:00Z)
    - Artifacts: business-logic-model.md, business-rules.md (BR-API01..23), domain-entities.md
    - All answers A. U-07 is the composition root - the only unit that knows every other one. It has NO business logic of its own
    - Q1 Pydantic DTOs confined to U-07 with explicit conversions (fulfils U-01 pattern 1; domain types never serialised directly); Q2 single hand-wired composition root, no DI container; Q3 middleware SEC-03->04->01->02->05 + global handler mapping exceptions to generic responses (403/429/401/403, unexpected -> generic 500) + SECURITY-04 headers; Q4 DB-backed job queue returning 202 job_id with a worker running U-04, states QUEUED/RUNNING/SUCCEEDED/INFEASIBLE/FAILED (INFEASIBLE deliberately distinct from FAILED); Q5 FULL vs INCREMENTAL re-optimisation with the trade-off surfaced (US-24); Q7 HttpOnly+Secure+SameSite=Strict session cookie
    - **Q6=A: add a PUBLIC constraint-validation function to U-04 (in-place change to approved code)** so FR-06.3's immediate C1..C5 check reuses U-04's logic rather than duplicating the interpretation of the constraints in U-07 where it would drift. Same call as U-02 modifying U-01's approved code
    - Handoffs discharged by design: U06-H2 (SqlSessionStore implemented in U-07 and injected into U-06 - U-06 cannot import sqlalchemy), U06-H3 (sanitize_csv_cell injected into U-03/U-05 CSV export at the composition root), U06-H4 (middleware order), U01-H14 (global handler), H-5/NFR-M05 (explicit HTTP boundary)
    - PBT-01: P-API01..07 (DTO round-trip, unauthenticated/disallowed-IP always denied, no internals in errors, job state transitions, security headers, CSV export sanitised). **PBT-06 stateful REQUIRED for the job state machine**
    - SECURITY-04/05/08/09/15/03/11 compliant. Zero blocking findings
    - New handoffs: U07-H1 (public validation fn in U-04), U07-H2 (SqlSessionStore), U07-H3 (job queue on optimization_jobs), U07-H4 (worker + build_problem), U07-H5 (FastAPI/uvicorn/Pydantic deps), U07-H6 (U-08 calls the HTTP boundary; URL externalised), U07-H7/H8 (job types, DTOs + round-trip property)
  - [x] NFR Requirements - COMPLETED & APPROVED (2026-07-17T11:30:00Z)
    - Artifacts: nfr-requirements.md, tech-stack-decisions.md
    - **U07-H5 RESOLVED: fastapi==0.115.6, uvicorn==0.34.0, pydantic==2.10.4, httpx==0.28.1 (dev)** - verified BEFORE deciding: TestClient returns 200 for a valid body and **422 for an invalid one** (direct SECURITY-05 evidence). Matches the project's late-2024 pinning baseline
    - Q2 worker = CLI entry point `python -m api_orchestration.worker`, resident via systemd/supervisor (U-01's process split), polling interval externalised (default 2s), one job at a time. In-API background execution rejected (would occupy API resources for 300s)
    - Q3 no U-07-specific numeric target (heavy work already has NFR-P04/NFR-P02); Q5 test through the REAL HTTP boundary with TestClient, no mocks, worker stepped synchronously, PBT-06 for the job state machine; Q6 scalability/availability N/A
    - **Q4 lint contract: pydantic/fastapi permitted HERE ONLY** - the positive mirror of every other unit's contract forbidding them, i.e. proof the "Pydantic at the API boundary" decision held across all 6 units. sqlalchemy also permitted because U-06 is forbidden it and therefore U-07 must implement SqlSessionStore (U06-H2) - the contract決定 the design's placement
    - Environment note: pydantic 2.10.4 conflicts with unrelated packages in the shared env (litellm/mcp want >=2.11); not part of this project, same class as the ortools/protobuf downgrade
    - Extension compliance: SECURITY-04/05/08/09/10/15/03, PBT-06/09 compliant. Zero blocking findings
    - New handoffs: U07-H9 (pin deps + pip-audit/SBOM), U07-H10 (lint contract; verify `frontend` import -> BROKEN)
  - [x] NFR Design - COMPLETED & APPROVED (2026-07-17T11:48:00Z)
    - Artifacts: nfr-design-patterns.md (DP-01..07), logical-components.md (LC-01..09)
    - All answers A. Same guiding idea as U-06, applied at the HTTP layer: forgetting something must fail CLOSED
    - **DP-01 (core): authentication as MIDDLEWARE + explicit PUBLIC_ROUTES allowlist**, not FastAPI's per-route Depends idiom. A new route is protected by default; forgetting a check denies the request instead of silently publishing an endpoint. Publishing requires a reviewable allowlist edit
    - DP-02 middleware order + exception->generic response (unexpected -> 500); DP-03 job claim via conditional UPDATE + rowcount (costs nothing now, prevents a future double-run of a 300s solve); DP-04 worker split step()/run_forever() so tests need no process/thread; DP-05 DTO conversions as pure functions (round-trip property-testable, Pydantic never touches domain types); DP-06 composition root injection with P-API07 guarding against a forgotten sanitiser; DP-07 security headers + HttpOnly/Secure/SameSite cookie + PII only where the screen needs it
    - Logical components: LC-01 app, LC-02 routers, LC-03 dto, LC-04 converters, LC-05 composition, LC-06 job_queue, LC-07 session_store (lives in U-07 precisely BECAUSE U-06 is forbidden sqlalchemy - the contract determines the placement), LC-08 worker, LC-09 errors
    - Extension compliance: SECURITY-08/04/05/09/15/03 compliant; PBT via P-API01..07 + PBT-06. Scalability/Availability N/A. Zero blocking findings
    - New handoffs: U07-H11 (PUBLIC_ROUTES limited to login + health; additions need security review), U07-H12 (P-API07 guards the sanitiser injection)
  - [x] Infrastructure Design - **SKIPPED & user-approved (2026-07-17T11:58:00Z)** - a VERIFIED skip with TWO findings, both accepted. U-07 owns the API process and touches the public boundary, so shared-infrastructure.md was actually read: all 7 categories are settled at U-01 (exposure platform TLS/WAF/access log with H-6 discharged; API process = FastAPI+uvicorn; single job worker; DB job queue; WAL BECAUSE api+worker share the file; SECURITY-07 documented exception; least privilege). **FINDING 1**: that document attributes the worker process to U-04, but the refined design puts the worker CODE in U-07 executing U-04's logic (U-04 NFR-Req Q5=A + U-07 FD Q4=A) - label only, corrected via U07-H14. **FINDING 2**: the document mandates that the optimisation run OUTSIDE a write transaction (SQLite single writer; a 300s write tx would stall the API process) - the design already complies (claim=short UPDATE, solve outside, save=short) but implementation could easily violate it, recorded as U07-H13. See api-orchestration-infrastructure-design-skip.md
  - [x] Code Generation - COMPLETED & APPROVED (2026-07-17T13:35:00Z)
    - Part 1 (Planning) approved 2026-07-17T12:20:00Z; Part 2 executed all 16 steps
    - `src/api_orchestration/` (16 files) + `tests/api_orchestration/` (23 tests: 15 example, 6 property, 1 stateful/PBT-06)
    - In-place modifications: `optimization_engine/validation.py` (U07-H1 - `_validate_pins` rewritten to share it, so C1..C5 has ONE interpretation), `data_management/schema.py` + `alembic/versions/0002_accounts_sessions_jobs.py` (accounts/sessions/jobs columns), `pyproject.toml`, `.importlinter`
    - **U07-H13 honoured**: `worker.step()` = claim (short tx) -> solve (NO tx) -> record (short tx). SQLite is a single writer; a 300s write tx would stall the API process
    - **U07-H14 discharged**: shared-infrastructure.md section 2 worker ownership corrected U-04 -> U-07
    - **DP-01 structural**: auth is middleware with a `PUBLIC_ROUTES` allowlist, NOT per-route `Depends()`. Forgetting fails CLOSED (401), not open. P-API02 tests it
    - **4 deviations found during generation** (see implementation-summary.md): (1) source-IP design gap - behind the exposure platform `request.client.host` is the PROXY's, making NFR-S10.2 allowlisting meaningless; fixed with `trusted_proxies` + `source_ip()` honouring X-Forwarded-For ONLY from a listed peer, empty (=deny) otherwise; (2) **real bug** - request parameters were never persisted so the worker solved with config defaults (`department_cap_limit=1` -> INFEASIBLE); fixed via `params_json` column; (3) `GET /events/{id}/comparison` NOT exposed - blocked on U05-H6's deferred historical tables, not on U-07; (4) U-03 schema skeleton extended in place
    - **New mypy waiver**: `api_orchestration.dto` `disallow_any_explicit=false` - pydantic's own `BaseModel` declares `__init__(**data: Any)` (verified: a 3-line model with no Any of ours reports the same error). Contained like cp_sat_adapter: import-linter keeps pydantic out of U-01..U-06 and the override is one module, so a `BaseModel` anywhere else in U-07 fails mypy. **Non-vacuity proven** by injecting `class _Probe(BaseModel)` into converters.py -> 1 error
    - **R-8 non-vacuity proven**: `import frontend` injected into routers.py -> BROKEN (13 kept, 1 broken); removed -> 14 kept
    - Gates: **pytest 173 passed** (no regression in U-01..U-06's 150), **mypy strict clean (105 files)**, **ruff clean**, **lint-imports 14 contracts kept**
- [x] **U-08 frontend — COMPLETE & APPROVED (2026-07-23T18:55:00Z), all 5 stages (Infra Design SKIPPED - verified)**
  - [x] Functional Design - COMPLETED & APPROVED (2026-07-23) - 7 screens V-01..V-07, comparison deferred (U08-H3), value via assignment metrics needs U08-H2
  - [x] NFR Requirements - COMPLETED & APPROVED (2026-07-23) - React 18 + TS strict + Vite / fast-check / Vitest + Testing Library / WCAG 2.1 AA / evergreen (U01-H20 discharged)
  - [x] NFR Design - COMPLETED & APPROVED (2026-07-23) - TanStack Query + Context, ESLint import-boundary for H-5, CSS Modules (Q3=A)
  - [x] Infrastructure Design - **SKIPPED & user-approved (2026-07-23)** - verified against shared-infrastructure.md; frontend adds no infra (client-side, no DB/compute/cloud), static serving is a Code Gen detail (U08-H4)
  - [x] Code Generation - COMPLETED & APPROVED (2026-07-23T18:55:00Z)
    - `src/frontend/` React 18 + TS (22 source + 7 test files). Frontend gates: tsc clean, eslint clean, vitest 12 passed (7 fast-check PBT + 5 component). H-5 non-vacuity proven (backend import -> eslint FAIL).
    - Backend in-place: U08-H1 (facility/district import-export endpoints + 5 tests), U08-H4 (guarded static mount), **U07-H15 (middleware now uses the injected clock - real bug: sessions made with the frozen test clock read as expired once wall-clock passed NOW+8h)**.
    - Deviations: U08-H5 (self-contained npm project), U08-H6 (single global.css vs approved CSS Modules Q3=A - awaiting confirmation), U08-H2 (value shown via objective/gap until AssignmentResponse carries travel metrics).
    - Backend 4 gates: pytest 178, mypy 106 clean, ruff clean, lint-imports 14 kept.
- [x] Build and Test - **COMPLETE (2026-07-24)** - backend pytest 181 + frontend vitest 12, all gates green, 6 integration scenarios; instruction files under construction/build-and-test/. Fixed U08-H7 (SPA shell was 401'd by deny-by-default auth; auth now guards API only, IP/rate still apply to static) + regression test_static.py. Frontend built (dist/, 231KB/73KB gzip). Awaiting approval for OPERATIONS.

**Note**: Each per-unit stage remains CONDITIONAL. At the start of each unit's stage, re-evaluate whether that stage adds value for that unit (e.g. Infrastructure Design for U-01 shared-kernel) and propose a skip if it does not.

### OPERATIONS PHASE
- [ ] Operations - PLACEHOLDER

## Current Status
- **Lifecycle Phase**: INCEPTION
- **Current Stage**: Workflow Planning Complete
- **Next Stage**: Application Design
- **Status**: Awaiting user approval of execution plan

## Handoffs to Later Stages
See `aidlc-docs/inception/plans/execution-plan.md` section 8 (H-1 .. H-8).
- H-1: A-04 linear cost model does not capture the taxi-cost nonlinearity -> Functional Design
- H-2: 13 invariants + property categories -> Functional Design (PBT-01)
- H-3: exact vs heuristic solver trade-off for 400k binary variables -> NFR Requirements
- H-4: PBT framework selection -> NFR Requirements (PBT-09)
- H-5: explicit API boundary (NFR-M05) -> Application Design, Code Generation
- H-6: confirm controls provided by the existing internet-exposure platform (A-06) -> Infrastructure Design (SECURITY-02)
- H-7: 4 misuse cases (MU-01..MU-04) -> Application Design, NFR Design (SECURITY-11)
- H-8: PoC vs production deltas (A-07 topology, A-08 availability input) -> Application Design, Infrastructure Design
