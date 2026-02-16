# Implementation Plan: Agent 365 Synthetic Worker

## Phase 1: Foundation ("The Shell") (Complete)
- [x] Scaffolding & Hosting.
- [x] Work IQ Integration.

## Phase 2: Core Integrations ("The Muscle") (Complete)
- [x] `GraphTranscriptClient` (Implemented: event → onlineMeeting resolution + transcript content retrieval).
- [x] `DynamicsClient` (Stub).

## Phase 3: Meeting Detection ("The Eyes") (Complete)
- [x] `EmailHandler` & `CalendarHandler` (Initial Implementation).

## Phase 4: Intelligence Pipeline ("The Brain")
**Goal**: Process the meeting the agent attended.
- [x] **4.1 Update Calendar Handler**:
    - [x] Polls and filters recently ended meetings for the agent context.
- [x] **4.2 Meeting Processor Service**:
    - [x] `src/services/meeting_processor.py` implemented.
    - [x] `process_meeting(meeting_id)` implemented:
        1. Fetch Transcript (via `GraphTranscriptClient`, user-scoped Graph routes).
        2. Call LLM for extraction (Summary, Tasks, Opportunity Updates).
        3. Generate HTML + Adaptive Card reports.
        4. Attempt delivery via Graph/MCP strategy.
- [ ] **4.3 Action Handler**:
    - [ ] Handle the user's reply to the approval email (Approved -> Execute CRM Update).

## Phase 4c: Interactive Presence ("The Voice")
**Goal**: Make the agent a polite participant.
- [x] **4.4 Teams Chat Service**:
    - [x] Create `src/services/teams_chat_service.py`.
    - [x] Implement `send_intro_message(chat_id)`: "Hi everyone! I'm joining to capture notes for Dynamics 365."
- [x] **4.5 Update Calendar Handler**:
    - [x] Poll for meetings starting in 5 mins -> Trigger Intro Message.

## Phase 4d: Live Knowledge ("The Helpful Colleague")
**Goal**: Monitor call and inject MS Learn links.
- [x] **4.6 MS Learn Client**:
    - [x] Implemented `src/integrations/ms_learn_client.py` (real HTTP search API).
    - [ ] **Future**: Replace with `McpServers.WebSearch.All` (Bing) constrained to `site:learn.microsoft.com`.
- [x] **4.7 Live Knowledge Service**:
    - [x] Create `src/services/live_knowledge_service.py`.
    - [x] Logic: Poll transcript -> Detect Keywords -> Search -> Post to Chat.

## Phase 5: Verification
- [x] **5.1 End-to-End Test**:
    - [x] Simulate a meeting end -> Verify transcript fetch -> Verify CRM proposal email/report path.
    - [x] Validate deployment health and active revision in Azure Container Apps.
