---
name: ejecucion-paralela
description: Orquesta de 2 a 4 subagentes en paralelo con validación previa de contratos, propiedad disjunta de archivos y formato estandarizado de reporte.
---

# Habilidad: Ejecución Paralela (/ejecucion-paralela)

Utiliza este procedimiento cuando debas construir, refactorizar o auditar 2 o más módulos independientes simultáneamente aplicando `doc 01 §1–§4`.

## Prerrequisitos (Gate obligatorio antes del Fan-Out)

1. **Contratos validados (`doc 01 §1 Fase 1.5`):**
   - Los tipos, interfaces y esquemas comunes ya existen y pasan `typecheck` / `build`.
   - **Prohibido despachar subagentes si el contrato base no compila.**
2. **Límite de concurrencia:** respeta `max_parallel_subagents` de `.agents/agent.settings.json` (por defecto `4`). Si existen más módulos que slots, encola por prioridad (`riesgo × dependencia`).
3. **Propiedad disjunta garantizada (`strict_disjoint_file_ownership`):** verifica que las listas de archivos editables asignadas a cada subagente no tengan intersección alguna.

---

## Matriz de Roles

| Rol | Permisos | Responsabilidad |
| :--- | :--- | :--- |
| **Coordinador** (Agente principal) | Lectura/escritura global + integración | Define contratos (Fase 1 + 1.5), asigna ámbitos disjuntos, integra en archivos compartidos y ejecuta la verificación final. |
| **Explorador** (`Explorer`) | Solo lectura | Audita módulos, esquemas o logs en paralelo y devuelve punteros exactos `archivo:línea` con etiquetas `[V]/[I]/[?]`. |
| **Implementador** (`Implementer`) | Escritura restringida a su lista asignada | Implementa el módulo asignado y sus pruebas unitarias/regresión cumpliendo el contrato. |
| **Verificador** (`Verifier`) | Solo lectura + ejecución de pruebas | Revisa `git diff` en contexto limpio, ejecuta la suite de pruebas y valida casos borde y seguridad. |

---

## Plantilla de Delegación Autocontenida

Al invocar cada subagente, entrégale siempre esta especificación explícita:

```text
MISIÓN: <objetivo funcional y técnico exacto con alcance cerrado>
ARCHIVOS AUTORIZADOS PARA CREAR/EDITAR: <lista explícita de rutas; prohibido tocar cualquier otro archivo>
ARCHIVOS DE SOLO LECTURA (CONTRATOS): <rutas de interfaces, esquemas y configuración>
INVARIANTES OBLIGATORIOS:
- Prohibido leer o modificar .env ni exponer secretos o PII.
- Prohibido usar bloques catch/except silenciosos o sleeps arbitrarios.
- Prohibido modificar archivos fuera de tu lista autorizada; si necesitas un cambio en el contrato compartido, detente y reporta BLOQUEADO.
- Tras 2 fallos consecutivos del mismo enfoque, detente y reporta causa raíz.
COMANDO DE VERIFICACIÓN: <comando exacto de test/lint/typecheck para tu alcance>
FORMATO DE RETORNO REQUERIDO:
  - Tarea:
  - Archivos leídos:
  - Archivos modificados:
  - Comandos ejecutados + salida:
  - Resultado: IMPLEMENTADO | CAUSA RAÍZ | BLOQUEADO
  - Evidencia [V] / [I] / [?]:
```

---

## Reducción e Integración (Coordinador)

Una vez que todos los subagentes finalicen:
1. Si algún subagente devolvió `BLOQUEADO`, ajusta primero el contrato compartido o reasigna archivos antes de relanzar.
2. Conecta los módulos en los puntos de entrada o archivos barril (`index.ts`, `__init__.py`, `main.go`, `lib.rs`, etc.).
3. Verifica que ninguna implementación se haya desviado de las firmas y esquemas de la Fase 1.5.
4. Ejecuta la suite completa de verificación del proyecto (`lint`, `format_check`, `typecheck`, `build`, `test`) y documenta la salida real.
