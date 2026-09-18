# syntax=docker/dockerfile:1
ARG BASE_IMAGE=debian:trixie-slim
FROM ${BASE_IMAGE} AS guest

FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates proot tar tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home --home-dir /home/container container
COPY --from=guest / /opt/soneyko/rootfs/
COPY entrypoint.sh /usr/local/bin/soneyko-entrypoint
COPY instance.sh /usr/local/bin/soneyko-instance
RUN chmod 755 /usr/local/bin/soneyko-entrypoint /usr/local/bin/soneyko-instance \
    && mkdir -p /opt/soneyko/rootfs/workspace /opt/soneyko/rootfs/root \
    && chmod 755 /opt/soneyko/rootfs/root
LABEL org.opencontainers.image.source="https://github.com/trusted-technologies/eggs-for-soneyko"
USER container
ENV HOME=/home/container USER=container TERM=xterm-256color
WORKDIR /home/container
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/soneyko-entrypoint"]
CMD ["/usr/local/bin/soneyko-instance"]
