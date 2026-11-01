# sasori container image
# Multi-stage: Go builder → minimal Debian 13 (bookworm) runtime
# Build: podman build -t sasori:latest -f Containerfile .
# The resulting image is pushed to a registry and pinned by digest in
# range-config.yml's ludus_extensions.emulator.template_image.

# ── Stage 1: Build ──────────────────────────────────────────────────────────
FROM --platform=linux/amd64 docker.io/library/golang:1.22-bookworm AS builder

WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build \
    -trimpath \
    -ldflags="-s -w" \
    -o /sasori \
    ./cmd/sasori

# ── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM --platform=linux/amd64 docker.io/library/debian:bookworm-slim

# ca-certificates: TLS to Proxmox API
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Persona configs and passwords are mounted at /etc/sasori/ by the LXC.
RUN mkdir -p /etc/sasori

COPY --from=builder /sasori /usr/local/bin/sasori
RUN chmod 755 /usr/local/bin/sasori

# Non-root user for the service.
RUN useradd -r -s /usr/sbin/nologin -u 1001 emulator
USER emulator

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/sasori"]
