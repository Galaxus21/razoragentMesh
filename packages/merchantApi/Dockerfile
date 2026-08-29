FROM python:3.13-slim
WORKDIR /app
COPY packages/merchantApi/pyproject.toml .
RUN pip install --no-cache-dir fastapi==0.141.1 uvicorn==0.52.4 pydantic==2.13.5 pynacl==1.6.2 redis==8.1.0 httpx==0.28.1 qdrant-client==1.19.0 python-multipart==0.0.32 fastembed==0.8.0
# Copy the source code
COPY packages/merchantApi/src ./src
# Copy the shared mandateEngine package
COPY packages/mandateEngine ./packages/mandateEngine
RUN touch ./packages/__init__.py
ENV PYTHONPATH=/app
EXPOSE 4002
CMD ["uvicorn", "src.merchantApp:merchantApp", "--host", "0.0.0.0", "--port", "4002"]
