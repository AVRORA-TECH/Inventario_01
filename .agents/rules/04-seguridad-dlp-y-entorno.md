---
trigger: always_on
alwaysApply: true
description: "Cercas de seguridad no negociables: inmutabilidad de .env y secretos, privacidad de datos personales (PII / Habeas Data / GDPR) y controles OWASP multi-lenguaje."
---

# 04 — Seguridad, credenciales, privacidad de datos y fronteras de ejecución (NON-NEGOTIABLE)

> **Naturaleza de este documento:** las reglas de las secciones 1 y 2 son invariantes obligatorios de seguridad y cumplimiento. La sección 3 opera bajo principio *fail-closed*: ante cualquier duda sobre si una entrada externa es segura, se rechaza o sanitiza en la frontera antes de procesarla.

## 1. Protección absoluta de `.env` y secretos

### 1.1 Invariante

El archivo `.env` (y sus variantes `.env.local`, `.env.development`, `.env.staging`, `.env.production`, `.env.test`, `vault.enc`, `license.json`, `*.pem`, `*.p12`, `*.key`, `id_rsa*` y cualquier archivo de credenciales o material criptográfico) es **estrictamente inmutable y opaco** para el agente y los scripts automatizados.

### 1.2 Bajo ninguna circunstancia puedes

- Leer, editar, borrar, renombrar, sobrescribir o reformatear `.env` ni sus variantes.
- Listar el contenido de archivos de secretos mediante comandos de shell (`cat`, `Get-Content`, `type`, `head`, `tail`, `rg`, `grep`, `awk`, `sed`) ni mediante herramientas de lectura del IDE.
- Exponer claves API, tokens, contraseñas, cadenas de conexión o certificados en código fuente, comentarios, logs, trazas, fixtures de pruebas, mensajes de commit, descripciones de PR ni en respuestas del chat.
- Solicitar al desarrollador o usuario que pegue credenciales reales en el chat.
- Imprimir el volcado completo de variables de entorno (`env`, `printenv`, `Get-ChildItem Env:`). Si necesitas verificar que una variable está definida, comprueba únicamente su **existencia** (booleano), nunca su valor.

### 1.3 Enforcement técnico en el proyecto

1. **Exclusión en Git:** todo archivo de secretos debe figurar en `.gitignore` y verificarse con `git check-ignore -v <archivo>`.
2. **Hook activo de agente:** `.agents/hooks.json` ejecuta `.agents/security_gate.py` en `PreToolUse` para bloquear lecturas o mutaciones accidentales sobre archivos protegidos y comandos destructivos.
3. **Escaneo de secretos en pre-commit / CI:** emplear `gitleaks`, `trufflehog` o equivalente sobre el historial y los diffs antes de fusionar.
4. **Auditoría de historial al adoptar un repositorio:** verificar con `git log --all --full-history -- "**/.env*" "**/*.pem" "**/*.key"` que ningún secreto haya sido commiteado previamente.

### 1.4 Procedimiento cuando se requiere una nueva variable de entorno

1. **No modifiques `.env`.**
2. Implementa la lectura segura en el módulo de configuración del proyecto (validando en el arranque y fallando rápido si falta una variable requerida; prohibido usar valores por defecto inseguros como `"secret123"` para credenciales).
3. Documenta **únicamente el nombre de la variable y un valor ficticio evidente** (`REPLACE_WITH_API_KEY`) en `.env.example` dentro del mismo cambio.
4. Indica explícitamente al desarrollador qué variable debe configurar manualmente en su entorno local.

### 1.5 Respuesta ante exposición accidental de un secreto

Si se detecta un secreto comprometido en el repositorio, logs o historial:
1. Informar de inmediato en la primera línea de la respuesta para que el propietario **revoque y rote** la credencial en el proveedor.
2. No asumir que borrar el archivo en un commit nuevo resuelve la exposición si el commit anterior ya fue compartido.

### 1.6 Enmascaramiento en logs y errores

Todo sistema de logging o reporte de errores debe redactar patrones de tokens (`Bearer ...`, `sk_...`, `ghp_...`, `AKIA...`, cadenas de conexión con contraseña) antes de escribir en consola, disco o telemetría. Ningún endpoint de diagnóstico (`/healthz`) debe devolver valores de configuración sensible.

### 1.7 Gestores de secretos en producción

`.env` es exclusivo para desarrollo local. En entornos productivos, las credenciales se inyectan desde el gestor de secretos de la plataforma (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, HashiCorp Vault o secretos del orquestador) y jamás se empaquetan dentro de imágenes Docker o artefactos compilados.

---

## 2. Privacidad y protección de datos personales (PII / Ley 1581 Habeas Data / GDPR)

Todo sistema que procese información de personas naturales o jurídicas debe cumplir los principios de protección de datos personales aplicables a la jurisdicción del proyecto (definida en `agent.settings.json`):

### 2.1 Clasificación de datos

- **Públicos:** datos de identificación corporativa pública.
- **Privados / Semiprivados:** documentos de identidad personal, teléfonos, direcciones, correos personales, historial financiero o contable.
- **Sensibles:** datos de salud, biométricos, menores de edad o convicciones personales (requieren cifrado estricto, control de acceso auditado y autorización explícita).

### 2.2 Reglas operativas obligatorias

1. **Cero PII real en código, pruebas o repositorios:** queda prohibido incluir nombres reales de clientes, documentos de identidad, NITs personales, extractos financieros, teléfonos o correos reales en tests, semillas (`seeds`), fixtures o capturas.
2. **Datos 100% sintéticos en pruebas:** toda suite de pruebas debe utilizar datos generados sintéticamente y claramente ficticios (`user@example.com`, documentos de rango reservado de prueba).
3. **Minimización y retención:** capturar, almacenar y registrar en logs únicamente los campos estrictamente necesarios para la operación. Los identificadores en logs deben ir seudonimizados o en hash cuando corresponda.
4. **Anonimización irreversible para diagnóstico:** si se requiere reproducir un bug originado con datos de producción, se construye primero un caso sintético equivalente e irreversiblemente anonimizado antes de incorporarlo como test de regresión.

---

## 3. Validación de entradas y seguridad de aplicaciones (OWASP)

Toda entrada externa (peticiones HTTP, CLI, webhooks, archivos subidos, mensajes MQTT/WebSocket, bases de datos externas y salidas de LLMs) se trata como **no confiable**:

### 3.1 Prevención de inyección (SQL / NoSQL / Command / Template)

1. **Consultas parametrizadas:** prohibido construir consultas SQL o NoSQL concatenando o interpolando cadenas (`f"SELECT ... {val}"`, `` `SELECT ... ${val}` ``, `fmt.Sprintf`). Usa siempre parámetros preparados del driver o del ORM.
2. **Ejecución de comandos de sistema:** prohibido invocar shells con cadenas interpoladas (`shell=True`, `child_process.exec`, `system()`). Usa llamadas de proceso con arreglo de argumentos separados y valida contra una lista blanca.

### 3.2 Prevención de XSS y seguridad en Frontend

1. Prohibido inyectar contenido no confiable mediante `innerHTML`, `outerHTML`, `document.write` o `dangerouslySetInnerHTML`. Usa `textContent` o el escapado nativo del motor de componentes, o sanitiza explícitamente con una biblioteca auditada (`DOMPurify`).
2. Prohibido `eval()`, `new Function()` o temporizadores con cadenas de código.
3. Validar esquemas de URL en enlaces dinámicos (permitir solo `https:`, `http:`, `mailto:` según corresponda; bloquear `javascript:` y `data:`).

### 3.3 Prevención de Path Traversal y subida segura de archivos

1. Al operar sobre rutas derivadas de entradas externas, resuelve la ruta canónica (`Path.resolve()`, `path.resolve()`, `filepath.Clean` + evaluación de symlinks) y comprueba que sea hija estricta del directorio base autorizado.
2. Nunca almacenes archivos subidos usando directamente el nombre original enviado por el cliente; asigna un identificador seguro (UUID/hash), valida tamaño máximo y verifica tanto la extensión como la firma real del contenido (magic bytes).

### 3.4 Resiliencia en llamadas de red y hardware externo

1. **Timeouts obligatorios:** toda llamada HTTP, RPC, consulta a base de datos o lectura de puerto serie/Modbus/MQTT debe especificar un `timeout` explícito (`external_io_timeout_sec`, por defecto `15s`).
2. **Reintentos acotados:** aplica reintentos con *exponential backoff + jitter* únicamente ante fallos transitorios (red, HTTP 429/502/503/504) y sobre operaciones idempotentes.
3. **Prevención de SSRF:** si el sistema realiza peticiones a URLs provistas por el usuario, valida el esquema y dominio contra una lista blanca y bloquea rangos de IP privados, loopback (`127.0.0.0/8`, `::1`) y endpoints de metadatos cloud (`169.254.169.254`).

### 3.5 Confirmación en operaciones destructivas

1. Eliminar tablas, purgar directorios, truncar colecciones o sobrescribir firmware requiere confirmación explícita del usuario y un backup verificado previo (`doc 03 §3`).
2. Prohibido ejecutar sentencias `DELETE` o `UPDATE` masivas sin cláusula `WHERE` verificada.

### 3.6 Autenticación, autorización y dependencias

1. **AuthN y AuthZ:** utiliza bibliotecas probadas para autenticación y hashing de contraseñas (`argon2`, `bcrypt`, `scrypt`). Verifica permisos explícitos (autorización) en cada endpoint o acción crítica, previniendo vulnerabilidades IDOR.
2. **Cadena de suministro:** todo proyecto debe mantener su archivo de bloqueo de dependencias actualizado (`package-lock.json`, `pnpm-lock.yaml`, `poetry.lock`, `uv.lock`, `Cargo.lock`, `go.sum`, `packages.lock.json`).

### 3.7 Seguridad en integraciones con LLMs

Las salidas de modelos de lenguaje y los argumentos propuestos para herramientas se tratan como entrada externa no confiable: valida su esquema antes de ejecutarlos y nunca pases la salida cruda de un LLM a un intérprete de código, shell o motor SQL.
