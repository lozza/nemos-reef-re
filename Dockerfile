FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN groupadd --gid 10001 nemo \
    && useradd --uid 10001 --gid nemo --no-create-home nemo \
    && mkdir /data /game \
    && chown nemo:nemo /data

# Only server code and its story/text files enter the image. APK and saves are mounts.
COPY server/ ./server/
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).close()"]
ENTRYPOINT ["python", "server/nemo_server.py"]
CMD ["--apk", "/game/nemo.apk", "--data", "/data", "--host", "0.0.0.0", "--port", "8080"]
