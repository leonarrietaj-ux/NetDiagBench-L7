# Evaluación de compromiso entre modelos

## 1. Criterio multicriterio

El puntaje compuesto provisional utiliza cuatro dimensiones:

\[
S=0,40A+0,20R+0,20V+0,20M
\]

A es la exactitud del diagnóstico completo; R es la rúbrica técnica normalizada; V es la velocidad de generación normalizada respecto del máximo de la terna; M es la razón entre la memoria declarada mínima y la memoria declarada del modelo. La elegibilidad requiere exactitud completa igual o superior al 70 %.

La dimensión R utiliza la rúbrica técnica registrada en rubric_score. La rúbrica humana v3.0.0 se informa aparte y no se sustituye por la puntuación técnica.

## 2. Resultados

| Modelo | Diagnóstico completo | Rúbrica técnica | Rúbrica humana v3.0.0 | Velocidad | Memoria declarada | Puntaje compuesto | Elegibilidad |
|---|---:|---:|---:|---:|---:|---:|---|
| GLM-4-9B-Chat | 74,1 % | 4,13 | 3,82 | 2,91 tok/s | 5,9 GB | 0,732 | Elegible |
| Qwen3-8B | 87,0 % | 4,07 | 3,65 | 1,75 tok/s | 5,5 GB | 0,722 | Elegible |
| Phi-4-mini-instruct | 64,8 % | 3,55 | 3,64 | 3,29 tok/s | 2,8 GB | 0,801 | No elegible |

El valor compuesto de Phi-4-mini-instruct no habilita su selección para diagnóstico autónomo porque su exactitud completa (64,8 %) no alcanza el umbral establecido.

## 3. Perfil de latencia y energía

| Modelo | Latencia P50 | Latencia P95 | Energía por corrida |
|---|---:|---:|---:|
| GLM-4-9B-Chat | 491,6 s | 687,7 s | 21,0 Wh |
| Qwen3-8B | 756,5 s | 1.663,1 s | 37,7 Wh |
| Phi-4-mini-instruct | 213,0 s | 247,9 s | 8,5 Wh |

La campaña se ejecutó en CPU. Ninguno de los modelos produjo diagnósticos en menos de dos minutos y medio; los tiempos medidos se ajustan a procesamiento por lotes o análisis de segunda línea, no a interacción inmediata.

## 4. Selección

GLM-4-9B-Chat presenta el mejor compromiso entre los modelos que superan el umbral: 74,1 % de diagnóstico completo, 42,6 % de sustentación automática, 491,6 s de latencia P50 y 21,0 Wh estimados por corrida. Qwen3-8B obtiene la mayor exactitud completa (87,0 %), aunque su latencia y consumo energético son superiores. Phi-4-mini-instruct ofrece la menor latencia y consumo, pero queda por debajo del umbral de exactitud.

## 5. Límites de interpretación

La memoria de cada modelo es declarada, no una medición física de VRAM. La plataforma de ejecución utilizó GPU integrada AMD Radeon 610M y backend CPU. Por esa razón, el puntaje compuesto se conserva como provisional y sus tiempos no se extrapolan a plataformas con GPU dedicada.
