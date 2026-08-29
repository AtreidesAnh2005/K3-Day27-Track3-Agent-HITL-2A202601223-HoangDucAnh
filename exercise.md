# Exercise — Human-in-the-Loop (HITL) Agent Lab

## Mục tiêu

Hoàn thành bài lab **Agent Human-in-the-Loop (HITL)** trong repo hiện tại theo đúng starter code và yêu cầu của bài.

Mục tiêu cuối cùng là có một agent có thể:

1. Nhận yêu cầu từ người dùng.
2. Tự phân tích và đề xuất hành động.
3. Với hành động cần kiểm soát, **không tự ý thực thi ngay** mà phải dừng để xin quyết định của con người.
4. Cho phép người duyệt chọn tối thiểu:
   - **Approve** — chấp thuận và tiếp tục.
   - **Edit / Modify** — chỉnh sửa hành động hoặc dữ liệu rồi tiếp tục.
   - **Reject** — từ chối hành động.
5. Sau quyết định của con người, agent tiếp tục đúng workflow.
6. Ghi lại đủ thông tin để kiểm tra được:
   - yêu cầu ban đầu,
   - hành động agent đề xuất,
   - lý do cần human review,
   - quyết định của human,
   - dữ liệu sau khi edit nếu có,
   - kết quả cuối cùng.
7. Có demo/test chứng minh cả các nhánh HITL hoạt động.

> Ưu tiên hoàn thành đúng yêu cầu lab trước. Không over-engineer, không thay đổi kiến trúc/API đang có nếu không cần thiết.

---

# Quy tắc làm bài cho Agent IDE

Trước khi code:

- Đọc toàn bộ `README`, thư mục `src`, `app`, `tests`, notebook, config và các file hướng dẫn lab có trong repo.
- Xác định framework đang dùng trước khi sửa code.
- Tận dụng code có sẵn.
- Không tự ý chuyển framework hoặc viết lại project.
- Không đổi endpoint/request/response contract hiện có nếu không bắt buộc.
- Không xóa code starter chỉ vì chưa hiểu; phải kiểm tra nơi nó được sử dụng.
- Nếu repo đã dùng LangGraph/LangChain/OpenAI SDK hoặc framework agent khác thì tiếp tục dùng framework đó.
- Nếu tên file trong hướng dẫn này không giống repo, hãy map chức năng vào file tương ứng thay vì tạo cấu trúc mới vô lý.
- Mọi secret/API key phải lấy từ environment variables, không hard-code.
- Nếu API LLM không khả dụng, vẫn phải làm được demo/test phần HITL bằng mock/fake response nếu starter code cho phép.

---

# PHASE 0 — Inspect repo và lập checklist yêu cầu

## Việc cần làm

1. Kiểm tra cấu trúc repo.
2. Đọc tài liệu lab/starter code.
3. Xác định:
   - entrypoint chạy chương trình;
   - agent được tạo ở đâu;
   - tools/actions hiện có;
   - state/context của workflow;
   - nơi gọi LLM;
   - nơi hiển thị hoặc nhận input từ human;
   - test hiện có;
   - dependency và command chạy project.
4. Tìm TODO, FIXME, placeholder, stub, `pass`, `NotImplemented`, mock chưa hoàn thiện.
5. Tạo checklist nội bộ gồm tất cả yêu cầu thực tế tìm thấy trong repo/tài liệu.

## Không được làm

- Không phỏng đoán cấu trúc nếu có thể đọc trực tiếp từ repo.
- Không bắt đầu refactor lớn ở phase này.

## Done khi

- Hiểu được luồng hiện tại từ user input → agent → tool/action → output.
- Xác định chính xác vị trí cần chèn HITL.
- Có danh sách các phần còn thiếu.

---

# PHASE 1 — Hoàn thiện Agent Workflow cơ bản

## Mục tiêu

Đảm bảo agent có một workflow chạy được trước khi thêm HITL.

## Việc cần làm

Agent cần có state/context tối thiểu tương đương:

- user request / messages;
- current proposed action;
- action arguments;
- trạng thái cần human review hay không;
- human decision;
- final result;
- thông tin lỗi nếu có.

Không bắt buộc dùng đúng các tên field trên nếu repo đã có schema riêng.

Kiểm tra workflow có các bước logic:

```text
User Request
    ↓
Agent Reason / Decide
    ↓
Proposed Action
    ↓
Policy / Risk / HITL Check
```

Nếu action không cần approval:

```text
→ Execute
→ Final Response
```

Nếu action cần approval:

```text
→ Pause / Interrupt
→ Human Review
→ Resume
```

## Done khi

- Một request bình thường chạy được end-to-end.
- Workflow không bị lỗi state.
- Có thể phân biệt action cần review và action không cần review.

---

# PHASE 2 — Xác định khi nào cần Human-in-the-Loop

## Mục tiêu

Không phải mọi bước đều hỏi người dùng. Chỉ interrupt tại các hành động cần kiểm soát.

## Việc cần làm

Dựa trên yêu cầu thật của lab/starter code để xác định policy.

Nếu tài liệu không quy định cụ thể, áp dụng nguyên tắc đơn giản:

**Require human approval trước các side-effect action**, ví dụ:

- gửi email/message;
- ghi/sửa/xóa dữ liệu;
- thực hiện giao dịch;
- gọi API tạo thay đổi bên ngoài;
- thao tác có hậu quả khó hoàn tác;
- hành động mà agent không đủ confidence.

Các hành động chỉ đọc/search/analyze có thể chạy trực tiếp nếu lab không yêu cầu review.

Tạo một hàm/policy rõ ràng tương đương:

```python
requires_human_review(action) -> bool
```

Policy nên dễ đọc và dễ test.

## Done khi

- Có rule rõ ràng quyết định action nào phải review.
- Không hard-code rải rác nhiều nơi.
- Có ít nhất một case không cần HITL và một case bắt buộc HITL.

---

# PHASE 3 — Implement Pause / Interrupt

## Mục tiêu

Khi gặp action cần human review, workflow phải **dừng trước khi thực hiện side effect**.

## Yêu cầu bắt buộc

Human phải nhìn thấy đủ thông tin để quyết định:

- agent định làm gì;
- arguments/data agent định dùng;
- lý do hoặc context liên quan;
- các lựa chọn `Approve`, `Edit`, `Reject`.

Pseudo-flow:

```text
Agent proposes action
        ↓
requires_human_review?
        ↓ yes
Create approval request
        ↓
PAUSE / INTERRUPT
        ↓
Wait for human decision
```

Nếu framework có cơ chế interrupt/checkpoint/resume riêng, dùng đúng cơ chế framework thay vì tự chế vòng lặp phức tạp.

Ví dụ nếu project dùng graph/state machine:

- lưu state trước khi interrupt;
- interrupt trả approval payload;
- sau khi human input được cung cấp, resume từ state trước đó;
- không chạy lại side effect hai lần.

## Cực kỳ quan trọng

**Không được execute tool trước rồi mới hỏi approval.**

Human approval phải xảy ra **trước side effect**.

## Done khi

- Agent dừng đúng vị trí.
- Action chưa được thực thi trong lúc chờ.
- State có thể resume.

---

# PHASE 4 — Implement 3 Human Decisions

## 4.1 Approve

Khi human chọn `approve`:

```text
Human approves
    ↓
Execute original proposed action
    ↓
Store result
    ↓
Agent continues / final answer
```

Yêu cầu:

- giữ đúng arguments đã được duyệt;
- action chỉ chạy một lần.

---

## 4.2 Edit / Modify

Khi human chọn `edit`:

```text
Human edits arguments/action
    ↓
Validate edited input
    ↓
Execute edited action
    ↓
Store both original + edited values
    ↓
Agent continues
```

Yêu cầu:

- không bỏ qua dữ liệu human sửa;
- validate kiểu dữ liệu cần thiết;
- log lại proposed value và approved/edited value;
- nếu edited action vẫn nguy hiểm hơn đáng kể, có thể review lại nếu architecture yêu cầu.

---

## 4.3 Reject

Khi human chọn `reject`:

```text
Human rejects
    ↓
DO NOT execute action
    ↓
Record rejection
    ↓
Agent produces safe/meaningful response
```

Agent không được giả vờ rằng action đã thành công.

## Done khi

Cả ba nhánh:

- approve,
- edit,
- reject

đều chạy được và cho kết quả đúng.

---

# PHASE 5 — Persistence / Checkpoint / Resume

## Mục tiêu

Workflow phải giữ được state trong thời gian chờ human.

## Việc cần làm

Nếu framework có checkpointer/persistence:

- cấu hình checkpoint;
- mỗi conversation/run có ID riêng;
- resume đúng run/thread;
- tránh resume nhầm state.

Nếu lab chỉ yêu cầu demo đơn giản, persistence in-memory là đủ **chỉ khi tài liệu không yêu cầu database/persistent storage**.

Đảm bảo các trường quan trọng không mất sau interrupt:

- messages;
- proposed action;
- arguments;
- approval request;
- human decision;
- current workflow position.

## Test nhanh

1. Start request.
2. Agent interrupt.
3. Kiểm tra action chưa chạy.
4. Submit human decision.
5. Resume.
6. Kiểm tra workflow tiếp tục từ đúng bước.

## Done khi

- Resume không restart toàn bộ workflow sai cách.
- Không tạo duplicate side effect.

---

# PHASE 6 — Audit Trail / Logging

## Mục tiêu

Có thể chứng minh Human-in-the-Loop thực sự xảy ra.

## Log tối thiểu

Mỗi HITL event nên ghi được:

```text
run/thread id
timestamp
user request
proposed action
proposed arguments
reason for review
human decision
edited arguments (nếu có)
execution status
result/error
```

Không log API key hoặc secret.

Nếu repo đã có logging framework thì dùng framework hiện tại.

Nếu chưa có, triển khai tối giản nhưng dễ kiểm tra.

## Done khi

Sau một demo, có thể xem log và trả lời:

- Agent đề xuất gì?
- Human quyết định gì?
- Tool có được chạy không?
- Nếu edit thì giá trị cuối cùng là gì?
- Kết quả ra sao?

---

# PHASE 7 — UI / CLI Human Review

Giữ đúng interface mà starter code yêu cầu.

Nếu project là CLI, hiển thị approval prompt rõ ràng.

Ví dụ trải nghiệm mong muốn:

```text
Agent wants to execute:
Action: send_message
Arguments:
  recipient: ...
  content: ...

Decision:
[1] Approve
[2] Edit
[3] Reject
```

Nếu project có web UI:

- hiển thị proposed action;
- hiển thị arguments;
- có nút Approve / Edit / Reject;
- Edit cho phép sửa dữ liệu cần thiết;
- sau quyết định, UI hiển thị kết quả sau resume.

Không dành thời gian làm đẹp UI nếu không phải deliverable.

## Done khi

Người chấm có thể thao tác HITL mà không phải sửa code bằng tay.

---

# PHASE 8 — Error Handling

Bổ sung xử lý tối thiểu cho:

- human nhập decision không hợp lệ;
- edited arguments sai format;
- tool execution thất bại;
- LLM/API lỗi;
- missing environment variable;
- resume sai run/thread id;
- repeated approval request;
- action đã execute nhưng bị gọi lại.

Thông báo lỗi phải dễ hiểu, không crash im lặng.

---

# PHASE 9 — Tests / Demo Scenarios

Tạo hoặc hoàn thiện test theo convention hiện tại của repo.

Phải chứng minh ít nhất các scenario sau.

## Scenario A — No HITL needed

```text
User request
→ agent handles safe/read-only task
→ completes directly
```

Expected:

- không interrupt không cần thiết;
- có final result.

## Scenario B — Approve

```text
User requests side-effect action
→ agent proposes
→ HITL interrupt
→ human approves
→ action executes
→ final result
```

Expected:

- action chưa chạy trước approval;
- action chạy đúng 1 lần sau approval.

## Scenario C — Edit

```text
agent proposes action with argument A
→ human edits A → B
→ resume
→ action executes with B
```

Expected:

- tool nhận B, không phải A;
- log lưu cả proposed và edited value.

## Scenario D — Reject

```text
agent proposes action
→ human rejects
→ action is NOT executed
```

Expected:

- không có side effect;
- final response nói rõ action đã bị từ chối hoặc không thực hiện.

## Scenario E — Failure handling

Cho tool/mock tool fail.

Expected:

- workflow không treo;
- error được log;
- người dùng nhận message phù hợp.

---

# PHASE 10 — Run toàn bộ project

Agent tự xác định stack rồi chạy command phù hợp.

Ví dụ:

```bash
# Python
python -m pytest
python <entrypoint>

# hoặc
pytest -q

# Node
npm test
npm run dev
```

Không blindly dùng command trên nếu repo có command khác trong README/Makefile/package scripts.

Kiểm tra:

- install dependencies thành công;
- import không lỗi;
- app chạy;
- tests pass;
- demo HITL chạy được.

Nếu có test cũ bị fail do bug không liên quan bài lab:

- xác minh nguyên nhân;
- chỉ sửa nếu an toàn và trong scope;
- ghi rõ nếu còn issue.

---

# PHASE 11 — README / Hướng dẫn chạy

Cập nhật README ngắn gọn nếu đang thiếu.

README cần đủ để người chấm chạy:

```text
1. Install
2. Environment variables
3. Start application
4. Run HITL demo
5. Run tests
```

Thêm mô tả flow HITL cực ngắn:

```text
Agent proposes action
→ interrupt
→ human approve/edit/reject
→ workflow resumes
```

Nếu cần API key, cung cấp `.env.example`, không commit `.env`.

---

# PHASE 12 — Final Cleanup

Trước khi kết thúc:

- bỏ debug print thừa;
- bỏ dead code;
- bỏ secret;
- không commit cache/build artifacts không cần thiết;
- format code;
- kiểm tra imports;
- kiểm tra tên biến;
- bảo đảm app vẫn chạy sau cleanup.

Không refactor lớn sát deadline.

---

# FINAL DELIVERABLE CHECK — PHẢI CHẠY TRƯỚC KHI NỘP

Agent hãy kiểm tra từng mục dưới đây và sửa ngay nếu thiếu.

## A. Core Agent

- [ ] Project chạy được.
- [ ] Agent nhận được user request.
- [ ] Agent có thể đề xuất action/tool call.
- [ ] Workflow/state hoạt động đúng.

## B. Human-in-the-Loop

- [ ] Có rule xác định khi nào cần human review.
- [ ] Agent interrupt **trước** side effect.
- [ ] Human thấy proposed action + arguments.
- [ ] Có `Approve`.
- [ ] Có `Edit/Modify`.
- [ ] Có `Reject`.
- [ ] Approve thực thi đúng action.
- [ ] Edit thực thi dữ liệu đã chỉnh.
- [ ] Reject không thực thi side effect.
- [ ] Workflow resume đúng sau human decision.

## C. State / Persistence

- [ ] State không bị mất khi interrupt.
- [ ] Run/thread/session được phân biệt.
- [ ] Không execute action hai lần khi resume.

## D. Logging / Audit

- [ ] Log proposed action.
- [ ] Log human decision.
- [ ] Log edited data nếu có.
- [ ] Log execution result/error.
- [ ] Không log secrets.

## E. Tests

- [ ] Test no-HITL path.
- [ ] Test approve path.
- [ ] Test edit path.
- [ ] Test reject path.
- [ ] Test lỗi cơ bản.
- [ ] Toàn bộ test quan trọng pass.

## F. Demo

- [ ] Có ít nhất một demo end-to-end.
- [ ] Người chấm có thể tự trigger approval.
- [ ] Có thể chứng minh action chưa chạy trước approval.
- [ ] Có thể chứng minh reject ngăn side effect.
- [ ] Có thể chứng minh edit thay đổi arguments thực thi.

## G. Submission Hygiene

- [ ] README có cách install/run/test.
- [ ] Có `.env.example` nếu cần.
- [ ] Không commit API key.
- [ ] Không còn TODO bắt buộc.
- [ ] Không có syntax/import error.
- [ ] Git diff chỉ chứa thay đổi cần thiết.
- [ ] Các file deliverable theo đề bài đều tồn tại.

---

# FINAL AGENT REPORT

Sau khi hoàn thành, **không chỉ nói "done"**.

Hãy trả về báo cáo ngắn theo format:

```markdown
## Completed
- ...

## HITL Flow Implemented
- Trigger:
- Interrupt:
- Approve:
- Edit:
- Reject:
- Resume:

## Files Changed
- `...`: ...

## Tests
- Command:
- Result:

## Demo
- How to run:
- Expected flow:

## Deliverables Check
- [x] ...
- [x] ...

## Remaining Issues
- None
```

Nếu còn lỗi, nói chính xác lỗi gì và file nào thay vì che giấu.

---

# Ưu tiên nếu sắp hết thời gian

Nếu thời gian cực ít, làm theo thứ tự này:

1. App chạy được.
2. Có HITL interrupt trước side effect.
3. Approve hoạt động.
4. Reject hoạt động.
5. Edit hoạt động.
6. State/resume không duplicate action.
7. Có demo end-to-end.
8. Có audit/log.
9. Tests quan trọng pass.
10. README + cleanup.

Không dành thời gian làm UI đẹp, abstraction phức tạp hoặc refactor không cần thiết trước khi core HITL hoạt động.
