# BITACORA.md — Registro Append-Only de Ingeniería (Avrora Tech)

## 2026-10-29 08:07 — Inicialización del proyecto y configuración de Agente Universal ([Dev: nicolas])
- Objetivo: Inicializar la estructura de memoria (`NUCLEO.md`, `BITACORA.md`, `BACKLOG.md`) y sincronizar las reglas multi-IDE desde `.agents/agent.settings.json`.
- Archivos tocados: `docs/bitacora/NUCLEO.md`, `docs/bitacora/BITACORA.md`, `BACKLOG.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.windsurfrules`.
- Causa raíz: N/A (Inicialización estructural).
- Evidencia: Ejecución exitosa de `python .agents/sync_agent_config.py --init-project`.
- No verificado: Módulos de negocio pendientes de implementación según `PROJECT_SPEC.md`.
- Pendiente / siguiente: Completar `PROJECT_SPEC.md` y ejecutar `/arrancar-proyecto`.

## 2026-10-29 10:20 — Auditoría, reparación integral y generalización multi-lenguaje de `.agents`, `.backups` y `.github` ([Dev: nicolas])
- **Tipo:** diagnóstico | decisión | cambio de contrato
- **Contexto:** Se requería validar y depurar `.agents`, `.backups` y `.github`, eliminando archivos obsoletos o corruptos y dejando una plantilla 100% profesional y agnóstica para cualquier proyecto y lenguaje.
- **Decisión / causa raíz:**
  1. `[CAUSA RAÍZ]` `.agents/hooks.json` fallaba en Windows (`SyntaxError: unterminated string literal`) por el uso de `python -c "..."` con comillas escapadas en `cmd /c`, y bloqueaba falsos positivos como `.env.example`. Se extrajo la lógica a `.agents/security_gate.py` con expresiones regulares de frontera y lectura dinámica de `immutable_files`.
  2. `[CAUSA RAÍZ]` `.agents/sync_agent_config.py` leía claves inexistentes (`team`, `agent_runtime`, `git`, `security`, `backup`) respecto a `.agents/agent.settings.json`. Se unificó el esquema v2.1.0 e incorporaron `language_presets` (`python`, `node_ts`, `go`, `rust`, `jvm`, `dotnet`, `cpp_embedded`) y verificación triple de backups (`--verify-latest-backup`).
  3. `[CAUSA RAÍZ]` Se repararon 6 reglas truncadas o con encabezados envolventes inválidos (`### archivo.md` / ````markdown`) en `.agents/rules/`, se estandarizaron nombres en kebab-case (`00` a `06` con `trigger: always_on` y `< 24 KB`), se repararon las 5 skills en `.agents/skills/` para que todas sean descubiertas por Antigravity, y se eliminó la carpeta deprecada y duplicada `.agents/workflows/`.
  4. Se limpió el backup obsoleto en `.backups/`, se añadió `.gitignore` universal multi-lenguaje y plantillas profesionales de PR, Issues y CI en `.github/`.
- **Alternativas descartadas:** Conservar `.agents/workflows/` en paralelo a `.agents/skills/` (descartado porque `workflows` está deprecado en Antigravity y generaba duplicación y deriva de instrucciones).
- **Consecuencias:** Descubrimiento completo de las 5 skills y 7 reglas, compatibilidad total del hook `PreToolUse` en Windows/Linux/macOS y soporte directo para proyectos en cualquier stack.
- **Evidencia:** Compilación limpia, pruebas unitarias del gate y sincronizador, ejecución de `python .agents/sync_agent_config.py` y verificación SHA-256 + CRC del nuevo snapshot en `.backups/`.
- **No verificado:** Comandos de un proyecto específico de cliente hasta que se defina `PROJECT_SPEC.md` `[?]`.
- **Pendiente / siguiente:** Definir `PROJECT_SPEC.md` cuando se inicie un proyecto concreto y ejecutar `/arrancar-proyecto`.

## 2026-11-02 18:05 — Implementación Integral de Refribreak Inventory Core (RIC) ([Dev: nicolas])
- **Tipo:** decisión | arquitectura | entrega funcional
- **Contexto:** Construcción del sistema web para control de inventario, costos, trazabilidad FEFO y despacho de refrigerios empresariales para Refribreak, cumpliendo con la especificación técnica de `Refribreak_Arquitectura_y_Desarrollo.docx` y las referencias visuales (panel de órdenes Shopware, tabla Sellerskills, base tipo Airtable y formato oficial físico OE 7217).
- **Decisión / causa raíz:**
  1. **Backend:** FastAPI + Uvicorn exponiendo API REST 100% JSON en `/api/v1/*`, validada con modelos Pydantic v2.
  2. **Persistencia:** SQLite en modo WAL (`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`) con modelos relacionales completos (`warehouses`, `categories`, `products`, `suppliers`, `customers`, `stock`, `lots`, `movements`, `delivery_orders`, `audit_logs`).
  3. **Reglas de Negocio (§8 docx):** Cálculo bancario determinista de costo promedio ponderado, asignación de lotes por política FEFO con rechazo íntegro ante existencias insuficientes (cero stock negativo), registro justificado de mermas y auditoría append-only transaccional.
  4. **Frontend:** Single Page Application construida con HTML5 semántico, Vanilla CSS (design system con paleta Navy, pills Airtable y tipografía Inter) y Vanilla JS puro consumiendo `/api/v1/*` con `fetch` nativo (sin frameworks tipo React o Vue).
  5. **Módulo OE 7217 & Menaje:** Renderizado e impresión fiel de la confirmación física de entrega con desglose de refrigerios servidos y cuadrícula de menaje de catering.
  6. **Agente IA de Facturas:** Endpoint de extracción con score de confianza para agilizar la recepción en bodega.
- **Alternativas descartadas:** Uso de frameworks frontend pesados como React o Vue (descartado por requerimiento explícito del cliente y para evitar dependencias frágiles en la beta).
- **Consecuencias:** Plataforma funcional, rápida, sin deuda técnica, con cobertura de pruebas automatizadas y disponible en `http://127.0.0.1:8000/`.
- **Evidencia:** `pytest -v` con 7 pruebas en verde (unitarias y de API REST con `TestClient`), compilación limpia con `python -m compileall`, servidor activo en `http://127.0.0.1:8000/`.
- **No verificado:** Impresión física en hardware de impresora de bodega `[?]`.
- **Pendiente / siguiente:** Demostración al cliente y recopilación de retroalimentación en la semana del 2 al 6 de noviembre de 2026.

