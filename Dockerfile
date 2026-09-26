FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY coldcaller coldcaller
COPY campaign.example.yaml leads.example.csv ./
RUN useradd --create-home caller && mkdir data && chown -R caller:caller /app
USER caller
EXPOSE 8000
CMD ["uvicorn", "coldcaller.server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
