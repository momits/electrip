# srcpd with a loopback bus as a stand-in for a real command station.
FROM debian:trixie-slim@sha256:f6b08b09a05725f9431502d3b5714f5c4576e82c1a84fa1debe0c24a7e0c3ec4
RUN apt-get update \
    && apt-get install -y --no-install-recommends srcpd \
    && rm -rf /var/lib/apt/lists/*
COPY srcpd.conf /etc/srcpd.conf
EXPOSE 4303
CMD ["srcpd", "-n", "-f", "/etc/srcpd.conf"]
