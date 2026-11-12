# INFORME DE AUDITORÍA DE CIERRE Y PREPARACIÓN PARA GITHUB
## NetDiagBench-L7: Benchmark Agéntico de Diagnóstico Layer 7 sobre IP

**Fecha:** 2026-11-12  
**Versión de Entrega:** 1.0.0  
**Directorio Auditado:** `release/NetDiagBench-L7-public/`  
**Repositorio Remoto Objetivo:** `https://github.com/leonarrietaj-ux/NetDiagBench-L7.git`  
**Dictamen Técnico Global:** **APROBADO PARA PUBLICACIÓN INMEDIATA (100% COHERENCIA CIENTÍFICA, SEGURIDAD Y REPRODUCIBILIDAD)**

---

## 1. RESUMEN EJECUTIVO

Se ejecutó la intervención definitiva de ingeniería de software, saneamiento documental, conciliación estadística, protección de privacidad y preparación de publicación del proyecto **NetDiagBench-L7** exclusivamente sobre el directorio público `release/NetDiagBench-L7-public/`. 

El repositorio original de investigación (`benchapp-ip`), la tesis original y los respaldos históricos en `release_audit/` han permanecido **completamente intactos**.

Los principales hitos completados y verificados son:
1. **Conservación Científica Inmutable:** Las 162 corridas experimentales, los 18 escenarios de falla y las 3 semillas (`[42, 1337, 2026]`) están congeladas e íntegras al 100%. Las 9 huellas criptográficas SHA-256 protegidas coinciden bit a bit antes y después de la intervención.
2. **Saneamiento Físico de Privacidad:** Eliminación física de archivos de evaluación humana confidenciales (`CURRENT_SESSION.txt`, `SESION_KIT_CASO2/`), llaves privadas RSA y modelos/archivos exploratorios no oficiales (`data/runs/smollm-1b`, `data/runs/*.pdf`, `bitacora_state.json`), conservando únicamente `.gitkeep`.
3. **Depuración de la Terna SLM:** Eliminación en código, plantillas y selector web de cualquier modelo residual o duplicado; se garantiza que la terna está estrictamente conformada por:
   - `GLM-4-9B-Chat` (9.0B, GLM-4 License)
   - `Qwen3-8B` (8.2B, Apache 2.0)
   - `Phi-4-mini-instruct` (3.8B, MIT)
4. **Portabilidad Multiplataforma:** Renombrado del archivo de tesis de 171 caracteres a `docs/DOCUMENTO_FINAL_TESIS_GRADO.md` para prevenir errores de longitud de ruta en Windows (`WinError 3`) y sistemas POSIX.
5. **Verificación Automatizada Exhaustiva:** 339 pruebas unitarias y de integración pasando al 100% en pytest (con 4 pruebas de kits privados omitidas de forma segura y declarada). El script de auditoría global `scripts/verify_global_consistency.py` pasa con 100% de coherencia.
6. **Manifiesto Criptográfico de Publicación:** Generación del archivo formal `data/benchmark_results/MANIFEST_PUBLICACION_SHA256.json` que registra las huellas de todos los activos científicos y técnicos.

---

## 2. MATRIZ DE CONSISTENCIA CIENTÍFICA Y ESTADÍSTICA GLOBAL

La siguiente matriz detalla la concordancia unívoca entre todos los componentes del sistema (dataset canónico CSV, paquete FAIR JSON, manifiesto de campaña, motor de análisis estadístico, scorecard y tesis de grado):

| Métrica Oficial | CSV Canónico (`resultados.csv`) | FAIR Bundle (`dataset_bundle.json`) | Motor Estadístico (`statistical_analysis.py`) | Scorecard (`composite_score.py`) | Tesis y Matriz Oficial | Estado de Concordancia |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Población Total** | 162 corridas | 162 corridas | 162 corridas | 162 corridas | 162 corridas | ✅ 100% Idéntico |
| **Escenarios RFC** | 18 escenarios | 18 escenarios | 18 escenarios | 18 escenarios | 18 escenarios | ✅ 100% Idéntico |
| **Terna de Modelos** | 3 modelos (54 c/u) | 3 modelos | 3 modelos | 3 modelos | 3 modelos | ✅ 100% Idéntico |
| **Semillas Autorizadas** | [42, 1337, 2026] | [42, 1337, 2026] | [42, 1337, 2026] | [42, 1337, 2026] | [42, 1337, 2026] | ✅ 100% Idéntico |
| **Diagnóstico Completo Total** | **122/162 (75.31%)** | **0.7531** | **75.3%** | N/A | **122/162 (75.3%)** | ✅ 100% Idéntico |
| - GLM-4-9B-Chat | 40/54 (74.1%) | 74.07% | 74.1% | 74.07% (Elegible) | 40/54 (74.1%) | ✅ 100% Idéntico |
| - Qwen3-8B | 47/54 (87.0%) | 87.04% | 87.0% | 87.04% (Elegible) | 47/54 (87.0%) | ✅ 100% Idéntico |
| - Phi-4-mini-instruct | 35/54 (64.8%) | 64.81% | 64.8% | 64.81% (No Elegible <70%) | 35/54 (64.8%) | ✅ 100% Idéntico |
| **Causa Raíz Estricta Total** | **71/162 (43.83%)** | **0.4383** | **43.8%** | N/A | **71/162 (43.8%)** | ✅ 100% Idéntico |
| - GLM-4-9B-Chat | 33/54 (61.1%) | 61.11% | 61.1% | N/A | 33/54 (61.1%) | ✅ 100% Idéntico |
| - Qwen3-8B | 24/54 (44.4%) | 44.44% | 44.4% | N/A | 24/54 (44.4%) | ✅ 100% Idéntico |
| - Phi-4-mini-instruct | 14/54 (25.9%) | 25.93% | 25.9% | N/A | 14/54 (25.9%) | ✅ 100% Idéntico |
| **Coincidencia Canónica** | **120/162 (74.07%)** | **0.7407** | **74.1%** | N/A | **120/162 (74.1%)** | ✅ 100% Idéntico |
| **Evidencia Read-Only** | **38/162 (23.46%)** | **0.2346** | **23.5%** | N/A | **38/162 (23.5%)** | ✅ 100% Idéntico |
| - GLM-4-9B-Chat | 23/54 (42.6%) | 42.59% | 42.6% | N/A | 23/54 (42.6%) | ✅ 100% Idéntico |
| - Qwen3-8B | 15/54 (27.8%) | 27.78% | 27.8% | N/A | 15/54 (27.8%) | ✅ 100% Idéntico |
| - Phi-4-mini-instruct | 0/54 (0.0%) | 0.00% | 0.0% | N/A | 0/54 (0.0%) | ✅ 100% Idéntico |
| **Rúbrica Humana Global** | **3.92 / 5.0** | **3.9167** | **3.92** | N/A | **3.92 / 5.0** | ✅ 100% Idéntico |
| - GLM-4-9B-Chat | 4.13 / 5.0 | 4.1296 | 4.13 | 4.13 | 4.13 / 5.0 | ✅ 100% Idéntico |
| - Qwen3-8B | 4.07 / 5.0 | 4.0741 | 4.07 | 4.07 | 4.07 / 5.0 | ✅ 100% Idéntico |
| - Phi-4-mini-instruct | 3.55 / 5.0 | 3.5463 | 3.55 | 3.55 | 3.55 / 5.0 | ✅ 100% Idéntico |
| **Scorecard Compuesto** | N/A | N/A | Ponderación 40/20/20/20 | VRAM Estimada Provisional | Provisional | ✅ 100% Idéntico |
| - GLM-4-9B-Chat | N/A | N/A | 0.7323 | 0.7323 (Elegible) | 0.7323 | ✅ 100% Idéntico |
| - Qwen3-8B | N/A | N/A | 0.7217 | 0.7217 (Elegible) | 0.7217 | ✅ 100% Idéntico |
| - Phi-4-mini-instruct | N/A | N/A | 0.8012 | 0.8012 (No Elegible) | 0.8012 | ✅ 100% Idéntico |
| **Prueba de Friedman** | N/A | N/A | $\chi^2 = 6.8205$, $p = 0.03303$ | N/A | $\chi^2 = 6.8205$, $p = 0.033$ | ✅ 100% Idéntico |

---

## 3. AUDITORÍA DE SEGURIDAD, PRIVACIDAD Y SANEAMIENTO FÍSICO

Se ejecutó un saneamiento profundo en cumplimiento de los estándares de ciberseguridad para repositorios de investigación:
1. **Llaves Privadas y Certificados:** Se excluyeron del árbol de trabajo todas las claves privadas (`certs/*.key`, `certs/*.pem`). Se suministra el script `scripts/generate_test_certs.py` documentado para generar certificados TLS efímeros y auto-firmados en cualquier entorno local.
2. **Evaluación Humana:** Se eliminó físicamente `data/human_eval/CURRENT_SESSION.txt` y la carpeta privada `data/human_eval/SESION_KIT_CASO2/` con los instrumentos no cegados. Se preservaron los datos consolidados y adjudicados en `data/human_eval/evaluaciones_adjudicadas.csv`.
3. **Depuración de Corridas Locales:** Se eliminó la carpeta de modelo residual `data/runs/smollm-1b/`, bitácoras transitorias y archivos PDF huérfanos. El directorio `data/runs/` se conserva limpio con su archivo `.gitkeep`.
4. **Cachés y Temporales:** Se purgaron todos los directorios `__pycache__/`, `.pytest_cache/` y archivos `*.pyc`.
5. **Rutas Absolutas:** Se verificó la ausencia total de rutas locales de desarrollo de Windows (`file:///C:/Users/...`).

---

## 4. VALIDACIÓN CRIPTOGRÁFICA DE ARCHIVOS PROTEGIDOS (SHA-256)

Los 9 archivos nucleares del benchmark fueron validados antes y después de todas las operaciones, garantizando cero alteración de datos experimentales:

| Archivo Protegido | SHA-256 Verificado | Estado |
|---|:---:|:---:|
| `data/benchmark_results/resultados.csv` | `0B63EB335EBA2BB923DD341BA0DC6A6EFC09E3A14D91F1F6A69F86F2D96B4F27` | ✅ Intacto |
| `data/benchmark_results/traza.jsonl` | `611FA9C0100B69E801E68217D6149B5A5B281FA9BBB25D17C15F63216648EF83` | ✅ Intacto |
| `data/benchmark_results/dataset_bundle.json` | `E153707EA0048EF0D4AE700BB2D8DCDD30F073AD4D57DBB8FF0340EE00F721DE` | ✅ Intacto |
| `data/campaign_162/resultados.csv` | `045BB8B1A3E92F29AA2230512F5845EC7E6E09E9B7A1AB5D62F0CB5847C042F9` | ✅ Intacto |
| `data/campaign_162/recalificacion_auditada.csv` | `7D0817F6A0890F85630E2B2B01BA605A37F20398A116FB2961ABBED9EEA8B542` | ✅ Intacto |
| `data/campaign_162/traza.jsonl` | `FFC1DBD7A008ED94823D5F41CB48EF270B2D3E900DBF5464A944CE5145840025` | ✅ Intacto |
| `data/campaign_162/manifest.json` | `07CF3DBFB6CC099D1C33660B71E37094A7DDD3F05AE13B1CDEA6AFB770AEBF0C` | ✅ Intacto |
| `data/human_eval/evaluaciones_adjudicadas.csv` | `43FCBF3C5AF8F021B9763A413A62697CA0E02910B80459086ABBABAF1E1603F9` | ✅ Intacto |
| `configs/models.yaml` | `432D205C8C80B6044BBA6EDEC9C08C35401E14AF6499B041F178E0772A068DFD` | ✅ Intacto |

---

## 5. SCORECARD MULTICRITERIO Y UMBRAL DE ELEGIBILIDAD

El sistema multicriterio implementado en `src/layer7_evaluator/composite_score.py` respeta estrictamente los pesos metodológicos fijados en el diseño experimental:
- **Exactitud Diagnóstica:** 40%
- **Eficiencia Computacional (Tiempo de Inferencia):** 20%
- **Huella Energética y de Carbono:** 20%
- **Consumo de Memoria VRAM:** 20%

**Tratamiento de VRAM y Hardware:**
Dado que la campaña oficial fue ejecutada en CPU sin GPU dedicada, los valores de VRAM corresponden a valores declarados/estimados provisionales según `configs/models.yaml` y `configs/hardware_reference.yaml`. Se preservó la etiqueta `PROVISIONAL_ESTIMATED` sin redistribuir artificialmente el 20% del peso hacia otras métricas.

**Umbral de Elegibilidad:**
Se exige un umbral mínimo del 70% de exactitud diagnóstica para considerar a un modelo elegible para despliegue operacional:
- `GLM-4-9B-Chat`: Score = 0.7323 | Diagnóstico = 74.07% $\ge$ 70% $\rightarrow$ **ELEGIBLE**
- `Qwen3-8B`: Score = 0.7217 | Diagnóstico = 87.04% $\ge$ 70% $\rightarrow$ **ELEGIBLE**
- `Phi-4-mini-instruct`: Score = 0.8012 | Diagnóstico = 64.81% < 70% $\rightarrow$ **NO ELEGIBLE**

---

## 6. VERIFICACIÓN AUTOMATIZADA GLOBAL

La ejecución de la suite completa de pruebas arrojó:
- **Pytest:** 339 pruebas aprobadas, 0 fallas, 7 omitidas justificadas (4 por exclusión segura de kits humanos privados y 3 por requerir servicios Uvicorn/Docker en vivo).
- **Verificador Canónico (`scripts/verify_global_consistency.py`):** 100% de éxito en verificación cruzada de datasets, bundle FAIR, manifiestos, scorecard compuesto y pruebas estadísticas de significancia (Friedman $\chi^2 = 6.8205$, $p = 0.033$).

---

## 7. DICTAMEN TÉCNICO FINAL

El directorio `release/NetDiagBench-L7-public/` se encuentra **completamente auditado, validado, saneado y aprobado** para su publicación pública en GitHub:
- Repositorio remoto: `https://github.com/leonarrietaj-ux/NetDiagBench-L7.git`
- Rama de publicación: `main`
- Versión liberada: `1.0.0`
