# Guía de operación de NetDiagBench-L7

## 1. Ejecución y datos

La campaña oficial publicada consta de 162 corridas: tres modelos, 18 escenarios y tres semillas (42, 1337 y 2026), con una ejecución por combinación. Las corridas se ejecutaron con Ollama 0.34.2 en CPU; 27 escenarios se ejecutaron en modo emulado y 135 en modo sintético determinista.

El dataset canónico es data/benchmark_results/resultados.csv y la traza consolidada es data/benchmark_results/traza.jsonl. Los archivos de resumen y análisis se encuentran en data/benchmark_results/.

## 2. Configuración

La configuración de campaña se mantiene en configs/benchmark_config.yaml. La terna y las etiquetas Ollama se describen en configs/models.yaml. La plataforma de referencia y el equipo real de campaña se documentan en configs/hardware_reference.yaml.

Los parámetros efectivos son una repetición por combinación, semillas 42, 1337 y 2026, temperatura 0,0, máximo de 1.024 tokens y tiempo límite de lectura de 900 segundos. La ventana de contexto utilizada fue de 8.192 tokens. El parámetro top-p fue 0,9.

## 3. Interpretación de las métricas

El diagnóstico completo y la causa raíz estricta son métricas diferentes. La rúbrica técnica (rubric_score) también es distinta de la rúbrica humana v3.0.0, que se calcula sobre 18 casos por modelo mediante C2-C5. S humano no equivale a S automático.

La latencia se reporta en segundos. La memoria del modelo es declarada, no una medición física de VRAM. El equipo utilizó GPU integrada AMD Radeon 610M sin sensor de VRAM y ejecutó inferencia en CPU.

## 4. Análisis estadístico

La unidad independiente para la comparación de exactitud es el escenario (n=18); las tres semillas se promedian dentro de cada escenario. La correlación de Spearman se calcula sobre 162 corridas y tres tamaños de modelo. Sus resultados describen esta terna y no permiten atribuir causalidad al tamaño paramétrico.

## 5. Reproducción

La instrucción documentada para ejecutar una nueva campaña es:

    benchapp run-benchmark --seeds 42,1337,2026 --repetitions 1

Una nueva ejecución genera mediciones nuevas y no debe sustituir el dataset oficial congelado sin una nueva versión de campaña y su correspondiente trazabilidad.
