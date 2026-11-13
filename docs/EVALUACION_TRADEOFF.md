# NetDiagBench-L7: Evaluación Comparativa de Compromiso y Trade-off

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Layer 7 sobre IP  
**Fecha:** Noviembre de 2026 (v1.0.4)  

---

## 1. Introducción y Marco Operacional

El presente informe técnico consolida los hallazgos experimentales de la evaluación multidimensional de la terna de modelos de lenguaje ligeros (SLMs) seleccionada: **GLM-4-9B-Chat (9.0B)**, **Qwen3-8B (8.2B)** y **Phi-4-mini-instruct (3.8B)**, cuantizados a 4 bits (`Q4_K_M GGUF`), en el diagnóstico autónomo de fallas de Capa de Aplicación (L7) sobre redes IP (DNS, HTTP/Web, API Gateway y TLS).

Los ensayos se ejecutaron bajo condiciones de laboratorio controladas con aislamiento LAN y presupuesto estricto de hardware ($\le 8\text{ GB}$ VRAM).

---

## 2. Matriz de Evaluación Multidimensional Consolidada

La evaluación compara cuatro dimensiones de desempeño operativo sobre 18 escenarios de falla y 162 ensayos controlados:

### Tabla Resumen de Magnitudes Oficiales Congeladas (162 Corridas)

| Métrica Multidimensional | Phi-4-mini-instruct (3.8B) | Qwen3-8B (8.2B) | GLM-4-9B-Chat (9.0B) |
|---|:---:|:---:|:---:|
| **Diagnóstico Completo (`is_full_diagnosis_correct`)** | 64.8% (35/54) | **87.0%** (47/54) | 74.1% (40/54) |
| **Causa Raíz Estricta (`is_root_cause_correct`)** | 25.9% (14/54) | 44.4% (24/54) | **61.1%** (33/54) |
| **Coincidencia de Clase Canónica (`fault_class_match`)** | 61.1% (33/54) | **87.0%** (47/54) | 74.1% (40/54) |
| **Tasa de Respaldo en Evidencia Read-Only** | 0.0% (0/54) | 27.8% (15/54) | **42.6%** (23/54) |
| **Rúbrica Humana de Evaluación (0 - 5.0)** | 3.55 / 5.0 | 4.07 / 5.0 | **4.13 / 5.0** |
| **Velocidad de Inferencia (tok/s)** | **3.29 tok/s** | 1.75 tok/s | 2.91 tok/s |
| **Memoria VRAM Declarada/Estimada (GB)** | **2.8 GB** | 5.5 GB | 5.9 GB |
| **Puntaje Compuesto Provisional (Scorecard 40/20/20/20)** | 0.8012 | 0.7217 | **0.7323** |
| **Umbral Mínimo Viable ($\ge 70.0\%$)** | No (64.8% < 70.0%) | **Sí (87.0%)** | **Sí (74.1%)** |
| **Dictamen de Elegibilidad Técnica** | **NO ELEGIBLE** | **ELEGIBLE** | **ELEGIBLE** |

---

## 3. Análisis de Compensaciones (*Trade-Offs*)

El análisis de compensaciones examina la tensión intrínseca entre **latencia operativa**, **consumo de memoria** y **profundidad analítica**:

### 3.1. GLM-4-9B-Chat (9.0B): Mejor Compromiso Global y Mayor Tasa de Evidencia
- **Ventajas:** Lidera el scorecard multicriterio de elegibilidad con un puntaje compuesto de **0.7323** (Elegible). Registra la mayor tasa de sustentación con herramientas de red Read-Only (**42.6%**, 23/54), el mayor aislamiento de causa raíz estricta (**61.1%**) y la mayor rúbrica de evaluación humana (**4.13 / 5.0**).
- **Compromiso / Limitación:** Mayor huella de memoria (5.9 GB VRAM estimada).

### 3.2. Qwen3-8B (8.2B): Máxima Exactitud Diagnóstica con Razonamiento CoT
- **Ventajas:** Lidera la exactitud diagnóstica completa con un **87.0%** (47/54 aciertos) y coincidencia canónica del 87.0%, integrando un bloque reflexivo nativo (`<thought>`) que explicita el razonamiento analítico.
- **Compromiso:** Velocidad de generación acotada en CPU/UMA (1.75 tok/s), con puntaje compuesto de **0.7217** (Elegible).

### 3.3. Phi-4-mini-instruct (3.8B): Máxima Velocidad y Despliegue en Borde
- **Ventajas:** Mayor velocidad de inferencia en CPU/UMA (**3.29 tok/s**) y menor huella de memoria (2.8 GB VRAM estimada).
- **Compromiso / Limitación:** Exactitud diagnóstica del **64.8%** (35/54 aciertos), situándose por debajo del umbral mínimo del 70.0% requerido para diagnóstico autónomo, resultando **NO ELEGIBLE** para operaciones no supervisadas.

---

## 4. Fundamentación de la Configuración de Mejor Compromiso (*Best Trade-Off*)

> ### Veredicto de Selección:
> Conforme al criterio formal de filtrar primero por exactitud viable ($\ge 70.0\%$) y ordenar por score multicriterio de compromiso, se ratifica a **GLM-4-9B-Chat** como la **configuración de mejor compromiso global (*best trade-off*)** para el diagnóstico de fallas L7 en estaciones de ingeniería y Centros de Operaciones de Red (NOC).
> Asimismo, **Qwen3-8B** se establece como la **segunda configuración de compromiso** recomendada para entornos que prioricen la máxima exactitud diagnóstica (87.0%).
