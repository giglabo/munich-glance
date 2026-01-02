FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy source files for installation
COPY pyproject.toml README.md ./
COPY trmnl_server/ trmnl_server/

# Install Python dependencies
RUN pip install --no-cache-dir .
COPY assets/ assets/
COPY web/ web/

# Create runtime directories
RUN mkdir -p var/db var/generated

# Copy system fonts to assets if not present
RUN cp -n /usr/share/fonts/truetype/dejavu/DejaVuSans*.ttf assets/fonts/ 2>/dev/null || true

# Create non-root user
RUN useradd -m -u 1000 trmnl && \
    chown -R trmnl:trmnl /app
USER trmnl

# Expose port
EXPOSE 4567

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:4567/api/health', timeout=5).raise_for_status()"

# Run server
CMD ["python", "-m", "trmnl_server"]
