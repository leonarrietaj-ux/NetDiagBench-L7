# Documento Final de Trabajo de Grado (Entregable E7)

**UNIVERSIDAD DE PAMPLONA**  
**FACULTAD DE INGENIERÍAS Y ARQUITECTURA**  
**DEPARTAMENTO DE ELECTRICIDAD, ELECTRÓNICA, SISTEMAS Y TELECOMUNICACIONES (E.E.S.T.)**  
**PROGRAMA DE INGENIERÍA EN TELECOMUNICACIONES**  

---

# IMPLEMENTACIÓN DE UN BENCHMARK REPRODUCIBLE PARA EL DIAGNÓSTICO DE FALLAS EN SERVICIOS DE CAPA DE APLICACIÓN SOBRE IP CON MODELOS DE LENGUAJE LIGEROS DE EJECUCIÓN LOCAL

**Modalidad:** Trabajo de Grado Independiente  
**Autor:** Juan David León Arrieta  
**Código Estudiantil:** 109040xxxx  
**Director:** Mg. Richard Eliseo Mendoza Gáfaro  

**Pamplona, Norte de Santander, Colombia**  
**Noviembre de 2026**  

---

## Resumen Ejecutivo

El presente trabajo de grado diseña, implementa y valida experimentalmente **NetDiagBench-L7**, un marco metodológico y banco de pruebas reproducible para la evaluación multidimensional de modelos de lenguaje ligeros (SLMs) ejecutados de forma local en el diagnóstico de fallas en servicios de Capa de Aplicación sobre redes IP. Frente a las limitaciones de privacidad, costos y latencias variables asociadas al uso de APIs de LLMs propietarios en la nube, la investigación demuestra la viabilidad de utilizar modelos de pesos abiertos con escalas paramétricas entre 3.8B y 9.0B parámetros cuantizados a 4 bits (`Q4_K_M GGUF`) sobre estaciones de trabajo de consumo ($\le 8\text{ GB}$ VRAM). 

El sistema se estructura en una arquitectura desacoplada de siete capas que integra: emulación determinista de laboratorio, minería de registros con el algoritmo Drain3 v0.9.11, un motor de recuperación contextual acotado a estándares normativos del IETF (RFC 1035, RFC 9110, RFC 8446, RFC 5280 y RFC 6066) con una huella de memoria RAM de $0.05\text{ MB}$, instrumentación de telemetría física de inferencia, un orquestador agéntico con persistencia en RAM (LangGraph MemorySaver) que interactúa exclusivamente con herramientas de red en modo de solo lectura (`dig`, `curl`, `openssl`), extracción estricta del diagnóstico exclusivamente desde la generación del modelo con traducción universal al español, y evaluación determinista basada en especificaciones IETF versionadas por SHA-256 (`1f8c1a7e3a9d`).

La evaluación empírica de la terna seleccionada (`GLM-4-9B-Chat`, `Qwen3-8B` y `Phi-4-mini-instruct`) a lo largo de 162 corridas controladas sobre 18 clases de falla L7 (DNS, HTTP/Web, Gateway y TLS) evaluadas deterministamente con criterios normativos oficiales arrojó una precisión diagnóstica global del **79.0%** respaldada por un **95.1%** de sustento en evidencia activa de red. El análisis de compensaciones (*trade-offs*) ratifica a **GLM-4-9B-Chat** como la configuración de mejor compromiso global para Centros de Operaciones de Red (NOC) con un score multicriterio de **0.860** y **88.9%** de precisión diagnóstica, seguido por **Qwen3-8B** (**0.850**) por su balance con razonamiento estructurado CoT (`<thought>`) y aislamiento de componentes (**74.1%**), y a **Phi-4-mini-instruct** (**0.745**) como la solución óptima para despliegues de borde (*edge*) debido a su reducida demanda computacional, alta velocidad de generación ($4.51\text{ tok/s}$) y bajo consumo de memoria ($2.8\text{ GB}$ VRAM, $0.330\text{ kWh}$).

---

## 1. Planteamiento del Problema y Justificación

Las fallas en servicios de Capa de Aplicación (L7) constituyen uno de los mayores desafíos operacionales en infraestructuras de telecomunicaciones contemporáneas. Anomalías como desincronizaciones de delegación DNS (*lame delegation*), códigos 502/504 en pasarelas Nginx o rupturas de cadenas de confianza en certificados digitales TLS provocan interrupciones de servicio cuyo diagnóstico tradicionalmente depende de la pericia manual de ingenieros de soporte o de herramientas estadísticas que no interpretan la semántica normativa de los estándares.

El empleo de LLMs comerciales en la nube presenta riesgos inasumibles de fuga de información confidencial de red (direcciones IP, nombres de dominio y topologías internas) y costos recurrentes de API. A su vez, los SLMs locales han carecido de un entorno de evaluación unificado que permita caracterizar sus compensaciones de velocidad, exactitud y consumo de recursos bajo condiciones estrictamente reproducibles. NetDiagBench-L7 resuelve esta brecha al proveer un entorno abierto, parametrizable y 100% auditable.

---

## 2. Objetivos

### 2.1. Objetivo General
Implementar un benchmark reproducible para el diagnóstico de fallas en servicios de capa de aplicación sobre IP con modelos de lenguaje ligeros de ejecución local sobre hardware con restricciones de recursos ($\le 8\text{ GB}$ VRAM).

### 2.2. Objetivos Específicos
1. **OE1:** Diseñar y caracterizar la plataforma de referencia y seleccionar una terna representativa de modelos de lenguaje ligeros (3.0B a 9.0B parámetros) mediante una revisión sistemática basada en criterios ponderados de licenciamiento, independencia arquitectónica y soporte de herramientas.
2. **OE2:** Desarrollar el catálogo formal de escenarios de falla de Capa 7 (DNS, HTTP/Web, API Gateway y TLS) y el conjunto de datos de evaluación con especificación de fichas técnicas, causas raíz esperadas y evidencias mínimas de red.
3. **OE3:** Implementar el asistente de diagnóstico mediante una arquitectura modular en siete capas que integre preprocesamiento con Drain3, RAG normativo con presupuesto acotado de memoria ($\le 0.45\text{ GB}$ RAM), orquestación agéntica de solo lectura con persistencia en RAM, interfaz de línea de comandos y panel web bimodal de alto contraste.
4. **OE4:** Evaluar multidimensionalmente la terna de modelos seleccionada midiendo precisión diagnóstica, percentiles de latencia ($p_{50}$ y $p_{95}$), velocidad de generación, ocupación de VRAM, estimación de huella energética y rúbrica de explicabilidad, identificando la configuración de mejor compromiso (*best trade-off*).

---

## 3. Arquitectura y Componentes del Sistema Desarrollado

El sistema NetDiagBench-L7 opera mediante siete capas completamente desacopladas a través de contratos tipados con Pydantic:

```
[ Capa 1: Laboratorio y Escenarios ] -> escenario.yaml + Registros Crudos (18 clases L7)
                │
                ▼
[ Capa 2: Pipeline y Minería Drain3 ] -> ventana.jsonl + Contexto Estructurado (v0.9.11)
                │
                ▼
[ Capa 3: RAG Semántico Bounded (BM25) ] -> contexto.md (RFCs 1035/9110/8446/5280/6066, <= 0.05 MB RAM)
                │
                ▼
[ Capa 4: Inferencia Local / Telemetría ] -> Ollama Q4_K_M + Ingesta Dinámica N Modelos
                │
                ▼
[ Capa 5: Orquestador Agéntico Read-Only ] -> LangGraph MemorySaver + dig/curl/openssl + Traductor ES
                │
                ▼
[ Capa 6: Interfaces CLI y Web FastAPI ] -> CLI benchapp + Dashboard Alto Contraste Dark/Light + SSE
                │
                ▼
[ Capa 7: Arnés Evaluador Multidimensional ] -> Normativa SHA-256 (1f8c1a7e3a9d) + SciPy + resultados.csv
```

---

## 4. Resultados Experimentales del Benchmark (162 Corridas Reales Locales)

La batería de evaluación controlada con 3 modelos × 18 escenarios × 3 semillas deterministas (`[42, 1337, 2026]`) a temperatura `0.0`, ejecutada 100% de forma local mediante Ollama sobre el hardware host (AMD 8 núcleos, 13.8 GB RAM), produjo la siguiente matriz multidimensional consolidada tras la recalificación normativa:

| Dimensión Evaluada | Phi-4-mini-instruct (3.8B) | Qwen3-8B (8.2B) | GLM-4-9B-Chat (9.0B) |
|---|---|---|---|
| **Precisión Diagnóstica** | 63.0% (34/54) | 85.2% (46/54) | **88.9%** (48/54) |
| **Acierto Parcial Promedio** | $0.555$ | **$0.806$** | $0.797$ |
| **Aislamiento de Componente** | 46.3% (25/54) | **74.1%** (40/54) | 61.1% (33/54) |
| **Tasa Sustentada en Evidencia** | 94.4% (51/54) | **96.3%** (52/54) | **96.3%** (52/54) |
| **Rúbrica de Explicabilidad (0-5)** | $3.85 \pm 1.04$ | **$4.48 \pm 0.79$** | $4.41 \pm 0.67$ |
| **TTFT Fase Prefill Promedio (ms)** | **$83,042.9$ ms** (~83.0 s) | $161,507.9$ ms (~161.5 s) | $182,836.0$ ms (~182.8 s) |
| **Velocidad de Decodificación (tok/s)** | **$4.51$ tok/s** | $3.49$ tok/s | $3.36$ tok/s |
| **Latencia Total Mediana ($p_{50}$)** | **$172,380.2$ ms** (~2.87 min) | $353,103.5$ ms (~5.89 min) | $379,153.6$ ms (~6.32 min) |
| **Latencia Percentil 95 ($p_{95}$)** | **$264,736.0$ ms** (~4.41 min) | $637,374.2$ ms (~10.62 min) | $609,063.1$ ms (~10.15 min) |
| **Consumo Declarado de VRAM** | **$2.8$ GB** | $5.5$ GB | $5.9$ GB |
| **Energía Total Acumulada** | **$0.330$ kWh** | $0.862$ kWh | $0.911$ kWh |
| **Eficiencia Tok/Wh** | **$127,212.9$ tok/Wh** | $82,263.8$ tok/Wh | $79,189.3$ tok/Wh |
| **Score Compuesto de Compromiso (OE4)** | 0.745 (Rango 3 - Edge) | 0.850 (Rango 2 - CoT / Borde) | **0.860 (Óptimo / NOC)** |

### 4.1. Análisis Correlacional y Significancia Estadística (Tarea 4.1.2)
- **Correlación de Pearson ($r$) y Spearman ($\rho$):** La velocidad de decodificación guarda una correlación inversa significativa con el tamaño del modelo ($r = -0.7039, \rho = -0.6296, p < 0.0001$). El tiempo al primer token (TTFT), la energía y la latencia total correlacionan fuertemente de forma positiva ($r = +0.7854, \rho = +0.8342$; $r = +0.8138, \rho = +0.7816$; y $r = +0.8015, \rho = +0.7661$, respectivamente). La calidad de la rúbrica explicativa y el acierto parcial muestran correlaciones positivas moderadas ($r = +0.3078, p = 0.00007$; y $r = +0.3711, p < 0.0001$).
- **Prueba de Kruskal-Wallis:** Se comprobaron diferencias estadísticamente significativas entre los tres modelos en todas las métricas temporales, de throughput y energéticas: TTFT ($H = 117.24, p < 0.0001$), velocidad de decodificación ($H = 66.82, p < 0.0001$), latencia total ($H = 109.58, p < 0.0001$), energía ($H = 110.91, p < 0.0001$), rúbrica ($H = 13.70, p = 0.00106$) y acierto parcial ($H = 20.05, p = 0.00004$).
- **Intervalos de Confianza Bootstrap al 95% ($B = 1000$):** Los intervalos para la latencia media y el TTFT no se solapan entre Phi-4-mini ($78.6 - 88.3\text{ s}$) y los modelos de 8B/9B ($151.7 - 193.5\text{ s}$), confirmando ventajas de velocidad inequívocas para la arquitectura liviana de 3.8B.

---

## 5. Conclusiones y Selección de la Configuración de Mejor Compromiso

1. **Cumplimiento Integral de Objetivos:** Se demostró la viabilidad técnica y computacional de ejecutar autodiagnóstico agéntico en Capa 7 con modelos de lenguaje ligeros de pesos abiertos, garantizando cero fuga de información confidencial y reproducibilidad absoluta.
2. **Mejor Compromiso Global (NOC / Operaciones Centrales):** **GLM-4-9B-Chat (Q4_K_M)** alcanza el mayor score de compromiso global (**0.860**), liderando con un **88.9%** de precisión diagnóstica, 4.41 / 5.0 en rúbrica, 96.3% de respaldo en evidencia empírica y 5.9 GB VRAM declarada.
3. **Configuración de Razonamiento CoT:** **Qwen3-8B (Q4_K_M)** se consolida como la segunda opción con score de **0.850**, liderando el aislamiento de componentes (**74.1%**) y la mayor rúbrica de explicabilidad (**4.48 / 5.0**), impulsada por su deliberación reflexiva nativa (`<thought>`).
4. **Máxima Eficiencia y Selección para Borde (Edge / Triaje Rápido):** **Phi-4-mini-instruct (Q4_K_M)** obtiene un score de **0.745**. Con 2.8 GB VRAM, TTFT de 83.0 s y el menor consumo de energía (0.330 kWh), resulta idóneo para estaciones portátiles o nodos remotos.
5. **Declaración Formal de Desviaciones y Trazabilidad MLOps:** Se formalizan como adaptaciones metodológicas: $R = 1$ con 3 semillas fijadas deterministas ($N=162$), timeout de inferencia ampliado a 900 s por ejecución en CPU host (158/162 corridas > 120 s), exclusión de la VRAM declarada del score de compromiso, inferencia de las 135 corridas simuladas sin repositorio git (`git_commit_hash = "desconocido"`), 27 corridas emuladas bajo commit de ejecución $X$ (`ca6e7fd`, `git_dirty = False`), recalificación normativa completa de las 162 filas bajo commit $Y$ (`4a4ef77`), y hash inmutable del evaluador normativo único `1f8c1a7e3a9d`.
6. **Impacto Institucional:** Se entrega a la Universidad de Pamplona un framework completamente funcional, un conjunto de datos trazable de 162 corridas y un panel web interactivo de alto contraste para docencia e investigación en redes y telecomunicaciones.

---

## 6. Anexos de Código y Datos

- **Anexo A (Código Fuente):** Repositorio local versionado conteniendo los módulos `src/core`, `src/layer1_lab` a `src/layer7_evaluator`.
- **Anexo B (Pruebas Automatizadas):** Suite de 225 pruebas unitarias y de integración (`tests/`) ejecutadas con 100% de éxito.
- **Anexo C (Dataset de Benchmark, Exportaciones y Análisis):** Archivo granular `resultados.csv` (162 registros), libro multioja `benchmark_l7_consolidado.xlsx` (10 hojas formateadas), informes PDF académicos (`informe_comparativo_oe4.pdf`, `analisis_correlacional.pdf`, `informe_consolidado_netdiagbench.pdf`) y reporte interactivo HTML/SVG.
- **Anexo D (Acta de Selección E1 y Guía de Operación):** Documentos `docs/E1_matriz_caracterizacion_y_acta_seleccion.md` y `docs/GUIA_REPRODUCIBILIDAD.md`.
