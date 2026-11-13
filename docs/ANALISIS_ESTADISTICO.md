# Análisis estadístico de la campaña

## 1. Comparación de exactitud entre modelos

La unidad de análisis independiente es el escenario. Las tres semillas se promediaron dentro de cada escenario, con 18 bloques.

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

En diagnóstico completo, la diferencia ajustada significativa se presenta entre Qwen3-8B y Phi-4-mini-instruct. En el alcance estricto, la diferencia significativa se presenta entre GLM-4-9B-Chat y Phi-4-mini-instruct.

## 2. Correlación entre parámetros y métricas

La correlación de Spearman se calculó sobre 162 corridas y tres niveles de tamaño (3,8 B, 8,2 B y 9,4 B). Los intervalos se obtuvieron mediante remuestreo por escenario.

| Métrica | ρ de Spearman | IC 95 % | Tendencia |
|---|---:|---:|---|
| TTFT | 0,812 | [0,770; 0,854] | Positiva fuerte |
| Latencia total | 0,504 | [0,486; 0,529] | Positiva moderada |
| Energía estimada | 0,504 | [0,487; 0,527] | Positiva moderada |
| Velocidad de decodificación | −0,396 | [−0,472; −0,314] | Negativa moderada |
| Acierto parcial | 0,293 | [0,172; 0,387] | Positiva débil |

El número de parámetros solo toma tres valores y está confundido con la familia arquitectónica y el esquema de cuantización: GLM ejecutó Q4_0; Qwen y Phi, Q4_K_M. Los coeficientes describen la terna evaluada y no permiten atribuir causalidad al tamaño del modelo.

## 3. Concordancia de la evaluación humana

La evaluación humana se aplicó a 54 casos, 18 por modelo. El resumen de la campaña registra 32 casos de consenso entre E1 y E2 y 22 casos enviados a E3.

| Indicador | Valor comunicado |
|---|---:|
| Kappa de Cohen sobre S, casos de consenso | 0,932 (n=41) |
| Kappa de Cohen sobre S, con dirimente | 0,955 (n=54) |
| ICC(2,1), rúbrica continua | 0,786 |
| Alfa de Krippendorff ordinal | 0,787 |
| Kappa ponderado del puntaje total | 0,783 |

Se mantiene una discrepancia de denominadores: el resumen informa 32 casos de consenso espontáneo, mientras que el coeficiente de kappa para S se reporta con n=41 en el subconjunto de consenso. El repositorio público no contiene los 108 registros originales E1/E2 necesarios para reconstruir el cálculo. Los coeficientes se presentan como valores comunicados, sin afirmar un recálculo independiente.

## 4. Separación de las métricas de calidad

La rúbrica técnica del benchmark se calculó sobre 54 corridas por modelo y produjo medias de 4,13 (GLM), 4,07 (Qwen) y 3,55 (Phi). La rúbrica humana v3.0.0 se aplicó a 18 casos por modelo y utiliza la fórmula:

\[
R_{\mathrm{humana}}=\operatorname{round}\left(\frac{C2+C3+C4+C5}{8}\times 5,\ 2\right)
\]

Las medias comunicadas fueron 3,82, 3,65 y 3,64, respectivamente. La puntuación técnica y la humana miden constructos y muestras diferentes; no deben intercambiarse.

## 5. Fuente canónica

Los resultados diagnósticos y las métricas de rendimiento se encuentran en data/benchmark_results/resultados.csv. Las tablas de campaña se resumen en data/benchmark_results/resultados_resumen.md. Los coeficientes humanos comunicados se documentan en data/human_eval/informe_concordancia.md y data/human_eval/concordancia_resultados.csv.
