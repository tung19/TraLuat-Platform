"""TraLuat — walking skeleton.

Chứng minh moat #1: dựng lại "văn bản luật tại ngày T" trên mô hình dữ liệu
bitemporal (valid-time + transaction-time), remodel từ pattern của Indigo
(FRBR Work/Expression + amendment → materialize phiên bản mới) sang SQLAlchemy.

Đây là proof-of-concept, dùng dữ liệu MINH HOẠ (không phải văn bản pháp luật thật).
"""
