# CHECKLIST DE VALIDACIÓN Y PUBLICACIÓN EN GITHUB
## NetDiagBench-L7 (Versión Pública Oficial v1.0.0)

Este checklist detalla los 10 puntos de control completados y auditados antes de la publicación final en GitHub (`https://github.com/leonarrietaj-ux/NetDiagBench-L7.git`).

---

### ESTADO DE PUNTOS DE CONTROL

| # | Punto de Control | Estado | Evidencia y Verificación |
|---|---|:---:|---|
| 1 | **Aislamiento de Entornos** | ✅ COMPLETADO | Copia pública independiente en `release/NetDiagBench-L7-public/`. Repositorio original y `release_audit/` intactos. |
| 2 | **Sanitización de Secretos y Privacidad** | ✅ COMPLETADO | Llaves RSA privadas (`*.key`), archivos de sesión confidencial (`CURRENT_SESSION.txt`, `SESION_KIT_CASO2/`) y corridas transitorias eliminados físicamente. Generador de certificados de prueba incorporado en `scripts/generate_test_certs.py`. |
| 3 | **Congelación de Cifras Oficiales** | ✅ COMPLETADO | 162 corridas, 18 escenarios, 3 modelos, 3 semillas. 122/162 Diagnóstico Completo (75.3%), 71/162 Causa Raíz Estricta (43.8%), 120/162 Coincidencia Canónica (74.1%), 38/162 Evidencia Read-Only (23.5%). |
| 4 | **Armonización de Variables Estadísticas** | ✅ COMPLETADO | Separación rigurosa en contratos Pydantic, dataset CSV, bundle JSON y evaluador: `is_full_diagnosis_correct` (122/162) vs `is_root_cause_correct` / `is_root_cause_correct_strict` (71/162). |
| 5 | **FAIR Dataset Bundle y Huellas Criptográficas** | ✅ COMPLETADO | `data/benchmark_results/dataset_bundle.json` con claves explícitas (`full_diagnosis_accuracy_all_models: 0.7531`, `strict_root_cause_accuracy_all_models: 0.4383`, `fault_class_accuracy_all_models: 0.7407`, `evidence_backed_accuracy_all_models: 0.2346`) y huella SHA-256 coincidente al 100%. Manifiesto criptográfico en `data/benchmark_results/MANIFEST_PUBLICACION_SHA256.json`. |
| 6 | **Trazabilidad Git y Normalización de Saltos de Línea** | ✅ COMPLETADO | `.gitattributes` configurado con LF para código, JSON, Markdown y CRLF para scripts de Windows. Registro honesto de `git_dirty=True` documentado por modificaciones del arnés durante la ejecución sin alteración de datos. |
| 7 | **Scorecard Compuesto y Umbral de Elegibilidad** | ✅ COMPLETADO | Fórmula 40/20/20/20 preservada. VRAM clasificada como `PROVISIONAL_ESTIMATED` sin redistribución espuria del 20%. GLM: 0.7323 (Elegible), Qwen: 0.7217 (Elegible), Phi: 0.8012 (No Elegible por 64.8% < 70.0%). |
| 8 | **Pruebas Automatizadas y Resiliencia** | ✅ COMPLETADO | Suite de pruebas de 348 ítems con 339 aprobadas, 0 fallas y 7 omitidas justificadas. Verificación global `verify_global_consistency.py` aprobada con 100% de coherencia. |
| 9 | **Portabilidad de Rutas y Licenciamiento** | ✅ COMPLETADO | Archivo de tesis renombrado a `docs/DOCUMENTO_FINAL_TESIS_GRADO.md` para evitar errores de longitud de ruta. Rutas absolutas locales eliminadas. Licencia MIT y `CITATION.cff` validados. |
| 10 | **Terna Oficial Estricta (3 Modelos)** | ✅ COMPLETADO | Eliminación en interfaz web, backend y configuración de cualquier modelo residual o duplicado (`Qwen3-8B`, `GLM-4-9B-Chat`, `Phi-4-mini-instruct`). |

---

### INSTRUCCIONES MANUALES PARA EL USUARIO PARA PUBLICAR EN GITHUB

Para realizar la publicación en GitHub, ejecute los siguientes comandos en su terminal:

```bash
cd release/NetDiagBench-L7-public

# 1. Verificar estado limpio del repositorio
git status

# 2. Agregar todos los archivos preparados
git add .

# 3. Realizar el commit de cierre de release
git commit -m "chore(release): cierre de auditoria y preparacion publica v1.0.0"

# 4. Vincular el repositorio remoto oficial (si no estuviese configurado)
git remote set-url origin https://github.com/leonarrietaj-ux/NetDiagBench-L7.git

# 5. Publicar en GitHub
git branch -M main
git push -u origin main
```
