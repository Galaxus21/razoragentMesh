FROM python:3.13-slim
WORKDIR /app
COPY packages/x402Gateway/pyproject.toml .
RUN pip install --no-cache-dir fastapi==0.141.1 uvicorn==0.52.4 pydantic==2.13.5 pynacl==1.6.2 redis==8.1.0 httpx==0.28.1
# Copy the source code
COPY packages/x402Gateway/src ./src
# Copy the shared mandateEngine package
COPY packages/mandateEngine ./packages/mandateEngine
RUN touch ./packages/__init__.py
ENV PYTHONPATH=/app

# Drop root. The gateway only reads its own code and reaches Redis over the network.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 4003
CMD ["uvicorn", "src.gatewayApp:app", "--host", "0.0.0.0", "--port", "4003"]
