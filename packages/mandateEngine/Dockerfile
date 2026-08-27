FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml /app/packages/mandateEngine/
RUN pip install --no-cache-dir fastapi uvicorn pydantic pynacl redis httpx
COPY . /app/packages/mandateEngine/
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "packages.mandateEngine.mandateApp:mandateApp", "--host", "0.0.0.0", "--port", "8000"]
