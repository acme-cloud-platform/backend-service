# ---------- Stage 1: builder ----------
# Pinned to 3.11 to match gcr.io/distroless/python3-debian12's bundled
# Python interpreter exactly. psycopg2 (and any compiled C extension) is
# ABI-tied to a specific Python minor version — a mismatch here causes
# cryptic import errors at runtime in the final distroless stage, so this
# pin is deliberate, not arbitrary.
# Pinned to an exact patch version (not just "3.11-slim") deliberately —
# floating minor tags can lag behind on OS-level security patches between
# rebuilds. 3.11.27 carries fewer known CVEs than earlier 3.11.x patches at
# time of writing. If Docker Hub ever deprecates this exact tag, bump to
# the next available 3.11.x patch release — check
# https://hub.docker.com/_/python/tags before changing.
FROM python:3.11.27-slim AS builder

WORKDIR /app

COPY requirements.txt .
# Install into a local target dir instead of system site-packages, so we
# can cleanly copy just the installed packages into the distroless stage
# without dragging along pip, apt caches, or anything else from the builder.
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

COPY app/ ./app/

# ---------- Stage 2: distroless runtime ----------
# No shell, no package manager, no apt, no pip — nothing an attacker could
# use even with code execution inside the container beyond the Python
# interpreter and our own app code. This is the real production hardening
# upgrade over python:3.12-slim: drastically smaller attack surface, and
# far fewer CVEs to begin with since there's almost nothing OS-level here
# to have a CVE in.
FROM gcr.io/distroless/python3-debian12:nonroot

WORKDIR /app

COPY --from=builder /app/deps /app/deps
COPY --from=builder /app/app /app/app

ENV PYTHONPATH=/app/deps

# distroless:nonroot already runs as a non-root user by default — no
# separate useradd/USER step needed like the slim-based version required.

EXPOSE 8000

# No shell in this image, so CMD must be exec-form pointing directly at the
# python entrypoint — can't use uvicorn's CLI script directly since that
# relies on a shebang/shell resolution that doesn't exist here.
ENTRYPOINT ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]