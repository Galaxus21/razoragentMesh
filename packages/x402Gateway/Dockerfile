FROM python:3.13-slim
WORKDIR /app
COPY packages/x402Gateway/pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn pydantic pynacl redis httpx
# Copy the source code
COPY packages/x402Gateway/src ./src
# Copy the shared mandateEngine package
COPY packages/mandateEngine ./packages/mandateEngine
RUN touch ./packages/__init__.py
ENV PYTHONPATH=/app
EXPOSE 4003
CMD ["uvicorn", "src.gatewayApp:app", "--host", "0.0.0.0", "--port", "4003"]
