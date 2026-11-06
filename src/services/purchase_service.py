"""Domain purchase and supplier comparison service for Refribreak Inventory Core (RIC).
Handles smart replenishment suggestions based on min stock, RFQ supplier quotes,
multi-criteria quotation comparison matrix, PO awarding, and inventory reception.
"""
from datetime import datetime, date, timedelta
import uuid
from typing import Dict, Any, List, Optional
from src.database import get_db_cursor
from src.services.inventory_service import compute_weighted_average_cost, record_audit


def get_replenishment_suggestions(warehouse_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Calculates replenishment needs based on min_stock, available_qty, and reserved_qty."""
    with get_db_cursor() as cur:
        query = """
        SELECT 
            p.id AS product_id,
            p.sku,
            p.name AS product_name,
            c.name AS category_name,
            p.unit,
            p.min_stock,
            w.id AS warehouse_id,
            w.name AS warehouse_name,
            COALESCE(s.available_qty, 0.0) AS available_qty,
            COALESCE(s.reserved_qty, 0.0) AS reserved_qty,
            COALESCE(s.weighted_avg_cost, 0.0) AS last_unit_cost
        FROM products p
        JOIN categories c ON p.category_id = c.id
        CROSS JOIN warehouses w
        LEFT JOIN stock s ON s.product_id = p.id AND s.warehouse_id = w.id
        WHERE w.is_active = 1
        """
        params = []
        if warehouse_id:
            query += " AND w.id = ?"
            params.append(warehouse_id)

        cur.execute(query, params)
        rows = cur.fetchall()

    suggestions = []
    for r in rows:
        avail = float(r["available_qty"])
        reserved = float(r["reserved_qty"])
        min_stk = float(r["min_stock"])
        cost = float(r["last_unit_cost"])

        # Deficit calculation: needed to restore min_stock plus fulfill current reservations
        net_stock = avail - reserved
        deficit = max(0.0, min_stk - net_stock)

        # We flag anything that is below or near min_stock
        if deficit > 0 or avail <= min_stk:
            suggested = round(deficit if deficit > 0 else (min_stk - avail + 5.0), 1)
            if suggested <= 0:
                suggested = 10.0

            if avail <= 0:
                urgency = "CRITICAL"
            elif avail < min_stk * 0.5:
                urgency = "CRITICAL"
            elif avail <= min_stk:
                urgency = "LOW_STOCK"
            else:
                urgency = "NORMAL"

            suggestions.append({
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "sku": r["sku"],
                "category_name": r["category_name"],
                "unit": r["unit"],
                "warehouse_id": r["warehouse_id"],
                "warehouse_name": r["warehouse_name"],
                "available_qty": avail,
                "reserved_qty": reserved,
                "min_stock": min_stk,
                "deficit_qty": round(deficit, 1),
                "suggested_qty": suggested,
                "last_unit_cost": cost,
                "estimated_total_cost": round(suggested * cost, 2),
                "urgency": urgency
            })

    # Sort critical first, then highest deficit
    urgency_order = {"CRITICAL": 0, "LOW_STOCK": 1, "NORMAL": 2}
    suggestions.sort(key=lambda x: (urgency_order.get(x["urgency"], 3), -x["deficit_qty"]))
    return suggestions


def create_purchase_requisition(
    warehouse_id: str,
    origin: str,
    notes: Optional[str],
    items: List[Dict[str, Any]],
    user_alias: str = "diego"
) -> Dict[str, Any]:
    """Creates a new purchase requisition (RFQ baseline)."""
    now_iso = datetime.now().isoformat()
    req_id = f"req-{uuid.uuid4().hex[:10]}"

    with get_db_cursor() as cur:
        # Validate warehouse
        cur.execute("SELECT name FROM warehouses WHERE id = ?;", (warehouse_id,))
        wh = cur.fetchone()
        if not wh:
            raise ValueError(f"Bodega con ID {warehouse_id} no existe.")

        # Generate consecutive REQ-YYYY-XXXX
        year = datetime.now().year
        cur.execute("SELECT COUNT(*) FROM purchase_requisitions;")
        count = cur.fetchone()[0] + 1
        consecutive = f"REQ-{year}-{count:04d}"

        cur.execute("""
        INSERT INTO purchase_requisitions (id, consecutive, warehouse_id, status, origin, notes, created_by, created_at)
        VALUES (?, ?, ?, 'DRAFT', ?, ?, ?, ?);
        """, (req_id, consecutive, warehouse_id, origin, notes, user_alias, now_iso))

        for it in items:
            item_id = f"ritem-{uuid.uuid4().hex[:10]}"
            # Look up current stock and min_stock
            cur.execute("""
            SELECT COALESCE(s.available_qty, 0.0) AS cur_stock, p.min_stock
            FROM products p
            LEFT JOIN stock s ON s.product_id = p.id AND s.warehouse_id = ?
            WHERE p.id = ?;
            """, (warehouse_id, it["product_id"]))
            p_data = cur.fetchone()
            cur_stock = float(p_data["cur_stock"]) if p_data else 0.0
            min_stk = float(p_data["min_stock"]) if p_data else 0.0

            cur.execute("""
            INSERT INTO purchase_requisition_items (id, requisition_id, product_id, current_stock, min_stock, requested_qty, estimated_unit_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                item_id,
                req_id,
                it["product_id"],
                cur_stock,
                min_stk,
                float(it["requested_qty"]),
                float(it.get("estimated_unit_cost", 0.0))
            ))

        record_audit(
            cur,
            user_alias,
            "CREATE_PURCHASE_REQUISITION",
            "PURCHASE_REQUISITION",
            req_id,
            {"consecutive": consecutive, "items_count": len(items), "origin": origin}
        )

    return get_purchase_requisition_detail(req_id)


def get_purchase_requisitions(
    warehouse_id: Optional[str] = None,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Lists purchase requisitions with summary counts."""
    with get_db_cursor() as cur:
        query = """
        SELECT 
            r.id,
            r.consecutive,
            r.warehouse_id,
            w.name AS warehouse_name,
            r.status,
            r.origin,
            r.notes,
            r.created_by,
            r.created_at,
            (SELECT COUNT(*) FROM purchase_requisition_items WHERE requisition_id = r.id) AS items_count,
            (SELECT COUNT(*) FROM supplier_quotations WHERE requisition_id = r.id) AS quotations_count
        FROM purchase_requisitions r
        JOIN warehouses w ON r.warehouse_id = w.id
        WHERE 1=1
        """
        params = []
        if warehouse_id:
            query += " AND r.warehouse_id = ?"
            params.append(warehouse_id)
        if status:
            query += " AND r.status = ?"
            params.append(status)

        query += " ORDER BY r.created_at DESC;"
        cur.execute(query, params)
        rows = cur.fetchall()

    return [dict(r) for r in rows]


def get_purchase_requisition_detail(req_id: str) -> Dict[str, Any]:
    """Retrieves full details of a purchase requisition and its items."""
    with get_db_cursor() as cur:
        cur.execute("""
        SELECT 
            r.id,
            r.consecutive,
            r.warehouse_id,
            w.name AS warehouse_name,
            r.status,
            r.origin,
            r.notes,
            r.created_by,
            r.created_at
        FROM purchase_requisitions r
        JOIN warehouses w ON r.warehouse_id = w.id
        WHERE r.id = ?;
        """, (req_id,))
        header = cur.fetchone()
        if not header:
            raise ValueError(f"Solicitud con ID {req_id} no encontrada.")

        cur.execute("""
        SELECT 
            ri.id,
            ri.product_id,
            p.name AS product_name,
            p.sku,
            p.unit,
            ri.current_stock,
            ri.min_stock,
            ri.requested_qty,
            ri.estimated_unit_cost
        FROM purchase_requisition_items ri
        JOIN products p ON ri.product_id = p.id
        WHERE ri.requisition_id = ?
        ORDER BY p.name ASC;
        """, (req_id,))
        items = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM supplier_quotations WHERE requisition_id = ?;", (req_id,))
        q_count = cur.fetchone()[0]

    res = dict(header)
    res["items"] = [dict(it) for it in items]
    res["quotations_count"] = q_count
    return res


def add_supplier_quotation(
    requisition_id: str,
    supplier_id: str,
    quotation_number: Optional[str],
    delivery_days: int,
    payment_terms: str,
    shipping_cost: float,
    notes: Optional[str],
    items: List[Dict[str, Any]],
    user_alias: str = "diego"
) -> Dict[str, Any]:
    """Registers a quotation from a supplier for a specific requisition."""
    now_iso = datetime.now().isoformat()
    quote_id = f"quote-{uuid.uuid4().hex[:10]}"

    with get_db_cursor() as cur:
        # Validate requisition
        cur.execute("SELECT id, status FROM purchase_requisitions WHERE id = ?;", (requisition_id,))
        req = cur.fetchone()
        if not req:
            raise ValueError(f"Solicitud {requisition_id} no existe.")

        # Validate supplier
        cur.execute("SELECT id, name FROM suppliers WHERE id = ?;", (supplier_id,))
        sup = cur.fetchone()
        if not sup:
            raise ValueError(f"Proveedor {supplier_id} no existe.")

        # Compute totals
        items_total = 0.0
        quote_items_to_insert = []
        for it in items:
            cur.execute("SELECT requested_qty FROM purchase_requisition_items WHERE requisition_id = ? AND product_id = ?;",
                        (requisition_id, it["product_id"]))
            req_item = cur.fetchone()
            qty = float(it.get("quantity") or (req_item["requested_qty"] if req_item else 1.0))
            cost = float(it["unit_cost"])
            line_tot = round(qty * cost, 2)
            items_total += line_tot
            quote_items_to_insert.append((
                f"qitem-{uuid.uuid4().hex[:10]}",
                quote_id,
                it["product_id"],
                qty,
                cost,
                line_tot
            ))

        grand_total = round(items_total + float(shipping_cost), 2)

        cur.execute("""
        INSERT INTO supplier_quotations (id, requisition_id, supplier_id, quotation_number, delivery_days, payment_terms, shipping_cost, total_amount, is_awarded, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?);
        """, (
            quote_id,
            requisition_id,
            supplier_id,
            quotation_number or f"COT-{supplier_id[:3].upper()}-{datetime.now().strftime('%m%d')}",
            delivery_days,
            payment_terms,
            float(shipping_cost),
            grand_total,
            notes,
            now_iso
        ))

        cur.executemany("""
        INSERT INTO supplier_quotation_items (id, quotation_id, product_id, quantity, unit_cost, total_cost)
        VALUES (?, ?, ?, ?, ?, ?);
        """, quote_items_to_insert)

        # Update requisition status to QUOTING if DRAFT
        if req["status"] == "DRAFT":
            cur.execute("UPDATE purchase_requisitions SET status = 'QUOTING' WHERE id = ?;", (requisition_id,))

        record_audit(
            cur,
            user_alias,
            "ADD_SUPPLIER_QUOTATION",
            "SUPPLIER_QUOTATION",
            quote_id,
            {"requisition_id": requisition_id, "supplier_name": sup["name"], "total_amount": grand_total}
        )

    return {
        "id": quote_id,
        "requisition_id": requisition_id,
        "supplier_id": supplier_id,
        "supplier_name": sup["name"],
        "total_amount": grand_total,
        "delivery_days": delivery_days,
        "is_awarded": False,
        "created_at": now_iso
    }


def compare_quotations(requisition_id: str) -> Dict[str, Any]:
    """Generates the multi-criteria side-by-side comparison matrix for decision-making."""
    with get_db_cursor() as cur:
        # Requisition info
        cur.execute("""
        SELECT r.id, r.consecutive, r.notes, w.name AS warehouse_name
        FROM purchase_requisitions r
        JOIN warehouses w ON r.warehouse_id = w.id
        WHERE r.id = ?;
        """, (requisition_id,))
        req = cur.fetchone()
        if not req:
            raise ValueError(f"Solicitud {requisition_id} no encontrada.")

        # Requisition items
        cur.execute("""
        SELECT ri.product_id, p.name AS product_name, p.sku, p.unit, ri.requested_qty
        FROM purchase_requisition_items ri
        JOIN products p ON ri.product_id = p.id
        WHERE ri.requisition_id = ?
        ORDER BY p.name ASC;
        """, (requisition_id,))
        req_items = cur.fetchall()

        # All quotations for this requisition
        cur.execute("""
        SELECT 
            q.id AS quotation_id,
            q.supplier_id,
            s.name AS supplier_name,
            s.nit AS supplier_nit,
            q.delivery_days,
            q.payment_terms,
            q.shipping_cost,
            q.total_amount,
            q.is_awarded
        FROM supplier_quotations q
        JOIN suppliers s ON q.supplier_id = s.id
        WHERE q.requisition_id = ?
        ORDER BY q.total_amount ASC;
        """, (requisition_id,))
        quotes = cur.fetchall()

        # Item prices per quotation
        item_prices_by_quote: Dict[str, Dict[str, float]] = {}
        for q in quotes:
            cur.execute("""
            SELECT product_id, unit_cost, quantity, total_cost
            FROM supplier_quotation_items
            WHERE quotation_id = ?;
            """, (q["quotation_id"],))
            q_items = cur.fetchall()
            item_prices_by_quote[q["quotation_id"]] = {it["product_id"]: float(it["unit_cost"]) for it in q_items}

    if not quotes:
        return {
            "requisition_id": req["id"],
            "requisition_consecutive": req["consecutive"],
            "warehouse_name": req["warehouse_name"],
            "notes": req["notes"],
            "items": [],
            "suppliers": [],
            "best_quote_id": None
        }

    # Identify benchmarks
    totals = [float(q["total_amount"]) for q in quotes]
    min_total = min(totals)
    max_total = max(totals)
    min_days = min(int(q["delivery_days"]) for q in quotes)

    # Build supplier summary cards
    supplier_cards = []
    for q in quotes:
        tot = float(q["total_amount"])
        ship = float(q["shipping_cost"])
        days = int(q["delivery_days"])
        is_cheap = (tot == min_total)
        is_fast = (days == min_days)

        savings_cop = round(max_total - tot, 2)
        savings_pct = round((savings_cop / max_total * 100.0) if max_total > 0 else 0.0, 1)

        # Recommendation logic
        if is_cheap and is_fast:
            badge = "MEJOR_PRECIO_Y_RAPIDO"
        elif is_cheap:
            badge = "MEJOR_PRECIO"
        elif is_fast:
            badge = "ENTREGA_MAS_RAPIDA"
        elif savings_pct >= 5.0:
            badge = "RECOMENDADO"
        else:
            badge = "ESTANDAR"

        supplier_cards.append({
            "quotation_id": q["quotation_id"],
            "supplier_id": q["supplier_id"],
            "supplier_name": q["supplier_name"],
            "supplier_nit": q["supplier_nit"],
            "delivery_days": days,
            "payment_terms": q["payment_terms"],
            "items_subtotal": round(tot - ship, 2),
            "shipping_cost": ship,
            "total_amount": tot,
            "savings_cop": savings_cop,
            "savings_pct": savings_pct,
            "is_cheapest": is_cheap,
            "is_fastest": is_fast,
            "recommendation_badge": badge,
            "is_awarded": bool(q["is_awarded"])
        })

    # Build item rows with prices by supplier
    item_rows = []
    for ri in req_items:
        p_id = ri["product_id"]
        prices = {}
        for q in quotes:
            q_id = q["quotation_id"]
            cost = item_prices_by_quote.get(q_id, {}).get(p_id, 0.0)
            prices[q["supplier_id"]] = cost

        # Find lowest price for this specific item
        valid_prices = {k: v for k, v in prices.items() if v > 0}
        lowest_price = min(valid_prices.values()) if valid_prices else 0.0
        lowest_supplier = [k for k, v in valid_prices.items() if v == lowest_price][0] if valid_prices else ""

        item_rows.append({
            "product_id": p_id,
            "product_name": ri["product_name"],
            "sku": ri["sku"],
            "unit": ri["unit"],
            "requested_qty": float(ri["requested_qty"]),
            "prices_by_supplier": prices,
            "lowest_unit_price": lowest_price,
            "lowest_supplier_id": lowest_supplier
        })

    # Pick overall best quote
    best_quote = next((c["quotation_id"] for c in supplier_cards if c["is_cheapest"]), quotes[0]["quotation_id"])

    return {
        "requisition_id": req["id"],
        "requisition_consecutive": req["consecutive"],
        "warehouse_name": req["warehouse_name"],
        "notes": req["notes"],
        "items": item_rows,
        "suppliers": supplier_cards,
        "best_quote_id": best_quote
    }


def award_quotation_and_create_po(
    quotation_id: str,
    user_alias: str = "diego",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Awards the selected quotation and automatically creates the official Purchase Order (OC)."""
    now_iso = datetime.now().isoformat()
    today = date.today()
    po_id = f"po-{uuid.uuid4().hex[:10]}"

    with get_db_cursor() as cur:
        # Load quotation
        cur.execute("""
        SELECT 
            q.id, q.requisition_id, q.supplier_id, q.delivery_days, q.payment_terms,
            q.shipping_cost, q.total_amount, r.warehouse_id, s.name AS supplier_name
        FROM supplier_quotations q
        JOIN purchase_requisitions r ON q.requisition_id = r.id
        JOIN suppliers s ON q.supplier_id = s.id
        WHERE q.id = ?;
        """, (quotation_id,))
        quote = cur.fetchone()
        if not quote:
            raise ValueError(f"Cotización con ID {quotation_id} no existe.")

        req_id = quote["requisition_id"]

        # Award this quotation and clear others
        cur.execute("UPDATE supplier_quotations SET is_awarded = 0 WHERE requisition_id = ?;", (req_id,))
        cur.execute("UPDATE supplier_quotations SET is_awarded = 1 WHERE id = ?;", (quotation_id,))
        cur.execute("UPDATE purchase_requisitions SET status = 'AWARDED' WHERE id = ?;", (req_id,))

        # Generate OC consecutive
        year = today.year
        cur.execute("SELECT COUNT(*) FROM purchase_orders;")
        count = cur.fetchone()[0] + 1
        consecutive_oc = f"OC-{year}-{count:04d}"

        expected_date = (today + timedelta(days=int(quote["delivery_days"]))).isoformat()
        subtotal = float(quote["total_amount"]) - float(quote["shipping_cost"])

        cur.execute("""
        INSERT INTO purchase_orders (
            id, consecutive_oc, requisition_id, quotation_id, supplier_id, warehouse_id,
            status, order_date, expected_delivery_date, payment_terms, subtotal, shipping_cost,
            total_amount, notes, created_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'ISSUED', ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            po_id,
            consecutive_oc,
            req_id,
            quotation_id,
            quote["supplier_id"],
            quote["warehouse_id"],
            today.isoformat(),
            expected_date,
            quote["payment_terms"],
            subtotal,
            float(quote["shipping_cost"]),
            float(quote["total_amount"]),
            notes or f"Adjudicada a {quote['supplier_name']} según análisis comparativo de cotizaciones.",
            user_alias,
            now_iso
        ))

        # Copy line items from quotation
        cur.execute("""
        SELECT product_id, quantity, unit_cost, total_cost
        FROM supplier_quotation_items
        WHERE quotation_id = ?;
        """, (quotation_id,))
        q_items = cur.fetchall()

        po_items = []
        for it in q_items:
            po_items.append((
                f"poitem-{uuid.uuid4().hex[:10]}",
                po_id,
                it["product_id"],
                float(it["quantity"]),
                float(it["unit_cost"]),
                float(it["total_cost"]),
                0.0
            ))

        cur.executemany("""
        INSERT INTO purchase_order_items (id, purchase_order_id, product_id, quantity, unit_cost, total_cost, received_qty)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """, po_items)

        record_audit(
            cur,
            user_alias,
            "AWARD_QUOTATION_AND_CREATE_PO",
            "PURCHASE_ORDER",
            po_id,
            {
                "consecutive_oc": consecutive_oc,
                "quotation_id": quotation_id,
                "supplier_name": quote["supplier_name"],
                "total_amount": float(quote["total_amount"])
            }
        )

    return get_purchase_order_detail(po_id)


def get_purchase_orders(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists purchase orders."""
    with get_db_cursor() as cur:
        query = """
        SELECT 
            po.id,
            po.consecutive_oc,
            po.requisition_id,
            po.quotation_id,
            po.supplier_id,
            s.name AS supplier_name,
            s.nit AS supplier_nit,
            po.warehouse_id,
            w.name AS warehouse_name,
            po.status,
            po.order_date,
            po.expected_delivery_date,
            po.payment_terms,
            po.subtotal,
            po.shipping_cost,
            po.total_amount,
            po.notes,
            po.created_by,
            po.created_at,
            (SELECT COUNT(*) FROM purchase_order_items WHERE purchase_order_id = po.id) AS items_count
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        JOIN warehouses w ON po.warehouse_id = w.id
        WHERE 1=1
        """
        params = []
        if status:
            query += " AND po.status = ?"
            params.append(status)

        query += " ORDER BY po.created_at DESC;"
        cur.execute(query, params)
        rows = cur.fetchall()

    return [dict(r) for r in rows]


def get_purchase_order_detail(po_id: str) -> Dict[str, Any]:
    """Retrieves full details of a purchase order and its lines."""
    with get_db_cursor() as cur:
        cur.execute("""
        SELECT 
            po.id,
            po.consecutive_oc,
            po.requisition_id,
            po.quotation_id,
            po.supplier_id,
            s.name AS supplier_name,
            s.nit AS supplier_nit,
            po.warehouse_id,
            w.name AS warehouse_name,
            po.status,
            po.order_date,
            po.expected_delivery_date,
            po.payment_terms,
            po.subtotal,
            po.shipping_cost,
            po.total_amount,
            po.notes,
            po.created_by,
            po.created_at
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        JOIN warehouses w ON po.warehouse_id = w.id
        WHERE po.id = ?;
        """, (po_id,))
        header = cur.fetchone()
        if not header:
            raise ValueError(f"Orden de compra con ID {po_id} no encontrada.")

        cur.execute("""
        SELECT 
            poi.id,
            poi.product_id,
            p.name AS product_name,
            p.sku,
            p.unit,
            poi.quantity,
            poi.unit_cost,
            poi.total_cost,
            poi.received_qty
        FROM purchase_order_items poi
        JOIN products p ON poi.product_id = p.id
        WHERE poi.purchase_order_id = ?
        ORDER BY p.name ASC;
        """, (po_id,))
        items = cur.fetchall()

    res = dict(header)
    res["items"] = [dict(it) for it in items]
    return res


def receive_purchase_order(
    po_id: str,
    expiration_date_override: Optional[str] = None,
    user_alias: str = "diego",
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Receives goods from an official Purchase Order into warehouse stock with FEFO lots and cost recalculation."""
    now_iso = datetime.now().isoformat()
    today = date.today()

    with get_db_cursor() as cur:
        cur.execute("""
        SELECT po.id, po.consecutive_oc, po.warehouse_id, po.supplier_id, po.status, s.name AS supplier_name
        FROM purchase_orders po
        JOIN suppliers s ON po.supplier_id = s.id
        WHERE po.id = ?;
        """, (po_id,))
        po = cur.fetchone()
        if not po:
            raise ValueError(f"Orden de Compra {po_id} no existe.")

        if po["status"] == "RECEIVED":
            raise ValueError(f"La Orden de Compra {po['consecutive_oc']} ya fue recibida en inventario.")

        cur.execute("""
        SELECT poi.id, poi.product_id, poi.quantity, poi.unit_cost, p.name AS product_name, p.shelf_life_days
        FROM purchase_order_items poi
        JOIN products p ON poi.product_id = p.id
        WHERE poi.purchase_order_id = ?;
        """, (po_id,))
        lines = cur.fetchall()

        if not lines:
            raise ValueError("La Orden de Compra no contiene ítems para recepcionar.")

        warehouse_id = po["warehouse_id"]
        supplier_id = po["supplier_id"]

        # Master movement
        cur.execute("SELECT COUNT(*) FROM movements WHERE movement_type = 'IN_PURCHASE';")
        seq = cur.fetchone()[0] + 1
        mov_consecutive = f"ENT-{seq:05d}"
        mov_id = f"mov-{uuid.uuid4().hex[:10]}"

        total_receipt_value = sum(float(l["quantity"]) * float(l["unit_cost"]) for l in lines)

        cur.execute("""
        INSERT INTO movements (id, consecutive, movement_type, warehouse_id, status, reference_doc, operator_name, notes, total_cost, created_at)
        VALUES (?, ?, 'IN_PURCHASE', ?, 'CONFIRMED', ?, ?, ?, ?, ?);
        """, (
            mov_id,
            mov_consecutive,
            warehouse_id,
            po["consecutive_oc"],
            user_alias,
            notes or f"Recepción física de Orden de Compra {po['consecutive_oc']}",
            round(total_receipt_value, 2),
            now_iso
        ))

        created_lots = []
        for l in lines:
            p_id = l["product_id"]
            qty = float(l["quantity"])
            cost = float(l["unit_cost"])
            shelf_days = int(l["shelf_life_days"])

            # Expiration date logic
            if expiration_date_override:
                exp_date = expiration_date_override
            elif shelf_days > 0:
                exp_date = (today + timedelta(days=shelf_days)).isoformat()
            else:
                exp_date = "2030-12-31"

            # Create lot
            lot_id = f"lot-{uuid.uuid4().hex[:10]}"
            lot_number = f"L-OC-{po['consecutive_oc'].replace('OC-', '')}-{p_id[-4:]}"

            cur.execute("""
            INSERT INTO lots (id, lot_number, product_id, warehouse_id, initial_qty, remaining_qty, unit_cost, reception_date, expiration_date, supplier_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AVAILABLE');
            """, (
                lot_id,
                lot_number,
                p_id,
                warehouse_id,
                qty,
                qty,
                cost,
                today.isoformat(),
                exp_date,
                supplier_id
            ))

            # Add movement line
            cur.execute("""
            INSERT INTO movement_lines (id, movement_id, product_id, lot_id, quantity, unit_cost, total_line_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                f"mline-{uuid.uuid4().hex[:10]}",
                mov_id,
                p_id,
                lot_id,
                qty,
                cost,
                round(qty * cost, 2)
            ))

            # Update stock available and weighted avg cost
            cur.execute("SELECT id, available_qty, weighted_avg_cost FROM stock WHERE product_id = ? AND warehouse_id = ?;", (p_id, warehouse_id))
            stk = cur.fetchone()
            if stk:
                prev_qty = float(stk["available_qty"])
                prev_cost = float(stk["weighted_avg_cost"])
                new_cost = compute_weighted_average_cost(prev_qty, prev_cost, qty, cost)
                cur.execute("""
                UPDATE stock 
                SET available_qty = available_qty + ?, weighted_avg_cost = ?, updated_at = ?
                WHERE id = ?;
                """, (qty, new_cost, now_iso, stk["id"]))
            else:
                cur.execute("""
                INSERT INTO stock (id, product_id, warehouse_id, available_qty, reserved_qty, weighted_avg_cost, updated_at)
                VALUES (?, ?, ?, ?, 0.0, ?, ?);
                """, (f"stk-{uuid.uuid4().hex[:10]}", p_id, warehouse_id, qty, cost, now_iso))

            # Update received qty on PO item
            cur.execute("UPDATE purchase_order_items SET received_qty = ? WHERE id = ?;", (qty, l["id"]))

            created_lots.append({
                "product_id": p_id,
                "product_name": l["product_name"],
                "lot_number": lot_number,
                "quantity": qty,
                "expiration_date": exp_date
            })

        # Mark PO as RECEIVED
        cur.execute("UPDATE purchase_orders SET status = 'RECEIVED' WHERE id = ?;", (po_id,))

        record_audit(
            cur,
            user_alias,
            "RECEIVE_PURCHASE_ORDER",
            "PURCHASE_ORDER",
            po_id,
            {
                "consecutive_oc": po["consecutive_oc"],
                "movement_consecutive": mov_consecutive,
                "total_receipt_value": round(total_receipt_value, 2),
                "lots_created_count": len(created_lots)
            }
        )

    return {
        "status": "SUCCESS",
        "po_id": po_id,
        "consecutive_oc": po["consecutive_oc"],
        "movement_consecutive": mov_consecutive,
        "message": f"Orden de Compra {po['consecutive_oc']} recepcionada exitosamente en bodega.",
        "lots_created": created_lots
    }
