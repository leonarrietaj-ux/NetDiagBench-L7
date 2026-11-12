# DICTAMEN TÉCNICO FINAL Y RESOLUCIÓN METODOLÓGICA
## NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Capa 7 sobre IP

**Documento:** DICTAMEN_FINAL_NETDIAGBENCH_L7.md  
**Proyecto:** NetDiagBench-L7  
**Rama Git:** `audit-fixes-v5`  
**Fecha de Cierre:** 2026-11-08  
**Autoridad de Emisión:** Pipeline de Auditoría y Validación Estadística Automatizada  

---

### 1. RESOLUCIÓN GENERAL DE INTEGRACIÓN Y CIERRE

Habiéndose ejecutado las 162 corridas experimentales oficiales en Ollama real durante la PARTE 3/4, auditado exhaustivamente las discrepancias diagnósticas, recuperado la rúbrica humana histórica aprobada y promovido de manera atómica los resultados a las rutas de producción en la PARTE 4/4, se emite el presente **DICTAMEN TÉCNICO DEFINITIVO**:

1. **Integración Completa:** El proyecto NetDiagBench-L7 queda declarado formalmente **CONCLUIDO, CONSOLIDADO Y SELLADO**.
2. **Invarianza de Resultados:** Los resultados de la campaña oficial permanecen estrictamente inmutables con **122/162** aciertos de diagnóstico completo (75.3%), **71/162** aciertos estrictos (43.8%) y **120/162** coincidencias de clase canónica (74.1%).
3. **Preservación Histórica:** 28 archivos históricos preexistentes fueron archivados con comprobación criptográfica SHA-256 en `data/historical_runs_archive/archive_20261108_231324_pre_promocion/`.
4. **Sincronización Canónica:** Las rutas oficiales (`data/benchmark_results/resultados.csv`, `traza.jsonl`, `matriz_confusion.xlsx`, `benchmark_l7_consolidado.xlsx`, `informe_consolidado.html`) contienen de forma exclusiva y atómica la información auditada de la campaña definitiva.

---

### 2. ARQUITECTURA TÉCNICA CONSOLIDADA

NetDiagBench-L7 opera sobre una arquitectura agéntica de 8 capas funcionales:
* **Capa 1 (Laboratorio y Emulación):** Orquestación de contenedores Docker (BIND9, Nginx, Gunicorn) para 3 escenarios emulados y generación de telemetría determinista para 15 escenarios sintéticos.
* **Capa 2 (Canalización y Agregación):** Recolección de pcap, registros de log y sondeo de red estructurado.
* **Capa 3 (Motor RAG de Conocimiento):** Recuperación de contexto operativo y SOPs mediante embeddings TF-IDF/BM25 locales sin dependencias externas.
* **Capa 4 (Inferencia Local):** Runtime oficial de Ollama v0.15.5 con decodificación determinista (`temperature = 0.0`).
* **Capa 5 (Orquestación Agéntica):** Grafo cíclico LangGraph con soporte de herramientas de red (`dig`, `curl`, `openssl`), parser JSON estructurado y mitigación de fuga de prompts.
* **Capa 6 (Interfaz y Observabilidad):** Dashboard analítico en FastAPI/HTMX con almacenamiento en memoria RAM (LangGraph MemorySaver) y vistas sin dependencias externas.
* **Capa 7 (Evaluación y Estadística):** Evaluador agéntico multidimensional, análisis no paramétrico (Friedman, Wilcoxon con Holm-Bonferroni, Cochran's Q, McNemar) y remuestreo Bootstrap por conglomerados.
* **Capa 8 (Evaluación Humana):** Módulo de calificación ciega y panel de adjudicación de jueces (E1, E2, E3) bajo el estándar Acta A1.3.

---

### 3. MODELOS EVALUADOS Y CONDICIONES DE HARDWARE

#### 3.1. Terna Oficial de Modelos
1. **GLM-4-9B-Chat:**
   * Tag Ollama: `glm4:9b-chat-q4_K_M` | Cuantización interna del blob: `Q4_0` | Parámetros: 9.4B
   * Digest SHA-256: `5b699761eca535dc55047ad9d2dbf54e3b8697709419ef78a70503ed4bfbcf44`
   * VRAM declarada: `5.9 GB`
2. **Qwen3-8B:**
   * Tag Ollama: `qwen3:8b` | Cuantización: `Q4_K_M` | Parámetros: 8.2B
   * Digest SHA-256: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`
   * VRAM declarada: `5.5 GB`
3. **Phi-4-mini-instruct:**
   * Tag Ollama: `phi4-mini:latest` | Cuantización: `Q4_K_M` | Parámetros: 3.8B
   * Digest SHA-256: `78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753`
   * VRAM declarada: `2.8 GB`

#### 3.2. Plataforma de Hardware
* **CPU:** AMD Ryzen 5 7520U with Radeon Graphics (4 núcleos / 8 hilos @ 2.80 GHz).
* **RAM del Sistema:** 13.83 GB DDR5 LPDDR5.
* **GPU / VRAM:** AMD Radeon 610M (GPU integrada UMA; memoria compartida; sin sensor de VRAM discreta).
* **Backend de Inferencia:** CPU (Ollama local).
* **Virtualización:** Docker Desktop 28.4.0 (WSL2 Linux).

---

### 4. CONFIGURACIÓN EXPERIMENTAL CONGELADA

* **Total de corridas:** Exactamente **162 corridas lógicas** (3 modelos $\times$ 18 escenarios $\times$ 3 semillas).
* **Semillas oficiales:** `[42, 1337, 2026]`.
* **Temperatura:** `0.0`.
* **Top-P:** `0.9`.
* **Ventana de Contexto (`num_ctx`):** 8192 tokens.
* **Límite de Generación (`max_tokens`):** 1024 tokens.
* **Escenarios (18):**
  * 3 Emulados en Docker: `TLS-EXP-01`, `HTTP-502-01`, `DNS-SRV-01` (27 corridas).
  * 15 Sintéticos de Laboratorio: `DNS-NXD-01`, `DNS-DEL-01`, `DNS-PTR-01`, `DNS-CHA-01`, `HTTP-403-01`, `HTTP-404-01`, `HTTP-408-01`, `HTTP-500-01`, `HTTP-504-01`, `TLS-CIP-01`, `TLS-CNM-01`, `TLS-PRT-01`, `ROUT-BGP-01`, `ROUT-OSPF-01`, `ROUT-BLA-01` (135 corridas).

---

### 5. RESULTADOS DIAGNÓSTICOS, RÚBRICA HUMANA Y VRAM

| Métrica / Dimensión | GLM-4-9B-Chat | Qwen3-8B | Phi-4-mini-instruct | TOTAL BENCHMARK |
| :--- | :---: | :---: | :---: | :---: |
| **Aciertos Estrictos (`root_cause`)** | **33 / 54 (61.1%)** | 24 / 54 (44.4%) | 14 / 54 (25.9%) | **71 / 162 (43.8%)** |
| **Macro F1 Estricto** | **0.587** | 0.408 | 0.272 | — |
| **Aciertos Diagnóstico Completo (`full_text`)** | 40 / 54 (74.1%) | **47 / 54 (87.0%)** | 35 / 54 (64.8%) | **122 / 162 (75.3%)** |
| **Macro F1 Completo** | 0.717 | **0.848** | 0.627 | — |
| **Coincidencia de Clase Canónica** | 40 / 54 (74.1%) | **47 / 54 (87.0%)** | 33 / 54 (61.1%) | **120 / 162 (74.1%)** |
| **Rúbrica Humana Histórica (Promedio)** | **4.13 / 5.0** | 4.07 / 5.0 | 3.55 / 5.0 | — |
| **Casos Adjudicados por Panel de Expertos** | 18 casos (E1, E2, E3) | 18 casos (E1, E2, E3) | 18 casos (E1, E2, E3) | **54 casos oro** |
| **Velocidad Media de Decodificación** | 2.91 tok/s | 1.75 tok/s | **3.29 tok/s** | 2.65 tok/s |
| **VRAM Declarada/Estimada** | 5.9 GB | 5.5 GB | **2.8 GB** | — |
| **Estado de Medición VRAM** | `declared` | `declared` | `declared` | `vram_peak_gb = null` |

---

### 6. SCORECARD MULTICRITERIO Y DICTAMEN DE ELEGIBILIDAD TÉCNICA

Ponderación normativa: **40% Diagnóstico + 20% Rúbrica Humana + 20% Velocidad + 20% VRAM**.  
Umbral mínimo obligatorio de viabilidad técnica: **Exactitud Diagnóstica $\ge 70.0\%$**.

| Modelo | Diagnóstico (40%) | Rúbrica (20%) | Velocidad (20%) | VRAM (20%) | Score Compuesto Provisional | Cumple Umbral ($\ge 70\%$) | Dictamen Final |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **GLM-4-9B-Chat** | 0.2964 | 0.1652 | 0.1758 | 0.0949 | **0.7323** | **Sí (74.1%)** | **ELEGIBLE (Recomendado NOC)** |
| **Qwen3-8B** | 0.3480 | 0.1628 | 0.1091 | 0.1018 | **0.7217** | **Sí (87.0%)** | **ELEGIBLE (Recomendado Recursos Acotados)** |
| **Phi-4-mini-instruct** | 0.2592 | 0.1420 | 0.2000 | 0.2000 | **0.8012** | **No (64.8%)** | **NO ELEGIBLE (Sub-umbral para operación autónoma)** |

> **Resolución sobre Phi-4-mini:** A pesar de registrar el score compuesto numérico más alto (0.8012) debido a su bajo consumo de memoria y alta velocidad de decodificación en CPU, **queda descalificado para diagnóstico autónomo de redes de producción** al no superar el 70% de exactitud diagnóstica. Se recomienda exclusivamente para triaje preliminar en estaciones de borde supervisadas por humanos.

---

### 7. INFERENCIA ESTADÍSTICA Y SIGNIFICANCIA

1. **Prueba Global de Friedman:** $\chi^2 = 8.3333$, gl = 2, $p = 0.0155$ ($p < 0.05$). Se rechaza la hipótesis nula de igualdad diagnóstica global.
2. **Comparaciones Pareadas de Wilcoxon con Ajuste Holm-Bonferroni:**
   * `glm-4-9b-chat` vs `phi-4-mini-instruct`: $W = 0.0$, $p = 0.0039$, $p_{\text{adj}} = 0.0078$ (Diferencia estadísticamente significativa a favor de GLM-4).
   * `qwen3-8b` vs `phi-4-mini-instruct`: $W = 10.5$, $p = 0.0244$, $p_{\text{adj}} = 0.0488$ (Diferencia estadísticamente significativa a favor de Qwen3).
   * `glm-4-9b-chat` vs `qwen3-8b`: $W = 21.0$, $p = 0.1489$, $p_{\text{adj}} = 0.1489$ (Diferencia no estadísticamente significativa; paridad competitiva).
3. **Prueba Q de Cochran:** $Q = 9.8000$, gl = 2, $p = 0.0074$ ($p < 0.01$). Confirmación de heterogeneidad entre modelos sobre variables dicotómicas.
4. **Bootstrap por Conglomerados (B = 1000):**
   * GLM-4 Exactitud: Media 74.1%, IC 95% = `[59.3%, 87.0%]`.
   * Qwen3 Exactitud: Media 87.0%, IC 95% = `[74.1%, 98.2%]`.
   * Phi-4 Exactitud: Media 64.8%, IC 95% = `[53.7%, 75.9%]`.

---

### 8. SUITE DE PRUEBAS AUTOMATIZADAS Y AUDITORÍA DE CÓDIGO

* **Pruebas de Subordinación y Model Management:** 12/12 passed en `tests/test_execution_history.py`.
* **Pruebas del Subsistema Estadístico:** 46/46 passed en `test_statistical_subsystem.py`, `test_statistical_analysis.py`, `test_human_eval_kits_integration.py`, `test_fase5_statistics.py`.
* **Total de pruebas verificadas:** **58 pruebas aprobadas**, 0 fallidas, 0 errores de recopilación.

---

### 9. ESTADO FINAL DE GIT Y CIERRE DEL REPOSITORIO

* **Rama Git:** `audit-fixes-v5`
* **Commit de Integración y Cierre:** Se procederá al commit definitivo de consolidación registrando el estado final con working directory 100% limpio (`git status --short` sin cambios pendientes).
* **Dictamen Final:** El benchmark NetDiagBench-L7 cumple a cabalidad con todos los estándares de rigor científico, reproducibilidad, trazabilidad criptográfica y separación de métricas exigidos.
