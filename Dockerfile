FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copia arquivos de requisitos
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY monitor.py .
COPY sites_config.json .

# Cria arquivo para produtos notificados (será persistido via volume)
RUN touch notified_products.json

# Executa o monitor
CMD ["python", "-u", "monitor.py"]
