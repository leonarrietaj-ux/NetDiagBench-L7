# NetDiagBench-L7: Guía de Reproducibilidad y Manual de Operación

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Layer 7 sobre IP  
**Versión:** 1.0.4 | **Fecha:** Noviembre de 2026  

Esta guía proporciona las instrucciones exhaustivas para que investigadores independientes puedan verificar y reproducir la totalidad de los experimentos, diagnósticos agénticos y matrices de evaluación del framework **NetDiagBench-L7**.

---

## 1. Requisitos del Entorno

- **Sistema Operativo:** Windows 10/11 (64-bit) o GNU/Linux (Ubuntu 22.04 / 24.04 LTS).
- **Python:** Versión ≥ 3.11 (validado en Python 3.14.4).
- **Memoria RAM:** Mínimo 8 GB (Recomendado 16 GB). Motor RAG de recuperación léxica acotada mediante BM25 (no vectorial, $\le 0.05\text{ MB}$ RAM).
- **Aceleración Gráfica (Opcional):** Tarjeta gráfica NVIDIA (CUDA) o AMD (ROCm) con 8 GB VRAM. En ausencia de GPU dedicada o de servicio Ollama local, el framework conmuta automáticamente a su simulador determinista de alta fidelidad, garantizando reproducibilidad sin requerir descargas pesadas de pesos GGUF.
- **Servicio Ollama (Para inferencia local real):** Versión $\ge 0.5$, ejecutando modelos cuantizados a `Q4_K_M` (`glm-4-9b-chat`, `qwen3-8b`, `phi-4-mini-instruct`, o modelos dinámicos registrados).

---

## 2. Instalación y Puesta en Marcha

Desde la raíz del repositorio (`NetDiagBench-L7`):

```powershell
# 1. Crear el entorno virtual de Python
python -m venv .venv

# 2. Activar el entorno virtual
# En Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# En Linux / macOS Bash:
# source .venv/bin/activate

# 3. Instalar el paquete en modo editable y dependencias principales
pip install -e . --no-deps
pip install -r requirements.txt
pip install -e . --no-deps
```

---

## 3. Verificación Automatizada (Suite de Pruebas Pytest)

Para comprobar la integridad de las ocho capas arquitectónicas y los contratos de datos:

```powershell
.venv\Scripts\pytest.exe -v tests/
```

**Resultado esperado:**
- **225 pruebas unitarias y de integración ejecutadas con 100% de éxito (225 passed)**.
- Verificación exhaustiva de:
  1. Contratos Pydantic de entrada/salida y esquema tabular de 42 columnas.
  2. Catálogo de 18 escenarios de falla L7 (DNS, HTTP/Web, Gateway y TLS).
  3. Preprocesamiento y minería semántica con Drain3 v0.9.11.
  4. Presupuesto de memoria RAG ($\le 0.05\text{ MB}$ RAM frente al tope de $0.45\text{ GB}$).
  5. Orquestación agéntica de solo lectura con persistencia en RAM (LangGraph MemorySaver).
  6. Extracción estricta del diagnóstico derivada exclusivamente de la respuesta del modelo (cero fuga de verdad terreno).
  7. Traducción técnica universal al español (`src/core/translator.py`).
  8. Ingesta dinámica de modelos de Ollama clasificados en `model_group = "adicional"`.
  9. Interfaz CLI Typer y API web FastAPI con modo de alto contraste claro/oscuro y streaming SSE.
  10. Suite estadística SciPy (Spearman, Pearson, Kruskal-Wallis, Bootstrap 95%, $d$ de Cohen).
  11. Exportadores a PDF (ReportLab), Excel multioja (.xlsx) y CSV.

### 3.1. Verificación de Seguridad y Guardrails Defensivos (Hardening)

Para certificar la robustez del sistema frente a riesgos de seguridad (inyección de argumentos, SSRF multicloud, sanitización de entradas y cabeceras OWASP):

```powershell
.venv\Scripts\pytest.exe -v tests/test_security_audit.py
```

**Cobertura de pruebas de seguridad:**
1. `test_security_headers_middleware`: Cabeceras OWASP en FastAPI (`Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`).
2. `test_ollama_model_tag_validation`: Prevención de inyección de opciones/banderas CLI en `POST /api/models/pull` (CWE-88).
3. `test_read_only_tools_ssrf_blocking`: Bloqueo estricto anti-SSRF hacia metadatos de proveedores cloud (AWS IPv4/IPv6, Alibaba Cloud, GCP, Tencent Cloud, Kubernetes CoreDNS) y banderas mutativas (`-X POST`, `-d`, etc.).
4. `test_diagnose_request_validation`: Validación estricta de límites y expresiones regulares en contratos Pydantic de la API.

Para la especificación exhaustiva de seguridad, consulte [`SEGURIDAD_SISTEMA.md`](SEGURIDAD_SISTEMA.md).

---

## 4. Manual de la Interfaz de Línea de Comandos (`benchapp`)

El comando `benchapp` expone subcomandos alineados con los objetivos del benchmark:

### 4.1. Listar el Catálogo de Escenarios L7
```powershell
.venv\Scripts\benchapp.exe list-scenarios
```
Despliega la tabla con los 18 escenarios clasificados por categoría (`DNS`, `HTTP_WEB`, `API_GATEWAY`, `TLS`), componente de red afectado y causa técnica esperada.

### 4.2. Listar la Terna de Modelos de Lenguaje
```powershell
.venv\Scripts\benchapp.exe list-models
```
Detalla la terna adoptada: `GLM-4-9B-Chat`, `Qwen3-8B` y `Phi-4-mini-instruct`, con su esquema de cuantización `Q4_K_M`, tamaño de contexto y requisitos de VRAM.

### 4.3. Consulta Semántica al Motor RAG Acotado
```powershell
.venv\Scripts\benchapp.exe rag-query "cadena de certificados TLS intermedia" --top-k 3
```
Realiza una búsqueda BM25 acotada sobre los RFCs normativos (RFC 1035, RFC 9110, RFC 8446, RFC 5280, RFC 6066) y los procedimientos operativos estándar (SOPs), mostrando la huella de memoria RAM utilizada ($\le 0.05\text{ MB}$).

### 4.4. Ejecución de un Diagnóstico Agéntico Individual
```powershell
.venv\Scripts\benchapp.exe run-scenario TLS-CHN-01 --model qwen3-8b --seed 42
```
Ejecuta el ciclo de orquestación agéntico completo:
1. Ingesta de registros y telemetría (Capa 1 y Capa 2).
2. Recuperación de fragmentos de norma (Capa 3).
3. Invocación de herramientas de solo lectura (`dig`, `curl`, `openssl`) por el agente (Capa 5).
4. Emisión del veredicto estructurado, extracción estricta del modelo y traducción universal al español.
5. Generación de los artefactos `.json` y `.md` en la carpeta `data/runs/`.

### 4.5. Ejecución del Arnés de Benchmark Automatizado (OE4)
```powershell
# Modo rápido de verificación (1 repetición, 1 semilla = 54 corridas):
.venv\Scripts\benchapp.exe run-benchmark --quick

# Modo completo con protocolo de 3 semillas deterministas (162 corridas):
.venv\Scripts\benchapp.exe run-benchmark --seeds 42,1337,2026 --repetitions 1
```
Al finalizar, el arnés genera automáticamente:
- El dataset completo en formato tabular: `data/benchmark_results/resultados.csv`.
- El informe técnico comparativo con la matriz multidimensional y análisis de compromiso: `data/benchmark_results/resultados_resumen.md`.
- El reporte de significancia estadística y correlación bivariada: `data/benchmark_results/analisis_correlacional.md`.

### 4.6. Exportación de Datos a Excel (.xlsx) y Reportes a PDF
```powershell
# Exportar libro Excel multioja (10 hojas con formato y fórmulas):
.venv\Scripts\benchapp.exe export-excel

# Exportar informe consolidado unificado a PDF:
.venv\Scripts\benchapp.exe export-pdf --type all

# Exportar informe técnico comparativo OE4 a PDF:
.venv\Scripts\benchapp.exe export-pdf --type comparative

# Exportar análisis correlacional Tarea 4.1.2 a PDF:
.venv\Scripts\benchapp.exe export-pdf --type correlation
```

---

## 5. Lanzamiento del Dashboard Web Interactivo (Capa 6)

Para la sustentación en vivo ante el jurado calificador:

```powershell
.venv\Scripts\benchapp.exe serve-dashboard --host 127.0.0.1 --port 8000
```

Abra el navegador en `http://127.0.0.1:8000`:
- **Selector de Escenario:** Permite elegir cualquiera de los 18 escenarios y visualizar la ficha de Ground Truth en tiempo real.
- **Selector de Modelo:** Permite alternar entre GLM-4-9B-Chat, Qwen3-8B, Phi-4-mini-instruct, o modelos dinámicos registrados.
- **Botón "Ejecutar Diagnóstico":** Dispara el ciclo en vivo y grafica las tarjetas de telemetría (TTFT, velocidad tok/s, VRAM pico y latencia total), el veredicto estructurado (traducido al español y extraído sin fugas), la traza de herramientas de red y los fragmentos RAG recuperados.
- **Botón "Ver Informe Benchmark (OE4)":** Despliega el informe comparativo consolidado con la matriz multidimensional de las 162 corridas directamente en el navegador.
- **Modo Claro / Oscuro de Alto Contraste:** Permite conmutar la apariencia visual garantizando contraste óptimo y legibilidad completa de todos los elementos interactivos y bitácoras.

---

## 6. Estructura de Salidas y Almacenamiento

- `data/runs/`: Contratos de diagnóstico emitidos en formato JSON y Markdown por cada escenario ejecutado.
- `data/benchmark_results/resultados.csv`: Registro granular de cada corrida con 99 columnas estandarizadas de datos y trazabilidad experimental (versión canónica publicada que expande el núcleo inicial de 42 columnas de telemetría hacia la totalidad de dimensiones de evaluación humana E1/E2/E3, adjudicaciones, telemetría extendida y hash normativo del evaluador SHA-256 `b26a394b7fb3`, con `1f8c1a7e3a9d` correspondiente a la calibración preliminar histórica).
- `data/benchmark_results/resultados_resumen.md`: Informe final consolidado que sustenta las conclusiones del Objetivo Específico 4.
- `data/benchmark_results/analisis_correlacional.md`: Reporte estadístico formal con correlaciones de Pearson, Spearman, Kruskal-Wallis, Bootstrap 95% y tamaño de efecto ($d$ de Cohen).


---

## 7. Reproducibilidad de la Evaluación Humana (Capa 8)

El protocolo de validación humana opera bajo un diseño experimental de doble ciego independiente con 54 diagnósticos de la terna oficial evaluados por los expertos E1 y E2 (108 registros en total), con arbitraje dirimente por el experto E3:

1. **Datos Originales Preservados:** Los registros de evaluación humana reposan en `data/human_eval/` (`evaluaciones_adjudicadas.csv`, `concordancia_resultados.csv`, `informe_concordancia.md`).
2. **Autenticidad Metodológica:** Las evaluaciones corresponden a calificaciones emitidas por evaluadores independientes sobre los 54 casos estratificados.
3. **Cálculo de Concordancia:**
   ```powershell
   .venv\Scripts\pytest.exe tests/test_layer8_human_eval.py -v
   ```
   Valida el acuerdo exacto (74.1% a 83.3%), Kappa de Cohen cuadrático por criterio (0.7327 a 0.8905), ICC(2,1) = 0.7049 [0.5539, 0.8155] (conforme al informe oficial `data/human_eval/informe_concordancia.md`, donde 0.7860 correspondió a la cohorte piloto preliminar).
4. **Matrices de Concordancia:**
   - Matriz $N = 41$: Casos con consenso unánime sin dirimente ($\text{TP} = 31, \text{FP} = 1, \text{FN} = 0, \text{TN} = 9$, Exactitud = 97.56%, $\kappa = 0.9316$).
   - Matriz $N = 54$: Muestra completa tras la dirimencia de E3 ($\text{TP} = 38, \text{FP} = 1, \text{FN} = 0, \text{TN} = 15, \kappa = 0.955$).

---

## 8. Resultados Oficiales Congelados de la Campaña (162 Corridas)

Para contrastar cualquier réplica experimental con la campaña oficial de referencia (18 escenarios x 3 modelos x 3 semillas deterministas `[42, 1337, 2026]`):

| Métrica Oficial Congelada | GLM-4-9B-Chat | Qwen3-8B | Phi-4-mini-instruct | TOTAL / Promedio |
|---|---:|---:|---:|---:|
| **Aciertos Diagnósticos Completos (`full_text`)** | 40 / 54 (74.1%) | 47 / 54 (87.0%) | 35 / 54 (64.8%) | **122 / 162 (75.3%)** |
| **Aciertos Estrictos (`root_cause`)** | 33 / 54 (61.1%) | 24 / 54 (44.4%) | 14 / 54 (25.9%) | **71 / 162 (43.8%)** |
| **Coincidencia de Clase Canónica (`fault_class`)** | 40 / 54 (74.1%) | 47 / 54 (87.0%) | 33 / 54 (61.1%) | **120 / 162 (74.1%)** |
| **Rúbrica Humana Adjudicada (0 a 5)** | 4.13 / 5.0 | 4.07 / 5.0 | 3.55 / 5.0 | **3.92 / 5.0** |
| **Velocidad de Decodificación (tok/s)** | 2.91 tok/s | 1.75 tok/s | 3.29 tok/s | **2.65 tok/s** |
| **VRAM Declarada/Estimada (`configs/models.yaml`)** | 5.9 GB | 5.5 GB | 2.8 GB | Min: 2.8 GB |
| **Puntaje VRAM Ponderado (20%)** | 0.0949 | 0.1018 | 0.2000 | $0.20 \times \frac{2.8}{\text{VRAM}}$ |
| **Puntaje Compuesto Provisional** | 0.7323 | 0.7217 | 0.8012 | Viables: GLM, Qwen |

- **Prueba de Friedman:** $\chi^2 = 6.8205$, $p = 0.0330$ (estadísticamente significativa a $\alpha = 0.05$).
- **Post-hoc Wilcoxon con corrección Holm:** Qwen3-8B vs Phi-4-mini ($p = 0.041$), GLM-4-9B vs Qwen3-8B ($p = 0.053$), GLM-4-9B vs Phi-4-mini ($p = 0.370$).

---

## 9. Trazabilidad Experimental y Hash de Compromiso Criptográfico

Cada uno de los 162 contratos de diagnóstico oficiales (`data/campaign_162/runs/*/*_diagnostico.json`) y el resumen ejecutivo de la terna (`data/benchmark_results/informe_modelos_seleccionados.json`) registran el commit canónico de ejecución:

```json
"git_commit_hash": "952a628e13ba8bbbe60a5c5c65a34d05becb764a"
```

### Origen y Validación del Commit Histórico
- **Entorno de congelación original:** El hash `952a628e13ba8bbbe60a5c5c65a34d05becb764a` corresponde al commit de cierre metodológico del arnés en el repositorio experimental institucional (`audit-fixes-v5`), donde se selló la campaña de las 162 corridas tras completar la auditoría estricta de reproducibilidad.
- **Transición a la distribución pública:** Para la liberación pública e independiente de `NetDiagBench-L7`, se estructuró un árbol Git limpio y anonimizado en la rama `main` de GitHub. La totalidad de los 162 artefactos JSON, trazas JSONL y tablas CSV fueron transferidos de manera íntegra, conservando exactamente los mismos bytes, marcas temporales y hashes criptográficos SHA-256 certificados en `data/benchmark_results/MANIFEST_PUBLICACION_SHA256.json`.
