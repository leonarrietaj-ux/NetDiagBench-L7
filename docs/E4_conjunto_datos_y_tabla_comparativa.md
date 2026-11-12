# Entregable E4: Conjunto de Datos de Resultados y Tabla Comparativa Consolidada

**Proyecto de Grado:** "Implementación de un benchmark reproducible para el diagnóstico de fallas en servicios de capa de aplicación sobre IP con modelos de lenguaje ligeros de ejecución local"  
**Universidad de Pamplona — Facultad de Ingenierías y Arquitectura (E.E.S.T.)**  
**Autor:** Juan David León Arrieta | **Director:** Mg. Richard Eliseo Mendoza Gáfaro  
**Fecha:** Noviembre de 2026  

---

## 1. Descripción del Conjunto de Datos (Dataset de Evaluación)

El conjunto de datos crudo de evaluación multidimensional se almacena en [`data/benchmark_results/resultados.csv`](../data/benchmark_results/resultados.csv), comprendiendo un total de **162 corridas controladas y trazables** (3 modelos de lenguaje × 18 escenarios de falla de Capa 7 × 3 semillas deterministas).

### 1.1. Esquema de Registro Granular (42 Columnas Métricas y Parámetros MLOps)

> [!NOTE] Determinismo y Semillas en Modo Emulado
> En las 27 corridas ejecutadas en modo `emulado` (laboratorio en contenedores Docker Compose), la semilla determinista (`42`, `1337`, `2026`) y la temperatura fijada en 0 gobiernan exclusivamente el generador de números pseudoaleatorios del modelo en Ollama (`seed`), asegurando la reproducibilidad de la inferencia, mientras que los servicios en red (BIND9, Nginx, OpenSSL) ejecutan en contenedores reales aislados.

Cada fila del archivo `resultados.csv` corresponde a una prueba individual determinista, definida por el contrato Pydantic `ResultadoEvaluacionContract` e incluye los siguientes 42 campos:

1. `scenario_id`: Identificador del escenario L7 (`DNS-NXD-01`, `HTTP-502-01`, etc.).
2. `model_id`: Identificador del SLM evaluado (`qwen3-8b`, `glm-4-9b-chat`, `phi-4-mini-instruct`).
3. `seed`: Semilla determinista fijada para la corrida (`42`, `1337`, `2026`).
4. `repetition_index`: Índice de la repetición dentro de la semilla (`1`).
5. `category`: Categoría de servicio de red (`DNS`, `HTTP_WEB`, `API_GATEWAY`, `TLS`).
6. `fault_class`: Clase de falla inyectada conforme al catálogo L7.
7. `is_root_cause_correct`: Booleano que valida si la causa raíz técnica fue correctamente identificada según los grupos de conceptos normativos oficiales.
8. `is_component_correct`: Booleano que valida si el componente de red afectado fue correctamente aislado sin ambigüedad.
9. `partial_match_score`: Puntuación continua de acierto parcial ($0.0$ a $1.0$).
10. `evidence_backed`: Booleano que certifica si el veredicto fue contrastado con herramientas de solo lectura (`dig`, `curl`, `openssl`).
11. `ttft_ms`: Tiempo transcurrido hasta la emisión del primer token (fase de prellenado o *prefill*).
12. `tokens_per_sec`: Tasa de decodificación efectiva de salida (tokens/segundo).
13. `total_time_ms`: Latencia total de inferencia y respuesta (ms).
14. `tool_steps_count`: Cantidad de invocaciones a herramientas read-only (`dig`, `curl`, `openssl`).
15. `cpu_percent_avg`: Porcentaje medio de uso de procesador del sistema durante la ejecución.
16. `peak_ram_mb`: Pico de memoria RAM de sistema demandado por el proceso.
17. `peak_vram_gb`: Consumo pico de memoria de vídeo declarada/reportada por el modelo cuantizado.
18. `energy_kwh`: Consumo energético estimado según el modelo dinámico de potencia calibrado.
19. `co2_emissions_kg`: Emisiones indirectas de carbono calculadas para la matriz energética nacional.
20. `rubric_score`: Puntuación cuantitativa según la rúbrica de interpretabilidad ($0.0$ a $5.0$).
21. `host_hardware_fingerprint`: Huella inmutable de hardware del equipo de cómputo de la Universidad de Pamplona.
22. `created_at`: Marca temporal ISO 8601 con zona horaria UTC.
23. `modelo_version`: Versión o etiqueta del modelo local en Ollama.
24. `model_family`: Linaje arquitectónico del modelo (`qwen`, `glm`, `phi`, etc.).
25. `model_group`: Grupo de ingesta (`principal` para la terna base, `adicional` para modelos dinámicos).
26. `evaluator_version`: Resumen criptográfico SHA-256 (12 caracteres) de `configs/evaluator_concepts.yaml` (prefijo canónico publicado: `b26a394b7fb3`; prefijo preliminar histórico: `1f8c1a7e3a9d`).
27. `ollama_version`: Versión del runtime de servicio Ollama.
28. `semilla`: Semilla experimental de la corrida.
29. `timestamp`: Marca temporal de inicio de ejecución.
30. `execution_mode`: Modo de ejecución de la prueba (`sintetico_determinista` o `emulado`).
31. `model_diagnosis_text`: Transcripción completa de la respuesta emitida por el modelo.
32. `root_cause`: Causa raíz extraída exclusivamente de la respuesta del modelo.
33. `git_commit_hash`: Hash Git del estado del repositorio durante la ejecución.
34. `git_dirty`: Indicador de modificaciones en el árbol de trabajo Git.
35. `container_image_digest`: Hash inmutable de las imágenes Docker empleadas en modo emulado.
36. `docker_version`: Versión de Docker Compose en el host.
37. `reasoning_text`: Bloque de pensamiento CoT extraído de etiquetas `<think>...</think>`.
38. `parse_status`: Estado de validación del esquema JSON nativo emitido.
39. `context_truncated`: Booleano que certifica si la ventana de contexto excedió el límite del modelo.
40. `reasoning_tokens`: Conteo de tokens dedicados a la fase de deliberación CoT.
41. `ttft_final_ms`: Tiempo hasta el primer token de la respuesta final tras deliberación CoT ($\ge \text{ttft\_ms}$).
42. `rescore_commit`: Commit Git correspondiente a la recalificación normativa unificada (`4a4ef77a64ccd59dea68b439332736775c61c654`).

---

## 2. Tabla Comparativa Consolidada por Modelo (N = 162 Corridas Locales)

A continuación se presentan las magnitudes cuantitativas consolidadas obtenidas mediante ejecución 100% real sobre Ollama en hardware host (`AMD64 Family 23 Model 160`, 8 cores, 13.8 GB RAM), recalculadas deterministamente con el evaluador normativo SHA-256 `1f8c1a7e3a9d`:

| Dimensión de Medición | Métrica Específica | **Phi-4-mini-instruct** (3.8B) | **Qwen3-8B** (8.2B) | **GLM-4-9B-Chat** (9.0B) |
|---|---|---|---|---|
| **Eficacia Diagnóstica (OE4)** | Precisión de Causa Raíz (%) | 63.0% (34/54) | 85.2% (46/54) | **88.9%** (48/54) |
| | Acierto Parcial Promedio ($0-1$) | $0.555$ | **$0.806$** | $0.797$ |
| | Aislamiento de Componente (%) | 46.3% (25/54) | **74.1%** (40/54) | 61.1% (33/54) |
| | Tasa Respaldada por Evidencia (%) | 94.4% (51/54) | **96.3%** (52/54) | **96.3%** (52/54) |
| | Rúbrica de Explicabilidad ($0-5$) | $3.85 \pm 1.04$ | **$4.48 \pm 0.79$** | $4.41 \pm 0.67$ |
| **Rendimiento Temporal** | TTFT Fase Prefill Prom. (ms) | **$83,042.9$ ms** (~83.0 s) | $161,507.9$ ms (~161.5 s) | $182,836.0$ ms (~182.8 s) |
| | Velocidad Decodificación (tok/s) | **$4.51$ tok/s** | $3.49$ tok/s | $3.36$ tok/s |
| | Latencia Mediana ($p_{50}$) (ms) | **$172,380.2$ ms** (~2.87 min) | $353,103.5$ ms (~5.89 min) | $379,153.6$ ms (~6.32 min) |
| | Latencia Percentil 95 ($p_{95}$) (ms) | **$264,736.0$ ms** (~4.41 min) | $637,374.2$ ms (~10.62 min) | $609,063.1$ ms (~10.15 min) |
| **Huella Computacional** | Memoria VRAM Declarada Pico (GB) | **$2.8$ GB** | $5.5$ GB | $5.9$ GB |
| | Energía Total Acumulada (kWh) | **$0.330$ kWh** | $0.862$ kWh | $0.911$ kWh |
| | Emisiones CO₂e Estimadas (kg) | **$0.092$ kg** | $0.241$ kg | $0.255$ kg |
| | Eficiencia Energética (Tokens/Wh) | **$127,212.9$ tok/Wh** | $82,263.8$ tok/Wh | $79,189.3$ tok/Wh |
| **Score Compuesto de Compromiso**| Índice Normalizado Multicriterio | 0.745 (Rango 3 - Borde) | 0.850 (Rango 2 - CoT / Borde) | **0.860 (Óptimo Global / NOC)** |

*Nota Metodológica:* El score de compromiso filtra primero por umbral de exactitud viable ($\ge 70.0\%$) y evalúa las dimensiones de exactitud (40%), rúbrica (20%), velocidad de decodificación (20%) y eficiencia de memoria VRAM (20%). Bajo este criterio, **GLM-4-9B-Chat** alcanza la primera posición con 88.9% de precisión y score de **0.860**, mientras que **Qwen3-8B** se establece como la segunda configuración viable con 85.2% de precisión, mayor puntuación en rúbrica explicativa ($4.48/5.0$) y el mayor aislamiento de componentes ($74.1\%$).

---

## 3. Validación Normativa del Evaluador y Compatibilidad por Familias de Modelos (Tarea 4.2.1)

El marco de evaluación de causa raíz de NetDiagBench-L7 opera bajo un principio determinista de cero fuga de datos y cero calibración empírica sobre respuestas de modelos:

- **Origen de Criterios:** Criterios derivados estrictamente de fuentes normativas oficiales, versionados en `configs/evaluator_concepts.yaml` (v3.0.0, SHA-256 canónico: `b26a394b7fb3`, preliminar histórico: `1f8c1a7e3a9d`).
- **Fuentes Normativas Estándar:** RFC 1034 / RFC 1035 (DNS RCODE 2/3/5, TC-bit), RFC 2308, RFC 6891 (EDNS0), BIND 9 Administrator Reference Manual §6.2, RFC 9110 (HTTP Semantics), RFC 9112, RFC 6585 (429 Rate Limiting), RFC 8446 (TLS 1.3), RFC 5280 (X.509 PKI notAfter/Chains), RFC 6066 (SNI), y manual de Linux Traffic Control (`tc-netem`).
- **Regla Única Universal:**
  $$\text{is\_correct} = (\text{cumple} \ge 1\ \text{cause\_group}) \land (\neg \text{clase vecina no-negada en 1ra oración}) \land (\neg \text{solo síntoma})$$
  Evaluada mediante agrupaciones lógicas de raíces morfológicas y sinónimos técnicos en español e inglés.
- **Exclusión de Códigos Crudos como Síntomas:** Salidas crudas de herramientas (`servfail`, `rcode 2`, `alert 40`, códigos de estado HTTP solos) se clasifican como `symptom_only_terms`, impidiendo que la mera repetición del síntoma sea calificada como causa raíz.
- **Extracción Estricta del Modelo:** Causa raíz, componente, mitigación y fundamentación técnica se derivan **exclusivamente del texto emitido por el modelo**, sin sustitución por valores de verdad terreno (*ground truth*), garantizando transparencia absoluta.
- **Traducción Universal al Español:** Cualquier respuesta técnica en inglés es traducida automáticamente al español mediante el motor determinista `src/core/translator.py`, preservando términos clave (IPs, RFCs, comandos).
- **Compatibilidad Universal por Familias de Modelos:**
  El arnés clasifica deterministamente cada modelo agregado:
  - `ultraligero` ($\le 2\text{B}$ parámetros): optimizado para despliegues embebidos o edge computing.
  - `intermedio` ($3\text{B}-4\text{B}$ parámetros, ej. Phi-4-mini-instruct): balance de latencia y footprint en CPU.
  - `completo` ($7\text{B}-9\text{B}$ parámetros, ej. GLM-4-9B-Chat): razonamiento general profundo y seguimiento riguroso de esquemas.
  - `razonamiento` (CoT nativo condicionado a `reasoning_tokens > 0`): extracción desacoplada de `<think>...</think>`, preservación del razonamiento en artefactos JSON y verificación de $\text{ttft\_final\_ms} \ge \text{ttft\_ms}$.
  - `codigo` (especializados en tool calling / código, ej. Qwen2.5-Coder): despacho de herramientas de solo lectura con lista blanca (`dig`, `curl`, `openssl`).

---

## 4. Análisis Correlacional y de Significancia Estadística (Tarea 4.1.2 / SciPy)

Conforme a lo formulado en la Tarea 4.1.2 y el diseño metodológico del proyecto, se evaluó mediante `scipy.stats` la relación entre la escala de parámetros del modelo (eje independiente) y las magnitudes cuantitativas de rendimiento observadas sobre las 162 corridas reales (registrado en `data/benchmark_results/analisis_correlacional.md`):

### 4.1. Coeficientes de Correlación (Parámetros vs. Métricas)

| Dimensión / Métrica Evaluada | Coeficiente Spearman ($\rho$) | $p$-valor Spearman | Coeficiente Pearson ($r$) | $p$-valor Pearson | Significativo ($\alpha = 0.05$) |
|---|---|---|---|---|---|
| **TTFT (Prefill Latency)** | **$+0.8342$** | $< 0.0001$ | **$+0.7854$** | $< 0.0001$ | **Sí (Fuerte Positiva)** |
| **Velocidad Decodificación (Tokens/s)** | **$-0.6296$** | $< 0.0001$ | **$-0.7039$** | $< 0.0001$ | **Sí (Fuerte Inversa)** |
| **Latencia Total de Inferencia (ms)** | **$+0.7661$** | $< 0.0001$ | **$+0.8015$** | $< 0.0001$ | **Sí (Fuerte Positiva)** |
| **Consumo Energético (kWh)** | **$+0.7816$** | $< 0.0001$ | **$+0.8138$** | $< 0.0001$ | **Sí (Fuerte Positiva)** |
| **Rúbrica de Explicabilidad ($0-5$)** | $+0.2145$ | $0.00614$ | $+0.3078$ | $0.00007$ | **Sí (Positiva Moderada)** |
| **Acierto Parcial de Causa Raíz** | $+0.2426$ | $0.00187$ | $+0.3711$ | $< 0.0001$ | **Sí (Positiva Moderada)** |

*Interpretación:* La cantidad de parámetros gobierna de manera concluyente y estadísticamente significativa la velocidad de decodificación ($r = -0.7039$, $\rho = -0.6296$) y el tiempo al primer token ($r = +0.7854$, $\rho = +0.8342$). En hardware accesible, los modelos de mayor tamaño experimentan una sobrecarga apreciable en prellenado y consumo energético, pero compensan con una mayor capacidad para estructurar causas complejas sin caer en repetición de síntomas.

### 4.2. Prueba No Paramétrica de Kruskal-Wallis entre Modelos

Para verificar si las diferencias de rendimiento entre la terna son estadísticamente significativas más allá del azar muestral:
- **TTFT (ms):** $H = 117.24$, $p < 0.0001$ $\rightarrow$ Diferencias altamente significativas ($p < 0.001$).
- **Velocidad (Tokens/s):** $H = 66.82$, $p < 0.0001$ $\rightarrow$ Diferencias altamente significativas ($p < 0.001$).
- **Latencia Total (ms):** $H = 109.58$, $p < 0.0001$ $\rightarrow$ Diferencias altamente significativas ($p < 0.001$).
- **Energía (kWh):** $H = 110.91$, $p < 0.0001$ $\rightarrow$ Diferencias altamente significativas ($p < 0.001$).
- **Rúbrica Explicativa:** $H = 13.70$, $p = 0.00106$ $\rightarrow$ Diferencias significativas ($p < 0.01$).
- **Acierto Parcial:** $H = 20.05$, $p = 0.00004$ $\rightarrow$ Diferencias significativas ($p < 0.01$).

### 4.3. Intervalos de Confianza al 95% vía Bootstrap Percentil ($B = 1000$)

| Modelo Evaluado | Métrica | IC 95% Inferior | IC 95% Superior |
|---|---|---|---|
| **Phi-4-mini-instruct** | TTFT (ms) | $78,606.6\text{ ms}$ (~78.6 s) | $88,326.7\text{ ms}$ (~88.3 s) |
| | Velocidad (tok/s) | $4.34\text{ tok/s}$ | $4.68\text{ tok/s}$ |
| | Latencia Total Media (ms) | $167,253.6\text{ ms}$ (~2.79 min) | $187,521.7\text{ ms}$ (~3.13 min) |
| | Energía Media (kWh) | $0.0057\text{ kWh}$ | $0.0065\text{ kWh}$ |
| **Qwen3-8B** | TTFT (ms) | $151,745.7\text{ ms}$ (~151.7 s) | $173,262.8\text{ ms}$ (~173.3 s) |
| | Velocidad (tok/s) | $3.33\text{ tok/s}$ | $3.64\text{ tok/s}$ |
| | Latencia Total Media (ms) | $363,856.3\text{ ms}$ (~6.06 min) | $417,268.9\text{ ms}$ (~6.95 min) |
| | Energía Media (kWh) | $0.0149\text{ kWh}$ | $0.0173\text{ kWh}$ |
| **GLM-4-9B-Chat** | TTFT (ms) | $173,733.8\text{ ms}$ (~173.7 s) | $193,533.5\text{ ms}$ (~193.5 s) |
| | Velocidad (tok/s) | $3.28\text{ tok/s}$ | $3.42\text{ tok/s}$ |
| | Latencia Total Media (ms) | $383,535.7\text{ ms}$ (~6.39 min) | $427,132.6\text{ ms}$ (~7.12 min) |
| | Energía Media (kWh) | $0.0159\text{ kWh}$ | $0.0180\text{ kWh}$ |

### 4.4. Tamaño del Efecto ($d$ de Cohen) entre Pares de Modelos

| Dimensión / Métrica | Comparación | $d$ de Cohen | Interpretación Cualitativa |
|---|---|---|---|
| **TTFT (ms)** | GLM-4-9B vs. Phi-4-mini | $3.2988$ | Efecto muy grande (*Large*) |
| | GLM-4-9B vs. Qwen3-8B | $0.5406$ | Efecto mediano (*Medium*) |
| | Phi-4-mini vs. Qwen3-8B | $-2.4945$ | Efecto muy grande (*Large*) |
| **Velocidad (tok/s)** | GLM-4-9B vs. Phi-4-mini | $-2.3376$ | Efecto muy grande (*Large*) |
| | GLM-4-9B vs. Qwen3-8B | $-0.2908$ | Efecto pequeño (*Small*) |
| | Phi-4-mini vs. Qwen3-8B | $1.6657$ | Efecto muy grande (*Large*) |
| **Latencia Total (ms)** | GLM-4-9B vs. Phi-4-mini | $3.5125$ | Efecto muy grande (*Large*) |
| | GLM-4-9B vs. Qwen3-8B | $0.1670$ | Efecto despreciable (*Negligible*) |
| | Phi-4-mini vs. Qwen3-8B | $-2.8550$ | Efecto muy grande (*Large*) |

---

## 5. Trazabilidad de Resultados

Cada valor numérico de la tabla superior es directamente auditable en el archivo [`resultados.csv`](../data/benchmark_results/resultados.csv) mediante el triplete `(scenario_id, model_id, seed)`:
- Corridas 1 a 54: Modelo `qwen3-8b` sobre los 18 escenarios y 3 semillas deterministas.
- Corridas 55 a 108: Modelo `glm-4-9b-chat` sobre los 18 escenarios y 3 semillas deterministas.
- Corridas 109 a 162: Modelo `phi-4-mini-instruct` sobre los 18 escenarios y 3 semillas deterministas.

---

## 6. Desglose de Resultados por Modo de Ejecución (135 Simuladas vs. 27 Emuladas)

Conforme a los datos consolidados y auditados directamente desde el archivo `resultados.csv`, el desempeño comparativo entre ambos modos de ejecución es el siguiente:

| Modo de Ejecución | Total Corridas | Precisión Diagnóstica | Tasa Evidencia | Latencia Media (ms) | Rúbrica Prom. |
|---|---|---|---|---|---|
| **Laboratorio en Contenedores (Docker Compose) (emulado)** | 27 | **48.1%** | 96.3% | 460,288.9 ms (~7.67 min) | 4.00 / 5.0 |
| **Simulador Sintético Calibrado (sintetico_determinista)** | 135 | **85.2%** | 95.6% | 295,466.1 ms (~4.92 min) | 4.29 / 5.0 |
| **Consolidado Global (Benchmark L7)** | **162** | **79.0%** (128/162) | **95.1%** (154/162) | **322,723.4 ms** (~5.38 min) | **4.24 / 5.0** |

*Observación Metodológica:* El modo emulado impone el desafío de lidiar con telemetría de red real, tiempos de respuesta dinámicos y registros crudos de servicios vivos (BIND9, Nginx), lo que evidencia una brecha respecto al entorno controlado del simulador sintético, demostrando la necesidad de pruebas en contenedores reales para evaluar la robustez práctica de los SLM.

---

## 7. Declaración Formal de Desviaciones Metodológicas

Conforme al rigor experimental exigido por la Cuarta Auditoría, se declaran explícitamente las siguientes adaptaciones metodológicas:

1. **Repeticiones por Configuración:** Se ejecutó $R = 1$ repetición por cada una de las 3 semillas deterministas fijadas (`42`, `1337`, `2026`) con temperatura 0.0 ($3 \text{ modelos} \times 18 \text{ escenarios} \times 3 \text{ semillas} = 162 \text{ corridas}$). Esto garantiza cobertura del espacio estocástico sin duplicación redundante de cómputo determinista.
2. **Desviación de Tiempo Límite de Inferencia:** Debido a la ejecución sobre CPU host accesible (sin GPU dedicada), **158 de las 162 corridas** superaron la cota nominal de 120 segundos. El timeout de inferencia en `engine.py` fue ajustado formalmente a 900.0 segundos con mecanismo de reintento, asegurando la finalización completa de las cadenas CoT y evitando sesgos por truncamiento forzado.
3. **Trazabilidad Git y Versionado MLOps:** Inferencia de las 135 corridas simuladas realizada en entorno inicial sin repositorio Git inicializado (`git_commit_hash = "desconocido"`, `git_dirty = "desconocido"`); 27 corridas emuladas ejecutadas formalmente bajo commit de ejecución $X$ (`ca6e7fde914e6466840aeb0803ae45de24d94ce0`, `git_dirty = False`); recalificación normativa completa de las 162 filas efectuada bajo commit $Y$ (`4a4ef77a64ccd59dea68b439332736775c61c654`, registrado en la columna `rescore_commit`); inmutabilidad y paridad semántica garantizadas por la versión criptográfica única del evaluador normativo (`1f8c1a7e3a9d`).
4. **Memoria VRAM Reportada:** Las métricas de memoria de vídeo corresponden a la memoria declarada/estimada por Ollama para el cargue de capas GGUF y se excluyen del cálculo del score compuesto de compromiso.
