# Entregable E6: Manuscrito de Artículo Científico Académico

**Título en Español:** Evaluación Multidimensional de Modelos de Lenguaje Ligeros de Ejecución Local para el Diagnóstico Agéntico de Fallas en Servicios de Capa de Aplicación sobre Redes IP  
**Título en Inglés:** Multidimensional Evaluation of Locally Executed Small Language Models for Agentic Fault Diagnosis in Application Layer Services over IP Networks  

**Autores:**  
Juan David León Arrieta, Richard Eliseo Mendoza Gáfaro  
*Departamento de Electricidad, Electrónica, Sistemas y Telecomunicaciones (E.E.S.T.)*  
*Facultad de Ingenierías y Arquitectura, Universidad de Pamplona, Pamplona, Colombia*  
Correos electrónicos: `juan.leon22@unipamplona.edu.co`, `richard.mendoza@unipamplona.edu.co`  

---

### Resumen
El creciente despliegue de microservicios y protocolos de Capa de Aplicación (L7) en redes IP ha complejizado el aislamiento de anomalías en centros de operaciones de red (NOC). Si bien los Modelos de Lenguaje Grande (LLMs) han demostrado capacidades notables en análisis de texto técnico, su dependencia de infraestructuras en la nube compromete la privacidad de las trazas de red, genera costos recurrentes inviables y añade latencias WAN incompatibles con contingencias operativas. Este artículo presenta **NetDiagBench-L7**, un marco metodológico y banco de pruebas reproducible para evaluar modelos de lenguaje ligeros (SLMs) ejecutados de forma estrictamente local bajo restricciones de hardware accesible ($\le 8\text{ GB}$ VRAM). Se evalúa una terna arquitectónicamente diversa (GLM-4-9B-Chat, Qwen3-8B y Phi-4-mini-instruct) cuantizada a 4 bits (`Q4_K_M GGUF`) a través de un ciclo agéntico desacoplado en siete capas que combina minería de registros con Drain3 v0.9.11, recuperación contextual normativo-semántica acotada (RAG léxico-semántico $\le 0.05\text{ MB}$ RAM sobre RFCs 1035, 9110, 8446, 5280 y 6066), un orquestador agéntico con persistencia en RAM (LangGraph MemorySaver), invocación contrastada de herramientas de red en modo de solo lectura (`dig`, `curl`, `openssl`), extracción estricta de diagnóstico derivada exclusivamente de la generación del modelo con traducción universal al español, y un evaluador formal determinista basado en criterios normativos IETF versionados por resumen criptográfico SHA-256 (`1f8c1a7e3a9d`). A lo largo de 162 corridas experimentales controladas sobre 18 clases de falla L7 (DNS, HTTP/Web, API Gateway y TLS) evaluadas con 3 semillas deterministas (`[42, 1337, 2026]`), el sistema alcanzó una precisión diagnóstica global del **79.0%** (128/162) con una tasa de respaldo en evidencia activa del **95.1%** (154/162). El análisis de compensaciones (*trade-offs*) multidimensional revela que **GLM-4-9B-Chat (9.0B)** constituye la configuración de **mejor compromiso global (*best trade-off*)** para centros de control e ingeniería NOC, alcanzando un score compuesto de **0.860** con **88.9%** (48/54) de precisión en causa raíz, rúbrica de 4.41/5.0 y 5.9 GB VRAM. **Qwen3-8B (8.2B)** se posiciona en segundo lugar con score de **0.850**, liderando la explicabilidad (rúbrica 4.48/5.0) y el aislamiento de componentes (**74.1%**) con razonamiento CoT reflexivo nativo (`<thought>`) en 5.5 GB VRAM. Por su parte, **Phi-4-mini-instruct (3.8B)** se establece como la solución óptima para despliegues ligeros en borde (*edge*), exhibiendo la menor latencia mediana ($p_{50} = 172.4\text{ s}$), mayor tasa de generación ($4.5\text{ tok/s}$) y mínima huella computacional ($2.8\text{ GB}$ VRAM, $0.330\text{ kWh}$).

**Palabras clave:** Diagnóstico de Redes, Modelos de Lenguaje Ligeros (SLM), Capa de Aplicación (L7), Benchmark Reproducible, RAG Acotado, Orquestación Agéntica, Validación Normativa IETF.

---

### Abstract
The expanding deployment of microservices and Application Layer (L7) protocols in IP networks has significantly increased the complexity of fault isolation in Network Operations Centers (NOC). Although Large Language Models (LLMs) have proven adept at technical log analysis, their reliance on cloud infrastructures compromises the confidentiality of network telemetry, incurs recurring API costs, and introduces variable WAN latencies that hinder scientific reproducibility and operational sovereignty. This paper presents **NetDiagBench-L7**, a reproducible benchmarking framework designed to evaluate Small Language Models (SLMs) running strictly on local consumer hardware ($\le 8\text{ GB}$ VRAM). We evaluate an architecturally diverse triplet (GLM-4-9B-Chat, Qwen3-8B, and Phi-4-mini-instruct) in 4-bit quantization (`Q4_K_M GGUF`) across a decoupled seven-layer agentic architecture. The framework integrates log template mining (Drain3 v0.9.11), normative semantic retrieval with minimal memory overhead (RAG $\le 0.05\text{ MB}$ RAM over RFCs 1035, 9110, 8446, 5280, and 6066), a memory-preserved orchestrator (LangGraph MemorySaver), empirical verification via read-only network utilities (`dig`, `curl`, `openssl`), model-exclusive verdict extraction with universal technical Spanish translation, and a formal deterministic evaluator based on IETF specifications versioned by SHA-256 (`1f8c1a7e3a9d`). Across 162 controlled experimental trials covering 18 L7 fault scenarios (DNS, HTTP/Web, API Gateway, and TLS) evaluated over 3 deterministic seeds (`[42, 1337, 2026]`), the framework achieved an overall diagnostic accuracy of **79.0%** (128/162) and a **95.1%** (154/162) empirical evidence-backing rate. Multidimensional trade-off analysis indicates that **GLM-4-9B-Chat (9.0B)** represents the **optimal overall compromise (*best trade-off*)** for NOC engineering, achieving a composite efficiency score of **0.860**, **88.9%** (48/54) root-cause accuracy, a 4.41/5.0 rubric score, and 5.9 GB VRAM footprint. **Qwen3-8B (8.2B)** ranks second with a composite score of **0.850**, leading component isolation (**74.1%**) and explainability (4.48/5.0) via native CoT reasoning (`<thought>`) under 5.5 GB VRAM. Concurrently, **Phi-4-mini-instruct (3.8B)** emerges as the optimal configuration for edge computing deployments, delivering the lowest median latency ($p_{50} = 172.4\text{ s}$), highest decoding velocity ($4.5\text{ tok/s}$), and lowest resource consumption ($2.8\text{ GB}$ VRAM, $0.330\text{ kWh}$).

**Keywords:** Network Fault Diagnosis, Small Language Models, Application Layer (L7), Reproducible Benchmark, Bounded RAG, Agentic Orchestration, IETF Normative Validation.

---

## 1. Introducción
La operación de servicios en redes de telecomunicaciones modernas enfrenta una transformación estructural debido a la adopción de arquitecturas de microservicios distribuidos, balanceadores de carga, pasarelas API y cifrado TLS 1.3 generalizado. Anomalías en protocolos de Capa de Aplicación (Capa 7 del modelo OSI) —tales como errores de resolución DNS (`NXDOMAIN`, `SERVFAIL`, delegaciones cojas *lame delegation*), códigos HTTP de pasarela (`502 Bad Gateway`, `504 Gateway Timeout`, saturación de *connection pools*), caídas de servidor de origen o disrupciones de cadena de confianza X.509 en TLS— provocan degradaciones severas del servicio cuyo aislamiento manual exige una correlación temporal compleja entre registros heterogéneos y telemetría de red.

La literatura reciente ha explorado el uso de Modelos de Lenguaje Grande (LLMs) comerciales en tareas de gestión y autodiagnóstico de redes (Boateng et al., 2024; Tseng et al., 2026a). No obstante, su operación mediante APIs propietarias en la nube plantea barreras insalvables para operadores de telecomunicaciones e instituciones académicas:
1. **Riesgo Crítico de Fuga de Información Sensible:** La transmisión externa de volcados de registros, esquemas de direccionamiento IP interno, certificados y nombres de dominio vulnera normativas de seguridad de la información y privacidad de datos.
2. **Dependencia WAN y Costos Recurrentes:** Las llamadas a modelos en la nube sufren de derivas de versión (*model drift*) y latencias impredecibles que destruyen la reproducibilidad experimental, además de representar un costo financiero recurrente inviable.
3. **Brecha de Recursos Computacionales:** En entornos educativos o centros de datos locales no se dispone de clústeres masivos de aceleradores de alto rendimiento (ej. NVIDIA H100).

Frente a este panorama, los Modelos de Lenguaje Ligeros (SLMs) con menos de 10 mil millones de parámetros cuantizados a 4 bits (`Q4_K_M GGUF`) posibilitan la inferencia local sobre estaciones de cómputo accesibles ($\le 8\text{ GB}$ VRAM). Sin embargo, existía un vacío metodológico: la falta de un marco de evaluación estandarizado, determinista y auditable que evalúe la precisión de diagnóstico de estos modelos apoyados en orquestación agéntica y estándares normativos oficiales.

El presente artículo expone el diseño, desarrollo y validación experimental de **NetDiagBench-L7**, un marco metodológico abierto y reproducible concebido para caracterizar las capacidades diagnósticas y las compensaciones computacionales de modelos de lenguaje ligeros locales.

---

## 2. Metodología y Arquitectura del Framework NetDiagBench-L7

NetDiagBench-L7 opera mediante una arquitectura modular y desacoplada estructurada en siete capas tipadas mediante contratos de datos estandarizados con Pydantic:

1. **Capa 1 (Entorno de Laboratorio y Catálogo L7):** Comprende un catálogo formal de 18 escenarios de falla que cubren integralmente la taxonomía L7:
   - **DNS (5 escenarios):** `DNS-NXD-01` (nombre inexistente RFC 1035), `DNS-SRV-01` (timeout de resolución recursiva), `DNS-DEL-01` (error de delegación coja), `DNS-REF-01` (rechazo por lista de control de acceso), y `DNS-TRUNC-01` (truncamiento UDP sin respaldo TCP RFC 6891).
   - **HTTP / Web (3 escenarios):** `HTTP-500-01` (excepción interna no controlada), `HTTP-503-01` (saturación de hilos de trabajo), y `NET-LAT-01` (latencia anómala emulada con Linux `tc-netem`).
   - **API Gateway (6 escenarios):** `HTTP-502-01` (Bad Gateway por socket cerrado), `HTTP-504-01` (Gateway Timeout por demora de backend), `HTTP-ORIGIN-01` (caída total de servidor de origen), `HTTP-POOL-01` (agotamiento de conexiones reutilizables), `HTTP-403-01` (bloqueo por política WAF/ACL), y `HTTP-429-01` (estrangulamiento por límite de tasa RFC 6585).
   - **Transporte Seguro TLS (4 escenarios):** `TLS-EXP-01` (certificado digital expirado RFC 5280), `TLS-CHN-01` (cadena de certificación incompleta), `TLS-SNI-01` (discrepancia de nombre de host SNI RFC 6066), y `TLS-CIPH-01` (incompatibilidad de suites criptográficas RFC 8446).
   El entorno admite tanto simulación sintética calibrada (`sintetico_determinista`) como emulación real en contenedores Docker Compose (`emulado`) con servicios vivos (BIND9 v9.18, Nginx v1.24, OpenSSL v3.0).
2. **Capa 2 (Pipeline de Ingesta y Minería de Registros):** Implementa el algoritmo de agrupamiento `Drain3` (v0.9.11) para extraer plantillas semánticas invariantes a partir de registros crudos de syslog, servidores web y DNS, filtrando parámetros efímeros y normalizando marcas temporales y direcciones IP. La ventana de contexto se ensambla deterministamente mediante plantillas `Jinja2`.
3. **Capa 3 (Recuperación RAG Léxico-Semántica Acotada):** Motor de recuperación basado en BM25 alimentado por fragmentos indexados de especificaciones estándar del IETF (RFC 1035, RFC 9110, RFC 8446, RFC 5280, RFC 6066, manuales BIND9 ARM y `tc-netem`) y procedimientos operativos estandarizados (SOPs). El índice opera en memoria principal con un consumo estricto de $0.05\text{ MB}$ de RAM, garantizando el cumplimiento holgado del presupuesto de memoria ($\le 0.45\text{ GB}$ RAM).
4. **Capa 4 (Motor de Inferencia Local y Telemetría Granular):** Abstracción sobre Ollama y backends compatibles con GGUF en cuantización `Q4_K_M`. Monitorea el tiempo hasta el primer token ($TTFT$, fase de prefill), la velocidad de decodificación ($\text{tok/s}$), latencia total, memoria RAM/VRAM y energía física estimada según el modelo de potencia de Henríquez Miranda et al. (2026). Incorpora gestión dinámica para ingerir $N$ modelos adicionales bajo el grupo `model_group = "adicional"`.
5. **Capa 5 (Orquestación Agéntica de Solo Lectura con Memoria RAM):** Máquina de estados agéntica basada en LangGraph con persistencia de puntos de control en memoria RAM (`MemorySaver`). El agente formula una hipótesis diagnóstica, recupera contexto normativo y ejecuta comprobaciones empíricas de red limitadas a una lista blanca de herramientas de solo lectura (`dig`, `curl`, `openssl`). La causa raíz, componente técnico y mitigación se extraen **obligatoriamente y en su totalidad de la respuesta emitida por el modelo** (cero fuga del *ground truth*), incorporando traducción técnica universal al español mediante `src/core/translator.py` y preservando el razonamiento reflexivo nativo CoT (`<think>...</think>`).
6. **Capa 6 (Interfaz de Usuario y Observabilidad Web):** Interfaz CLI (`benchapp`) construida con Typer y Dashboard web interactivo desarrollado con FastAPI, Jinja2, HTMX y Tailwind CSS. Dispone de soporte bimodal de alto contraste (Dark / Light Mode con legibilidad total de texto y botones), streaming SSE en tiempo real, pausa/reanudación de suites y exportación a PDF, Excel (.xlsx) y CSV.
7. **Capa 7 (Evaluador Formal Determinista y Análisis Estadístico):** Evaluación formal basada en criterios normativos derivados de especificaciones IETF, versionados mediante el resumen criptográfico SHA-256 `1f8c1a7e3a9d` (`configs/evaluator_concepts.yaml`). La regla universal de aceptación exige:
   $$\text{is\_correct} = (\text{cumple} \ge 1\ \text{cause\_group}) \land (\neg \text{clase vecina en primera oración}) \land (\neg \text{solo síntoma})$$
   Incluye cálculo de acierto parcial, rúbrica cualitativa de interpretabilidad ($0.0-5.0$), concordancia inter-evaluador ($\kappa$ de Cohen), y una suite de análisis estadístico bivariado (`scipy.stats`) que computa correlaciones de Spearman, Pearson, prueba de Kruskal-Wallis, intervalos bootstrap al 95% y tamaño de efecto ($d$ de Cohen).

---

## 3. Resultados Experimentales y Discusión

La batería experimental se conformó por 3 modelos SLM (`GLM-4-9B-Chat`, `Qwen3-8B`, `Phi-4-mini-instruct`) $\times$ 18 escenarios de falla $\times$ 3 semillas deterministas (`[42, 1337, 2026]`) a temperatura $0.0$, totalizando **162 corridas completas** ejecutadas sobre la plataforma host de referencia (procesador AMD64 de 8 núcleos, 13.8 GB RAM de sistema y límite de 8 GB VRAM). El dataset comprende 135 corridas en modo sintético calibrado y 27 corridas en modo emulado sobre contenedores Docker Compose.

### 3.1. Eficacia Diagnóstica y Calidad Explicativa

La Tabla 1 consolida los indicadores de exactitud, aislamiento de componentes y calidad explicativa para los tres modelos evaluados:

*Tabla 1. Métricas de Eficacia Diagnóstica y Explicabilidad (N = 162 corridas, 54 por modelo).*

| Modelo Evaluado | Parámetros | Precisión Causa Raíz (%) | Acierto Parcial Promedio | Aislamiento Componente (%) | Respaldo Evidencia (%) | Rúbrica Explicativa (0-5) | Score Compuesto |
|---|---|---|---|---|---|---|---|
| **GLM-4-9B-Chat** | 9.0 B | **88.9%** (48/54) | 0.797 | 61.1% (33/54) | **96.3%** (52/54) | 4.41 / 5.0 | **0.860 (#1)** |
| **Qwen3-8B** | 8.2 B | 85.2% (46/54) | **0.806** | **74.1%** (40/54) | **96.3%** (52/54) | **4.48 / 5.0** | 0.850 (#2) |
| **Phi-4-mini-instruct** | 3.8 B | 63.0% (34/54) | 0.555 | 46.3% (25/54) | 94.4% (51/54) | 3.85 / 5.0 | 0.745 (#3) |

**GLM-4-9B-Chat (9.0B)** alcanzó la mayor precisión diagnóstica global con un **88.9%** (48 aciertos sobre 54 ensayos), logrando un 100% de efectividad en 11 de los 18 escenarios (incluyendo todos los casos de DNS delegado, truncamiento, HTTP 500, HTTP 502, y la totalidad de escenarios TLS).
**Qwen3-8B (8.2B)** obtuvo un **85.2%** de exactitud global, pero se destacó como el modelo superior en aislamiento específico del componente de red afectado (**74.1%** frente a 61.1% de GLM y 46.3% de Phi-4) y en la rúbrica de calidad de la fundamentación técnica (**4.48 / 5.0**), impulsado por su bloque de razonamiento nativo reflexivo (`<thought>`).
**Phi-4-mini-instruct (3.8B)** registró una precisión del **63.0%** (34/54) y una rúbrica de 3.85/5.0. Si bien mostró alta precisión en fallas directas como `DNS-NXD-01` y códigos HTTP simples, evidenció dificultades para discriminar causas en escenarios con acoplamiento de pasarela (`HTTP-502-01`, `TLS-EXP-01` en modo emulado).

La tasa de diagnósticos respaldados en evidencia empírica activa superó el **94%** en todos los modelos (96.3% en GLM-4 y Qwen3, 94.4% en Phi-4-mini), demostrando que el patrón agéntico de la Capa 5 fuerza una contrastación efectiva con la salida de utilidades de red antes de formular conclusiones.

### 3.2. Desempeño Temporal, Recursos Computacionales y Análisis Estadístico

La Tabla 2 presenta el comportamiento temporal y el consumo de recursos computacionales durante la inferencia local sobre CPU:

*Tabla 2. Métricas de Rendimiento Físico e Inferencia Local.*

| Modelo Evaluado | TTFT Promedio (ms) | Velocidad (tok/s) | Latencia $p_{50}$ (s) | Latencia $p_{95}$ (s) | VRAM Pico (GB) | Energía Total (kWh) | Eficiencia (tok/Wh) |
|---|---|---|---|---|---|---|---|
| **Phi-4-mini-instruct** | **83,042.9 ms** (~83.0 s) | **4.51 tok/s** | **172.4 s** (~2.87 min) | **264.7 s** (~4.41 min) | **2.8 GB** | **0.330 kWh** | **127,212.9** |
| **Qwen3-8B** | 161,507.9 ms (~161.5 s) | 3.49 tok/s | 353.1 s (~5.89 min) | 637.4 s (~10.62 min) | 5.5 GB | 0.862 kWh | 82,263.8 |
| **GLM-4-9B-Chat** | 182,836.0 ms (~182.8 s) | 3.36 tok/s | 379.2 s (~6.32 min) | 609.1 s (~10.15 min) | 5.9 GB | 0.911 kWh | 79,189.3 |

El análisis estadístico bivariado formal (`scipy.stats`) ejecutado sobre las 162 observaciones arroja conclusiones contundentes:
- **Correlación Parámetros vs. Rendimiento:**
  - **Tiempo al Primer Token ($TTFT$):** Fuerte correlación positiva con la escala paramétrica ($\rho = 0.8342, r = 0.7854, p < 0.0001$).
  - **Velocidad de Decodificación ($\text{tok/s}$):** Fuerte correlación negativa ($\rho = -0.6296, r = -0.7039, p < 0.0001$). El modelo de 3.8B emite tokens a un ritmo 34% mayor que el de 9.0B sobre CPU host.
  - **Latencia Total de Inferencia:** Fuerte correlación positiva ($\rho = 0.7661, r = 0.8015, p < 0.0001$).
  - **Consumo Energético:** Fuerte correlación positiva ($\rho = 0.7816, r = 0.8138, p < 0.0001$). Phi-4-mini consumió únicamente 0.330 kWh acumulados frente a 0.862 kWh de Qwen3 y 0.911 kWh de GLM-4.
  - **Calidad de Rúbrica y Acierto Parcial:** Correlación positiva moderada ($\rho = 0.2145, p = 0.0061$ en rúbrica; $\rho = 0.2426, p = 0.0019$ en coincidencia parcial), demostrando que los modelos mayores preservan explicaciones técnicas más completas.
- **Prueba No Paramétrica de Kruskal-Wallis:** Confirma diferencias altamente significativas entre los tres modelos en todas las dimensiones: $TTFT$ ($H = 117.24, p < 0.0001$), velocidad de salida ($H = 66.82, p < 0.0001$), latencia total ($H = 109.58, p < 0.0001$), consumo de energía ($H = 110.91, p < 0.0001$), rúbrica ($H = 13.70, p = 0.0011$) y acierto parcial ($H = 20.05, p < 0.0001$).
- **Intervalos de Confianza Bootstrap al 95% ($B = 1000$):** Los intervalos para la latencia total media no se solapan entre Phi-4-mini ($167.3 - 187.5\text{ s}$) y los modelos de 8B/9B ($363.9 - 427.1\text{ s}$), ratificando la ventaja de agilidad del modelo ultracompacto.

### 3.3. Comparación entre Modos de Ejecución (Sintético vs. Emulado)

El desglose entre las 135 corridas en modo sintético y las 27 en modo emulado (contenedores Docker) revela una brecha operacional significativa:
- **Simulador Sintético Calibrado (135 corridas):** 85.2% de precisión diagnóstica, 95.6% de respaldo en evidencia, latencia media de 295.5 s y rúbrica de 4.3/5.0.
- **Laboratorio Emulado en Contenedores (27 corridas):** 48.1% de precisión diagnóstica, 96.3% de respaldo en evidencia, latencia media de 460.3 s y rúbrica de 4.0/5.0.
Esta disparidad pone de relieve que los registros dinámicos y la concurrencia real de servicios vivos imponen un desafío de generalización superior al de simulaciones deterministas, validando la relevancia de contar con pruebas en contenedores reales.

### 3.4. Análisis de Compensaciones (*Trade-Offs*) y Recomendaciones de Selección

1. **Configuración de Mejor Compromiso Global (NOC / Operaciones Centrales):** **GLM-4-9B-Chat (Q4_K_M)** se ratifica como la configuración óptima global (**Score de Eficiencia Compuesto: 0.860**). Tras aplicar el filtro de exactitud viable ($\ge 70.0\%$), lidera la precisión diagnóstica con un **88.9%**, excelente solidez en seguimiento de esquemas estructurados, 4.41/5.0 en rúbrica y opera de forma estable con 5.9 GB de VRAM declarada sobre el límite de 8.0 GB.
2. **Configuración de Razonamiento CoT para Recursos Acotados:** **Qwen3-8B (Q4_K_M)** se posiciona en segundo lugar (**Score: 0.850**). Es la alternativa recomendada cuando se requiere máxima explicabilidad (rúbrica 4.48/5.0) y aislamiento exacto del componente dañado (**74.1%**), beneficiándose de su traza de razonamiento reflexivo (`<thought>`) y menor consumo de memoria (5.5 GB VRAM).
3. **Configuración para Despliegues de Borde (*Edge Deployment* / Triaje Rápido):** **Phi-4-mini-instruct (Q4_K_M)** alcanza un score de **0.745**. Con un $TTFT$ de 83.0 s, tasa de 4.51 tok/s y consumo mínimo de 2.8 GB VRAM y 0.330 kWh, es la opción idónea para estaciones de campo portátiles o nodos de borde donde se priorice la velocidad preliminar, con posterior escalamiento al NOC para incidentes complejos.

---

## 4. Conclusiones
NetDiagBench-L7 demuestra experimentalmente que es completamente viable realizar diagnósticos autónomos y confiables de fallas complejas en servicios de Capa de Aplicación utilizando modelos de lenguaje ligeros operados de forma 100% local sobre estaciones de trabajo convencionales ($\le 8\text{ GB}$ VRAM). La arquitectura de siete capas propuesta —en particular la integración de minería semántica con Drain3, recuperación normativa acotada basada en especificaciones IETF, orquestación agéntica de solo lectura con persistencia en RAM, extracción rigurosa de veredicto sin fuga de datos y traducción universal al español— compensa la menor escala paramétrica de los SLMs frente a modelos de frontera comerciales. Los resultados confirman que GLM-4-9B-Chat ofrece el balance óptimo para centros de operaciones NOC, mientras que Qwen3-8B y Phi-4-mini-instruct ofrecen alternativas sobresalientes para tareas con razonamiento reflexivo o restricciones severas de cómputo en el borde.

---

## Referencias
- Agrawal, A., Agarwal, A., Kedia, N., Mohan, J., Kundu, S., Kwatra, N., Ramjee, R., & Tumanov, A. (2024). Etalon: Holistic Performance Evaluation Framework for LLM Inference Systems. *arXiv preprint arXiv:2407.07000*.
- Boateng, G. O., Sami, H., Alagha, A., Elmekki, H., Hammoud, A., Mizouni, R., Mourad, A., Otrok, H., Bentahar, J., Muhaidat, S., Talhi, C., Dziong, Z., & Guizani, M. (2024). A Survey on Large Language Models for Communication, Network, and Service Management. *arXiv preprint arXiv:2412.19823*.
- Chang, Y., Wang, X., Wang, J., Wu, Y., Yang, L., Zhu, K., Chen, H., Yi, X., Wang, C., Wang, Y., Ye, W., Zhang, Y., Yu, P. S., Yang, Q., & Xie, X. (2023). A Survey on Evaluation of Large Language Models. *ACM Transactions on Intelligent Systems and Technology*.
- Fielding, R., Nottingham, M., & Reschke, J. (2022). HTTP Semantics. *IETF RFC 9110*.
- Henríquez Miranda, C. N., Sánchez Cataño, M. A., & Sánchez Torres, G. (2026). Explorando el efecto ambiental del escalamiento multi-GPU en la relación energía-tiempo-CO2e durante el entrenamiento de modelos de aprendizaje profundo para visión. *Revista Colombiana de Tecnologías de Avanzada*, 2(48), 124-139.
- Mockapetris, P. (1987). Domain Names - Implementation and Specification. *IETF RFC 1035*.
- Rescorla, E. (2018). The Transport Layer Security (TLS) Protocol Version 1.3. *IETF RFC 8446*.
- Tseng, K.-H., Bogahawatta, N., Ginige, Y., Dakic, K., Sivanathan, A., & Seneviratne, S. (2026a). SADE: Symptom-Aware Diagnostic Escalation for LLM-Based Network Troubleshooting. *arXiv preprint arXiv:2605.04530*.
- Wang, Z., Cornacchia, A., Sacco, A., Galante, F., Canini, M., & Jiang, D. (2025). A Network Arena for Benchmarking AI Agents on Network Troubleshooting. *arXiv preprint arXiv:2512.16381*.
- Wu, K., Yu, Q., Mei, M., Liu, R., Wang, J., Zhang, K., Bao, Y., Wan, W., Ye, R., He, B., Liao, J., Du, Y., Yang, Z., Liu, K., Huang, L., Song, Z., Gao, Y., Tan, F., Yang, J., & Gu, N. (2025). TN-AutoRCA: Benchmark Construction and Agentic Framework for Self-Improving Alarm-Based Root Cause Analysis in Telecommunication Networks. *arXiv preprint arXiv:2507.18190*.
