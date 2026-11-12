# Analisis Correlacional y de Significancia Estadistica

**Modulo:** NetDiagBench-L7 / Layer 7 - Statistical Analysis
**Muestras totales:** 162 corridas, 3 modelos evaluados

---

## 1. Correlacion Parametros del Modelo vs Metricas de Rendimiento

Analisis de la relacion entre el numero de parametros del modelo (eje X)
y cada metrica de rendimiento (eje Y), usando correlacion de Spearman (rho)
y Pearson (r) con su p-value asociado.

| Metrica | Spearman rho | p-value | Pearson r | p-value | Significativo (p<0.05) |
|---|---|---|---|---|---|
| TTFT (ms) | 0.8119 | p < 0.001 | 0.8801 | p < 0.001 | Si |
| Tokens/s | -0.3963 | p < 0.001 | -0.569 | p < 0.001 | Si |
| Latencia Total (ms) | 0.5039 | p < 0.001 | 0.5886 | p < 0.001 | Si |
| Energia (kWh) | 0.5044 | p < 0.001 | 0.5874 | p < 0.001 | Si |
| Rubrica (0-5) | 0.2864 | p < 0.001 | 0.3113 | p < 0.001 | Si |
| Puntaje de Coincidencia Parcial | 0.2934 | p < 0.001 | 0.2961 | p < 0.001 | Si |

## 2. Prueba de Kruskal-Wallis: Diferencias entre Modelos

H0: Las distribuciones de la metrica son identicas entre los k modelos.
Se rechaza H0 si p < 0.05.

| Metrica | H Estadistico | p-value | Diferencias Significativas |
|---|---|---|---|
| TTFT (ms) | 114.4049 | p < 0.001 | Si |
| Tokens/s | 132.6446 | p < 0.001 | Si |
| Latencia Total (ms) | 133.9315 | p < 0.001 | Si |
| Energia (kWh) | 133.8047 | p < 0.001 | Si |
| Rubrica (0-5) | 15.3527 | p < 0.001 | Si |
| Puntaje de Coincidencia Parcial | 15.2939 | p < 0.001 | Si |

## 3. Intervalos de Confianza Bootstrap al 95%

| Modelo | Metrica | IC 95% Inferior | IC 95% Superior |
|---|---|---|---|
| **glm-4-9b-chat** | TTFT (ms) | 276966.695 | 300522.3133 |
| **glm-4-9b-chat** | Tokens/s | 2.8807 | 2.937 |
| **glm-4-9b-chat** | Latencia (ms) | 489556.283 | 547867.018 |
| **glm-4-9b-chat** | Energia (kWh) | 0.0198 | 0.0222 |
| **phi-4-mini-instruct** | TTFT (ms) | 129587.0069 | 137789.8807 |
| **phi-4-mini-instruct** | Tokens/s | 3.2437 | 3.3424 |
| **phi-4-mini-instruct** | Latencia (ms) | 203626.193 | 216479.8381 |
| **phi-4-mini-instruct** | Energia (kWh) | 0.0082 | 0.0088 |
| **qwen3-8b** | TTFT (ms) | 243482.0143 | 264297.1289 |
| **qwen3-8b** | Tokens/s | 1.7207 | 1.782 |
| **qwen3-8b** | Latencia (ms) | 838900.1457 | 1032815.0991 |
| **qwen3-8b** | Energia (kWh) | 0.034 | 0.0419 |

## 4. Tamano del Efecto (d de Cohen) entre Pares de Modelos

| Metrica | Comparacion | d de Cohen | Interpretacion |
|---|---|---|---|
| TTFT (ms) | glm-4-9b-chat vs phi-4-mini-instruct | 4.6611 | Efecto grande (Large) |
| TTFT (ms) | glm-4-9b-chat vs qwen3-8b | 0.8214 | Efecto grande (Large) |
| TTFT (ms) | phi-4-mini-instruct vs qwen3-8b | -3.9367 | Efecto grande (Large) |
| Tokens/s | glm-4-9b-chat vs phi-4-mini-instruct | -2.4651 | Efecto grande (Large) |
| Tokens/s | glm-4-9b-chat vs qwen3-8b | 10.5403 | Efecto grande (Large) |
| Tokens/s | phi-4-mini-instruct vs qwen3-8b | 9.6435 | Efecto grande (Large) |
| Latencia Total (ms) | glm-4-9b-chat vs phi-4-mini-instruct | 3.9943 | Efecto grande (Large) |
| Latencia Total (ms) | glm-4-9b-chat vs qwen3-8b | -1.5455 | Efecto grande (Large) |
| Latencia Total (ms) | phi-4-mini-instruct vs qwen3-8b | -2.7993 | Efecto grande (Large) |

## 5. Estadisticos Descriptivos Consolidados por Modelo

| Modelo | Metrica | Media | Sigma | CV% | p50 | p95 | N |
|---|---|---|---|---|---|---|---|
| **glm-4-9b-chat** | TTFT (ms) | 288148.8176 | 44173.7564 | 15.33 | 295931.7 | 372773.78 | 54 |
| **glm-4-9b-chat** | Tokens/s | 2.9102 | 0.1034 | 3.55 | 2.93 | 3.03 | 54 |
| **glm-4-9b-chat** | Latencia (ms) | 516344.7539 | 105628.2208 | 20.46 | 501916.83 | 706684.77 | 54 |
| **glm-4-9b-chat** | VRAM (Declarada/Estimada) Pico (GB) | 5.9 | 0.0 | 0.0 | 5.9 | 5.9 | 54 |
| **glm-4-9b-chat** | RAM Pico (MB) | 92.0196 | 25.4892 | 27.7 | 85.77 | 128.25 | 54 |
| **glm-4-9b-chat** | Energia (kWh) | 0.021 | 0.0043 | 20.45 | 0.0203 | 0.0287 | 54 |
| **glm-4-9b-chat** | Rubrica (0-5) | 4.1296 | 0.8079 | 19.56 | 4.0 | 5.0 | 54 |
| **glm-4-9b-chat** | Puntaje de Coincidencia Parcial | 0.6073 | 0.3117 | 51.32 | 0.66 | 1.0 | 54 |
| **phi-4-mini-instruct** | TTFT (ms) | 133724.1556 | 15618.2668 | 11.68 | 136320.47 | 150892.34 | 54 |
| **phi-4-mini-instruct** | Tokens/s | 3.2931 | 0.1939 | 5.89 | 3.34 | 3.52 | 54 |
| **phi-4-mini-instruct** | Latencia (ms) | 210324.9913 | 24123.7065 | 11.47 | 213264.28 | 248464.14 | 54 |
| **phi-4-mini-instruct** | VRAM (Declarada/Estimada) Pico (GB) | 2.8 | 0.0 | 0.0 | 2.8 | 2.8 | 54 |
| **phi-4-mini-instruct** | RAM Pico (MB) | 83.4776 | 11.7526 | 14.08 | 82.3 | 111.76 | 54 |
| **phi-4-mini-instruct** | Energia (kWh) | 0.0085 | 0.001 | 11.5 | 0.0085 | 0.0102 | 54 |
| **phi-4-mini-instruct** | Rubrica (0-5) | 3.5463 | 0.8969 | 25.29 | 4.0 | 5.0 | 54 |
| **phi-4-mini-instruct** | Puntaje de Coincidencia Parcial | 0.3603 | 0.3428 | 95.15 | 0.2 | 1.0 | 54 |
| **qwen3-8b** | TTFT (ms) | 253500.0587 | 40092.897 | 15.82 | 261629.54 | 328665.68 | 54 |
| **qwen3-8b** | Tokens/s | 1.7533 | 0.1158 | 6.6 | 1.78 | 1.88 | 54 |
| **qwen3-8b** | Latencia (ms) | 928438.7435 | 361994.758 | 38.99 | 761328.4 | 1681854.98 | 54 |
| **qwen3-8b** | VRAM (Declarada/Estimada) Pico (GB) | 5.5 | 0.0 | 0.0 | 5.5 | 5.5 | 54 |
| **qwen3-8b** | RAM Pico (MB) | 90.2759 | 9.6803 | 10.72 | 90.24 | 105.7 | 54 |
| **qwen3-8b** | Energia (kWh) | 0.0377 | 0.0148 | 39.37 | 0.0304 | 0.0689 | 54 |
| **qwen3-8b** | Rubrica (0-5) | 4.0741 | 0.7098 | 17.42 | 4.0 | 5.0 | 54 |
| **qwen3-8b** | Puntaje de Coincidencia Parcial | 0.5435 | 0.3596 | 66.17 | 0.5 | 1.0 | 54 |

## 6. M├®tricas de Clasificaci├│n Diagn├│stica y F1 Macro (Tarea 4.1.3)

| Modelo | F1 Macro | IC 95% Bootstrap F1 | Precisi├│n Macro | Recall Macro |
|---|---|---|---|---|
| **glm-4-9b-chat** | 0.7569 | [0.5622, 0.8708] | 0.8426 | 0.7407 |
| **phi-4-mini-instruct** | 0.6615 | [0.4952, 0.7462] | 0.7972 | 0.6111 |
| **qwen3-8b** | 0.8480 | [0.6420, 0.9679] | 0.8611 | 0.8704 |

## 7. Interpretacion y Conclusiones (Tarea 4.1.2 / OE4)

Se encontraron correlaciones estadisticamente significativas (p < 0.05) entre el numero de parametros del modelo y las siguientes metricas: **TTFT (ms), Tokens/s, Latencia Total (ms), Energia (kWh), Rubrica (0-5), Puntaje de Coincidencia Parcial**.

La prueba de Kruskal-Wallis revela diferencias estadisticamente significativas entre modelos en: **TTFT (ms), Tokens/s, Latencia Total (ms), Energia (kWh), Rubrica (0-5), Puntaje de Coincidencia Parcial** (p < 0.05), lo que confirma que la eleccion del modelo tiene un impacto medible en el rendimiento.

---
*Reporte autogenerado por NetDiagBench-L7 Statistical Analysis Module.*