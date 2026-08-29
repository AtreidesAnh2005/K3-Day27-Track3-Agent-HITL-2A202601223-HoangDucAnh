# Day 27 — Agent Human-in-the-Loop (HITL): Churn Risk Workflow

LangGraph workflow đánh giá churn risk của khách hàng và đề xuất action.
Action rủi ro cao (`increase_credit_limit`) hoặc confidence thấp (< 0.85)
sẽ **luôn dừng lại** để con người review trước khi thực thi. Xem
[`../Readme_1.md`](../Readme_1.md) và [`../exercise.md`](../exercise.md)
để biết đầy đủ yêu cầu lab.

## HITL flow

```text
Agent proposes action (evaluate_customer)
        -> route_action (hard rule -> confidence threshold)
                -> low-risk & confidence >= 0.85 : auto execute
                -> increase_credit_limit OR confidence < 0.85 : INTERRUPT
                        -> Streamlit: Approve / Edit / Reject
                        -> graph.update_state(...) + graph.invoke(None, config)
                        -> resume -> execute/abort -> audit_log.json
```

## 1. Install

```bash
cd day27-hitl
python -m pip install -r requirements.txt
```

Yêu cầu Python 3.10+.

## 2. Environment variables

Không cần API key — `evaluate_customer` dùng mock/heuristic thay cho gọi
LLM thật, để phần HITL luôn demo/test được mà không phụ thuộc dịch vụ bên
ngoài.

## 3. Start application

```bash
streamlit run app.py
```

Mở trình duyệt tại URL Streamlit in ra (mặc định `http://localhost:8501`).

## 4. Run HITL demo

1. Trong sidebar, nhập `Customer ID`, kéo `Churn probability`, rồi bấm
   **Run Agent Evaluation**.
   - `Churn probability >= 0.7` → agent đề xuất `increase_credit_limit`
     (luôn bị chặn lại để human review, bất kể confidence).
   - `Churn probability < 0.7` → agent đề xuất `send_email`. Nếu confidence
     tính được `>= 0.85` thì auto-execute ngay; nếu thấp hơn thì vẫn bị
     escalate lên human review.
2. Khi workflow dừng ("Human Decision" xuất hiện), chọn một trong ba nút:
   - **Approve** — thực thi đúng action agent đề xuất.
   - **Edit & Approve** — sửa `Edited value` rồi thực thi giá trị đã sửa.
   - **Reject** — không thực thi gì cả.
3. Xem **Audit Trail** ở cuối trang — mỗi quyết định (kể cả auto-execute)
   được append vào `audit_log.json`, không bao giờ ghi đè lịch sử cũ.

## 5. Run tests

```bash
python -m pytest tests/ -v
```

10 test bao phủ: agent reasoning output hợp lệ, hard rule (policy
override luôn thắng confidence), auto-execute, escalation do confidence
thấp, và toàn bộ luồng interrupt → approve/edit/reject → resume → audit
log (bao gồm việc action tuyệt đối không chạy trước khi có quyết định của
con người, và audit log không bị ghi đè).

## Project structure

```text
day27-hitl/
├── app.py             # Streamlit human approval interface
├── graph.py            # GraphState, agent node, routing, graph compile
├── models.py            # AuditEntry (pydantic) + audit log helpers
├── audit_log.json        # append-only audit trail
├── requirements.txt
└── tests/
    └── test_graph.py     # HITL scenario tests
```
