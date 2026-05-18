# =============================================================================
# Dockerfile - Streamlit App
# =============================================================================
# Constrói a imagem do nosso frontend Streamlit.
# Baseado em Python slim para manter a imagem pequena.
# =============================================================================

FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia o arquivo de dependências primeiro (aproveita o cache do Docker)
# Se o requirements.txt não mudar, o Docker pula o pip install
COPY requirements.txt .

# Instala as dependências Python
# --no-cache-dir: não guarda cache de pacotes (reduz tamanho da imagem)
# --upgrade pip: garante que o pip está atualizado
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia o restante do código do app
COPY . .

# Expõe a porta padrão do Streamlit
EXPOSE 8501

# Healthcheck: verifica se o Streamlit está respondendo
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Comando para iniciar o Streamlit
# --server.address=0.0.0.0 → aceita conexões de fora do container
# --server.port=8501        → porta padrão
# --server.headless=true    → sem abrir browser automaticamente
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
