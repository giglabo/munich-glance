# Scripts

Utility scripts for the Munich Glance project.

## Available Scripts

| Script | Purpose |
|--------|---------|
| `build.sh` | Build and push Docker images |
| `setup_fonts.sh` | Download required fonts |
| `format_code.sh` | Auto-format Python code |
| `check_code.sh` | Run code quality checks |

---

## build.sh

Builds and pushes Docker images with multi-architecture support.

**Usage:**
```bash
./scripts/build.sh [command] [options]
```

**Commands:**

| Command | Description |
|---------|-------------|
| `build` | Build image locally for current architecture |
| `push` | Build and push multi-arch image to registry |
| `list` | Show current configuration |

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--registry=URL` | Registry prefix (e.g., `ghcr.io/myorg`) | (none) |
| `--tag=TAG` | Image tag | `latest` |
| `--arch=ARCH` | Architecture: `amd64`, `arm64`, or `both` | current/both |
| `--name=NAME` | Image name | `munich-glance` |

**Examples:**
```bash
# Build for current architecture
./scripts/build.sh build

# Build for specific architecture
./scripts/build.sh build --arch=arm64

# Build and push both architectures
./scripts/build.sh push --registry=ghcr.io/myorg

# Push only amd64 with custom tag
./scripts/build.sh push --registry=ghcr.io/myorg --arch=amd64 --tag=v1.0

# Show configuration
./scripts/build.sh list --registry=ghcr.io/myorg
```

**Environment Variables:**
- `REGISTRY` - Registry prefix
- `TAG` - Image tag (default: latest)
- `IMAGE_NAME` - Image name (default: munich-glance)
- `ARCH` - Architecture (default: current for build, both for push)

**Notes:**
- Multi-arch push requires Docker buildx
- Creates `multiarch-builder` buildx instance if not present
- Registry is required for `push` command

---

## setup_fonts.sh

Downloads DejaVu fonts required for the display renderer.

**Usage:**
```bash
./scripts/setup_fonts.sh
```

**What it does:**
1. Creates the `assets/fonts/` directory if needed
2. Downloads DejaVu fonts v2.37 from GitHub releases
3. Extracts TTF files to `assets/fonts/`

**Notes:**
- Safe to run multiple times (skips if fonts exist)
- Requires `curl` or `wget`
- To re-download, remove `assets/fonts/` first

---

## format_code.sh

Formats Python code across all packages using `ruff` and `black`.

**Usage:**
```bash
./scripts/format_code.sh
```

**What it does:**
1. Runs `ruff check --fix` for linting fixes and import sorting
2. Runs `ruff format` for consistent formatting
3. Runs `black` for final formatting pass

**Packages formatted:**
- `trmnl_server/`
- `tests/`

**Configuration:** Uses `pyproject.toml`

---

## check_code.sh

Runs code quality checks without modifying files.

**Usage:**
```bash
./scripts/check_code.sh
```

**Checks performed:**

| Tool | Purpose | Blocking |
|------|---------|----------|
| `ruff check` | Linting + import sorting | Yes |
| `ruff format --check` | Format verification | Yes |
| `black --check` | Format verification | Yes |
| `flake8` | Additional linting | Yes |
| `mypy` | Type checking | No |
| `bandit` | Security scanning | No |

**Exit codes:**
- `0` - All blocking checks passed
- `1` - One or more blocking checks failed

**Fix issues:**
```bash
./scripts/format_code.sh  # Auto-fix formatting
./scripts/check_code.sh   # Verify fixes
```

---

## Prerequisites

### Docker (for build.sh)

- Docker with buildx support (included in Docker Desktop)
- For multi-arch builds: `docker buildx` command available

### Python Tools

Install development dependencies:
```bash
pip install -e ".[dev]"
```

Or install tools individually:
```bash
pip install ruff black flake8 mypy bandit
```

---

## Adding New Scripts

When adding new scripts:

1. Create the script in the `scripts/` directory
2. Add shebang and description comment at the top
3. Make it executable: `chmod +x scripts/your_script.sh`
4. Update this README with usage information
