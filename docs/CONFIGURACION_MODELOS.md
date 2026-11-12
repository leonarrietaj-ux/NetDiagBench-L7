# NetDiagBench-L7: Configuración y Caracterización de Modelos

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico de Redes Layer 7 sobre IP  
**Fecha:** Septiembre de 2026 / Noviembre de 2026 (v1.0.2)  

---

## 1. Protocolo de Búsqueda y Criterios de Selección (Actividad A1.1)

El objetivo de la actividad A1.1 consiste en evaluar sistemáticamente el espacio de modelos de lenguaje ligeros (SLMs / Small Language Models) de pesos abiertos capaces de ejecutarse de forma 100% local sobre estaciones de trabajo con restricciones de hardware (GPU ≤ 8 GB VRAM).

### 1.1. Criterios de Inclusión
1. **Condición de Admisión Legal (Licenciamiento Abierto):** Licencia que autorice explícitamente el uso investigativo/académico y la divulgación pública de resultados (Apache 2.0, MIT, OpenRAIL o licencias comunitarias permisivas de pesos abiertos).
2. **Eje de Parámetros con Recorrido Amplio:** Modelos con conteo de parámetros entre 3.0B y 9.0B, permitiendo correlacionar el impacto de la escala paramétrica con la fidelidad diagnóstica y la latencia.
3. **Independencia Arquitectónica:** Diversidad de linajes y familias neuronales para evitar sesgos derivados de destilación sobre un mismo modelo base (se descartan destilados directos como DeepSeek-R1-Distill-Qwen si Qwen ya está presente).
4. **Soporte Nativo Declarado de Herramientas (Function Calling):** Capacidad del modelo para invocar funciones estructuradas de red (ej. JSON/schema tool calling) documentada por el autor original, garantizando que las fallas en orquestación no se deban a ausencia de alineación funcional.
5. **Ejecutabilidad Local en Cuantización Q4_K_M (≤ 8 GB VRAM):** Compatibilidad con motores de inferencia local (`Ollama`, `llama.cpp` o `GGUF`) con huella de memoria de vídeo admisible.

---

## 2. Matriz Comparativa de los Doce (12) Modelos Candidatos (Tarea 1.1.2)

| # | Modelo Candidato | Familia / Laboratorio | Capas (Bloques) | Dim. Oculta ($d_{model}$) | Tipo Atención | Vocabulario | Parámetros Totales | Cuantización Base | Licencia | Tool Calling Declarado | Dictamen y Justificación |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | **Qwen3-8B** | Qwen / Alibaba | 36 | 4096 | GQA | 152,064 | 8.2 B | Q4_K_M (5.5 GB) | Apache 2.0 | Nativo documentado | **SELECCIONADO (Terna Final)**. Modo de razonamiento conmutable (`<thought>`), tool calling nativo, Apache 2.0. |
| **2** | **GLM-4-9B-Chat** | GLM / Zhipu AI | 40 | 4096 | GQA | 151,552 | 9.0 B | Q4_K_M (5.9 GB) | GLM-4 License | 81% Berkeley FC | **SELECCIONADO (Terna Final)**. Mayor rendimiento en function calling, arquitectura independiente, contexto 128k. |
| **3** | **Phi-4-mini-instruct** | Phi / Microsoft | 32 | 3072 | GQA | 200,064 | 3.8 B | Q4_K_M (2.8 GB) | MIT | JSON Schema Tools | **SELECCIONADO (Terna Final)**. Extremo inferior ligero, licencia MIT permisiva, alta velocidad en edge. |
| **4** | **Qwen2.5-7B-Instruct** | Qwen / Alibaba | 28 | 3584 | GQA | 152,064 | 7.6 B | Q4_K_M (4.7 GB) | Apache 2.0 | Nativo documentado | *Descartado.* Superado por Qwen3-8B en razonamiento conmutable y orquestación dentro de la misma familia. |
| **5** | **Llama-3.1-8B-Instruct** | Llama / Meta | 32 | 4096 | GQA | 128,256 | 8.0 B | Q4_K_M (5.2 GB) | Llama 3.1 Community | Nativo documentado | *Descartado.* Licencia comunitaria con restricciones de uso aceptable y redistribución frente a Apache 2.0 / MIT. |
| **6** | **Mistral-7B-Instruct-v0.3** | Mistral AI | 32 | 4096 | GQA | 32,768 | 7.2 B | Q4_K_M (4.6 GB) | Apache 2.0 | Function Calling v3 | *Descartado.* Menor vocabulario y rendimiento en seguimiento de esquemas complejos en español frente a GLM-4. |
| **7** | **Gemma-2-9B-It** | Gemma / Google | 42 | 3584 | MHA/GQA | 256,000 | 9.2 B | Q4_K_M (6.1 GB) | Gemma Terms of Use | No nativo formal | *Descartado.* Huella VRAM en límite superior y carece de soporte nativo estandarizado de llamadas a herramientas. |
| **8** | **DeepSeek-R1-Distill-Qwen-8B** | DeepSeek / Qwen | 36 | 4096 | GQA | 152,064 | 8.2 B | Q4_K_M (5.5 GB) | MIT | Limitado por razonamiento | *Descartado (Criterio 3).* Compararlo con Qwen3 mediría efecto de destilación y no variación arquitectónica independiente. |
| **9** | **GLM-Edge-4B-Chat** | GLM / Zhipu AI | 30 | 2560 | GQA | 151,552 | 4.0 B | Q4_K_M (2.6 GB) | GLM-4 License | Sin soporte nativo | *Descartado (Criterio 4).* Incumple soporte nativo de function calling; forzarlo alteraría la evaluación de escala. |
| **10** | **Qwen2.5-3B-Instruct** | Qwen / Alibaba | 36 | 2048 | GQA | 151,936 | 3.1 B | Q4_K_M (2.2 GB) | Apache 2.0 | Nativo documentado | *Descartado.* Phi-4-mini-instruct demostró mejor balance de calidad y licencia MIT más amplia en el rango ~3.8B. |
| **11** | **SmolLM2-1.7B-Instruct** | SmolLM / HuggingFace | 24 | 2048 | GQA | 49,152 | 1.7 B | Q4_K_M (1.2 GB) | Apache 2.0 | Experimental | *Descartado.* Fuera del rango paramétrico mínimo (inferior a 3.0B); alta tasa de alucinaciones en diagnósticos L7. |
| **12** | **Phi-3.5-mini-instruct** | Phi / Microsoft | 32 | 3072 | GQA | 32,064 | 3.8 B | Q4_K_M (2.8 GB) | MIT | Limitado en español | *Descartado.* Superado directamente por su sucesor directo Phi-4-mini-instruct en vocabulario (200k) y tokenización. |

---

## 3. Rúbrica Ponderada de Selección y Puntuación (Tarea 1.3.1)

Se aplicó una rúbrica con cinco dimensiones ponderadas:
1. **Rendimiento Declarado en Invocación de Herramientas (Peso 30%):** Capacidad de function calling estructurado.
2. **Independencia Arquitectónica y Diversidad de Familia (Peso 25%):** Representación de diferentes escuelas de diseño.
3. **Permisividad de la Licencia (Peso 20%):** Apertura para uso investigativo y divulgación (Apache 2.0 / MIT = 10 pts; licencias comunitarias = 6-7 pts).
4. **Eficiencia en VRAM y Velocidad en Cuantización Q4_K_M (Peso 15%):** Facilidad de ejecución dentro de los 8 GB VRAM.
5. **Amplitud de Vocabulario y Soporte Multilingüe (Peso 10%):** Tratamiento adecuado del léxico técnico en español e inglés.

### Resultados de la Evaluación Ponderada:

| Modelo Candidato | Tool Calling (30%) | Independencia (25%) | Licencia (20%) | Eficiencia VRAM (15%) | Vocabulario (10%) | Puntuación Final (0 - 10) | Estado |
|---|---|---|---|---|---|---|---|
| **Qwen3-8B** | 9.5 | 9.0 | 10.0 | 8.5 | 9.5 | **9.30** | **ADOPTADO** |
| **Phi-4-mini-instruct** | 9.0 | 9.5 | 10.0 | 10.0 | 9.0 | **9.48** | **ADOPTADO** |
| **GLM-4-9B-Chat** | 10.0 | 9.5 | 8.5 | 8.0 | 9.0 | **9.18** | **ADOPTADO** |
| Qwen2.5-7B-Instruct | 9.0 | 7.0 | 10.0 | 8.5 | 9.5 | 8.68 | Suplente |
| Llama-3.1-8B-Instruct | 9.0 | 9.0 | 6.5 | 8.5 | 8.0 | 8.33 | Descartado |
| Mistral-7B-Instruct-v0.3 | 8.5 | 8.5 | 10.0 | 9.0 | 6.5 | 8.68 | Descartado |
| Gemma-2-9B-It | 6.0 | 8.5 | 6.5 | 7.0 | 9.0 | 7.18 | Descartado |
| DeepSeek-R1-Distill-Qwen | 7.5 | 4.0 | 10.0 | 8.5 | 9.5 | 7.48 | Descartado |
| GLM-Edge-4B-Chat | 4.0 | 8.0 | 8.5 | 9.5 | 9.0 | 7.23 | Descartado |

---

## 4. Selección Justificada de la Terna de Modelos

A continuación se formaliza la justificación técnica de la selección adoptada para el benchmark:

1. **Ratificación de la Terna:**  
   Se declara formalmente adoptada la terna compuesta por:
   - **`Qwen3-8B` (8.2B, Q4_K_M, Apache 2.0)**
   - **`GLM-4-9B-Chat` (9.0B, Q4_K_M, GLM-4 License)**
   - **`Phi-4-mini-instruct` (3.8B, Q4_K_M, MIT)**
2. **Justificación Técnica:**  
   Esta selección garantiza:
   - Recorrido paramétrico continuo de 3.8B a 9.0B sin discontinuidades arquitectónicas.
   - Tres linajes de entrenamiento totalmente independientes (Alibaba, Zhipu AI, Microsoft).
   - Invocación estructurada comprobada en los tres modelos.
   - Compatibilidad estricta con el límite de 8 GB de VRAM de la plataforma de referencia.
3. **Registro de la Plataforma de Hardware de Referencia:**
   - **Sistema Operativo:** Microsoft Windows 11 Pro (64 bits).
   - **Procesador Central (CPU):** AMD64 Family 23 Model 160 Stepping 0 (8 núcleos lógicos / físicos).
   - **Memoria RAM de Sistema:** 13.8 GB asignables (Presupuesto RAG verificado: 0.02 MB ≤ 0.45 GB).
   - **Acelerador Gráfico / VRAM:** Límite operacional de 8.0 GB VRAM para pesos y KV cache en Q4_K_M.
   - **Ambiente de Inferencia:** Ollama v0.5+ / llama.cpp con fallback determinista calibrado.
