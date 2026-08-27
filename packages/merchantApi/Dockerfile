FROM python:3.13-slim
WORKDIR /app
COPY packages/merchantApi/pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn pydantic pynacl redis httpx qdrant-client python-multipart fastembed
# Copy the source code
COPY packages/merchantApi/src ./src
# Copy the shared mandateEngine package
COPY packages/mandateEngine ./packages/mandateEngine
RUN touch ./packages/__init__.py
ENV PYTHONPATH=/app
EXPOSE 4002
CMD ["uvicorn", "src.merchantApp:merchantApp", "--host", "0.0.0.0", "--port", "4002"]
