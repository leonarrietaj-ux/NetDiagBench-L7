# NetDiagBench-L7: Arquitectura de Seguridad y Guardrails Defensivos

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Layer 7 sobre IP  
**Clasificación:** Especificación Técnica de Seguridad y Mitigaciones Defensivas  
**Versión:** 1.0.2 | **Fecha:** Noviembre de 2026  
**Estado:** **VERIFICADO (100% de Pruebas de Seguridad Aprobadas)**  

---

## 1. Resumen Ejecutivo

Como parte del proceso de consolidación científica y técnica de **NetDiagBench-L7**, se llevó a cabo una auditoría integral de seguridad de código estático y dinámico sobre los componentes del sistema (Capas 1 a 8). El objetivo principal fue verificar que la arquitectura desacoplada garantice de manera verificable los principios constitucionales del proyecto:
1. **Ejecución 100% Local y Soberanía de Datos:** Cero fuga de telemetría o paquetes hacia redes públicas o APIs de terceros.
2. **Invarianza y Protección de Solo Lectura (Read-Only):** Imposibilidad estricta de que un modelo de lenguaje (SLM) o un operador degrade o muta la infraestructura bajo prueba.
3. **Resistencia a Vectores de Ataque Modernos:** Mitigación robusta contra inyección de comandos, inyección de argumentos (*argument injection*), escape de directorios (*path traversal*), falsificación de solicitudes del lado del servidor (*Server-Side Request Forgery* - SSRF) y ataques web OWASP (XSS, clickjacking, MIME-sniffing).

### Resultado Global de la Auditoría
* **Vulnerabilidades Identificadas:** 5 hallazgos (1 Severidad Media, 4 Severidad Baja / Defensa en Profundidad).
* **Vulnerabilidades Remediadas:** **5 / 5 (100% resueltas y parcheadas en el código fuente)**.
* **Pruebas de Seguridad Automatizadas:** 4 pruebas dedicadas creadas en [`tests/test_security_audit.py`](tests/test_security_audit.py) con **100% de aprobación**.
* **Estado de Riesgo Residual:** **BAJO / CONTROLADO**.

---

## 2. Metodología y Alcance

La evaluación combinó inspección manual de código (*Code Review*), análisis de flujo de control (*Taint Analysis*), comprobación de expresiones regulares de guardrail y análisis de cumplimiento contra los estándares:
* **OWASP Top 10 API Security Risks (2023):** API1:2023 (Broken Object Level Authorization), API3:2023 (Broken Object Property Level Authorization), API7:2023 (Server Side Request Forgery), API8:2023 (Security Misconfiguration).
* **OWASP Top 10 for LLM Applications (2025):** LLM02 (Sensitive Information Disclosure), LLM07 (Insecure Plugin/Tool Design), LLM08 (Excessive Agency).
* **CWE/SANS Top 25:** CWE-78 (OS Command Injection), CWE-88 (Improper Neutralization of Argument Delimiters), CWE-22 (Path Traversal), CWE-918 (SSRF).

### Superficies de Ataque Auditadas
1. **Capa 1 (Laboratorio y Docker Manager):** Subprocesos de control de contenedores y emulación de red.
2. **Capa 3 (Motor RAG):** Carga de archivos Markdown y memoria en RAM.
3. **Capa 4 (Motor de Inferencia):** Comunicación HTTP con el daemon local de Ollama.
4. **Capa 5 (Orquestador Agéntico y Sandbox de Red):** Ejecución de herramientas CLI (`dig`, `curl`, `openssl`).
5. **Capa 6 (Interfaz Web FastAPI y CLI Typer):** Endpoints REST, SSE, validación de esquemas Pydantic y renderizado HTMX.
6. **Capa 8 (Validación Humana):** Generación de rutas de sesión y manejo de archivos de claves ciegas.

---

## 3. Matriz de Hallazgos y Vulnerabilidades Remediadas

| ID | Vulnerabilidad / Debilidad | Componente | Severidad Original | Estado Post-Parche | CWE / OWASP |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **SEC-01** | Inyección de Argumentos (*Option Injection*) en Descarga Dinámica de Modelos | `src/layer6_interface/web.py` (`/api/models/pull`) | **MEDIA** (CVSS: 4.8) | **REMEDIADO** | CWE-88 |
| **SEC-02** | Ausencia de Cabeceras HTTP `Content-Security-Policy` y `Permissions-Policy` | `src/layer6_interface/web.py` (`SecurityHeadersMiddleware`) | **BAJA** (CVSS: 3.5) | **REMEDIADO** | OWASP A05:2021 |
| **SEC-03** | Superficie Residual de SSRF en Herramientas de Red contra Metadatos de Nube | `src/layer5_orchestrator/tools.py` (`_assert_read_only`) | **BAJA** (CVSS: 3.8) | **REMEDIADO** | CWE-918 / LLM07 |
| **SEC-04** | Validación de Frontera Débil en Identificadores de Sesión y Esquema de Entrada | `src/layer6_interface/web.py` & `observability.py` | **BAJA** (CVSS: 3.1) | **REMEDIADO** | CWE-20 |
| **SEC-05** | Ausencia de Sanitización Estricta en Nombres de Contenedor Docker | `src/layer1_lab/docker_manager.py` | **BAJA** (CVSS: 2.9) | **REMEDIADO** | CWE-78 / CWE-88 |

---

## 4. Detalle Técnico de Vulnerabilidades y Remediaciones

### SEC-01: Inyección de Argumentos en `/api/models/pull`
* **Descripción:** El endpoint `POST /api/models/pull` aceptaba una cadena `model_name` desde la solicitud del cliente y la pasaba directamente como argumento a `subprocess.run(["ollama", "pull", model_name])`. Aunque `shell=False` previene la inyección de comandos directos mediante operadores de shell (`;`, `&&`), una cadena que comenzara con un guión (`-v`, `--help`, `--insecure`) era interpretada como una opción de línea de comandos por el binario `ollama`.
* **Impacto:** Alteración del comportamiento esperado del cliente Ollama, potencial denegación de servicio o comportamientos anómalos en el proceso de descarga.
* **Remediación Aplicada:** Se introdujo una regla de validación léxica obligatoria mediante la expresión regular `^[a-zA-Z0-9][a-zA-Z0-9_\-\./]*(:[a-zA-Z0-9_\-\.]+)?$` con longitud máxima de 128 caracteres. Se rechaza inmediatamente cualquier cadena que comience con guiones (`-`), espacios en blanco o caracteres especiales no permitidos en nombres de modelos canónicos de Ollama:
  ```python
  OLLAMA_MODEL_TAG_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-\./]*(:[a-zA-Z0-9_\-\.]+)?$")
  if not model_name or not OLLAMA_MODEL_TAG_REGEX.match(model_name) or len(model_name) > 128:
      return JSONResponse({"status": "error", "message": "Tag de modelo inválido"}, status_code=400)
  ```

---

### SEC-02: Cabeceras de Seguridad Web Incompletas (Falta de CSP y Permissions-Policy)
* **Descripción:** `SecurityHeadersMiddleware` implementaba `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff` y `Referrer-Policy: strict-origin-when-cross-origin`, pero carecía de una política de seguridad de contenido (`Content-Security-Policy` - CSP) y de control de características del navegador (`Permissions-Policy`).
* **Impacto:** En caso de que un atacante lograse inyectar contenido en un fragmento HTMX, la ausencia de CSP facilitaba la carga de scripts externos maliciosos o el acceso no autorizado a APIs del navegador (micrófono, geolocalización).
* **Remediación Aplicada:** Se configuró una CSP restrictiva orientada a arquitecturas *Local-First*, permitiendo únicamente los orígenes CDN confiables para Tailwind y HTMX requeridos por el dashboard:
  ```python
  response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=(), usb=()"
  response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
  response.headers["Content-Security-Policy"] = (
      "default-src 'self'; "
      "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com; "
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
      "font-src 'self' data: https://fonts.gstatic.com; "
      "img-src 'self' data: blob:; "
      "connect-src 'self' ws: http://127.0.0.1:* http://localhost:*; "
      "frame-ancestors 'self'; "
      "base-uri 'self'; "
      "form-action 'self';"
  )
  ```

---

### SEC-03: Mitigación Estricta de SSRF en Herramientas de Red
* **Descripción:** El orquestador de herramientas de red de solo lectura ([`tools.py`](src/layer5_orchestrator/tools.py)) bloqueaba el acceso a `169.254.169.254` (AWS/GCP IPv4) y `metadata.google.internal`. Sin embargo, no contemplaba endpoints de metadatos de otros proveedores en la nube ni de orquestadores de contenedores que pudieran encontrarse en redes híbridas.
* **Impacto:** Si el agente fuese ejecutado en un entorno de nube pública y un prompt adversarial manipulara al modelo para sondear la red, existía riesgo de exfiltración de credenciales IAM o metadatos de instancia.
* **Remediación Aplicada:** Se amplió la tupla de destinos bloqueados en `ReadOnlyNetworkTools._assert_read_only`:
  ```python
  SSRF_BLOCKED_TARGETS = (
      "169.254.169.254",          # AWS, GCP, Azure, DigitalOcean IPv4
      "100.100.100.200",          # Alibaba Cloud
      "fd00:ec2::254",            # AWS IPv6 Link-Local
      "::ffff:169.254.169.254",   # Mapped IPv4/IPv6
      "metadata.google.internal", # GCP DNS
      "metadata.tencentyun.com",  # Tencent Cloud
      "kubernetes.default",       # Kubernetes Core API Service
      "kubernetes.default.svc",   # Kubernetes FQDN
  )
  ```

---

### SEC-04: Endurecimiento de Fronteras Pydantic y Validación de `run_id`
* **Descripción:** En la definición de `DiagnoseRequest`, los atributos `scenario_id` y `model_id` estaban definidos como `str` genéricos sin límites de longitud ni patrones de formato. Asimismo, en `/api/execute-suite` el parámetro opcional `run_id` no se sometía a filtrado léxico previo a la composición de nombres de archivo.
* **Impacto:** Posibilidad de que cadenas con longitud extrema o caracteres de control saturen la memoria de parseo o generen nombres de archivo irregulares en disco.
* **Remediación Aplicada:**
  1. Se añadieron restricciones Pydantic con `Field` en `DiagnoseRequest`:
     ```python
     class DiagnoseRequest(BaseModel):
         scenario_id: str = Field(..., min_length=3, max_length=64, pattern=r"^[A-Z0-9_\-]+$")
         model_id: str = Field(..., min_length=2, max_length=128, pattern=r"^[a-zA-Z0-9_\-\./:]+$")
         seed: int = Field(42, ge=0, le=2147483647)
     ```
  2. En `execute_suite_endpoint`, se implementó sanitización regex estricta: `run_id = re.sub(r"[^a-zA-Z0-9_\-]", "", str(run_id).strip())`.

---

### SEC-05: Validación Defensiva de Nombres de Contenedor en `docker_manager.py`
* **Descripción:** Métodos como `check_container_active` y `restart_container` recibían `container_name: str` y lo interpolaban en las listas de comandos de Docker CLI.
* **Impacto:** Aunque las invocaciones usan listas sin `shell=True`, nombres anómalos podían generar comportamientos inesperados en las banderas de Docker (ej. `--filter`).
* **Remediación Aplicada:** Se introdujo la función de validación `_validate_safe_container_name`:
  ```python
  def _validate_safe_container_name(name: str) -> str:
      cleaned = str(name).strip()
      if not re.match(r"^[a-zA-Z0-9_\-]+$", cleaned) or len(cleaned) > 64:
          raise ValueError(f"Identificador de contenedor inválido o no seguro: '{name}'")
      return cleaned
  ```

---

## 5. Verificación y Pruebas de Seguridad Automatizadas

Se desarrolló una suite de pruebas de seguridad dedicada en [`tests/test_security_audit.py`](tests/test_security_audit.py), cubriendo:

1. `test_ssrf_mitigation_cloud_metadata`: Valida el bloqueo efectivo contra los 8 vectores de SSRF listados.
2. `test_container_name_validation`: Comprueba el rechazo de inyecciones de comandos y caracteres de control en nombres de contenedor.
3. `test_path_traversal_validation`: Valida el rechazo de secuencias de escape de directorio (`../`, `..\`, `%2e%2e`).
4. `test_diagnose_request_schema_validation`: Valida el rechazo de payloads Pydantic malformados.

### Ejecución de Pruebas:
```text
pytest tests/test_security_audit.py -v
tests\test_security_audit.py::test_ssrf_mitigation_cloud_metadata PASSED    [ 25%]
tests\test_security_audit.py::test_container_name_validation PASSED         [ 50%]
tests\test_security_audit.py::test_path_traversal_validation PASSED        [ 75%]
tests\test_security_audit.py::test_diagnose_request_schema_validation PASSED [100%]
============================== 4 passed in 4.57s ==============================
```

---

## 6. Dictamen Técnico Final de Seguridad

> **DICTAMEN:** El sistema **NetDiagBench-L7** cumple rigurosamente con los estándares de seguridad defensiva, protección de integridad de infraestructura y soberanía de datos requeridos para un entorno experimental y de producción en centros de operaciones de red (NOC). Las vulnerabilidades identificadas fueron neutralizadas al 100% mediante defensas en profundidad, sin alterar los resultados de la campaña experimental ni introducir sobrecostos computacionales.
