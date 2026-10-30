# Every download is pinned: the base image by digest, Claude Code by version and SHA-256,
# Rust by rust-toolchain.toml, everything else comes from signed Debian packages.
FROM mcr.microsoft.com/devcontainers/rust:2-1-trixie@sha256:2bf8d694491c0cd5edb860bd984f45b50a0207df75fdc707c378cf7c1ac83620

ARG CLAUDE_VERSION=2.1.312
ARG CLAUDE_SHA256_ARM64=dc4af28917455e009d26704b82a438353a06149e825b6cdf782908b2d28661f5
ARG CLAUDE_SHA256_AMD64=4f4178ce41d83e23341ebfbaecdbcf8ea6bf7baea0690025abe49eeec3a5d01d

RUN apt-get update \
    && apt-get install -y --no-install-recommends srcpd tinyproxy iptables \
    && rm -rf /var/lib/apt/lists/*

RUN case $(dpkg --print-architecture) in \
       arm64) arch=arm64 sha=$CLAUDE_SHA256_ARM64 ;; \
       amd64) arch=x64 sha=$CLAUDE_SHA256_AMD64 ;; \
       *) echo "unsupported architecture" >&2; exit 1 ;; \
    esac \
    && curl -fsSL -o /usr/local/bin/claude \
       "https://downloads.claude.ai/claude-code-releases/$CLAUDE_VERSION/linux-$arch/claude" \
    && echo "$sha  /usr/local/bin/claude" | sha256sum -c - \
    && chmod 755 /usr/local/bin/claude

# The agent may run init-sandbox.sh as root, nothing else. Only user keeper
# can read the tokens, the auth proxy adds them to the agent's requests.
COPY .devcontainer/init-sandbox.sh /usr/local/bin/
COPY .devcontainer/auth-proxy.py /usr/local/lib/electrip/
COPY .devcontainer/tinyproxy.conf .devcontainer/allowlist /etc/tinyproxy/
RUN echo "vscode ALL=(root) NOPASSWD: /usr/local/bin/init-sandbox.sh" > /etc/sudoers.d/vscode \
    && useradd --system --no-create-home --shell /usr/sbin/nologin keeper \
    && install -d -o keeper -g keeper -m 700 /etc/electrip-secrets \
    && git config --system http.postBuffer 524288000 \
    && mkdir -p /workspaces/electrip && chown vscode:vscode /workspaces/electrip

USER vscode
COPY rust-toolchain.toml /tmp/toolchain/
RUN cd /tmp/toolchain && rustup toolchain install
