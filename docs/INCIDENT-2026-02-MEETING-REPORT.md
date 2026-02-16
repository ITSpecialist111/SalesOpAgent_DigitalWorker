# Incident Report: Meeting Report Transcript Pipeline Stabilization (2026-02-16)

## Summary
This incident covered repeated failures in the run_meeting_report flow for Avon Sunday meeting. The failures progressed through multiple layers (Graph meeting resolution, transcript content retrieval, report rendering, and final response formatting).

Final state: fixed and verified in production.

## Production Validation Snapshot (2026-02-16)

- Active revision: `<container-app-revision>`
- Container app status: Running / Healthy / 100% traffic on latest revision
- Health endpoint: `status=ok`, `agent_initialized=true`, MCP `state=ready`

---

## User-visible symptoms observed

1. Transcript unavailable despite permissions remediation.
2. HTTP 400 from onlineMeetings lookup calls.
3. HTTP 400 when fetching transcript content for a resolved meeting/transcript pair.
4. Runtime exception: replace() argument 2 must be str, not dict.
5. Runtime exception: dict object has no attribute lower.
6. Low-quality response formatting:
   - Summary printed as raw dict.
   - CRM fields with None values surfaced in user output.

---

## Root causes and fixes

### RC-1: Unsupported/brittle Graph onlineMeetings query patterns
- Problem:
  - Event id to onlineMeeting id resolution depended on query shapes that intermittently returned 400.
  - Fallback listing and filters included query variants not consistently accepted for this tenant/workload.
- Fix:
  - Prioritized event onlineMeeting data and supported filter paths.
  - Removed unsupported query options from failing lookup paths.
  - Added additional fallback via VideoTeleconferenceId where available.
  - Added Graph error-body extraction for actionable diagnostics.

### RC-2: Path encoding and transcript content format handling
- Problem:
  - Transcript content request failed with 400 in certain ID forms.
- Fix:
  - URL-encoded onlineMeetingId and transcriptId path segments.
  - Requested content with $format=text/vtt and fallback retry without format.

### RC-3: Report generator type assumptions
- Problem:
  - generate_email_html expected string summary; LLM occasionally returned structured summary object.
- Fix:
  - Added type coercion in report_generator for summary/tasks/crm_updates.
  - Safely handled dict/list values via JSON serialization.
  - Added regression test coverage.

### RC-4: Learn-reference extraction assumed summary is string
- Problem:
  - _fetch_learn_references called .lower() on summary directly.
- Fix:
  - Normalized summary to string for keyword matching.
  - Added regression test for dict summary input.

### RC-5: Response formatting quality gap
- Problem:
  - run_meeting_report returned raw structured summary and noisy None CRM values.
- Fix:
  - Normalized output in agent-level formatter:
    - Flattened key_agreements style summaries into readable text.
    - Normalized tasks into readable strings.
    - Filtered empty CRM values.

---

## Files changed during stabilization

- src/integrations/graph_transcript_client.py
- src/services/report_generator.py
- src/services/meeting_processor.py
- src/agent.py
- tests/test_report_generator.py
- tests/test_meeting_processor.py

---

## Validation performed

- Repeated local test runs after each patch phase (suite green).
- Multiple Azure deployments with azd up.
- Live Container Apps log verification at each stage.
- Direct in-container runtime probes for transcript retrieval and processor execution.
- Final user confirmation from live agent output:
  - readable summary text
  - clean task list
  - no dict/lower or replace errors
  - no None CRM noise

---

## Operations runbook for future incidents

1. Confirm active revision and health.
2. Capture latest run_meeting_report trace (single correlation window).
3. Isolate failure layer:
   - meeting resolution
   - transcript listing
   - transcript content
   - report generation
   - output formatting
4. Patch only the failing layer with typed guards and explicit logging.
5. Run tests locally.
6. Deploy and verify on live logs.
7. Re-run end-to-end user path and confirm final user-visible output quality.

---

## Preventive controls added

- Better type normalization across summary/tasks/crm payload surfaces.
- Safer Graph fallback strategy and richer error diagnostics.
- Regression tests for dict/structured analysis outputs.
- Reduced runtime log noise from SDK internals while preserving app-level diagnostics.

---

## Follow-up recommendations

1. Introduce a strict typed schema for analysis_data before report generation.
2. Add a small formatter utility with unit tests for all user-facing summary render paths.
3. Add one integration smoke test fixture that simulates structured LLM output variants (string, dict, list) for summary.
4. Keep this incident document updated if related regressions appear.
