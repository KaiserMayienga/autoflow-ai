"""LangGraph orchestration: 7 pipeline steps + clarification and technician interrupts.

Flow:
  parse -> vehicle_context -> [clarify?] -> risk -> retrieve -> decide -> tools
        -> recommend -> [technician_review?] -> END
Interrupts pause the run and persist state via the checkpointer. In production use
a Postgres checkpointer (langgraph-checkpoint-postgres) so runs survive restarts.
"""
import operator
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from . import quote, rules
from .rag import KeywordRetriever, Retriever
from .repo import InMemoryRepo, VehicleRepo


class AgentState(TypedDict, total=False):
    request_id: str
    text: str
    vehicle: dict
    categories: list[str]
    symptoms: list[str]
    history: list[dict]
    questions: list[dict]
    answers: dict
    risk: dict
    retrieval: list[dict]
    actions: list[str]
    quote: dict
    parts: list[str]
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
        cats, syms = rules.find_categories(s["text"]), rules.find_symptoms(s["text"])
        n = len(s["text"].split())
        return {"categories": cats, "symptoms": syms,
                "trace": _t("Request Parser", f"Parsed {n} words; components={cats or 'none'}; symptoms={syms or 'none'}")}

    def vehicle_context(s: AgentState) -> dict:
        v, h = s["vehicle"], repo.history(s["vehicle"])
        label = f"{v.get('make', '?')} {v.get('model', '?')} {v.get('year', '')}".strip()
        return {"history": h, "trace": _t("Vehicle Context", f"{label}; {len(h)} service history records loaded")}

    def needs_clarification(s: AgentState) -> str:
        if s.get("answers"):
            return "risk"
        return "clarify" if rules.questions_for(s["categories"], s["symptoms"]) else "risk"

    def clarify(s: AgentState) -> dict:
        qs = rules.questions_for(s["categories"], s["symptoms"])
        answers = interrupt({"type": "clarification", "questions": qs})
        return {"questions": qs, "answers": answers,
                "trace": _t("Clarification", f"Asked {len(qs)} questions; customer answered")}

    def risk(s: AgentState) -> dict:
        r = rules.assess_risk(s["categories"], s["symptoms"], s.get("answers"))
        return {"risk": {"level": r.level, "confidence": r.confidence, "escalate": r.escalate, "reasons": r.reasons},
                "trace": _t("Risk Assessment", f"Risk {r.level}, confidence {r.confidence}%, escalate={r.escalate}. " + " | ".join(r.reasons))}

    def retrieve(s: AgentState) -> dict:
        hits = retriever.search(s["text"], s["categories"])
        names = ", ".join(f"{h['source']} §{h['section']}" for h in hits) or "no match"
        return {"retrieval": hits, "trace": _t("Knowledge Retrieval", f"Matched: {names}")}

    def decide(s: AgentState) -> dict:
        actions = [c for c in s["categories"] if c != "noise_unknown"] or ["diagnostic"]
        if "noise_unknown" in s["categories"] and len(s["categories"]) == 1:
            actions = ["diagnostic"]
        return {"actions": actions, "trace": _t("Agent Decision", f"Actions: {', '.join(actions)}")}

    def tools(s: AgentState) -> dict:
        a = s["actions"]
        if "brakes" in a:
            q, parts = quote.brake_inspection_quote(), ["brake_pad_set", "rotor_pair"]
        elif "service" in a:
            q, parts = quote.fixed_quote("Oil service", ["oil_filter_kit"], 10), ["oil_filter_kit"]
        elif "upgrade_electrical" in a:
            q, parts = quote.fixed_quote("LED headlights and dashcam", ["led_headlight_kit", "dashcam_kit"], 20), ["led_headlight_kit", "dashcam_kit"]
        else:
            q, parts = quote.fixed_quote("Diagnostic inspection", [], 10), []
        return {"quote": q, "parts": parts,
                "trace": _t("Controlled Tool Execution", f"Parts lookup ({len(parts)}), quotation engine run ({q['type']})")}

    def recommend(s: AgentState) -> dict:
        r = s["risk"]
        severe = r["level"] == "high" and any(
            "Severe symptom" in x for x in r["reasons"])
        if severe:
            msg = "Based on what you described, please avoid driving the vehicle until a technician has inspected it."
        elif r["escalate"]:
            msg = "A qualified technician will review your request before any work is booked."
        else:
            msg = "Your request looks routine. You can approve the estimate and choose a slot."
        top = s["retrieval"][0] if s.get("retrieval") else None
        rec = {"summary": f"Preliminary assessment for: {s['text']}", "customer_message": msg,
               "advise_not_to_drive": severe, "top_source": top["source"] if top else None}
        status = "pending_technician" if r["escalate"] else "ready_to_book"
        return {"recommendation": rec, "status": status,
                "trace": _t("Recommendation Builder", "Prepared for technician review" if r["escalate"] else "Ready to book")}

    def route_after_recommend(s: AgentState) -> str:
        return "technician_review" if s["risk"]["escalate"] else END

    def technician_review(s: AgentState) -> dict:
        d = interrupt({"type": "technician_review", "recommendation": s["recommendation"],
                       "risk": s["risk"], "quote": s["quote"], "retrieval": s["retrieval"]})
        mapping = {"approve": "approved", "reject": "rejected", "more_info": "needs_info"}
        status = mapping.get(d.get("action"), "needs_info")
        return {"technician_decision": d, "status": status,
                "trace": _t("Technician Review", f"{d.get('action')}: {d.get('note', '')}".strip())}

    g = StateGraph(AgentState)
    for name, fn in [("parse", parse), ("vehicle_context", vehicle_context), ("clarify", clarify), ("risk", risk),
                     ("retrieve", retrieve), ("decide", decide), ("tools", tools), ("recommend", recommend),
                     ("technician_review", technician_review)]:
        g.add_node(name, fn)
    g.add_edge(START, "parse")
    g.add_edge("parse", "vehicle_context")
    g.add_conditional_edges("vehicle_context", needs_clarification, {"clarify": "clarify", "risk": "risk"})
    g.add_edge("clarify", "risk")
    for a, b in [("risk", "retrieve"), ("retrieve", "decide"), ("decide", "tools"), ("tools", "recommend")]:
        g.add_edge(a, b)
    g.add_conditional_edges("recommend", route_after_recommend, {"technician_review": "technician_review", END: END})
    g.add_edge("technician_review", END)
    return g.compile(checkpointer=checkpointer or MemorySaver())
