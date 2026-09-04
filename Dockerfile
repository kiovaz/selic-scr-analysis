# Só é usado se o grupo decidir manter o Docker (seção 7.3 do architecture.md).
# Se a decisão for não usar, apague este arquivo e o docker-compose.yml.

FROM python:3.11-slim

WORKDIR /app

# Instala as dependências primeiro, separado do código.
# Assim o Docker reaproveita esta camada quando só o código muda.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "scripts/run_pipeline.py"]
