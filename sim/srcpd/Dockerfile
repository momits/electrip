# srcpd with a loopback bus as a stand-in for a real command station.
FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends srcpd \
    && rm -rf /var/lib/apt/lists/*
COPY srcpd.conf /etc/srcpd.conf
EXPOSE 4303
CMD ["srcpd", "-n", "-f", "/etc/srcpd.conf"]
