"""Order management service for Delivery Orders (OE - Órdenes de Entrega).
Manages full lifecycle, menaje/catering equipment breakdowns, and dispatch linking.
"""
from datetime import datetime, date
import uuid
import json
from typing import Dict, Any, List, Optional
from src.database import get_db_cursor
from src.schemas import DeliveryOrderCreate, DispatchRequest
from src.services.inventory_service import process_fefo_dispatch, record_audit


def get_default_equipment_for_service(service_type: str, quantity: int) -> Dict[str, int]:
    """Generates standard menaje and catering equipment list based on quantity and service."""
    return {
        "guantes": 2,
        "tapabocas": 2,
        "pinzas": 4,
        "cuchara_servir": 2,
        "cuchillo_buen_estado": 1,
        "mesa_catering": 2 if quantity >= 20 else 1,
        "mantel_y_tapa": 2 if quantity >= 20 else 1,
        "individuales_refribreak": 1,
        "servilletas_lujo": quantity,
        "scoot": 4,
        "plato_fuerte": quantity,
        "vaso_jugo": quantity,
        "copa_parfait": quantity,
        "plato_base": quantity,
        "cubiertos_x2": quantity,
        "cucharita_parfait": quantity
    }


def create_delivery_order(data: DeliveryOrderCreate) -> Dict[str, Any]:
    """Creates a new Delivery Order with consecutive auto-generation (e.g., OE 7219)."""
    now_iso = datetime.now().isoformat()
    order_id = f"oe-{uuid.uuid4().hex[:10]}"

    with get_db_cursor() as cur:
        # Check customer
        cur.execute("SELECT name, address FROM customers WHERE id = ?;", (data.customer_id,))
        cust = cur.fetchone()
        if not cust:
            raise ValueError("Cliente no encontrado.")

        # Determine consecutive
        if data.consecutive_oe:
            consecutive = data.consecutive_oe
        else:
            cur.execute("SELECT COUNT(*) FROM delivery_orders;")
            next_num = 7217 + cur.fetchone()[0]
            consecutive = f"OE {next_num}"

        # Equipment
        eq = data.equipment or get_default_equipment_for_service(data.service_type, data.quantity)
        equipment_json = json.dumps(eq, ensure_ascii=False)

        cur.execute(
            """INSERT INTO delivery_orders (
                id, consecutive_oe, customer_id, warehouse_id, order_date, delivery_date, delivery_day_name,
                delivery_address, arrival_time, start_time, end_time, departure_time, transporter_name,
                transport_mode, vehicle_plate, advisor_name, requested_by, received_by, receiver_phone,
                service_type, service_description, product_detail, quantity, status, observations,
                equipment_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'APPROVED', ?, ?, ?);""",
            (
                order_id,
                consecutive,
                data.customer_id,
                data.warehouse_id,
                data.order_date,
                data.delivery_date,
                data.delivery_day_name,
                data.delivery_address or cust["address"],
                data.arrival_time,
                data.start_time,
                data.end_time,
                data.departure_time,
                data.transporter_name,
                data.transport_mode,
                data.vehicle_plate,
                data.advisor_name,
                data.requested_by,
                data.received_by,
                data.receiver_phone,
                data.service_type,
                data.service_description,
                data.product_detail,
                data.quantity,
                data.observations,
                equipment_json,
                now_iso
            )
        )

        record_audit(
            cur,
            data.advisor_name,
            "DELIVERY_ORDER_CREATED",
            "DELIVERY_ORDER",
            order_id,
            {
                "consecutive": consecutive,
                "customer": cust["name"],
                "quantity": data.quantity,
                "product": data.product_detail
            }
        )

        return {
            "id": order_id,
            "consecutive_oe": consecutive,
            "status": "APPROVED",
            "message": f"Orden {consecutive} creada exitosamente."
        }


def dispatch_delivery_order(order_id: str, operator_name: str = "Nicolas Santa") -> Dict[str, Any]:
    """Marks a delivery order as DISPATCHED and discounts inventory using FEFO for relevant products."""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM delivery_orders WHERE id = ?;", (order_id,))
        order = cur.fetchone()
        if not order:
            raise ValueError("Orden de entrega no encontrada.")

        if order["status"] == "DISPATCHED":
            return {"status": "ALREADY_DISPATCHED", "message": "La orden ya había sido despachada previamente."}

        # Descontamos el producto principal: wrap express
        cur.execute("SELECT id FROM products WHERE sku = 'REF-WRAP-001';")
        wrap_prod = cur.fetchone()

        dispatch_results = []
        if wrap_prod:
            req = DispatchRequest(
                warehouse_id=order["warehouse_id"],
                product_id=wrap_prod["id"],
                quantity=float(order["quantity"]),
                reference_doc=order["consecutive_oe"],
                delivery_order_id=order["id"],
                operator_name=operator_name,
                notes=f"Despacho automático para orden {order['consecutive_oe']} - {order['product_detail']}"
            )
            # Execute FEFO deduction
            res = process_fefo_dispatch(req)
            dispatch_results.append(res)

        # Mark order as DISPATCHED
        cur.execute("UPDATE delivery_orders SET status = 'DISPATCHED' WHERE id = ?;", (order_id,))

        record_audit(
            cur,
            operator_name,
            "DELIVERY_ORDER_DISPATCHED",
            "DELIVERY_ORDER",
            order_id,
            {
                "consecutive": order["consecutive_oe"],
                "quantity": order["quantity"],
                "dispatch_details": dispatch_results
            }
        )

        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "consecutive_oe": order["consecutive_oe"],
            "new_order_status": "DISPATCHED",
            "stock_depleted": dispatch_results
        }
