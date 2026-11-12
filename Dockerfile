# NetDiagBench-L7: Benchmark Reproducible de Diagnóstico L7 con SLMs
# Dockerfile para contenedorización completa y reproducción portable

FROM python:3.11-slim

LABEL maintainer="Juan David León Arrieta <juan.leon22@unipamplona.edu.co>"
LABEL institution="Universidad de Pamplona - E.E.S.T."
LABEL description="Framework de benchmark reproducible para diagnóstico L7 sobre IP"

# Evitar prompts interactivos y buffers de Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema operativo (herramientas de red para verificación L7)
RUN apt-get update && apt-get install -y --no-install-recommends \
    dnsutils \
    curl \
    openssl \
    iproute2 \
    iputils-ping \
    procps \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar manifiesto de dependencias primero para optimizar cache de capas Docker
COPY pyproject.toml .

# Instalar dependencias de Python
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir pytest scipy

# Copiar el código fuente completo, configuraciones, escenarios y conocimiento
COPY src/ ./src/
COPY configs/ ./configs/
COPY scenarios/ ./scenarios/
COPY knowledge/ ./knowledge/
COPY tests/ ./tests/
COPY data/ ./data/
COPY docs/ ./docs/
COPY README.md .

# Crear usuario de sistema sin privilegios para mitigar ejecución como root (CIS Docker Benchmark)
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser && \
    chown -R appuser:appuser /app

# Cambiar a usuario no root
USER appuser

# Exponer el puerto para el Dashboard Web FastAPI
EXPOSE 8000

# Por defecto iniciar el dashboard interactivo
CMD ["python", "-m", "uvicorn", "src.layer6_interface.web:app", "--host", "0.0.0.0", "--port", "8000"]
