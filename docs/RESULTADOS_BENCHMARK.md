# Resultados oficiales de NetDiagBench-L7

## 1. Alcance y estructura de los datos

La campaña comprende 162 corridas: tres modelos × 18 escenarios × tres semillas (42, 1337 y 2026), con una ejecución por combinación de modelo, escenario y semilla. De las corridas, 27 utilizaron escenarios emulados en contenedores y 135 escenarios sintéticos deterministas. Las 162 inferencias se realizaron con Ollama y backend CPU.

El archivo canónico es data/benchmark_results/resultados.csv. Su versión publicada contiene 99 columnas: los 98 campos experimentales descritos en el protocolo de campaña y el campo de procedencia human_score_source. Las trazas consolidadas se encuentran en data/benchmark_results/traza.jsonl.

## 2. Precisión diagnóstica

El diagnóstico completo evalúa conjuntamente la causa raíz y la fundamentación técnica. La exactitud estricta evalúa el campo de causa raíz de manera aislada.

| Modelo | DNS (n=15) | HTTP y API (n=27) | TLS (n=12) | Completo (n=54) | Estricto (n=54) | F1 macro (K=18) | Evidencia automática |
|---|---:|---:|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 100,0 % | 59,3 % | 75,0 % | 74,1 % (40) | 61,1 % (33) | 0,757 | 42,6 % (23) |
| Qwen3-8B | 100,0 % | 85,2 % | 75,0 % | 87,0 % (47) | 44,4 % (24) | 0,848 | 27,8 % (15) |
| Phi-4-mini-instruct | 80,0 % | 51,9 % | 75,0 % | 64,8 % (35) | 25,9 % (14) | 0,661 | 0,0 % (0) |
| Total | 93,3 % | 65,4 % | 75,0 % | 75,3 % (122) | 43,8 % (71) | n. a. | 23,5 % (38) |

La diferencia entre exactitud completa y estricta corresponde a 51 corridas (31,5 % del total) clasificadas como aciertos demostrables en el alcance completo, aunque el campo aislado de causa raíz no satisfizo el criterio estricto.

## 3. Tiempo de inferencia

Los valores siguientes corresponden a la Tabla de tiempo de campaña. TTFT es la mediana del tiempo hasta el primer token. La latencia P50 y P95 se informa en segundos; los intervalos se obtuvieron mediante remuestreo por escenario (B=1.000, semilla 42).

| Modelo | TTFT mediano (s) | Decodificación y orquestación, mediana (s) | Latencia P50 (s), IC 95 % | Latencia P95 (s), IC 95 % | Tokens/s |
|---|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 295,5 | 165,4 | 491,6 [451,3; 571,5] | 687,7 [634,6; 734,9] | 2,91 |
| Qwen3-8B | 261,0 | 487,5 | 756,5 [697,1; 952,1] | 1.663,1 [1.343,8; 1.901,5] | 1,75 |
| Phi-4-mini-instruct | 136,2 | 73,4 | 213,0 [200,1; 219,1] | 247,9 [230,7; 269,7] | 3,29 |

Los tiempos absolutos corresponden a inferencia en CPU sobre el equipo registrado. No deben extrapolarse directamente a plataformas con aceleración gráfica.

## 4. Consumo de recursos

| Modelo | CPU media (%) | RAM pico del arnés (GB) | Memoria declarada del modelo (GB) | Energía media por corrida (Wh) | Energía total (kWh) | CO2e total estimado (kg) |
|---|---:|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 67,7 | 0,090 | 5,9 | 21,0 | 1,132 | 0,317 |
| Qwen3-8B | 67,2 | 0,088 | 5,5 | 37,7 | 2,033 | 0,569 |
| Phi-4-mini-instruct | 66,8 | 0,082 | 2,8 | 8,5 | 0,460 | 0,129 |

La memoria de los modelos es declarada. No se obtuvo medición física de VRAM porque el equipo utilizó una GPU integrada AMD Radeon 610M sin sensor de VRAM; el backend de inferencia fue CPU. La energía y el CO2e son estimaciones derivadas del tiempo de ejecución.

## 5. Calidad de las explicaciones y validación humana

Se distinguen la rúbrica técnica del benchmark (54 corridas por modelo) y la rúbrica humana v3.0.0 (18 casos por modelo). La puntuación humana se calcula con los criterios C2 a C5: round((C2 + C3 + C4 + C5) / 8 × 5, 2).

| Modelo | Rúbrica técnica, media (d. e.) | Rúbrica humana v3.0.0, media (d. e.) | S humano = Sí (n=18) | C6 humano, media (0-2) | S automático = Sí (n=54) |
|---|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 4,13 (0,81) | 3,82 (0,83) | 14 | 1,33 | 23 (42,6 %) |
| Qwen3-8B | 4,07 (0,71) | 3,65 (1,10) | 13 | 1,22 | 15 (27,8 %) |
| Phi-4-mini-instruct | 3,55 (0,90) | 3,64 (0,84) | 15 | 1,39 | 0 (0,0 %) |

S humano representa el juicio de los evaluadores sobre el respaldo del diagnóstico en los registros. S automático requiere ejecución efectiva de una herramienta de solo lectura y evidencia verificable. Las dos variables no son equivalentes; la diferencia es especialmente visible en Phi-4-mini-instruct.

Los coeficientes de concordancia comunicados son: kappa de Cohen sobre S de 0,932 (n=41, casos de consenso) y 0,955 (n=54, con dirimente), ICC(2,1)=0,786, alfa de Krippendorff=0,787 y kappa ponderado del puntaje total=0,783. El resumen de la campaña registra 32 casos de consenso espontáneo y 22 casos dirimidos por E3. La diferencia entre n=41 y los 32 casos de consenso queda señalada como limitación documental.

El repositorio público incluye 54 registros adjudicados, pero no contiene los 108 formularios originales de E1 y E2. Por tanto, los coeficientes se conservan como cifras comunicadas y no se afirma que hayan sido recalculados a partir de los archivos públicos.

## 6. Matriz multicriterio

El puntaje provisional aplica S = 0,40·A + 0,20·R + 0,20·V + 0,20·M. A corresponde a exactitud completa; R, a la rúbrica técnica normalizada; V, a la velocidad normalizada respecto del máximo de la terna; y M, a la razón entre la memoria declarada mínima y la memoria declarada del modelo.

| Modelo | Precisión completa / estricta | Latencia P50 / P95 (s) | Energía por corrida / memoria declarada | Rúbrica técnica (humana v3.0.0) / evidencia automática | Puntaje y elegibilidad |
|---|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 74,1 % / 61,1 % | 491,6 / 687,7 | 21,0 Wh / 5,9 GB | 4,13 (3,82) / 42,6 % | 0,732 · Elegible |
| Qwen3-8B | 87,0 % / 44,4 % | 756,5 / 1.663,1 | 37,7 Wh / 5,5 GB | 4,07 (3,65) / 27,8 % | 0,722 · Elegible |
| Phi-4-mini-instruct | 64,8 % / 25,9 % | 213,0 / 247,9 | 8,5 Wh / 2,8 GB | 3,55 (3,64) / 0,0 % | 0,801 · No elegible (<70 %) |

El puntaje compuesto de Phi es superior en valor numérico, pero el modelo no supera el umbral eliminatorio de exactitud completa del 70 %. Entre los modelos elegibles, GLM presenta el mejor compromiso global; Qwen obtiene la mayor exactitud completa.

## 7. Condiciones de interpretación

La campaña se ejecutó con AMD Ryzen 5 7520U, cuatro núcleos físicos y ocho lógicos, 16 GB LPDDR5 instalados (13,8 GB utilizables), AMD Radeon 610M integrada con 2 GB compartidos, Windows 11, Docker Desktop 28.4.0 sobre WSL2 y Ollama 0.34.2. La inferencia se ejecutó en CPU.

Las puntuaciones técnicas 4,13, 4,07 y 3,55 proceden de la rúbrica técnica histórica conservada en rubric_score. La rúbrica humana v3.0.0 se calculó por separado sobre 54 casos. No deben presentarse las medias técnicas como si fueran medias humanas.

La correlación entre parámetros y métricas utiliza solo tres tamaños de modelo y está confundida con la familia arquitectónica y la cuantización. Los resultados describen esta terna; no identifican un efecto causal general del tamaño del modelo.
