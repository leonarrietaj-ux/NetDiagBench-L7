# INFORME TÉCNICO DE EJECUCIÓN — PARTE 2/4
## Corrección Estadística, Evaluación Humana y Trazabilidad de NetDiagBench-L7

**Fecha:** 2026-11-06  
**Rama Git:** `audit-fixes-v4-parte1`  
**Commit Base:** `703f6f9`  
**Entorno de Ejecución:** Windows 11 / AMD Ryzen 3 7320U / Radeon 610M (iGPU) / Python 3.14.4  

---

## 1. RESUMEN EJECUTIVO

En cumplimiento estricto de las directrices metodológicas de la **PARTE 2/4**, se auditó, rediseñó y corrigió el núcleo estadístico, evaluativo y de trazabilidad de NetDiagBench-L7. Las intervenciones principales abarcaron:

1. **Centralización del Puntaje Compuesto 40/20/20/20:** Implementación estricta de la ponderación oficial ($0.40 \cdot A + 0.20 \cdot R + 0.20 \cdot V + 0.20 \cdot M$), umbral eliminatorio de viabilidad técnica ($\text{Accuracy} \ge 70.0\%$), separación taxativa entre puntaje medido y provisional, y formalización de los 5 estados estandarizados sin redistribución arbitraria del peso de VRAM.
2. **Eliminación Total de Fuga de Información (Zero Data Leakage):** Erradicación del sesgo en [src/layer7_evaluator/statistical_analysis.py](src/layer7_evaluator/statistical_analysis.py) (antiguas líneas 415-417 y 1411 que empleaban `is_root_cause_correct` y `fault_class` para reconstruir predicciones). Implementación del parser determinista `parse_fault_class_predicted()` basado exclusivamente en el texto emitido por el modelo contrastado contra el catálogo normativo [configs/evaluator_concepts.yaml](configs/evaluator_concepts.yaml), con cálculo riguroso de F1 Macro, precisión, recall, soporte y matriz de confusión vía `sklearn.metrics`.
3. **Bootstrap por Conglomerados (Cluster Bootstrap):** Sustitución del remuestreo simple i.i.d. por remuestreo por conglomerados emparejados a nivel de escenario (18 clusters), con 1000 réplicas, intervalo de confianza al 95%, semilla fija (`seed=42`) y preservación del formateo formal APA/IEEE para valores $p$ (eliminación de salidas `p = 0.000` reemplazadas por `p < 0.001`).
4. **Exactitud Factual (C6) y Sustentación Empírica (S):** Condicionamiento estricto de la bandera $S = \text{True}$ a la obtención de evidencia factual plena ($C_6 = 2$). Verificación de ejecución real de herramienta, salida verificable, correspondencia con `minimum_required_evidence` y penalización de contradicciones protocolarias en [src/layer5_orchestrator/agent.py](src/layer5_orchestrator/agent.py).
5. **Aislamiento Normativo TLS vs HTTP 503:** Expansión de conceptos de expiración TLS en [configs/evaluator_concepts.yaml](configs/evaluator_concepts.yaml) (`expired`, `notAfter`, `not after`, `vencido`, `certificado expirado`, `certificate has expired`, `certificate validity`) e inclusión de términos vecinos en `HTTP_503_SERVICE_UNAVAILABLE` para impedir falsas asociaciones sin evidencia de saturación de workers.
6. **Trazabilidad Criptográfica JSONL:** Emisión completa de los 27 campos mínimos en [src/layer7_evaluator/harness.py](src/layer7_evaluator/harness.py), diferenciando inequívocamente `template_sha256` (hash SHA-256 de [context_window.j2](data/templates/context_window.j2)) de `prompt_sha256` (hash del prompt instanciado). Actualización del validador [src/core/trace_validator.py](src/core/trace_validator.py) con detección de duplicados, respuestas vacías, hashes discordantes y discrepancias CSV/JSONL.
7. **Integridad de Evaluación Humana y Kits Excel:** Comprobación de que las hojas de los evaluadores A, B y C no contienen verdad fundamental. Adición de respaldo automático versionado en [src/layer8_human_eval/importer.py](src/layer8_human_eval/importer.py) para preservar el historial de importaciones sin sobrescrituras destructivas, y verificación de la lógica de dirimencia del Kit C limitada a desacuerdos $|C1_A - C1_B| \ge 1$ o $S_A \ne S_B$.

---

## 2. MODIFICACIONES DETALLADAS POR COMPONENTE

### 2.1. Puntaje Compuesto Centralizado ([src/layer7_evaluator/composite_score.py](src/layer7_evaluator/composite_score.py))
- **Ponderaciones fijadas:**
  $$\text{WEIGHTS} = \{\text{'accuracy'}: 0.40, \text{'rubric'}: 0.20, \text{'speed'}: 0.20, \text{'vram\_efficiency'}: 0.20\}$$
- **Umbral eliminatorio:**
  $$\text{accuracy} < 70.0\% \implies \text{elegible} = \text{False}, \quad \text{estado} = \text{INELIGIBLE\_ACCURACY}$$
- **Estados implementados:**
  - `COMPLETE_MEASURED`: Mediciones físicas de VRAM disponibles vía GPU dedicada + rúbrica humana disponible.
  - `PROVISIONAL_ESTIMATED`: VRAM física no medible (ej. iGPU compartida o CPU); conserva puntaje compuesto provisional separado sin publicar ranking como medido.
  - `PENDING_HUMAN_EVALUATION`: Pendiente de calificaciones humanas ($R$).
  - `PENDING_VRAM_MEASUREMENT`: Pendiente de telemetría de VRAM.
  - `INELIGIBLE_ACCURACY`: Modelo con exactitud diagnóstica inferior al 70%.
- **No redistribución:** El 20% de VRAM nunca se reparte entre los demás componentes ante la ausencia de GPU dedicada.

### 2.2. F1 Macro y Eliminación de Fuga de Datos ([src/layer7_evaluator/statistical_analysis.py](src/layer7_evaluator/statistical_analysis.py))
- **Eliminación del sesgo:** Se suprimieron las líneas que inspeccionaban `row.get("is_root_cause_correct")` y `row.get("fault_class")`.
- **Nuevo Parser:** [`parse_fault_class_predicted(model_text, concepts_catalog)`](src/layer7_evaluator/statistical_analysis.py#L382):
  1. Limpia y normaliza el texto libre del modelo.
  2. Evalúa grupos de causas (+3 puntos), conceptos directos (+1 punto) y penaliza conceptos vecinos (-1 punto).
  3. Detecta empates (`is_ambiguous = True`) y asigna `UNKNOWN` cuando la puntuación máxima es $\le 0$ o el texto está vacío.
  4. Preserva intacto el texto de diagnóstico original en `model_diagnosis_text` y `root_cause`.
- **Métricas Oficiales:** Cálculo de `f1_score(average='macro')`, `precision_score`, `recall_score`, métricas por clase y matriz de confusión mediante `sklearn.metrics`.

### 2.3. Bootstrap por Conglomerados y Valores $p$ ([src/layer7_evaluator/statistical_analysis.py](src/layer7_evaluator/statistical_analysis.py))
- **Diseño de Conglomerados:** En [`compute_model_bootstrap_ci95`](src/layer7_evaluator/statistical_analysis.py#L1400), el escenario actúa como unidad de remuestreo (18 clusters). Se muestrean escenarios con reemplazo y se conservan emparejadas todas las corridas asociadas (modelos y semillas).
- **Parámetros:** 1000 réplicas, $95\%$ de confianza, semilla reproducible `seed=42`.
- **Metadatos registrados:** `method: "cluster_bootstrap_percentile"`, `cluster_unit: "scenario_id"`, `n_clusters: 18`, `seed: 42`, `limitations: "Muestra finita de 18 escenarios de red L7; el remuestreo por conglomerados preserva la correlación intrascenario y el diseño emparejado entre modelos."`.
- **Formateo de Valores $p$:** [`format_p_value(p)`](src/layer7_evaluator/statistical_analysis.py#L372) formatea $p < 0.001$ según norma formal APA/IEEE. Nunca emite `p = 0.000`.

### 2.4. Exactitud Factual C6 y Sustentación S ([src/layer5_orchestrator/agent.py](src/layer5_orchestrator/agent.py))
- Implementación de [`_evaluate_factual_accuracy_c6`](src/layer5_orchestrator/agent.py#L186):
  1. Comprueba salida verificable no vacía (sin errores de seguridad ni bloqueos).
  2. Verifica coincidencia con `minimum_required_evidence`.
  3. Detecta contradicciones explícitas (ej. salida muestra NXDOMAIN pero modelo diagnostica SERVFAIL; salida muestra expiración TLS pero modelo diagnostica HTTP 503).
  4. Asigna:
     - $C_6 = 2 \implies S = \text{True}$ (Evidencia plena verificable sin contradicción).
     - $C_6 = 1 \implies S = \text{False}$ (Evidencia verificada pero parcial/incompleta respecto al requerimiento).
     - $C_6 = 0 \implies S = \text{False}$ (Sin evidencia, comando bloqueado o contradicción factual de protocolo).
- Regla inviolable: $S = 1$ únicamente cuando $C_6 = 2$.

### 2.5. Aislamiento TLS y HTTP ([configs/evaluator_concepts.yaml](configs/evaluator_concepts.yaml))
- Se expandió `TLS_EXPIRED_CERT` con términos requeridos: `expired`, `notAfter`, `not after`, `vencido`, `certificado expirado`, `certificate has expired`, `certificate validity`.
- Se añadieron `certificate validity`, `notAfter` y `not after` como conceptos vecinos excluyentes en `HTTP_503_SERVICE_UNAVAILABLE`.

### 2.6. Trazabilidad JSONL y Criptografía ([src/layer7_evaluator/harness.py](src/layer7_evaluator/harness.py) y [src/core/trace_validator.py](src/core/trace_validator.py))
- En [`_emit_trace_entry`](src/layer7_evaluator/harness.py#L606):
  - `template_sha256`: Hash SHA-256 del archivo [data/templates/context_window.j2](data/templates/context_window.j2).
  - `prompt_sha256`: Hash SHA-256 del prompt final instanciado.
  - `response_sha256`: Hash SHA-256 de la respuesta del modelo.
  - `config_sha256`: Hash SHA-256 de [configs/benchmark_config.yaml](configs/benchmark_config.yaml).
  - Campos mínimos: `campaign_id`, `run_id`, `attempt_id`, `model_id`, `scenario_id`, `seed`, `execution_mode`, `engine_mode`, `execution_backend`, `latency_s`, `diagnostico`, `evidence_status`.
- En [`trace_validator.py`](src/core/trace_validator.py):
  - Detección de duplicados en tiempo lineal mediante seguimiento de `run_id`.
  - Detección de respuestas vacías o nulas.
  - Validación de divergencia obligatoria entre `template_sha256` y `prompt_sha256`.
  - Nueva función [`validate_alignment_csv_jsonl`](src/core/trace_validator.py#L248) para cotejar integridad y cantidad entre `resultados.csv` y `traza.jsonl`.

### 2.7. Preservación Histórica de Evaluación Humana ([src/layer8_human_eval/importer.py](src/layer8_human_eval/importer.py))
- En [`import_expert_responses`](src/layer8_human_eval/importer.py#L104):
  - Si `respuestas_<ID>.csv` ya existe, se genera un archivo de respaldo con marca temporal UTC (`respuestas_<ID>_YYYYMMDD_HHMMSS.bak.csv`) antes de escribir nuevas filas, impidiendo la pérdida silenciosa de evaluaciones históricas.
  - Verificación del desempate de Kit C: el árbitro E3 interviene exclusivamente sobre las discrepancias detectadas entre Kit A y Kit B ($|C1_A - C1_B| \ge 1$ o $S_A \ne S_B$).

---

## 3. RESULTADOS DE PRUEBAS AUTOMATIZADAS

Se ejecutó la suite completa de pruebas unitarias implementada para la Parte 2:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_parte2_suite.py
```
**Resultado:**
```
============================= 21 passed in 24.33s =============================
```

### Desglose de Pruebas:
| Módulo / Clase de Prueba | Pruebas | Estado | Verificación |
|---|:---:|:---:|---|
| `TestCompositeScore` | 4 | **PASSED** | Ponderación 40/20/20/20, umbral $\ge 70\%$, VRAM no redistribuida, 5 estados normativos |
| `TestF1MacroZeroLeakage` | 4 | **PASSED** | Parseo sin verdad fundamental, manejo de ambigüedad/UNKNOWN, cero fuga de datos |
| `TestBootstrapAndStats` | 2 | **PASSED** | Cluster Bootstrap por escenario (18 clusters), IC 95%, $p < 0.001$ (sin $p = 0.000$) |
| `TestFactualAccuracyC6` | 4 | **PASSED** | Respaldo pleno ($C_6=2 \implies S=1$), parcial ($C_6=1 \implies S=0$), penalización de contradicciones |
| `TestTlsHttpIsolation` | 3 | **PASSED** | Aislamiento de conceptos normativos TLS vs HTTP 503 conforme a RFC 5280 y RFC 9110 |
| `TestTraceValidatorAndHashes` | 4 | **PASSED** | Diferenciación `template_sha256` vs `prompt_sha256`, detección de respuestas vacías y cotejo CSV/JSONL |

Adicionalmente, se re-ejecutó la suite de la Parte 1 ([tests/test_multiplatform_hardware.py](tests/test_multiplatform_hardware.py)):
```
============================= 10 passed in 1.48s ==============================
```
**Total de pruebas superadas sin regresiones:** 31/31 pruebas aprobadas (100%).

---

## 4. CUESTIONES RESUELTAS

1. **Eliminación del sesgo tramposo en F1 Macro:** Se removió la lógica que forzaba la clase predicha basándose en `is_root_cause_correct`.
2. **Independencia en remuestreo estadístico:** Se sustituyó el remuestreo de filas independientes por remuestreo por conglomerados emparejados a nivel de escenario.
3. **Formateo de valores de significancia:** Se aseguró que ningún reporte o función devuelva `p = 0.000`.
4. **Regla unificada de evidencia:** Se implementó que un diagnóstico solo está sustentado empíricamente ($S = \text{True}$) si $C_6 = 2$.
5. **Diferenciación de huellas digitales:** Se separó el hash de la plantilla Jinja2 del hash del prompt renderizado.
6. **Preservación de importaciones de expertos:** Se creó el mecanismo de copias de seguridad automáticas ante reimportaciones en Capa 8.
7. **Integridad de datos originales:** Se conservaron intactos los archivos [data/human_eval/evaluaciones_originales.csv](data/human_eval/evaluaciones_originales.csv) (108 filas) y [data/human_eval/evaluaciones_adjudicadas.csv](data/human_eval/evaluaciones_adjudicadas.csv) (54 filas).

---

## 5. ESTADO DE PREPARACIÓN PARA PRUEBAS PILOTO

- **Inicio del Aplicativo:** El backend FastAPI ([src/layer6_interface/web.py](src/layer6_interface/web.py)) y la interfaz web cargan correctamente todos los routers y módulos sin errores de importación.
- **Detección de Hardware Local:**
  - Clasificación: `GPU_INTEGRATED`
  - GPU: `AMD Radeon(TM) 610M`
  - RAM Total: `13.83 GB`
  - Backend de Inferencia: `CPU`
  - VRAM Pico Medida: `null` (`not_available`, sin falseo de telemetría dedicada)
- **Terna Oficial Identificada:**
  1. `qwen3-8b`
  2. `glm-4-9b-chat`
  3. `phi-4-mini-instruct`
- **Preparación de Pilotos:** El sistema está listo para ejecutar las 6 inferencias piloto (2 por modelo: 1 emulada en contenedor Docker y 1 sintética determinista) sin iniciar aún las 162 corridas experimentales definitivas.

---

## 6. CUESTIONES PENDIENTES PARA LA PARTE 3

1. **Calibración de las 6 corridas piloto:** Ejecución controlada de 2 corridas por modelo (1 emulada Docker + 1 determinista) para verificar la emisión de trazas v4 en tiempo real.
2. **Validación del Dashboard de Observabilidad:** Comprobación del renderizado de los 5 estados en la interfaz web y paneles HTMX.
3. **Comprobación de Exportación Técnica:** Verificación de generación de reportes PDF y Markdown con los nuevos intervalos de confianza BCa/Percentil y formato de valor $p$.
4. **Verificación de límites de contexto:** Asegurar manejo de tokens de razonamiento (`reasoning_tokens`) y truncamiento en modelos CoT (Qwen3-8B).

---

## 7. ARCHIVOS MODIFICADOS EN LA PARTE 2

- [`configs/evaluator_concepts.yaml`](configs/evaluator_concepts.yaml)
- [`src/core/trace_validator.py`](src/core/trace_validator.py)
- [`src/layer5_orchestrator/agent.py`](src/layer5_orchestrator/agent.py)
- [`src/layer7_evaluator/composite_score.py`](src/layer7_evaluator/composite_score.py)
- [`src/layer7_evaluator/harness.py`](src/layer7_evaluator/harness.py)
- [`src/layer7_evaluator/statistical_analysis.py`](src/layer7_evaluator/statistical_analysis.py)
- [`src/layer8_human_eval/importer.py`](src/layer8_human_eval/importer.py)
- [`tests/test_parte2_suite.py`](tests/test_parte2_suite.py) (nuevo archivo de pruebas)
- [`docs/INFORME_PARTE_2.md`](docs/INFORME_PARTE_2.md) (presente informe)
