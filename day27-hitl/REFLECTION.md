# Reflection Questions — Lab 27 (HITL Agent)

Trả lời 3 câu hỏi ở [`../Readme_1.md`](../Readme_1.md) mục 12.

## Câu 1 — `interrupt_before` hay `interrupt_after`?

Dùng **`interrupt_before`**, đặt trước node routing/gửi email (ví dụ
`interrupt_before=["send_retention_email"]`), chứ không phải sau node
generate.

Lý do: vị trí interrupt quyết định **thời điểm** con người can thiệp, và
mục tiêu ở đây là con người *rewrite nội dung trước khi nó có hệ quả*.
Nếu dùng `interrupt_after` đặt sau node generate, graph sẽ chạy xong node
generate rồi mới dừng — tại thời điểm đó nội dung email đã tồn tại trong
state và, tùy graph tiếp theo, có thể đã trôi tới node routing/gửi. Human
review lúc này chỉ còn là "xem lại sau khi đã generate" chứ không ngăn
được việc bản nháp bị đẩy đi trước khi sửa. `interrupt_before` đặt ngay
trước node có side-effect (gửi/route) đảm bảo: generate → **dừng** →
human rewrite → resume → gửi bản đã sửa. Nguyên tắc chung của lab này
("agent không được tự thực hiện side-effect trước khi human duyệt") chỉ
đúng khi interrupt nằm ngay trước hành động không thể hoàn tác, bất kể đó
là gửi tiền hay gửi email.

## Câu 2 — Giảm Alert Fatigue khi 500 `send_email`/ngày bị kẹt ở confidence 0.82

Nguyên nhân gốc: đang dùng **một threshold cứng (0.85)** cho một action đã
được xếp loại low-risk, nên mọi dao động nhỏ quanh 0.82–0.84 đều bị đẩy
sang human dù hậu quả sai (gửi nhầm một email) rất nhỏ và dễ hoàn tác.

Thay đổi cụ thể:

**Routing/Architecture**
- Tách threshold theo *risk tier* thay vì dùng chung một con số cho mọi
  action. `send_email` là reversible/low-blast-radius → threshold auto-execute
  có thể hạ xuống (vd. 0.70) hoặc bỏ hẳn gate confidence, chỉ giữ hard
  rule cho action thật sự nguy hiểm (`increase_credit_limit`). Confidence
  routing nên là hàm của `(risk_tier, action)`, không phải một hằng số
  toàn cục.
- Thêm **batch review** thay vì review từng cái: gom N action cùng loại,
  cùng confidence band vào một "digest" review mỗi giờ/ngày, reviewer
  duyệt hàng loạt (bulk approve) thay vì click 500 lần.
- Thêm **sampling-based review**: nếu action là low-risk và confidence
  nằm trong vùng biên (0.80–0.85), chỉ escalate ngẫu nhiên một tỷ lệ nhỏ
  (vd. 10%) để giám sát chất lượng model, số còn lại auto-execute với log
  đầy đủ để audit sau — đánh đổi risk thấp lấy giảm tải review.

**UI/UX**
- Ưu tiên hiển thị theo mức độ nghiêm trọng: high-risk luôn hiện riêng,
  đòi hỏi xem xét; low-risk biên confidence gom vào một tab "batch
  review" tách biệt để không làm loãng các case thật sự cần chú ý.
- Cho phép reviewer "Approve all similar" khi thấy pattern lặp lại, giảm
  thao tác lặp.

**Ngắn hạn (không đổi routing)**: nếu chưa muốn sửa threshold ngay, có
thể tạm thời chỉ áp dụng human review cho batch đầu ngày rồi auto-execute
phần còn lại trong ngày dựa trên pattern đã được duyệt, miễn accuracy ổn
định — nhưng đây là workaround, không phải fix gốc.

## Câu 3 — Vì sao chỉ tin vào confidence tự báo của LLM là nguy hiểm, và cách calibrate

**Vì sao nguy hiểm**: confidence LLM tự báo là *self-reported*, phản ánh
mức độ "chắc chắn về ngôn ngữ" của model khi sinh câu trả lời, không phải
xác suất được hiệu chỉnh (calibrated probability) rằng thông tin đó đúng
trong thực tế. Một LLM có thể rất "tự tin" (0.95) về một con số nó suy
diễn/bịa ra (thu nhập khách hàng) vì câu trả lời *nghe hợp lý và mạch
lạc*, trong khi độ chính xác thực tế lại thấp — đây chính là hiện tượng
hallucination có vỏ bọc tự tin. Nếu hệ thống dùng confidence này làm cổng
duy nhất để quyết định auto-execute vs. human review, model sẽ tự cấp
quyền bỏ qua review đúng vào những trường hợp nó sai nhiều nhất — ngược
hoàn toàn với mục đích của HITL.

**Cách calibrate trước bước routing**:
1. **Tách nguồn dữ liệu khỏi self-assessment**: `confidence_score` dùng để
   routing không nên đến từ chính câu trả lời tự nhiên ngôn ngữ của LLM
   (không parse "tôi tự tin 95%" từ text), mà từ một tín hiệu định lượng
   độc lập — ví dụ log-probability của token, hoặc tốt hơn là một model
   phân loại/scoring riêng (calibration model) được train trên dữ liệu
   lịch sử (predicted vs. actual outcome).
2. **Đối chiếu với dữ liệu có thể verify được**: với `increase_credit_limit`,
   thu nhập/TOI khai báo bởi agent phải được cross-check với hệ thống
   nguồn (core banking, KYC) trước khi tính vào confidence — nếu số liệu
   agent dùng không khớp nguồn xác thực, hạ confidence hoặc force human
   review bất kể model "tự tin" thế nào.
3. **Calibration curve / temperature scaling**: theo dõi thực tế
   (approve/reject/edit rate theo từng dải confidence) qua audit log, vẽ
   reliability diagram, rồi remap confidence thô sang confidence đã hiệu
   chỉnh (Platt scaling / isotonic regression) trước khi so với threshold.
4. **Hard rule vẫn là lớp bảo vệ cuối**: đây là lý do policy override
   (Rule 1) trong lab này không bao giờ được confidence bypass —
   `increase_credit_limit` luôn đi qua human review bất kể agent báo
   0.99, chính vì confidence tự đánh giá không đáng tin cậy tuyệt đối cho
   action có hậu quả tài chính khó hoàn tác.
