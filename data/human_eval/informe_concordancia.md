# Protocolo e Informe de Concordancia Inter-Evaluador (NetDiagBench-L7)

**Proyecto:** NetDiagBench-L7 — Universidad de Pamplona  
**Fecha de Validación:** Noviembre de 2026  
**Rúbrica:** Versión 3.0.0 (Actividad A1.3 del cronograma de investigación)  
**Muestra Evaluada:** 54 unidades estratificadas (3 modelos × 18 escenarios de red)  

---

## 1. Diseño del Análisis Estadístico
Conforme al Plan de Análisis de Concordancia (`docs/evaluacion_humana/07_Plan_analisis_concordancia.md`):
- **Criterios Ordinales (C1 a C6):** Porcentaje de acuerdo exacto ($P_o$) y Kappa de Cohen con ponderación cuadrática ($\kappa_w$).
- **Criterio Dicotómico (S):** Porcentaje de acuerdo exacto y Kappa de Cohen simple no ponderado.
- **Intervalos de Confianza al 95%:** Estimados mediante Bootstrap pareado por unidad de caso (1,000 réplicas con semilla registrada `20261105`), manteniendo los pares (E1, E2) unidos para no romper la estructura de dependencia.
- **Consistencia Inter-Jueces:** Alfa de Krippendorff ordinal sobre la escala de medición de la rúbrica [0, 1, 2].
- **Confiabilidad Compuesta:** Coeficiente de Correlación Intraclase ICC(2,1) (modelo de dos vías, efectos aleatorios, acuerdo absoluto) sobre la rúbrica continua (0 a 5).

---

## 2. Resultados Consolidados de Concordancia (E1 vs E2, $n=54$)

| Criterio / Métrica | $n$ Pares | Acuerdo Exacto ($P_o$) | Kappa Cohen ($\kappa$) | Ponderación | IC 95% Bootstrap | Dictamen Metodológico |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **C1: Causa Raíz** | 54 | 0.7593 (41/54) | **0.7327** | Cuadrática | [0.5281, 0.8611] | **Acuerdo Sustancial** |
| **C2: Coherencia Técnica** | 54 | 0.7778 (42/54) | **0.8073** | Cuadrática | [0.6932, 0.8988] | **Altamente Confiable** |
| **C3: Fundamentación Normativa** | 54 | 0.7593 (41/54) | **0.8002** | Cuadrática | [0.6538, 0.8928] | **Altamente Confiable** |
| **C4: Componente Afectado** | 54 | 0.7407 (40/54) | **0.7620** | Cuadrática | [0.6176, 0.8674] | **Confiable** |
| **C5: Procedimiento Mitigación** | 54 | 0.8148 (44/54) | **0.7945** | Cuadrática | [0.6037, 0.9058] | **Confiable** |
| **C6: Exactitud Factual CoT** | 54 | 0.8333 (45/54) | **0.8905** | Cuadrática | [0.7924, 0.9515] | **Altamente Confiable** |
| **S: Respaldo Evidencia Empírica** | 54 | 0.8148 (44/54) | **0.5872** | No ponderada | [0.3721, 0.7908] | **Acuerdo Moderado** |

- **ICC(2,1) Rúbrica Continua (0–5):** **0.7049** (IC 95%: [0.5539, 0.8155]) $\rightarrow$ Confiabilidad inter-evaluador moderada/aceptable.
- **Alfa de Krippendorff Ordinal:**
  - $C_1$: 0.6651 | $C_2$: 0.8165 | $C_3$: 0.7409 | $C_4$: 0.7573 | $C_5$: 0.7103 | $C_6$: 0.8604.

---

## 3. Adjudicación y Arbitraje por Tercer Experto (E3)
- En **32 casos** (59.26%), el acuerdo entre E1 y E2 fue espontáneo y unánime en $C_1$ y $S$.
- En **22 casos** (40.74%), se presentó discrepancia ($|C1_A - C1_B| \ge 1$ o $S_A \ne S_B$). Conforme al protocolo, el Árbitro Dirimente E3 intervino exclusivamente sobre estos casos, emitiendo veredicto vinculante archivado en `evaluaciones_adjudicadas.csv`.

---

## 4. Validación Diagnóstica del Evaluador Automático frente al Consenso Humano

Cruza la métrica automática `is_correct` (1/0) y `rubric_score` del benchmark frente al veredicto humano colegiado:

- **Matriz de Confusión ($n=41$ sin arbitraje):**
  - Verdaderos Positivos (TP): **31**
  - Falsos Positivos (FP): **1**
  - Falsos Negativos (FN): **0**
  - Verdaderos Negativos (TN): **9**
- **Exactitud Diagnóstica:** 97.56% (40/41)
- **Kappa de Cohen Diagnóstico:** **$\kappa = 0.9316$ (0.932)** $\rightarrow$ Acuerdo casi perfecto.
- **Correlación de Spearman Rúbrica ($n=54$):** $\rho = -0.2085$ ($p = 0.1302$).
- **Análisis de Bland-Altman (Auto $-$ Humano):**
  - Diferencia Media (Sesgo): **$-0.3462$ puntos**
  - Desviación Estándar de Diferencias: $1.3325$
  - Límites de Acuerdo al 95%: **$[-2.958, +2.266]$ puntos**

---

## 5. Trazabilidad Documental
- Evaluaciones independientes E1 y E2: `evaluaciones_originales.csv` (108 registros).
- Resoluciones vinculantes E3: `evaluaciones_adjudicadas.csv` (54 registros consolidados).
- Matriz ciega y estado de asignación: `matriz_asignacion.xlsx` (100% evaluado).
- Libro analítico de soporte: `data/human_eval/SESION_KIT_CASO2/Analisis_Concordancia_SESION_KIT_CASO2.xlsx`.
