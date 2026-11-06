"""Unit and integration tests for Refribreak Procurement, Supplier Comparison and Replenishment.
Level: unit | integration | api
Prevents: Blind purchasing without stock checking, flawed price comparisons, and unlinked PO receiving.
Isolation: Uses SQLite test database with seed catalog.
Covers: Smart replenishment suggestions, RFQ quotes, multi-criteria comparison matrix, PO awarding and FEFO receiving.
"""
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.database import init_db, get_db_cursor
from src.services.purchase_service import (
    get_replenishment_suggestions,
    create_purchase_requisition,
    get_purchase_requisitions,
    get_purchase_requisition_detail,
    add_supplier_quotation,
    compare_quotations,
    award_quotation_and_create_po,
    get_purchase_orders,
    receive_purchase_order
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    init_db()


def test_replenishment_suggestions():
    """Validates that replenishment suggestions detect products below min_stock or with deficits."""
    suggestions = get_replenishment_suggestions(warehouse_id="wh-bog-central")
    assert isinstance(suggestions, list)
    # Suggestions should exist from catalog
    for s in suggestions:
        assert "product_id" in s
        assert "min_stock" in s
        assert "available_qty" in s
        assert "suggested_qty" in s
        assert s["suggested_qty"] > 0
        assert s["urgency"] in ["CRITICAL", "LOW_STOCK", "NORMAL"]


def test_create_requisition_and_add_quotes():
    """Tests creating an RFQ requisition and registering competing supplier quotations."""
    # 1. Create requisition
    items = [
        {"product_id": "prod-wrap-exp", "requested_qty": 30.0, "estimated_unit_cost": 7500.0},
        {"product_id": "prod-fruta-pic", "requested_qty": 40.0, "estimated_unit_cost": 3200.0}
    ]
    req = create_purchase_requisition(
        warehouse_id="wh-bog-central",
        origin="INVENTORY_SUGGESTION",
        notes="Test RFQ for events",
        items=items,
        user_alias="diego"
    )
    assert req["id"].startswith("req-")
    assert req["status"] == "DRAFT"
    assert len(req["items"]) == 2

    # 2. Add Supplier 1 Quote (Cheaper: sup-andina)
    q1 = add_supplier_quotation(
        requisition_id=req["id"],
        supplier_id="sup-andina",
        quotation_number="COT-TEST-01",
        delivery_days=3,
        payment_terms="Crédito 15 días",
        shipping_cost=0.0,
        notes="Free shipping",
        items=[
            {"product_id": "prod-wrap-exp", "unit_cost": 7000.0},
            {"product_id": "prod-fruta-pic", "unit_cost": 3000.0}
        ],
        user_alias="diego"
    )
    # Total: (30 * 7000) + (40 * 3000) = 210000 + 120000 = 330,000 COP
    assert q1["total_amount"] == 330000.0

    # 3. Add Supplier 2 Quote (Faster: sup-empaques, 1 day, but more expensive)
    q2 = add_supplier_quotation(
        requisition_id=req["id"],
        supplier_id="sup-empaques",
        quotation_number="COT-TEST-02",
        delivery_days=1,
        payment_terms="Contado",
        shipping_cost=10000.0,
        notes="Express delivery",
        items=[
            {"product_id": "prod-wrap-exp", "unit_cost": 7500.0},
            {"product_id": "prod-fruta-pic", "unit_cost": 3400.0}
        ],
        user_alias="diego"
    )
    # Total: (30 * 7500) + (40 * 3400) + 10000 = 225000 + 136000 + 10000 = 371,000 COP
    assert q2["total_amount"] == 371000.0

    # 4. Run Comparison Matrix
    comparison = compare_quotations(req["id"])
    assert comparison["requisition_id"] == req["id"]
    assert len(comparison["suppliers"]) == 2
    assert len(comparison["items"]) == 2

    # Verify best price identification
    cards = {c["supplier_id"]: c for c in comparison["suppliers"]}
    assert cards["sup-andina"]["is_cheapest"] is True
    assert cards["sup-andina"]["recommendation_badge"] in ["MEJOR_PRECIO", "MEJOR_PRECIO_Y_RAPIDO"]
    assert cards["sup-empaques"]["is_fastest"] is True
    assert cards["sup-empaques"]["recommendation_badge"] == "ENTREGA_MAS_RAPIDA"
    # Savings should be 371000 - 330000 = 41000
    assert cards["sup-andina"]["savings_cop"] == 41000.0

    # 5. Award cheapest quotation and generate Purchase Order
    po = award_quotation_and_create_po(quotation_id=q1["id"], user_alias="diego")
    assert po["id"].startswith("po-")
    assert po["consecutive_oc"].startswith("OC-")
    assert po["status"] == "ISSUED"
    assert po["supplier_id"] == "sup-andina"
    assert po["total_amount"] == 330000.0
    assert len(po["items"]) == 2

    # 6. Receive physical goods from PO into warehouse
    receipt = receive_purchase_order(po_id=po["id"], user_alias="diego")
    assert receipt["status"] == "SUCCESS"
    assert len(receipt["lots_created"]) == 2
    assert "movement_consecutive" in receipt


def test_purchases_rest_api():
    """Validates end-to-end REST API endpoints for procurement."""
    # 1. Suggestions endpoint
    res = client.get("/api/v1/purchases/replenishment-suggestions?warehouse_id=wh-bog-central")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)

    # 2. Seeded sample requisition comparison endpoint
    res_comp = client.get("/api/v1/purchases/requisitions/req-sample-01/compare")
    assert res_comp.status_code == 200
    comp_data = res_comp.json()
    assert comp_data["requisition_consecutive"] == "REQ-2026-0001"
    assert len(comp_data["suppliers"]) >= 2
    assert len(comp_data["items"]) == 3

    # 3. List purchase orders endpoint
    res_orders = client.get("/api/v1/purchases/orders")
    assert res_orders.status_code == 200
    orders = res_orders.json()
    assert isinstance(orders, list)
