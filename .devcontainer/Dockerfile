# The Rust image already brings Python for the legacy harness and jq for loop.sh.
FROM mcr.microsoft.com/devcontainers/rust:2-1-trixie
USER vscode
RUN curl -fsSL https://claude.ai/install.sh | bash
ENV PATH=/home/vscode/.local/bin:$PATH
