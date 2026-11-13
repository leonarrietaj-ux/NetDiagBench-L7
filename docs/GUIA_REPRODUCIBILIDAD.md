# Guía de reproducibilidad

## 1. Entorno de la campaña oficial

- Sistema operativo: Windows 11 (10.0.26300).
- Procesador: AMD Ryzen 5 7520U, cuatro núcleos físicos y ocho lógicos.
- Memoria: 16 GB LPDDR5 instalados, 13,8 GB utilizables.
- GPU: AMD Radeon 610M integrada, 2 GB de memoria compartida, sin sensor de VRAM.
- Backend de inferencia: CPU.
- Docker Desktop: 28.4.0 sobre WSL2.
- Ollama: 0.34.2.
- Python: 3.11 o superior.

La campaña se ejecutó con inferencia real en Ollama. No se utilizó el simulador determinista para las 162 corridas oficiales.

## 2. Parámetros congelados

| Parámetro | Valor |
|---|---|
| Modelos | GLM-4-9B-Chat, Qwen3-8B, Phi-4-mini-instruct |
| Escenarios | 18 |
| Semillas | 42, 1337, 2026 |
| Repeticiones por combinación | 1 |
| Total | 162 corridas |
| Temperatura | 0,0 |
| Top-p | 0,9 |
| Contexto | 8.192 tokens |
| Máximo de generación | 1.024 tokens |
| Tiempo límite de lectura | 900 segundos |
| Escenarios emulados | 3 |
| Escenarios sintéticos deterministas | 15 |

Los valores se encuentran en configs/benchmark_config.yaml, configs/models.yaml, configs/hardware_reference.yaml y manifest.json.

## 3. Instalación

Desde la raíz del repositorio:

    python -m venv .venv
    .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    pip install -e . --no-deps

Instalar Ollama y descargar las etiquetas utilizadas:

    ollama pull qwen3:8b
    ollama pull glm4:9b-chat-q4_K_M
    ollama pull phi4-mini:instruct-q4_K_M

La etiqueta phi4-mini:latest se admite como alias local si apunta al mismo archivo de pesos y conserva el mismo SHA-256.

## 4. Ejecución de la campaña

La instrucción de ejecución documentada es:

    benchapp run-benchmark --seeds 42,1337,2026 --repetitions 1

Una ejecución nueva produce mediciones nuevas; no debe confundirse con la campaña congelada que se publica en data/benchmark_results/resultados.csv. La campaña histórica cubrió del 7 de noviembre de 2026 a las 16:55 UTC al 8 de noviembre de 2026 a las 18:46 UTC.

## 5. Artefactos canónicos

- data/benchmark_results/resultados.csv: 162 registros de resultados.
- data/benchmark_results/traza.jsonl: trazas consolidadas.
- data/benchmark_results/resultados_resumen.md: resultados descriptivos.
- data/benchmark_results/analisis_correlacional.md: inferencia estadística.
- manifest.json: diseño experimental, etiquetas de modelos y parámetros.

El CSV publicado tiene 99 columnas. Los resultados de la campaña se deben analizar sin reemplazar mediciones por valores de ejecuciones anteriores.

## 6. Evaluación humana

La muestra humana contiene 54 casos, 18 por modelo. El repositorio publica evaluaciones adjudicadas en data/human_eval/evaluaciones_adjudicadas.csv. Los formularios originales independientes E1/E2 no forman parte de la publicación actual; por tanto, los coeficientes de concordancia se presentan como valores comunicados y no como cálculos reproducidos desde los formularios originales.

## 7. Pruebas de software

El repositorio conserva una suite de pruebas automatizadas para el código. Esta guía no declara resultados de ejecución de dicha suite. La campaña experimental y las pruebas de software son actividades distintas.
