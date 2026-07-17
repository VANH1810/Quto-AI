"""AI Agent service (LangGraph worker) — hệ cảnh báo sớm thiên tai Điện Biên.

Service riêng, nhận job từ BackEnd Services qua RabbitMQ, chạy graph LangGraph gọi
các tool (risk engine / user API / shelter / recommend / zalo), lưu vết LLM
(tool call / response / thinking) vào Postgres và điều phối gửi đa kênh đa ngữ.

Import lại `app.*` của backend qua PYTHONPATH (không viết lại risk engine / LLM).
"""
