# CookiX server — hardened single-node container image.
#
# Build:  docker build -t cookix .
# Run:    docker run -p 8000:8000 \
#             -e COOKIX_API_KEY=change-me \
#             -e COOKIX_RATE_LIMIT_RPM=600 \
#             cookix
#
# Security posture: slim base, no build toolchain in the final image, runs as an
# unprivileged user, and ships a container HEALTHCHECK wired to /healthz.

FROM python:3.12-slim AS build
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
# Install into a self-contained prefix we can copy into the runtime stage.
RUN pip install --no-cache-dir --prefix=/install ".[server]"

FROM python:3.12-slim AS runtime

# Create an unprivileged user to run the server (never run as root).
RUN useradd --create-home --uid 10001 cookix

COPY --from=build /install /usr/local
WORKDIR /home/cookix
USER cookix

ENV PYTHONUNBUFFERED=1 \
    COOKIX_METRICS=1

EXPOSE 8000

# Liveness: the orchestrator restarts the container if /healthz stops answering.
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status==200 else 1)"

# Bind to all interfaces inside the container; publish with -p on the host.
CMD ["cookix", "serve", "--host", "0.0.0.0", "--port", "8000"]
