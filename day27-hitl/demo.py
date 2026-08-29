"""End-to-end CLI demo of the HITL churn-risk graph.

Drives the exact same build_graph() object app.py uses via
graph.update_state() + graph.invoke(None, config) - the identical calls
Streamlit's Approve/Edit/Reject buttons make - so this is a faithful,
browser-free reproduction of the full workflow. Runs in deterministic
heuristic mode (real OpenAI calls are skipped here) so the output is
reproducible on any machine with no API key required.

Run:
    python demo.py

Appends 5 new entries to audit_log.json (kept, since it never overwrites
prior history) demonstrating: auto-execute, hard-rule interrupt +
Approve/Reject/Edit, and confidence-based escalation.
"""
import os

os.environ.pop("OPENAI_API_KEY", None)  # force deterministic heuristic mode

from graph import build_graph  # noqa: E402


def run(graph, label: str, churn_probability: float, decision: str | None = None,
        edited_value: float | None = None) -> dict:
    config = {"configurable": {"thread_id": f"demo-{label}"}}
    graph.invoke(
        {
            "customer_id": f"CUST_DEMO_{label}",
            "customer_data": {
                "churn_probability": churn_probability,
                "toi": 15_000_000,
                "requested_credit_increase": 50_000_000,
            },
            "reviewer_id": "operator_01",
        },
        config,
    )
    snapshot = graph.get_state(config)
    state = snapshot.values
    pending = "execute_high_risk_action" in snapshot.next

    print(f"\n=== {label} (churn_probability={churn_probability}) ===")
    print(f"proposed_action={state.get('proposed_action')} confidence={state.get('confidence_score')}")
    print(f"reasoning: {state.get('reasoning')}")
    print(f"pending human review: {pending}")

    if pending:
        assert decision is not None, f"{label} interrupted but no decision was provided"
        update = {"human_decision": decision, "reviewer_id": "operator_01"}
        if decision == "edit":
            update["edited_action"] = state.get("proposed_action")
            update["edited_value"] = edited_value
        graph.update_state(config, update)
        result = graph.invoke(None, config)
    else:
        result = state
        assert decision is None, f"{label} auto-executed but a human decision was expected"

    print(f"-> status={result.get('status')} final_action={result.get('final_action')} "
          f"final_value={result.get('final_value')}")
    return result


def main() -> None:
    graph = build_graph()

    # A: low-risk, high confidence -> auto-execute, no human review at all.
    run(graph, "A_auto_execute", churn_probability=0.3)

    # B: hard policy rule (increase_credit_limit) -> interrupt -> Approve.
    run(graph, "B_approve", churn_probability=0.9, decision="approve")

    # C: hard policy rule -> interrupt -> Reject (no side effect).
    run(graph, "C_reject", churn_probability=0.9, decision="reject")

    # D: hard policy rule -> interrupt -> Edit (20,000,000 instead of 50,000,000).
    run(graph, "D_edit", churn_probability=0.9, decision="edit", edited_value=20_000_000)

    # E: low-risk action but confidence < 0.85 -> escalate anyway -> Approve.
    run(graph, "E_escalate_approve", churn_probability=0.5, decision="approve")

    print("\nDone. See audit_log.json for the full, append-only audit trail.")


if __name__ == "__main__":
    main()
