# Agent Instructions for create-forgejo-repo

## Project Overview

This is a Python script that creates Forgejo repositories and sets up Pipelines-as-Code (PAC) Kubernetes resources. It uses UV's shebang trick for dependency management (PEP 723).

## Key Architecture Decisions

### UV Shebang Script
- **Dependencies are declared inline** in the script header using PEP 723 format
- No separate `requirements.txt` or `pyproject.toml` needed
- UV automatically creates isolated environments and installs dependencies
- DO NOT add traditional Python packaging files unless explicitly requested

### Kubernetes Integration
- Uses `kubectl` commands via subprocess (NOT Python Kubernetes library)
- This keeps dependencies minimal and leverages existing cluster configuration
- kubectl must be available in PATH and properly configured

### Code Quality
- Formatted with `ruff` (NOT black or autopep8)
- Import sorting with `ruff --select I` (NOT isort as separate tool)
- Use `make format` or `make check` for formatting

## File Structure

```
.
├── main.py  # Main executable script (UV shebang)
├── example-usage.sh      # Example usage with environment variables
├── README.md             # User-facing documentation
├── AGENTS.md             # This file (agent instructions)
├── Makefile              # Development tasks (format, lint, test)
├── .gitignore            # Git ignore rules
├── main.go               # Legacy Go implementation (kept for reference)
└── go.mod                # Legacy Go module (kept for reference)
```

## When Making Changes

### Adding Features
1. Keep the single-file architecture - all code in `main.py`
2. For new dependencies: add to `# dependencies = [...]` section at top of script
3. Use subprocess for external commands (git, kubectl)
4. Follow existing patterns for error handling and user feedback

### Code Style
- **ALWAYS run `make format` before committing**
- Use `click` for CLI options (already established pattern)
- Use `requests` for HTTP calls (already established pattern)
- Use subprocess for external commands (git, kubectl)

### Environment Variables
The script uses PAC E2E test environment variables:
- `TEST_GITEA_API_URL` - Forgejo server URL
- `TEST_GITEA_USERNAME` - Username
- `TEST_GITEA_PASSWORD` - Password
- `TEST_GITEA_REPO_OWNER` - Owner in format "user/org"
- `TEST_GITEA_SMEEURL` - Webhook URL (optional)
- `TEST_GITEA_SKIP_TLS` - Skip TLS verification (optional)
- `TEST_GITEA_INTERNAL_URL` - Internal Forgejo URL for PAC
- `KUBECONFIG` - Kubernetes config path

**DO NOT change these variable names** - they match the upstream PAC test suite.

### Testing
```bash
# Quick test
make test

# Full test with real Forgejo instance
source <(pass show pac/vars/forgejo-civuole)
./main.py test-repo-name
```

## What This Script Does

1. **Authenticates** with Forgejo using username/password
2. **Creates access token** programmatically via Forgejo API
3. **Deletes existing repository** (if present)
4. **Creates new repository** with auto-init
5. **Creates webhook** (if smee URL provided)
6. **Creates Kubernetes resources**:
   - Namespace (named after repo)
   - Secret (contains Forgejo token)
   - Repository CR (PAC custom resource)
7. **Clones repository** locally with authenticated URL
8. **Creates branch** named "tektonci"

## Common Tasks

### Format code
```bash
make format
```

### Add a new CLI option
Add to the `@click.command()` decorator section, following the existing pattern.

### Add a new dependency
Add to the inline dependencies list at the top:
```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "click",
#     "your-new-package",
# ]
# ///
```

### Modify Kubernetes resources
Edit the `create_pac_resources()` function. The YAML is embedded as an f-string.

## DO NOT

- ❌ Create separate `requirements.txt` or `pyproject.toml`
- ❌ Use Python Kubernetes library (use kubectl instead)
- ❌ Change environment variable names (must match PAC test suite)
- ❌ Use black, autopep8, or standalone isort (use ruff for everything)
- ❌ Add unnecessary comments (code should be self-documenting)
- ❌ Break the single-file architecture

## DO

- ✅ Keep everything in one file (`main.py`)
- ✅ Use `make format` before committing
- ✅ Use subprocess for external commands
- ✅ Follow existing error handling patterns
- ✅ Update README when adding user-facing features
- ✅ Test with real Forgejo instance before committing
