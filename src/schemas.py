"""Pydantic schemas for Refribreak Inventory Core (RIC) API.
Ensures boundary validation for all REST requests and responses.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WarehouseResponse(BaseModel):
    id: str
    name: str
    code: str
    address: str
    city: str
    is_active: bool


class CategoryResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_perishable: bool
    default_alert_days: int
    description: Optional[str] = None


class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=150)
    category_id: str
    unit: str
    is_perishable: bool = False
    shelf_life_days: int = Field(0, ge=0)
    min_stock: float = Field(10.0, ge=0)
    description: Optional[str] = None


class ProductResponse(BaseModel):
    id: str
    sku: str
    name: str
    category_id: str
    category_name: Optional[str] = None
    unit: str
    is_perishable: bool
    shelf_life_days: int
    min_stock: float
    description: Optional[str] = None
    created_at: str


class StockItemResponse(BaseModel):
    id: str
    product_id: str
    product_name: str
    sku: str
    category_id: str
    category_name: str
    unit: str
    is_perishable: bool
    warehouse_id: str
    warehouse_name: str
    available_qty: float
    reserved_qty: float
    total_on_hand: float
    weighted_avg_cost: float
    total_value_cop: float
    min_stock: float
    is_under_min: bool
    earliest_expiration: Optional[str] = None
    days_to_expiration: Optional[int] = None
    expiration_status: str  # 'OK', 'WARNING_EXPIRING_SOON', 'EXPIRED', 'NON_PERISHABLE'


class LotItemResponse(BaseModel):
    id: str
    lot_number: str
    product_id: str
    product_name: str
    warehouse_id: str
    warehouse_name: str
    initial_qty: float
    remaining_qty: float
    unit_cost: float
    reception_date: str
    expiration_date: str
    supplier_name: Optional[str] = None
    status: str
    days_to_expiration: int
    is_expiring_soon: bool
    is_expired: bool


class PurchaseEntryRequest(BaseModel):
    warehouse_id: str
    product_id: str
    lot_number: str
    expiration_date: str
    quantity: float = Field(..., gt=0)
    unit_cost: float = Field(..., ge=0)
    supplier_id: Optional[str] = None
    reference_doc: Optional[str] = None
    idempotency_key: Optional[str] = None
    operator_name: str = "Nicolas Santa"
    notes: Optional[str] = None


class DispatchRequest(BaseModel):
    warehouse_id: str
    product_id: str
    quantity: float = Field(..., gt=0)
    reference_doc: Optional[str] = None
    delivery_order_id: Optional[str] = None
    operator_name: str = "Nicolas Santa"
    notes: Optional[str] = None


class WasteRequest(BaseModel):
    warehouse_id: str
    product_id: str
    lot_id: str
    quantity: float = Field(..., gt=0)
    reason: str = Field(..., min_length=4)  # 'Vencimiento', 'Daño', 'Merma preparación'
    approved_by: Optional[str] = None
    operator_name: str = "Nicolas Santa"
    notes: Optional[str] = None


class InventoryAdjustmentRequest(BaseModel):
    warehouse_id: str
    product_id: str
    physical_count: float = Field(..., ge=0)
    justification: str = Field(..., min_length=5)
    operator_name: str = "Nicolas Santa"


class DeliveryOrderCreate(BaseModel):
    customer_id: str
    warehouse_id: str
    consecutive_oe: Optional[str] = None  # If empty, auto-generates OE-XXXX
    order_date: str
    delivery_date: str
    delivery_day_name: str
    delivery_address: str
    arrival_time: str
    start_time: str
    end_time: str
    departure_time: str
    transporter_name: Optional[str] = None
    transport_mode: Optional[str] = "Carro"
    vehicle_plate: Optional[str] = None
    advisor_name: str = "Nays Navarro"
    requested_by: str
    received_by: str
    receiver_phone: str
    service_type: str = "Desayuno"
    service_description: str = "Servido"
    product_detail: str
    quantity: int = Field(..., gt=0)
    observations: Optional[str] = None
    equipment: Optional[Dict[str, int]] = None


class DeliveryOrderResponse(BaseModel):
    id: str
    consecutive_oe: str
    customer_id: str
    customer_name: str
    customer_nit: str
    warehouse_id: str
    warehouse_name: str
    order_date: str
    delivery_date: str
    delivery_day_name: str
    delivery_address: str
    arrival_time: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    departure_time: Optional[str] = None
    transporter_name: Optional[str] = None
    transport_mode: Optional[str] = None
    vehicle_plate: Optional[str] = None
    advisor_name: Optional[str] = None
    requested_by: Optional[str] = None
    received_by: Optional[str] = None
    receiver_phone: Optional[str] = None
    service_type: str
    service_description: str
    product_detail: str
    quantity: int
    status: str
    observations: Optional[str] = None
    equipment: Optional[Dict[str, int]] = None
    created_at: str


class DashboardSummary(BaseModel):
    total_inventory_value_cop: float
    total_available_units: float
    critical_stock_count: int
    expiring_soon_lots_count: int
    total_delivery_orders: int
    pending_delivery_orders: int
    monthly_waste_value_cop: float
    active_warehouses_count: int


class AiInvoiceSimulationRequest(BaseModel):
    raw_text: Optional[str] = None
    supplier_hint: Optional[str] = None
