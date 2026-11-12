# INTEGRIDAD EXPERIMENTAL Y TRAZABILIDAD CRIPTOGRÁFICA DEFINITIVA
## NetDiagBench-L7: Evaluación Agéntica de Diagnóstico Layer 7 sobre IP

**Fecha:** 2026-11-08  
**Rama:** `audit-fixes-v5`  
**Fase:** PARTE 4/4 — Consolidación y Cierre Canónico  

---

### 1. Auditoría de la Campaña Oficial (162 Corridas)

La campaña experimental de 162 corridas lógicas fue ejecutada de forma determinista y reproducible con inferencia local real:
* **Total de corridas lógicas:** Exactamente **162**.
* **Modelos evaluados:**
  1. `glm-4-9b-chat` (54 corridas)
  2. `qwen3-8b` (54 corridas)
  3. `phi-4-mini-instruct` (54 corridas)
* **Semillas experimentales autorizadas:** `[42, 1337, 2026]` (54 corridas por semilla, 18 por combinación modelo-semilla).
* **Escenarios evaluados (18):**
  * **3 Emulados en Docker (`execution_mode = emulado`):**
    * `TLS-EXP-01` (Expiración de Certificado TLS en Nginx)
    * `HTTP-502-01` (Bad Gateway por caída de backend upstream)
    * `DNS-SRV-01` (Fallo de Resolución de Servicios SRV en BIND9)
    * Subtotal: **27 ejecuciones** (3 modelos $\times$ 3 escenarios $\times$ 3 semillas).
  * **15 Sintéticos de Laboratorio (`execution_mode = sintetico_determinista`):**
    * DNS: `DNS-NXD-01`, `DNS-DEL-01`, `DNS-PTR-01`, `DNS-CHA-01`
    * HTTP: `HTTP-403-01`, `HTTP-404-01`, `HTTP-408-01`, `HTTP-500-01`, `HTTP-504-01`
    * TLS: `TLS-CIP-01`, `TLS-CNM-01`, `TLS-PRT-01`
    * Enrutamiento / L7: `ROUT-BGP-01`, `ROUT-OSPF-01`, `ROUT-BLA-01`
    * Subtotal: **135 ejecuciones** (3 modelos $\times$ 15 escenarios $\times$ 3 semillas).
  * Total consolidado: $27 + 135 = \mathbf{162}$ corridas.

> **Aclaración Metodológica Crucial:** Las 162 inferencias corresponden a llamadas reales en streaming a Ollama local (`engine_mode = live_ollama`). La denominación de escenarios sintéticos refiere a la inyección determinista de logs/pcap en el entorno de pruebas, no a respuestas inventadas o simuladas.

---

### 2. Trazabilidad Criptográfica de Inferencia y Hashes SHA-256

Cada una de las 162 corridas cuenta con su correspondiente objeto JSON en [data/benchmark_results/traza.jsonl](data/benchmark_results/traza.jsonl), alineado biyectivamente con [data/benchmark_results/resultados.csv](data/benchmark_results/resultados.csv):
* **Prompt SHA-256:** Recalculado y validado mediante `calculate_prompt_sha256(prompt)`.
* **Response SHA-256:** Recalculado y validado mediante `calculate_prompt_sha256(response)`.
* **Config SHA-256:** Hash SHA-256 canónico de 64 caracteres hexadecimales que congela temperatura (`0.0`), top-p (`0.9`), ventana de contexto (`8192`) y max tokens (`1024`).
* **Digest de Modelos en Ollama:**
  * `glm-4-9b-chat`: `5b699761eca535dc55047ad9d2dbf54e3b8697709419ef78a70503ed4bfbcf44`
  * `qwen3-8b`: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
  * `phi-4-mini-instruct`: `78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753`

#### Resolución Documentada de Cuantización GLM-4:
* **Tag Ollama registrado:** `glm4:9b-chat-q4_K_M`
* **Tipo de blob GGUF efectivo:** `Q4_0`
* **Digest íntegro verificado:** `5b699761eca535dc55047ad9d2dbf54e3b8697709419ef78a70503ed4bfbcf44`
* Esta discrepancia formal entre la etiqueta externa del manifiesto de Ollama y el tipo de cuantización interna del archivo blob ha quedado resuelta y documentada explícitamente en el manifiesto oficial ([manifest.json](manifest.json)).

---

### 3. Protocolo de Promoción Atómica y Preservación Histórica

Conforme a la Sección 6 y el script de promoción controlada:
1. **Directorio de Archivo Histórico Creado:**  
   `data/historical_runs_archive/archive_20261108_231324_pre_promocion/`
2. **Archivos Históricos Respaldados:**
   * 28 archivos canónicos preexistentes (CSV, HTML, JSON, MD, PDF, XLSX) fueron respaldados de manera atómica con su correspondiente `MANIFEST_SHA256.txt`.
3. **Promoción de Rutas Canónicas:**
   * `data/benchmark_results/resultados.csv` (SHA-256: `410e901a3ae5f9116e4ee640eb24a9a089ec0a5ceee935c1ec8f7e716da2d354`)
   * `data/benchmark_results/traza.jsonl` (SHA-256: `ffc1dbd7a0082f5b5b03f0b2f540b6eec3b6a94f6f7bc22db0c0b3d8702b3780`)
   * `data/benchmark_results/ACTA_PROMOCION_20261108_231324.json`
   * `data/benchmark_results/benchmark_summary.json`
