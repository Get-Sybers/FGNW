# get_sybers.templates — shared molecule substrate.
#
# A hermetic Debian userspace for the host-side logic that does NOT need live
# infrastructure (argument validation and entry assertions). It is not a Proxmox
# node, a Windows host, or a legacy guest; those are exercised against real
# infrastructure in CI. Pinned by digest so every run builds the same base.
# molecule-docker renders this through Jinja before building, so it contains no
# Jinja delimiters (not even in a comment) and no COPY.
FROM docker.io/library/debian:trixie-slim@sha256:918311b7b6c4c6f68b232ba516584925f6c78ad82b6fd534b98979df6438e483

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-yaml \
        sudo \
        ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN printf 'Defaults:root !requiretty\n' > /etc/sudoers.d/molecule \
    && chmod 0440 /etc/sudoers.d/molecule
