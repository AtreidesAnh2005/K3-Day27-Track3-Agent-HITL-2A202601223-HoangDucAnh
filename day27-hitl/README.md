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

API key là **tùy chọn**, không bắt buộc để pass lab — Readme_1.md 5.4 cho
phép "hardcode mock LLM output" và mọi test đều chạy offline/free (LLM
call bị mock trong `tests/`).

Nếu muốn `evaluate_customer` gọi **OpenAI thật** thay vì heuristic:

```bash
cp .env.example .env
# rồi điền OPENAI_API_KEY vào .env (đã gitignore, không bao giờ bị commit)
```

`app.py` tự load `.env` bằng `python-dotenv`. Model mặc định là
`gpt-4o-mini`, đổi bằng biến `OPENAI_MODEL` nếu muốn.

Thứ tự ưu tiên trong `evaluate_customer` (xem `graph.py`):

1. `customer_data["proposed_action"]` được set thẳng (dùng cho test/demo
   không cần mạng).
2. Có `OPENAI_API_KEY` → gọi OpenAI thật (`_llm_evaluate`), model phải trả
   JSON với `proposed_action`/`confidence_score`/`reasoning`.
3. Không có key, hoặc gọi API lỗi (mạng/auth/JSON không hợp lệ) → fallback
   an toàn về heuristic rule-based, **không crash**.

Dù dùng LLM thật hay không, **hard rule luôn thắng**: nếu model tự đề
xuất `increase_credit_limit` với confidence 0.99, `route_action` vẫn bắt
buộc human review — đã verify bằng smoke test thật với `gpt-4o-mini`.

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

14 test bao phủ: agent reasoning output hợp lệ, việc dùng kết quả LLM khi
có (mocked, không gọi API thật) và fallback khi không có key, hard rule
(policy override luôn thắng confidence), auto-execute, escalation do
confidence thấp, toàn bộ luồng interrupt → approve/edit/reject → resume →
audit log (bao gồm việc action tuyệt đối không chạy trước khi có quyết
định của con người, audit log không bị ghi đè, giá trị edit được ghi
đúng), cùng 2 test lỗi cơ bản (decision không hợp lệ, resume một thread
đã xong hai lần). Toàn bộ test chạy offline/free dù `.env` có key thật
hay không.

## Reflection

Trả lời 3 Reflection Questions (Readme_1.md mục 12) ở
[`REFLECTION.md`](REFLECTION.md).

## Project structure

```text
day27-hitl/
├── app.py             # Streamlit human approval interface
├── graph.py            # GraphState, agent node (heuristic + OpenAI), routing, graph compile
├── models.py            # AuditEntry (pydantic) + audit log helpers
├── audit_log.json        # append-only audit trail
├── requirements.txt
├── .env.example          # OPENAI_API_KEY / OPENAI_MODEL template
└── tests/
    └── test_graph.py     # HITL scenario tests (LLM always mocked)
```
