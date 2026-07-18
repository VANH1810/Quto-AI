"""AI Agent service (LangGraph worker) — hệ cảnh báo sớm thiên tai Điện Biên.

Service riêng, nhận job từ BackEnd Services qua RabbitMQ, chạy AGENT tool-calling
(LangGraph ReAct) gọi các tool (risk engine / weather / recommend / shelter / user API /
message_formatter / telegram / speaker), lưu vết LLM (tool call / response / thinking)
vào Postgres và điều phối gửi đa kênh đa ngữ.
"""
