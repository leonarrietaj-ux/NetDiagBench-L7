# INFORME DE ENTREGA: PARTE 1/4 — AUDITORÍA INTEGRAL Y CORRECCIÓN DE ARQUITECTURA DE NetDiagBench-L7

**Proyecto:** NetDiagBench-L7 — Benchmark Reproducible para Diagnóstico de Fallas L7 con SLMs Locales  
**Fecha de Entrega:** 6 de noviembre de 2026  
**Rama Git:** `audit-fixes-v4-parte1`  
**Estado General:** Fase 1/4 Completada con Éxito. Arquitectura 100% estable, multiplataforma, detecciones no declarativas e integración Ollama verificada.

---

## 1. Respaldo Integral y Control de Versiones

Antes de realizar modificaciones sobre el código fuente, se ejecutaron las acciones preventivas de respaldo:
1. **Estado Git Inicial:** Identificado en rama `audit-fixes-v3` con árbol de trabajo limpio.
2. **Nueva Rama de Trabajo:** Creada la rama `audit-fixes-v4-parte1`.
3. **Respaldo Externo al Repositorio:**
   - **Ruta de Respaldo:** `c:\Users\USUARIO\OneDrive\Escritorio\backup_netdiagbench_l7_parte1`
   - **Alcance del Respaldo:** Código fuente (`src/`), configuraciones (`configs/`), escenarios (`scenarios/`), datos y evaluaciones humanas (`data/`), documentación (`docs/`), reportes (`reports/`), entregables técnicos (`entrega_tecnica/`), pruebas (`tests/`) y scripts (`scripts/`).
   - **Archivos Respaldados:** 743 archivos.
   - **Hashes Criptográficos:** Generados en `hashes.sha256` y `BACKUP_MANIFEST.json`.
   - **Verificación de Integridad:** 743 archivos verificados de forma exacta (0 discrepancias, 0 errores).

---

## 2. Archivos Modificados y Creados

| Archivo | Tipo de Acción | Propósito de la Modificación |
|---|---|---|
| `src/core/hardware_detector.py` | Modificación Mayor | Eliminación de valores fijos en código. Implementación de detección multiplataforma (Windows, Linux, macOS) para NVIDIA, AMD, iGPU y CPU-only; diferenciación rigurosa de VRAM dedicada vs. compartida; clasificación normativa (`GPU_DEDICATED`, `GPU_INTEGRATED`, `CPU_ONLY`, `GPU_DETECTED_UNSUPPORTED`, `HARDWARE_DETECTION_PARTIAL`); sondeo en vivo de backend de Ollama (`CPU`, `GPU`, `HYBRID`, `UNKNOWN`). |
| `src/core/contracts.py` | Modificación | Incorporación de campos normativos de VRAM y RAM (`vram_declared_gb`, `vram_estimated_gb`, `vram_peak_gb`, `vram_total_gb`, `vram_shared_gb`, `vram_measurement_method`, `vram_measurement_valid`, `vram_measurement_status`, `ram_total_gb`, `ram_available_gb`, `ram_peak_gb`, `ram_measurement_method`, `hardware_classification`, `inference_backend`) en `ResultadoEvaluacionContract` y `TelemetriaInferencia`. |
| `src/layer4_inference/engine.py` | Modificación | Enlace con `detect_ollama_backend_and_vram`. Asignación estricta de `engine_mode: live_ollama` vs `deterministic_simulator`. Supresión del fallback silencioso a valores aproximados de VRAM cuando el modelo se ejecuta en CPU (`size_vram == 0`). Telemetría de simulador determinista sin inventar picos físicos de VRAM. |
| `src/layer5_orchestrator/agent.py` | Corrección de Bug | Propagación explícita de `engine_mode` desde la respuesta de inferencia hacia `_parse_final_diagnosis` para evitar que diagnósticos reales de Ollama fueran catalogados erróneamente como simulación determinista. |
| `src/layer7_evaluator/harness.py` | Modificación | Persistencia de los 12 campos de telemetría de hardware real en `finalize_trial_evaluation`, eliminando el valor estático `vram_declared_gb = 8.0` y registrando el backend real y el método de medición. |
| `src/layer7_evaluator/composite_score.py` | Modificación | Generalización de la observación técnica para cualquier hardware sin sensor físico de VRAM dedicada, preservando la regla de no redistribución del 20%. |
| `tests/test_multiplatform_hardware.py` | Creación | Suite completa de 10 pruebas unitarias con mocks para: NVIDIA, AMD, GPU integrada, CPU-only, memoria compartida, VRAM no disponible, errores de instrumentación, Ollama caído, modelos no instalados e incompatibilidad de recursos. |
| `docs/AUDITORIA_TECNICA_INICIAL.md` | Creación | Informe técnico exhaustivo de la auditoría inicial del repositorio, fuentes de datos, dependencias y anomalías. |
| `docs/REGISTRO_DECISIONES_METODOLOGICAS.md` | Creación | Registro formal de aclaraciones normativas: inexistencia del "Acta A1.3", justificación de los pesos 40/20/20/20 como especificaciones técnicas, ubicación de la rúbrica humana real v3.0.0 y reglas C6 y S. |
| `docs/INFORME_PARTE_1.md` | Creación | Presente informe de entrega de la Parte 1/4. |

---

## 3. Problemas Identificados y Resueltos

1. **Valores Estáticos de Hardware en Código (Resuelto):** Se eliminó la suposición fija de `AMD Radeon 610M`, `2.0 GB VRAM` y `8.0 GB declarados`. El sistema detecta dinámicamente el hardware del host real y clasifica la arquitectura.
2. **Confusión de Memoria Compartida con VRAM Dedicada (Resuelto):** Para GPU integrada y CPU-only, `vram_peak_gb = None`, `vram_measurement_valid = False` y `vram_measurement_status = "not_available"`. La memoria compartida se aísla en `vram_shared_gb`.
3. **Simulación Falsa de VRAM en CPU (Resuelto):** El motor ya no asigna `approx_vram_gb` simulando que hubo uso de memoria de vídeo cuando Ollama ejecuta el modelo en CPU (`size_vram == 0`).
4. **Desconexión de `engine_mode` en Orquestación (Resuelto):** Se corrigió la pérdida del parámetro `engine_mode` en el flujo de `agent.py`.
5. **Aclaración Documental sobre "Acta A1.3" (Resuelto):** Se aclaró la inexistencia de un "Acta A1.3", reconociéndose la Actividad A1.3 de pilotaje y fundamentando los pesos 40/20/20/20 como especificaciones directas del proyecto sin falsas atribuciones.
6. **Incompatibilidad de Recursos y Resiliencia (Resuelto):** Implementada la verificación preventiva de RAM física disponible antes de intentar cargar modelos pesados (`check_resource_availability`).

---

## 4. Problemas Pendientes (Para Partes 2, 3 y 4)

1. **Parte 2 (Limpieza y Sincronización de Trazas):**
   - Depurar `data/benchmark_results/traza.jsonl` (actualmente con 311 entradas, duplicados y ejecuciones de `smollm-1b`) para dejar exactamente las corridas de la campaña activa estructuradas con `seed` en el nivel superior.
2. **Parte 3 (Calibración Estadística y Evaluación Normativa):**
   - Ejecutar la verificación cruzada de pruebas no paramétricas (Kruskal-Wallis, Bootstrap 1000 iteraciones, corrección de Benjamini-Hochberg) y concordancia inter-evaluador (Krippendorff Alpha y Fleiss Kappa sobre las 54 corridas de expertos E1, E2, E3).
3. **Parte 4 (Ejecución Oficial de la Campaña de 162 Corridas):**
   - Ejecución secuencial controlada de las 162 corridas experimentales oficiales (3 modelos × 18 escenarios × 3 semillas) con inferencia real y generación final de libros Excel y reportes PDF.

---

## 5. Confirmación Operativa del Sistema

- **Arranque Web (FastAPI / HTMX):** Verificado exitosamente (`app.title = "NetDiagBench-L7 Dashboard"`).
- **Arranque CLI (`src.layer6_interface.cli`):** Verificado exitosamente.
- **Suite de Pruebas:**
  - `tests/test_multiplatform_hardware.py`: 10 pruebas pasadas (100%).
  - `tests/test_fase2_findings.py`: 7 pruebas pasadas (100%).
  - `tests/test_execution_history.py`: 12 pruebas pasadas (100%).
- **Estado de la Campaña Experimental:** **NO se han ejecutado todavía las 162 corridas oficiales**, en estricto cumplimiento de la regla de no avanzar hasta completar las fases previas de validación.

El sistema se encuentra en estado óptimo, estable y preparado para la siguiente instrucción del usuario.
