import uuid
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, Field

from .auth import current_user
from .graph import build_graph
from .store import make_checkpointer

_saver, _pool = make_checkpointer()
graph = build_graph(checkpointer=_saver)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    if _pool is not None:
        _pool.close()


app = FastAPI(title="AutoFlow AI agent service", version="0.2.0", lifespan=lifespan)


class Vehicle(BaseModel):
    id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, max_length=120)
    kind: str | None = Field(default=None, max_length=30)  # e.g. "ev"
    make: str | None = Field(default=None, max_length=60)
    model: str | None = Field(default=None, max_length=60)
    year: int | None = Field(default=None, ge=1950, le=2100)
    mileage_km: int | None = Field(default=None, ge=0)


class Price(BaseModel):
    name: str = Field(max_length=120)
    cents: int = Field(ge=0, le=100_000_000)


class NewRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    vehicle: Vehicle
    history: list[str] | None = Field(default=None, max_length=50)
    prices: dict[str, Price] | None = Field(default=None, max_length=200)  # live prices from the web app's database


class Clarification(BaseModel):
    answers: dict[str, str]


class TechnicianDecision(BaseModel):
    action: Literal["approve", "reject", "more_info"]
    note: str = Field(default="", max_length=1000)


def _cfg(rid: str) -> dict:
    return {"configurable": {"thread_id": rid}}


def _view(rid: str) -> dict:
    snap = graph.get_state(_cfg(rid))
    if not snap.values:
        raise HTTPException(404, "Request not found")
    awaiting = None
    for task in snap.tasks:
        if task.interrupts:
            awaiting = task.interrupts[0].value
    v = snap.values
    return {"request_id": rid, "status": v.get("status", "in_progress") if not awaiting else
            ("needs_clarification" if awaiting["type"] == "clarification" else "pending_technician"),
            "awaiting": awaiting,
            "text": v.get("text"), "vehicle": v.get("vehicle"), "hits": v.get("hits"),
            "risk": v.get("risk"), "retrieval": v.get("retrieval"), "quote": v.get("quote"),
            "recommendation": v.get("recommendation"), "technician_decision": v.get("technician_decision"),
            "trace": [{"step": i + 1, **t} for i, t in enumerate(v.get("trace", []))]}


def _authorise(rid: str, user: dict) -> None:
    """The owner lives in the stored run state, so access checks survive restarts."""
    values = graph.get_state(_cfg(rid)).values
    if not values:
        raise HTTPException(404, "Request not found")
    if user["role"] != "technician" and values.get("owner") != user["sub"]:
        raise HTTPException(403, "Not your request")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/requests")
def create_request(body: NewRequest, user: dict = Depends(current_user)) -> dict:
    rid = uuid.uuid4().hex[:12]
    state = {"request_id": rid, "owner": user["sub"], "text": body.text.strip(), "vehicle": body.vehicle.model_dump()}
    if body.history is not None:
        state["provided_history"] = body.history
    if body.prices is not None:
        state["prices"] = {k: v.model_dump() for k, v in body.prices.items()}
    graph.invoke(state, _cfg(rid))
    return _view(rid)


@app.post("/requests/{rid}/clarify")
def clarify(rid: str, body: Clarification, user: dict = Depends(current_user)) -> dict:
    _authorise(rid, user)
    if _view(rid)["status"] != "needs_clarification":
        raise HTTPException(409, "Request is not waiting for clarification")
    graph.invoke(Command(resume=body.answers), _cfg(rid))
    return _view(rid)


@app.post("/requests/{rid}/resume")
def technician_resume(rid: str, body: TechnicianDecision, user: dict = Depends(current_user)) -> dict:
    if user["role"] != "technician":
        raise HTTPException(403, "Technicians only")
    _authorise(rid, user)
    if _view(rid)["status"] != "pending_technician":
        raise HTTPException(409, "Request is not waiting for technician review")
    graph.invoke(Command(resume=body.model_dump()), _cfg(rid))
    return _view(rid)


@app.get("/requests/{rid}")
def get_request(rid: str, user: dict = Depends(current_user)) -> dict:
    _authorise(rid, user)
    return _view(rid)


@app.get("/requests/{rid}/trace")
def get_trace(rid: str, user: dict = Depends(current_user)) -> dict:
    _authorise(rid, user)
    snap = graph.get_state(_cfg(rid))
    return {"request_id": rid, "trace": [{"step": i + 1, **t} for i, t in enumerate(snap.values.get("trace", []))]}
