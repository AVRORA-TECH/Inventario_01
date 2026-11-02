## Resumen Ejecutivo (`[V]` / `[I]` / `[?]`)

- **Objetivo / Causa raíz:** <!-- Describe qué problema resuelve en el origen o qué requerimiento de PROJECT_SPEC.md implementa -->
- **Tipo de cambio:** `feat` | `fix` | `refactor` | `perf` | `test` | `docs` | `chore`
- **Clasificación (si es bug):** `[CAUSA RAÍZ]` | `[MITIGACIÓN]`

---

## Archivos Afectados

- `ruta/al/archivo:línea` — Motivo técnico del cambio.

---

## Evidencia de Validación

> Pega el comando exacto ejecutado (según `.agents/agent.settings.json`) y su salida real.

```text
# Comando(s) de test / lint / build ejecutados y salida:
```

---

## Alcance No Verificado (`[?]`) y Riesgos

- **Riesgos identificados:** <!-- Bajo / Medio / Alto / Crítico -->
- **Pendiente de verificar en entorno externo (`[?]`):** <!-- Si aplica, pasos para probarlo -->

---

## Checklist de Definition of Done (DoD)

- [ ] Resuelve la causa raíz o cumple el contrato especificado sin parches cosméticos.
- [ ] Linter, verificación de tipos y build finalizan sin errores.
- [ ] Pruebas automatizadas (incluyendo test de regresión rojo -> verde si aplica) pasan en verde.
- [ ] `.env` intacto; cero credenciales, tokens o datos personales (PII) en el diff o en logs.
- [ ] `docs/bitacora/NUCLEO.md` y `docs/bitacora/BITACORA.md` actualizados cuando corresponde.

