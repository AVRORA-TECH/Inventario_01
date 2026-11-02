"""Domain inventory service for Refribreak Inventory Core (RIC).
Implements weighted average cost calculation, FEFO lot depletion,
transactional consistency and audit logging.
"""
from datetime import datetime, date, timedelta
import uuid
import json
from typing import Dict, Any, List, Optional
from src.database import get_db_cursor
from src.schemas import PurchaseEntryRequest, DispatchRequest, WasteRequest, InventoryAdjustmentRequest


def compute_weighted_average_cost(prev_qty: float, prev_avg_cost: float, new_qty: float, new_cost: float) -> float:
    """Computes the new weighted average cost with standard banker's rounding to 2 decimals."""
    total_qty = prev_qty + new_qty
    if total_qty <= 0:
        return 0.0
    total_value = (prev_qty * prev_avg_cost) + (new_qty * new_cost)
    raw_avg = total_value / total_qty
    return round(raw_avg, 2)


def record_audit(cur, user_alias: str, action: str, entity_type: str, entity_id: str, details: Dict[str, Any]) -> None:
    """Appends an immutable audit event in the active transaction."""
    audit_id = f"aud-{uuid.uuid4().hex[:10]}"
    cur.execute(
        "INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?);",
        (
            audit_id,
            datetime.now().isoformat(),
            user_alias,
            action,
            entity_type,
            entity_id,
            json.dumps(details, ensure_ascii=False)
        )
    )


def process_purchase_entry(req: PurchaseEntryRequest) -> Dict[str, Any]:
    """Processes an incoming purchase entry with lot creation and weighted average cost update."""
    now_iso = datetime.now().isoformat()
    movement_id = f"mov-{uuid.uuid4().hex[:10]}"
    lot_id = f"lot-{uuid.uuid4().hex[:10]}"
    line_id = f"mline-{uuid.uuid4().hex[:10]}"

    with get_db_cursor() as cur:
        # Check idempotency key if provided
        if req.idempotency_key:
            cur.execute("SELECT id, consecutive FROM movements WHERE idempotency_key = ?;", (req.idempotency_key,))
            existing = cur.fetchone()
            if existing:
                return {
                    "status": "IDEMPOTENT_HIT",
                    "movement_id": existing["id"],
                    "consecutive": existing["consecutive"],
                    "message": "Operación ya procesada anteriormente con la misma clave de idempotencia."
                }

        # Validate product and warehouse
        cur.execute("SELECT name FROM products WHERE id = ?;", (req.product_id,))
        prod = cur.fetchone()
        if not prod:
            raise ValueError(f"Producto con ID {req.product_id} no existe.")

        cur.execute("SELECT name FROM warehouses WHERE id = ?;", (req.warehouse_id,))
        wh = cur.fetchone()
        if not wh:
            raise ValueError(f"Bodega con ID {req.warehouse_id} no existe.")

        # Generate movement consecutive
        cur.execute("SELECT COUNT(*) FROM movements WHERE movement_type = 'IN_PURCHASE';")
        seq = cur.fetchone()[0] + 1
        consecutive = f"ENT-{seq:05d}"

        # 1. Fetch current stock
        cur.execute(
            "SELECT id, available_qty, weighted_avg_cost FROM stock WHERE product_id = ? AND warehouse_id = ?;",
            (req.product_id, req.warehouse_id)
        )
        stock_row = cur.fetchone()
        if stock_row:
            curr_qty = stock_row["available_qty"]
            curr_avg_cost = stock_row["weighted_avg_cost"]
            new_avg_cost = compute_weighted_average_cost(curr_qty, curr_avg_cost, req.quantity, req.unit_cost)
            new_qty = curr_qty + req.quantity

            cur.execute(
                """UPDATE stock 
                   SET available_qty = ?, weighted_avg_cost = ?, updated_at = ? 
                   WHERE id = ?;""",
                (new_qty, new_avg_cost, now_iso, stock_row["id"])
            )
        else:
            stock_id = f"stk-{uuid.uuid4().hex[:10]}"
            new_qty = req.quantity
            new_avg_cost = round(req.unit_cost, 2)
            cur.execute(
                """INSERT INTO stock (id, product_id, warehouse_id, available_qty, reserved_qty, weighted_avg_cost, updated_at) 
                   VALUES (?, ?, ?, ?, 0.0, ?, ?);""",
                (stock_id, req.product_id, req.warehouse_id, new_qty, new_avg_cost, now_iso)
            )

        # 2. Create Lot
        cur.execute(
            """INSERT INTO lots (id, lot_number, product_id, warehouse_id, initial_qty, remaining_qty, unit_cost, reception_date, expiration_date, supplier_id, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AVAILABLE');""",
            (
                lot_id,
                req.lot_number,
                req.product_id,
                req.warehouse_id,
                req.quantity,
                req.quantity,
                req.unit_cost,
                date.today().isoformat(),
                req.expiration_date,
                req.supplier_id
            )
        )

        # 3. Create Movement and Line
        total_line_cost = round(req.quantity * req.unit_cost, 2)
        cur.execute(
            """INSERT INTO movements (id, consecutive, movement_type, warehouse_id, status, reference_doc, idempotency_key, operator_name, notes, total_cost, created_at)
               VALUES (?, ?, 'IN_PURCHASE', ?, 'CONFIRMED', ?, ?, ?, ?, ?, ?);""",
            (
                movement_id,
                consecutive,
                req.warehouse_id,
                req.reference_doc,
                req.idempotency_key,
                req.operator_name,
                req.notes,
                total_line_cost,
                now_iso
            )
        )

        cur.execute(
            """INSERT INTO movement_lines (id, movement_id, product_id, lot_id, quantity, unit_cost, total_line_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?);""",
            (line_id, movement_id, req.product_id, lot_id, req.quantity, req.unit_cost, total_line_cost)
        )

        # 4. Audit
        record_audit(
            cur,
            req.operator_name,
            "PURCHASE_ENTRY_CONFIRMED",
            "STOCK",
            req.product_id,
            {
                "consecutive": consecutive,
                "lot_number": req.lot_number,
                "quantity": req.quantity,
                "unit_cost": req.unit_cost,
                "new_avg_cost": new_avg_cost,
                "new_available_qty": new_qty
            }
        )

        return {
            "status": "SUCCESS",
            "movement_id": movement_id,
            "consecutive": consecutive,
            "new_available_qty": new_qty,
            "new_weighted_avg_cost": new_avg_cost,
            "lot_id": lot_id
        }


def process_fefo_dispatch(req: DispatchRequest) -> Dict[str, Any]:
    """Depletes stock using First-Expired-First-Out (FEFO) logic.
    Rejects completely if total available stock is insufficient (no negative stock).
    """
    now_iso = datetime.now().isoformat()
    movement_id = f"mov-{uuid.uuid4().hex[:10]}"

    with get_db_cursor() as cur:
        # Check current stock
        cur.execute(
            "SELECT id, available_qty, weighted_avg_cost FROM stock WHERE product_id = ? AND warehouse_id = ?;",
            (req.product_id, req.warehouse_id)
        )
        stock_row = cur.fetchone()
        if not stock_row or stock_row["available_qty"] < req.quantity:
            avail = stock_row["available_qty"] if stock_row else 0.0
            raise ValueError(
                f"Existencias insuficientes. Se solicitan {req.quantity} unidades pero solo hay {avail} disponibles."
            )

        # Get available lots ordered by FEFO: expiration_date ASC, unit_cost ASC
        cur.execute(
            """SELECT id, lot_number, remaining_qty, unit_cost, expiration_date 
               FROM lots 
               WHERE product_id = ? AND warehouse_id = ? AND remaining_qty > 0 AND status = 'AVAILABLE'
               ORDER BY expiration_date ASC, unit_cost ASC;""",
            (req.product_id, req.warehouse_id)
        )
        lots = cur.fetchall()

        needed_qty = req.quantity
        allocated_lines = []
        total_dispatch_cost = 0.0

        for lot in lots:
            lot_rem = lot["remaining_qty"]
            take_qty = min(needed_qty, lot_rem)
            lot_cost = lot["unit_cost"]
            line_cost = round(take_qty * lot_cost, 2)
            total_dispatch_cost += line_cost

            allocated_lines.append({
                "lot_id": lot["id"],
                "lot_number": lot["lot_number"],
                "qty": take_qty,
                "unit_cost": lot_cost,
                "total_cost": line_cost,
                "new_rem": lot_rem - take_qty
            })

            needed_qty -= take_qty
            if needed_qty <= 0:
                break

        if needed_qty > 0:
            raise ValueError("No hay suficientes lotes activos para completar el despacho.")

        # Update lots
        for line in allocated_lines:
            status_val = "EXHAUSTED" if line["new_rem"] == 0 else "AVAILABLE"
            cur.execute(
                "UPDATE lots SET remaining_qty = ?, status = ? WHERE id = ?;",
                (line["new_rem"], status_val, line["lot_id"])
            )

        # Update stock
        new_avail_qty = stock_row["available_qty"] - req.quantity
        cur.execute(
            "UPDATE stock SET available_qty = ?, updated_at = ? WHERE id = ?;",
            (new_avail_qty, now_iso, stock_row["id"])
        )

        # Movement header
        cur.execute("SELECT COUNT(*) FROM movements WHERE movement_type = 'OUT_DISPATCH';")
        seq = cur.fetchone()[0] + 1
        consecutive = f"SAL-{seq:05d}"

        cur.execute(
            """INSERT INTO movements (id, consecutive, movement_type, warehouse_id, status, reference_doc, operator_name, notes, total_cost, created_at)
               VALUES (?, ?, 'OUT_DISPATCH', ?, 'CONFIRMED', ?, ?, ?, ?, ?);""",
            (
                movement_id,
                consecutive,
                req.warehouse_id,
                req.reference_doc or req.delivery_order_id,
                req.operator_name,
                req.notes,
                total_dispatch_cost,
                now_iso
            )
        )

        # Movement lines
        for line in allocated_lines:
            line_id = f"mline-{uuid.uuid4().hex[:10]}"
            cur.execute(
                """INSERT INTO movement_lines (id, movement_id, product_id, lot_id, quantity, unit_cost, total_line_cost)
                   VALUES (?, ?, ?, ?, ?, ?, ?);""",
                (line_id, movement_id, req.product_id, line["lot_id"], line["qty"], line["unit_cost"], line["total_cost"])
            )

        # Audit
        record_audit(
            cur,
            req.operator_name,
            "FEFO_DISPATCH_CONFIRMED",
            "STOCK",
            req.product_id,
            {
                "consecutive": consecutive,
                "requested_qty": req.quantity,
                "total_dispatch_cost": total_dispatch_cost,
                "remaining_available_stock": new_avail_qty,
                "depleted_lots": allocated_lines
            }
        )

        return {
            "status": "SUCCESS",
            "movement_id": movement_id,
            "consecutive": consecutive,
            "depleted_qty": req.quantity,
            "remaining_available_stock": new_avail_qty,
            "total_dispatch_cost": total_dispatch_cost,
            "allocated_lots": allocated_lines
        }


def process_waste_registration(req: WasteRequest) -> Dict[str, Any]:
    """Registers spoilage / waste (baja por vencimiento o daño).
    Requires reason and Supervisor approval if over threshold.
    """
    now_iso = datetime.now().isoformat()
    movement_id = f"mov-{uuid.uuid4().hex[:10]}"

    with get_db_cursor() as cur:
        # Check lot
        cur.execute(
            "SELECT id, lot_number, remaining_qty, unit_cost FROM lots WHERE id = ? AND warehouse_id = ?;",
            (req.lot_id, req.warehouse_id)
        )
        lot = cur.fetchone()
        if not lot or lot["remaining_qty"] < req.quantity:
            avail = lot["remaining_qty"] if lot else 0.0
            raise ValueError(f"El lote no tiene cantidad suficiente para dar de baja ({avail} disponibles).")

        waste_value = round(req.quantity * lot["unit_cost"], 2)

        # Check stock
        cur.execute(
            "SELECT id, available_qty FROM stock WHERE product_id = ? AND warehouse_id = ?;",
            (req.product_id, req.warehouse_id)
        )
        stk = cur.fetchone()
        if not stk or stk["available_qty"] < req.quantity:
            raise ValueError("Inconsistencia en existencias de stock general.")

        # Update lot
        new_lot_rem = lot["remaining_qty"] - req.quantity
        lot_status = "EXHAUSTED" if new_lot_rem == 0 else "AVAILABLE"
        cur.execute("UPDATE lots SET remaining_qty = ?, status = ? WHERE id = ?;", (new_lot_rem, lot_status, req.lot_id))

        # Update stock (does not alter weighted average cost)
        new_stock_qty = stk["available_qty"] - req.quantity
        cur.execute("UPDATE stock SET available_qty = ?, updated_at = ? WHERE id = ?;", (new_stock_qty, now_iso, stk["id"]))

        # Consecutivo
        cur.execute("SELECT COUNT(*) FROM movements WHERE movement_type = 'WASTE';")
        seq = cur.fetchone()[0] + 1
        consecutive = f"MER-{seq:05d}"

        notes = f"Motivo: {req.reason}. {req.notes or ''}"
        cur.execute(
            """INSERT INTO movements (id, consecutive, movement_type, warehouse_id, status, reference_doc, operator_name, notes, total_cost, created_at)
               VALUES (?, ?, 'WASTE', ?, 'CONFIRMED', ?, ?, ?, ?, ?);""",
            (movement_id, consecutive, req.warehouse_id, req.approved_by, req.operator_name, notes, waste_value, now_iso)
        )

        line_id = f"mline-{uuid.uuid4().hex[:10]}"
        cur.execute(
            """INSERT INTO movement_lines (id, movement_id, product_id, lot_id, quantity, unit_cost, total_line_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?);""",
            (line_id, movement_id, req.product_id, req.lot_id, req.quantity, lot["unit_cost"], waste_value)
        )

        record_audit(
            cur,
            req.operator_name,
            "WASTE_REGISTERED",
            "LOT",
            req.lot_id,
            {
                "consecutive": consecutive,
                "reason": req.reason,
                "quantity": req.quantity,
                "waste_value_cop": waste_value,
                "approved_by": req.approved_by
            }
        )

        return {
            "status": "SUCCESS",
            "movement_id": movement_id,
            "consecutive": consecutive,
            "waste_value_cop": waste_value,
            "remaining_lot_qty": new_lot_rem
        }


def process_inventory_adjustment(req: InventoryAdjustmentRequest) -> Dict[str, Any]:
    """Applies a justified physical count adjustment."""
    now_iso = datetime.now().isoformat()
    movement_id = f"mov-{uuid.uuid4().hex[:10]}"

    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, available_qty, weighted_avg_cost FROM stock WHERE product_id = ? AND warehouse_id = ?;",
            (req.product_id, req.warehouse_id)
        )
        stk = cur.fetchone()
        current_qty = stk["available_qty"] if stk else 0.0
        avg_cost = stk["weighted_avg_cost"] if stk else 0.0
        diff = req.physical_count - current_qty

        if diff == 0:
            return {"status": "NO_CHANGE", "message": "El conteo físico coincide exactamente con el sistema."}

        cur.execute("SELECT COUNT(*) FROM movements WHERE movement_type = 'ADJUSTMENT';")
        seq = cur.fetchone()[0] + 1
        consecutive = f"AJU-{seq:05d}"

        adjustment_cost = round(abs(diff) * avg_cost, 2)

        if stk:
            cur.execute("UPDATE stock SET available_qty = ?, updated_at = ? WHERE id = ?;", (req.physical_count, now_iso, stk["id"]))
        else:
            stock_id = f"stk-{uuid.uuid4().hex[:10]}"
            cur.execute(
                "INSERT INTO stock (id, product_id, warehouse_id, available_qty, reserved_qty, weighted_avg_cost, updated_at) VALUES (?, ?, ?, ?, 0.0, 0.0, ?);",
                (stock_id, req.product_id, req.warehouse_id, req.physical_count, now_iso)
            )

        notes = f"Ajuste físico: antes={current_qty}, conteo={req.physical_count}, dif={diff}. Justificación: {req.justification}"
        cur.execute(
            """INSERT INTO movements (id, consecutive, movement_type, warehouse_id, status, operator_name, notes, total_cost, created_at)
               VALUES (?, ?, 'ADJUSTMENT', ?, 'CONFIRMED', ?, ?, ?, ?);""",
            (movement_id, consecutive, req.warehouse_id, req.operator_name, notes, adjustment_cost, now_iso)
        )

        record_audit(
            cur,
            req.operator_name,
            "INVENTORY_ADJUSTED",
            "STOCK",
            req.product_id,
            {"consecutive": consecutive, "diff": diff, "count": req.physical_count, "justification": req.justification}
        )

        return {
            "status": "SUCCESS",
            "consecutive": consecutive,
            "difference": diff,
            "new_qty": req.physical_count,
            "adjustment_cost_cop": adjustment_cost
        }
