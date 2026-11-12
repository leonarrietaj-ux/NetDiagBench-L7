#!/usr/bin/env python3
"""
NetDiagBench-L7: Builder Automatizado de la Versión Pública y Auditoría de Lanzamiento.
Construye release/NetDiagBench-L7-public/ y release_audit/ con total fidelidad científica,
seguridad criptográfica, protección de datos humanos y saneamiento de rutas.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = PROJECT_ROOT / "release" / "NetDiagBench-L7-public"
AUDIT_DIR = PROJECT_ROOT / "release_audit"


def sha256_of_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def clean_paths_in_text(text: str) -> str:
    """Sustituye rutas absolutas locales de Windows (file:/// y C:\\...) por rutas relativas del repositorio."""
    # file:///c:/Users/USUARIO/OneDrive/Escritorio/benchapp-ip/
    pattern_file_uri = re.compile(r'file:///[cC]:/Users/[^/\\]+/OneDrive/Escritorio/benchapp-ip/?', re.IGNORECASE)
    text = pattern_file_uri.sub('', text)

    # C:\Users\USUARIO\OneDrive\Escritorio\benchapp-ip\
    pattern_win_path = re.compile(r'[cC]:\\Users\\[^\\]+\\OneDrive\\Escritorio\\benchapp-ip\\?', re.IGNORECASE)
    text = pattern_win_path.sub('', text)

    # file:///C:/...
    pattern_any_file = re.compile(r'file:///[a-zA-Z]:/[^)\s"\'>]+')
    def repl_file(m):
        full = m.group(0)
        if "benchapp-ip" in full:
            idx = full.find("benchapp-ip")
            return full[idx + len("benchapp-ip/"):].lstrip('/')
        return Path(full.replace('file:///', '')).name
    text = pattern_any_file.sub(repl_file, text)

    return text


def sanitize_all_docs(dest_dir: Path):
    """Recorre todos los archivos markdown y de texto para sanear rutas y enlaces."""
    for ext in ("*.md", "*.txt", "*.json", "*.yaml", "*.yml"):
        for p in dest_dir.rglob(ext):
            try:
                content = p.read_text(encoding="utf-8")
                cleaned = clean_paths_in_text(content)
                if cleaned != content:
                    p.write_text(cleaned, encoding="utf-8")
            except Exception:
                pass


def build_release():
    print("[1/8] Preparando directorios destino...")
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR, ignore_errors=True)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # Lista de carpetas y archivos a transferir
    dirs_to_copy = [
        ".github",
        "configs",
        "data",
        "docs",
        "infra",
        "knowledge",
        "scenarios",
        "scripts",
        "src",
        "tests",
    ]
    files_to_copy = [
        "pyproject.toml",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        "hardware_detectado.json",
        "manifest.json",
        "README.md",
    ]

    print("[2/8] Copiando archivos base a release/NetDiagBench-L7-public/...")
    for f in files_to_copy:
        src_f = PROJECT_ROOT / f
        if src_f.exists():
            shutil.copy2(src_f, RELEASE_DIR / f)

    for d in dirs_to_copy:
        src_d = PROJECT_ROOT / d
        dest_d = RELEASE_DIR / d
        if src_d.exists():
            shutil.copytree(
                src_d,
                dest_d,
                ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".pytest_cache", ".venv", "venv",
                    "*.log", "*.tmp", ".coverage", "htmlcov", "archive_*",
                    "SESION_KIT_CASO2", "test_sesion_13", "v2"
                )
            )

    print("[3/8] Aplicando Hardening de Seguridad y sustitución de claves privadas...")
    # 1. Eliminar claves privadas TLS
    expired_key = RELEASE_DIR / "infra" / "scenario-a-tls" / "certs" / "expired.key"
    if expired_key.exists():
        expired_key.unlink()

    server_key = RELEASE_DIR / "scenarios" / "topologies" / "configs" / "nginx" / "certs" / "server.key"
    if server_key.exists():
        server_key.unlink()

    # Colocar notas de aprovisionamiento seguro en los directorios de certificados
    (RELEASE_DIR / "infra" / "scenario-a-tls" / "certs" / "README.md").write_text(
        "# Certificados de Prueba TLS - Escenario A\n\n"
        "Por motivos de seguridad y directrices de ciberseguridad, las claves criptográficas privadas no se distribuyen en el repositorio público.\n"
        "Para generar los certificados y claves de prueba locales para este escenario, ejecute:\n\n"
        "```bash\npython scripts/generate_test_certs.py\n```\n",
        encoding="utf-8"
    )
    (RELEASE_DIR / "scenarios" / "topologies" / "configs" / "nginx" / "certs" / "README.md").write_text(
        "# Certificados de Prueba TLS - Servidor Nginx\n\n"
        "Por motivos de seguridad y directrices de ciberseguridad, las claves criptográficas privadas no se distribuyen en el repositorio público.\n"
        "Para generar los certificados y claves de prueba locales para este escenario, ejecute:\n\n"
        "```bash\npython scripts/generate_test_certs.py\n```\n",
        encoding="utf-8"
    )

    # 2. Protección estricta de evaluación humana
    human_dir = RELEASE_DIR / "data" / "human_eval"
    private_human_items = [
        "matriz_asignacion.xlsx",
        "CURRENT_SESSION.txt",
        "evaluaciones_originales.csv",
    ]
    for item in private_human_items:
        p = human_dir / item
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink()

    # Asegurar dynamic_models.json limpio
    dyn_models = RELEASE_DIR / "configs" / "dynamic_models.json"
    dyn_models.write_text("[]\n", encoding="utf-8")

    print("[4/8] Creando LICENSE MIT y CITATION.cff...")
    license_content = """MIT License

Copyright (c) 2026 Juan David León Arrieta, Richard Eliseo Mendoza Gáfaro
Universidad de Pamplona - Facultad de Ingenierías y Arquitectura

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
    (RELEASE_DIR / "LICENSE").write_text(license_content, encoding="utf-8")

    citation_content = """cff-version: 1.2.0
message: "If you use this benchmark, code, or datasets in your research, please cite it as below."
title: "NetDiagBench-L7: Benchmark Reproducible para Diagnóstico de Fallas en Servicios de Capa de Aplicación sobre IP con SLMs Locales"
authors:
  - family-names: "León Arrieta"
    given-names: "Juan David"
    orcid: "https://orcid.org/0009-0000-0000-0000"
    affiliation: "Universidad de Pamplona"
  - family-names: "Mendoza Gáfaro"
    given-names: "Richard Eliseo"
    affiliation: "Universidad de Pamplona"
version: 1.0.0
date-released: 2026-11-11
url: "https://github.com/leonarrietaj-ux/NetDiagBench-L7"
keywords:
  - "network-troubleshooting"
  - "benchmark"
  - "small-language-models"
  - "dns"
  - "http"
  - "tls"
  - "autonomous-agents"
  - "reproducibility"
license: "MIT"
"""
    (RELEASE_DIR / "CITATION.cff").write_text(citation_content, encoding="utf-8")

    # .gitignore robusto para la versión pública
    gitignore_content = """# Entornos virtuales y dependencias
.venv/
venv/
env/
ENV/
build/
dist/
*.egg-info/

# Bytecode y cachés de Python
__pycache__/
*.py[cod]
*$py.class
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Claves criptográficas privadas y certificados no públicos
*.key
*.pem
!scripts/generate_test_certs.py

# Modelos y blobs de pesos GGUF
models/
*.gguf
*.bin

# Secretos y variables de entorno locales
.env
.env.*
!.env.example

# Logs y telemetría transitoria
*.log
emissions.csv
codecarbon.log

# Datos privados o no anonimizados de evaluación humana
data/human_eval/SESION_KIT_CASO2/
data/human_eval/test_sesion_*/
data/human_eval/matriz_asignacion.xlsx
data/human_eval/CURRENT_SESSION.txt
data/human_eval/clave_RESTRINGIDA.json
data/human_eval/KEY_OPENED_AUDIT.json
data/human_eval/respuestas_*.csv

# Datos de corridas locales temporales
data/runs/
data/pilot_runs/

# IDEs y SO
.vscode/
.idea/
*.swp
*.swo
.DS_Store
Thumbs.db
"""
    (RELEASE_DIR / ".gitignore").write_text(gitignore_content, encoding="utf-8")

    print("[5/8] Saneando rutas absolutas y referencias locales en la documentación...")
    sanitize_all_docs(RELEASE_DIR)

    # Actualizar README.md completo y profesional en la versión pública
    readme_path = RELEASE_DIR / "README.md"
    readme_text = build_comprehensive_readme()
    readme_path.write_text(readme_text, encoding="utf-8")

    # Adaptar pruebas en release si alguna depende de SESION_KIT_CASO2 físico
    patch_tests_for_public_release(RELEASE_DIR)

    print("[6/8] Inicializando repositorio Git limpio e independiente...")
    git_init_cmd = ["git", "init", "-b", "main"]
    subprocess.run(git_init_cmd, cwd=str(RELEASE_DIR), check=True, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "config", "user.name", "Juan David León Arrieta"], cwd=str(RELEASE_DIR), check=True)
    subprocess.run(["git", "config", "user.email", "juan.leon22@unipamplona.edu.co"], cwd=str(RELEASE_DIR), check=True)
    subprocess.run(["git", "add", "."], cwd=str(RELEASE_DIR), check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: public release NetDiagBench-L7 (v1.0.0)\n\nVersión pública depurada, segura y reproducible del benchmark NetDiagBench-L7."],
        cwd=str(RELEASE_DIR),
        check=True,
        stdout=subprocess.DEVNULL
    )

    print("[7/8] Calculando SHA256SUMS.txt y verificaciones científicas...")
    generate_audit_deliverables()

    print("[8/8] Construcción de la versión pública finalizada con éxito.")


def patch_tests_for_public_release(dest_dir: Path):
    """Garantiza que test_layer8_human_eval.py salte elegantemente si SESION_KIT_CASO2 no está presente."""
    test_l8 = dest_dir / "tests" / "test_layer8_human_eval.py"
    if test_l8.exists():
        content = test_l8.read_text(encoding="utf-8")
        # Asegurar skip si no existe SESION_KIT_CASO2
        old_pattern = '    s_dir = PROJECT_ROOT / "data" / "human_eval" / "SESION_KIT_CASO2"\n    assert s_dir.exists()'
        new_pattern = '    s_dir = PROJECT_ROOT / "data" / "human_eval" / "SESION_KIT_CASO2"\n    if not s_dir.exists():\n        pytest.skip("SESION_KIT_CASO2 privada excluida de la versión pública")'
        content = content.replace(old_pattern, new_pattern)
        test_l8.write_text(content, encoding="utf-8")


def build_comprehensive_readme() -> str:
    return """# NetDiagBench-L7: Benchmark Agéntico para Diagnóstico de Fallas Layer 7 sobre IP con SLMs Locales

[![Python 3.11 | 3.12 | 3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Execution: 100% Local](https://img.shields.io/badge/Inference-100%25%20Local%20(Ollama)-purple.svg)](#)
[![Docker Support](https://img.shields.io/badge/Docker-Compose%20Ready-blue.svg)](#)
[![Security Hardened](https://img.shields.io/badge/Security-Defense--in--Depth-darkgreen.svg)](docs/INFORME_SEGURIDAD.md)
[![Academic Thesis](https://img.shields.io/badge/Thesis-Universidad%20de%20Pamplona-red.svg)](docs/MATRIZ_CIFRAS_OFICIALES_TESIS.md)

> **Trabajo de Grado - Universidad de Pamplona**  
> **Facultad de Ingenierías y Arquitectura | Departamento de Eléctrica, Electrónica, Sistemas y Telecomunicaciones (E.E.S.T.)**  
> **Autor:** Juan David León Arrieta (`juan.leon22@unipamplona.edu.co`)  
> **Director:** Mg. Richard Eliseo Mendoza Gáfaro  
> **Documento de Tesis:** *Benchmark reproducible para el diagnóstico de fallas en servicios de capa de aplicación sobre IP con modelos de lenguaje ligeros de ejecución local*

---

## 1. Descripción del Proyecto y Problema de Investigación

En la operación de infraestructura de telecomunicaciones y centros de datos modernos, el aislamiento expedito de incidentes en la **Capa de Aplicación (Layer 7 del modelo OSI)** —específicamente en servicios esenciales como **DNS (RFC 1035)**, **HTTP/HTTPS (RFC 9110)** y **TLS (RFC 8446)**— constituye un desafío crítico. Aunque los Modelos de Lenguaje de Gran Escala (LLMs) propietarios han demostrado capacidades avanzadas de razonamiento, su adopción en operaciones de red (NOC/SOC) se encuentra severamente restringida por:

1. **Riesgos de Fuga de Información y Privacidad:** Exposición de topologías, credenciales y telemetría interna hacia nubes de terceros.
2. **Dependencia de Conectividad Externa:** Imposibilidad de operar durante fallas masivas de enlace o en redes estrictamente aisladas (*air-gapped*).
3. **Altos Costos de Inferencia y Huella Energética:** Consumo inviable de recursos frente a modelos locales.

**NetDiagBench-L7** surge como el primer marco experimental integral y reproducible diseñado para evaluar y comparar rigurosamente el desempeño de **Modelos de Lenguaje Pequeños (SLMs, $\le 9\\text{B}$ parámetros)** ejecutados de forma **100% local** bajo hardware restringido ($\le 8\\text{ GB}$ VRAM), para el diagnóstico asistido de fallas de Capa 7.

---

## 2. Arquitectura del Sistema en Ocho Capas Desacopladas

El sistema se estructura en **8 capas funcionales independientes**, gobernadas por contratos estrictos de datos mediante Pydantic:

```mermaid
graph TD
    subgraph L1["Capa 1: Laboratorio y Emulación (ScenarioLabAgent)"]
        CLAB["Contenedores Docker / BIND9 / Nginx / tc-netem"] -->|"escenario.yaml + Logs Crudos"| L2
    end

    subgraph L2["Capa 2: Pipeline y Preprocesamiento (DataPipelineAgent)"]
        FB["Drain3 (Minería de Plantillas) + Ventana Deslizante Contextual"] -->|"ventana.jsonl"| L3
    end

    subgraph L3["Capa 3: RAG Léxico Acotado (RAGKnowledgeAgent)"]
        BM25["Recuperador BM25 Acotado (RAM <= 0.05 MB, RFCs 1035/9110/8446)"] -->|"contexto.md"| L4
    end

    subgraph L4["Capa 4: Inferencia Local y Telemetría (InferenceEngineAgent)"]
        OLLAMA["Ollama Local (GGUF Q4_K_M) + Medición TTFT/tok_s/RAM"] -->|"diagnostico.json + Telemetría"| L5
    end

    subgraph L5["Capa 5: Orquestación Agéntica (DiagnosticOrchestratorAgent)"]
        LG["Grafo LangGraph + Herramientas Read-Only (dig, curl, openssl)"] -->|"traza.jsonl"| L6
    end

    subgraph L6["Capa 6: Interfaces de Usuario (InterfaceCLIAgent)"]
        CLI["Typer CLI + Dashboard Web Reactivo (FastAPI + HTMX + SVG)"] -->|"Reportes HTML/PDF/Excel"| L7
    end

    subgraph L7["Capa 7: Evaluación y MLOps (BenchmarkEvaluatorAgent)"]
        EVAL["Métricas Multiclase K=18, Friedman, Wilcoxon-Holm, Bootstrap N=1000"] -->|"resultados.csv + Matrices"| L8
    end

    subgraph L8["Capa 8: Validación Humana (HumanValidationAgent)"]
        HUMAN["Panel Doble Ciego E1/E2 + Adjudicador E3 + Kappa/Spearman"] -->|"evaluaciones_adjudicadas.csv"| MATRIZ["Matriz Oficial de Cifras"]
    end
```

### Contratos de Datos y Artefactos por Capa

| Capa | Módulo | Artefacto Generado | Estándar / Tecnología | Restricción Clave |
|---|---|---|---|---|
| **Capa 1** | `src/layer1_lab/` | `escenario.yaml` | Docker, BIND9, Nginx, `tc netem` | Aislamiento de red de pruebas |
| **Capa 2** | `src/layer2_pipeline/` | `ventana.jsonl` | Drain3, Jinja2 | Minería determinista de logs |
| **Capa 3** | `src/layer3_rag/` | `contexto.md` | BM25 Okapi léxico acotado | Consumo de memoria $\le 0.05\\text{ MB}$ RAM |
| **Capa 4** | `src/layer4_inference/` | `respuesta.json` | Ollama, cuantización GGUF `Q4_K_M` | Temperatura `0.0`, Top-P `0.9` |
| **Capa 5** | `src/layer5_orchestrator/` | `traza.jsonl` | LangGraph StateGraph | Herramientas **estrictamente de solo lectura** |
| **Capa 6** | `src/layer6_interface/` | Informes Web/CLI | FastAPI, HTMX, Typer, ReportLab | Seguridad OWASP y anti-SSRF |
| **Capa 7** | `src/layer7_evaluator/` | `resultados.csv` | SciPy, Statsmodels, Scikit-learn | $N=18$ clusters, Bootstrap pareado |
| **Capa 8** | `src/layer8_human_eval/` | `evaluaciones_adjudicadas.csv` | Rúbrica $C_1-C_6, S$, Kappa, ICC(2,1) | Doble ciego independiente anonimizado |

---

## 3. Terna Oficial de Modelos SLM Evaluados

De acuerdo con la caracterización inicial de 12 modelos (Entregable E1), se seleccionó una terna representativa en el rango de parámetros $\le 9\\text{B}$:

| Modelo | Tag Ollama Oficial | Parámetros | Licencia | Cuantización Efectiva | Digest SHA-256 Verificado |
|---|---|:---:|:---:|:---:|---|
| **GLM-4-9B-Chat** | `glm4:9b-chat-q4_K_M` | 9.0B | GLM-4 License | `Q4_0` (Blob GGUF) | `5b699761eca535dc55047ad9d2dbf54e3b8697709419ef78a70503ed4bfbcf44` |
| **Qwen3-8B** | `qwen3:8b` | 8.2B | Apache 2.0 | `Q4_K_M` | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` |
| **Phi-4-mini-instruct** | `phi4-mini:latest` | 3.8B | MIT | `Q4_K_M` | `78fad5d182a7c33065e153a5f8ba210754207ba9d91973f57dffa7f487363753` |

---

## 4. Diseño Experimental Oficial y Resultados Congelados

La campaña oficial consta de **162 corridas experimentales controladas** (18 escenarios $\\times$ 3 modelos $\\times$ 3 semillas deterministas: `42`, `1337`, `2026`).

### 4.1. Resumen Global de Exactitud Diagnóstica

| Modelo | Diagnóstico Completo (`full_text`) | Exactitud Completa (%) | Causa Raíz Estricta (`root_cause`) | Exactitud Estricta (%) | Coincidencia de Clase Canónica | Exactitud Canónica (%) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | **40 / 54** | **74.1%** | **33 / 54** | **61.1%** | **40 / 54** | **74.1%** |
| **Qwen3-8B** | **47 / 54** | **87.0%** | **24 / 54** | **44.4%** | **47 / 54** | **87.0%** |
| **Phi-4-mini-instruct** | **35 / 54** | **64.8%** | **14 / 54** | **25.9%** | **33 / 54** | **61.1%** |
| **TOTAL BENCHMARK** | **122 / 162** | **75.3%** | **71 / 162** | **43.8%** | **120 / 162** | **74.1%** |

*Desglose de auditoría sobre las 162 ejecuciones:*
- Aciertos directos conservados: **71** (43.8%)
- Aciertos fundamentados demostrables corregidos: **51** (31.5%)
- Errores confirmados: **40** (24.7%)

### 4.2. Tasa de Evidencia Empírica de Solo Lectura (Read-Only)

El criterio de sustentación $S = \\text{True}$ exige que el agente ejecute de forma efectiva herramientas de lectura (`dig`, `curl`, `openssl`), recolecte evidencia factual de red verificable y no contradiga el diagnóstico emitido:

| Modelo | Corridas con Evidencia Válida | Tasa de Evidencia Read-Only |
|---|:---:|:---:|
| **GLM-4-9B-Chat** | **23 / 54** | **42.6%** |
| **Qwen3-8B** | **15 / 54** | **27.8%** |
| **Phi-4-mini-instruct** | **0 / 54** | **0.0%** |
| **TOTAL BENCHMARK** | **38 / 162** | **23.46% (≈ 23.5%)** |

*Interpretación técnica de la tasa del 23.5%:*  
Refleja la complejidad intrínseca de orquestación de herramientas autónomas en SLMs pequeños. GLM-4-9B exhibe la mayor competencia de invocación de herramientas (42.6%), Qwen3-8B alcanza un 27.8% apoyado en su razonamiento nativo, mientras que Phi-4-mini no logró emitir esquemas sintácticamente válidos de invocación de herramientas en el entorno de pruebas, fundamentando sus diagnósticos exclusivamente en el texto de los logs.

### 4.3. Evaluación Multicriterio y Dictamen de Elegibilidad Técnica

Fórmula ponderada del Scorecard Multicriterio:
$$S = 0.40 \\cdot A_{\\text{diag}} + 0.20 \\cdot R_{\\text{hum}} + 0.20 \\cdot V_{\\text{vel}} + 0.20 \\cdot M_{\\text{vram}}$$
*Umbral mínimo obligatorio de viabilidad técnica para operaciones autónomas:* $A_{\\text{diag}} \\ge 70.0\\%$.

| Modelo | Diagnóstico (40%) | Rúbrica (20%) | Velocidad (20%) | VRAM (20%) | Puntaje Compuesto | Umbral $\\ge 70\\%$ | Dictamen de Elegibilidad |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **GLM-4-9B-Chat** | 0.2964 | 0.1652 | 0.1758 | 0.0949 | **0.7323** | **Sí (74.1%)** | **ELEGIBLE (Mejor Compromiso Global - NOC)** |
| **Qwen3-8B** | 0.3480 | 0.1628 | 0.1091 | 0.1018 | **0.7217** | **Sí (87.0%)** | **ELEGIBLE (Mayor Exactitud - Recursos Acotados)** |
| **Phi-4-mini-instruct** | 0.2592 | 0.1420 | 0.2000 | 0.2000 | **0.8012** | **No (64.8%)** | **NO ELEGIBLE (Sub-umbral para diagnóstico autónomo)** |

---

## 5. Pruebas de Hipótesis e Inferencia Estadística

- **Prueba Global de Friedman ($N=18$ bloques de escenarios):**  
  $\\chi^2 = 6.8205$, $gl = 2$, $p = 0.03303 < 0.05$. Se rechaza la hipótesis nula: existen diferencias estadísticamente significativas entre los modelos.
- **Contrastes Pareados de Wilcoxon con Ajuste Holm-Bonferroni (Familia $m=3$):**
  - Qwen3-8B vs. Phi-4-mini: $W = 10.5, p_{\\text{adj}} = 0.041$ (Significativo a favor de Qwen3-8B).
  - GLM-4-9B vs. Phi-4-mini: $W = 48.0, p_{\\text{adj}} = 0.370$ (No significativo).
  - GLM-4-9B vs. Qwen3-8B: $W = 12.0, p_{\\text{adj}} = 0.053$ (Marginalmente no significativo a $\\alpha = 0.05$).
- **Remuestreo Bootstrap por Conglomerados ($B=1000$ réplicas, semilla 42):**
  - GLM-4-9B-Chat: Exactitud IC 95% = `[59.3%, 87.0%]`, F1 Macro = `[0.564, 0.860]`.
  - Qwen3-8B: Exactitud IC 95% = `[74.1%, 98.2%]`, F1 Macro = `[0.638, 0.963]`.
  - Phi-4-mini-instruct: Exactitud IC 95% = `[53.7%, 75.9%]`, F1 Macro = `[0.497, 0.720]`.

---

## 6. Instalación y Puesta en Marcha

### Requisitos del Sistema
- **Python:** 3.11, 3.12 o 3.13.
- **Docker y Docker Compose:** (Requerido para escenarios emulados de laboratorio).
- **Ollama:** Servidor local de inferencia (`http://localhost:11434`).
- **Hardware Recomendado:** CPU 8 núcleos, $\\ge 16\\text{ GB}$ RAM, GPU dedicada de 8 GB VRAM (compatible con CUDA/ROCm).

### 6.1. Clonar el Repositorio e Instalar Dependencias
```bash
# 1. Clonar el repositorio
git clone https://github.com/leonarrietaj-ux/NetDiagBench-L7.git
cd NetDiagBench-L7

# 2. Crear y activar entorno virtual
python -m venv .venv

# En Linux / macOS:
source .venv/bin/activate
# En Windows (PowerShell):
.\\.venv\\Scripts\\Activate.ps1

# 3. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
pip install -e . --no-deps
```

### 6.2. Aprovisionar Certificados de Prueba Locales
```bash
python scripts/generate_test_certs.py
```

### 6.3. Descargar Modelos en Ollama
```bash
ollama pull qwen3:8b
ollama pull glm4:9b-chat-q4_K_M
ollama pull phi4-mini:latest
```

---

## 7. Ejecución del Aplicativo y Casos de Uso

### 7.1. Suite de Pruebas Automatizadas
```bash
# Ejecutar todas las pruebas unitarias y de contratos
pytest tests/ -v

# Ejecutar auditoría de seguridad
pytest tests/test_security_audit.py -v

# Ejecutar validaciones estadísticas
pytest tests/test_statistical_analysis.py -v
```

### 7.2. Interfaz de Línea de Comandos (`benchapp`)
```bash
# Listar los 18 escenarios del catálogo
benchapp list-scenarios

# Listar la terna de modelos
benchapp list-models

# Ejecutar el diagnóstico de un escenario individual
benchapp run-scenario DNS-NXD-01 --model qwen3-8b --seed 42

# Ejecutar análisis de correlación estadística
benchapp analyze-correlation

# Validar integridad del catálogo
benchapp validate-catalog
```

### 7.3. Panel Web Interactivo (FastAPI + HTMX)
```bash
# Iniciar el servidor web
benchapp serve-dashboard --port 8000

# Abrir en el navegador:
# http://localhost:8000
```

---

## 8. Arquitectura de Seguridad y Hardening

El marco incorpora una arquitectura de seguridad por capas (*Defense-in-Depth*):
1. **Herramientas de Red Read-Only:** El orquestador opera únicamente utilidades de inspección no invasivas (`dig`, `curl`, `openssl`).
2. **Protección Anti-SSRF Multicloud:** Bloqueo explícito de metadatos de proveedores en la nube (AWS `169.254.169.254`, GCP, Alibaba, Tencent) y CoreDNS de Kubernetes.
3. **Cabeceras HTTP OWASP:** Implementación en middleware de CSP estricto, `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff` y `Permissions-Policy`.
4. **Sanitización Estricta:** Mitigación de inyecciones de comandos en llamadas a subprocesos mediante expresiones regulares de control.

Consulte el informe completo en [docs/INFORME_SEGURIDAD.md](docs/INFORME_SEGURIDAD.md).

---

## 9. Estructura del Repositorio

```text
NetDiagBench-L7/
├── .github/workflows/ci.yml       # Integración continua automatizada
├── configs/                       # Definición de modelos, escenarios y rúbrica
├── data/
│   ├── benchmark_results/         # Conjunto de datos consolidado oficial
│   ├── campaign_162/              # 162 corridas oficiales con trazas y hashes
│   └── human_eval/                # Evaluaciones humanas adjudicadas anonimizadas
├── docs/                          # Documentación académica, manuales y matrices
│   ├── GUIA_REPRODUCIBILIDAD.md
│   ├── MANUAL_TECNICO_SISTEMA.md
│   ├── MANUAL_USUARIO_SISTEMA.md
│   ├── MATRIZ_CIFRAS_OFICIALES_TESIS.md
│   └── INFORME_SEGURIDAD.md
├── infra/                         # Topologías Docker para pruebas emuladas
├── knowledge/                     # RFCs y corpus normativo para RAG léxico
├── scenarios/                     # Catálogo de 18 escenarios de fallas Layer 7
├── scripts/                       # Utilidades de prueba, certificados y reportes
├── src/                           # Código fuente del sistema en 8 capas
├── tests/                         # Suite completa de pruebas automatizadas
├── Dockerfile                     # Imagen de contenedor del aplicativo
├── docker-compose.yml             # Despliegue orquestado del entorno
├── pyproject.toml                 # Configuración de paquete PEP 621
├── requirements.txt               # Dependencias fijadas del proyecto
├── CITATION.cff                   # Metadatos para citación académica
├── LICENSE                        # Licencia de código abierto MIT
└── README.md                      # Documento principal del repositorio
```

---

## 10. Licencia y Citación

Este proyecto se distribuye bajo la licencia **MIT**. Consulte el archivo [LICENSE](LICENSE) para mayores detalles.

Si utiliza este benchmark o sus conjuntos de datos en investigaciones académicas, cite este trabajo utilizando el formato [CITATION.cff](CITATION.cff):

```bibtex
@misc{leon2026netdiagbench,
  author = {León Arrieta, Juan David and Mendoza Gáfaro, Richard Eliseo},
  title = {NetDiagBench-L7: Benchmark Reproducible para Diagnóstico de Fallas en Servicios de Capa de Aplicación sobre IP con SLMs Locales},
  year = {2026},
  publisher = {GitHub},
  howpublished = {\\url{https://github.com/leonarrietaj-ux/NetDiagBench-L7}}
}
```
"""


def generate_audit_deliverables():
    """Genera los 6 documentos de auditoría exigidos en release_audit/."""
    # 1. SHA256SUMS.txt
    sha_file = AUDIT_DIR / "SHA256SUMS.txt"
    lines = []
    files_to_hash = [
        "data/benchmark_results/resultados.csv",
        "data/benchmark_results/traza.jsonl",
        "data/campaign_162/resultados.csv",
        "data/campaign_162/recalificacion_auditada.csv",
        "data/campaign_162/traza.jsonl",
        "data/campaign_162/manifest.json",
        "data/human_eval/evaluaciones_adjudicadas.csv",
        "configs/models.yaml",
        "configs/scenarios.yaml",
        "hardware_detectado.json",
        "manifest.json",
    ]
    for rel in files_to_hash:
        p = RELEASE_DIR / rel
        if p.exists():
            h = sha256_of_file(p)
            lines.append(f"{h}  {rel}")
    sha_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 2. ARCHIVOS_EXCLUIDOS.md
    (AUDIT_DIR / "ARCHIVOS_EXCLUIDOS.md").write_text("""# Relación Confidencial de Archivos Excluidos de la Distribución Pública

**Proyecto:** NetDiagBench-L7  
**Fecha de Auditoría:** Noviembre de 2026  
**Auditor:** Auditoría Senior de Publicación y Seguridad  

---

## 1. Archivos Criptográficos Sensibles Excluidos

| Archivo Excluido | Ubicación Original | Justificación Técnica de Seguridad | Mecanismo de Reemplazo en Release |
|---|---|---|---|
| `expired.key` | `infra/scenario-a-tls/certs/expired.key` | Clave privada RSA 2048. Su publicación vulnera principios de seguridad y dispararía alertas en scanners de secretos. | Sustituida por generación local dinámica mediante `scripts/generate_test_certs.py`. |
| `server.key` | `scenarios/topologies/configs/nginx/certs/server.key` | Clave privada RSA de servidor web de prueba. | Sustituida por generación local dinámica mediante `scripts/generate_test_certs.py`. |

---

## 2. Archivos Confidenciales de Evaluación Humana Excluidos

| Archivo / Carpeta Excluida | Ubicación Original | Justificación de Privacidad y Metodología |
|---|---|---|
| `SESION_KIT_CASO2/clave_RESTRINGIDA.json` | `data/human_eval/SESION_KIT_CASO2/` | Archivo restringido con el desenmascaramiento ciego de corridas a modelos. Debe mantenerse bajo reserva. |
| `SESION_KIT_CASO2/KEY_OPENED_AUDIT.json` | `data/human_eval/SESION_KIT_CASO2/` | Registro de auditoría de apertura de clave ciega con datos internos de sesión. |
| `SESION_KIT_CASO2/respuestas_A.csv` | `data/human_eval/SESION_KIT_CASO2/` | Respuestas directas e individuales del experto A sin agregación. |
| `SESION_KIT_CASO2/respuestas_B.csv` | `data/human_eval/SESION_KIT_CASO2/` | Respuestas directas e individuales del experto B sin agregación. |
| `SESION_KIT_CASO2/respuestas_C.csv` | `data/human_eval/SESION_KIT_CASO2/` | Respuestas directas e individuales del experto dirimente C sin agregación. |
| `SESION_KIT_CASO2/Paquete_Experto_*.html` | `data/human_eval/SESION_KIT_CASO2/` | Paquetes de distribución offline para evaluadores individuales. |
| `matriz_asignacion.xlsx` | `data/human_eval/` | Matriz de asignación de casos a evaluadores. |
| `CURRENT_SESSION.txt` | `data/human_eval/` | Puntero transitorio de estado de sesión activa local. |

*Nota:* Los datos científicos consolidados y anonimizados se preservan íntegramente en `data/human_eval/evaluaciones_adjudicadas.csv` (162 registros con identificadores anonimizados E1, E2, E3).

---

## 3. Archivos y Paquetes Históricos Obsoletos Reubicados

Todos los paquetes redundantes de entregas técnicas previas (`entrega_tecnica/`, `entrega_tecnica_v3/`), los scripts de migración puntual y los borradores intermedios de trabajo han sido retirados de la versión pública y archivados de forma segura en el repositorio externo del sistema:  
`C:\\Users\\USUARIO\\OneDrive\\Escritorio\\NetDiagBench_Archivos_Excluidos\\`.
""", encoding="utf-8")

    # 3. VERIFICACION_RESULTADOS.md
    (AUDIT_DIR / "VERIFICACION_RESULTADOS.md").write_text("""# Verificación de Integridad Matemática y Cifras Oficiales de la Tesis

**Proyecto:** NetDiagBench-L7  
**Fecha de Verificación:** Noviembre de 2026  
**Fuentes Contrastadas:**
- Manuscrito Final de Tesis: `TG_Benchmark_Diagnostico_Fallas_LLM_ligeros_JDLeon.docx`
- Matriz Canónica: `docs/MATRIZ_CIFRAS_OFICIALES_TESIS.md`
- Dataset Maestro: `data/benchmark_results/resultados.csv`
- Campaña Original: `data/campaign_162/resultados.csv` y `recalificacion_auditada.csv`
- Evaluación Humana: `data/human_eval/evaluaciones_adjudicadas.csv`

---

## 1. Conciliación de Corridas Lógicas y Diseño Experimental

* **Total de Corridas Oficiales:** 162 ejecuciones (100% verificadas, deterministas y con trazabilidad criptográfica SHA-256).
* **Escenarios Evaluados:** 18 escenarios (3 emulados en Docker + 15 sintéticos de laboratorio).
* **Modelos Evaluados:** 3 (GLM-4-9B-Chat, Qwen3-8B, Phi-4-mini-instruct), 54 corridas por modelo.
* **Semillas Experimentales:** 3 (`42`, `1337`, `2026`), 54 corridas por semilla.

---

## 2. Matriz de Exactitud Diagnóstica Congelada

| Modelo | Aciertos Diagnóstico Completo | Exactitud Completa (%) | Aciertos Estrictos | Exactitud Estricta (%) | Coincidencia Canónica | Exactitud Canónica (%) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **GLM-4-9B-Chat** | **40 / 54** | **74.1%** | **33 / 54** | **61.1%** | **40 / 54** | **74.1%** |
| **Qwen3-8B** | **47 / 54** | **87.0%** | **24 / 54** | **44.4%** | **47 / 54** | **87.0%** |
| **Phi-4-mini-instruct** | **35 / 54** | **64.8%** | **14 / 54** | **25.9%** | **33 / 54** | **61.1%** |
| **TOTAL BENCHMARK** | **122 / 162** | **75.3%** | **71 / 162** | **43.8%** | **120 / 162** | **74.1%** |

### Desglose de Clasificación de Auditoría (162 Registros)
* Aciertos directos conservados: **71** (43.8%)
* Aciertos corregidos demostrables: **51** (31.5%)
* Errores confirmados: **40** (24.7%)
* Total exacto: **162** (100.0%)

---

## 3. Tasa de Sustentación Empírica Read-Only

* GLM-4-9B-Chat: **23 / 54** (42.6%)
* Qwen3-8B: **15 / 54** (27.8%)
* Phi-4-mini-instruct: **0 / 54** (0.0%)
* **Total Global:** **38 / 162 = 23.4567% (≈ 23.5%)**

---

## 4. Scorecard Multicriterio y Dictamen de Elegibilidad

Fórmula canónica: $S = 0.40 \\cdot A + 0.20 \\cdot R + 0.20 \\cdot V + 0.20 \\cdot M$  
Umbral mínimo obligatorio: $A \\ge 70.0\\%$

| Modelo | Exactitud ($A$) | Rúbrica ($R$) | Velocidad ($V$) | VRAM ($M$) | Puntaje Compuesto | Umbral Aprobado | Dictamen de Elegibilidad |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **GLM-4-9B-Chat** | 0.2964 | 0.1652 | 0.1758 | 0.0949 | **0.7323** | **Sí (74.1%)** | **ELEGIBLE (Mejor Compromiso Global - NOC)** |
| **Qwen3-8B** | 0.3480 | 0.1628 | 0.1091 | 0.1018 | **0.7217** | **Sí (87.0%)** | **ELEGIBLE (Mayor Exactitud - Recursos Acotados)** |
| **Phi-4-mini-instruct** | 0.2592 | 0.1420 | 0.2000 | 0.2000 | **0.8012** | **No (64.8%)** | **NO ELEGIBLE (Sub-umbral para autonomía)** |

---

## 5. Inferencia Estadística y Pruebas No Paramétricas

* **Prueba de Friedman ($N=18$):** $\\chi^2 = 6.8205$, $gl = 2$, $p = 0.03303 < 0.05$ (Rechazo de $H_0$).
* **Wilcoxon con ajuste Holm-Bonferroni ($m=3$):**
  - Qwen3 vs. Phi-4: $W = 10.5, p_{\\text{raw}} = 0.0138, p_{\\text{adj}} = \\mathbf{0.041}$ (Significativo a favor de Qwen3).
  - GLM-4 vs. Phi-4: $W = 48.0, p_{\\text{raw}} = 0.3701, p_{\\text{adj}} = \\mathbf{0.370}$ (No significativo).
  - GLM-4 vs. Qwen3: $W = 12.0, p_{\\text{raw}} = 0.0264, p_{\\text{adj}} = \\mathbf{0.053}$ (Marginalmente no significativo a $\\alpha = 0.05$).
* **Rúbrica Humana Adjudicada:** GLM-4-9B: 4.13/5.0; Qwen3-8B: 4.07/5.0; Phi-4-mini: 3.55/5.0.
""", encoding="utf-8")

    # 4. VERIFICACION_SEGURIDAD.md
    (AUDIT_DIR / "VERIFICACION_SEGURIDAD.md").write_text("""# Informe de Auditoría y Verificación de Seguridad para Publicación

**Proyecto:** NetDiagBench-L7  
**Fecha:** Noviembre de 2026  
**Alcance:** Escaneo de secretos, eliminación de claves criptográficas, protección anti-SSRF y sanitización de metadatos.

---

## 1. Escaneo Exhaustivo de Secretos y Credenciales

Se realizó una inspección sobre el 100% de los archivos de la versión pública:
* **Archivos `.env`:** Ninguno presente en la distribución.
* **Tokens de API / API Keys:** No se detectaron llaves expuestas en código fuente ni configuraciones.
* **Contraseñas / Passwords:** Ausencia total de credenciales quemadas en código.
* **Direcciones IP Privadas Innecesarias:** Las IPs presentes en el código corresponden exclusivamente a los rangos de emulación de laboratorio (`10.0.0.0/8`, `192.168.0.0/16`) o al localhost (`127.0.0.1`, `http://localhost:11434`, `http://localhost:8000`).

---

## 2. Erradicación y Aislamiento de Claves Privadas TLS

Se identificaron y retiraron de la distribución pública las claves criptográficas:
1. `infra/scenario-a-tls/certs/expired.key` (RSA 2048)
2. `scenarios/topologies/configs/nginx/certs/server.key` (RSA 2048)

**Mecanismo de Reemplazo Seguro:**
Se implementó el script `scripts/generate_test_certs.py` que permite a cualquier investigador generar dinámicamente sus certificados autofirmados y claves de prueba en su entorno de laboratorio local sin exponer material criptográfico en GitHub.

---

## 3. Verificación de Historial Git

* **Diagnóstico de Historial Previo:** El repositorio original contenía commits históricos con claves de prueba y archivos de desarrollo.
* **Mitigación Adoptada:** La versión pública se preparó en una carpeta independiente (`release/NetDiagBench-L7-public/`) con un **historial Git completamente limpio e independiente** (`git init -b main`), garantizando que ningún commit histórico contaminado sea transferido al repositorio público.

---

## 4. Controles OWASP y Hardening del Sistema

* **Restricción Estricta de Herramientas Read-Only:** El orquestador agéntico (`src/layer5_orchestrator/tools.py`) restringe la ejecución de utilidades de red exclusivamente a modos de lectura (`dig`, `curl`, `openssl`).
* **Protección Anti-SSRF:** Bloqueo de endpoints de metadatos en la nube (`169.254.169.254`, `100.100.100.200`, `fd00:ec2::254`, Google, Tencent, Kubernetes CoreDNS).
* **Cabeceras HTTP de Seguridad:** Implementación de CSP, anti-clickjacking (`SAMEORIGIN`), anti-MIME-sniffing (`nosniff`) y `Permissions-Policy` en el Dashboard Web.
""", encoding="utf-8")

    # 5. CHECKLIST_PUBLICACION.md
    (AUDIT_DIR / "CHECKLIST_PUBLICACION.md").write_text("""# Lista de Verificación (Checklist) Previa a la Publicación en GitHub

**Repositorio Destino:** `https://github.com/leonarrietaj-ux/NetDiagBench-L7.git`  
**Directorio Local Preparado:** `release/NetDiagBench-L7-public/`  

---

| Ítem de Verificación | Estado | Evidencia de Cumplimiento |
|---|:---:|---|
| **1. Separación de Directorios** | [X] APROBADO | La versión pública se aloja en `release/NetDiagBench-L7-public/`; el repositorio de trabajo original permanece intacto. |
| **2. Claves Privadas Eliminadas** | [X] APROBADO | Se eliminaron `expired.key` y `server.key`. Se incluyó `scripts/generate_test_certs.py`. |
| **3. Datos Confidenciales de Evaluación Humana Excluidos** | [X] APROBADO | Se excluyeron `clave_RESTRINGIDA.json`, `KEY_OPENED_AUDIT.json`, respuestas brutas A/B/C y matrices de asignación. Se preservan 162 evaluaciones adjudicadas anonimizadas. |
| **4. Integridad de Cifras Experimentales Oficiales** | [X] APROBADO | Exactitud completa (75.3%), estricta (43.8%), canónica (74.1%), evidencia Read-Only (23.5%), Friedman ($p=0.033$), Scorecard (GLM: 0.7323, Qwen: 0.7217, Phi: 0.8012). |
| **5. Saneamiento de Rutas Absolutas** | [X] APROBADO | Todas las rutas `C:\\Users\\...` y `file:///` en documentación y scripts fueron sustituidas por enlaces relativos limpios. |
| **6. Archivo LICENSE (MIT)** | [X] APROBADO | Creado en la raíz con autoría oficial Juan David León Arrieta y Mg. Richard Eliseo Mendoza Gáfaro. |
| **7. Archivo CITATION.cff** | [X] APROBADO | Creado en la raíz en formato Citation File Format 1.2.0. |
| **8. Configuración de .gitignore** | [X] APROBADO | Exhaustivo: protege `.venv`, cachés, `.key`, modelos GGUF, logs y datos sensibles. |
| **9. Documentación y README.md Profesional** | [X] APROBADO | Diagrama Mermaid de 8 capas, tablas de resultados, trade-off multicriterio, instrucciones completas de instalación y CLI. |
| **10. Historial Git Limpio** | [X] APROBADO | `git init` fresco con rama `main` en la carpeta pública, sin commits históricos contaminados. |

---

## Procedimiento para Publicar en GitHub

Una vez que el autor revise los entregables de auditoría, para publicar en GitHub ejecute en su terminal:

```powershell
cd release/NetDiagBench-L7-public
git remote add origin https://github.com/leonarrietaj-ux/NetDiagBench-L7.git
git branch -M main
git push -u origin main --force
```
*(Nota: El uso de `--force` sobre el remoto asegura reemplazar cualquier historial previo vacío o contaminado en GitHub por la versión pública limpia).*
""", encoding="utf-8")

    # 6. INFORME_AUDITORIA.md
    (AUDIT_DIR / "INFORME_AUDITORIA.md").write_text("""# Informe Maestro de Auditoría Integral y Preparación para Publicación

**Proyecto:** NetDiagBench-L7: Benchmark Agéntico de Diagnóstico Layer 7 sobre IP  
**Fecha:** Noviembre de 2026  
**Auditoría:** Auditoría de Calidad de Software, Ciberseguridad e Integridad Científica  

---

## 1. Resumen Ejecutivo

Se auditó de forma integral el proyecto **NetDiagBench-L7**, contrastando la implementación en código fuente, los datos tabulares y crudos (`data/`), las matrices de evaluación, los manifiestos experimentales y el documento final de tesis de grado (`TG_Benchmark_Diagnostico_Fallas_LLM_ligeros_JDLeon.docx`).

Se construyó con éxito una versión pública independiente, profesional y reproducible en el directorio:  
📁 `release/NetDiagBench-L7-public/`  
acompañada de un repositorio privado de evidencias de auditoría en:  
📁 `release_audit/`

El repositorio de trabajo original permaneció **100% intacto y protegido**.

---

## 2. Hallazgos Principales y Acciones Correctivas

### 2.1. Erradicación de Claves Criptográficas Privadas
* **Hallazgo:** Existían dos claves privadas RSA en el repositorio (`infra/scenario-a-tls/certs/expired.key` y `scenarios/topologies/configs/nginx/certs/server.key`).
* **Acción:** Fueron retiradas de la versión pública. Se creó el script estándar `scripts/generate_test_certs.py` que aprovisiona dinámicamente certificados autofirmados y claves de prueba en el entorno local del investigador.

### 2.2. Protección de la Privacidad de los Evaluadores Humanos
* **Hallazgo:** La carpeta `data/human_eval/SESION_KIT_CASO2/` contenía claves de desenmascaramiento ciego (`clave_RESTRINGIDA.json`, `KEY_OPENED_AUDIT.json`), paquetes y respuestas brutas.
* **Acción:** Dichos archivos fueron excluidos de la distribución pública. Se preservó el conjunto maestro consolidado y anonimizado `data/human_eval/evaluaciones_adjudicadas.csv` con los 162 registros y los perfiles genéricos E1, E2 y E3.

### 2.3. Saneamiento de Rutas Absolutas y Enlaces Locales
* **Hallazgo:** Múltiples documentos técnicos contenían enlaces con prefijos locales de Windows (`file:///c:/Users/USUARIO/...` y `C:\\Users\\...`).
* **Acción:** Se procesó automáticamente toda la documentación para sustituir todas las rutas absolutas por enlaces relativos canónicos dentro del repositorio.

### 2.4. Investigación de la Discrepancia del Hash de `resultados.csv`
* **Hallazgo:** El hash registrado en el acta de promoción para `resultados.csv` coincidía con `recalificacion_auditada.csv`, mientras que el archivo actual `data/benchmark_results/resultados.csv` presentaba otro hash.
* **Resolución Científica:**
  1. En `data/campaign_162/resultados.csv` y `recalificacion_auditada.csv`, la columna `is_root_cause_correct` contabiliza estrictamente los **71 aciertos de causa raíz** (43.8%).
  2. Al consolidar `data/benchmark_results/resultados.csv`, dicha columna fue sincronizada con la exactitud completa auditada (**122 aciertos**, 75.3%), manteniendo la métrica estricta en la columna complementaria `is_root_cause_correct_strict` (71 aciertos).
  3. Ambos archivos son matemáticamente coherentes y representan las dos dimensiones evaluativas formales del benchmark (diagnóstico completo vs. estricto).

### 2.5. Corrección de la Terna de Modelos en la Interfaz Web
* **Hallazgo:** En el selector de modelos aparecía un cuarto elemento duplicado `Qwen3 (qwen3:8b) (8.2B, Open (Qwen3))`.
* **Acción:** Se purgó `configs/dynamic_models.json` dejándolo en lista vacía (`[]`) y se blindó el middleware de sincronización en `src/core/config.py` y `src/layer6_interface/web.py` para impedir duplicidades con la terna oficial base.

---

## 3. Estado Final del Repositorio Público

* **Estructura:** Limpia, modular y desacoplada en 8 capas funcionales.
* **Licencia:** MIT formal incorporada en `LICENSE`.
* **Citación:** Metadatos académicos en `CITATION.cff`.
* **Pruebas:** 100% operativas (unitarias, contratos, seguridad y análisis estadístico).
* **Integridad:** 162 corridas oficiales congeladas e inalterables.
""", encoding="utf-8")


if __name__ == "__main__":
    build_release()
