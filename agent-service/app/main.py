import uuid
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from langgraph.types import Command
from pydantic import BaseModel, Field

from .auth import current_user
from .graph import build_graph

app = FastAPI(title="AutoFlow AI agent service", version="0.1.0")
graph = build_graph()
OWNERS: dict[str, str] = {}  # request_id -> customer id (move to Postgres in Phase 2)


class Vehicle(BaseModel):
    make: str
    model: str
    year: int = Field(ge=1950, le=2100)
    mileage_km: int | None = Field(default=None, ge=0)


class NewRequest(BaseModel):
    text: str = Field(min_length=3, max_length=2000)
    vehicle: Vehicle


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
            "risk": v.get("risk"), "retrieval": v.get("retrieval"), "quote": v.get("quote"),
            "recommendation": v.get("recommendation"), "technician_decision": v.get("technician_decision")}


def _authorise(rid: str, user: dict) -> None:
    if rid not in OWNERS:
        raise HTTPException(404, "Request not found")
    if user["role"] != "technician" and OWNERS[rid] != user["sub"]:
        raise HTTPException(403, "Not your request")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/requests")
def create_request(body: NewRequest, user: dict = Depends(current_user)) -> dict:
    rid = uuid.uuid4().hex[:12]
    OWNERS[rid] = user["sub"]
    graph.invoke({"request_id": rid, "text": body.text.strip(), "vehicle": body.vehicle.model_dump()}, _cfg(rid))
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
