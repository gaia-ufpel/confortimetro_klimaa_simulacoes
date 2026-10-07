# Servidor de simulações do Ambiens (docs/SERVIDOR.md).
# Build a partir da raiz do repositório:
#   docker build -f packaging/servidor/Dockerfile -t ambiens-servidor .
FROM python:3.10-slim-bookworm

# EnergyPlus 9.4 (REQUIRED_EP_VERSION em confortimetro/config.py).
ARG EP_URL=https://github.com/NREL/EnergyPlus/releases/download/v9.4.0/EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu20.04-x86_64.tar.gz
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates libgomp1 libx11-6 \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir /opt/energyplus \
 && curl -fsSL "$EP_URL" | tar -xz -C /opt/energyplus --strip-components=1

ENV ENERGYPLUS_DIR=/opt/energyplus \
    CONFORTIMETRO_DATA_DIR=/dados \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints.txt
COPY pyproject.toml cli.py ./
COPY confortimetro ./confortimetro

RUN useradd -m ambiens && mkdir /dados && chown ambiens /dados
USER ambiens
VOLUME /dados
EXPOSE 8765
CMD ["python", "-m", "confortimetro.remote.server", "servir", "--host", "0.0.0.0", "--porta", "8765"]
