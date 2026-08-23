FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn pydantic pynacl redis httpx
COPY . .
EXPOSE 8000
CMD ["uvicorn", "razoragentMesh.packages.mandateEngine.mandateApp:mandateApp", "--host", "0.0.0.0", "--port", "8000"]
