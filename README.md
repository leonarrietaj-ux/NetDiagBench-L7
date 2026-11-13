# NetDiagBench-L7

Benchmark reproducible para evaluar modelos de lenguaje pequeños en el diagnóstico de fallas de servicios de red de capa 7. El sistema utiliza inferencia local, escenarios DNS, HTTP y TLS, recuperación léxica BM25 y herramientas de verificación de solo lectura.

## Conjunto de datos oficial

El archivo canónico es **data/benchmark_results/resultados.csv**. Contiene 162 corridas: tres modelos, 18 escenarios y tres semillas (42, 1337 y 2026), con una ejecución por combinación de modelo, escenario y semilla. El CSV publicado contiene 99 columnas: los 98 campos experimentales descritos en el protocolo y el campo adicional human_score_source, utilizado para identificar la procedencia de las calificaciones humanas.

Las 162 inferencias de la campaña se ejecutaron con Ollama en CPU. La distribución comprende 27 corridas emuladas en contenedores y 135 corridas sintéticas deterministas. El archivo data/benchmark_results/traza.jsonl conserva la trazabilidad consolidada.

## Modelos evaluados

| Modelo | Etiqueta Ollama | Parámetros reportados | Cuantización efectiva | Memoria declarada |
|---|---|---:|---|---:|
| GLM-4-9B-Chat | glm4:9b-chat-q4_K_M | 9,4 B en Ollama; ficha del modelo: 9,0 B | Q4_0 | 5,9 GB |
| Qwen3-8B | qwen3:8b | 8,2 B | Q4_K_M | 5,5 GB |
| Phi-4-mini-instruct | phi4-mini:instruct-q4_K_M | 3,8 B | Q4_K_M | 2,8 GB |

La etiqueta phi4-mini:latest se utilizó como alias local del mismo archivo de pesos que phi4-mini:instruct-q4_K_M. En GLM, la etiqueta contiene q4_K_M, pero la inspección del archivo GGUF identificó Q4_0 como cuantización efectiva.

## Resultados diagnósticos

| Modelo | Diagnóstico completo | Causa raíz estricta | F1 macro, 18 clases | Diagnósticos con evidencia automática |
|---|---:|---:|---:|---:|
| GLM-4-9B-Chat | 40/54 (74,1 %) | 33/54 (61,1 %) | 0,757 | 23/54 (42,6 %) |
| Qwen3-8B | 47/54 (87,0 %) | 24/54 (44,4 %) | 0,848 | 15/54 (27,8 %) |
| Phi-4-mini-instruct | 35/54 (64,8 %) | 14/54 (25,9 %) | 0,661 | 0/54 (0,0 %) |
| Total | 122/162 (75,3 %) | 71/162 (43,8 %) | n. a. | 38/162 (23,5 %) |

El diagnóstico completo considera la causa raíz y su fundamentación técnica. La métrica estricta evalúa el campo de causa raíz por separado. Las dos medidas no deben intercambiarse.

## Tiempo y consumo

Los tiempos se midieron con inferencia en CPU. Los intervalos de confianza se calcularon mediante remuestreo por escenario (1.000 réplicas, semilla 42).

| Modelo | TTFT mediano | Latencia P50 | Latencia P95 | Tokens/s | Energía estimada por corrida |
|---|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 295,5 s | 491,6 s | 687,7 s | 2,91 | 21,0 Wh |
| Qwen3-8B | 261,0 s | 756,5 s | 1.663,1 s | 1,75 | 37,7 Wh |
| Phi-4-mini-instruct | 136,2 s | 213,0 s | 247,9 s | 3,29 | 8,5 Wh |

| Modelo | Energía total | CO2e estimado |
|---|---:|---:|
| GLM-4-9B-Chat | 1,132 kWh | 0,317 kg |
| Qwen3-8B | 2,033 kWh | 0,569 kg |
| Phi-4-mini-instruct | 0,460 kWh | 0,129 kg |

La memoria indicada para los modelos es declarada. No se obtuvo una medición física de VRAM: el equipo utilizó una GPU integrada AMD Radeon 610M y la inferencia se ejecutó en CPU.

## Evaluación de explicaciones

La rúbrica técnica del benchmark y la rúbrica humana v3.0.0 son medidas distintas.

| Modelo | Rúbrica técnica, media (d. e.), n=54 | Rúbrica humana v3.0.0, media (d. e.), n=18 | S humano = Sí | S automático = Sí |
|---|---:|---:|---:|---:|
| GLM-4-9B-Chat | 4,13 (0,81) | 3,82 (0,83) | 14/18 | 23/54 |
| Qwen3-8B | 4,07 (0,71) | 3,65 (1,10) | 13/18 | 15/54 |
| Phi-4-mini-instruct | 3,55 (0,90) | 3,64 (0,84) | 15/18 | 0/54 |

La puntuación técnica procede de rubric_score. La puntuación humana v3.0.0 se calcula como round((C2 + C3 + C4 + C5) / 8 × 5, 2). La variable S humana refleja el juicio de los evaluadores; S automático exige verificación activa con herramientas de solo lectura.

Los valores de concordancia comunicados para la evaluación humana son: kappa de Cohen sobre S de 0,932 (n=41, consenso) y 0,955 (n=54, con dirimente), ICC(2,1) de 0,786, alfa de Krippendorff de 0,787 y kappa ponderado del puntaje total de 0,783. El paquete público no incluye las 108 calificaciones originales E1/E2; por ello estos coeficientes se conservan como valores comunicados y no se presentan como recalculados a partir de los archivos públicos. El informe de concordancia documenta también la diferencia entre n=41 y los 32 casos descritos como consenso espontáneo.

## Comparación multicriterio

El puntaje provisional utiliza la ponderación 40/20/20/20: exactitud completa, rúbrica técnica normalizada, velocidad normalizada y memoria declarada. La memoria no fue medida físicamente.

| Modelo | Puntaje compuesto | Umbral de exactitud de 70 % | Dictamen |
|---|---:|---|---|
| GLM-4-9B-Chat | 0,732 | Cumple (74,1 %) | Elegible; mejor compromiso entre los elegibles |
| Qwen3-8B | 0,722 | Cumple (87,0 %) | Elegible; mayor exactitud completa |
| Phi-4-mini-instruct | 0,801 | No cumple (64,8 %) | No elegible para diagnóstico autónomo |

## Inferencia estadística

La prueba de Friedman sobre diagnóstico completo, con escenario como bloque (n=18), obtuvo χ²=6,82, gl=2 y p=0,033. En las comparaciones pareadas con ajuste de Holm, Qwen3-8B frente a Phi-4-mini-instruct fue significativa (p ajustado=0,041); GLM frente a Qwen quedó en p ajustado=0,053.

La correlación de Spearman entre número de parámetros y métricas, calculada sobre tres tamaños de modelo, fue 0,812 para TTFT, 0,504 para latencia total, 0,504 para energía, −0,396 para velocidad y 0,293 para acierto parcial. Son tendencias descriptivas de esta terna: el tamaño está confundido con la familia del modelo y no permite atribuir causalidad al número de parámetros.

## Entorno de ejecución

La campaña se ejecutó con AMD Ryzen 5 7520U, cuatro núcleos físicos y ocho lógicos, 16 GB LPDDR5 instalados (13,8 GB utilizables), GPU integrada AMD Radeon 610M con 2 GB de memoria compartida y sin sensor de VRAM, Windows 11, Docker Desktop 28.4.0 sobre WSL2 y Ollama 0.34.2. El backend de inferencia fue CPU.

## Reproducibilidad

La configuración de campaña queda registrada en configs/benchmark_config.yaml, configs/models.yaml, configs/hardware_reference.yaml y manifest.json. La instrucción de ejecución documentada es:

    benchapp run-benchmark --seeds 42,1337,2026 --repetitions 1

Esta instrucción describe cómo reproducir la campaña; no se ejecutó una nueva campaña durante la actualización documental.

## Estructura principal

- data/benchmark_results/resultados.csv: dataset canónico.
- data/benchmark_results/traza.jsonl: trazas consolidadas.
- data/benchmark_results/resultados_resumen.md: resumen tabular.
- data/benchmark_results/analisis_correlacional.md: pruebas y asociaciones estadísticas.
- data/human_eval/evaluaciones_adjudicadas.csv: 54 registros consolidados de adjudicación.
- docs/: documentación técnica y de reproducibilidad.
