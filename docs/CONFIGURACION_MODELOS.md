# Configuración de los modelos evaluados

## 1. Terna experimental

| Identificador | Nombre | Familia | Parámetros | Etiqueta Ollama utilizada | Cuantización declarada | Cuantización efectiva | Memoria declarada |
|---|---|---|---:|---|---|---|---:|
| glm-4-9b-chat | GLM-4-9B-Chat | chatglm | 9,4 B reportados por Ollama; 9,0 B en ficha | glm4:9b-chat-q4_K_M | Q4_K_M en la etiqueta | Q4_0 | 5,9 GB |
| qwen3-8b | Qwen3-8B | qwen3 | 8,2 B | qwen3:8b | Q4_K_M | Q4_K_M | 5,5 GB |
| phi-4-mini-instruct | Phi-4-mini-instruct | phi3 | 3,8 B | phi4-mini:instruct-q4_K_M | Q4_K_M | Q4_K_M | 2,8 GB |

La cuantización efectiva de GLM se verificó en el archivo GGUF: la etiqueta Ollama incluye q4_K_M, pero el archivo ejecutado corresponde a Q4_0. Para Phi, phi4-mini:latest funcionó como alias local del mismo archivo de pesos que phi4-mini:instruct-q4_K_M, con el mismo resumen SHA-256.

## 2. Identidad de pesos

| Modelo | SHA-256 del archivo de pesos |
|---|---|
| GLM-4-9B-Chat | 5b699761eca535dc55047ad9d2dbf54e3b8697709419ef78a70503ed4bfbcf44 |
| Qwen3-8B | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 |
| Phi-4-mini-instruct | 78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753 |

## 3. Parámetros de inferencia

- Motor: Ollama 0.34.2, con llama.cpp como backend interno.
- Temperatura: 0,0.
- Top-p: 0,9.
- Ventana de contexto: 8.192 tokens.
- Máximo de generación: 1.024 tokens.
- Semillas: 42, 1337 y 2026.
- Repeticiones por combinación modelo-escenario-semilla: 1.
- Tiempo límite de lectura de la solicitud: 900 segundos.

Hugging Face Transformers no se utilizó en la campaña. Las 162 inferencias se ejecutaron mediante Ollama en CPU.

## 4. Plataforma de ejecución

La campaña se ejecutó en AMD Ryzen 5 7520U, cuatro núcleos físicos y ocho lógicos, 16 GB LPDDR5 instalados (13,8 GB utilizables), GPU integrada AMD Radeon 610M con 2 GB de memoria compartida y sin sensor de VRAM, Windows 11 (10.0.26300), Docker Desktop 28.4.0 sobre WSL2. El backend de inferencia fue CPU.

Los valores 5,9 GB, 5,5 GB y 2,8 GB corresponden a memoria declarada de los modelos. No representan mediciones físicas de VRAM de la GPU integrada.
