FROM python:3.13-slim
WORKDIR /app
COPY packages/merchantApi/pyproject.toml .
RUN pip install --no-cache-dir fastapi==0.141.1 uvicorn[standard]==0.52.4 pydantic==2.13.5 pynacl==1.6.2 redis==8.1.0 httpx==0.28.1 qdrant-client==1.19.0 python-multipart==0.0.32 fastembed==0.8.0
# Copy the source code
COPY packages/merchantApi/src ./src
COPY packages/mandateEngine ./razoragentMesh/packages/mandateEngine
# Layer 3. Until this line no image contained the vector healer at all, so OosInterceptor could
# not have run in the mesh even once it was constructed. merchantApi is its host because it
# already installs qdrant-client and fastembed and already builds a Qdrant client.
COPY packages/vectorHealer ./razoragentMesh/packages/vectorHealer
# Layer 0. `src/catalog/ingressSanitizer.py` imports this on the listing-ingestion path, so an
# image without it fails at import rather than merely losing a capability.
COPY packages/catalogSanitizer ./razoragentMesh/packages/catalogSanitizer
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

# Drop root. Unlike the other two Python services this one needs a writable HOME: fastembed
# downloads its embedding model on first use (src/catalog/autoVectorizer.py) and caches it
# under $HOME, so --create-home and an explicit HOME are both load-bearing here.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
ENV HOME=/home/appuser
USER appuser

# Pre-download the embedding model at BUILD time. fastembed otherwise fetches it on the first
# search (src/catalog/embeddingEngine.py constructs TextEmbedding lazily), and on a freshly
# created container that download runs longer than the MCP server's 30s search_catalog timeout
# -- so an agent's very first discovery call failed while the download quietly completed in the
# background and every later call was fast. Baking it in also lets the mesh rank semantically
# with no network access at run time.
#
# Deliberately after USER appuser: the cache is keyed off the running user's environment, so
# downloading it as root would leave the server looking somewhere the model is not.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2')"

EXPOSE 4002
CMD ["uvicorn", "src.merchantApp:merchantApp", "--host", "0.0.0.0", "--port", "4002"]
