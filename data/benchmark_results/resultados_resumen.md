# Resumen de resultados de NetDiagBench-L7

**Dataset:** data/benchmark_results/resultados.csv  
**Tamaño:** 162 corridas, 3 modelos, 18 escenarios, 3 semillas y una ejecución por combinación.  
**Ejecución:** Ollama 0.34.2, inferencia CPU; 27 corridas emuladas y 135 sintéticas deterministas.

## 1. Exactitud diagnóstica

| Modelo | Diagnóstico completo | Causa raíz estricta | F1 macro | Evidencia automática |
|---|---:|---:|---:|---:|
| GLM-4-9B-Chat | 40/54 (74,1 %) | 33/54 (61,1 %) | 0,757 | 23/54 (42,6 %) |
| Qwen3-8B | 47/54 (87,0 %) | 24/54 (44,4 %) | 0,848 | 15/54 (27,8 %) |
| Phi-4-mini-instruct | 35/54 (64,8 %) | 14/54 (25,9 %) | 0,661 | 0/54 (0,0 %) |
| Total | 122/162 (75,3 %) | 71/162 (43,8 %) | n. a. | 38/162 (23,5 %) |

## 2. Tiempo de inferencia

| Modelo | TTFT mediano (s) | Latencia P50 (s) | IC 95 % P50 | Latencia P95 (s) | IC 95 % P95 | Tokens/s |
|---|---:|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 295,5 | 491,6 | [451,3; 571,5] | 687,7 | [634,6; 734,9] | 2,91 |
| Qwen3-8B | 261,0 | 756,5 | [697,1; 952,1] | 1.663,1 | [1.343,8; 1.901,5] | 1,75 |
| Phi-4-mini-instruct | 136,2 | 213,0 | [200,1; 219,1] | 247,9 | [230,7; 269,7] | 3,29 |

IC calculados mediante remuestreo por escenario (B=1.000, semilla 42).

## 3. Recursos

| Modelo | CPU media (%) | RAM pico del arnés (GB) | Memoria declarada (GB) | Energía por corrida (Wh) | Energía total (kWh) | CO2e estimado (kg) |
|---|---:|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 67,7 | 0,090 | 5,9 | 21,0 | 1,132 | 0,317 |
| Qwen3-8B | 67,2 | 0,088 | 5,5 | 37,7 | 2,033 | 0,569 |
| Phi-4-mini-instruct | 66,8 | 0,082 | 2,8 | 8,5 | 0,460 | 0,129 |

La memoria de modelo es declarada. No se midió VRAM física; la inferencia utilizó CPU.

## 4. Calidad de las explicaciones

| Modelo | Rúbrica técnica, media (d. e.), n=54 | Rúbrica humana v3.0.0, media (d. e.), n=18 | S humano = Sí | C6 humano | S automático = Sí |
|---|---:|---:|---:|---:|---:|
| GLM-4-9B-Chat | 4,13 (0,81) | 3,82 (0,83) | 14/18 | 1,33 | 23/54 |
| Qwen3-8B | 4,07 (0,71) | 3,65 (1,10) | 13/18 | 1,22 | 15/54 |
| Phi-4-mini-instruct | 3,55 (0,90) | 3,64 (0,84) | 15/18 | 1,39 | 0/54 |

La rúbrica técnica y la humana son medidas distintas. La rúbrica humana v3.0.0 utiliza C2-C5: round((C2 + C3 + C4 + C5) / 8 × 5, 2).

## 5. Puntaje compuesto provisional

| Modelo | Puntaje | Elegibilidad |
|---|---:|---|
| GLM-4-9B-Chat | 0,732 | Elegible |
| Qwen3-8B | 0,722 | Elegible |
| Phi-4-mini-instruct | 0,801 | No elegible: exactitud completa inferior al 70 % |

La memoria declarada se utiliza como aproximación del componente de memoria; por ello el puntaje es provisional.
