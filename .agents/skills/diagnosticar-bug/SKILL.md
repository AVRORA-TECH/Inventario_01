---
name: diagnosticar-bug
description: Diagnostica y corrige defectos en su causa raíz mediante el protocolo forense de 6 pasos, criterio de falsación observable y prueba de regresión rojo-verde.
---

# Habilidad: Diagnosticar Defecto (/diagnosticar-bug)

Ejecuta este procedimiento para investigar y resolver cualquier bug o regresión aplicando estrictamente `doc 02 §1–§2`. **Está prohibido modificar código de producción antes de completar el Paso 3.**

## Pasos de Ejecución

### 1. Reproducir el fallo de forma determinista

1. Delimita qué entrada o acción dispara el problema, cuál es el resultado esperado y cuál es el fallo observado.
2. Construye o ejecuta un caso mínimo repetible (test automatizado, comando CLI o petición aislada) y guarda la salida exacta del error (`doc 00 §2`).
3. **Fallos intermitentes o de concurrencia:** si el fallo es probabilístico, instrumenta primero en modo observación y mide la frecuencia de aparición ($N$ de $M$ ejecuciones).
4. **No reproducible en el entorno actual:** no adivines ni propongas parches a ciegas; declara qué dato adicional se requiere para reproducirlo y detente.

### 2. Formular hipótesis con criterio de falsación

Formula por escrito la causa sospechada junto con la prueba observable que la confirmaría o refutaría:

```text
Hipótesis: <qué estado inválido o contrato roto produce el síntoma>
Criterio de falsación: <qué línea de código, traza o estado en disco/BD debe observarse si la hipótesis es cierta>
```

### 3. Recolectar evidencia literal en los 3 registros de la verdad

Inspecciona y cita literalmente (`[V]`):
1. **Logs / salida de error:** stack trace completo y mensaje exacto.
2. **Estado / persistencia / trazas:** datos involucrados leídos sin alterar ni bloquear el entorno.
3. **Código fuente real:** `archivo:línea` donde se origina el estado defectuoso.

Si la evidencia refuta la hipótesis del Paso 2, descártala y formula una nueva basada en los hallazgos reales.

### 4. Corregir en la causa raíz

1. Repara el defecto exactamente donde nace el estado inválido o la violación de contrato, nunca enmascarando el síntoma capas más abajo.
2. Respeta las prohibiciones de `doc 02 §2`: cero bloques `try/catch` o `try/except` vacíos, cero `sleep` arbitrarios y cero debilitamiento de pruebas existentes.

### 5. Prueba de regresión verificada (Rojo -> Verde)

1. Escribe un test automatizado que reproduzca el caso exacto del Paso 1.
2. Comprueba que el test **falle (rojo)** sin la corrección y **pase (verde)** con la corrección aplicada (`doc 05 §1.2`).
3. Incluye el bloque de cabecera del archivo de prueba (`Level`, `Prevents`, `Isolation`, `Covers`).

### 6. Verificación integral y registro

1. Ejecuta la suite completa de pruebas, linter y verificación de tipos definidos en `.agents/agent.settings.json` para asegurar cero regresiones colaterales.
2. Si la causa raíz no era obvia, añade la entrada diagnóstica correspondiente en `docs/bitacora/BITACORA.md` (`doc 06 §2.B`).
3. Entrega el reporte etiquetando la solución como `[CAUSA RAÍZ]` o `[MITIGACIÓN]`.
