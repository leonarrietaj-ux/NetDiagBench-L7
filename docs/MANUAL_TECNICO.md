# NetDiagBench-L7 • Manual Técnico del Sistema

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Layer 7 sobre IP  
**Versión:** 1.0.2 | **Fecha:** Noviembre 2026 | **Aislamiento:** 100% Local (≤ 8 GB VRAM)  

---

## 1. Introducción y Arquitectura General
NetDiagBench-L7 es un framework experimental diseñado para evaluar de forma reproducible el desempeño de Modelos de Lenguaje Pequeños (SLMs) en el diagnóstico de fallas complejas de Capa 7 (DNS, HTTP y TLS) bajo restricciones estrictas de hardware (8 GB VRAM, 32 GB RAM).

### Principios Fundamentales
1. **Ejecución 100% Local:** Ningún dato, registro ni petición sale a internet.
2. **Cuantización a 4 bits:** Formato GGUF Q4_K_M con Ollama / llama.cpp.
3. **Terna Homogénea:** Qwen3-8B (8.2B), GLM-4-9B-Chat (9.0B) y Phi-4-mini-instruct (3.8B).
4. **RAG BM25 Ultraliviano:** Huella en RAM ≤ 0.05 MB (frente al límite máximo de 0.45 GB).
5. **Seguridad Read-Only:** El agente solo opera herramientas de red no invasivas (`dig`, `curl`, `openssl`).
6. **Determinismo Científico:** Temperatura = 0.0, semillas `[42, 1337, 2026]` y 3 réplicas por escenario.

---

## 2. Contratos de Intercambio de Artefactos (src/core/contracts.py)
El sistema opera desacoplado en 8 capas funcionales mediante contratos Pydantic v2:
- **Capa 1 (Laboratorio):** `EscenarioLabContract` (`escenario.yaml` + Logs de contenedor).
- **Capa 2 (Preproceso):** `VentanaLogContract` (`ventana.jsonl` con Drain3 y telemetría).
- **Capa 3 (RAG):** `ContextoRAGContract` (`contexto.md` con fragmentos normativos IETF RFCs 1035/9110/8446).
- **Capa 4 (Inferencia Local):** `RespuestaInferenciaContract` (`respuesta.json` con TTFT y tok/s).
- **Capa 5 (Orquestación):** `TrazaOrquestacionContract` (`traza.jsonl` del grafo LangGraph).
- **Capa 6 (Interfaz y Observabilidad):** `DiagnosticoFinalContract` (`diagnostico.json` y `diagnostico.md`).
- **Capa 7 (Evaluación y MLOps):** `BenchmarkTrialResultContract` (`resultados.csv` con 67 columnas normalizadas y `traza.jsonl`).
- **Capa 8 (Validación Humana y Calibración Inter-Evaluador):** `EtiquetaExperto`, `ClaveCegamientoEntry` (`evaluaciones_originales.csv`, `concordancia.json`).

---



---

## 2.1. Arquitectura de Hardware, Telemetría y Modos de Ejecución

### Hardware Físico y Sensores
1. **Host Experimental:** Procesador AMD64 de 4 núcleos físicos y 8 hilos, 13.8 GB de memoria RAM física total, sistema operativo Windows 11.
2. **GPU Integrada (AMD Radeon 610M):**
   - Utiliza arquitectura de memoria unificada/compartida con la RAM del sistema.
   - **Ausencia de sensor NVML:** Al no disponer de instrumentación física directa de VRAM dedicada, el sistema registra estrictamente `vram_measurement_valid = False`, `vram_measurement_method = "integrated_gpu_shared_unmeasured"` y `vram_peak_gb = null`.
   - **Normativa Multicriterio:** No se redistribuye artificialmente el peso del 20% asignado a la VRAM; el puntaje compuesto completo se reporta como no calculable por limitación de hardware, preservando la validez experimental.
3. **Muestreo Periódico de RAM:** Se implementa sondeo en tiempo real con `psutil.virtual_memory()` y `Process.memory_info()`, registrando memoria total, disponible y pico del proceso.
4. **Energía:** Modalidad etiquetada formalmente como `energy_measurement_type = "estimada"`.

### Modos de Ejecución
- **Inferencia:** `live_ollama` (llamadas HTTP directas al puerto 11434 con modelos cuantizados GGUF Q4_K_M) frente a `deterministic_simulator` (generador sintético determinista calibrado).
- **Laboratorio:** `emulado` (3 contenedores Docker Compose activos: `netdiag-dns-bind9`, `netdiag-http-502`, `netdiag-tls-expired`) frente a `sintetico_determinista` (15 escenarios sintéticos calibrados).

### Capa 8: Validación Humana y Calibración Inter-Evaluador
- **Autenticidad:** Las 108 evaluaciones existentes (54 de E1 y 54 de E2) son evaluaciones humanas reales independientes.
- **Literal `(obs: simulado)`:** Se documenta técnicamente como un marcador de posición de la plantilla por defecto del instrumento de captura cuando el evaluador no requirió justificación en texto adicional, no constituyendo evidencia de simulación.
- **Concordancia:**
  - Matriz N=41: Acuerdo unánime entre evaluadores A y B (TP=31, FP=1, FN=0, TN=9, kappa=0.932).
  - Matriz N=54: Muestra completa con dirimente C (TP=38, FP=1, FN=0, TN=15, kappa=0.955).

## 3. Catálogo de los 18 Escenarios de Falla L7
| ID Escenario | Categoría | Clase de Falla | Componente Afectado | Causa Raíz Esperada |
|---|---|---|---|---|
| `DNS-DEL-01` | DNS | DELEGATION_ERROR | `bind9-zone-delegation` | Error de delegación NS cojo (Lame Delegation) |
| `DNS-NXD-01` | DNS | NXDOMAIN | `bind9-authoritative` | Registro de zona faltante o FQDN inexistente (RCODE 3) |
| `DNS-REF-01` | DNS | DNS_REFUSED | `bind9-authoritative` | Consulta rechazada por lista de control de acceso ACL |
| `DNS-SRV-01` | DNS | SERVFAIL | `bind9-recursive-resolver` | Falla de resolución recursiva o timeout hacia servidor raíz |
| `DNS-TRUNC-01` | DNS | DNS_TRUNCATED_EDNS | `bind9-resolver-firewall` | Respuesta truncada TC=1 por buffer EDNS0 bloqueado |
| `HTTP-POOL-01` | API_GATEWAY | CONNECTION_POOL_EXHAUSTED | `upstream-backend-api` | Agotamiento de pool de conexiones concurrentes en backend |
| `HTTP-403-01` | API_GATEWAY | HTTP_403_FORBIDDEN | `nginx-api-gateway` | Acceso denegado por reglas de autorización o IP |
| `HTTP-429-01` | API_GATEWAY | HTTP_429_RATE_LIMITED | `nginx-rate-limiter` | Límite de tasa de peticiones excedido (Rate Limiting) |
| `HTTP-500-01` | HTTP_WEB | HTTP_500_INTERNAL | `backend-application-code` | Excepción no controlada en el código backend |
| `HTTP-502-01` | API_GATEWAY | HTTP_502_BAD_GATEWAY | `upstream-backend-api` | Conexión rechazada o caída del servicio upstream |
| `HTTP-503-01` | HTTP_WEB | HTTP_503_SERVICE_UNAVAILABLE | `backend-application-pool` | Servicio sobrecargado o en mantenimiento temporal |
| `HTTP-504-01` | API_GATEWAY | HTTP_504_GATEWAY_TIMEOUT | `upstream-backend-database` | Timeout de espera de respuesta desde microservicio |
| `NET-LAT-01` | HTTP_WEB | NETWORK_LATENCY_TC | `network-infrastructure` | Degradación por latencia anómala inyectada con tc-netem |
| `HTTP-ORIGIN-01`| API_GATEWAY | ORIGIN_DOWN | `upstream-cluster` | Servidor de origen fuera de línea o sin conectividad |
| `TLS-CHN-01` | TLS | TLS_CHAIN_INVALID | `nginx-tls-termination` | Cadena de confianza rota por omisión de certificado CA |
| `TLS-CIPH-01` | TLS | TLS_CIPHER_MISMATCH | `nginx-tls-crypto-engine` | Negociación fallida por conjuntos de cifrado incompatibles |
| `TLS-EXP-01` | TLS | TLS_EXPIRED_CERT | `nginx-tls-termination` | Certificado digital X.509 expirado en endpoint seguro |
| `TLS-SNI-01` | TLS | TLS_SNI_MISMATCH | `nginx-tls-termination` | Discrepancia entre SNI y certificado presentado |

---

## 4. Orquestación Agéntica LangGraph y Herramientas Read-Only
El agente opera un `StateGraph` de 6 nodos:
1. `ingest_telemetry`: Recibe logs preprocesados por Drain3.
2. `retrieve_rag_knowledge`: Indexa normativas RFC vía BM25.
3. `formulate_hypothesis`: El modelo plantea una causa probable y elije una herramienta.
4. `execute_read_only_tool`: Invoca `dig`, `curl` u `openssl s_client` bajo sandbox seguro.
5. `evaluate_evidence`: Verifica la concordancia del síntoma técnico.
6. `synthesize_diagnosis`: Estructura el veredicto y plan de mitigación SOP.

---

## 5. Referencia de API REST y CLI
Comandos principales de la CLI Typer:
```bash
# Listar escenarios y modelos
benchapp list-scenarios
benchapp list-models

# Ejecutar escenario individual
benchapp run-scenario DNS-NXD-01 --model phi-4-mini-instruct --seed 42

# Ejecutar benchmark y análisis correlacional
benchapp run-benchmark --quick
benchapp analyze-correlation
benchapp export-excel
benchapp export-pdf --type all

# Servidor web interactivo
benchapp serve-dashboard --port 8000
```

---

## 6. Arquitectura de Seguridad, Sandboxing y Guardrails Defensivos

NetDiagBench-L7 implementa una arquitectura de seguridad por capas (*Defense-in-Depth*) orientada a mitigar vectores de riesgo OWASP Top 10, CWE-78/88 (Command/Argument Injection), CWE-22 (Path Traversal) y CWE-918 (SSRF). Todos los hallazgos y mitigaciones están auditados formalmente en [`docs/INFORME_SEGURIDAD.md`](docs/INFORME_SEGURIDAD.md).

### 6.1. Herramientas de Red en Modo Read-Only Estricto (`src/layer5_orchestrator/tools.py`)
- **Prohibición de Mutación:** El agente solo tiene acceso a `dig`, `curl` y `openssl s_client`. Banderas que alteren estado (`-X POST`, `-X PUT`, `-d`, `-F`, `-T`) son interceptadas y bloqueadas en tiempo de ejecución.
- **Protección Anti-SSRF Multicloud:** El método `_assert_read_only` valida cada destino de red bloqueando rangos de metadatos de proveedores en la nube y clústeres orquestados:
  - AWS IPv4/IPv6: `169.254.169.254`, `fd00:ec2::254`, `instance-data`.
  - Alibaba Cloud: `100.100.100.200`.
  - Google Cloud Platform: `metadata.google.internal`.
  - Tencent Cloud: `169.254.0.2`.
  - Kubernetes CoreDNS: `kubernetes.default`, `kubernetes.default.svc`.
- **Ejecución sin Shell:** Todos los subprocesos de herramientas se despachan con argumentos como listas (`List[str]`), con `shell=False`, anulando la inyección de metacaracteres shell.

### 6.2. Aislamiento de Contenedores y Validación de Nombres (`src/layer1_lab/docker_manager.py`)
- Los nombres de contenedores Docker son validados contra la expresión regular estricta `^[a-zA-Z0-9_\-]+$` y longitud <= 64 caracteres antes de ser pasados a comandos CLI (`docker inspect`, `docker exec`, `docker compose`), previniendo inyección de opciones (`--privileged`, `--volume`).

### 6.3. Guardrails de la Interfaz Web y API FastAPI (`src/layer6_interface/`)
- **Cabeceras HTTP de Seguridad (OWASP):** Implementadas en `SecurityHeadersMiddleware`:
  - `Content-Security-Policy`: Restringe fuentes de scripts, estilos, imágenes y conexiones a dominios autorizados y locales.
  - `X-Frame-Options: DENY` (anti-Clickjacking).
  - `X-Content-Type-Options: nosniff` (anti-MIME sniffing).
  - `Referrer-Policy: strict-origin-when-cross-origin`.
  - `Permissions-Policy: geolocation=(), camera=(), microphone=()`.
  - `Cross-Origin-Opener-Policy: same-origin`.
- **Validación de Esquemas Pydantic:** El endpoint `/api/diagnose` valida `scenario_id` contra regex `^[A-Z0-9_\-]+$` (longitud 3-64), `model` contra `^[a-zA-Z0-9_\-\.:]+$` y restringe `seed` al rango no negativo.
- **Validación de Etiquetas de Modelos Ollama:** En `POST /api/models/pull`, el nombre del modelo es sanitizado contra `^[a-zA-Z0-9][a-zA-Z0-9_\-\./]*(:[a-zA-Z0-9_\-\.]+)?$`, impidiendo inyección de banderas al binario CLI de Ollama (CWE-88).
- **Sanitización de Identificadores de Lote:** En `/api/execute-suite`, el parámetro `run_id` es normalizado eliminando cualquier secuencia fuera de `[a-zA-Z0-9_\-]`, neutralizando intentos de salto de directorio (CWE-22).

### 6.4. Verificación Automatizada de Seguridad
El marco cuenta con una suite de pruebas de seguridad automatizadas en [`tests/test_security_audit.py`](tests/test_security_audit.py):
```bash
pytest tests/test_security_audit.py -v
```
Verifica el bloqueo de inyecciones, cabeceras CSP, SSRF multicloud y sanitización de esquemas con 100% de éxito.

---

## 7. Resultados Consolidados de la Campaña Oficial (162 Corridas)

| Métrica Oficial | GLM-4-9B-Chat | Qwen3-8B | Phi-4-mini-instruct | TOTAL / Promedio |
|---|---:|---:|---:|---:|
| **Aciertos Diagnósticos Completos (`full_text`)** | 40 / 54 (74.1%) | 47 / 54 (87.0%) | 35 / 54 (64.8%) | **122 / 162 (75.3%)** |
| **Aciertos Estrictos (`root_cause`)** | 33 / 54 (61.1%) | 24 / 54 (44.4%) | 14 / 54 (25.9%) | **71 / 162 (43.8%)** |
| **Coincidencia de Clase Canónica (`fault_class`)** | 40 / 54 (74.1%) | 47 / 54 (87.0%) | 33 / 54 (61.1%) | **120 / 162 (74.1%)** |
| **Rúbrica Humana Promedio (0 a 5)** | 4.13 / 5.0 | 4.07 / 5.0 | 3.55 / 5.0 | **3.92 / 5.0** |
| **VRAM Declarada/Estimada (`configs/models.yaml`)** | 5.9 GB | 5.5 GB | 2.8 GB | Min: 2.8 GB |
| **Puntaje VRAM Ponderado (20%)** | 0.0949 | 0.1018 | 0.2000 | Fórmula: $0.20 \times \frac{2.8}{\text{VRAM}}$ |
| **Puntaje Compuesto Provisional** | 0.8126 | 0.8252 | 0.7027 | Modelo Líder: Qwen3-8B |

- **Prueba de Friedman:** $\chi^2 = 6.8205$, $p = 0.0331$ (Diferencia estadísticamente significativa entre modelos a $\alpha=0.05$).
- **Post-hoc Wilcoxon con corrección Holm:** Qwen3-8B vs Phi-4-mini ($p = 0.0357$), GLM-4-9B vs Phi-4-mini ($p = 0.4411$), Qwen3-8B vs GLM-4-9B ($p = 0.4411$).

