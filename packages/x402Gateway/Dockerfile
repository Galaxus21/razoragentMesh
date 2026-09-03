FROM python:3.13-slim
WORKDIR /app
COPY packages/x402Gateway/pyproject.toml .
RUN pip install --no-cache-dir fastapi==0.141.1 uvicorn[standard]==0.52.4 pydantic==2.13.5 pynacl==1.6.2 redis==8.1.0 httpx==0.28.1
# Copy the source code
COPY packages/x402Gateway/src ./src
# Copy the shared mandateEngine package
COPY packages/mandateEngine ./razoragentMesh/packages/mandateEngine
RUN touch ./razoragentMesh/__init__.py ./razoragentMesh/packages/__init__.py
# The tree imports shared packages under TWO spellings -- `packages.mandateEngine` and
# `razoragentMesh.packages.mandateEngine` -- and both appear in code this image runs. The old
# layout served only the first, so every `razoragentMesh.`-spelled import raised
# ModuleNotFoundError here while passing under pytest, which runs from the directory above the
# mesh root. That is not a cosmetic split: `oosHealingRoute._loadHealer` catches ImportError and
# degrades, so Layer 3 reported `vector_healer_unavailable` in the running mesh no matter that
# the package had been copied in.
#
# One copy, two roots on PYTHONPATH: /app resolves `razoragentMesh.packages....` and
# /app/razoragentMesh resolves `packages....`.
ENV PYTHONPATH=/app:/app/razoragentMesh

# Drop root. The gateway only reads its own code and reaches Redis over the network.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 4003
CMD ["uvicorn", "src.gatewayApp:app", "--host", "0.0.0.0", "--port", "4003"]
