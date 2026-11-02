# Avrora Tech — Instrucciones Operativas Universales de Ingeniería

> **Sincronizado dinámicamente desde `.agents/agent.settings.json`**
> **Desarrollador activo:** `Diego Delgado` (`diego`) — Lead Engineer / Arquitectura, IA & Full-Stack
> **Región / Moneda:** CO (COP) | **Zona Horaria:** America/Bogota

---

## 1. Protocolo Obligatorio de Inicio de Sesión
1. Lee `docs/bitacora/NUCLEO.md` completo (máx. 400 líneas).
2. Lee las últimas 30 entradas de `docs/bitacora/BITACORA.md`.
3. Si existe `PROJECT_SPEC.md`, consulta los requerimientos del módulo activo y sus criterios de aceptación.
4. Declara en la primera línea de tu primera respuesta de la sesión:
   `"Núcleo del <fecha>, bitácora hasta <última entrada> | Dev activo: Diego Delgado (diego)"`

---

## 2. Parámetros Operativos del Entorno Activo
- **Ejecución Paralela:** Habilitada (True) | Máximo de subagentes paralelos: `4`.
- **Propiedad Disjunta de Archivos:** Dos subagentes jamás modifican el mismo archivo al mismo tiempo.
- **Multi-IDE:** Emplear `git worktree add ../worktrees/<rama>` para trabajar en ventanas concurrentes sin conflictos.
- **Límites de Ejecución:** Timeout de subagente: `240s` | Reintentos transitorios: `2`.
- **Regla Fail-Fast Pivot-Fast:** Tras `2` fallos consecutivos del mismo enfoque, detente y pivota a una alternativa determinista.
- **Anti-Micro-Reading:** Lectura por bloques lógicos de `300` líneas; prohibido el micro-reading de 20 líneas en bucle.
- **Seguridad Inquebrantable:** `.env, .env.local, .env.development, .env.staging, .env.production, .env.test, vault.enc, license.json` son **100% INMUTABLES**. Prohibido leer, crear, modificar o exponer secretos.
- **Privacidad y Protección de Datos (PII):** Cero datos personales reales de clientes en repositorios, tests o logs.
- **Ramas Git para diego:** `{type}/diego-{slug}` | Ramas protegidas: `main, master, production`.
- **Rúbrica de Calidad:** Mínimo `9.0/10` con pruebas ejecutadas y salida real presentada para cerrar tareas.

---

## 3. Comandos de Verificación del Proyecto
- **Pruebas automatizadas:** `pytest -q`
- **Linter de código:** `ruff check .`
- **Verificación de formato:** `ruff format --check .`
- **Verificación de tipos:** `pyright`
- **Compilación / Build:** `python -m compileall -q .`
- **Crear backup verificado:** `python .agents/sync_agent_config.py --create-backup --label "hito-seguro"`
