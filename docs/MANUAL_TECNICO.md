# Manual técnico de NetDiagBench-L7

## 1. Arquitectura

NetDiagBench-L7 organiza el diagnóstico en ocho capas: laboratorio y emulación, ingesta y preprocesamiento, recuperación léxica BM25, inferencia local, orquestación, interfaz, evaluación automática y validación humana.

Las herramientas de diagnóstico de red se restringen a operaciones de solo lectura. Los escenarios cubren fallas DNS, HTTP, pasarela de API y TLS.

## 2. Modelos de la campaña

| Modelo | Etiqueta Ollama | Parámetros | Cuantización efectiva |
|---|---|---:|---|
| GLM-4-9B-Chat | glm4:9b-chat-q4_K_M | 9,4 B reportados por runtime; ficha 9,0 B | Q4_0 |
| Qwen3-8B | qwen3:8b | 8,2 B | Q4_K_M |
| Phi-4-mini-instruct | phi4-mini:instruct-q4_K_M | 3,8 B | Q4_K_M |

En GLM, la etiqueta de distribución declara Q4_K_M, pero el archivo GGUF ejecutado fue identificado como Q4_0. Phi también tuvo el alias local phi4-mini:latest para el mismo archivo de pesos.

## 3. Campaña experimental

La campaña oficial comprende 162 corridas (3 modelos × 18 escenarios × 3 semillas), una ejecución por combinación. Las semillas fueron 42, 1337 y 2026. Las 162 inferencias utilizaron Ollama 0.34.2 con backend CPU. Se ejecutaron 27 escenarios emulados y 135 sintéticos deterministas.

## 4. Plataforma real

La campaña se ejecutó sobre AMD Ryzen 5 7520U, cuatro núcleos físicos y ocho lógicos, 16 GB LPDDR5 instalados (13,8 GB utilizables), GPU integrada AMD Radeon 610M con 2 GB compartidos y sin sensor de VRAM, Windows 11 y Docker Desktop 28.4.0 sobre WSL2.

Los valores de memoria de los modelos son declarados. No deben describirse como VRAM física medida.

## 5. Resultados

El diagnóstico completo fue 74,1 % para GLM, 87,0 % para Qwen y 64,8 % para Phi. La causa raíz estricta fue 61,1 %, 44,4 % y 25,9 %, respectivamente. Los resultados detallados, tiempos, energía y análisis estadístico se presentan en docs/RESULTADOS_BENCHMARK.md y docs/ANALISIS_ESTADISTICO.md.

La rúbrica técnica y la rúbrica humana v3.0.0 se reportan por separado. La primera se conserva en rubric_score; la segunda se calcula sobre 54 casos humanos, 18 por modelo, mediante C2-C5.
