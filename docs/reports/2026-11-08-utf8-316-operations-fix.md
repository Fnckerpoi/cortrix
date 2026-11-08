# Cortrix `type_error.316` 500 — Root Cause, Fix, Upstream PR Evaluation & Live Redeploy

Date: 2026-11-08 (Asia/Shanghai) · Repo: `/Users/fnckerpoi/Documents/GitHub/cortrix`
- Upstream base: `upstream/main` (`cortrix/cortrix` @ `b2203f7`, PR #266) — verified unfixed upstream.
- PR-ready branch pushed to fork: `origin/fix/utf8-safe-truncation` @ `476ca35` (`https://github.com/Fnckerpoi/cortrix/tree/fix/utf8-safe-truncation`, DCO `Signed-off-by` included, isolated from 18 local watcher/MCP/Dockerfile files).
- Live system: `deploy-cortrix-1` rebuilt and redeployed (`cortrix:quickstart` `159c387f5e8b`, `CORTRIX_SOURCE_REVISION=476ca35-local`, `/app/cortrix_server` SHA-256 `c85e4958...`); previous image preserved as `cortrix:quickstart-backup-20261108` (`08bc0b925a3a`).

## Symptom

Log line reported:
`Permanent CX_ERR_INTERNAL_ERROR Internal server error: [json.exception.type_error.316] incomplete UTF-8 string; last byte: 0x80`

Reproduced pre-redeploy on `GET http://127.0.0.1:8420/api/v1/operations?limit=50` → **HTTP 500** `CX_ERR_INTERNAL_ERROR`.

## Root Cause

1. `src/query/query_wiring.cpp` (`QueryTextSummary`, L803) and `src/observability/operation_log_emitter.cpp` (`TruncateSummary`, L32) byte-sliced strings with `substr(0, 100)` before writing `operation_log.summary`.
2. Multi-byte UTF-8 queries (e.g. 3-byte CJK characters) split mid-character at byte 100, persisting ill-formed trailing lead/continuation bytes into SQLite `TEXT` (95 legacy `action='query'` rows in `catalog.db`).
3. `src/observability/operation_logger_impl.cpp` (`ColText`, L39) read raw bytes without validation, and `GET /api/v1/operations` serialized responses with strict `nlohmann::json::dump()`, throwing `json.exception.type_error.316` caught by the global exception handler in `src/server/http_server.cpp`.

## Fix Summary (17 files in `476ca35`)

- `include/cortrix/common/utf8_utils.h`: header-only `IsWellFormedUtf8`, `Utf8SafeTruncate`, `Utf8SafeHeadTail`, and `SanitizeUtf8` (Unicode RPI #3 maximal-subpart replacement, byte-identical to `nlohmann::json::error_handler_t::replace`).
- Write sites aligned to UTF-8 code-point boundaries:
  - `src/query/query_wiring.cpp` (`QueryTextSummary`)
  - `src/observability/operation_log_emitter.cpp` (`TruncateSummary`)
  - `src/agent_trace/mcp_session_handler.cpp` (`TruncateParams`, `TruncateResult`, `FormatError`)
  - `src/agent_trace/interactions_handler.cpp` (`TruncateSnippet`)
  - `src/server/routes/observability_routes.cpp` (`value_preview` on invalid query parameters)
  - `src/spc/spc_pipeline.cpp`, `src/spc/enrich_backfill_worker.cpp` (`last_error` 200B caps)
  - `src/doc_summary/doc_summary_generator.cpp` (`TruncateForDiagnostics`)
  - `src/logging/sanitizer.cpp` (`MaskPartial`, `TruncateContent`)
  - `src/common/agent_llm_config_codec.cpp` (`MaskApiKey`)
  - `src/import/import_manager.cpp` (`QuerySignature` SQL digest)
- Read-side healing for legacy stored rows:
  - `src/observability/operation_logger_impl.cpp` (`ColText`) normalizes ill-formed byte sequences via `SanitizeUtf8`.
- Unit & route tests:
  - `tests/unit/test_utf8_utils.cpp` (registered in `tests/CMakeLists.txt`), `tests/unit/test_operations_routes.cpp` (`LegacyByteTruncatedSummarySerializesCleanly`), `tests/unit/test_cleanup_scheduler.cpp` (`SummaryTruncatedTo100`).

## Verification

1. **Host C++ unit suite**: `ctest -L unit` → 11,948/11,948 passed; post-polish rebuild + 323 targeted tests across 42 suites → 323/323 passed; `scripts/sync_version.py --check` and `tests/ci/test_classify_changes.sh` passed.
2. **Live Docker redeployment (`127.0.0.1:8420` & MCP `127.0.0.1:8421`)**:
   - `GET /api/v1/health` → 200 (`healthy`); `GET /api/v1/system/health/ready` → 200 (`ready`, all 6 components `ok`); `GET /api/v1/agent/health` → 200 (`ready`, `llm_reachable: true`).
   - `GET /api/v1/namespaces` → 200: `obsidian-knowledge` (`doc_count=1632`, `block_count=26788`), `obsidian-experience` (`doc_count=48`, `block_count=1435`) — 100% preserved.
   - `GET /api/v1/operations?limit=50` → **200 OK** (43 legacy byte-cut summaries in first page healed with `U+FFFD`, strict UTF-8 JSON valid).
   - `POST /api/v1/query` (171-byte Chinese query) → 200 OK (3 hits); newly written `operation_log` row `id=437` has `summary_bytes=98`, valid UTF-8, `has_ufffd=False`.
   - `GET /api/v1/operations?limit=%80%80` → **400** `CX_ERR_OPLOG_INVALID_FILTER` (not 500).
   - MCP gateway (`127.0.0.1:8421/mcp`): missing/wrong Bearer token → 401; valid token → `tools/list` (32 tools), `cortrix_health` → 200, `cortrix_list_operations(limit=50)` → 200 (`isError=False`, 27,529B), `cortrix_query` → 200 (`isError=False`).
   - Container restart recovery (`docker restart deploy-cortrix-1`): returned `healthy`, `/health`=200, `/system/health/ready`=200, `/operations?limit=50`=200, zero error logs.
