# NetDiagBench-L7: Análisis Estadístico Inferencial

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Layer 7 sobre IP  
**Dataset Oficial:** `data/benchmark_results/resultados.csv` (162 corridas oficiales congeladas)  
**Diseño Experimental:** 3 modelos × 18 escenarios (3 emulados Docker + 15 sintéticos) × 3 semillas deterministas (`[42, 1337, 2026]`)  
**Unidad de Muestreo:** 18 conglomerados de escenarios  
**Versión:** 1.0.2  

---

## 1. Congelación Oficial de Resultados Diagnósticos

Conforme al dictamen de cierre, los aciertos diagnósticos de la campaña permanecen rigurosamente congelados:

| Modelo | Aciertos Estrictos (`root_cause`) | Exactitud Estricta (%) | Aciertos Diagnóstico Completo (`full_text`) | Exactitud Completa (%) | Coincidencia de Clase Canónica | Aciertos Históricos (Ref.) | Ecos de Placeholder Copiados |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | 33 / 54 | 61.1% | **40 / 54** | **74.1%** | 40 / 54 (74.1%) | 48 / 54 | 0 |
| **Qwen3-8B** | 24 / 54 | 44.4% | **47 / 54** | **87.0%** | 47 / 54 (87.0%) | 46 / 54 | 9 |
| **Phi-4-mini-instruct** | 14 / 54 | 25.9% | **35 / 54** | **64.8%** | 33 / 54 (61.1%) | 32 / 54 | 0 |
| **TOTAL CAMPAÑA** | **71 / 162** | **43.8%** | **122 / 162** | **75.3%** | **120 / 162 (74.1%)** | **126 / 162** | **9** |

---

## 2. Métricas de Clasificación Multiclase Independientes

Se garantiza la independencia estricta entre evaluaciones. Cada tabla se computa sobre sus propias predicciones y matriz de confusión.

### A. Evaluación Auditada (Diagnóstico Completo: `root_cause` + `fundamentacion_tecnica`)

| Modelo | Exactitud Global (%) | Macro Precision | Macro Recall | Macro F1 | IC 95% Bootstrap (Exactitud) | IC 95% Bootstrap (Macro F1) | Predicciones UNKNOWN |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | **74.1%** | 0.798 | 0.702 | **0.717** | [59.3%, 87.0%] | [0.564, 0.860] | 7 |
| **Qwen3-8B** | **87.0%** | 0.861 | 0.870 | **0.848** | [74.1%, 98.2%] | [0.638, 0.963] | 0 |
| **Phi-4-mini-instruct** | **64.8%** | 0.755 | 0.579 | **0.627** | [53.7%, 75.9%] | [0.497, 0.720] | 14 |

### B. Evaluación Estricta Original (Campo `root_cause` Aislado)

| Modelo | Exactitud Global (%) | Macro Precision | Macro Recall | Macro F1 | IC 95% Bootstrap (Exactitud) | IC 95% Bootstrap (Macro F1) | Predicciones UNKNOWN |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | 61.1% | 0.658 | 0.579 | 0.587 | [46.3%, 74.1%] | [0.429, 0.723] | 13 |
| **Qwen3-8B** | 44.4% | 0.447 | 0.404 | 0.408 | [25.9%, 63.0%] | [0.236, 0.574] | 22 |
| **Phi-4-mini-instruct** | 25.9% | 0.351 | 0.246 | 0.272 | [11.1%, 44.4%] | [0.136, 0.407] | 38 |

---

## 3. Pruebas de Hipótesis No Paramétricas (Bloques Pareados por Escenario, gl = 2)

### A. Prueba Global de Friedman
- **Diagnóstico Completo (Auditado):** $\chi^2 = 6.8205$, p = 0.033 (Significativo al nivel $\\alpha = 0.05$).
- **Evaluación Estricta:** $\chi^2 = 8.3333$, p = 0.016 (Significativo al nivel $\\alpha = 0.05$).

### B. Comparaciones Post-Hoc por Pares (Wilcoxon Pareado con Corrección Holm-Bonferroni)

#### Resultados sobre Diagnóstico Completo (Auditado):
| Par de Modelos | Estadístico W | p-value Original | p-value Ajustado (Holm) | Decisión ($\alpha = 0.05$) |
|---|:---:|:---:|:---:|:---:|
| `glm-4-9b-chat_vs_phi-4-mini-instruct` | 48.0 | p = 0.370 | p = 0.370 | **No significativo** |
| `qwen3-8b_vs_phi-4-mini-instruct` | 10.5 | p = 0.014 | p = 0.041 | **Diferencia Significativa** |
| `glm-4-9b-chat_vs_qwen3-8b` | 12.0 | p = 0.026 | p = 0.053 | **No significativo** |

#### Resultados sobre Evaluación Estricta Original:
| Par de Modelos | Estadístico W | p-value Original | p-value Ajustado (Holm) | Decisión ($\alpha = 0.05$) |
|---|:---:|:---:|:---:|:---:|
| `glm-4-9b-chat_vs_phi-4-mini-instruct` | 0.0 | p = 0.001 | p = 0.004 | **Diferencia Significativa** |
| `qwen3-8b_vs_phi-4-mini-instruct` | 52.5 | p = 0.217 | p = 0.407 | **No significativo** |
| `glm-4-9b-chat_vs_qwen3-8b` | 46.5 | p = 0.204 | p = 0.407 | **No significativo** |

---

## 4. Scorecard Multicriterio Normativo y Rúbrica VRAM

Ponderación oficial 40/20/20/20:
- Exactitud Diagnóstica (40%): $A = \text{acc} / 100.0$
- Rúbrica Humana Recuperada (20%): $R = \text{rub} / 5.0$ (GLM: 4.13, Qwen: 4.07, Phi: 3.55)
- Velocidad de Inferencia (20%): $V = \text{tok\_s} / \max(\text{tok\_s})$
- Eficiencia de VRAM (20%): $M = \min(VRAM) / VRAM_{modelo}$

### Valores Oficiales de VRAM:
- GLM-4-9B-Chat (5.9 GB): $M = 2.8 / 5.9 = 0.4746 \rightarrow \mathbf{0.0949}$
- Qwen3-8B (5.5 GB): $M = 2.8 / 5.5 = 0.5091 \rightarrow \mathbf{0.1018}$
- Phi-4-mini-instruct (2.8 GB): $M = 2.8 / 2.8 = 1.0000 \rightarrow \mathbf{0.2000}$

### Scorecard Final con Diagnóstico Auditado y Rúbrica Humana:

| Modelo | Diagnóstico (40%) | Rúbrica Humana (20%) | Velocidad (20%) | VRAM Estimada (20%) | Elegibilidad (>=70%) | Puntaje Compuesto Provisional |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **glm-4-9b-chat** | 0.2964 | 0.1652 | 0.1758 | 0.0949 | **ELEGIBLE** | **0.7323** |
| **qwen3-8b** | 0.3480 | 0.1628 | 0.1091 | 0.1018 | **ELEGIBLE** | **0.7217** |
| **phi-4-mini-instruct** | 0.2592 | 0.1420 | 0.2000 | 0.2000 | **NO ELEGIBLE** | **0.8012** |

---

## 5. Dictamen de Integridad de la Campaña

1. **Aciertos Conservados:** **71 corridas** (estrictamente válidas sin necesidad de corrección).
2. **Aciertos Corregidos Demostrables:** **51 corridas** (diagnóstico fundamentado conforme a verdad fundamental y conceptos RFC, rechazado inicialmente por restricción del extractor estricto o eco de plantilla).
3. **Errores Confirmados:** **40 corridas** (falla incorrecta, alucinación o diagnóstico disonante).
4. **Cero Datos Sintéticos:** Las 162 inferencias provienen de llamadas reales a Ollama con trazas y digests SHA-256 inalterados.
