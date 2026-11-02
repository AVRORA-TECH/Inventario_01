---
trigger: always_on
alwaysApply: true
description: "Estándar universal de pruebas automatizadas (comportamiento real, aislamiento hermético, determinismo), rúbrica de calidad 1–10 y Definition of Done."
---

# 05 — Estándar de testing, autoevaluación y Definition of Done (DoD)

> **Alcance:** aplica a todo módulo nuevo, integración, corrección de defecto y refactor en cualquier lenguaje de programación. Un entregable sin ejecución real del comando de pruebas del proyecto tiene un puntaje máximo de **6.0/10** (`doc 00 §5`).

## 1. Reglas no negociables de testing

Ningún módulo nuevo, integración o corrección de bug se considera terminado sin pruebas automatizadas verificables y reproducibles mediante el comando `test` definido en `.agents/agent.settings.json`.

### 1.1 Probar comportamiento observable, no detalles internos

Un test es válido si cumple estas tres propiedades:
1. **Describe un contrato o invariante del sistema:** el nombre identifica qué comportamiento garantiza ante el consumidor (`test_invoice_reconciliation_rejects_duplicate_payment`), no cómo está implementado internamente.
2. **Consume la interfaz pública:** invoca la función exportada, clase pública, endpoint o CLI del módulo sin depender de atributos o funciones privadas.
3. **Resiste refactorizaciones internas:** si se optimiza la estructura interna sin cambiar el contrato público, el test sigue pasando sin requerir ediciones.

### 1.2 Prohibición de tests tautológicos o que no puedan fallar

Quedan prohibidos como prueba:
- Aserciones triviales (`assert True`, `expect(true).toBe(true)`, `assert result is not None` sin verificar el contenido del resultado).
- Bloques `try/catch` o `try/except` dentro del test que silencien fallos en lugar de usar el mecanismo nativo del framework (`pytest.raises`, `expect(...).toThrow()`, `assertThrows`).
- Comparar la salida de una función consigo misma (`assert fn(x) == fn(x)`).
- Ignorar o deshabilitar tests (`skip`, `xfail`, `.skip`, `#[ignore]`) para lograr que la suite pase.

**Verificación rojo -> verde:** todo test nuevo o de regresión debe comprobarse viendo cómo falla cuando el defecto está presente (o mutando temporalmente la condición crítica) y cómo pasa una vez aplicada la solución.

### 1.3 Documentación clara del propósito en archivos de prueba

Cada archivo de prueba debe incluir al inicio un bloque breve de comentarios o docstring en el idioma del código indicando:

```text
Level: unit | integration | e2e
Prevents: <qué defecto real o rotura de contrato previene este archivo>
Isolation: <cómo garantiza que no toca red externa real, .env ni datos de producción>
Covers: <comportamiento público o requerimiento cubierto>
```

### 1.4 Aislamiento hermético

1. La suite estándar de pruebas debe correr de forma 100% local y determinista: sin depender de conexión a internet, sin consumir APIs externas de pago y sin leer ni modificar bases de datos de desarrollo o producción.
2. Toda persistencia en pruebas unitarias o de integración local utiliza directorios temporales limpios por test (`tmp_path`, `t.TempDir()`, contenedores efímeros o bases SQLite temporales) y datos 100% sintéticos.
3. Las pruebas que requieran hardware físico o servicios externos reales se separan en una categoría explícita (`live` / `e2e-external`) excluida de la corrida rápida por defecto.

### 1.5 Determinismo estricto

1. Prohibido depender de la hora real del sistema, zonas horarias del host, semillas aleatorias no fijadas o del orden de ejecución entre archivos de prueba. Inyecta relojes controlables o congela el tiempo en las pruebas que dependan de fechas/expiración.
2. Prohibido usar esperas fijas (`sleep`) para sincronizar asincronía; utiliza eventos deterministas, promesas resueltas o condiciones con polling acotado.
3. Toda suite modificada debe poder ejecutarse dos veces consecutivas en verde con el mismo resultado.

---

## 2. Rúbrica objetiva de calidad (1–10)

Al cerrar cualquier tarea en modo completo (`doc 00 §4`), califica el entregable con base en evidencia verificada:

| Criterio | Peso | Evidencia requerida |
| :--- | :---: | :--- |
| **1. Correctitud funcional** | 30% | Cumple la especificación y maneja casos borde (nulos, vacíos, límites numéricos, codificación UTF-8, errores de frontera). |
| **2. Calidad y mantenibilidad** | 20% | Código claro, modular, tipado/validado, con nombres expresivos y cero código muerto o duplicación innecesaria. |
| **3. Seguridad y privacidad** | 15% | `.env` intacto, entradas externas validadas, consultas parametrizadas, cero secretos o PII expuestos. |
| **4. Rendimiento y confiabilidad** | 15% | Timeouts explícitos, manejo limpio de recursos/conexiones y ausencia de bloqueos o fugas. |
| **5. Testing** | 10% | Suite de pruebas y test de regresión ejecutados en verde con salida real presentada. |
| **6. Documentación y memoria** | 10% | `NUCLEO.md`, `BITACORA.md` (si hubo decisión/diagnóstico) y comentarios de "por qué" actualizados. |

- **Umbral de cierre:** el puntaje mínimo para declarar una tarea completada es el configurado en `minimum_quality_score_out_of_10` (por defecto **9.0/10**).

---

## 3. Checklist de Definition of Done (DoD)

Antes de dar por finalizada una tarea, verifica cada punto aplicable (si un punto no pudo verificarse en el entorno actual, decláralo como `[?]` en lugar de marcarlo como completado):

- [ ] La solución resuelve la causa raíz o implementa el alcance exacto requerido sin romper contratos existentes.
- [ ] El comando de **linter / formato** (`lint` / `format_check` en `agent.settings.json`) pasa sin errores.
- [ ] El comando de **tipado / compilación** (`typecheck` / `build` en `agent.settings.json`) finaliza con código de salida `0`.
- [ ] El comando de **pruebas automatizadas** (`test` en `agent.settings.json`) pasa en verde y su salida real está incluida en el reporte.
- [ ] Los archivos protegidos (`.env`, secretos) permanecen intactos y `git status` / `git diff` no contienen credenciales, artefactos basura ni PII.
- [ ] `docs/bitacora/NUCLEO.md` refleja cualquier cambio estructural con etiqueta `[V AAAA-MM-DD]` y `docs/bitacora/BITACORA.md` registra las decisiones arquitectónicas o diagnósticos relevantes.
