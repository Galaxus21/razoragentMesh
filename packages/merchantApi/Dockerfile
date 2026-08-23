FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
COPY . .
EXPOSE 4002
CMD ["uvicorn", "razoragentMesh.packages.merchantApi.src.merchantApp:merchantApp", "--host", "0.0.0.0", "--port", "4002"]
