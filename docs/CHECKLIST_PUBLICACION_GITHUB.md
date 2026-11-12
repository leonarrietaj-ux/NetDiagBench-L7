# CHECKLIST DE VALIDACIÓN Y PUBLICACIÓN EN GITHUB
## NetDiagBench-L7 (Versión Pública Oficial)

Este checklist detalla los 10 puntos de verificación completados antes de publicar el repositorio en GitHub (`https://github.com/leonarrietaj-ux/NetDiagBench-L7.git`).

---

### ESTADO DE PUNTOS DE CONTROL

| # | Punto de Control | Estado | Evidencia y Verificación |
|---|---|:---:|---|
| 1 | **Aislamiento de Entornos** | ✅ COMPLETADO | Copia pública independiente en `release/NetDiagBench-L7-public/`. Repositorio original y `release_audit/` intactos. |
| 2 | **Sanitización de Secretos y Privacidad** | ✅ COMPLETADO | Llaves RSA privadas (`*.key`), credenciales de evaluación humana no ciega (`clave_RESTRINGIDA.json`, etc.) eliminadas de la copia pública. Generador de certificados de prueba incorporado en `scripts/generate_test_certs.py`. |
| 3 | **Congelación de Cifras Oficiales** | ✅ COMPLETADO | 162 corridas, 18 escenarios, 3 modelos, 3 semillas. 122/162 Diagnóstico Completo (75.3%), 71/162 Causa Raíz Estricta (43.8%), 120/162 Coincidencia Canónica (74.1%), 38/162 Evidencia Read-Only (23.5%). |
| 4 | **Armonización de Variables Estadísticas** | ✅ COMPLETADO | Separación rigurosa en contratos Pydantic, dataset CSV, bundle JSON y evaluador: `is_full_diagnosis_correct` (122/162) vs `is_root_cause_correct` / `is_root_cause_correct_strict` (71/162). |
| 5 | **FAIR Dataset Bundle y Huellas Criptográficas** | ✅ COMPLETADO | `data/benchmark_results/dataset_bundle.json` con claves explícitas (`full_diagnosis_accuracy_all_models: 0.7531`, `strict_root_cause_accuracy_all_models: 0.4383`, `fault_class_accuracy_all_models: 0.7407`, `evidence_backed_accuracy_all_models: 0.2346`) y huella SHA-256 coincidente al 100%. |
| 6 | **Trazabilidad Git y Normalización de Saltos de Línea** | ✅ COMPLETADO | `.gitattributes` configurado con LF para código, JSON, Markdown y CRLF para scripts de Windows. Registro honesto de `git_dirty=True` documentado por modificaciones del arnés durante la ejecución sin alteración de datos. |
| 7 | **Scorecard Compuesto y Umbral de Elegibilidad** | ✅ COMPLETADO | Fórmula 40/20/20/20 preservada. VRAM clasificada como `PROVISIONAL_ESTIMATED` sin redistribución espuria del 20%. GLM: 0.7323 (Elegible), Qwen: 0.7217 (Elegible), Phi: 0.8012 (No Elegible por 64.8% < 70.0%). |
| 8 | **Pruebas Automatizadas y Resiliencia** | ✅ COMPLETADO | Suite de pruebas automatizadas ejecutada y aprobada. Suite de resiliencia ante listas vacías y datos faltantes en `tests/test_report_generator_resilience.py` validada al 100%. |
| 9 | **Portabilidad de Rutas y Licenciamiento** | ✅ COMPLETADO | Eliminadas rutas absolutas locales (`file:///` y `C:\Users\...`). Archivo `LICENSE` (MIT) y `CITATION.cff` validados sin placeholders inválidos. |
| 10 | **Verificación Automatizada Global** | ✅ COMPLETADO | Script oficial `scripts/verify_global_consistency.py` ejecutado con éxito total (100% de coherencia verificada entre CSV, bundle, manifiesto, scorecard y estadística no paramétrica). |

---

### INSTRUCCIONES PARA PUBLICACIÓN EN GITHUB

Para publicar la versión pública oficial en GitHub, ejecute los siguientes comandos desde la raíz de `release/NetDiagBench-L7-public/`:

```bash
cd release/NetDiagBench-L7-public

# 1. Verificar estado limpio de Git
git status

# 2. Agregar cambios y realizar commit final de publicación
git add .
git commit -m "chore(release): preparacion definitiva y auditoria de cierre cientifico v1.0.0"

# 3. Vincular repositorio remoto oficial (si no está vinculado)
git remote add origin https://github.com/leonarrietaj-ux/NetDiagBench-L7.git

# 4. Publicar en rama principal
git branch -M main
git push -u origin main
```
