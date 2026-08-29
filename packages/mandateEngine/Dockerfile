FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml /app/packages/mandateEngine/
RUN pip install --no-cache-dir fastapi==0.141.1 uvicorn==0.52.4 pydantic==2.13.5 pynacl==1.6.2 redis==8.1.0 httpx==0.28.1
COPY . /app/packages/mandateEngine/
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "packages.mandateEngine.mandateApp:mandateApp", "--host", "0.0.0.0", "--port", "8000"]
