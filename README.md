# Sherlock AI

### Find the Cause. Fix the Future.

Sherlock AI is an evidence-driven, agentic Windows diagnostics platform that investigates computer problems instead of simply suggesting generic fixes.

It takes a user's complaint, builds an investigation plan, collects system evidence, researches relevant information, reasons over the evidence, identifies possible causes, and produces a structured troubleshooting report.

> Every bug leaves a clue.

---

## Overview

When a computer starts behaving strangely, users usually have to search through forums, try random fixes, or manually inspect Task Manager, Device Manager, Windows Settings, and other system tools.

Sherlock AI approaches the problem differently.

Instead of immediately suggesting a solution, Sherlock investigates:

```text
User Complaint
      ↓
Investigation Plan
      ↓
Evidence Collection
      ↓
Research
      ↓
Reasoning
      ↓
Hypotheses
      ↓
Recommendations
      ↓
Guided Troubleshooting
      ↓
Case Report
```

The goal is to make Windows troubleshooting more structured, explainable, and evidence-driven.

---

## What Sherlock Does

A user can enter a problem such as:

> "My laptop is running very slowly."

Sherlock then:

1. Understands the complaint.
2. Creates an investigation plan.
3. Collects relevant system evidence.
4. Performs targeted research when required.
5. Reasons over the collected evidence.
6. Produces possible explanations with confidence levels.
7. Generates evidence-grounded recommendations.
8. Guides the user through troubleshooting steps.
9. Records the outcome of each troubleshooting step.
10. Produces a structured investigation record.

---

## Why Sherlock?

Traditional troubleshooting tools often follow a fixed checklist.

Sherlock is designed around an investigation model:

### Complaint → Evidence → Hypothesis → Action → Verification

This allows the system to adapt its investigation based on what it discovers instead of treating every problem the same way.

Sherlock does not blindly modify the user's system.

Recommendations are presented as manual actions so the user remains in control.

---

# Core Features

## 1. Agentic Investigation

Sherlock separates the investigation into multiple stages rather than generating one large AI response.

```text
Planner
   ↓
Tool Manager
   ↓
Evidence Collector
   ↓
Researcher
   ↓
Reasoner
   ↓
Report Generator
```

---

## 2. System Evidence Collection

Current diagnostic areas include:

- CPU
- Memory
- Disk
- Startup applications

Planned areas include:

- Wi-Fi
- Battery
- Storage
- Temperature / overheating
- Device and driver information

Evidence is stored as structured tool results.

Example:

```json
{
  "tool_name": "cpu",
  "status": "success",
  "payload": {
    "usage_percent": 78.4
  }
}
```

---

## 3. Evidence-Based Reasoning

Sherlock produces hypotheses with:

- Explanation
- Supporting evidence
- Contradicting evidence
- Confidence

Example:

```text
Hypothesis:
High background resource usage

Supporting Evidence:
CPU utilization is elevated.

Contradicting Evidence:
No significant memory pressure was observed.

Confidence:
Medium
```

---

## 4. Local AI Reasoning

Sherlock can use local Ollama models for reasoning.

Current development configuration:

```text
Ollama
└── qwen2.5:1.5b
```

The reasoning layer uses structured JSON output. A deterministic baseline reasoner is also available as a fallback.

---

## 5. Web Research

When additional information is useful, Sherlock generates investigation-specific research queries.

Research supplements system evidence and can provide:

- Relevant documentation
- Windows troubleshooting information
- Known causes
- Configuration guidance
- Supporting technical references

Research sources are displayed in the final report.

---

## 6. Structured Investigation Reports

Each investigation produces:

- Case ID
- Problem description
- Summary
- Confidence
- Reasoning method
- Hypotheses
- Supporting evidence
- Contradicting evidence
- Recommendations
- Research sources
- Investigation timestamp

Example:

```text
INVESTIGATION REPORT

Problem
└── Laptop is running slowly

Confidence
└── High

Hypotheses
├── Background applications
├── Startup applications
└── Resource-intensive applications

Recommendations
├── Investigate startup applications
├── Identify resource-intensive processes
└── Perform additional system checks
```

---

## 7. Guided Troubleshooting

Each recommendation can become an interactive troubleshooting session.

```text
Recommendation
      ↓
Start Guided Troubleshooting
      ↓
Step 1 of N
      ↓
Done / Couldn't Complete
      ↓
Step 2 of N
      ↓
...
      ↓
Resolved / Exhausted
```

A session records:

- Current recommendation
- Current step
- Completed answers
- Step result
- Session status
- Start time
- Last update

---

## 8. Persistent Troubleshooting State

Guided troubleshooting sessions are stored as part of the investigation.

Example:

```text
Recommendation: 1
Step: 3
Status: in_progress
```

The session can be retrieved with:

```http
GET /investigation/{case_id}/troubleshooting
```

---

# Architecture

```text
                    ┌─────────────────────┐
                    │     React / Tauri   │
                    │      Frontend       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │        API          │
                    └──────────┬──────────┘
                               │
                               ▼
                 ┌──────────────────────────┐
                 │  Investigation Service   │
                 └────────────┬─────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │   Planner   │    │ Tool Manager│    │  Researcher │
   │    Agent    │    │             │    │             │
   └─────────────┘    └──────┬──────┘    └─────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Evidence        │
                    │ Collectors      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Reasoner     │
                    │ Ollama / Local  │
                    │      AI         │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Investigation   │
                    │     Report      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    Guided       │
                    │ Troubleshooting │
                    └─────────────────┘
```

---

# Technology Stack

### Frontend
- React
- TypeScript
- Tailwind CSS
- Vite
- Tauri

### Backend
- Python
- FastAPI
- Pydantic
- SQLite

### AI
- Ollama
- Qwen 2.5
- Structured JSON reasoning
- LangGraph planned

### Diagnostics
- PowerShell
- psutil
- WMI
- Windows system APIs

### Reporting
- Structured investigation reports
- ReportLab planned for exportable case reports

---

# Project Structure

```text
Sherlock-AI/
│
├── backend/
│   └── app/
│       ├── api/
│       │   ├── endpoints/
│       │   │   └── troubleshooting.py
│       │   └── router.py
│       ├── models/
│       │   ├── investigation.py
│       │   └── troubleshooting_session.py
│       ├── schemas/
│       │   ├── investigation.py
│       │   └── troubleshooting.py
│       ├── services/
│       │   └── investigation_service.py
│       └── reasoning/
│           └── ollama_reasoner.py
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── investigation/
│       │   │   └── TroubleshootingSession.tsx
│       │   ├── landing/
│       │   │   ├── InvestigationForm.tsx
│       │   │   ├── InvestigationReportCard.tsx
│       │   │   ├── InvestigationResults.tsx
│       │   │   ├── ToolResultCard.tsx
│       │   │   └── ...
│       │   └── ...
│       ├── lib/
│       │   └── investigationApi.ts
│       ├── types/
│       │   └── index.ts
│       ├── App.tsx
│       └── main.tsx
│
└── README.md
```

---

# Investigation API

### Start Investigation

```http
POST /investigation/start
```

```json
{
  "problem_description": "My laptop is running very slowly."
}
```

### Start Guided Troubleshooting

```http
POST /investigation/{case_id}/troubleshooting/start
```

```json
{
  "recommendation_index": 0
}
```

### Answer Troubleshooting Step

```http
POST /investigation/{case_id}/troubleshooting/answer
```

```json
{
  "result": "done"
}
```

or:

```json
{
  "result": "could_not_complete"
}
```

### Get Troubleshooting Session

```http
GET /investigation/{case_id}/troubleshooting
```

---

# Troubleshooting State Machine

```text
                  ┌──────────────┐
                  │  IN_PROGRESS │
                  └──────┬───────┘
                         │
              ┌──────────┴──────────┐
              │                     │
             Done          Couldn't Complete
              │                     │
              ▼                     ▼
       Next Step?            Next Step?
              │                     │
              ▼                     ▼
         IN_PROGRESS          IN_PROGRESS
              │                     │
              └──────────┬──────────┘
                         │
                    Final Step
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
            Done            No path remaining
              │                     │
              ▼                     ▼
          RESOLVED              EXHAUSTED
```

---

# Safety Philosophy

Sherlock is an investigation and guidance system.

It does **not** blindly execute potentially destructive system changes.

Recommendations are presented to the user so they can:

- Review the proposed action.
- Decide whether to perform it.
- Report whether the step worked.
- Continue or stop the investigation.

The reasoning layer is instructed to avoid:

- Destructive system changes
- Disabling security protections
- Unsafe registry modifications
- Uncontrolled system automation

---

# Design Philosophy

Sherlock's interface follows a case-investigation metaphor.

### Professional Mode

```text
Diagnostics
Evidence
Recommendations
History
```

### Sherlock Mode

```text
Investigation
Clues
Suspects
Verdict
Case Files
```

Both modes represent the same underlying functionality.

---

# Current Development Status

### Completed

- [x] React + TypeScript frontend
- [x] FastAPI backend
- [x] Investigation API
- [x] Investigation domain model
- [x] Evidence collection architecture
- [x] CPU diagnostics
- [x] Memory diagnostics
- [x] Disk diagnostics
- [x] Startup application diagnostics
- [x] Structured investigation reports
- [x] Hypothesis generation
- [x] Confidence levels
- [x] Ollama local reasoning
- [x] Research query generation
- [x] Research source display
- [x] Deterministic reasoning fallback
- [x] Recommendation generation
- [x] Guided troubleshooting backend
- [x] Troubleshooting session state
- [x] Troubleshooting API endpoints
- [x] Guided troubleshooting frontend
- [x] Recommendation-level troubleshooting buttons
- [x] Step-by-step troubleshooting UI
- [x] Done / Couldn't Complete flow
- [x] Resolved / Exhausted session states

### In Progress

- [ ] Enforce stronger recommendation step generation
- [ ] Improve AI-generated Windows troubleshooting instructions
- [ ] Resume troubleshooting automatically after page refresh
- [ ] Expand diagnostic tools
- [ ] Improve investigation planning
- [ ] Improve evidence-to-hypothesis reasoning
- [ ] Improve UI polish
- [ ] Case history
- [ ] Exportable investigation reports
- [ ] Tauri desktop integration
- [ ] LangGraph agent orchestration
- [ ] AMD hardware/local AI optimization

---

# Roadmap

## Phase 1 — Investigation Core

- Expand diagnostic tools
- Improve investigation planning
- Improve evidence collection
- Improve hypothesis generation

## Phase 2 — Guided Troubleshooting

- Multi-step troubleshooting
- Persistent sessions
- Better verification steps
- Investigation resumption
- Troubleshooting history

## Phase 3 — Desktop Application

- Tauri integration
- Native Windows experience
- Background diagnostics
- System notifications
- Case history

## Phase 4 — Advanced Agentic System

- LangGraph orchestration
- Dynamic investigation planning
- More specialized diagnostic agents
- Improved evidence correlation
- Long-term investigation memory

## Phase 5 — AMD Optimization

- AMD hardware-aware diagnostics
- Local inference optimization
- Radeon / ROCm experimentation where applicable
- Hardware-specific evidence collection

---

# Running Locally

## Backend

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start FastAPI:

```bash
uvicorn app.main:app --reload
```

Backend:

```text
http://127.0.0.1:8000
```

## Ollama

Pull the development model:

```bash
ollama pull qwen2.5:1.5b
```

Verify it:

```bash
ollama run qwen2.5:1.5b
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

---

# Testing

Backend:

```bash
pytest
```

Frontend type checking:

```bash
npx tsc --noEmit
```

Frontend build:

```bash
npm run build
```

Recommended verification flow:

```text
Backend tests
      ↓
TypeScript check
      ↓
Production build
      ↓
Live investigation
      ↓
Guided troubleshooting
```

---

# Project Vision

Sherlock AI is intended to evolve from a simple troubleshooting assistant into an **evidence-driven computer investigation agent**.

The long-term goal is not:

> "Tell me what button to click."

It is:

> "Investigate what is happening on my computer, show me the evidence, explain the likely causes, and guide me through verifying the fix."

---

# Hackathon

Sherlock AI was developed for the **AMD AI DevMaster Hackathon**, with a focus on agentic AI and local/system-level intelligence.

The project explores how local AI can combine:

- System diagnostics
- Evidence collection
- Research
- Reasoning
- Agentic planning
- Human-guided troubleshooting

into a single desktop investigation workflow.

---

# License

Add your preferred license here.

---

## Sherlock AI

**Find the Cause. Fix the Future.**

> Every bug leaves a clue.
