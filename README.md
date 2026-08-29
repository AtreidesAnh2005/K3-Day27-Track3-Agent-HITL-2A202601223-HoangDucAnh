# K3 Day27 Track3 — Agent HITL Lab

Lab implementation của **Human-in-the-Loop (HITL) Agent** với LangGraph,
đánh giá churn risk khách hàng và chuyển các hành động rủi ro cao cho con
người duyệt trước khi thực thi.

- Đề bài đầy đủ: [`Readme_1.md`](Readme_1.md), [`exercise.md`](exercise.md)
- Code + hướng dẫn chạy: [`day27-hitl/`](day27-hitl/README.md)

## Quick start

```bash
cd day27-hitl
python -m pip install -r requirements.txt
python -m pytest tests/ -v
streamlit run app.py
```
