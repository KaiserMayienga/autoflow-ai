"""LangGraph orchestration: the 7 pipeline steps plus clarification and technician interrupts.

  parse -> vehicle_context -> [clarify?] -> risk -> retrieve -> decide -> tools -> recommend
        -> [technician_review (loops on more_info)?] -> END

Interrupts pause the run and persist state via the checkpointer. MemorySaver loses state on
restart; switch to a Postgres checkpointer (langgraph-checkpoint-postgres) before production."""
import operator
from typing import Annotated, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import kb, quote, rules
from .rag import KeywordRetriever, Retriever
from .repo import InMemoryRepo, VehicleRepo


class AgentState(TypedDict, total=False):
    request_id: str
    text: str
    norm_text: str
    vehicle: dict
    prices: dict
    provided_history: list[str]
    hits: list[dict]
    symptoms: list[str]
    history: list[dict]
    questions: list[dict]
    answers: dict
    risk: dict
    retrieval: list[dict]
    actions: list[str]
    quote: dict
    recommendation: dict
    technician_decision: dict
    status: str
    trace: Annotated[list[dict], operator.add]


def _t(name: str, detail: str) -> list[dict]:
    return [{"name": name, "detail": detail}]


def build_graph(retriever: Retriever | None = None, repo: VehicleRepo | None = None, checkpointer=None):
    retriever = retriever or KeywordRetriever()
    repo = repo or InMemoryRepo()

    def parse(s: AgentState) -> dict:
        t = kb.norm(s["text"])
        hits = [{"id": e.id, "title": e.title, "doc": e.doc, "risk": e.risk} for e in kb.match(t)]
        syms = rules.find_symptoms(s["text"])
        extra = f"; symptoms: {', '.join(syms)}" if syms else ""
        return {"norm_text": t, "hits": hits, "symptoms": syms,
                "trace": _t("Request Parser", f"Parsed {len(t.split(' '))} words{extra}")}

    def vehicle_context(s: AgentState) -> dict:
        v = s["vehicle"]
        if "provided_history" in s:  # the web app passes the real service history from Neon
            h = [{"work": n} for n in s["provided_history"]]
        else:
            h = repo.history(v)
        label = v.get("name") or f"{v.get('make', '?')} {v.get('model', '?')} {v.get('year', '')}".strip()
        return {"history": h, "trace": _t("Vehicle Context", f"{label}; {len(h)} service history records loaded")}

    def route_after_context(s: AgentState) -> str:
        if s.get("answers"):
            return "risk"
        return "clarify" if rules.questions_for([h["id"] for h in s["hits"]], s["symptoms"]) else "risk"

    def clarify(s: AgentState) -> dict:
        qs = rules.questions_for([h["id"] for h in s["hits"]], s["symptoms"])
        answers = interrupt({"type": "clarification", "questions": qs})
        return {"questions": qs, "answers": answers,
                "trace": _t("Clarification", f"Asked {len(qs)} questions; customer answered")}

    def risk(s: AgentState) -> dict:
        r = rules.assess_risk(s["hits"], s["symptoms"], s.get("answers"), s["vehicle"].get("kind"), s["norm_text"])
        detail = f"Risk {r.level}, confidence {r.confidence}%" + (f", escalation: {r.reason}" if r.escalate else "")
        return {"risk": {"level": r.level, "confidence": r.confidence, "escalate": r.escalate, "reason": r.reason,
                         "reasons": r.reasons, "severe": r.severe},
                "trace": _t("Risk Assessment", detail)}

    def retrieve(s: AgentState) -> dict:
        passages = retriever.search(s["text"], [h["id"] for h in s["hits"]])
        docs = ", ".join(h["doc"] for h in s["hits"]) or "No relevant documents"
        return {"retrieval": passages, "trace": _t("Knowledge Retrieval", f"Matched: {docs}" if s["hits"] else docs)}

    def decide(s: AgentState) -> dict:
        ids = [h["id"] for h in s["hits"]]
        return {"actions": ids, "trace": _t("Agent Decision", f"Actions: {', '.join(ids)}" if ids else "Route to technician")}

    def tools(s: AgentState) -> dict:
        q = quote.quote_for_hits(s["actions"], s.get("prices"))
        n = len(q["parts"])
        extra = "; range pending inspection" if "range" in q else ""
        return {"quote": q, "trace": _t("Controlled Tool Execution", f"Parts lookup ({n}), quotation engine run{extra}")}

    def recommend(s: AgentState) -> dict:
        r = s["risk"]
        if r["severe"]:
            msg = "Based on what you described, please avoid driving the vehicle until a technician has inspected it."
        elif r["escalate"]:
            msg = "A qualified technician will review your request before any work is booked."
        else:
            msg = "Your request looks routine. An appointment will be booked for you."
        top = s["retrieval"][0] if s.get("retrieval") else None
        rec = {"summary": f"Preliminary assessment for: {s['text']}", "customer_message": msg,
               "advise_not_to_drive": r["severe"], "top_source": top["source"] if top else None}
        return {"recommendation": rec, "status": "pending_technician" if r["escalate"] else "ready_to_book",
                "trace": _t("Recommendation Builder", "Prepared for technician review" if r["escalate"] else "Ready for booking")}

    def route_after_recommend(s: AgentState) -> str:
        return "technician_review" if s["risk"]["escalate"] else END

    def technician_review(s: AgentState) -> dict:
        d = interrupt({"type": "technician_review", "recommendation": s["recommendation"],
                       "risk": s["risk"], "quote": s["quote"], "hits": s["hits"]})
        mapping = {"approve": "approved", "reject": "rejected", "more_info": "needs_info"}
        return {"technician_decision": d, "status": mapping.get(d.get("action"), "needs_info"),
                "trace": _t("Technician Review", f"{d.get('action')}: {d.get('note', '')}".strip())}

    def route_after_review(s: AgentState) -> str:
        # More information requested: stay open so the technician can decide again, as the web app allows.
        return "technician_review" if s["technician_decision"].get("action") == "more_info" else END

    g = StateGraph(AgentState)
    for name, fn in [("parse", parse), ("vehicle_context", vehicle_context), ("clarify", clarify), ("risk", risk),
                     ("retrieve", retrieve), ("decide", decide), ("tools", tools), ("recommend", recommend),
                     ("technician_review", technician_review)]:
        g.add_node(name, fn)
    g.add_edge(START, "parse")
    g.add_edge("parse", "vehicle_context")
    g.add_conditional_edges("vehicle_context", route_after_context, {"clarify": "clarify", "risk": "risk"})
    g.add_edge("clarify", "risk")
    for a, b in [("risk", "retrieve"), ("retrieve", "decide"), ("decide", "tools"), ("tools", "recommend")]:
        g.add_edge(a, b)
    g.add_conditional_edges("recommend", route_after_recommend, {"technician_review": "technician_review", END: END})
    g.add_conditional_edges("technician_review", route_after_review, {"technician_review": "technician_review", END: END})
    return g.compile(checkpointer=checkpointer or MemorySaver())
