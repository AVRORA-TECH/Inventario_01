---
trigger: always_on
alwaysApply: true
description: "Memoria estructural del proyecto entre sesiones: protocolo de inicio y cierre con NUCLEO.md, BITACORA.md y BACKLOG.md, mantenimiento y compactación."
---

# 06 — Núcleo, bitácora y control de alcance (memoria persistente entre sesiones)

> Un modelo de lenguaje inicia cada sesión sin memoria previa. Este sistema garantiza que **cualquier agente en cualquier IDE y lenguaje comprenda la arquitectura, invariantes y decisiones del proyecto en una lectura rápida (~1–2 minutos)** sin consumir toda la ventana de contexto.

## 1. Protocolo obligatorio de inicio de sesión

Antes de modificar código en una sesión nueva:

1. **Leer `.agents/agent.settings.json`** para identificar el desarrollador activo, el perfil de lenguaje, los comandos de verificación y los límites operativos.
2. **Leer completo `docs/bitacora/NUCLEO.md` (máx. ~400 líneas).**
   - Si no existe, inicialízalo con `python .agents/sync_agent_config.py --init-project` o ejecuta la habilidad `/crear-bitacora`.
3. **Leer las últimas 30 entradas de `docs/bitacora/BITACORA.md`.**
4. **Verificar frescura frente al código real:**
   - Si el archivo que vas a editar es más reciente que su referencia en `NUCLEO.md` o la etiqueta `[V fecha]` supera los 90 días, inspecciona el archivo de código fuente directamente antes de asumir su implementación. Cuando exista discrepancia entre `NUCLEO.md` y el código real, prevalece el código real y se actualiza `NUCLEO.md`.
5. **Declarar en la primera línea de la primera respuesta de la sesión:**
   > `"Núcleo del <fecha>, bitácora hasta <última entrada> | Dev activo: <nombre> (<alias>)"`

---

## 2. Propósito diferenciado de los 3 archivos de memoria

Cada archivo cumple una responsabilidad única y no debe duplicar información de los otros:

| Archivo | Qué registra | Qué NO registra |
| :--- | :--- | :--- |
| `docs/bitacora/NUCLEO.md` | Estado actual de la arquitectura, entrypoints, invariantes y comandos verificados | Historial cronológico de cambios o tareas futuras |
| `docs/bitacora/BITACORA.md` | **Decisiones de arquitectura**, **cambios de contrato** y **diagnósticos de causa raíz** | Listados rutinarios de archivos editados (eso vive en `git log`) |
| `BACKLOG.md` | Mejoras o hallazgos fuera del alcance de la tarea activa (solo si no hay issue tracker externo) | Tareas ya completadas o decisiones ya tomadas |

### A. `docs/bitacora/NUCLEO.md` (máximo ~400 líneas)

Índice técnico verificado del sistema con punteros `archivo:símbolo`:
- **Capas y entrypoints:** por dónde inicia la aplicación y cómo fluye una operación de principio a fin.
- **Mapa de módulos clave:** responsabilidad de cada directorio o componente principal.
- **Invariantes críticos:** reglas de dominio, seguridad y contratos que ningún cambio puede violar.
- **Comandos verificados:** instrucciones exactas para compilar, probar, ejecutar linter y crear backups.
- Cada afirmación incluye su etiqueta fechada: **`[V AAAA-MM-DD]`**, **`[I]`** o **`[?]`**.

### B. `docs/bitacora/BITACORA.md` (append-only)

Registro cronológico e inmutable del **porqué** detrás de decisiones técnicas y diagnósticos complejos. Nunca se borran ni reescriben entradas históricas; las nuevas entradas se agregan al final (o en orden cronológico consistente del archivo) con este formato:

```markdown
## AAAA-MM-DD HH:MM — Título conciso de la decisión o diagnóstico ([Dev: alias])

- **Tipo:** decisión | diagnóstico | cambio de contrato | rechazo
- **Contexto:** problema técnico o requerimiento que motivó la entrada (1–2 líneas).
- **Decisión / causa raíz:** qué se determinó o qué origen se confirmó.
- **Alternativas descartadas:** qué otra opción se evaluó y por qué se descartó.
- **Consecuencias:** impacto en módulos, contratos o operación.
- **Evidencia:** comando ejecutado, test o referencia `archivo:línea`.
- **No verificado:** aspectos que quedan en `[?]`.
- **Pendiente / siguiente:** paso siguiente o referencia a `BACKLOG.md` / issue tracker.
```

### C. `BACKLOG.md` (cerco contra desvío de alcance)

- **Condición de existencia:** solo se mantiene si `use_external_issue_tracker` es `false` en `agent.settings.json`. Si el proyecto utiliza GitHub/GitLab Issues, Linear o Jira, los hallazgos fuera de alcance se registran allí y `BACKLOG.md` no se utiliza.
- Si durante la resolución de una tarea detectas una mejora secundaria no relacionada con el objetivo actual, **no interrumpas la tarea activa**: regístrala en `BACKLOG.md` con su severidad (`Crítico` / `Alto` / `Medio` / `Bajo`) y continúa con el alcance acordado.

---

## 3. Mantenimiento, caducidad y compactación

### 3.1 Actualización al cierre de tarea

Al finalizar cualquier cambio que agregue o mueva módulos, modifique contratos o cambie comandos de construcción/prueba, actualiza la sección correspondiente de `NUCLEO.md` con la fecha actual `[V AAAA-MM-DD]`.

### 3.2 Caducidad de etiquetas `[V]`

Toda etiqueta `[V AAAA-MM-DD]` con más de **90 días** de antigüedad se considera expirada y debe tratarse como `[?]` hasta que un agente o desarrollador vuelva a verificar el módulo contra el código fuente actual.

### 3.3 Desglose modular y archivo de bitácora

- Si `NUCLEO.md` se acerca a las **400 líneas**, extrae el detalle de los submódulos secundarios a `docs/bitacora/modulos/<modulo>.md` y conserva en `NUCLEO.md` el resumen arquitectónico y los punteros.
- Si `BITACORA.md` supera las **150 entradas**, mueve las entradas más antiguas a `docs/bitacora/archivo/BITACORA-AAAA.md`, conservando un índice resumido y las últimas 30 entradas activas en `docs/bitacora/BITACORA.md`.
