# NUCLEO.md — Mapa Estructural Verificado (Refribreak Inventory Core - RIC)
Fecha de verificación: 2026-11-05
Estado: `[V 2026-11-05]` Validado y estandarizado por `Diego Delgado` (`diego`)

## 1. Capas y Entrypoints
- **Entrypoint Backend (FastAPI + Uvicorn):** `src/main.py:app` `[V 2026-11-05]`
- **Frontend SPA (Vanilla HTML/CSS/JS):** `src/static/index.html` `[V 2026-11-05]`
- **Capa de Persistencia (SQLite WAL + Foreign Keys):** `src/database.py` `[V 2026-11-05]`
- **Contratos de Entrada/Salida (Pydantic v2):** `src/schemas.py` `[V 2026-11-05]`
- **Dominio e Inventario FEFO + Costos Ponderados:** `src/services/inventory_service.py` `[V 2026-11-05]`
- **Gestión de Compras, Comparador de Ofertas & Reabastecimiento:** `src/services/purchase_service.py` `[V 2026-11-05]`
- **Gestión de Órdenes de Entrega (OE) y Menaje:** `src/services/order_service.py` `[V 2026-11-05]`
- **Agente de Extracción de Facturas con IA:** `src/services/ai_service.py` `[V 2026-11-05]`
- **Enrutador REST JSON:** `src/api/routes.py` `[V 2026-11-05]`
- **Cliente API Frontend (Vanilla Fetch):** `src/static/js/api.js` `[V 2026-11-05]`
- **Lógica e Interfaz de Usuario:** `src/static/js/app.js` + `src/static/css/styles.css` `[V 2026-11-05]`

## 2. Flujo Operativo de Punta a Punta
1. **Frontera de entrada (API REST JSON):** Rutas `/api/v1/*` validadas estrictamente con esquemas Pydantic.
2. **Reabastecimiento y Compras:**
   - Cálculo automático de faltantes según stock mínimo: $\text{Déficit} = \max(0, \text{Stock Mínimo} - \text{Disponible} + \text{Reservado})$.
   - Solicitudes de compra (RFQ) e ingreso de ofertas de proveedores concurrentes.
   - Matriz comparativa multicriterio (Mejor Precio, Entrega más Rápida, cálculo de ahorro COP/%).
   - Adjudicación y emisión oficial de Órdenes de Compra (OC), con recepción directa a lotes FEFO.
3. **Lógica de inventario y despacho:**
   - Entradas por compra: Creación de lotes, cálculo transaccional de costo promedio ponderado y validación de idempotencia.
   - Salidas y despachos: Asignación automática por política FEFO (fecha de vencimiento más próxima primero), verificación estricta de stock (prohibido inventario negativo).
   - Mermas y bajas: Registro de causa justificada (vencimiento, daño) sin alterar el costo promedio.
   - Órdenes de Entrega (OE): Ciclo completo (Borrador -> Aprobada -> Despachada), desglose de menaje de catering y formato oficial imprimible OE 7217.
4. **Persistencia:** SQLite en modo WAL con `busy_timeout = 30000ms`, transacciones atómicas e integridad referencial forzada.
5. **Auditoría Append-Only:** Toda mutación sensible registra usuario, timestamp ISO-8601, entidad y detalle JSON estructurado en `audit_logs`.

## 3. Invariantes Críticos Inquebrantables
1. Restricción única por `(producto, bodega)` y cero existencias negativas en stock. `[V 2026-11-05]`
2. Consumo prioritario por fecha de expiración ascendente (FEFO); rechazo íntegro ante disponibilidad insuficiente. `[V 2026-11-05]`
3. Recálculo bancario a dos decimales de costo promedio ponderado en cada entrada o recepción de OC. `[V 2026-11-05]`
4. Frontend 100% Vanilla (HTML5 semántico, CSS3 con tokens y JS nativo con `fetch`), sin dependencias de frameworks externos. `[V 2026-11-05]`
5. Bitácora de auditoría inmutable e inviolable vinculada en la misma transacción de cada movimiento. `[V 2026-11-05]`

## 4. Comandos Verificados del Repositorio
- **Ejecución de Servidor Local:** `python -m uvicorn src.main:app --host 127.0.0.1 --port 8000` `[V 2026-11-05]`
- **Pruebas automatizadas (10/10 verdes):** `python -m pytest -v` `[V 2026-11-05]`
- **Compilación de módulos Python:** `python -m compileall -q .` `[V 2026-11-05]`
- **Sincronizar reglas multi-IDE:** `python .agents/sync_agent_config.py` `[V 2026-10-29]`
- **Crear backup seguro:** `python .agents/sync_agent_config.py --create-backup --label "beta-refribreak"` `[V 2026-10-29]`

