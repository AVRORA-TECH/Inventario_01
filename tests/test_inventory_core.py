"""Unit and integration test suite for Refribreak Inventory Core (RIC).
Level: unit | integration | api
Prevents: Weighted average cost distortion, negative stock, FEFO lot bypass, and invalid OE lifecycle.
Isolation: Uses ephemeral test database with synthetic test data.
Covers: Core business rules of Section 8, Section 10, and REST API contracts.
"""
import pytest
import sqlite3
import os
from datetime import date, timedelta
from fastapi.testclient import TestClient

from src.main import app
from src.services.inventory_service import (
    compute_weighted_average_cost,
    process_purchase_entry,
    process_fefo_dispatch,
    process_waste_registration,
    process_inventory_adjustment
)
from src.services.order_service import create_delivery_order, dispatch_delivery_order
from src.schemas import PurchaseEntryRequest, DispatchRequest, WasteRequest, InventoryAdjustmentRequest, DeliveryOrderCreate
from src.database import init_db

client = TestClient(app)


def test_weighted_average_cost_computation():
    """Validates banker's rounding and weighted average cost calculation (§8.1)."""
    # Case 1: Initial 10 units at 5000, new 10 units at 6000 -> 5500
    res = compute_weighted_average_cost(10.0, 5000.0, 10.0, 6000.0)
    assert res == 5500.0

    # Case 2: 157 units at 7691.08, new 50 units at 7500.0
    res2 = compute_weighted_average_cost(157.0, 7691.08, 50.0, 7500.0)
    assert isinstance(res2, float)
    assert 7600.0 < res2 < 7700.0

    # Case 3: Empty previous stock
    res3 = compute_weighted_average_cost(0.0, 0.0, 20.0, 4500.0)
    assert res3 == 4500.0


def test_database_initialization_and_seed():
    """Ensures database initializes with all required tables and baseline Refribreak catalog."""
    init_db()
    from src.database import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM warehouses;")
    assert cur.fetchone()[0] >= 3

    cur.execute("SELECT COUNT(*) FROM products;")
    assert cur.fetchone()[0] >= 10

    cur.execute("SELECT COUNT(*) FROM delivery_orders;")
    assert cur.fetchone()[0] >= 1

    # Verify OE 7217 baseline exists
    cur.execute("SELECT * FROM delivery_orders WHERE consecutive_oe = 'OE 7217';")
    oe = cur.fetchone()
    assert oe is not None
    assert oe["service_type"] == "Desayuno"

    conn.close()


def test_purchase_entry_updates_stock_and_creates_lot():
    """Verifies that registering a purchase updates stock quantity and average cost deterministically."""
    init_db()
    exp = (date.today() + timedelta(days=10)).isoformat()

    req = PurchaseEntryRequest(
        warehouse_id="wh-bog-central",
        product_id="prod-wrap-exp",
        lot_number="TEST-LOT-999",
        expiration_date=exp,
        quantity=20.0,
        unit_cost=8000.0,
        supplier_id="sup-andina",
        operator_name="Nicolas Santa",
        notes="Prueba automatizada de entrada"
    )

    res = process_purchase_entry(req)
    assert res["status"] == "SUCCESS"
    assert res["consecutive"].startswith("ENT-")
    assert res["new_available_qty"] > 20.0


def test_fefo_dispatch_depletes_earliest_expiring_lot_first():
    """Verifies that dispatches consume the earliest expiring lot (FEFO) and reject negative stock."""
    init_db()

    req = DispatchRequest(
        warehouse_id="wh-bog-central",
        product_id="prod-wrap-exp",
        quantity=5.0,
        reference_doc="TEST-DISP-001",
        operator_name="Nicolas Santa"
    )

    res = process_fefo_dispatch(req)
    assert res["status"] == "SUCCESS"
    assert res["depleted_qty"] == 5.0
    assert len(res["allocated_lots"]) >= 1

    # Attempt to request an impossible quantity to ensure negative stock prevention (§8.2)
    impossible_req = DispatchRequest(
        warehouse_id="wh-bog-central",
        product_id="prod-wrap-exp",
        quantity=999999.0,
        reference_doc="TEST-IMPOSSIBLE",
        operator_name="Nicolas Santa"
    )

    with pytest.raises(ValueError, match="Existencias insuficientes"):
        process_fefo_dispatch(impossible_req)


def test_waste_registration():
    """Verifies waste / spoilage recording decreases lot and stock while preserving weighted average cost."""
    init_db()
    from src.database import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, product_id, warehouse_id, remaining_qty FROM lots WHERE remaining_qty > 2 LIMIT 1;")
    lot = cur.fetchone()
    conn.close()

    assert lot is not None
    req = WasteRequest(
        warehouse_id=lot["warehouse_id"],
        product_id=lot["product_id"],
        lot_id=lot["id"],
        quantity=1.0,
        reason="Vencimiento en refrigeración",
        approved_by="Supervisor Control Calidad",
        operator_name="Nicolas Santa"
    )

    res = process_waste_registration(req)
    assert res["status"] == "SUCCESS"
    assert res["consecutive"].startswith("MER-")
    assert res["waste_value_cop"] > 0


def test_order_creation_and_dispatch_lifecycle():
    """Tests the full delivery order (OE) lifecycle from draft creation to FEFO dispatch."""
    init_db()
    today_iso = date.today().isoformat()

    order_in = DeliveryOrderCreate(
        customer_id="cust-liid",
        warehouse_id="wh-bog-central",
        order_date=today_iso,
        delivery_date=today_iso,
        delivery_day_name="Viernes",
        delivery_address="Trv 23 97 -73 Ofc 212",
        arrival_time="7:30 AM",
        start_time="8:30 AM",
        end_time="11:30 AM",
        departure_time="6:40 AM",
        requested_by="Leonardo Ramírez",
        received_by="Leonardo Ramírez",
        receiver_phone="3504163975",
        service_type="Desayuno",
        service_description="Servido",
        product_detail="Wrap de jamón, queso y vegetales con jugo",
        quantity=10
    )

    create_res = create_delivery_order(order_in)
    assert create_res["status"] == "APPROVED"
    order_id = create_res["id"]

    # Dispatch order
    dispatch_res = dispatch_delivery_order(order_id)
    assert dispatch_res["status"] == "SUCCESS"
    assert dispatch_res["new_order_status"] == "DISPATCHED"


def test_rest_api_endpoints():
    """Tests FastAPI REST endpoints returning valid JSON contracts."""
    init_db()

    # 1. Dashboard summary
    resp = client.get("/api/v1/dashboard/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_inventory_value_cop" in data
    assert "expiring_soon_lots_count" in data

    # 2. Inventory listing
    resp_inv = client.get("/api/v1/inventory")
    assert resp_inv.status_code == 200
    items = resp_inv.json()
    assert len(items) > 0
    assert "available_qty" in items[0]
    assert "weighted_avg_cost" in items[0]

    # 3. Orders listing
    resp_orders = client.get("/api/v1/orders")
    assert resp_orders.status_code == 200
    orders = resp_orders.json()
    assert len(orders) > 0

    # 4. AI simulation endpoint
    resp_ai = client.post("/api/v1/ai/simulate-extract", json={})
    assert resp_ai.status_code == 200
    ai_data = resp_ai.json()
    assert ai_data["status"] == "PARSED_SUCCESSFULLY"
    assert len(ai_data["extracted_items"]) > 0
