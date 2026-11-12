# INFORME DE AUDITORÍA DE CIERRE Y PREPARACIÓN PARA GITHUB
## NetDiagBench-L7: Benchmark Científico de Diagnóstico Layer 7 sobre IP

**Fecha:** 2026-11-12  
**Directorio Auditado:** `release/NetDiagBench-L7-public/`  
**Repositorio Remoto Objetivo:** `https://github.com/leonarrietaj-ux/NetDiagBench-L7.git`  
**Dictamen Técnico:** **APROBADO PARA PUBLICACIÓN INMEDIATA (100% COHERENCIA VERIFICADA)**  

---

## 1. RESUMEN EJECUTIVO

Se completó la auditoría técnica, científica, documental y de seguridad sobre la versión pública de **NetDiagBench-L7**. 

El repositorio resultante garantiza:
1. **Reproducibilidad y portabilidad:** Eliminación de rutas locales de desarrollo, configuración de `.gitattributes` para terminaciones de línea LF/CRLF uniformes en Windows y Linux, y adición de generador seguro de certificados de prueba en `scripts/generate_test_certs.py`.
2. **Seguridad y privacidad:** Eliminación de llaves RSA privadas y eliminación de credenciales de evaluación humana privada, preservando los datos anonimizados, agregados y de consenso.
3. **Integridad estadística inmutable:** Todas las cifras experimentales oficiales se mantienen congeladas e idénticas a los valores reportados en la tesis de grado y la matriz canónica.

---

## 2. MATRIZ DE CONSISTENCIA CIENTÍFICA GLOBAL

La siguiente matriz presenta la verificación cruzada de cada métrica oficial a través de los diferentes componentes del sistema:

| Métrica Oficial | CSV Canónico (`resultados.csv`) | FAIR Bundle (`dataset_bundle.json`) | Motor de Evaluación (`statistical_analysis.py`) | Scorecard (`composite_score.py`) | Tesis y Matriz Oficial | Estado de Concordancia |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Población Total** | 162 corridas | 162 corridas | 162 corridas | 162 corridas | 162 corridas | ✅ 100% Idéntico |
| **Escenarios RFC** | 18 escenarios | 18 escenarios | 18 escenarios | 18 escenarios | 18 escenarios | ✅ 100% Idéntico |
| **Terna de Modelos** | 3 modelos (54 c/u) | 3 modelos | 3 modelos | 3 modelos | 3 modelos | ✅ 100% Idéntico |
| **Semillas Autorizadas** | [42, 1337, 2026] | [42, 1337, 2026] | [42, 1337, 2026] | [42, 1337, 2026] | [42, 1337, 2026] | ✅ 100% Idéntico |
| **Diagnóstico Completo Total** | **122/162 (75.31%)** | **0.7531** | **75.3%** | N/A | **122/162 (75.3%)** | ✅ 100% Idéntico |
| - GLM-4-9B-Chat | 40/54 (74.1%) | 74.07% | 74.1% | 74.07% (Elegible) | 40/54 (74.1%) | ✅ 100% Idéntico |
| - Qwen3-8B | 47/54 (87.0%) | 87.04% | 87.0% | 87.04% (Elegible) | 47/54 (87.0%) | ✅ 100% Idéntico |
| - Phi-4-mini-instruct | 35/54 (64.8%) | 64.81% | 64.8% | 64.81% (Ineligible <70%) | 35/54 (64.8%) | ✅ 100% Idéntico |
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
| **Scorecard Compuesto** | N/A | N/A | N/A | Formula 40/20/20/20 | Provisional | ✅ 100% Idéntico |
| - GLM-4-9B-Chat | N/A | N/A | 0.7323 | 0.7323 (Elegible) | 0.7323 | ✅ 100% Idéntico |
| - Qwen3-8B | N/A | N/A | 0.7217 | 0.7217 (Elegible) | 0.7217 | ✅ 100% Idéntico |
| - Phi-4-mini-instruct | N/A | N/A | 0.8012 | 0.8012 (Ineligible) | 0.8012 | ✅ 100% Idéntico |
| **Prueba de Friedman** | N/A | N/A | $\chi^2 = 6.8205$, $p = 0.03303$ | N/A | $\chi^2 = 6.8205$, $p = 0.033$ | ✅ 100% Idéntico |

---

## 3. AUDITORÍA DE SEGURIDAD Y PRIVACIDAD

1. **Llaves Privadas:** Fueron eliminadas del árbol público `certs/server.key` y `certs/expired.key`. Se suministra el script estándar `scripts/generate_test_certs.py` con permisos de ejecución y documentación para regenerar certificados TLS efímeros y auto-firmados en cualquier entorno de pruebas.
2. **Evaluación Humana y Cegado:** Se preservó el informe de concordancia, las estadísticas agregadas, las matrices de confusión y los instrumentos oficiales. Se excluyeron las claves técnicas no cegadas que contenían asociaciones directas de evaluadores con modelos.
3. **Saneamiento de Rutas:** Se verificó la ausencia total de prefijos de depuración local (`file:///C:/Users/...`).

---

## 4. VERIFICACIÓN AUTOMATIZADA

Se incorporó y validó el script de verificación automatizada:

```bash
python scripts/verify_global_consistency.py
```

Resultado de la ejecución:
```
===========================================================================
AUDITORÍA DE CONSISTENCIA CIENTÍFICA GLOBAL - NETDIAGBENCH-L7
===========================================================================
[1] Verificando dataset canónico: resultados.csv: [PASS] 100% coincidente.
[2] Verificando FAIR Dataset Bundle: dataset_bundle.json: [PASS] 100% coincidente.
[3] Verificando manifest.json: [PASS] 100% coincidente.
[4] Verificando Scorecard Compuesto (composite_score.py): [PASS] 100% coincidente.
[5] Verificando Friedman y Wilcoxon-Holm: [PASS] 100% coincidente.
===========================================================================
RESULTADO GLOBAL: TODAS LAS COMPROBACIONES PASARON EXITOSAMENTE (100% COHERENCIA)
===========================================================================
```

---

## 5. CONCLUSIÓN Y RECOMENDACIÓN

El repositorio público ubicado en `release/NetDiagBench-L7-public/` satisface plenamente los requisitos de integridad científica, seguridad de publicación, rigor metodológico y reproducibilidad de software requeridos para su distribución pública en GitHub.
