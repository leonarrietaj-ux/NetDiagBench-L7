# NetDiagBench-L7: Análisis Estadístico Inferencial

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Layer 7 sobre IP  
**Dataset Oficial:** `data/benchmark_results/resultados.csv` (162 corridas oficiales congeladas)  
**Diseño Experimental:** 3 modelos × 18 escenarios (3 emulados Docker + 15 sintéticos) × 3 semillas deterministas (`[42, 1337, 2026]`)  
**Unidad de Muestreo:** 18 conglomerados de escenarios  
**Versión:** 1.0.4  

---

## 1. Congelación Oficial de Resultados Diagnósticos

Conforme al dictamen de cierre, los aciertos diagnósticos de la campaña permanecen rigurosamente congelados:

| Modelo | Aciertos Estrictos (`root_cause`) | Exactitud Estricta (%) | Aciertos Diagnóstico Completo (`full_text`) | Exactitud Completa (%) | Coincidencia de Clase Canónica | Evidencia Empírica Read-Only | Aciertos Históricos (Ref.) | Ecos de Placeholder Copiados |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | 33 / 54 | 61.1% | **40 / 54** | **74.1%** | 40 / 54 (74.1%) | 23 / 54 (42.6%) | 48 / 54 | 0 |
| **Qwen3-8B** | 24 / 54 | 44.4% | **47 / 54** | **87.0%** | 47 / 54 (87.0%) | 15 / 54 (27.8%) | 46 / 54 | 9 |
| **Phi-4-mini-instruct** | 14 / 54 | 25.9% | **35 / 54** | **64.8%** | 33 / 54 (61.1%) | 0 / 54 (0.0%) | 32 / 54 | 0 |
| **TOTAL CAMPAÑA** | **71 / 162** | **43.8%** | **122 / 162** | **75.3%** | **120 / 162 (74.1%)** | **38 / 162 (23.5%)** | **126 / 162** | **9** |

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

## 5. Concordancia de Evaluación Humana y Validación Inter-Jueces

La evaluación cualitativa y de razonamiento diagnóstico fue validada mediante un panel de tres evaluadores expertos independientes (E1, E2 y E3) sobre una muestra estratificada de **54 unidades de diagnóstico** (3 modelos × 18 escenarios RFC Layer 7), siguiendo la Rúbrica Versión 3.0.0 (`data/human_eval/version_rubrica.json`) y el protocolo formal (`docs/evaluacion_humana/01_Protocolo_evaluacion_humana.docx`).

### A. Adjudicación y Arbitraje de Casos
- **Acuerdo Espontáneo:** En **32 casos (59.26%)**, los evaluadores E1 y E2 alcanzaron consenso unánime e idéntico de manera independiente en la calificación de causa raíz ($C_1$) y soporte empírico ($S$).
- **Arbitraje Vinculante (E3):** En **22 casos (40.74%)**, donde se identificó discrepancia ($|C1_A - C1_B| \ge 1$ o $S_A \ne S_B$), el árbitro dirimente E3 intervino para emitir una resolución técnica final vinculante, documentada en `data/human_eval/evaluaciones_adjudicadas.csv`.

### B. Tabla Consolidada de Concordancia Inter-Evaluador (E1 vs E2, $n=54$)

Las métricas provienen de la ejecución del análisis formal (`data/human_eval/concordancia_resultados.csv`) con 1,000 réplicas Bootstrap pareadas (semilla `20261105`):

| Criterio Evaluado | $n$ Pares | Acuerdo Exacto ($P_o$) | Kappa de Cohen ($\kappa$) | Tipo de Ponderación | IC 95% Bootstrap | Nivel de Acuerdo |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **C1: Causa Raíz** | 54 | 75.93% (41/54) | **0.7327** | Cuadrática | [0.5281, 0.8611] | Acuerdo Sustancial |
| **C2: Coherencia Técnica** | 54 | 77.78% (42/54) | **0.8073** | Cuadrática | [0.6932, 0.8988] | Altamente Confiable |
| **C3: Fundamentación Normativa** | 54 | 75.93% (41/54) | **0.8002** | Cuadrática | [0.6538, 0.8928] | Altamente Confiable |
| **C4: Componente Afectado** | 54 | 74.07% (40/54) | **0.7620** | Cuadrática | [0.6176, 0.8674] | Confiable |
| **C5: Procedimiento de Mitigación** | 54 | 81.48% (44/54) | **0.7945** | Cuadrática | [0.6037, 0.9058] | Confiable |
| **C6: Exactitud Factual CoT** | 54 | 83.33% (45/54) | **0.8905** | Cuadrática | [0.7924, 0.9515] | Altamente Confiable |
| **S: Respaldo Evidencia Empírica** | 54 | 81.48% (44/54) | **0.5872** | No ponderada | [0.3721, 0.7908] | Acuerdo Moderado |

### C. Confiabilidad Compuesta y Diferenciación de Coeficientes

1. **Coeficiente de Correlación Intraclase ICC(2,1):**
   - **Valor oficial del benchmark:** $\text{ICC}(2,1) = \mathbf{0.7049}$ (IC 95%: [0.5539, 0.8155]), computado bajo un modelo bidireccional de efectos aleatorios con acuerdo absoluto sobre la rúbrica continua (escala 0 a 5).
   - **Nota sobre antecedentes preliminares:** Reportes iniciales y borradores preliminares mencionaban un ICC de 0.7860, el cual derivó de una cohorte exploratoria previa a la adjudicación definitiva. El valor oficial, exhaustivo y auditable de la liberación pública es **0.7049**.

2. **Diferenciación Metodológica de Estadísticos Kappa:**
   - **Kappa Inter-Evaluador Humano ($\kappa = 0.5872 \text{ a } 0.8905$):** Mide la concordancia pareada entre jueces humanos independientes sobre criterios cualitativos continuos y ordinales.
   - **Kappa de Validación Diagnóstica ($\kappa = 0.9316 \approx 0.932$):** Mide el acuerdo en la clasificación binaria del diagnóstico (`is_correct`: 1/0) entre el evaluador automatizado del harness y el consenso humano colegiado sobre los 41 casos con acuerdo pleno espontáneo:
     - Verdaderos Positivos (TP): 31
     - Falsos Positivos (FP): 1
     - Falsos Negativos (FN): 0
     - Verdaderos Negativos (TN): 9
     - Exactitud Diagnóstica: **97.56% (40/41)**

### D. Distinción Operativa entre C6 y S

El benchmark formaliza una distinción estricta entre la argumentación teórica y la comprobación empírica activa:
- **Criterio C6 (Exactitud Factual en Chain-of-Thought):** Evalúa la corrección técnica, congruencia deductiva y ausencia de alucinaciones en la cadena discursiva de razonamiento del LLM. Un modelo puede obtener una calificación alta en C6 razonando coherentemente sobre la teoría del protocolo sin haber emitido comandos de prueba.
- **Criterio S (Soporte en Evidencia Empírica Read-Only):** Evalúa la verificación empírica activa mediante la ejecución comprobada de comandos no destructivos (`ping`, `curl`, `dig`, `ip route`, etc.) provistos por el entorno emulado. Demuestra que el diagnóstico se apoya en observaciones reales del sistema y no exclusivamente en inferencias deductivas a priori.

---

## 6. Dictamen de Integridad de la Campaña

1. **Aciertos Conservados:** **71 corridas** (estrictamente válidas sin necesidad de corrección).
2. **Aciertos Corregidos Demostrables:** **51 corridas** (diagnóstico fundamentado conforme a verdad fundamental y conceptos RFC, rechazado inicialmente por restricción del extractor estricto o eco de plantilla).
3. **Errores Confirmados:** **40 corridas** (falla incorrecta, alucinación o diagnóstico disonante).
4. **Cero Datos Sintéticos:** Las 162 inferencias provienen de llamadas reales a Ollama con trazas y digests SHA-256 inalterados.
