"""REST API Routers for Refribreak Inventory Core (RIC).
All endpoints strictly return and consume JSON.
"""
from fastapi import APIRouter, HTTPException, Query, status
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import json

from src.database import get_db_cursor
from src.schemas import (
    WarehouseResponse, CategoryResponse, ProductCreate, ProductResponse,
    StockItemResponse, LotItemResponse, PurchaseEntryRequest, DispatchRequest,
    WasteRequest, InventoryAdjustmentRequest, DeliveryOrderCreate, DeliveryOrderResponse,
    DashboardSummary, AiInvoiceSimulationRequest
)
from src.services.inventory_service import (
    process_purchase_entry, process_fefo_dispatch,
    process_waste_registration, process_inventory_adjustment
)
from src.services.order_service import create_delivery_order, dispatch_delivery_order
from src.services.ai_service import extract_invoice_data

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/dashboard/summary", response_model=DashboardSummary)
def get_dashboard_summary(warehouse_id: Optional[str] = None):
    """Returns high-level operational metrics and urgent alerts."""
    today = date.today()
    alert_date = (today + timedelta(days=7)).isoformat()

    with get_db_cursor() as cur:
        # Inventory value & total units
        if warehouse_id:
            cur.execute("""
                SELECT 
                    COALESCE(SUM(available_qty * weighted_avg_cost), 0.0) as total_value,
                    COALESCE(SUM(available_qty), 0.0) as total_units
                FROM stock 
                WHERE warehouse_id = ?;
            """, (warehouse_id,))
        else:
            cur.execute("""
                SELECT 
                    COALESCE(SUM(available_qty * weighted_avg_cost), 0.0) as total_value,
                    COALESCE(SUM(available_qty), 0.0) as total_units
                FROM stock;
            """)
        val_row = cur.fetchone()
        total_val = round(val_row["total_value"], 2)
        total_units = round(val_row["total_units"], 1)

        # Critical stock count
        if warehouse_id:
            cur.execute("""
                SELECT COUNT(*) 
                FROM stock s 
                JOIN products p ON s.product_id = p.id 
                WHERE s.warehouse_id = ? AND s.available_qty < p.min_stock;
            """, (warehouse_id,))
        else:
            cur.execute("""
                SELECT COUNT(*) 
                FROM stock s 
                JOIN products p ON s.product_id = p.id 
                WHERE s.available_qty < p.min_stock;
            """)
        crit_count = cur.fetchone()[0]

        # Expiring soon lots (< 7 days)
        if warehouse_id:
            cur.execute("""
                SELECT COUNT(*) 
                FROM lots 
                WHERE warehouse_id = ? AND remaining_qty > 0 AND status = 'AVAILABLE' 
                AND expiration_date <= ? AND expiration_date >= ?;
            """, (warehouse_id, alert_date, today.isoformat()))
        else:
            cur.execute("""
                SELECT COUNT(*) 
                FROM lots 
                WHERE remaining_qty > 0 AND status = 'AVAILABLE' 
                AND expiration_date <= ? AND expiration_date >= ?;
            """, (alert_date, today.isoformat()))
        exp_count = cur.fetchone()[0]

        # Delivery orders
        cur.execute("SELECT COUNT(*) FROM delivery_orders;")
        total_orders = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM delivery_orders WHERE status IN ('APPROVED', 'DRAFT');")
        pending_orders = cur.fetchone()[0]

        # Monthly waste value
        cur.execute("""
            SELECT COALESCE(SUM(total_cost), 0.0) 
            FROM movements 
            WHERE movement_type = 'WASTE' AND created_at >= date('now', 'start of month');
        """)
        waste_val = round(cur.fetchone()[0], 2)

        # Active warehouses
        cur.execute("SELECT COUNT(*) FROM warehouses WHERE is_active = 1;")
        active_whs = cur.fetchone()[0]

        return DashboardSummary(
            total_inventory_value_cop=total_val,
            total_available_units=total_units,
            critical_stock_count=crit_count,
            expiring_soon_lots_count=exp_count,
            total_delivery_orders=total_orders,
            pending_delivery_orders=pending_orders,
            monthly_waste_value_cop=waste_val,
            active_warehouses_count=active_whs
        )


@api_router.get("/warehouses", response_model=List[WarehouseResponse])
def list_warehouses():
    with get_db_cursor() as cur:
        cur.execute("SELECT id, name, code, address, city, is_active FROM warehouses WHERE is_active = 1 ORDER BY name;")
        return [dict(row) for row in cur.fetchall()]


@api_router.get("/categories", response_model=List[CategoryResponse])
def list_categories():
    with get_db_cursor() as cur:
        cur.execute("SELECT id, name, slug, is_perishable, default_alert_days, description FROM categories ORDER BY name;")
        return [dict(row) for row in cur.fetchall()]


@api_router.get("/products", response_model=List[ProductResponse])
def list_products(category_id: Optional[str] = None):
    with get_db_cursor() as cur:
        if category_id:
            cur.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name, p.unit, 
                       p.is_perishable, p.shelf_life_days, p.min_stock, p.description, p.created_at
                FROM products p
                JOIN categories c ON p.category_id = c.id
                WHERE p.category_id = ?
                ORDER BY p.name;
            """, (category_id,))
        else:
            cur.execute("""
                SELECT p.id, p.sku, p.name, p.category_id, c.name as category_name, p.unit, 
                       p.is_perishable, p.shelf_life_days, p.min_stock, p.description, p.created_at
                FROM products p
                JOIN categories c ON p.category_id = c.id
                ORDER BY p.name;
            """)
        return [dict(row) for row in cur.fetchall()]


@api_router.post("/products", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(prod: ProductCreate):
    import uuid
    prod_id = f"prod-{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now().isoformat()

    with get_db_cursor() as cur:
        cur.execute("SELECT id FROM products WHERE sku = ?;", (prod.sku,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Ya existe un producto con este SKU.")

        cur.execute(
            """INSERT INTO products (id, sku, name, category_id, unit, is_perishable, shelf_life_days, min_stock, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);""",
            (prod_id, prod.sku, prod.name, prod.category_id, prod.unit, int(prod.is_perishable), prod.shelf_life_days, prod.min_stock, prod.description, now_iso)
        )
        # Create zero stock for all warehouses
        cur.execute("SELECT id FROM warehouses;")
        whs = cur.fetchall()
        for wh in whs:
            stk_id = f"stk-{uuid.uuid4().hex[:10]}"
            cur.execute(
                "INSERT INTO stock (id, product_id, warehouse_id, available_qty, reserved_qty, weighted_avg_cost, updated_at) VALUES (?, ?, ?, 0.0, 0.0, 0.0, ?);",
                (stk_id, prod_id, wh["id"], now_iso)
            )

        cur.execute("SELECT name FROM categories WHERE id = ?;", (prod.category_id,))
        cat_name = cur.fetchone()["name"]

        return ProductResponse(
            id=prod_id,
            sku=prod.sku,
            name=prod.name,
            category_id=prod.category_id,
            category_name=cat_name,
            unit=prod.unit,
            is_perishable=prod.is_perishable,
            shelf_life_days=prod.shelf_life_days,
            min_stock=prod.min_stock,
            description=prod.description,
            created_at=now_iso
        )


@api_router.get("/inventory", response_model=List[StockItemResponse])
def get_inventory_status(
    warehouse_id: Optional[str] = None,
    category_id: Optional[str] = None,
    query: Optional[str] = None
):
    """Detailed inventory matrix inspired by Sellerskills & Airtable schemas."""
    today = date.today()

    sql = """
        SELECT 
            s.id, s.product_id, p.name as product_name, p.sku, p.category_id, c.name as category_name,
            p.unit, p.is_perishable, s.warehouse_id, w.name as warehouse_name,
            s.available_qty, s.reserved_qty, (s.available_qty + s.reserved_qty) as total_on_hand,
            s.weighted_avg_cost, (s.available_qty * s.weighted_avg_cost) as total_value_cop,
            p.min_stock,
            (SELECT MIN(expiration_date) FROM lots l WHERE l.product_id = s.product_id AND l.warehouse_id = s.warehouse_id AND l.remaining_qty > 0 AND l.status = 'AVAILABLE') as earliest_expiration
        FROM stock s
        JOIN products p ON s.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        JOIN warehouses w ON s.warehouse_id = w.id
        WHERE 1=1
    """
    params = []

    if warehouse_id:
        sql += " AND s.warehouse_id = ?"
        params.append(warehouse_id)
    if category_id:
        sql += " AND p.category_id = ?"
        params.append(category_id)
    if query:
        sql += " AND (p.name LIKE ? OR p.sku LIKE ?)"
        wild = f"%{query}%"
        params.extend([wild, wild])

    sql += " ORDER BY p.name ASC;"

    with get_db_cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        items = []
        for r in rows:
            avail = r["available_qty"]
            min_s = r["min_stock"]
            earliest = r["earliest_expiration"]
            days_left = None
            exp_status = "NON_PERISHABLE"

            if r["is_perishable"] and earliest:
                try:
                    exp_date = date.fromisoformat(earliest)
                    days_left = (exp_date - today).days
                    if days_left < 0:
                        exp_status = "EXPIRED"
                    elif days_left <= 7:
                        exp_status = "WARNING_EXPIRING_SOON"
                    else:
                        exp_status = "OK"
                except Exception:
                    pass

            items.append(StockItemResponse(
                id=r["id"],
                product_id=r["product_id"],
                product_name=r["product_name"],
                sku=r["sku"],
                category_id=r["category_id"],
                category_name=r["category_name"],
                unit=r["unit"],
                is_perishable=bool(r["is_perishable"]),
                warehouse_id=r["warehouse_id"],
                warehouse_name=r["warehouse_name"],
                available_qty=round(avail, 2),
                reserved_qty=round(r["reserved_qty"], 2),
                total_on_hand=round(r["total_on_hand"], 2),
                weighted_avg_cost=round(r["weighted_avg_cost"], 2),
                total_value_cop=round(r["total_value_cop"], 2),
                min_stock=round(min_s, 2),
                is_under_min=(avail < min_s),
                earliest_expiration=earliest,
                days_to_expiration=days_left,
                expiration_status=exp_status
            ))
        return items


@api_router.get("/lots", response_model=List[LotItemResponse])
def list_lots(warehouse_id: Optional[str] = None, only_active: bool = True):
    """Returns active FEFO lots with expiration countdowns."""
    today = date.today()
    sql = """
        SELECT 
            l.id, l.lot_number, l.product_id, p.name as product_name,
            l.warehouse_id, w.name as warehouse_name,
            l.initial_qty, l.remaining_qty, l.unit_cost,
            l.reception_date, l.expiration_date,
            s.name as supplier_name, l.status
        FROM lots l
        JOIN products p ON l.product_id = p.id
        JOIN warehouses w ON l.warehouse_id = w.id
        LEFT JOIN suppliers s ON l.supplier_id = s.id
        WHERE 1=1
    """
    params = []
    if warehouse_id:
        sql += " AND l.warehouse_id = ?"
        params.append(warehouse_id)
    if only_active:
        sql += " AND l.remaining_qty > 0 AND l.status = 'AVAILABLE'"

    sql += " ORDER BY l.expiration_date ASC;"

    with get_db_cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        lots = []
        for r in rows:
            try:
                exp_date = date.fromisoformat(r["expiration_date"])
                days_to_exp = (exp_date - today).days
            except Exception:
                days_to_exp = 999

            lots.append(LotItemResponse(
                id=r["id"],
                lot_number=r["lot_number"],
                product_id=r["product_id"],
                product_name=r["product_name"],
                warehouse_id=r["warehouse_id"],
                warehouse_name=r["warehouse_name"],
                initial_qty=round(r["initial_qty"], 2),
                remaining_qty=round(r["remaining_qty"], 2),
                unit_cost=round(r["unit_cost"], 2),
                reception_date=r["reception_date"],
                expiration_date=r["expiration_date"],
                supplier_name=r["supplier_name"],
                status=r["status"],
                days_to_expiration=days_to_exp,
                is_expiring_soon=(0 <= days_to_exp <= 7),
                is_expired=(days_to_exp < 0)
            ))
        return lots


@api_router.post("/movements/entry")
def register_purchase_entry(req: PurchaseEntryRequest):
    try:
        res = process_purchase_entry(req)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/movements/exit")
def register_fefo_dispatch(req: DispatchRequest):
    try:
        res = process_fefo_dispatch(req)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/movements/waste")
def register_waste(req: WasteRequest):
    try:
        res = process_waste_registration(req)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.post("/movements/adjustment")
def register_adjustment(req: InventoryAdjustmentRequest):
    try:
        res = process_inventory_adjustment(req)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/movements")
def list_movements(limit: int = 50, warehouse_id: Optional[str] = None):
    """Returns kardex movements history."""
    sql = """
        SELECT m.id, m.consecutive, m.movement_type, m.warehouse_id, w.name as warehouse_name,
               m.status, m.reference_doc, m.operator_name, m.notes, m.total_cost, m.created_at,
               (SELECT COUNT(*) FROM movement_lines ml WHERE ml.movement_id = m.id) as lines_count
        FROM movements m
        JOIN warehouses w ON m.warehouse_id = w.id
        WHERE 1=1
    """
    params = []
    if warehouse_id:
        sql += " AND m.warehouse_id = ?"
        params.append(warehouse_id)

    sql += " ORDER BY m.created_at DESC LIMIT ?;"
    params.append(limit)

    with get_db_cursor() as cur:
        cur.execute(sql, tuple(params))
        return [dict(r) for r in cur.fetchall()]


@api_router.get("/orders", response_model=List[DeliveryOrderResponse])
def list_delivery_orders(status_filter: Optional[str] = None):
    """Lists Delivery Orders (OE) formatted for the Orders table view."""
    sql = """
        SELECT o.*, c.name as customer_name, c.nit as customer_nit, w.name as warehouse_name
        FROM delivery_orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN warehouses w ON o.warehouse_id = w.id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND o.status = ?"
        params.append(status_filter)

    sql += " ORDER BY o.consecutive_oe DESC;"

    with get_db_cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("equipment_json"):
                try:
                    d["equipment"] = json.loads(d["equipment_json"])
                except Exception:
                    d["equipment"] = {}
            results.append(DeliveryOrderResponse(**d))
        return results


@api_router.post("/orders", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
def create_order(req: DeliveryOrderCreate):
    try:
        return create_delivery_order(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/orders/{order_id}")
def get_order_detail(order_id: str):
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT o.*, c.name as customer_name, c.nit as customer_nit, c.phone as customer_phone, w.name as warehouse_name
            FROM delivery_orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN warehouses w ON o.warehouse_id = w.id
            WHERE o.id = ?;
        """, (order_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Orden de entrega no encontrada.")

        d = dict(row)
        if d.get("equipment_json"):
            try:
                d["equipment"] = json.loads(d["equipment_json"])
            except Exception:
                d["equipment"] = {}
        return d


@api_router.post("/orders/{order_id}/dispatch")
def dispatch_order_endpoint(order_id: str):
    try:
        return dispatch_delivery_order(order_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@api_router.get("/customers")
def list_customers():
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM customers ORDER BY name;")
        return [dict(r) for r in cur.fetchall()]


@api_router.get("/suppliers")
def list_suppliers():
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM suppliers ORDER BY name;")
        return [dict(r) for r in cur.fetchall()]


@api_router.get("/audit")
def list_audit_logs(limit: int = 50):
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?;", (limit,))
        logs = []
        for r in cur.fetchall():
            d = dict(r)
            try:
                d["details"] = json.loads(d["details_json"])
            except Exception:
                d["details"] = {}
            logs.append(d)
        return logs


@api_router.post("/ai/simulate-extract")
def simulate_ai_extraction(req: AiInvoiceSimulationRequest):
    """Simulates AI OCR invoice reading for rapid receiving."""
    return extract_invoice_data(raw_text=req.raw_text, supplier_hint=req.supplier_hint)
