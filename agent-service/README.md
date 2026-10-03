# AutoFlow AI agent service (Phase 2, step 1)

FastAPI + LangGraph service that runs the 7-step workshop pipeline with two
human-in-the-loop pauses: customer clarification and technician review.

## Run
    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env          # AUTH_DISABLED=1 for local dev
    uvicorn app.main:app --reload
    pytest -q

## API
| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | /requests | customer/technician | Run the graph; may pause for clarification or review |
| POST | /requests/{id}/clarify | owner | Resume with customer answers |
| POST | /requests/{id}/resume | technician | approve / reject / more_info |
| GET | /requests/{id} | owner/technician | Current status, risk, quote, citations |
| GET | /requests/{id}/trace | owner/technician | Step-by-step agent trace |

Statuses: needs_clarification, pending_technician, ready_to_book, approved, rejected, needs_info.
In dev mode send `X-Dev-Role: customer|technician`.

## Design rules
- Escalation, risk and pricing are deterministic (`rules.py`, `quote.py`). A model may extract fields or draft wording but never prices or de-escalates.
- Money is integer minor units. Keyword matching uses word boundaries.
- Interfaces (`Retriever`, `VehicleRepo`, `LLMProvider`) are the seams for Phase 2.

## Live vs planned
| Layer | Now | Next |
|---|---|---|
| Orchestration | LangGraph, MemorySaver | Postgres checkpointer |
| Retrieval | Keyword over built-in KB | Qdrant + embeddings |
| LLM | Rules only | Ollama (local) / OpenRouter (hosted) |
| Data | In-memory seed | Neon Postgres via SQLAlchemy |
| Cache/queue | None | Redis (rate limit, notifications) |
| Evaluation | Unit tests | Labelled eval set + score page |
