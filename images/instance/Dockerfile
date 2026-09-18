# syntax=docker/dockerfile:1
ARG BASE_IMAGE=debian:trixie-slim
FROM ${BASE_IMAGE} AS guest

FROM debian:trixie-slim AS guest-archive
COPY --from=guest / /guest/
RUN mkdir -p /guest/workspace \
    && tar -C /guest -cf /rootfs.tar . \
    && chmod 644 /rootfs.tar

FROM debian:trixie-slim AS proot-build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config libtalloc-dev uthash-dev git ca-certificates \
    && git clone https://github.com/proot-me/proot.git /src/proot \
    && cd /src/proot \
    && git checkout d4b49e2243dee34e41c13dfeca6a3d07e9cf0f00 \
    && tar --exclude=.git -czf /tmp/proot-source.tar.gz . \
    && make -C src -j2 proot \
    && strip src/proot

FROM debian:trixie-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates libtalloc2 tar tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home --home-dir /home/container container
COPY --from=proot-build /src/proot/src/proot /usr/local/bin/proot
COPY --from=proot-build /tmp/proot-source.tar.gz /usr/share/doc/proot/source.tar.gz
COPY --from=guest-archive /rootfs.tar /opt/soneyko/rootfs.tar
COPY entrypoint.sh /usr/local/bin/soneyko-entrypoint
COPY instance.sh /usr/local/bin/soneyko-instance
RUN chmod 755 /usr/local/bin/soneyko-entrypoint /usr/local/bin/soneyko-instance
LABEL org.opencontainers.image.source="https://github.com/trusted-technologies/eggs-for-soneyko"
USER container
ENV HOME=/home/container USER=container TERM=xterm-256color
WORKDIR /home/container
ENTRYPOINT ["/usr/bin/tini", "-g", "--", "/usr/local/bin/soneyko-entrypoint"]
CMD ["/usr/local/bin/soneyko-instance"]
