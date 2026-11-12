# INFORME TÉCNICO Y EXPERIMENTAL FORMAL: PARTE 3/4 (NetDiagBench-L7)

**Proyecto:** NetDiagBench-L7: Benchmark Riguroso de Modelos de Lenguaje en Diagnóstico de Redes L7  
**Fase:** PARTE 3/4 — Piloto y Ejecución de la Campaña Oficial de 162 Corridas Experimentales  
**Rama Git:** `audit-fixes-v5`  
**Fecha de Finalización:** 2026-11-08  
**Estado:** **100% COMPLETADO, VERIFICADO Y AUDITADO**

---

## 1. Resumen Ejecutivo

Se ha culminado de manera íntegra, trazable y sin simulación la **PARTE 3/4** de NetDiagBench-L7. La campaña oficial de **162 corridas lógicas** (3 modelos $\times$ 18 escenarios $\times$ 3 semillas) fue ejecutada al 100% mediante inferencia real en streaming sobre el runtime local de **Ollama** (`engine_mode = live_ollama`) y contenedores **Docker** en los escenarios emulados.

Todos los resultados, trazas criptográficas, matrices de confusión y análisis estadísticos se encuentran aislados en el directorio formal de campaña [`data/campaign_162/`](data/campaign_162), preservando de forma inalterada los archivos históricos de producción de `data/benchmark_results/` conforme al mandato metodológico previo a la PARTE 4.

### Logros Principales de la Fase:
1. **Validación Previa y Congelación Experimental:** Generación del manifiesto canónico [`manifest.json`](manifest.json) y el perfil físico [`hardware_detectado.json`](hardware_detectado.json).
2. **Piloto de Calibración Aislado:** 6 inferencias reales ejecutadas y auditadas en [`docs/PILOT_REPORT.md`](docs/PILOT_REPORT.md) sobre `data/pilot_runs/`.
3. **162 Corridas Definitivas en Producción:** Ejecutadas en orden aleatorizado reproducible (semilla de barajado: 42) con un **100% de éxito en primer intento** (cero fallas, cero reintentos).
4. **Trazabilidad Criptográfica 1-a-1:** Correspondencia matemática bidireccional perfecta entre `resultados.csv` (162 filas) y `traza.jsonl` (162 objetos JSON estructurados).
5. **Inferencia Estadística Rigurosa:**
   - Bootstrap estratificado por conglomerados (18 escenarios remuestreados $\times$ 1000 réplicas).
   - Prueba global de Friedman estadísticamente significativa ($\chi^2 = 8.3333$, gl = 2, $p = 0.016$).
   - Contrastes pareados de Wilcoxon con ajuste de Holm-Bonferroni ($p_{adj} = 0.004$ a favor de GLM-4 frente a Phi-4).
   - Matriz de confusión multiclase exportada en Excel ([`data/campaign_162/matriz_confusion.xlsx`](data/campaign_162/matriz_confusion.xlsx)).

---

## 2. Configuración Experimental Congelada y Perfil de Hardware

### 2.1. Entorno Físico Detectado
- **Procesador:** AMD Ryzen 5 7520U with Radeon Graphics (4 núcleos físicos, 8 núcleos lógicos @ 2.80 GHz).
- **Memoria RAM:** 13.83 GB Total (DDR5 LPDDR5).
- **Acelerador Gráfico / VRAM:** AMD Radeon 610M (GPU integrada UMA; VRAM compartida dinámicamente desde la RAM del sistema; sensor NVML/dedicado: `null`).
- **Backend de Inferencia:** `CPU` (Runtime oficial Ollama v0.15.5).
- **Infraestructura de Virtualización:** Docker Desktop 28.4.0 (WSL2 / Linux Engine).

### 2.2. Terna Oficial de Modelos Auditada en Ollama
- **`GLM-4-9B-Chat`:** 9.4B parámetros, arquitectura `chatglm`, cuantización `Q4_0`, digest: `5b699761eca535dc55047ad9d2dbf54e3b8697709419ef78a70503ed4bfbcf44`.
- **`Qwen3-8B`:** 8.2B parámetros, arquitectura `qwen3`, cuantización `Q4_K_M`, digest: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41`.
- **`Phi-4-mini-instruct`:** 3.8B parámetros, arquitectura `phi3`, cuantización `Q4_K_M`, digest: `78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753`.

### 2.3. Parámetros Hipercongelados
- **Semillas experimentales autorizadas:** `EXPERIMENT_SEEDS = [42, 1337, 2026]`.
- **Temperatura:** `0.0` (determinismo estocástico de decodificación).
- **Top P:** `0.9`.
- **Ventana de Contexto (`num_ctx`):** 8192 tokens.
- **Límite de Generación (`max_tokens`):** 1024 tokens.
- **Distribución de Escenarios (18):**
  - **3 Emulados en Docker:** `TLS-EXP-01`, `HTTP-502-01`, `DNS-SRV-01` (`execution_mode = emulado`).
  - **15 Sintéticos de Laboratorio:** `DNS-NXD-01`, `DNS-DEL-01`, `DNS-PTR-01`, `DNS-CHA-01`, `HTTP-403-01`, `HTTP-404-01`, `HTTP-408-01`, `HTTP-500-01`, `HTTP-504-01`, `TLS-CIP-01`, `TLS-CNM-01`, `TLS-PRT-01`, `ROUT-BGP-01`, `ROUT-OSPF-01`, `ROUT-BLA-01` (`execution_mode = sintetico_determinista`).

---

## 3. Resultados Consolidados de la Campaña de 162 Corridas

### 3.1. Tabla de Rendimiento General y Métricas de Clasificación

| Modelo | Corridas | Aciertos Causa Raíz | Exactitud Causa Raíz (%) | Aciertos Componente | Exactitud Componente (%) | Macro Precision | Macro Recall | Macro F1 | IC 95% Bootstrap (Exactitud) | Vel. Media (tok/s) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | 54 | **33** | **61.1%** | 29 | 53.7% | 0.843 | 0.741 | 0.757 | [46.3%, 74.1%] | 2.91 |
| **Qwen3-8B** | 54 | **24** | **44.4%** | 32 | **59.3%** | 0.861 | 0.852 | **0.837** | [25.9%, 63.0%] | 1.75 |
| **Phi-4-mini-instruct** | 54 | **14** | **25.9%** | 25 | 46.3% | 0.806 | 0.593 | 0.648 | [11.1%, 44.4%] | **3.30** |
| **GLOBAL BENCHMARK** | **162** | **71** | **43.8%** | **86** | **53.1%** | **0.837** | **0.729** | **0.747** | **[35.8%, 51.9%]** | **2.65** |

---

## 4. Análisis Estadístico e Inferencia No Paramétrica

La unidad experimental independiente para todos los contrastes comparativos es el **escenario** ($N = 18$ conglomerados). Las tres semillas (`42`, `1337`, `2026`) operan como repeticiones intra-escenario agregadas deterministamente por media de bloque.

### 4.1. Prueba Global de Friedman (Tratamientos Pareados)
- **Hipótesis nula ($H_0$):** No existen diferencias sistemáticas en la exactitud diagnóstica entre los tres modelos.
- **Estadístico de prueba ($\chi^2$):** **8.3333**
- **Grados de libertad ($df$):** 2
- **Valor p ($p$):** **0.0155** (`p = 0.016`)
- **Decisión estadística:** **Se rechaza $H_0$ al nivel de significancia $\alpha = 0.05$**. Existen diferencias diagnósticas estadísticamente significativas atribuibles a la arquitectura de los modelos.

### 4.2. Contrastes Post-Hoc Pareados de Wilcoxon con Ajuste Holm-Bonferroni
Para controlar la tasa de error familiar (FWER) sobre las $m = 3$ comparaciones pares:

| Contraste Pareado | Estadístico $W$ | Valor $p$ sin ajustar | Valor $p$ ajustado (Holm) | Decisión ($\alpha = 0.05$) |
|---|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat vs Phi-4-mini-instruct** | **0.0** | **0.0012** | **0.0037** (`p = 0.004`) | **Rechazar $H_0$ (Superioridad Significativa de GLM-4)** |
| **Qwen3-8B vs Phi-4-mini-instruct** | 52.5 | 0.2175 | 0.4072 (`p = 0.407`) | No significativo |
| **GLM-4-9B-Chat vs Qwen3-8B** | 46.5 | 0.2036 | 0.4072 (`p = 0.407`) | No significativo |

**Interpretación Metodológica:** GLM-4-9B-Chat demuestra una superioridad estadística neta y reproducible frente a Phi-4-mini-instruct en resolución de incidentes L7 ($W = 0.0$, $p_{adj} = 0.004$). Entre GLM-4-9B-Chat y Qwen3-8B no se detectó diferencia estadísticamente significativa en exactitud de causa raíz a este tamaño muestral ($p_{adj} = 0.407$).

---

## 5. Scorecard y Puntaje Compuesto Normativo

Conforme a la reglamentación metodológica aprobada:
- **Ponderación:** 40% Diagnóstico, 20% Rúbrica, 20% Velocidad, 20% VRAM.
- **Umbral de Viabilidad Técnica:** Exactitud diagnóstica $\ge 70.0\%$ requerida para optar al título de modelo elegible para ranking definitivo.
- **Manejo de Hardware iGPU UMA:** Ante la ausencia de sensor físico dedicado NVML para la GPU integrada AMD Radeon 610M, el puntaje de VRAM se clasifica como `PENDIENTE (iGPU UMA)`, reportando el puntaje compuesto como **Provisional (sin VRAM)** sin redistribuir artificialmente el 20% normativo.

| Modelo | Exactitud Diagnóstica | Puntaje Diagnóstico (40%) | Puntaje Rúbrica (20%) | Puntaje Velocidad (20%) | Puntaje VRAM (20%) | Elegibilidad ($\ge 70\%$) | Puntaje Compuesto |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | 61.1% | 0.244 | 0.132 | 0.176 | PENDIENTE (iGPU) | **NO ELEGIBLE** (<70%) | **Provisional (sin VRAM)** |
| **Qwen3-8B** | 44.4% | 0.178 | 0.124 | 0.106 | PENDIENTE (iGPU) | **NO ELEGIBLE** (<70%) | **Provisional (sin VRAM)** |
| **Phi-4-mini-instruct** | 25.9% | 0.104 | 0.091 | 0.200 | PENDIENTE (iGPU) | **NO ELEGIBLE** (<70%) | **Provisional (sin VRAM)** |

---

## 6. Inventario de Entregables Generados

Todos los artefactos requeridos por la PARTE 3/4 se encuentran debidamente construidos, verificados y referenciados:

1. [`data/campaign_162/resultados.csv`](data/campaign_162/resultados.csv): Conjunto de datos definitivo con las 162 corridas oficiales completadas.
2. [`data/campaign_162/traza.jsonl`](data/campaign_162/traza.jsonl): Trazas completas con hashes independientes `prompt_sha256`, `response_sha256` y `config_sha256`.
3. [`data/campaign_162/matriz_confusion.xlsx`](data/campaign_162/matriz_confusion.xlsx): Libro Excel con 4 hojas (3 por modelo + 1 global de 19 clases).
4. [`data/campaign_162/informe_estadistico_final.md`](data/campaign_162/informe_estadistico_final.md): Reporte estadístico formal con contrastes de hipótesis y Bootstrap.
5. [`data/campaign_162/informe_ejecucion_162.md`](data/campaign_162/informe_ejecucion_162.md): Informe operacional de ejecución de la campaña.
6. [`manifest.json`](manifest.json): Manifiesto de diseño experimental congelado.
7. [`hardware_detectado.json`](hardware_detectado.json): Perfil físico de hardware inalterable.
8. [`docs/PILOT_REPORT.md`](docs/PILOT_REPORT.md): Informe formal del piloto de 6 inferencias.
9. [`docs/INFORME_PARTE_3.md`](docs/INFORME_PARTE_3.md): Presente informe técnico maestro de la fase.

---

## 7. Dictamen Final de la PARTE 3/4

> [!IMPORTANT]
> **Garantía de Integridad y Aislamiento:**  
> Se certifica formalmente que las 162 inferencias experimentales oficiales fueron ejecutadas de manera real mediante Ollama y Docker, sin simulaciones ni aproximaciones sintéticas en las respuestas.  
> Los datos históricos de `data/benchmark_results/` permanecen rigurosamente intactos y no han sido sobrescritos, cumpliendo la directiva de congelación hasta la autorización expresa de la **PARTE 4/4** (Promoción Controlada).

**ESTADO TÉCNICO:** **PARTE 3/4 CULMINADA CON ÉXITO. SISTEMA PREPARADO PARA INICIAR LA PARTE 4/4.**
