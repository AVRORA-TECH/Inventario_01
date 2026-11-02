---
trigger: always_on
alwaysApply: true
description: "Protocolo forense de causa raíz en 6 pasos, patrones prohibidos y estándar universal de observabilidad, logs y apagado ordenado."
---

# 02 — Causa raíz y observabilidad (cero parches cosméticos)

## 1. Protocolo obligatorio de 6 pasos para cualquier defecto

Cuando ocurre un fallo, está prohibido adivinar o aplicar parches superficiales. Ejecuta estos 6 pasos en orden estricto:

1. **Reproducir:** obtén un caso mínimo que falle de forma repetible (test automatizado, comando CLI o petición reproducible). Si no es reproducible en el entorno actual, decláralo explícitamente e indica qué insumo necesitas (seed, versión, configuración, traza); nunca inventes la causa.
   - *Fallos probabilísticos o intermitentes (concurrencia, condiciones de carrera):* instrumenta primero en modo observación y documenta la tasa de fallo observada ($N$ de $M$ corridas). No avances al paso 2 sin reproducir el fallo o declarar formalmente por qué no fue posible.
2. **Hipótesis con criterio de falsación:** formula qué sospechas que ocurre y qué dato concreto en código, estado o logs confirmaría o refutaría esa hipótesis (por ejemplo: *"Si el pool de conexiones se agota por falta de cierre en rutas de error, las métricas del pool mostrarán conexiones activas crecientes tras cada petición fallida"*).
3. **Evidencia literal (los 3 registros de la verdad):**
   - **Logs del sistema/aplicación** con stack trace o contexto de error completo.
   - **Estado / trazas / persistencia** (inspeccionados en modo solo lectura o sobre copia temporal para no bloquear bases activas).
   - **Código fuente real** (`archivo:línea` leído en la sesión actual).
   Presenta citas literales y el comando con el que las obtuviste, nunca paráfrasis sin evidencia.
4. **Corregir en el origen:** repara exactamente donde nace el estado inválido o se rompe el contrato, no donde explota varias capas más abajo.
5. **Test de regresión (rojo -> verde):** escribe una prueba automatizada que **falle antes del arreglo** y **pase después del arreglo**. Presenta ambas salidas como evidencia.
6. **Verificación integral:** ejecuta el linter, verificador de tipos y suite de pruebas del proyecto (`agent.settings.json`) para confirmar cero regresiones colaterales.

Etiqueta todo arreglo como:
- **`[CAUSA RAÍZ]`**: origen confirmado con evidencia reproducible y eliminado.
- **`[MITIGACIÓN]`**: contención temporal del impacto cuando la causa raíz depende de un tercero o requiere un rediseño mayor (registra el seguimiento en el issue tracker o `BACKLOG.md`).

---

## 2. Patrones estrictamente prohibidos como "arreglo"

- Bloques silenciosos que ocultan errores (`try ... except: pass` en Python, `catch (e) {}` vacío en JS/TS/Java/C#, `_ = err` en Go, `.unwrap_or_default()` indiscriminado sobre errores críticos en Rust). Toda excepción no fatal suprimida deliberadamente debe ser específica y dejar rastro en log.
- Añadir `sleep` / `setTimeout` arbitrarios o multiplicar timeouts sin haber diagnosticado el bloqueo o condición de carrera subyacente.
- Condicionales defensivos internos (`if (x == null) return`) que silencian una violación de contrato interno en lugar de validar en la frontera o fallar ruidosamente.
- Modificar, debilitar, comentar o saltar (`skip`, `xfail`, `#[ignore]`, `.skip()`) un test existente únicamente para que la suite pase en verde.
- Desactivar globalmente advertencias del compilador o linter (`# noqa` masivo, `eslint-disable` global, `@SuppressWarnings("all")`, `allow(warnings)`).
- Ignorar códigos de salida de subprocesos o comandos externos.

---

## 3. Estándar universal de observabilidad y ciclo de vida en producción

### 3.1 Logging estructurado

1. **Trazabilidad completa:** todo error inesperado se registra con stack trace completo, nombre del componente, operación y contexto seguro.
2. **Privacidad por diseño:** usa una lista blanca (allowlist) de campos registrables. Prohibido escribir secretos, tokens, contraseñas o PII en logs.
3. **Formato:** JSON o clave-valor estructurado en producción; formato legible en desarrollo local.
4. **Correlation / Trace ID:** toda petición, trabajo en segundo plano o transacción propaga un identificador único entre capas.
5. **Semántica de niveles:** `ERROR` (requiere acción), `WARN` (degradación recuperable), `INFO` (hitos de negocio/sistema), `DEBUG` (diagnóstico desactivado por defecto en producción). Evita escribir en `stdout` mediante funciones de depuración (`print`, `console.log`, `fmt.Println`) en módulos de biblioteca o servidores productivos.

### 3.2 Rotación de logs en disco

Si la aplicación escribe logs en archivos locales (servidores on-premise, dispositivos IoT/embebidos, aplicaciones de escritorio), debe configurar rotación por tamaño y límite máximo de archivos retenidos para evitar agotar el almacenamiento.

### 3.3 Apagado ordenado (Graceful Shutdown)

Todo servicio de larga duración, worker o daemon debe:
1. Capturar señales de terminación (`SIGTERM`, `SIGINT` o eventos del SO) e iniciar el drenaje ordenado de operaciones en curso.
2. Aplicar un **timeout de gracia** acotado (5–10 s) tras el cual se fuerza el cierre.
3. Ser **idempotente** ante invocaciones repetidas de la rutina de cierre.
4. Sincronizar y cerrar limpiamente conexiones a bases de datos (por ejemplo, `PRAGMA wal_checkpoint(TRUNCATE)` en SQLite) y colas de mensajes.
5. Terminar el árbol completo de procesos hijos y liberar puertos, descriptores de archivo y locks antes de finalizar.

### 3.4 Verificación de salud (Health Checks)

Todo servicio continuo debe exponer un mecanismo de salud (`/healthz`, `/readyz`, latido MQTT o diagnóstico CLI) que valide tanto que el proceso responde como que sus dependencias críticas son alcanzables.
