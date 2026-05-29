# SINGULARITY — the kernel boots fully on the standard library alone.
FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY singularity ./singularity

# Install with the optional HTTP gateway.
RUN pip install --no-cache-dir -e '.[api]'

EXPOSE 8088
# Default: serve the federation gateway. Override CMD for `status` / `demo`.
CMD ["python", "-m", "singularity", "serve", "--host", "0.0.0.0", "--port", "8088"]
