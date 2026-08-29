"""Scenario tests for the HITL churn-risk graph.

Covers: agent reasoning output, hard-rule policy override, confidence
auto-execute, escalation on low confidence, and the full interrupt ->
approve / edit / reject -> resume -> audit-log flow.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models  # noqa: E402
from graph import build_graph, evaluate_customer, route_action  # noqa: E402


def make_state(**overrides):
    base = {
        "customer_id": "CUST_TEST",
        "customer_data": {},
        "proposed_action": "send_email",
        "action_value": None,
        "confidence_score": 0.9,
        "reasoning": "test",
        "human_decision": None,
        "reviewer_id": None,
    }
    base.update(overrides)
    return base


def use_temp_audit_log(monkeypatch, tmp_path):
    log_path = str(tmp_path / "audit_log.json")
    monkeypatch.setattr(models, "AUDIT_LOG_PATH", log_path)
    return log_path


# ---------------------------------------------------------------------------
# Agent reasoning
# ---------------------------------------------------------------------------

def test_evaluate_customer_returns_required_fields():
    state = make_state(customer_data={"churn_probability": 0.4})
    result = evaluate_customer(state)
    assert "proposed_action" in result
    assert "confidence_score" in result
    assert "reasoning" in result
    assert 0.0 <= result["confidence_score"] <= 1.0


def test_evaluate_customer_high_churn_proposes_credit_increase():
    state = make_state(customer_data={"churn_probability": 0.9})
    result = evaluate_customer(state)
    assert result["proposed_action"] == "increase_credit_limit"


# ---------------------------------------------------------------------------
# Routing rules
# ---------------------------------------------------------------------------

def test_hard_rule_overrides_high_confidence():
    """increase_credit_limit must always go to human review, even at 0.99."""
    state = make_state(proposed_action="increase_credit_limit", confidence_score=0.99)
    assert route_action(state) == "execute_high_risk_action"


def test_auto_execute_low_risk_high_confidence():
    state = make_state(proposed_action="send_email", confidence_score=0.90)
    assert route_action(state) == "execute_low_risk_action"


def test_escalate_low_confidence_low_risk_action():
    state = make_state(proposed_action="send_email", confidence_score=0.82)
    assert route_action(state) == "execute_high_risk_action"


# ---------------------------------------------------------------------------
# End-to-end scenarios
# ---------------------------------------------------------------------------

def test_scenario_no_hitl_auto_execute(tmp_path, monkeypatch):
    use_temp_audit_log(monkeypatch, tmp_path)
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-auto"}}

    result = graph.invoke(
        {
            "customer_id": "CUST001",
            "customer_data": {
                "proposed_action": "send_email",
                "confidence_score": 0.92,
                "reasoning": "low churn risk",
            },
            "reviewer_id": "operator_01",
        },
        config,
    )

    assert result["status"] == "auto_executed"
    assert result["final_action"] == "send_email"
    assert graph.get_state(config).next == ()

    entries = models.read_audit_log()
    assert any(e["decision"] == "auto_approved" for e in entries)


def test_scenario_high_risk_interrupts_then_approve(tmp_path, monkeypatch):
    use_temp_audit_log(monkeypatch, tmp_path)
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-approve"}}

    graph.invoke(
        {
            "customer_id": "CUST002",
            "customer_data": {
                "proposed_action": "increase_credit_limit",
                "confidence_score": 0.99,
                "reasoning": "high churn risk",
                "action_value": 50_000_000,
            },
            "reviewer_id": "operator_01",
        },
        config,
    )

    snapshot = graph.get_state(config)
    assert "execute_high_risk_action" in snapshot.next, "must interrupt before high-risk action"
    assert snapshot.values.get("status") != "executed", "action must not run before approval"

    graph.update_state(config, {"human_decision": "approve", "reviewer_id": "operator_01"})
    result = graph.invoke(None, config)

    assert result["status"] == "executed"
    assert result["final_action"] == "increase_credit_limit"
    assert result["final_value"] == 50_000_000

    entries = models.read_audit_log()
    assert any(e["decision"] == "approve" and e["action"] == "increase_credit_limit" for e in entries)


def test_scenario_reject_blocks_side_effect(tmp_path, monkeypatch):
    use_temp_audit_log(monkeypatch, tmp_path)
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-reject"}}

    graph.invoke(
        {
            "customer_id": "CUST003",
            "customer_data": {
                "proposed_action": "increase_credit_limit",
                "confidence_score": 0.95,
                "reasoning": "high churn risk",
                "action_value": 50_000_000,
            },
            "reviewer_id": "operator_01",
        },
        config,
    )

    graph.update_state(config, {"human_decision": "reject", "reviewer_id": "operator_01"})
    result = graph.invoke(None, config)

    assert result["status"] == "rejected"
    assert result["final_action"] is None

    entries = models.read_audit_log()
    assert any(e["decision"] == "reject" for e in entries)


def test_scenario_edit_executes_edited_value(tmp_path, monkeypatch):
    use_temp_audit_log(monkeypatch, tmp_path)
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-edit"}}

    graph.invoke(
        {
            "customer_id": "CUST004",
            "customer_data": {
                "proposed_action": "increase_credit_limit",
                "confidence_score": 0.95,
                "reasoning": "high churn risk",
                "action_value": 50_000_000,
            },
            "reviewer_id": "operator_01",
        },
        config,
    )

    graph.update_state(
        config,
        {
            "human_decision": "edit",
            "reviewer_id": "operator_01",
            "edited_action": "increase_credit_limit",
            "edited_value": 20_000_000,
        },
    )
    result = graph.invoke(None, config)

    assert result["status"] == "executed_edited"
    assert result["final_value"] == 20_000_000, "must execute the edited value, not the original"

    entries = models.read_audit_log()
    assert any(e["decision"] == "edit" for e in entries)


def test_scenario_audit_log_never_overwrites_history(tmp_path, monkeypatch):
    use_temp_audit_log(monkeypatch, tmp_path)
    graph = build_graph()

    for i, decision in enumerate(["approve", "reject"]):
        config = {"configurable": {"thread_id": f"test-history-{i}"}}
        graph.invoke(
            {
                "customer_id": f"CUST_{i}",
                "customer_data": {
                    "proposed_action": "increase_credit_limit",
                    "confidence_score": 0.9,
                    "reasoning": "test",
                    "action_value": 10_000_000,
                },
                "reviewer_id": "operator_01",
            },
            config,
        )
        graph.update_state(config, {"human_decision": decision, "reviewer_id": "operator_01"})
        graph.invoke(None, config)

    entries = models.read_audit_log()
    assert len(entries) == 2, "each decision must append, not overwrite, prior entries"
