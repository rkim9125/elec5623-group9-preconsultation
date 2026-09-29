# Proposed Component Breakdown and Team Collaboration

**Project:** Pre-consultation Preparation Agent
**Course / Group:** ELEC5623 — Group 9
**Team size:** 5 members
**Status:** Proposed implementation and collaboration plan; individual selections remain open.

## 1. Component Selection and Teamwork

We suggest organising our implementation into **seven components**. **Each person can choose 1–3 components** based on their interests, strengths and availability, indicating whether they would like to lead or support each one.

**The choices do not need to be exclusive. Overlapping areas are encouraged as part of our teamwork.** They give us opportunities to develop features together, pair-program, review each other's code, test integrations and understand more of the system rather than working in isolation.

After everyone shares their preferences, we should agree on a coordinator for each component and balance the actual tasks across the five members. Components differ in size, so selecting the same number of components does not necessarily mean taking on the same workload.

A coordinator keeps the work organised and interfaces consistent; they do not have to implement everything alone. For shared work, each task should still have a clear owner and an agreed collaborator or reviewer. **Overlap should create closer collaboration, not duplicate implementations or unclear accountability.**

This document proposes a new way to organise implementation work. It does not automatically replace the existing proposal's named responsibilities or expand its approved product scope; any changes should be agreed by the team.

## 2. Component Overview

| ID | Component | Main focus | Closest collaboration |
|---|---|---|---|
| **C1** | **UI — Patient** | Patient input, conversation, information review, correction and summary approval. | C2, C3 |
| **C2** | **UI — Doctor / Clinician Summary View** | Read-only presentation of patient-approved information. | C1, C3 |
| **C3** | **Backend — Core Logic** | Business APIs, dialogue state, validation, adaptive planning, safety and workflow orchestration. | C1, C2, C4, C5, C6 |
| **C4** | **Backend — LLM Calls and Prompt Engineering** | Model integration, structured extraction, question wording and grounded summary generation. | C3, C6 |
| **C5** | **Backend — Utilities, Document Processing and OSS Integration** | Agreed file processing, document generation and object storage integration. | C1, C2, C3, C6 |
| **C6** | **Database and Data Access Layer — DB & DAO** | Data models, persistence, migrations, source references and audit history. | C3, C4, C5 |
| **C7** | **Miscellaneous — Implementation Specification and Test Environment Setup** | Shared technical specification, environment configuration and integration readiness. | C1–C6 |

These are logical components, not a requirement to build seven separate services. The team can keep them in a shared repository and application structure while maintaining clear module boundaries.

## 3. Component Responsibilities

### C1 — UI: Patient

**Purpose:** Build the main patient-facing workflow, from starting a session to approving the final summary.

**Main responsibilities:** Implement the scope and limitations screen, initial free-text input, conversational follow-up questions, and displays of captured, uncertain, skipped and missing information. Provide correction, "I don't know", skip, finish and summary-approval controls. Support responsive layouts, loading states and recoverable error handling.

**Boundary:** The interface displays state, coverage and stopping information returned by the backend. It should not maintain a separate implementation of the planner or completeness rules. Coverage must be presented as coverage of selected preparation fields, not as clinical safety or a complete medical history. [P1, P2]

**Expected deliverables:** Patient pages and reusable UI components, API integration, interaction tests and a working input-to-approval flow.

**Collaboration:** Work with C3 on patient actions and API responses, and with C2 on a shared summary data structure and consistent presentation. Coordinate with C5 only for upload or download features included in the agreed scope.

### C2 — UI: Doctor / Clinician Summary View

**Purpose:** Present a concise, read-only handoff based on information the patient has reviewed and approved.

**Main responsibilities:** Display the approved structured summary and patient question list. Clearly label patient-reported information, uncertainty and unavailable details. Coordinate shared summary components with C1 so that the patient and clinician views present the same approved content.

**Boundary:** This is not a full clinician dashboard, diagnostic tool, prescription interface or electronic health record editor. The clinician does not chat with the agent. The proposal describes the clinician view as optional in FR-11; its inclusion and priority should be confirmed during allocation. [P1]

**Expected deliverables:** A read-only summary page, retrieval of the approved content through C3, and checks that drafts or unapproved changes are not presented as the final handoff.

**Collaboration:** Work closely with C1 on display components and C3 on approval status and summary retrieval. A contributor choosing this smaller UI component may also choose C7 or help coordinate shared evaluation work.

### C3 — Backend: Core Logic

**Purpose:** Own the application's business rules and connect the complete preparation workflow.

**Main responsibilities:** Implement session APIs, workflow orchestration, the versioned consultation schema, explicit dialogue-state tracking, candidate validation, correction and contradiction handling, conditional-field activation, completeness and resolution calculations, next-question selection, stopping rules, predefined safety controls, and patient review and approval.

**Boundary:** Deterministic application logic controls which information is accepted, how state changes, which target is asked about next and when the workflow stops. LLM outputs are candidates or generated wording, not authoritative state updates. Safety interruption uses the project's predefined rules and approved fixed wording; it is not a diagnosis or urgency assessment. [P2]

**Expected deliverables:** Business APIs, a testable state and planning engine, workflow integration and tests for correction, uncertainty, refusal, stopping and safety interruption.

**Collaboration:** Agree contracts with both UIs, structured model interfaces with C4, persistence requirements with C6, and approved file-processing entry points with C5. Provide technical decisions and setup requirements to C7.

### C4 — Backend: LLM Calls and Prompt Engineering

**Purpose:** Provide bounded language-model capabilities behind clear, testable interfaces.

**Main responsibilities:** Implement the model adapter, prompts, structured extraction with supporting evidence, neutral wording for the selected follow-up question, and summary and question-list generation from validated state. Handle output-format checks, timeouts, bounded retries, prompt versioning, and token and latency recording. Supply and test the wording or templates used by the agreed fallback process.

**Boundary:** The LLM must not directly write official slot state, choose a different question target or publish a final summary without validation and patient approval. C4 checks output structure and works with C3 on grounding, target validation and fallback behaviour; C3 controls acceptance into the business workflow. [P2]

**Expected deliverables:** Model integration, extraction/question/summary interfaces, versioned prompts and templates, representative test cases, and consistent success and error responses.

**Collaboration:** Work closely with C3 on schemas and validation rules. Coordinate with C6 on model-call records and with C7 on model configuration and mock responses for development without live calls.

### C5 — Backend: Utilities, Document Processing and OSS Integration

**Purpose:** Provide reusable file-processing and storage services for the capabilities the team agrees to implement.

| Area | Responsibilities |
|---|---|
| **Document processing** | Extract text from agreed image, PDF and Word formats; use OCR where needed; retain available source locations and report parsing failures. |
| **Document generation** | Render an approved summary into agreed downloadable formats, such as PDF or DOCX. |
| **Object storage / OSS integration** | Support file upload, retrieval, download and deletion, with storage references and controlled access. |
| **File handling** | Validate agreed file types and sizes, report processing status and coordinate cleanup. |

**Boundary:** Document processing does not itself interpret medical content or update patient state. C4 generates summary content; C5 renders that approved content into a file without inventing or rewriting facts. C3 decides whether a workflow action or file access is permitted, and C6 stores the relevant metadata.

**Expected deliverables:** A storage integration layer, the agreed parsing and export utilities, documented supported formats, and file-processing tests.

**Collaboration:** Work with the UIs on upload/download behaviour, C3 on how extracted content enters validation and review, C6 on metadata, and C7 on storage configuration.

**Scope note:** File processing, downloadable document generation and OSS integration are proposed engineering extensions from our team discussion, not mandatory capabilities established by the proposal's functional requirements. Agree their priority and supported formats separately so they do not delay the core text-based flow. [P1]

### C6 — Database and Data Access Layer: DB & DAO

**Purpose:** Save and retrieve application data reliably through a shared data-access layer.

**Main responsibilities:** Design data models, migrations and data-access methods for sessions, messages, structured slot states, source references, correction history, summary versions and audit logs. Support attachment metadata and model-call records where required. Provide database initialisation, synthetic test data and persistence tests.

**Boundary:** C3 defines business-state meaning and transition rules; C6 defines how those records are stored and retrieved. Avoid duplicating planner or validation decisions inside DAO methods. Keep raw messages and structured state distinct, and preserve the provenance and audit information required by the proposal. [P2, P3]

**Expected deliverables:** An agreed data model, migrations, DAO interfaces, database setup instructions and tests for saving, retrieval and correction history.

**Collaboration:** Work with C3 on consistent state updates and transaction requirements, C4 on model-call records, C5 on file metadata, and C7 on database setup and reset procedures.

### C7 — Miscellaneous: Implementation Specification and Test Environment Setup

**Purpose:** Coordinate the shared technical documentation and environment needed to develop, integrate, test and demonstrate the system.

| Area | Main responsibilities | Expected deliverables |
|---|---|---|
| **Implementation Specification Document** | Coordinate and maintain the system architecture, component boundaries, API contracts, data structures, key workflows, error handling and acceptance criteria. Collect contributions from component owners and keep the specification aligned with implementation changes. | A shared, version-controlled implementation specification with interface examples and key design decisions. |
| **Test Environment Setup** | Set up and maintain an agreed environment for integration testing and demonstrations. Document dependencies, configuration and startup procedures; coordinate database initialisation and synthetic test data; provide configuration templates without credentials and basic checks of connected services. | A working test environment, setup instructions, configuration templates, startup/reset scripts and a smoke-test checklist. |

**Boundary:** C7 coordinates documentation and environment readiness; it does not take over every component's tests, implementation decisions or report writing. Each component's contributors remain responsible for supplying their interface documentation, configuration requirements and tests.

**Collaboration:** Work across C1–C6. Shared setup sessions, specification reviews and integration checks are useful opportunities to keep the team closely connected.

## 4. Shared Responsibilities and Interface Agreements

### 4.1 Agree on contracts before building in isolation

| Interface | Contributors | What to agree |
|---|---|---|
| **UI ↔ Core Logic** | C1, C2, C3 | Patient actions, request/response structures, progress and state displays, errors, summary retrieval and approval status. |
| **Core Logic ↔ LLM** | C3, C4 | Extraction candidates, evidence references, locked question targets, summary structure, failures and fallback behaviour. |
| **Core Logic ↔ DB & DAO** | C3, C6 | State representation, saved records, correction history, summary versions and consistent persistence. |
| **Documents ↔ Core / Storage Metadata** | C3, C5, C6 | Extracted-content handoff, validation and review, storage references, file ownership and export metadata. |
| **All Components ↔ Specification / Environment** | C1–C7 | Dependencies, configuration, startup requirements, interface changes and integration checks. |

Use shared schema definitions and representative example payloads wherever possible. An interface change should be discussed with the affected contributors and reflected in the implementation specification, rather than changed independently on one side.

### 4.2 Share evaluation, documentation and demonstration work

Testing remains everyone's responsibility. Each contributor should provide tests and documentation for their own work, while the team nominates an evaluation coordinator to organise shared cases, experiments, metrics and results. C7 supports the environment and instructions needed to run this work.

The existing proposal's case cards, simulator, baselines, ablations, evaluation metrics and error analysis remain part of the project; this seven-component breakdown does not remove or replace them. [P4]

Everyone should contribute to the final report and demonstration, explain their own component and understand how it connects to the complete workflow. A report or demonstration coordinator organises the combined output rather than doing everyone's work. [P5]

### 4.3 Use overlap for concrete shared tasks

Useful examples include C1 and C2 building a shared summary component, C3 and C4 testing an extraction-and-validation flow, C3 and C6 implementing correction history together, and C5 and C7 connecting storage in the test environment.

For each shared task, agree on the implementation owner, collaborator or reviewer, expected output and acceptance check. This makes teamwork visible and keeps responsibilities clear.

## 5. Suggested Integration Milestones

| Milestone | Expected outcome |
|---|---|
| **1 — Contracts and setup** | Agree core schemas and interface examples; establish the repository, specification and initial development/test setup. |
| **2 — First complete flow** | Patient enters information → system asks follow-up questions → patient reviews and approves the summary → clinician view displays the same approved version. Use mocks where needed to integrate early. |
| **3 — Robustness and agreed extensions** | Test uncertainty, refusal, correction, conflicts, finish actions and failures. Add file-processing or storage features only according to the agreed priority. |
| **4 — Evaluation and demonstration** | Run the planned tests and experiments, document failures and limitations, update the specification and rehearse the shared demonstration. |

Work should proceed in parallel. For example, UI contributors can use mock API responses while C3 tests with mock LLM outputs and C4 tests real model calls against fixed inputs.

## 6. Preference and Allocation Template

Agreed allocation, as of this update. C2 and C5 were unassigned when the template first went out; both are now covered by overlap rather than a sixth/seventh person.

| Team member | Preferred components (1–3) | Lead / support preference | Notes or collaboration interests |
|---|---|---|---|
| Heeran | C1, C2 | Lead on both | C1 and C2 share a summary component, so picking up C2 alongside C1 is mostly the same frontend surface, not separate work. |
| Robin | C3, C5 | Lead C3; C5 once C3 is in a stable place | C5 is the scope-noted engineering extension (not required) — deliberately sequenced after C3, not in parallel with it. |
| Alan | C4 | Lead | |
| Bob | C6 | Lead | |
| Tom | C7 | Lead | |

All seven components are covered. Two decisions still open before UI work goes further (tracked in `docs/implementation-status.md`): where the "patient approves the final summary" step lives, and sign-off on the safety-interruption wording in `app/core/safety.py`.

## 7. Proposal Reference and Scope Alignment

Source document: *Pre-consultation Preparation Agent — Project Proposal for ELEC5623*, uploaded as `ELEC5623_Group9_Preconsultation_Proposal_Final_v6(1).pdf`. References below use the document's section numbers.

| Reference | Source sections | Basis retained in this plan |
|---|---|---|
| **P1** | Sections 3, 6.3 and 6.4, particularly FR-11 and FR-15 | Patient-facing preparation; optional read-only clinician view; patient review/approval; no full clinician dashboard or clinical decision-making. |
| **P2** | Sections 4.1–4.9 | Versioned schema; explicit state; bounded LLM extraction; deterministic validation, planning and stopping; coverage versus resolution; grounded summaries and patient control. |
| **P3** | Section 5.1 and Section 10 | Persistence, provenance, correction history, version logging, auditability and data minimisation. |
| **P4** | Sections 9 and 9.10 | Shared evaluation requirements and artefacts, rather than testing only whether the application runs. |
| **P5** | Section 11.1 | Joint final review and each member's ability to explain the system and results. |

The seven-component allocation model, flexible 1–3 selections, collaboration arrangements and proposed file/OSS extensions come from the team-planning discussion. They should not be represented as assignments or additional requirements already approved in the source proposal. Development and testing should retain the proposal's synthetic, mocked or appropriately de-identified data boundary. [P3]
