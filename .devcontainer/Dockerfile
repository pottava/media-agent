FROM python:3.13-slim

# Install related packages
RUN apt-get update && apt-get install -y build-essential vim curl wget git jq gnupg lsb-release golang
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV PATH "/.venv/bin:/root/go/bin:${PATH}"

# Terraform & gcloud
RUN wget -qO - https://apt.releases.hashicorp.com/gpg | gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
RUN echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(grep -oP '(?<=UBUNTU_CODENAME=).*' /etc/os-release || lsb_release -cs) main" \
    | tee /etc/apt/sources.list.d/hashicorp.list
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
    | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list \
    && curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg \
    | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
RUN apt-get update && apt-get install -y terraform google-cloud-cli

# Environment variables
ENV PYTHONUNBUFFERED 1
ENV GOOGLE_CLOUD_LOCATION us-central1

# Resolve dependencies for apps
COPY pyproject.toml .
COPY uv.lock .
RUN uv sync

# MCP tools for Genmedia
RUN git clone https://github.com/GoogleCloudPlatform/vertex-ai-creative-studio.git \
    && cd /vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go/mcp-veo-go && go mod tidy && go install \
    && cd /vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go/mcp-gemini-go && go mod tidy && go install \
    && cd /vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go/mcp-imagen-go && go mod tidy && go install \
    && cd /vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go/mcp-lyria-go && go mod tidy && go install \
    && cd / && rm -rf /vertex-ai-creative-studio /root/.cache /root/go/pkg/mod/cache
RUN go install github.com/f/mcptools/cmd/mcptools@latest

# Working directory
WORKDIR /workspace
