"""Package chemical — tách từ chemical_service.py 850 dòng (M-03/T1.2).

Cùng lý do và cùng cách làm như `research/`: file gốc đã đánh dấu sẵn ranh giới
bằng comment `# ===== lots =====`, `# ===== stock (FR-008) =====` v.v.

    _shared           18   coa_service      73
    stock_service    178   lot_service     245
    catalog_service  308

CỐ Ý KHÔNG re-export gì — caller import thẳng module domain:

    from app.services.chemical import lot_service
    lot_service.create_lot(...)

Đồ thị phụ thuộc không có vòng:
    _shared     ← catalog_service, stock_service
    lot_service ← stock_service
"""
