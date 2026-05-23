# --- Stage 1: build del frontend React ---
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


# --- Stage 2: compilazione launcher ---
FROM python:3.13.2-slim AS starter-builder

RUN set -eux; \
	apt-get update; \
	apt-get install -y --no-install-recommends gcc libc6-dev; \
	rm -rf /var/lib/apt/lists/*

COPY src/start.c /tmp/start.c
RUN gcc /tmp/start.c -o /start.bin


# --- Stage 3: binari ffmpeg statici ---
FROM mwader/static-ffmpeg:latest AS ffmpeg-builder


# --- Stage 4: runtime Python slim ---
FROM python:3.13.2-slim

LABEL maintainer="MainKronos"

RUN set -eux; \
	export DEBIAN_FRONTEND=noninteractive; \
	apt-get update; \
	apt-get install -y --no-install-recommends \
		curl \
		passwd \
		rtmpdump \
		tzdata; \
	rm -rf /var/lib/apt/lists/*

RUN set -eux; \
	groupadd --gid 1000 dockeruser; \
	useradd --no-log-init -r -m --gid dockeruser --uid 1000 dockeruser; \
	mkdir -p /downloads /src

COPY src/requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /src

COPY src/ /src/
RUN rm -f /src/start.c

# Frontend React buildato
COPY --from=frontend-builder /frontend/build /frontend

COPY --from=ffmpeg-builder /ffmpeg /usr/local/bin/ffmpeg
COPY --from=starter-builder /start.bin /start.bin
RUN set -eux; \
	chmod 777 /downloads -R; \
	chmod 777 /src -R; \
	chmod 755 /frontend -R; \
	chmod 755 /usr/local/bin/ffmpeg; \
	chown root:root /start.bin; \
	chmod 6751 /start.bin

ENV FLASK_DEBUG=production
ENV PIP_ROOT_USER_ACTION=ignore
ENV FRONTEND_FOLDER=/frontend
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV TZ=Europe/Rome

# USER dockeruser
ENV USER_NAME=dockeruser

ARG set_version="dev"
ENV VERSION=$set_version

EXPOSE 5000

VOLUME [ "/downloads", "/src/script", "/src/database" ]

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD curl --fail http://localhost:5000 || exit 1

CMD ["/start.bin"]
