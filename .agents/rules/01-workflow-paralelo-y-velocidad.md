---
trigger: always_on
alwaysApply: true
description: "Protocolo de ejecución paralela (fan-out / map-reduce / git worktrees), velocidad operativa, anti-micro-reading y reglas fail-fast / pivot-fast."
---

# 01 — Workflow paralelo, optimización de contexto y velocidad de trabajo

## 1. Regla de oro: paralelizar todo trabajo independiente

El principal cuello de botella en ingeniería asistida por IA es secuencializar tareas independientes o leer archivos en fragmentos diminutos. **El paralelismo es el modo por defecto siempre que no exista una dependencia de datos o de contrato entre tareas.**

### Cuándo activar ejecución en paralelo

1. **Exploración e investigación (2+ áreas independientes):** despacha subagentes de solo lectura (`Explorer`) en paralelo (por ejemplo, uno inspecciona dominio/persistencia, otro API/UI y otro pruebas/configuración) cuando los hallazgos de uno no sean prerrequisito para orientar al otro.
2. **Desarrollo modular (`PROJECT_SPEC.md` con 2+ módulos independientes):**
   - **Fase 1 (Map / Contratos):** el agente principal (`Coordinador`) define los contratos compartidos del sistema (tipos, interfaces, esquemas de base de datos, especificaciones OpenAPI/Protobuf/GraphQL, configuración base).
   - **Fase 1.5 (Validación de contrato — gate obligatorio):** antes de lanzar subagentes, el Coordinador verifica que los contratos compilen o pasen validación de esquema/tipos (según el comando `typecheck` o `build` de `agent.settings.json`). Prohibido iniciar el fan-out con un contrato roto.
   - **Fase 2 (Fan-Out paralelo):** se despachan hasta `max_parallel_subagents` subagentes simultáneos (por defecto `4` en `agent.settings.json`). Si hay más módulos que slots disponibles, se encolan por prioridad (`riesgo × dependencia`) sin exceder el límite.
   - **Invariante de propiedad disjunta (`strict_disjoint_file_ownership`):** dos agentes **jamás** modifican el mismo archivo simultáneamente. Cada subagente recibe una lista cerrada y explícita de archivos que puede crear o editar. Los archivos compartidos de barril o registro (`index.ts`, `__init__.py`, `mod.rs`, `CMakeLists.txt`, rutas raíz) los integra únicamente el Coordinador.
   - **Fase 3 (Reduce & Verify):** el Coordinador integra los cambios, verifica el cumplimiento estricto del contrato de la Fase 1.5 y ejecuta los comandos de `lint`, `typecheck`, `build` y `test` definidos en `agent.settings.json`.
3. **Llamadas a herramientas en un mismo turno:** cuando necesites leer varios archivos, buscar patrones o ejecutar verificaciones independientes, emite todas las llamadas en un único lote paralelo.

---

## 2. Desarrollo multi-IDE concurrente con Git Worktrees

Cuando varios desarrolladores o múltiples instancias de IDE trabajen en paralelo sobre distintas ramas del mismo repositorio:

- Cada rama debe existir o crearse antes de levantar el worktree.
- Cada worktree mantiene sus propias dependencias aisladas (`node_modules`, `.venv`, `target`, `build`); nunca compartas carpetas de dependencias compiladas entre worktrees.

```bash
# Crear entornos físicos aislados compartiendo el historial Git:
git worktree add ../worktrees/feat-core feat/dev-core
git worktree add ../worktrees/feat-ui feat/dev-ui

# Al finalizar, integrar y verificar pruebas:
git worktree remove ../worktrees/feat-core
```

---

## 3. Contrato de delegación y retorno de subagentes

Todo subagente invocado debe recibir un encargo autocontenido y devolver un reporte estructurado:

- **Entrada obligatoria al subagente:**
  1. Objetivo exacto y alcance cerrado.
  2. Lista exclusiva de archivos autorizados para escritura.
  3. Lista de archivos de contrato (solo lectura).
  4. Comando exacto de verificación que debe ejecutar antes de terminar.
- **Formato de retorno del subagente:**
  - `Tarea:` resumen de lo ejecutado.
  - `Archivos leídos:` rutas inspeccionadas.
  - `Archivos modificados:` rutas creadas o editadas.
  - `Comandos + salida:` evidencia real de compilación/pruebas.
  - `Resultado:` `IMPLEMENTADO` | `CAUSA RAÍZ` | `BLOQUEADO`.
  - `Evidencia:` etiquetas `[V]`, `[I]`, `[?]`.
- **Escalado de `BLOQUEADO`:** si un subagente necesita modificar un archivo fuera de su ámbito o detecta una ambigüedad en el contrato, se detiene y reporta `BLOQUEADO` al Coordinador. El Coordinador ajusta el contrato o reasigna la propiedad antes de reintentar; nunca reenvíes el mismo prompt sin resolver la causa del bloqueo.

---

## 4. Higiene de contexto, Fail-Fast y presión de convergencia

1. **Anti-Micro-Reading:** prohibido leer archivos en bloques de 20 líneas dentro de un bucle. Lee bloques lógicos de `250–400` líneas (`preferred_file_read_chunk_lines`) o localiza primero la línea exacta mediante búsqueda por contenido (`grep` / `rg`).
2. **Fail-Fast, Pivot-Fast:** tras `fail_fast_pivot_after_failures` (por defecto `2`) fallos consecutivos con el mismo comando o enfoque, detente inmediatamente. Analiza la causa raíz del fallo y pivota hacia una alternativa determinista.
3. **Circuit Breaker:** prohibido repetir más de `3` llamadas idénticas a una herramienta esperando un resultado diferente.
4. **Optimización basada en evidencia:** ningún cambio se reporta como mejora de rendimiento sin presentar métricas comparativas **Antes vs. Después** (latencia, memoria, operaciones de E/S, tamaño de bundle) y el comando reproducible con el que se midieron.
5. **Presión de convergencia:** si una tarea consume más del 70% del presupuesto de pasos del turno sin converger, prioriza dejar el árbol de trabajo en un estado limpio, compilable y documentado, reportando con precisión el avance `[V]` y el remanente `[?]`.

