---
name: arrancar-proyecto
description: Inicia un proyecto nuevo en cualquier lenguaje leyendo PROJECT_SPEC.md, validando contratos, preparando entorno y Git, y desplegando módulos en paralelo con gates obligatorios.
---

# Habilidad: Arrancar Proyecto (/arrancar-proyecto)

Ejecuta este procedimiento para iniciar la construcción de un sistema o módulo mayor a partir de una especificación aprobada (`PROJECT_SPEC.md`), aplicando las reglas `00` a `06` en cualquier lenguaje de programación.

## Prerrequisitos (bloqueantes)

1. `PROJECT_SPEC.md` existe y define el alcance funcional y técnico. Si no existe, detente y solicita o acuerda la especificación antes de escribir código (`doc 00 §1`).
2. `.agents/agent.settings.json` tiene configurados el desarrollador activo (`active_alias`), el perfil de lenguaje (`stack_profile`) y los comandos de verificación (`test`, `lint`, `format_check`, `typecheck`, `build`).
3. `.gitignore` excluye archivos sensibles y artefactos pesados (`.env*`, `.backups/*`, bases de datos locales y carpetas de dependencias/compilación). Verifica con `git check-ignore -v .env` (`doc 03 §2.1`, `doc 04 §1.3`).

---

## Pasos de Ejecución

### 1. Inspección de especificación y configuración

1. Lee `.agents/agent.settings.json` y `PROJECT_SPEC.md` completo.
2. Identifica:
   - Lenguaje, runtime y arquitectura objetivo.
   - Modelo de datos, esquemas y contratos de comunicación.
   - Módulos requeridos, sus fronteras de responsabilidad y criterios de aceptación.
   - Requerimientos de seguridad y privacidad de datos (`doc 04`).
3. Declara el alcance validado con `[V]` y cualquier punto ambiguo con `[?]`. Si existe una ambigüedad bloqueante, resuélvela antes de continuar.

### 2. Inicialización de memoria, entorno y rama Git

1. Ejecuta `python .agents/sync_agent_config.py --init-project` (agregando `--stack <lenguaje>` si corresponde) para inicializar `docs/bitacora/NUCLEO.md`, `docs/bitacora/BITACORA.md`, `.env.example` y sincronizar los archivos de instrucciones (`AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`).
2. Crea la rama de trabajo según `doc 03 §1`:
   ```bash
   git checkout -b feat/<alias>-arquitectura-base
   ```
3. Verifica que `.gitignore` cubra el lenguaje elegido.

### 3. Fase 1 — Cimientos comunes y contratos (Coordinador)

Construye de forma secuencial el esqueleto compartido que ningún subagente debe inventar por su cuenta:

1. **Módulo de configuración:** lectura tipada y segura de variables de entorno con fallo rápido (*fail-fast*) en el arranque si falta una variable obligatoria. Prohibido usar valores por defecto inseguros para credenciales (`doc 04 §1.4`).
2. **Capa de persistencia / infraestructura base:** inicialización idempotente de esquemas/migraciones y manejo ordenado de conexiones.
3. **Contratos e interfaces públicas:** tipos de dominio, DTOs, esquemas de validación y firmas de servicios.
4. **Plantilla de entorno:** actualiza `.env.example` con las variables requeridas usando valores ficticios evidentes.

### 4. Fase 1.5 — Validación de contrato (Gate obligatorio, `doc 01 §1`)

**Antes de despachar subagentes en paralelo**, comprueba que los contratos sean válidos y compilables ejecutando los comandos `typecheck` y `build` de `.agents/agent.settings.json`:

- Los tipos e interfaces compilan sin errores.
- Las migraciones o esquemas de datos aplican en limpio sobre un entorno temporal.
- Los contratos de API (OpenAPI, GraphQL, Protobuf, JSON Schema) son sintácticamente válidos.

**Prohibido avanzar a la Fase 2 si este gate falla.**

### 5. Fase 2 — Despliegue modular en paralelo

Invoca la habilidad `/ejecucion-paralela`:

1. Divide los módulos de `PROJECT_SPEC.md` garantizando **propiedad de archivos 100% disjunta** (`strict_disjoint_file_ownership`).
2. Despacha hasta `max_parallel_subagents` subagentes simultáneos entregando a cada uno su lista exclusiva de archivos editables, los contratos de solo lectura y su comando de prueba.
3. Si algún subagente reporta `BLOQUEADO`, resuelve el bloqueo en la capa de contrato antes de reintentar.

### 6. Fase 3 — Integración, verificación y cierre (Coordinador)

1. Integra los módulos en los puntos de entrada o archivos de registro compartidos.
2. Verifica conformidad estricta con el contrato de la Fase 1.5.
3. Ejecuta los comandos de `lint`, `format_check`, `typecheck`, `build` y `test` configurados en `.agents/agent.settings.json` (dos corridas consecutivas verdes de la suite de pruebas para confirmar determinismo, `doc 05 §1.5`).
4. Actualiza `docs/bitacora/NUCLEO.md` con el mapa real de módulos y etiquetas `[V AAAA-MM-DD]`.
5. Registra en `docs/bitacora/BITACORA.md` las decisiones de arquitectura tomadas (`doc 06 §2.B`).
6. Realiza commits atómicos siguiendo Conventional Commits (`doc 03 §2.2`) y entrega el informe de cierre en modo completo (`doc 00 §4`).
