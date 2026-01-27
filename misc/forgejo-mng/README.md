# Forgejo Repository Manager

A lightweight tool for quickly setting up Forgejo repositories and Pipelines-as-Code integration for testing and development. Automates repository creation, webhook configuration, and Kubernetes resources needed for PAC.

Originally designed as part of the [startpaac](https://github.com/openshift-pipelines/pipelines-as-code) project but can be used independently.

**Use this for:**

- Rapid testing and iteration with Forgejo and Pipelines-as-Code
- Automating setup of test repositories in development environments
- Creating repositories with pre-configured PAC resources

## Prerequisites

Install UV:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Quick Start

```bash
./main.py repo my-test-repo
```

## Configuration

Configuration can be provided via (in priority order):

1. **Password Store** (`GITEA_PASS_SECRET_FOLDER`)

   ```bash
   export GITEA_PASS_SECRET_FOLDER=gitea/civuole
   ./main.py repo my-test-repo
   ```

2. **Plain Text Directory** (`GITEA_SECRET_FOLDER`)

   ```bash
   mkdir -p ~/.config/gitea-secrets
   echo "http://forgejo.example.com/" > ~/.config/gitea-secrets/api-url
   echo "username" > ~/.config/gitea-secrets/username
   echo "password" > ~/.config/gitea-secrets/password
   echo "owner/org" > ~/.config/gitea-secrets/repo-owner

   export GITEA_SECRET_FOLDER=~/.config/gitea-secrets
   ./main.py repo my-test-repo
   ```

3. **Environment Variables** (Pipelines-as-Code compatible)

   ```bash
   export TEST_GITEA_API_URL=http://forgejo.example.com/
   export TEST_GITEA_USERNAME=username
   export TEST_GITEA_PASSWORD=password
   export TEST_GITEA_REPO_OWNER=owner/org
   export TEST_GITEA_SMEEURL=https://hook.pipelinesascode.com/hook  # Optional
   export TEST_GITEA_SKIP_TLS=true  # For self-signed certificates
   export TEST_GITEA_INTERNAL_URL=http://forgejo-http.forgejo:3000  # Optional
   ./main.py repo my-test-repo
   ```

4. **CLI Arguments**

   ```bash
   ./main.py repo my-test-repo \
     --forgejo-url http://forgejo.example.com \
     --username user \
     --password pass \
     --repo-owner owner
   ```

Required configuration keys: `api-url`, `username`, `password`, `repo-owner`

Optional keys: `smee`, `skip-tls` (accepts: true/1/yes), `internal-url`

## Commands

### `repo` - Create and configure repository

```bash
./main.py repo REPO_NAME [OPTIONS]
```

Creates a new Forgejo repository, optionally with webhook and Pipelines-as-Code resources.

Options:

- `--target-ns`: Kubernetes namespace (default: repo name)
- `--local-repo`: Local checkout path (default: /tmp/{repo-name})
- `--on-org`: Create under organisation instead of user account
- `--smee-url`: Webhook URL for smee.io
- `--internal-url`: Internal Forgejo URL for PAC (default: <http://forgejo-http.forgejo:3000>)
- `--no-create-pac-cr`: Skip creating PAC resources

Example:

```bash
./main.py repo my-test-repo --on-org --smee-url https://hook.pipelinesascode.com/hook
```

### `pr` - Create pull request

```bash
./main.py pr REPO_NAME [OPTIONS]
```

Creates a pull request with a Tekton PipelineRun file.

Options:

- `--target-branch`: Target branch (default: main)
- `--title`: PR title (auto-generated if not provided)
- `--pipelinerun-file`: Path to PipelineRun YAML (default: pr-noop.yaml)
- `--no-open`: Do not open PR in browser

Example:

```bash
./main.py pr my-test-repo --title "Test PR"
```

### `checkout` - Clone repository

```bash
./main.py checkout REPO DESTINATION
```

Clones an existing repository to a local destination.

Arguments:

- `REPO`: Repository name ("repo" uses configured owner, or "owner/repo" for explicit owner)
- `DESTINATION`: Local path to clone into

Example:

```bash
./main.py checkout my-repo /tmp/my-clone
./main.py checkout owner/repo /tmp/clone
```

## Global Options

All commands accept these options:

- `--forgejo-url`: Forgejo server URL
- `--username`: Forgejo username
- `--password`: Forgejo password
- `--repo-owner`: Repository owner (user/org format)
- `--skip-tls`: Skip TLS verification

## Pipelines-as-Code Integration

When creating a repository with the `repo` command, the tool optionally creates Kubernetes resources for Pipelines-as-Code:

- **Namespace**: Named after the repository (or specified via `--target-ns`)
- **Secret**: Contains the Forgejo access token
- **Repository CR**: Pipelines-as-Code custom resource pointing to the Forgejo repository

These require `kubectl` to be installed and configured. Use `--no-create-pac-cr` to skip.

## Authors

Mostly Claude see @AGENTS.md if you are a robot and want to interact with this repo
