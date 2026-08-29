# Lab 27 — Xây dựng hệ thống Agent Human-in-the-Loop (HITL)

## 1. Tổng quan Lab

### 1.1. Mục tiêu

Trong bài Lab này, chúng ta xây dựng một workflow sử dụng **LangGraph** để đánh giá **churn risk** của khách hàng.

Điểm quan trọng nhất không phải xây dựng hệ thống nghiệp vụ hoàn chỉnh, mà là hiểu được mô hình **Human-in-the-Loop (HITL)**:

```text
Customer Data
      ↓
Agent Reasoning
      ↓
Proposed Action
+ Confidence Score
+ Reasoning
      ↓
Policy + Confidence Routing
      ↓
 ┌───────────────┬─────────────────┐
 ↓               ↓
Low Risk       High Risk
 ↓               ↓
Auto Execute   Human Review
                  ↓
          Approve / Reject / Edit
                  ↓
             Resume Graph
                  ↓
              Audit Log
```

Workflow cần đảm bảo rằng **agent không được tự động thực hiện những hành động có rủi ro cao**. Những action này phải được chuyển cho con người kiểm tra trước khi thực thi.

---

## 2. Thuật ngữ và kiến thức cần biết

| Thuật ngữ | Bản chất khái niệm | Minh họa |
|---|---|---|
| **Human-in-the-Loop (HITL)** | Kiến trúc trong đó AI không được tự thực hiện mọi hành động mà phải chuyển một số quyết định cho con người kiểm tra trước khi tiếp tục. | Agent đề xuất tăng hạn mức tín dụng nhưng workflow dừng lại để nhân viên Approve hoặc Reject. |
| **LangGraph** | Framework xây workflow dạng graph cho agent, cho phép quản lý state, routing, checkpoint và tạm dừng/resume execution. | Customer data đi qua các node đánh giá → routing → human review → execution. |
| **GraphState** | Trạng thái dùng chung được truyền qua các node trong graph và lưu thông tin cần thiết của workflow. | Lưu `customer_id`, `proposed_action`, `confidence_score`, `reasoning`, `human_decision`. |
| **TypedDict** | Cách khai báo cấu trúc dictionary có kiểu dữ liệu rõ ràng trong Python. | Dùng để mô tả chính xác các field tồn tại trong `GraphState`. |
| **AuditEntry** | Schema đại diện cho một bản ghi audit để biết agent đã đề xuất gì, confidence bao nhiêu và con người quyết định thế nào. | Record có `timestamp`, `agent_id`, `action`, `confidence`, `reviewer_id`, `decision`. |
| **Confidence Score** | Điểm thể hiện mức độ tự tin của agent đối với quyết định của mình, thường nằm từ 0.0 đến 1.0. | `0.92` có thể auto-execute low-risk action, còn `0.72` phải human review. |
| **Confidence Routing** | Cơ chế dùng confidence score để quyết định workflow đi sang nhánh nào. | Confidence >= 0.85 và action low-risk → auto execute. |
| **Hard Rule** | Quy tắc cứng có độ ưu tiên cao hơn confidence của agent. | `increase_credit_limit` luôn phải human review dù confidence là 0.99. |
| **Policy Override** | Trường hợp policy cưỡng chế route, không cho confidence của agent quyết định. | Action tăng hạn mức luôn đi tới high-risk path. |
| **MemorySaver** | Checkpointer của LangGraph dùng để lưu state để workflow có thể tạm dừng và tiếp tục sau đó. | Graph dừng trước high-risk action nhưng customer data không bị mất khi chờ review. |
| **interrupt_before** | Cấu hình yêu cầu LangGraph dừng trước khi chạy một node cụ thể. | `interrupt_before=["execute_high_risk_action"]` dừng graph trước action nguy hiểm. |
| **Pending State** | Trạng thái workflow đang tạm dừng để chờ quyết định từ bên ngoài. | Streamlit lấy pending state và hiển thị proposed action cho reviewer. |
| **Audit Trail** | Nhật ký bất biến hoặc có thể kiểm toán về các quyết định và hành động đã diễn ra trong workflow. | Ghi agent đề xuất gì, confidence bao nhiêu, ai review và quyết định cuối cùng. |
| **Approve** | Human reviewer đồng ý với proposed action và cho workflow tiếp tục. | Cho phép thực hiện `increase_credit_limit`. |
| **Reject** | Human reviewer từ chối proposed action và yêu cầu workflow hủy hành động. | Không thực hiện thay đổi hạn mức tín dụng. |
| **Edit** | Human reviewer sửa proposed action trước khi workflow tiếp tục. | Agent đề xuất tăng 50 triệu, reviewer sửa thành tăng 20 triệu rồi approve. |

> **Nguyên tắc quan trọng:** Confidence cao không đồng nghĩa với việc agent được phép bypass policy.

---

## 3. Mục tiêu & đầu ra

Bạn hoàn thành khi xây dựng được một LangGraph workflow đánh giá rủi ro khách hàng rời bỏ (**churn risk**) và xử lý hành động bằng cơ chế Human-in-the-Loop.

Workflow cần thực hiện được toàn bộ luồng:

```text
Customer Data
      |
      v
Agent Reasoning
      |
      | proposed_action
      | confidence_score
      | reasoning
      v
Confidence Routing + Hard Rules
      |
      +-----------------------------+
      |                             |
      | Low-risk                    | High-risk / cần review
      v                             v
Auto Execute                  Interrupt Graph
                                    |
                                    v
                             Streamlit Review
                              /      |      \
                         Approve   Reject    Edit
                            |        |        |
                            +--------+--------+
                                     |
                                     v
                                Resume Graph
                                     |
                                     v
                                 Audit Log
```

### 3.1. Đầu ra bắt buộc

Một **`GraphState`** lưu:

- `customer_id`
- `proposed_action`
- `confidence_score`
- `reasoning`
- `human_decision`

Một Pydantic **`AuditEntry`** có:

- `timestamp`
- `agent_id`
- `action`
- `confidence`
- `reviewer_id`
- `decision`

Một node:

```python
evaluate_customer(state)
```

đánh giá khách hàng và trả về:

- `proposed_action`
- `confidence_score`
- `reasoning`

Một conditional edge function:

```python
route_action(state)
```

thực hiện:

- Policy Override.
- Auto-Execute.
- Escalate/Suggest.

LangGraph được compile với:

- `MemorySaver()`
- `interrupt_before=["execute_high_risk_action"]`

Một Streamlit approval interface cho phép:

- Approve.
- Reject.
- Edit.

Một audit trail ghi lại quyết định của agent và human reviewer.

---

# 4. Chuẩn bị

## 4.1. Python

Yêu cầu:

```text
Python 3.10+
```

## 4.2. Thư viện

Cài các thư viện:

```bash
pip install langgraph langchain streamlit pydantic
```

Các thư viện chính:

```text
langgraph
langchain
streamlit
pydantic
```

## 4.3. Cấu trúc project

```text
day27-hitl/
├── app.py
├── graph.py
├── models.py
├── audit_log.json
└── requirements.txt
```

Trong đó:

### `graph.py`

Chứa:

- GraphState.
- Agent nodes.
- Routing.
- Graph compilation.

### `models.py`

Chứa:

- AuditEntry.

### `app.py`

Chứa:

- Streamlit UI.
- Human approval logic.
- Resume graph logic.

### `audit_log.json`

Chứa:

- Audit trail.

---

# 5. Thực hành

## Bước 1 — Định nghĩa State và Audit Schema

### 5.1. Tạo GraphState

Graph cần một persistent state để giữ proposed action của agent trong khi chờ human approval.

Tạo một **`GraphState`** sử dụng **`TypedDict`**:

```python
from typing import TypedDict


class GraphState(TypedDict):
    customer_id: str
    proposed_action: str
    confidence_score: float
    reasoning: str
    human_decision: str | None
```

State bao gồm:

```text
customer_id
proposed_action
confidence_score
reasoning
human_decision
```

GraphState cần tồn tại xuyên suốt workflow.

### 5.2. Luồng State

```text
Agent đề xuất action
        |
        v
GraphState
        |
        | graph tạm dừng
        v
Human Review
        |
        | cập nhật decision
        v
GraphState
```

### 5.3. Tạo AuditEntry

Định nghĩa một Pydantic `BaseModel` có tên:

```text
AuditEntry
```

Schema:

```python
from pydantic import BaseModel


class AuditEntry(BaseModel):
    timestamp: str
    agent_id: str
    action: str
    confidence: float
    reviewer_id: str
    decision: str
```

Mục tiêu của audit schema là lưu lại đầy đủ:

```text
Agent nào đưa ra quyết định?
Hành động được đề xuất là gì?
Confidence bao nhiêu?
Ai review?
Human quyết định gì?
Thời điểm nào?
```

---

## Bước 2 — Implement Agent Reasoning Node

### 5.4. Tạo node `evaluate_customer`

Giả lập một agent đánh giá:

```text
Total Operating Income (TOI)
```

và:

```text
churn probability
```

của khách hàng.

Tạo node:

```python
def evaluate_customer(state: GraphState):
    ...
```

Có thể:

- Hardcode một mock LLM output.
- Hoặc sử dụng một prompt cơ bản để generate mock output.

### 5.5. Action

Agent cần đề xuất một action.

Low-risk:

```text
send_email
```

High-risk:

```text
increase_credit_limit
```

Node phải output:

```text
confidence_score
```

trong khoảng:

```text
0.0 -> 1.0
```

Ví dụ low-risk:

```python
{
    "proposed_action": "send_email",
    "confidence_score": 0.92,
    "reasoning": "Customer has moderate churn probability and no high-risk financial action is required."
}
```

Ví dụ high-risk:

```python
{
    "proposed_action": "increase_credit_limit",
    "confidence_score": 0.96,
    "reasoning": "Customer has high churn probability and increasing the credit limit may improve retention."
}
```

### 5.6. Lưu ý

```text
confidence_score cao KHÔNG có nghĩa là agent được phép bypass policy.
```

Hard policy rule ở bước tiếp theo có quyền override confidence.

---

## Bước 3 — Implement Confidence Routing và Hard Rules

Tạo conditional edge:

```python
def route_action(state: GraphState):
    ...
```

Routing phải thực hiện ba rule.

### 5.7. Rule 1 — Policy Override

Nếu action là:

```text
increase_credit_limit
```

thì route thẳng đến:

```text
execute_high_risk_action
```

bất kể:

```text
confidence_score
```

là bao nhiêu.

Ví dụ:

```text
action = increase_credit_limit
confidence = 0.99
```

vẫn phải:

```text
Human Review
```

Không được auto-execute.

Luồng:

```text
increase_credit_limit
        |
        | hard policy rule
        v
execute_high_risk_action
        |
        | interrupt_before
        v
Human Review
```

### 5.8. Rule 2 — Auto-Execute

Nếu:

```text
confidence_score >= 0.85
```

và action là:

```text
low-risk
```

thì route đến:

```text
execute_low_risk_action
```

Ví dụ:

```text
action = send_email
confidence_score = 0.91
```

thì:

```text
Auto Execute
```

### 5.9. Rule 3 — Escalate/Suggest

Nếu:

```text
confidence_score < 0.85
```

thì route đến:

```text
execute_high_risk_action
```

để ép buộc human review.

Ví dụ:

```text
action = send_email
confidence_score = 0.82
```

mặc dù action là low-risk nhưng confidence thấp hơn threshold:

```text
Human Review
```

### 5.10. Tổng hợp routing

```text
                      proposed_action
                            |
                            v
                 +-------------------------+
                 | increase_credit_limit ? |
                 +-------------------------+
                      | YES          | NO
                      v              v
                  High Risk     confidence >= 0.85 ?
                                   |
                                 +------+------+
                                 |             |
                                YES            NO
                                 |             |
                                 v             v
                            Low Risk       High Risk
```

**Hard policy phải được kiểm tra trước confidence threshold.**

---

## Bước 4 — Compile Graph với Interrupts

Đây là phần lõi của HITL architecture.

Bạn phải pause graph trước khi bất kỳ destructive action hoặc high-risk action nào diễn ra.

### 5.11. Khởi tạo MemorySaver

Import:

```python
from langgraph.checkpoint.memory import MemorySaver
```

Khởi tạo:

```python
memory = MemorySaver()
```

Điều này là bắt buộc.

Nếu không có persistent checkpoint, graph có thể mất customer data trong khi chờ con người review.

### 5.12. Build State Graph

Các node có thể gồm:

```text
evaluate_customer
execute_low_risk_action
execute_high_risk_action
```

Compile graph:

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["execute_high_risk_action"]
)
```

### 5.13. Hiểu `interrupt_before`

```python
interrupt_before=["execute_high_risk_action"]
```

có nghĩa là:

```text
Graph KHÔNG chạy execute_high_risk_action ngay.

Graph dừng TRƯỚC node đó.
```

Luồng:

```text
evaluate_customer
       |
       v
route_action
       |
       v
execute_high_risk_action
       X
       |
       | INTERRUPT BEFORE
       v
Human Review
```

State phải vẫn tồn tại trong lúc graph đang tạm dừng.

---

# 6. Hướng dẫn thiết kế và sử dụng giao diện Streamlit

## 6.1. Mục đích giao diện

Streamlit đóng vai trò là **Human Approval Interface**.

Giao diện không trực tiếp quyết định action thay cho agent. Nhiệm vụ của UI là:

```text
Lấy pending state
       ↓
Hiển thị đề xuất của agent
       ↓
Cho human xem reasoning + confidence
       ↓
Human chọn Approve / Reject / Edit
       ↓
Cập nhật GraphState
       ↓
Resume graph
```

---

## 6.2. Chạy giao diện

Tạo file:

```text
app.py
```

Chạy:

```bash
streamlit run app.py
```

---

## 6.3. Khởi tạo Graph trong Streamlit

Compiled graph nên được lưu trong:

```text
st.session_state
```

để graph không bị tạo lại không cần thiết mỗi lần Streamlit rerun.

Luồng khởi tạo:

```text
Streamlit Start
      ↓
Check session_state
      ↓
Graph chưa tồn tại?
      ├── YES → Create Graph
      └── NO  → Reuse Graph
```

---

## 6.4. Lấy Pending State

Sử dụng:

```python
graph.get_state(config)
```

để lấy pending state hiện tại.

Sau đó trích xuất:

```text
proposed_action
confidence_score
reasoning
```

---

## 6.5. Thiết kế giao diện tổng thể

Có thể chia UI thành các khu vực:

```text
┌──────────────────────────────────────────────┐
│              HITL Approval Dashboard         │
├──────────────────────────────────────────────┤
│ Customer Information                         │
│ Customer ID: CUST001                         │
├──────────────────────────────────────────────┤
│ Agent Proposal                               │
│                                              │
│ Proposed Action: increase_credit_limit      │
│ Confidence:      0.91                       │
│                                              │
│ Reasoning:                                   │
│ Customer has high churn probability...      │
├──────────────────────────────────────────────┤
│ Human Decision                               │
│                                              │
│ [ Approve ]  [ Reject ]  [ Edit ]            │
└──────────────────────────────────────────────┘
```

Mục tiêu là reviewer có thể nhìn thấy đầy đủ thông tin trước khi quyết định.

---

## 6.6. Khu vực Customer Information

Hiển thị:

```text
Customer ID
```

Ví dụ:

```text
Customer ID: CUST001
```

Mục đích là giúp reviewer xác định đúng customer đang được xử lý.

---

## 6.7. Khu vực Agent Proposal

Hiển thị tối thiểu:

```text
Proposed Action
Confidence Score
Reasoning
```

Ví dụ:

```text
Proposed Action:
increase_credit_limit

Confidence:
0.91

Reasoning:
Customer has high churn probability...
```

Reviewer phải có khả năng hiểu:

```text
Agent muốn làm gì?
        ↓
Agent tự tin đến mức nào?
        ↓
Tại sao agent lại đề xuất như vậy?
```

---

## 6.8. Khu vực Human Decision

UI phải có ba lựa chọn:

```text
[ Approve ]
[ Reject ]
[ Edit ]
```

### Approve

Khi reviewer đồng ý:

```text
Approve
   ↓
human_decision = "approve"
   ↓
update_state()
   ↓
resume graph
   ↓
execute action
```

### Reject

Khi reviewer từ chối:

```text
Reject
   ↓
human_decision = "reject"
   ↓
update_state()
   ↓
resume graph
   ↓
abort action
```

### Edit

Khi reviewer muốn sửa action:

```text
Edit
   ↓
Nhập action/value mới
   ↓
update state
   ↓
resume graph
   ↓
execute action đã chỉnh sửa
```

Ví dụ:

```text
Agent:
increase_credit_limit = 50,000,000

Human Edit:
increase_credit_limit = 20,000,000
```

---

## 6.9. Xử lý nút Approve / Reject / Edit

Khi button được click, trigger:

```python
graph.update_state(
    config,
    {"human_decision": decision}
)
```

Sau đó:

```python
graph.invoke(None, config)
```

để resume execution.

Luồng:

```text
Graph interrupted
       |
       v
Streamlit UI
       |
       +-------- Approve
       |
       +-------- Reject
       |
       +-------- Edit
       |
       v
graph.update_state(...)
       |
       v
graph.invoke(None, config)
       |
       v
Resume Graph
```

---

## 6.10. Lưu ý về `thread_id`

Khi lấy pending state và resume graph, `config` phải dùng cùng `thread_id` với lần invoke trước đó.

Ví dụ logic:

```text
Initial Invoke
     ↓
thread_id = customer/session/thread
     ↓
Graph Interrupt
     ↓
Streamlit
     ↓
get_state(same config)
     ↓
update_state(same config)
     ↓
invoke(None, same config)
     ↓
Resume
```

Nếu dùng `thread_id` khác, Streamlit có thể không lấy được state đang pending hoặc không resume đúng workflow.

---

# 7. Bước 6 — Ghi Audit Log

Chỉnh sửa node:

```text
execute_high_risk_action
```

để kiểm tra:

```python
state["human_decision"]
```

## 7.1. Approve

Nếu decision là:

```text
Approve
```

thì:

```text
execute action
```

Ví dụ:

```text
increase_credit_limit
```

được phép thực hiện.

---

## 7.2. Reject

Nếu decision là:

```text
Reject
```

thì:

```text
abort action
```

Không thực hiện proposed action.

---

## 7.3. Edit

Nếu decision là:

```text
Edit
```

thì thực hiện action sau khi đã được human operator chỉnh sửa.

---

## 7.4. Tạo AuditEntry

Trong tất cả các trường hợp, khởi tạo một:

```text
AuditEntry
```

và append vào file JSON cục bộ.

Ví dụ:

```json
{
  "timestamp": "2026-08-29T09:00:00",
  "agent_id": "churn-risk-agent",
  "action": "increase_credit_limit",
  "confidence": 0.94,
  "reviewer_id": "operator_01",
  "decision": "approve"
}
```

File:

```text
audit_log.json
```

có thể có dạng:

```json
[
  {
    "timestamp": "2026-08-29T09:00:00",
    "agent_id": "churn-risk-agent",
    "action": "increase_credit_limit",
    "confidence": 0.94,
    "reviewer_id": "operator_01",
    "decision": "approve"
  }
]
```

Mục tiêu:

```text
Mọi quyết định quan trọng phải truy vết được.
```

Trong production, có thể ghi log vào:

```text
PostgreSQL append-only database
```

để tăng độ tin cậy và khả năng kiểm toán.

---

# 8. Luồng hoàn chỉnh của hệ thống

```text
                    CUSTOMER DATA
                         │
                         ▼
                ┌─────────────────┐
                │ evaluate_customer│
                └────────┬────────┘
                         │
                         ▼
                 Agent Reasoning
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
            Action   Confidence  Reasoning
                         │
                         ▼
                  route_action()
                         │
             ┌───────────┴───────────┐
             │                       │
             ▼                       ▼
         LOW RISK                HIGH RISK
             │                       │
             ▼                       ▼
      Confidence >= 0.85         INTERRUPT
             │                       │
             ▼                       ▼
       Auto Execute            Streamlit UI
                                     │
                         ┌───────────┼───────────┐
                         ▼           ▼           ▼
                      Approve      Reject       Edit
                         │           │           │
                         └───────────┼───────────┘
                                     ▼
                              update_state()
                                     │
                                     ▼
                              resume graph
                                     │
                                     ▼
                               Execute/Abort
                                     │
                                     ▼
                                Audit Log
```

---

# 9. Kiểm tra kết quả

## 9.1. Kiểm tra State

Đảm bảo `GraphState` có:

```text
customer_id
proposed_action
confidence_score
reasoning
human_decision
```

Checklist:

```text
[ ] State tồn tại xuyên suốt graph
[ ] State không mất khi graph bị interrupt
[ ] human_decision có thể được cập nhật từ Streamlit
```

---

## 9.2. Kiểm tra Agent Reasoning

Chạy một customer input.

Đảm bảo agent output:

```text
[ ] proposed_action
[ ] confidence_score
[ ] reasoning
```

và:

```text
0.0 <= confidence_score <= 1.0
```

---

## 9.3. Kiểm tra Hard Rule

Test:

```text
proposed_action = increase_credit_limit
confidence_score = 0.99
```

Kết quả bắt buộc:

```text
Human Review
```

Không được:

```text
Auto Execute
```

---

## 9.4. Kiểm tra Auto-Execute

Test:

```text
proposed_action = send_email
confidence_score = 0.90
```

Kết quả:

```text
execute_low_risk_action
```

---

## 9.5. Kiểm tra Escalation

Test:

```text
proposed_action = send_email
confidence_score = 0.82
```

Kết quả:

```text
Human Review
```

---

## 9.6. Kiểm tra Interrupt

Đảm bảo graph compile với:

```python
graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["execute_high_risk_action"]
)
```

Khi route tới high-risk action:

```text
[ ] execute_high_risk_action chưa được chạy
[ ] graph ở pending state
[ ] state vẫn còn dữ liệu customer
```

---

## 9.7. Kiểm tra Streamlit UI

Streamlit UI phải hiển thị:

```text
[ ] proposed_action
[ ] confidence_score
[ ] reasoning
[ ] Approve
[ ] Reject
[ ] Edit
```

### Test Approve

```text
Approve
   |
   v
update_state
   |
   v
resume graph
   |
   v
execute action
```

### Test Reject

```text
Reject
   |
   v
update_state
   |
   v
resume graph
   |
   v
abort action
```

### Test Edit

```text
Edit
   |
   v
update proposed action/value
   |
   v
update_state
   |
   v
resume graph
   |
   v
execute edited action
```

---

## 9.8. Kiểm tra Audit Log

Sau mỗi human decision, `audit_log.json` phải có entry mới.

Entry phải chứa:

```text
timestamp
agent_id
action
confidence
reviewer_id
decision
```

Đảm bảo:

```text
[ ] Approve được log
[ ] Reject được log
[ ] Edit được log
[ ] Không overwrite audit history cũ
```

---

# 10. Lỗi thường gặp

## 10.1. Graph mất state sau khi interrupt

Kiểm tra có dùng:

```python
MemorySaver()
```

và truyền vào:

```python
checkpointer=memory
```

hay chưa.

---

## 10.2. High-risk action chạy trước khi human review

Kiểm tra:

```python
interrupt_before=["execute_high_risk_action"]
```

không phải interrupt sau khi action đã được thực hiện.

---

## 10.3. Hard rule bị confidence override

Sai:

```text
confidence = 0.99
-> auto execute increase_credit_limit
```

Đúng:

```text
increase_credit_limit
-> luôn human review
```

Hard policy phải được kiểm tra trước confidence threshold.

---

## 10.4. Streamlit bấm button nhưng graph không tiếp tục

Kiểm tra:

```python
graph.update_state(config, ...)
```

và sau đó:

```python
graph.invoke(None, config)
```

để resume graph.

---

## 10.5. Pending state không lấy được

Kiểm tra:

```python
graph.get_state(config)
```

và `config` phải dùng cùng `thread_id` với lần invoke trước đó.

---

## 10.6. Audit log bị ghi đè

Không ghi một object mới đè lên toàn bộ lịch sử.

Cần:

```text
1. Đọc audit entries hiện có.
2. Append AuditEntry mới.
3. Ghi lại danh sách.
```

Trong production nên dùng append-only database.

---

# 11. Checklist nghiệm thu cuối Lab

## Backend / Graph

```text
[ ] GraphState đã được định nghĩa bằng TypedDict
[ ] AuditEntry đã được định nghĩa bằng Pydantic
[ ] evaluate_customer() hoạt động
[ ] Agent trả về action
[ ] Agent trả về confidence
[ ] Agent trả về reasoning
[ ] route_action() hoạt động
[ ] Hard Rule hoạt động
[ ] Confidence Routing hoạt động
[ ] MemorySaver được sử dụng
[ ] interrupt_before được cấu hình
```

## Human-in-the-Loop

```text
[ ] High-risk action bị interrupt
[ ] Pending state lấy được
[ ] Streamlit hiển thị proposal
[ ] Approve hoạt động
[ ] Reject hoạt động
[ ] Edit hoạt động
[ ] Graph resume được sau human decision
```

## Audit

```text
[ ] AuditEntry được tạo
[ ] Approve được log
[ ] Reject được log
[ ] Edit được log
[ ] Audit history không bị overwrite
```

---

# 12. Reflection Questions

## Câu 1

Ở Bước 4, chúng ta đã dùng:

```python
interrupt_before=["execute_high_risk_action"]
```

Nếu mục tiêu của bạn là để con người rewrite một customer retention email vừa được generate trước khi nó di chuyển đến một routing node, bạn sẽ dùng:

```text
interrupt_before
```

hay:

```text
interrupt_after
```

Tại sao?

Điểm cần phân tích là vị trí interrupt trong graph quyết định thời điểm human can thiệp vào workflow.

---

## Câu 2

Giả sử Streamlit UI của bạn hiện đang ép human phải review:

```text
500 actions send_email mỗi ngày
```

vì confidence của agent bị kẹt ở:

```text
0.82
```

ngay dưới threshold:

```text
0.85
```

Hãy suy nghĩ những thay đổi cụ thể về:

```text
UI/UX
+
Architecture
+
Routing
```

để ngăn chặn:

```text
Alert Fatigue
```

---

## Câu 3

Bạn nhận thấy agent thường xuyên tự báo confidence là:

```text
0.95
```

khi đề xuất:

```text
increase_credit_limit
```

nhưng nó lại thường xuyên sai về thu nhập thực tế của khách hàng.

Tại sao việc chỉ phụ thuộc vào sự tự đánh giá confidence của LLM lại nguy hiểm?

Và làm thế nào bạn có thể calibrate điểm số này trước bước routing?

---

# 13. Kết luận

Sau khi hoàn thành Lab, bạn đã xây dựng được một hệ thống Agent HITL với pipeline:

```text
Agent
  ↓
Reasoning
  ↓
Action + Confidence
  ↓
Policy
  ↓
Routing
  ↓
 ┌───────────────┐
 │               │
Low Risk      High Risk
 │               │
Auto Execute   Interrupt
                 ↓
             Human Review
                 ↓
          Approve/Reject/Edit
                 ↓
             Resume Graph
                 ↓
             Execute/Abort
                 ↓
              Audit Log
```

Trọng tâm của Lab 27 là hiểu đúng kiến trúc:

```text
Agent
  →
Policy
  →
Interrupt
  →
Human Decision
  →
Resume
  →
Audit
```

Không cần xây một hệ thống ngân hàng hoàn chỉnh. Điều quan trọng là chứng minh được **agent đề xuất → policy quyết định route → graph tạm dừng khi cần → human đưa ra quyết định → graph tiếp tục → quyết định được audit**.
