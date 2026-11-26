FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc make libc6-dev zlib1g-dev time && rm -rf /var/lib/apt/lists/*
COPY nncp.tgz /tmp/nncp.tar.gz
RUN mkdir -p /opt/nncp && tar -xzf /tmp/nncp.tar.gz -C /opt/nncp --strip-components=1 && make -C /opt/nncp -j4 && rm /tmp/nncp.tar.gz
WORKDIR /data
