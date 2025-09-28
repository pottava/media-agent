FROM golang:1.25 AS builder

# Install MCP tools for Genmedia
RUN git clone https://github.com/GoogleCloudPlatform/vertex-ai-creative-studio.git
WORKDIR vertex-ai-creative-studio/experiments/mcp-genmedia/mcp-genmedia-go

RUN cd mcp-veo-go && go mod tidy && CGO_ENABLED=0 GOOS=linux go install -ldflags="-s -w" .
RUN cd mcp-gemini-go && go mod tidy && CGO_ENABLED=0 GOOS=linux go install -ldflags="-s -w" .
RUN cd mcp-imagen-go && go mod tidy && CGO_ENABLED=0 GOOS=linux go install -ldflags="-s -w" .
RUN cd mcp-lyria-go && go mod tidy && CGO_ENABLED=0 GOOS=linux go install -ldflags="-s -w" .

# Copy binaries
FROM scratch
COPY --from=builder /go/bin/mcp-veo-go /mcp-veo-go
COPY --from=builder /go/bin/mcp-gemini-go /mcp-gemini-go
COPY --from=builder /go/bin/mcp-imagen-go /mcp-imagen-go
COPY --from=builder /go/bin/mcp-lyria-go /mcp-lyria-go

EXPOSE 8081
CMD ["/mcp-gemini-go", "-transport", "http"]
