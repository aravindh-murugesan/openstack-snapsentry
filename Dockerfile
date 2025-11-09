# ---- Base stage ----
FROM ghcr.io/astral-sh/uv:python3.13-alpine AS base

WORKDIR /openstack-sentry/

# Copy only dependency files first to leverage caching
COPY pyproject.toml uv.lock* ./

# Install build dependencies temporarily
RUN apk add --no-cache gcc musl-dev linux-headers

# Sync dependencies (build wheels here for cache)
RUN uv sync --frozen --no-dev 


# ---- Runtime stage ----
FROM ghcr.io/astral-sh/uv:python3.13-alpine AS runtime

WORKDIR /openstack-sentry/

# Copy venv and dependencies from builder (if uv stores them in .venv)
COPY --from=base /openstack-sentry/.venv .venv

# Copy app source code
COPY . .

# If you ever need openstack config files:
# COPY /etc/openstack/clouds.yaml /etc/openstack/

# Set PATH to include uv/venv executables
ENV PATH="/openstack-sentry/.venv/bin:$PATH"

# Optionally create a non-root user
RUN adduser -D sentry && chown -R sentry /openstack-sentry
USER sentry
