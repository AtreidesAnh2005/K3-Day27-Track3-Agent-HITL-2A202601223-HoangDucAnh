"""Streamlit Human Approval Interface for the churn-risk HITL agent."""
import time

import streamlit as st

from graph import build_graph
from models import read_audit_log

st.set_page_config(page_title="HITL Approval Dashboard", layout="centered")

if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
if "config" not in st.session_state:
    st.session_state.config = None

graph = st.session_state.graph

st.title("HITL Approval Dashboard")
st.caption("Churn-risk agent — proposals for high-risk / low-confidence actions pause here for human review.")

with st.sidebar:
    st.header("New Customer Evaluation")
    customer_id = st.text_input("Customer ID", value="CUST001")
    churn_probability = st.slider("Churn probability", 0.0, 1.0, 0.75, 0.01)
    toi = st.number_input("Total Operating Income (TOI)", value=15_000_000, step=1_000_000)
    requested_credit_increase = st.number_input(
        "Requested credit increase (if high risk)", value=50_000_000, step=1_000_000
    )
    reviewer_id = st.text_input("Reviewer ID", value="operator_01")

    if st.button("Run Agent Evaluation", type="primary"):
        thread_id = f"{customer_id}-{int(time.time())}"
        config = {"configurable": {"thread_id": thread_id}}
        graph.invoke(
            {
                "customer_id": customer_id,
                "customer_data": {
                    "churn_probability": churn_probability,
                    "toi": toi,
                    "requested_credit_increase": requested_credit_increase,
                },
                "reviewer_id": reviewer_id,
            },
            config,
        )
        st.session_state.config = config
        st.rerun()

st.header("Customer Information")

if st.session_state.config is None:
    st.info("Chưa có evaluation nào. Nhập thông tin ở sidebar và bấm **Run Agent Evaluation**.")
else:
    config = st.session_state.config
    snapshot = graph.get_state(config)
    state = snapshot.values

    st.write(f"**Customer ID:** {state.get('customer_id')}")

    st.header("Agent Proposal")
    st.write(f"**Proposed Action:** `{state.get('proposed_action')}`")
    if state.get("action_value") is not None:
        st.write(f"**Action Value:** {state.get('action_value'):,}")
    st.write(f"**Confidence:** {state.get('confidence_score')}")
    st.write(f"**Reasoning:** {state.get('reasoning')}")

    is_pending = "execute_high_risk_action" in snapshot.next

    if is_pending:
        st.header("Human Decision")
        st.warning("Hành động này rủi ro cao hoặc confidence thấp — cần con người review trước khi thực thi.")

        edited_value = st.number_input(
            "Edited value (dùng cho Edit)",
            value=float(state.get("action_value") or 0),
            step=1_000_000.0,
            key="edited_value_input",
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Approve"):
                graph.update_state(config, {"human_decision": "approve", "reviewer_id": reviewer_id})
                graph.invoke(None, config)
                st.rerun()
        with col2:
            if st.button("Edit & Approve"):
                graph.update_state(
                    config,
                    {
                        "human_decision": "edit",
                        "reviewer_id": reviewer_id,
                        "edited_action": state.get("proposed_action"),
                        "edited_value": edited_value,
                    },
                )
                graph.invoke(None, config)
                st.rerun()
        with col3:
            if st.button("Reject"):
                graph.update_state(config, {"human_decision": "reject", "reviewer_id": reviewer_id})
                graph.invoke(None, config)
                st.rerun()
    else:
        status = state.get("status")
        if status == "rejected":
            st.error("Reviewer đã **Reject** — action không được thực thi.")
        else:
            st.success(f"Workflow đã hoàn tất — status: `{status}`")
        st.write(f"**Final Action:** {state.get('final_action')}")
        if state.get("final_value") is not None:
            st.write(f"**Final Value:** {state.get('final_value'):,}")

st.header("Audit Trail")
entries = read_audit_log()
if entries:
    st.dataframe(list(reversed(entries)), use_container_width=True)
else:
    st.write("Chưa có audit entries.")
