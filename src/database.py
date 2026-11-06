"""Database connection and idempotent schema initializer for Refribreak Inventory Core (RIC).
Uses SQLite with WAL mode and strict relational constraints.
"""
import sqlite3
from typing import Generator
from contextlib import contextmanager
from datetime import datetime, date, timedelta
from src.config import DB_PATH


def get_db_connection() -> sqlite3.Connection:
    """Returns a SQLite connection configured with WAL mode and row factory."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 30000;")
    return conn


@contextmanager
def get_db_cursor() -> Generator[sqlite3.Cursor, None, None]:
    """Context manager for transacted database operations."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Creates tables idempotently and populates baseline catalog data."""
    with get_db_cursor() as cur:
        # 1. Warehouses (Sedes)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS warehouses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            address TEXT NOT NULL,
            city TEXT NOT NULL DEFAULT 'Bogotá',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        """)

        # 2. Categories
        cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            slug TEXT NOT NULL UNIQUE,
            is_perishable INTEGER NOT NULL DEFAULT 0,
            default_alert_days INTEGER NOT NULL DEFAULT 7,
            description TEXT
        );
        """)

        # 3. Products
        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            sku TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            category_id TEXT NOT NULL,
            unit TEXT NOT NULL,
            is_perishable INTEGER NOT NULL DEFAULT 0,
            shelf_life_days INTEGER NOT NULL DEFAULT 0,
            min_stock REAL NOT NULL DEFAULT 10.0,
            image_url TEXT,
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        );
        """)

        # 4. Suppliers
        cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            id TEXT PRIMARY KEY,
            nit TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            contact_name TEXT,
            phone TEXT,
            email TEXT,
            city TEXT NOT NULL DEFAULT 'Bogotá'
        );
        """)

        # 5. Customers
        cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            nit TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL DEFAULT 'Bogotá',
            contact_person TEXT,
            phone TEXT,
            email TEXT
        );
        """)

        # 6. Stock summary per product and warehouse
        cur.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            available_qty REAL NOT NULL DEFAULT 0.0 CHECK (available_qty >= 0),
            reserved_qty REAL NOT NULL DEFAULT 0.0 CHECK (reserved_qty >= 0),
            weighted_avg_cost REAL NOT NULL DEFAULT 0.0 CHECK (weighted_avg_cost >= 0),
            updated_at TEXT NOT NULL,
            UNIQUE(product_id, warehouse_id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
        );
        """)

        # 7. Lots (FEFO traceability)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS lots (
            id TEXT PRIMARY KEY,
            lot_number TEXT NOT NULL,
            product_id TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            initial_qty REAL NOT NULL,
            remaining_qty REAL NOT NULL CHECK (remaining_qty >= 0),
            unit_cost REAL NOT NULL,
            reception_date TEXT NOT NULL,
            expiration_date TEXT NOT NULL,
            supplier_id TEXT,
            status TEXT NOT NULL DEFAULT 'AVAILABLE',
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses (id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
        );
        """)

        # 8. Movements header
        cur.execute("""
        CREATE TABLE IF NOT EXISTS movements (
            id TEXT PRIMARY KEY,
            consecutive TEXT NOT NULL UNIQUE,
            movement_type TEXT NOT NULL, -- 'IN_PURCHASE', 'OUT_DISPATCH', 'TRANSFER', 'WASTE', 'ADJUSTMENT'
            warehouse_id TEXT NOT NULL,
            target_warehouse_id TEXT,
            status TEXT NOT NULL DEFAULT 'CONFIRMED', -- 'DRAFT', 'CONFIRMED', 'CANCELLED'
            reference_doc TEXT,
            idempotency_key TEXT UNIQUE,
            operator_name TEXT NOT NULL,
            notes TEXT,
            total_cost REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
        );
        """)

        # 9. Movement Lines
        cur.execute("""
        CREATE TABLE IF NOT EXISTS movement_lines (
            id TEXT PRIMARY KEY,
            movement_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            lot_id TEXT,
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            total_line_cost REAL NOT NULL,
            FOREIGN KEY (movement_id) REFERENCES movements (id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (lot_id) REFERENCES lots (id)
        );
        """)

        # 10. Delivery Orders (Órdenes de Entrega OE)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS delivery_orders (
            id TEXT PRIMARY KEY,
            consecutive_oe TEXT NOT NULL UNIQUE, -- e.g. OE 7217
            customer_id TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            order_date TEXT NOT NULL,
            delivery_date TEXT NOT NULL,
            delivery_day_name TEXT NOT NULL,
            delivery_address TEXT NOT NULL,
            arrival_time TEXT,
            start_time TEXT,
            end_time TEXT,
            departure_time TEXT,
            transporter_name TEXT,
            transport_mode TEXT,
            vehicle_plate TEXT,
            advisor_name TEXT,
            requested_by TEXT,
            received_by TEXT,
            receiver_phone TEXT,
            service_type TEXT NOT NULL, -- 'Desayuno', 'Refrigerio', 'Almuerzo'
            service_description TEXT NOT NULL, -- 'Servido', 'Empacado individual'
            product_detail TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'APPROVED', -- 'DRAFT', 'APPROVED', 'DISPATCHED', 'DELIVERED', 'CANCELLED'
            observations TEXT,
            equipment_json TEXT, -- JSON structure of menaje / catering items
            created_at TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
        );
        """)

        # 11. Audit Log (append-only)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            user_alias TEXT NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            details_json TEXT NOT NULL
        );
        """)

        # 12. Purchase Requisitions (Solicitudes de Reabastecimiento/Compra)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requisitions (
            id TEXT PRIMARY KEY,
            consecutive TEXT NOT NULL UNIQUE,
            warehouse_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'DRAFT', -- 'DRAFT', 'QUOTING', 'AWARDED', 'CANCELLED'
            origin TEXT NOT NULL DEFAULT 'INVENTORY_SUGGESTION', -- 'INVENTORY_SUGGESTION', 'MANUAL'
            notes TEXT,
            created_by TEXT NOT NULL DEFAULT 'diego',
            created_at TEXT NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
        );
        """)

        # 13. Purchase Requisition Items
        cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_requisition_items (
            id TEXT PRIMARY KEY,
            requisition_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            current_stock REAL NOT NULL DEFAULT 0.0,
            min_stock REAL NOT NULL DEFAULT 0.0,
            requested_qty REAL NOT NULL,
            estimated_unit_cost REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (requisition_id) REFERENCES purchase_requisitions (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
        """)

        # 14. Supplier Quotations (Cotizaciones por Proveedor)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_quotations (
            id TEXT PRIMARY KEY,
            requisition_id TEXT NOT NULL,
            supplier_id TEXT NOT NULL,
            quotation_number TEXT,
            delivery_days INTEGER NOT NULL DEFAULT 1,
            payment_terms TEXT NOT NULL DEFAULT 'Contado',
            shipping_cost REAL NOT NULL DEFAULT 0.0,
            total_amount REAL NOT NULL DEFAULT 0.0,
            is_awarded INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (requisition_id) REFERENCES purchase_requisitions (id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
        );
        """)

        # 15. Supplier Quotation Items
        cur.execute("""
        CREATE TABLE IF NOT EXISTS supplier_quotation_items (
            id TEXT PRIMARY KEY,
            quotation_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            total_cost REAL NOT NULL,
            FOREIGN KEY (quotation_id) REFERENCES supplier_quotations (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
        """)

        # 16. Purchase Orders (Órdenes de Compra Oficiales)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id TEXT PRIMARY KEY,
            consecutive_oc TEXT NOT NULL UNIQUE,
            requisition_id TEXT,
            quotation_id TEXT,
            supplier_id TEXT NOT NULL,
            warehouse_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ISSUED', -- 'ISSUED', 'IN_TRANSIT', 'RECEIVED', 'CANCELLED'
            order_date TEXT NOT NULL,
            expected_delivery_date TEXT NOT NULL,
            payment_terms TEXT NOT NULL DEFAULT 'Contado',
            subtotal REAL NOT NULL DEFAULT 0.0,
            shipping_cost REAL NOT NULL DEFAULT 0.0,
            total_amount REAL NOT NULL DEFAULT 0.0,
            notes TEXT,
            created_by TEXT NOT NULL DEFAULT 'diego',
            created_at TEXT NOT NULL,
            FOREIGN KEY (requisition_id) REFERENCES purchase_requisitions (id),
            FOREIGN KEY (quotation_id) REFERENCES supplier_quotations (id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
            FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
        );
        """)

        # 17. Purchase Order Items
        cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_order_items (
            id TEXT PRIMARY KEY,
            purchase_order_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            total_cost REAL NOT NULL,
            received_qty REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
        """)

        # Seed initial data if warehouses table is empty
        cur.execute("SELECT COUNT(*) FROM warehouses;")
        if cur.fetchone()[0] == 0:
            seed_initial_data(cur)

        # Seed procurement comparison sample if empty
        cur.execute("SELECT COUNT(*) FROM purchase_requisitions;")
        if cur.fetchone()[0] == 0:
            seed_purchase_comparison_sample(cur)


def seed_initial_data(cur: sqlite3.Cursor) -> None:
    """Seeds real baseline data for Refribreak."""
    now_iso = datetime.now().isoformat()
    today = date.today()

    # 1. Warehouses
    warehouses = [
        ("wh-bog-central", "Bodega Central Chapinero", "BOG-CENTRAL", "Cra 13 # 65-20", "Bogotá", 1, now_iso),
        ("wh-bog-norte", "Bodega Satélite Calle 127", "BOG-NORTE", "Calle 127 # 19-35", "Bogotá", 1, now_iso),
        ("wh-bog-c80", "Punto Operativo Calle 80", "BOG-C80", "Av Calle 80 # 72-10", "Bogotá", 1, now_iso),
    ]
    cur.executemany("INSERT INTO warehouses VALUES (?, ?, ?, ?, ?, ?, ?);", warehouses)

    # 2. Categories
    categories = [
        ("cat-refrigerios", "Refrigerios Servidos y Desayunos", "refrigerios", 1, 2, "Refrigerios listos para consumo corporativo"),
        ("cat-frutas", "Frutas y Verduras Frescas", "frutas-verduras", 1, 3, "Materia prima perecedera de alta rotación"),
        ("cat-lacteos", "Lácteos y Derivados", "lacteos", 1, 15, "Yogurt, quesos y mantequilla"),
        ("cat-panaderia", "Panadería, Wraps y Cereales", "panaderia", 1, 5, "Tortillas, panes artesanales y granola"),
        ("cat-bebidas", "Bebidas y Jugos Naturales", "bebidas", 1, 4, "Jugos naturales embotellados y café"),
        ("cat-menaje", "Menaje, Vajilla y Catering", "menaje", 0, 365, "Mobiliario, mantelería, vajilla y cubiertos"),
    ]
    cur.executemany("INSERT INTO categories VALUES (?, ?, ?, ?, ?, ?);", categories)

    # 3. Products
    products = [
        ("prod-wrap-exp", "REF-WRAP-001", "EXPRESS Wrap de jamón, queso y vegetales", "cat-refrigerios", "Unidad", 1, 2, 20.0, None, "Wrap servido fresco con jamón York y queso doble crema", now_iso),
        ("prod-fruta-pic", "REF-FRUT-002", "Porción Fruta Picada Selección", "cat-frutas", "Porción", 1, 2, 25.0, None, "Melón, papaya, fresa y uva en vaso hermético", now_iso),
        ("prod-granola", "REF-GRAN-003", "Cereal Granola Artesanal con Miel", "cat-panaderia", "Porción", 0, 45, 30.0, None, "Avena horneada, nueces y semillas de chía", now_iso),
        ("prod-yogurt", "REF-YOG-004", "Yogurt Natural Gourmet 150ml", "cat-lacteos", "Vaso 150ml", 1, 15, 40.0, None, "Yogurt bajo en azúcar para parfait y desayunos", now_iso),
        ("prod-jugo-nar", "REF-JUG-005", "Jugo Natural de Naranja 250ml", "cat-bebidas", "Botella 250ml", 1, 4, 35.0, None, "Zumo 100% natural pasteurizado en frío", now_iso),
        ("prod-jamon", "MP-CARN-010", "Jamón York Premium Tajado", "cat-refrigerios", "Kg", 1, 7, 10.0, None, "Materia prima cárnica para wraps y sandwiches", now_iso),
        ("prod-queso", "MP-LACT-011", "Queso Doble Crema Especial", "cat-lacteos", "Kg", 1, 12, 10.0, None, "Materia prima tajada para refrigerios calientes/fríos", now_iso),
        ("prod-tortilla", "MP-PANA-012", "Tortilla Trigo 25cm (Paquete x 10)", "cat-panaderia", "Paquete", 1, 20, 15.0, None, "Base para wraps express", now_iso),
        ("prod-mesa-cat", "MEN-MOB-101", "Mesa Catering Plegable 1.80m", "cat-menaje", "Unidad", 0, 0, 5.0, None, "Mesa de servicio para estación de refrigerios", now_iso),
        ("prod-mantel", "MEN-TEXT-102", "Mantel y Tapa Negro Refribreak", "cat-menaje", "Juego", 0, 0, 6.0, None, "Juego de lencería corporativa", now_iso),
        ("prod-plato-f", "MEN-VAJ-103", "Plato Fuerte Porcelana Cuadrada", "cat-menaje", "Docena", 0, 0, 8.0, None, "Plato servido para eventos ejecutivos", now_iso),
        ("prod-copa-par", "MEN-VAJ-104", "Copa Cristal para Parfait", "cat-menaje", "Docena", 0, 0, 10.0, None, "Copas de 200ml para presentación de yogurt y granola", now_iso),
    ]
    cur.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", products)

    # 4. Suppliers
    suppliers = [
        ("sup-andina", "900.123.456-1", "Distribuidora Láctea Andina SAS", "Carlos Mora", "601-7441234", "pedidos@lacteosandina.co", "Bogotá"),
        ("sup-sabana", "901.456.789-2", "Frutas y Verduras del Campo Sabana", "Martha Gómez", "311-5896321", "comercial@frutasabana.com", "Chía"),
        ("sup-empaques", "830.555.222-3", "Empaques & Menajes Colombianos SAS", "Jorge Parra", "320-4123698", "ventas@empaquescol.com", "Bogotá"),
    ]
    cur.executemany("INSERT INTO suppliers VALUES (?, ?, ?, ?, ?, ?, ?);", suppliers)

    # 5. Customers (incluye cliente real del documento OE 7217)
    customers = [
        ("cust-liid", "900.876.543-8", "Liid Comunicacion y Creatividad SAS", "Trv 23 97 -73 Ofc 212", "Bogotá", "Leonardo Ramírez", "3504163975", "eventos@liid.com.co"),
        ("cust-bavaria", "860.005.224-6", "Bavaria & Cía SCA", "Calle 94 # 7A-47", "Bogotá", "Andrea Castillo", "310-9874561", "compras@bavaria.com.co"),
        ("cust-ecopetrol", "899.999.068-1", "Ecopetrol Centro de Innovación", "Carrera 7 # 37-69", "Bogotá", "Mauricio Silva", "315-7412589", "bienestar@ecopetrol.com.co"),
    ]
    cur.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?);", customers)

    # 6. Initial Lots and Stock in Central Warehouse
    # Lote 1: Próximo a vencer en 2 días para demostrar alertas FEFO
    lot_exp_2d = (today + timedelta(days=2)).isoformat()
    lot_exp_4d = (today + timedelta(days=4)).isoformat()
    lot_exp_12d = (today + timedelta(days=12)).isoformat()
    lot_exp_60d = (today + timedelta(days=60)).isoformat()

    lots = [
        ("lot-wrap-01", "L-WRP-2610A", "prod-wrap-exp", "wh-bog-central", 80.0, 57.0, 7500.0, today.isoformat(), lot_exp_2d, "sup-andina", "AVAILABLE"),
        ("lot-wrap-02", "L-WRP-2610B", "prod-wrap-exp", "wh-bog-central", 100.0, 100.0, 7800.0, today.isoformat(), lot_exp_4d, "sup-andina", "AVAILABLE"),
        ("lot-fruta-01", "L-FRU-2610", "prod-fruta-pic", "wh-bog-central", 120.0, 97.0, 3200.0, today.isoformat(), lot_exp_2d, "sup-sabana", "AVAILABLE"),
        ("lot-gran-01", "L-GRN-2609", "prod-granola", "wh-bog-central", 200.0, 177.0, 1800.0, (today - timedelta(days=10)).isoformat(), lot_exp_60d, "sup-empaques", "AVAILABLE"),
        ("lot-yog-01", "L-YOG-2610", "prod-yogurt", "wh-bog-central", 150.0, 127.0, 2400.0, today.isoformat(), lot_exp_12d, "sup-andina", "AVAILABLE"),
        ("lot-jug-01", "L-JUG-2610", "prod-jugo-nar", "wh-bog-central", 140.0, 117.0, 2800.0, today.isoformat(), lot_exp_4d, "sup-sabana", "AVAILABLE"),
        ("lot-jam-01", "L-JAM-2609", "prod-jamon", "wh-bog-central", 40.0, 35.0, 26000.0, today.isoformat(), lot_exp_12d, "sup-andina", "AVAILABLE"),
        ("lot-que-01", "L-QUE-2609", "prod-queso", "wh-bog-central", 50.0, 42.0, 22000.0, today.isoformat(), lot_exp_12d, "sup-andina", "AVAILABLE"),
        ("lot-tor-01", "L-TOR-2610", "prod-tortilla", "wh-bog-central", 60.0, 52.0, 9500.0, today.isoformat(), lot_exp_60d, "sup-empaques", "AVAILABLE"),
        ("lot-mes-01", "L-MEN-001", "prod-mesa-cat", "wh-bog-central", 15.0, 13.0, 120000.0, (today - timedelta(days=90)).isoformat(), "2030-12-31", "sup-empaques", "AVAILABLE"),
        ("lot-man-01", "L-MEN-002", "prod-mantel", "wh-bog-central", 20.0, 18.0, 35000.0, (today - timedelta(days=90)).isoformat(), "2030-12-31", "sup-empaques", "AVAILABLE"),
        ("lot-pla-01", "L-MEN-003", "prod-plato-f", "wh-bog-central", 12.0, 10.0, 48000.0, (today - timedelta(days=90)).isoformat(), "2030-12-31", "sup-empaques", "AVAILABLE"),
    ]
    cur.executemany("INSERT INTO lots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", lots)

    # 7. Stock per product
    stocks = [
        ("stk-wrap", "prod-wrap-exp", "wh-bog-central", 157.0, 0.0, 7691.08, now_iso),
        ("stk-fruta", "prod-fruta-pic", "wh-bog-central", 97.0, 0.0, 3200.00, now_iso),
        ("stk-gran", "prod-granola", "wh-bog-central", 177.0, 0.0, 1800.00, now_iso),
        ("stk-yog", "prod-yogurt", "wh-bog-central", 127.0, 0.0, 2400.00, now_iso),
        ("stk-jug", "prod-jugo-nar", "wh-bog-central", 117.0, 0.0, 2800.00, now_iso),
        ("stk-jam", "prod-jamon", "wh-bog-central", 35.0, 0.0, 26000.00, now_iso),
        ("stk-que", "prod-queso", "wh-bog-central", 42.0, 0.0, 22000.00, now_iso),
        ("stk-tor", "prod-tortilla", "wh-bog-central", 52.0, 0.0, 9500.00, now_iso),
        ("stk-mes", "prod-mesa-cat", "wh-bog-central", 13.0, 0.0, 120000.00, now_iso),
        ("stk-man", "prod-mantel", "wh-bog-central", 18.0, 0.0, 35000.00, now_iso),
        ("stk-pla", "prod-plato-f", "wh-bog-central", 10.0, 0.0, 48000.00, now_iso),
    ]
    cur.executemany("INSERT INTO stock VALUES (?, ?, ?, ?, ?, ?, ?);", stocks)

    # 8. Delivery Order baseline: OE 7217 de la imagen 4
    equipment_oe_7217 = (
        '{"guantes": 2, "tapabocas": 2, "pinzas": 4, "cuchara_servir": 2, '
        '"cuchillo_buen_estado": 1, "mesa_catering": 2, "mantel_y_tapa": 2, '
        '"individuales_refribreak": 1, "servilletas_lujo": 23, "scoot": 4, '
        '"plato_fuerte": 23, "vaso_jugo": 23, "copa_parfait": 23, '
        '"plato_base": 23, "cubiertos_x2": 23, "cucharita_parfait": 23}'
    )

    orders = [
        (
            "oe-7217",
            "OE 7217",
            "cust-liid",
            "wh-bog-central",
            (today - timedelta(days=1)).isoformat(),
            today.isoformat(),
            "Viernes",
            "Trv 23 97 -73 Ofc 212 Bogotá",
            "7:30 AM",
            "8:30 AM",
            "11:30 AM",
            "6:40 AM",
            "Carlos Rodríguez",
            "Carro",
            "WMA-452",
            "Nays Navarro",
            "Leonardo Ramírez",
            "Leonardo Ramírez",
            "3504163975",
            "Desayuno",
            "Servido",
            "EXPRESS Wrap de jamón, queso y vegetales - Fruta picada - Cereal Granola - Yogurt - Jugo natural 250 ml",
            23,
            "APPROVED",
            "Despacho corporativo VIP con montaje de estación de catering en piso 2.",
            equipment_oe_7217,
            now_iso
        ),
        (
            "oe-7218",
            "OE 7218",
            "cust-bavaria",
            "wh-bog-central",
            today.isoformat(),
            (today + timedelta(days=1)).isoformat(),
            "Sábado",
            "Calle 94 # 7A-47 Bogotá",
            "8:00 AM",
            "9:00 AM",
            "12:00 PM",
            "7:15 AM",
            "Andrés Pérez",
            "Furgón refrigerado",
            "TXL-108",
            "Nays Navarro",
            "Andrea Castillo",
            "Andrea Castillo",
            "310-9874561",
            "Refrigerio",
            "Empacado individual",
            "Wrap de jamón y vegetales + Fruta picada fresca + Jugo natural 250ml",
            40,
            "DRAFT",
            "Reunión de comité de innovación.",
            equipment_oe_7217,
            now_iso
        )
    ]
    cur.executemany("INSERT INTO delivery_orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", orders)

    # 9. Audit log entry
    cur.execute("""
    INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (
        "aud-seed-01",
        now_iso,
        "nicolas",
        "SYSTEM_INITIALIZATION",
        "DATABASE",
        "all",
        '{"action": "Initial data seed", "version": "1.0", "status": "OK"}'
    ))


def seed_purchase_comparison_sample(cur: sqlite3.Cursor) -> None:
    """Seeds baseline procurement requisition, competing quotes, and comparative matrix."""
    now_iso = datetime.now().isoformat()
    today = date.today()

    # 1. Requisition for low stock / reabastecimiento
    req_id = "req-sample-01"
    cur.execute("""
    INSERT OR IGNORE INTO purchase_requisitions (id, consecutive, warehouse_id, status, origin, notes, created_by, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        req_id,
        "REQ-2026-0001",
        "wh-bog-central",
        "QUOTING",
        "INVENTORY_SUGGESTION",
        "Reabastecimiento preventivo de insumos para desayunos y refrigerios corporativos semanales",
        "diego",
        now_iso
    ))

    req_items = [
        ("req-item-01", req_id, "prod-jamon", 35.0, 10.0, 20.0, 26000.0),
        ("req-item-02", req_id, "prod-queso", 42.0, 10.0, 25.0, 22000.0),
        ("req-item-03", req_id, "prod-tortilla", 52.0, 15.0, 30.0, 9500.0),
    ]
    cur.executemany("INSERT OR IGNORE INTO purchase_requisition_items VALUES (?, ?, ?, ?, ?, ?, ?);", req_items)

    # 2. Quotation 1 (Andina: Mejor Precio, flete gratis, entrega en 2 días)
    q1_id = "quote-sample-andina"
    cur.execute("""
    INSERT OR IGNORE INTO supplier_quotations (id, requisition_id, supplier_id, quotation_number, delivery_days, payment_terms, shipping_cost, total_amount, is_awarded, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        q1_id,
        req_id,
        "sup-andina",
        "COT-AND-4412",
        2,
        "Crédito 15 días",
        0.0,
        1324000.0,
        0,
        "Precios con descuento por volumen. Flete gratis en Bogotá.",
        now_iso
    ))
    q1_items = [
        ("q1-it-01", q1_id, "prod-jamon", 20.0, 25000.0, 500000.0),
        ("q1-it-02", q1_id, "prod-queso", 25.0, 21200.0, 530000.0),
        ("q1-it-03", q1_id, "prod-tortilla", 30.0, 9800.0, 294000.0),
    ]
    cur.executemany("INSERT OR IGNORE INTO supplier_quotation_items VALUES (?, ?, ?, ?, ?, ?);", q1_items)

    # 3. Quotation 2 (Empaques: Entrega express en 1 día, mejor precio en tortilla)
    q2_id = "quote-sample-empaques"
    cur.execute("""
    INSERT OR IGNORE INTO supplier_quotations (id, requisition_id, supplier_id, quotation_number, delivery_days, payment_terms, shipping_cost, total_amount, is_awarded, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        q2_id,
        req_id,
        "sup-empaques",
        "COT-EMP-8821",
        1,
        "Contado contra entrega",
        25000.0,
        1393500.0,
        0,
        "Despacho exprés prioritario en 24h. Recargo de flete.",
        now_iso
    ))
    q2_items = [
        ("q2-it-01", q2_id, "prod-jamon", 20.0, 26500.0, 530000.0),
        ("q2-it-02", q2_id, "prod-queso", 25.0, 22500.0, 562500.0),
        ("q2-it-03", q2_id, "prod-tortilla", 30.0, 9200.0, 276000.0),
    ]
    cur.executemany("INSERT OR IGNORE INTO supplier_quotation_items VALUES (?, ?, ?, ?, ?, ?);", q2_items)

    # 4. Quotation 3 (Sabana: Plazo amplio 30 días, entrega en 3 días)
    q3_id = "quote-sample-sabana"
    cur.execute("""
    INSERT OR IGNORE INTO supplier_quotations (id, requisition_id, supplier_id, quotation_number, delivery_days, payment_terms, shipping_cost, total_amount, is_awarded, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        q3_id,
        req_id,
        "sup-sabana",
        "COT-SAB-1092",
        3,
        "Crédito 30 días",
        15000.0,
        1418000.0,
        0,
        "Línea de crédito aprobada a 30 días.",
        now_iso
    ))
    q3_items = [
        ("q3-it-01", q3_id, "prod-jamon", 20.0, 27000.0, 540000.0),
        ("q3-it-02", q3_id, "prod-queso", 25.0, 23000.0, 575000.0),
        ("q3-it-03", q3_id, "prod-tortilla", 30.0, 9600.0, 288000.0),
    ]
    cur.executemany("INSERT OR IGNORE INTO supplier_quotation_items VALUES (?, ?, ?, ?, ?, ?);", q3_items)
