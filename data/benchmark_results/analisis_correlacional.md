# Análisis de asociación y comparación entre modelos

## 1. Comparación de exactitud

Unidad independiente: escenario (n=18). Las tres semillas se promediaron dentro de cada escenario.

| Prueba | Comparación | Estadístico | p | p ajustado (Holm) |
|---|---|---:|---:|---:|
| Friedman, diagnóstico completo | Tres modelos | χ²=6,82; gl=2 | 0,033 | n. a. |
| Wilcoxon (Pratt), completo | Qwen3-8B vs. Phi-4-mini | W=10,5 | 0,014 | 0,041 |
| Wilcoxon (Pratt), completo | GLM-4-9B vs. Qwen3-8B | W=12,0 | 0,026 | 0,053 |
| Wilcoxon (Pratt), completo | GLM-4-9B vs. Phi-4-mini | W=48,0 | 0,370 | 0,370 |
| Prueba de signos, completo | Qwen3-8B vs. Phi-4-mini | 8 a favor, 1 en contra | 0,039 | n. a. |
| Friedman, estricto | Tres modelos | χ²=8,33; gl=2 | 0,016 | n. a. |
| Wilcoxon (Pratt), estricto | GLM-4-9B vs. Phi-4-mini | W=0,0 | 0,001 | 0,004 |
| Wilcoxon (Pratt), estricto | GLM-4-9B vs. Qwen3-8B | W=46,5 | 0,204 | 0,407 |
| Wilcoxon (Pratt), estricto | Qwen3-8B vs. Phi-4-mini | W=52,5 | 0,218 | 0,407 |

## 2. Spearman: parámetros frente a métricas

n=162 corridas y tres niveles de tamaño (3,8 B, 8,2 B y 9,4 B). Intervalos de confianza mediante remuestreo por escenario.

| Métrica | ρ | IC 95 % | Tendencia |
|---|---:|---:|---|
| TTFT | 0,812 | [0,770; 0,854] | Positiva fuerte |
| Latencia total | 0,504 | [0,486; 0,529] | Positiva moderada |
| Energía estimada | 0,504 | [0,487; 0,527] | Positiva moderada |
| Velocidad de decodificación | −0,396 | [−0,472; −0,314] | Negativa moderada |
| Acierto parcial | 0,293 | [0,172; 0,387] | Positiva débil |

La terna utiliza tres familias y dos cuantizaciones efectivas: Q4_0 para GLM y Q4_K_M para Qwen y Phi. Los coeficientes describen esta muestra y no permiten atribuir causalidad al número de parámetros.

## 3. Nota de reproducibilidad

Las métricas de concordancia humana se documentan por separado en data/human_eval/informe_concordancia.md. El repositorio no incluye los formularios originales independientes E1/E2, por lo que los coeficientes comunicados no se presentan como recálculos efectuados sobre los archivos públicos.
