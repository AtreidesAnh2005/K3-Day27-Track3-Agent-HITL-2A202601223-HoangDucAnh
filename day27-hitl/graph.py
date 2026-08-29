"""LangGraph HITL workflow for churn-risk actions.

Flow: evaluate_customer -> route_action -> execute_low_risk_action
                                         -> execute_high_risk_action (interrupt_before)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from models import AuditEntry, append_audit_entry

AGENT_ID = "churn-risk-agent"
CONFIDENCE_THRESHOLD = 0.85
HIGH_RISK_ACTIONS = {"increase_credit_limit"}


class GraphState(TypedDict, total=False):
    customer_id: str
    customer_data: dict
    proposed_action: str
    action_value: Optional[float]
    confidence_score: float
    reasoning: str
    human_decision: Optional[str]
    reviewer_id: Optional[str]
    edited_action: Optional[str]
    edited_value: Optional[float]
    final_action: Optional[str]
    final_value: Optional[float]
    status: Optional[str]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_customer(state: GraphState) -> dict:
    """Agent reasoning node.

    Estimates churn risk from TOI/churn probability and proposes an action.
    A test/demo caller may inject an explicit mock LLM output via
    customer_data (proposed_action/confidence_score/reasoning/action_value)
    instead of relying on the heuristic below.
    """
    customer_data = state.get("customer_data") or {}

    if "proposed_action" in customer_data:
        return {
            "proposed_action": customer_data["proposed_action"],
            "action_value": customer_data.get("action_value"),
            "confidence_score": customer_data.get("confidence_score", 0.9),
            "reasoning": customer_data.get(
                "reasoning", "Mock LLM output provided directly by caller."
            ),
            "human_decision": None,
            "status": "proposed",
        }

    churn_probability = customer_data.get("churn_probability", 0.5)
    toi = customer_data.get("toi", 0)

    if churn_probability >= 0.7:
        proposed_action = "increase_credit_limit"
        action_value = customer_data.get("requested_credit_increase", 50_000_000)
        confidence_score = round(min(0.99, 0.75 + churn_probability * 0.25), 2)
        reasoning = (
            f"Customer has high churn probability ({churn_probability:.2f}, TOI={toi}) "
            "and increasing the credit limit may improve retention."
        )
    else:
        proposed_action = "send_email"
        action_value = None
        confidence_score = round(min(0.99, 0.6 + (1 - churn_probability) * 0.4), 2)
        reasoning = (
            f"Customer has moderate churn probability ({churn_probability:.2f}, TOI={toi}) "
            "and no high-risk financial action is required."
        )

    return {
        "proposed_action": proposed_action,
        "action_value": action_value,
        "confidence_score": confidence_score,
        "reasoning": reasoning,
        "human_decision": None,
        "status": "proposed",
    }


def route_action(state: GraphState) -> str:
    """Conditional edge: Policy Override -> Auto-Execute -> Escalate."""
    proposed_action = state["proposed_action"]
    confidence_score = state["confidence_score"]

    # Rule 1: Hard policy rule always wins, regardless of confidence.
    if proposed_action in HIGH_RISK_ACTIONS:
        return "execute_high_risk_action"

    # Rule 2: Auto-execute low-risk actions the agent is confident about.
    if confidence_score >= CONFIDENCE_THRESHOLD:
        return "execute_low_risk_action"

    # Rule 3: Escalate anything below the confidence threshold to a human.
    return "execute_high_risk_action"


def execute_low_risk_action(state: GraphState) -> dict:
    entry = AuditEntry(
        timestamp=_now(),
        agent_id=AGENT_ID,
        action=state["proposed_action"],
        confidence=state["confidence_score"],
        reviewer_id="system_auto",
        decision="auto_approved",
        action_value=state.get("action_value"),
        status="auto_executed",
    )
    append_audit_entry(entry)

    return {
        "final_action": state["proposed_action"],
        "final_value": state.get("action_value"),
        "status": "auto_executed",
    }


def execute_high_risk_action(state: GraphState) -> dict:
    """Runs only after interrupt_before pauses the graph and a human decision
    has been written into state via graph.update_state(...)."""
    decision = state.get("human_decision")
    reviewer_id = state.get("reviewer_id") or "unknown_reviewer"
    proposed_action = state["proposed_action"]
    proposed_value = state.get("action_value")

    if decision == "approve":
        final_action = proposed_action
        final_value = proposed_value
        status = "executed"
    elif decision == "edit":
        final_action = state.get("edited_action") or proposed_action
        final_value = state.get("edited_value", proposed_value)
        status = "executed_edited"
    elif decision == "reject":
        final_action = None
        final_value = None
        status = "rejected"
    else:
        # Direct invocation without a human decision yet (e.g. unit tests
        # calling the node in isolation) - do not execute anything.
        return {"status": "pending_review"}

    entry = AuditEntry(
        timestamp=_now(),
        agent_id=AGENT_ID,
        action=final_action or proposed_action,
        confidence=state["confidence_score"],
        reviewer_id=reviewer_id,
        decision=decision,
        action_value=final_value,
        status=status,
    )
    append_audit_entry(entry)

    return {
        "final_action": final_action,
        "final_value": final_value,
        "status": status,
    }


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("evaluate_customer", evaluate_customer)
    builder.add_node("execute_low_risk_action", execute_low_risk_action)
    builder.add_node("execute_high_risk_action", execute_high_risk_action)

    builder.set_entry_point("evaluate_customer")
    builder.add_conditional_edges(
        "evaluate_customer",
        route_action,
        {
            "execute_low_risk_action": "execute_low_risk_action",
            "execute_high_risk_action": "execute_high_risk_action",
        },
    )
    builder.add_edge("execute_low_risk_action", END)
    builder.add_edge("execute_high_risk_action", END)

    memory = MemorySaver()
    return builder.compile(
        checkpointer=memory,
        interrupt_before=["execute_high_risk_action"],
    )
