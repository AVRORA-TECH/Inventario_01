# Inventario_01 — Refribreak Inventory Core (RIC)

Plataforma web de control de inventario, costos, trazabilidad FEFO y despacho de refrigerios empresariales para **Refribreak**, desarrollada por **Avrora Tech**.

---

## 🚀 Arquitectura del Sistema

- **Backend:** Python 3.12 con **FastAPI** y **Uvicorn**, exponiendo una API REST modular en formato 100% JSON (`/api/v1/*`).
- **Frontend:** Single Page Application (SPA) construida en **Vanilla HTML5, CSS3 y JavaScript nativo** (sin frameworks pesados como React o Vue). Todo el consumo de datos se realiza mediante `fetch` nativo.
- **Persistencia:** Base de datos relacional **SQLite en modo WAL** (`journal_mode=WAL; foreign_keys=ON; busy_timeout=30000ms`), garantizando alta concurrencia y transacciones ACID.
- **Trazabilidad FEFO:** Depleción automática por fecha de caducidad más cercana (*First-Expired, First-Out*), protegiendo la inocuidad y reduciendo mermas.
- **Cálculo de Costos:** Costo promedio ponderado con redondeo bancario a 2 decimales en cada entrada por compra.
- **Módulo OE 7217 & Menaje:** Emisión, visualización e impresión digital fiel al formato físico de confirmación de entrega y orden de servicio con cuadrícula completa de menaje de catering.
- **Agente IA de Facturas:** Módulo de extracción asistida de facturas con cálculo de confianza por campo para acelerar la recepción en bodega.

---

## 📁 Estructura del Repositorio

```text
├── src/
│   ├── config.py                 # Constantes y variables de entorno
│   ├── database.py               # Conexión SQLite WAL, esquema relacional y seed inicial
│   ├── schemas.py                # Modelos de validación en frontera Pydantic v2
│   ├── services/
│   │   ├── inventory_service.py  # Lógica FEFO, costo promedio ponderado y transacciones
│   │   ├── order_service.py      # Gestión de Órdenes de Entrega (OE) y menaje
│   │   └── ai_service.py         # Simulación y extracción de facturas con Agente IA
│   ├── api/
│   │   └── routes.py             # Enrutador de endpoints REST JSON (/api/v1/*)
│   ├── static/
│   │   ├── index.html            # Interfaz Single Page Application Vanilla
│   │   ├── css/styles.css        # Sistema de diseño Navy + pills tipo Airtable / Notion
│   │   └── js/
│   │       ├── api.js            # Cliente HTTP fetch nativo
│   │       └── app.js            # Navegación SPA, reactividad y render de remisión OE
│   └── main.py                   # Entrypoint FastAPI y servicio de assets estáticos
├── tests/
│   └── test_inventory_core.py    # Suite de pruebas unitarias y de integración (pytest)
├── docs/
│   └── bitacora/                 # NUCLEO.md y BITACORA.md de ingeniería
├── conftest.py                   # Configuración de resolución de rutas para pruebas
├── requirements.txt              # Dependencias del proyecto
└── README.md
```

---

## 🛠️ Instalación y Puesta en Marcha

### 1. Clonar el repositorio
```bash
git clone https://github.com/AVRORA-TECH/Inventario_01.git
cd Inventario_01
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Iniciar el servidor
```bash
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```
Abre en tu navegador: **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**

---

## 🧪 Pruebas Automatizadas

Ejecutar la suite completa de pruebas:
```bash
pytest -v
```

---

## 📋 Licencia & Propiedad

Desarrollado por **Avrora Tech — Ingeniería Aplicada** para **Refribreak**. Todos los derechos reservados.
>>>>>>> f2fbfd6 (feat(core): implement Refribreak Inventory Core with FastAPI and Vanilla UI)
