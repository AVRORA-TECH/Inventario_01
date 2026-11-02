"""AI OCR / Invoice Extraction simulation and processing service for Refribreak.
Provides automated extraction of provider invoice items with confidence scores
to pre-populate warehouse purchase forms as described in Section 3 and 6.1 of the architecture spec.
"""
from typing import Dict, Any, List
from datetime import date, timedelta
import random


def extract_invoice_data(raw_text: str = None, supplier_hint: str = None) -> Dict[str, Any]:
    """Analyzes invoice content or simulates AI extraction of real food supplier invoices."""
    today = date.today()

    # Pre-canned high fidelity extraction for demonstration
    extracted_items = [
        {
            "product_name": "EXPRESS Wrap de jamón, queso y vegetales",
            "sku_match": "REF-WRAP-001",
            "suggested_product_id": "prod-wrap-exp",
            "lot_number": f"L-WRP-{today.strftime('%d%m')}-A",
            "quantity": 50.0,
            "unit_cost": 7500.0,
            "suggested_expiration": (today + timedelta(days=3)).isoformat(),
            "confidence_score": 0.98
        },
        {
            "product_name": "Yogurt Natural Gourmet 150ml",
            "sku_match": "REF-YOG-004",
            "suggested_product_id": "prod-yogurt",
            "lot_number": f"L-YOG-{today.strftime('%d%m')}",
            "quantity": 100.0,
            "unit_cost": 2400.0,
            "suggested_expiration": (today + timedelta(days=14)).isoformat(),
            "confidence_score": 0.96
        },
        {
            "product_name": "Porción Fruta Picada Selección",
            "sku_match": "REF-FRUT-002",
            "suggested_product_id": "prod-fruta-pic",
            "lot_number": f"L-FRU-{today.strftime('%d%m')}",
            "quantity": 60.0,
            "unit_cost": 3150.0,
            "suggested_expiration": (today + timedelta(days=2)).isoformat(),
            "confidence_score": 0.92
        }
    ]

    return {
        "status": "PARSED_SUCCESSFULLY",
        "supplier_identified": {
            "id": "sup-andina",
            "name": "Distribuidora Láctea Andina SAS",
            "nit": "900.123.456-1",
            "confidence": 0.99
        },
        "invoice_metadata": {
            "invoice_number": f"FE-{random.randint(10000, 99999)}",
            "issue_date": today.isoformat(),
            "subtotal_cop": 795000.0,
            "total_items_count": len(extracted_items)
        },
        "extracted_items": extracted_items,
        "ai_processing_time_ms": 320,
        "agent_model": "Avrora-Vision-OCR-v2.1"
    }
