# MATRIZ CANÓNICA DE CIFRAS OFICIALES PARA LA ELABORACIÓN DE LA TESIS
## NetDiagBench-L7: Benchmark Agéntico de Diagnóstico Layer 7 sobre IP

**Documento:** `docs/MATRIZ_CIFRAS_OFICIALES_TESIS.md`  
**Proyecto:** NetDiagBench-L7  
**Rama Git:** `audit-fixes-v5`  
**Fecha:** 2026-11-08  
**Propósito:** Referencia única, autorizada e inmutable de cifras experimentales y estadísticas para el manuscrito de tesis de grado.  

---

### 1. PARÁMETROS Y DISEÑO EXPERIMENTAL

| Parámetro | Valor Canónico | Fuente de Procedencia |
|---|---|---|
| **Población de Corridas Lógicas** | 162 corridas | `data/benchmark_results/resultados.csv` |
| **Modelos Evaluados (Terna)** | GLM-4-9B-Chat, Qwen3-8B, Phi-4-mini-instruct | `configs/models.yaml` |
| **Escenarios Totales** | 18 escenarios de Capa 7 | `configs/scenarios.yaml` |
| **Escenarios Emulados en Docker** | 3 (`TLS-EXP-01`, `HTTP-502-01`, `DNS-SRV-01`) | `src/layer1_lab/` |
| **Escenarios Sintéticos de Laboratorio** | 15 (DNS, HTTP, TLS, Enrutamiento) | `scenarios/` |
| **Semillas Experimentales Autorizadas** | `[42, 1337, 2026]` | `src/core/contracts.py` |
| **Temperatura de Inferencia** | `0.0` (determinista) | `configs/models.yaml` |
| **Ventana de Contexto (`num_ctx`)** | 8192 tokens | `configs/models.yaml` |
| **Límite de Generación (`max_tokens`)** | 1024 tokens | `configs/models.yaml` |
| **Motor de Inferencia** | `live_ollama` (100% de las 162 corridas) | `data/benchmark_results/traza.jsonl` |
| **Corridas por Modelo** | 54 ejecuciones | `data/benchmark_results/resultados.csv` |
| **Corridas por Semilla** | 54 ejecuciones | `data/benchmark_results/resultados.csv` |
| **Corridas por Escenario** | 9 ejecuciones (3 modelos $\times$ 3 semillas) | `data/benchmark_results/resultados.csv` |

---

### 2. RESULTADOS DIAGNÓSTICOS CONGELADOS

| Modelo | Aciertos Diagnóstico Completo (`full_text`) | Exactitud Completa (%) | Aciertos Estrictos (`root_cause`) | Exactitud Estricta (%) | Coincidencias de Clase Canónica | Exactitud Canónica (%) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | **40 / 54** | **74.1%** | **33 / 54** | **61.1%** | **40 / 54** | **74.1%** |
| **Qwen3-8B** | **47 / 54** | **87.0%** | **24 / 54** | **44.4%** | **47 / 54** | **87.0%** |
| **Phi-4-mini-instruct** | **35 / 54** | **64.8%** | **14 / 54** | **25.9%** | **33 / 54** | **61.1%** |
| **TOTAL BENCHMARK** | **122 / 162** | **75.3%** | **71 / 162** | **43.8%** | **120 / 162** | **74.1%** |

*Fuente:* `data/benchmark_results/resultados.csv` y `data/campaign_162/recalificacion_auditada.csv`.

#### Desglose de Clasificación de Auditoría (162 Corridas)
* **Aciertos conservados directos:** **71** (43.8%)
* **Aciertos corregidos demostrables:** **51** (31.5%)
* **Errores confirmados:** **40** (24.7%)
* **Total:** **162** (100.0%)

---

### 3. MÉTRICAS DE CLASIFICACIÓN MULTICLASE (CATÁLOGO CANÓNICO $K=18$)

Evaluación formal sobre el espacio de las 18 clases canónicas sin dilución de denominador por `UNKNOWN`:

| Modelo | Macro Precision | Macro Recall | Macro F1 | IC 95% Bootstrap (Macro F1) | Predicciones `UNKNOWN` (Penalizadas) |
|---|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | **0.843** | **0.741** | **0.757** | `[0.564, 0.860]` | 7 |
| **Qwen3-8B** | **0.861** | **0.870** | **0.848** | `[0.638, 0.963]` | 0 |
| **Phi-4-mini-instruct** | **0.797** | **0.611** | **0.661** | `[0.497, 0.720]` | 14 |

*Fuente:* `src/layer7_evaluator/statistical_analysis.py` (`compute_classification_metrics`, $K=18$).  
*Nota técnica de sensibilidad:* Si se incluye accidentalmente `UNKNOWN` en el conjunto de etiquetas evaluadas ($K=19$, diluyendo el promedio), los valores resultantes son: GLM: 0.717 (Prec: 0.798, Rec: 0.702); Qwen: 0.848 (Prec: 0.861, Rec: 0.870); Phi: 0.627 (Prec: 0.755, Rec: 0.579).

---

### 4. MÉTRICAS DE CLASIFICACIÓN ESTRICTA (`root_cause` AISLADO, $K=18$)

| Modelo | Macro Precision Estricto | Macro Recall Estricto | Macro F1 Estricto | Predicciones `UNKNOWN` Estrictas |
|---|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | 0.694 | 0.611 | **0.620** | 13 |
| **Qwen3-8B** | 0.472 | 0.426 | **0.431** | 22 |
| **Phi-4-mini-instruct** | 0.370 | 0.259 | **0.287** | 38 |

*Fuente:* Cómputo sobre `fault_class_predicted_strict` con $K=18$.

---

### 5. RÚBRICA HUMANA HISTÓRICA Y CASOS ADJUDICADOS

| Modelo | Promedio Rúbrica (/5.0) | Mínimo (/5.0) | Máximo (/5.0) | Corridas con Rúbrica | Casos Adjudicados (Oro) |
|---|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | **4.13** (4.1296) | 2.0 | 5.0 | 54 / 54 | 18 casos (E1, E2, E3) |
| **Qwen3-8B** | **4.07** (4.0741) | 2.5 | 5.0 | 54 / 54 | 18 casos (E1, E2, E3) |
| **Phi-4-mini-instruct** | **3.55** (3.5463) | 1.5 | 5.0 | 54 / 54 | 18 casos (E1, E2, E3) |

*Fuente:* `data/benchmark_results/resultados.csv` y `data/human_eval/evaluaciones_adjudicadas.csv` (Acta A1.3).

---

### 6. RÚBRICA DE EFICIENCIA DE MEMORIA VRAM DECLARADA

Fórmula normativa: $M = \min(VRAM) / VRAM_m = 2.8 / VRAM_m$; $S_{VRAM} = 0.20 \times M$.

| Modelo | VRAM Declarada/Estimada | Factor de Escala ($M$) | Puntaje Ponderado VRAM ($S_{VRAM}$) | Estado Formal de Telemetría |
|---|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | **5.9 GB** | 0.4746 | **0.0949** | `vram_peak_gb = null`, `valid = false`, `declared` |
| **Qwen3-8B** | **5.5 GB** | 0.5091 | **0.1018** | `vram_peak_gb = null`, `valid = false`, `declared` |
| **Phi-4-mini-instruct** | **2.8 GB** | 1.0000 | **0.2000** | `vram_peak_gb = null`, `valid = false`, `declared` |

*Fuente:* `configs/models.yaml` y `src/layer7_evaluator/composite_score.py`.

---

### 7. SCORECARD MULTICRITERIO Y DICTAMEN DE ELEGIBILIDAD

Fórmula: $S = 0.40 \cdot A + 0.20 \cdot R + 0.20 \cdot V + 0.20 \cdot M$.  
Umbral mínimo de viabilidad: $A \ge 70.0\%$.

| Modelo | Diagnóstico (40%) | Rúbrica (20%) | Velocidad (20%) | VRAM (20%) | Score Compuesto Provisional | Umbral Aprobado ($\ge 70\%$) | Elegibilidad Técnica Final |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | 0.2964 | 0.1652 | 0.1758 | 0.0949 | **0.7323** | **Sí (74.1%)** | **ELEGIBLE (NOC / Tier-1)** |
| **Qwen3-8B** | 0.3480 | 0.1628 | 0.1091 | 0.1018 | **0.7217** | **Sí (87.0%)** | **ELEGIBLE (Recursos Acotados)** |
| **Phi-4-mini-instruct** | 0.2592 | 0.1420 | 0.2000 | 0.2000 | **0.8012** | **No (64.8%)** | **NO ELEGIBLE (Sub-umbral)** |

*Fuente:* `data/benchmark_results/informe_modelos_seleccionados.json` y `composite_score.py`.

---

### 8. INFERENCIA ESTADÍSTICA Y CONTRASTES NO PARAMÉTRICOS

Unidad experimental independiente: Escenario ($N=18$ bloques). Repeticiones agregadas por media de bloque.

#### 8.1. Prueba Global de Friedman
* **Estadístico $\chi^2$:** **6.8205**
* **Grados de libertad:** **2**
* **Valor p:** **0.033** ($p = 0.03303 < 0.05$)
* **Conclusión:** Se rechaza la hipótesis nula; existen diferencias sistemáticas globales entre modelos.

#### 8.2. Contrastes Pareados de Wilcoxon con Ajuste Holm-Bonferroni (Familia $m=3$)
* **GLM-4 vs Phi-4:** $W = 48.0$, $p_{\text{raw}} = 0.3701$, $p_{\text{adj}} = \mathbf{0.370}$ (No significativo).
* **Qwen3 vs Phi-4:** $W = 10.5$, $p_{\text{raw}} = 0.0138$, $p_{\text{adj}} = \mathbf{0.041}$ (Significativo a favor de Qwen3).
* **GLM-4 vs Qwen3:** $W = 12.0$, $p_{\text{raw}} = 0.0264$, $p_{\text{adj}} = \mathbf{0.053}$ (Marginalmente no significativo a $\alpha = 0.05$).

#### 8.3. Análisis de Sensibilidad: Prueba de los Signos (Sign Test)
* **GLM-4 vs Phi-4:** $+:6, -:4, 0:8 \implies p = \mathbf{0.7539}$ (Concordante con Wilcoxon).
* **Qwen3 vs Phi-4:** $+:8, -:1, 0:9 \implies p = \mathbf{0.0391}$ (Concordante con Wilcoxon: superioridad robusta de Qwen3).
* **GLM-4 vs Qwen3:** $+:1, -:7, 0:10 \implies p = \mathbf{0.0703}$ (Concordante con Wilcoxon: sin significancia a $\alpha = 0.05$).

#### 8.4. Intervalos de Confianza al 95% Bootstrap (B = 1000 réplicas por conglomerados, semilla 42)
* **GLM-4-9B-Chat:** Exactitud = `[59.3%, 87.0%]`, F1 Macro = `[0.564, 0.860]`.
* **Qwen3-8B:** Exactitud = `[74.1%, 98.2%]`, F1 Macro = `[0.638, 0.963]`.
* **Phi-4-mini-instruct:** Exactitud = `[53.7%, 75.9%]`, F1 Macro = `[0.497, 0.720]`.

---

### 9. IDENTIDAD DE MODELOS Y CUANTIZACIÓN (OLLAMA LOCAL)

| Modelo | Tag Ollama Oficial | Arquitectura | Cuantización Efectiva | Digest SHA-256 Íntegro |
|---|---|---|---|---|
| **GLM-4-9B-Chat** | `glm4:9b-chat-q4_K_M` | `chatglm` (9.4B) | `Q4_0` *(Blob GGUF)* | `5b699761eca535dc55047ad9d2dbf54e3b8697709419ef78a70503ed4bfbcf44` |
| **Qwen3-8B** | `qwen3:8b` | `qwen3` (8.2B) | `Q4_K_M` | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| **Phi-4-mini-instruct**| `phi4-mini:latest` | `phi3` (3.8B) | `Q4_K_M` | `78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753` |

*Fuente:* `data/campaign_162/manifest.json` y salida verificada de `ollama show --modelfile`.
