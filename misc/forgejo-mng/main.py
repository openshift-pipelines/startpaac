#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests",
#     "click",
# ]
# ///
"""
Simple Forgejo repository creation tool using UV's inline script metadata.

This demonstrates UV's shebang trick for managing dependencies without
requiring a separate requirements.txt or pyproject.toml file.

Follows the Pipelines-as-Code E2E test pattern:
- Uses username/password for authentication
- Creates access token programmatically
- Manages repository lifecycle (delete/create)
"""

import base64
import os
import shutil
import subprocess
import sys
import time
import warnings
import webbrowser
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import click
import requests

# Get script directory for default pipelinerun-file
SCRIPT_DIR = Path(__file__).parent
DEFAULT_PIPELINERUN = str(SCRIPT_DIR / "pr-noop.yaml")


def read_secret(folder, key, method="cat"):
    """Read a single secret from folder using specified method.

    Args:
        folder: Folder path (plain directory or pass store path)
        key: Secret key name (e.g., 'api-url', 'username')
        method: 'pass' for password store, 'cat' for plain text files

    Returns:
        Stripped string value or None if not found
    """
    try:
        if method == "pass":
            # Use pass command to retrieve secret
            result = subprocess.run(
                ["pass", "show", f"{folder}/{key}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        else:
            # Read from plain text file
            secret_path = Path(folder) / key
            if secret_path.exists() and secret_path.is_file():
                content = secret_path.read_text().strip()
                # Treat empty files as not provided
                if content:
                    return content
    except Exception:
        pass

    return None


def load_secrets_from_folder(pass_folder=None, secret_folder=None):
    """Load secrets from folder (password store or plain text directory).

    Args:
        pass_folder: Password store folder path (takes priority)
        secret_folder: Plain text directory path

    Returns:
        Dict with keys: api_url, username, password, repo_owner, smee_url, skip_tls, internal_url
    """
    if not pass_folder and not secret_folder:
        return {}

    # Prefer pass_folder if both provided
    folder = pass_folder if pass_folder else secret_folder
    method = "pass" if pass_folder else "cat"

    secrets = {}

    # Map secret file names to config keys
    secret_mappings = {
        "api-url": "api_url",
        "username": "username",
        "password": "password",
        "repo-owner": "repo_owner",
        "smee": "smee_url",
        "skip-tls": "skip_tls",
        "internal-url": "internal_url",
    }

    for file_key, config_key in secret_mappings.items():
        value = read_secret(folder, file_key, method)
        if value:
            # Handle boolean conversion for skip-tls
            if config_key == "skip_tls":
                secrets[config_key] = value.lower() in ("true", "1", "yes")
            else:
                secrets[config_key] = value

    return secrets


def validate_required_config(config):
    """Validate required configuration fields are present.

    Args:
        config: Dictionary with configuration values

    Exits with error if validation fails.
    """
    required_fields = {
        "forgejo_url": [
            "GITEA_PASS_SECRET_FOLDER/api-url",
            "GITEA_SECRET_FOLDER/api-url",
            "TEST_GITEA_API_URL",
            "--forgejo-url",
        ],
        "username": [
            "GITEA_PASS_SECRET_FOLDER/username",
            "GITEA_SECRET_FOLDER/username",
            "TEST_GITEA_USERNAME",
            "--username",
        ],
        "password": [
            "GITEA_PASS_SECRET_FOLDER/password",
            "GITEA_SECRET_FOLDER/password",
            "TEST_GITEA_PASSWORD",
            "--password",
        ],
        "repo_owner": [
            "GITEA_PASS_SECRET_FOLDER/repo-owner",
            "GITEA_SECRET_FOLDER/repo-owner",
            "TEST_GITEA_REPO_OWNER",
            "--repo-owner",
        ],
    }

    missing_fields = []
    for field, sources in required_fields.items():
        if not config.get(field):
            missing_fields.append((field, sources))

    if missing_fields:
        click.echo("Error: Missing required configuration:", err=True)
        for field, sources in missing_fields:
            click.echo(f"\n  {field} can be provided via:", err=True)
            for source in sources:
                click.echo(f"    - {source}", err=True)
        sys.exit(1)


def generate_branch_name():
    """Generate unique branch name using timestamp."""
    return f"pac-test-{int(time.time())}"


def create_file_on_branch(
    forgejo_url,
    headers,
    owner,
    repo,
    filepath,
    content,
    branch,
    base_branch,
    message,
    verify_tls,
):
    """Create a file on a branch via Forgejo API (creates branch if needed)."""
    url = f"{forgejo_url}/api/v1/repos/{owner}/{repo}/contents/{filepath}"

    # Base64 encode the content
    encoded_content = base64.b64encode(content.encode()).decode()

    file_data = {
        "content": encoded_content,
        "message": message,
        "branch": base_branch,  # Fork from this branch
        "new_branch": branch,  # Create this new branch
    }

    response = requests.post(url, json=file_data, headers=headers, verify=verify_tls)
    if response.status_code not in (201, 200):
        click.echo(
            f"Error creating file: {response.status_code} {response.text}", err=True
        )
        return None

    return response.json()


def create_pull_request_api(
    forgejo_url, headers, owner, repo, title, head, base, verify_tls
):
    """Create a pull request via Forgejo API."""
    url = f"{forgejo_url}/api/v1/repos/{owner}/{repo}/pulls"

    pr_data = {
        "title": title,
        "head": head,
        "base": base,
    }

    response = requests.post(url, json=pr_data, headers=headers, verify=verify_tls)
    if response.status_code not in (201, 200):
        click.echo(
            f"Error creating pull request: {response.status_code} {response.text}",
            err=True,
        )
        return None

    return response.json()


@click.group()
@click.option(
    "--forgejo-url",
    "forgejo_url",
    envvar="TEST_GITEA_API_URL",
    help="Forgejo server URL",
)
@click.option("--username", envvar="TEST_GITEA_USERNAME", help="Forgejo username")
@click.option("--password", envvar="TEST_GITEA_PASSWORD", help="Forgejo password")
@click.option(
    "--repo-owner", envvar="TEST_GITEA_REPO_OWNER", help="Repository owner (user/org)"
)
@click.option(
    "--skip-tls",
    envvar="TEST_GITEA_SKIP_TLS",
    is_flag=True,
    help="Skip TLS verification",
)
@click.option(
    "--webhook-url",
    envvar="PAC_WEBHOOK_URL",
    default="",
    help="Direct webhook URL (e.g., http://127.0.0.1:30080), takes precedence over smee-url",
)
@click.pass_context
def cli(ctx, forgejo_url, username, password, repo_owner, skip_tls, webhook_url):
    """Forgejo repository and pull request management tool."""
    ctx.ensure_object(dict)

    # Read secret folder environment variables
    pass_folder = os.getenv("GITEA_PASS_SECRET_FOLDER")
    secret_folder = os.getenv("GITEA_SECRET_FOLDER")

    # Check if pass binary exists when GITEA_PASS_SECRET_FOLDER is set
    if pass_folder and not shutil.which("pass"):
        click.echo(
            "Error: GITEA_PASS_SECRET_FOLDER is set but 'pass' command not found",
            err=True,
        )
        click.echo(
            "Install pass (password-store) or use GITEA_SECRET_FOLDER instead", err=True
        )
        sys.exit(1)

    # Load secrets from folders
    folder_secrets = load_secrets_from_folder(pass_folder, secret_folder)

    # Merge configuration with priority: folder secrets > CLI args/env vars
    # Note: Click already handles CLI args > env vars, so we just need to override with folder secrets
    config = {
        "forgejo_url": folder_secrets.get("api_url") or forgejo_url,
        "username": folder_secrets.get("username") or username,
        "password": folder_secrets.get("password") or password,
        "repo_owner": folder_secrets.get("repo_owner") or repo_owner,
        "skip_tls": folder_secrets.get("skip_tls", skip_tls),
        "smee_url": folder_secrets.get("smee_url"),
        "internal_url": folder_secrets.get("internal_url"),
    }

    # Store merged configuration in context for subcommands
    ctx.obj["forgejo_url"] = config["forgejo_url"]
    ctx.obj["username"] = config["username"]
    ctx.obj["password"] = config["password"]
    ctx.obj["repo_owner"] = config["repo_owner"]
    ctx.obj["skip_tls"] = config["skip_tls"]
    ctx.obj["smee_url"] = config["smee_url"]
    ctx.obj["internal_url"] = config["internal_url"]
    ctx.obj["webhook_url"] = webhook_url


@cli.command("repo")
@click.argument("repo")
@click.option("--target-ns", default="", help="Namespace target")
@click.option("--local-repo", default="", help="Name of the local repo to clone")
@click.option("--on-org", is_flag=True, help="Create repo on organization")
@click.option(
    "--smee-url", envvar="TEST_GITEA_SMEEURL", default="", help="Webhook URL (smee.io)"
)
@click.option(
    "--internal-url",
    envvar="TEST_GITEA_INTERNAL_URL",
    default="http://forgejo-http.forgejo:3000",
    help="Internal Forgejo URL for PAC",
)
@click.option(
    "--create-pac-cr",
    is_flag=True,
    default=True,
    help="Create PAC namespace and Repository CR",
)
@click.pass_context
def repo_command(
    ctx,
    repo,
    target_ns,
    local_repo,
    on_org,
    smee_url,
    internal_url,
    create_pac_cr,
):
    """Create a Forgejo repository and optionally clone it locally."""
    # Get common options from context
    forgejo_url = ctx.obj["forgejo_url"]
    username = ctx.obj["username"]
    password = ctx.obj["password"]
    repo_owner = ctx.obj["repo_owner"]
    skip_tls = ctx.obj["skip_tls"]

    # Get webhook_url from context (takes precedence over smee_url)
    webhook_url = ctx.obj.get("webhook_url", "")

    # Get smee_url and internal_url from context if not provided via CLI/env
    if not smee_url and ctx.obj.get("smee_url"):
        smee_url = ctx.obj["smee_url"]
    if internal_url == "http://forgejo-http.forgejo:3000" and ctx.obj.get(
        "internal_url"
    ):
        internal_url = ctx.obj["internal_url"]

    # webhook_url takes precedence over smee_url
    effective_webhook_url = webhook_url if webhook_url else smee_url

    # Validate required configuration
    validate_required_config(
        {
            "forgejo_url": forgejo_url,
            "username": username,
            "password": password,
            "repo_owner": repo_owner,
        }
    )

    forgejo_url = forgejo_url.rstrip("/")

    verify_tls = not skip_tls

    if skip_tls:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    if forgejo_url.startswith("http://"):
        try:
            test_response = requests.head(
                forgejo_url, allow_redirects=True, timeout=5, verify=verify_tls
            )
            if test_response.url.startswith("https://") and not skip_tls:
                click.echo(
                    "Warning: HTTP redirects to HTTPS. If you have certificate issues, set TEST_GITEA_SKIP_TLS=true",
                    err=True,
                )
        except requests.exceptions.SSLError:
            click.echo("Error: SSL certificate verification failed.", err=True)
            click.echo(
                "Hint: Set TEST_GITEA_SKIP_TLS=true to skip TLS verification", err=True
            )
            sys.exit(1)
        except Exception:
            pass

    # Parse owner from TEST_GITEA_REPO_OWNER (format: "owner/repo")
    owner = repo_owner.split("/")[0] if "/" in repo_owner else repo_owner

    # Use basic auth for initial authentication
    auth = (username, password)

    # Create access token for this repository
    click.echo("Creating access token...")
    token = create_access_token(forgejo_url, auth, repo, verify_tls)
    if not token:
        click.echo("Error: Failed to create access token", err=True)
        sys.exit(1)

    # Setup headers with token
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
    }

    # Try to delete existing repo first
    delete_url = f"{forgejo_url}/api/v1/repos/{owner}/{repo}"
    response = requests.delete(delete_url, headers=headers, verify=verify_tls)
    if response.status_code == 204:
        click.echo(f"Repository {owner}/{repo} deleted")

    # Create new repository
    if on_org:
        create_url = f"{forgejo_url}/api/v1/orgs/{owner}/repos"
    else:
        create_url = f"{forgejo_url}/api/v1/user/repos"

    repo_data = {
        "name": repo,
        "private": False,
        "auto_init": True,
        "description": "This is a repo it's a wonderful thing",
    }

    response = requests.post(
        create_url, json=repo_data, headers=headers, verify=verify_tls
    )
    if response.status_code not in (201, 409):
        click.echo(
            f"Error creating repository: {response.status_code} {response.text}",
            err=True,
        )
        sys.exit(1)

    repo_info = response.json()
    html_url = repo_info.get("html_url", "")
    clone_url = repo_info.get("clone_url", "")

    click.echo(f"Repository created: {html_url}")

    # Create webhook if webhook URL or smee URL is provided
    if effective_webhook_url:
        create_webhook(forgejo_url, headers, owner, repo, effective_webhook_url, verify_tls)

    namespace = target_ns if target_ns else repo

    if create_pac_cr:
        create_pac_resources(namespace, repo, html_url, internal_url, token)

    # Build authenticated clone URL
    parsed = urlparse(clone_url)
    auth_url = urlunparse(
        (parsed.scheme, f"git:{password}@{parsed.netloc}", parsed.path, "", "", "")
    )

    # Clone repository
    local_checkout = local_repo if local_repo else f"/tmp/{repo}"
    local_path = Path(local_checkout)

    if local_path.exists():
        click.echo(f"Directory {local_checkout} already exists, skipping clone")
        click.echo(f"\nLocal Checkout Directory: {local_checkout}")
        click.echo(f"Forgejo Repository URL: {html_url}")
        return

    try:
        subprocess.run(
            ["git", "clone", auth_url, local_checkout],
            check=True,
            capture_output=True,
        )
        click.echo(f"Repository cloned to: {local_checkout}")

        # Create a branch
        subprocess.run(
            ["git", "checkout", "-b", "tektonci"],
            cwd=local_checkout,
            check=True,
            capture_output=True,
        )
        click.echo("Created branch: tektonci")

    except subprocess.CalledProcessError as e:
        click.echo(f"Error during git operations: {e}", err=True)
        if e.stderr:
            click.echo(e.stderr.decode(), err=True)
        sys.exit(1)

    click.echo(f"\nLocal Checkout Directory: {local_checkout}")
    click.echo(f"Forgejo Repository URL: {html_url}")


@cli.command("pr")
@click.argument("repo")
@click.option(
    "--target-branch", default="main", help="Target/base branch for the pull request"
)
@click.option(
    "--title", default="", help="Pull request title (auto-generated if not provided)"
)
@click.option(
    "--pipelinerun-file",
    default=DEFAULT_PIPELINERUN,
    help="Path to PipelineRun YAML file to add to the PR",
)
@click.option(
    "--no-open",
    is_flag=True,
    help="Do not open the PR URL in the web browser",
)
@click.pass_context
def pr_command(ctx, repo, target_branch, title, pipelinerun_file, no_open):
    """Create a pull request with a Tekton PipelineRun file."""
    # Get common options from context
    forgejo_url = ctx.obj["forgejo_url"]
    username = ctx.obj["username"]
    password = ctx.obj["password"]
    repo_owner = ctx.obj["repo_owner"]
    skip_tls = ctx.obj["skip_tls"]

    # Validate required configuration
    validate_required_config(
        {
            "forgejo_url": forgejo_url,
            "username": username,
            "password": password,
            "repo_owner": repo_owner,
        }
    )

    forgejo_url = forgejo_url.rstrip("/")
    verify_tls = not skip_tls

    if skip_tls:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    # Parse owner from TEST_GITEA_REPO_OWNER
    owner = repo_owner.split("/")[0] if "/" in repo_owner else repo_owner

    # Use basic auth for initial authentication
    auth = (username, password)

    # Create access token
    click.echo("Creating access token...")
    token = create_access_token(forgejo_url, auth, f"{repo}-pr", verify_tls)
    if not token:
        click.echo("Error: Failed to create access token", err=True)
        sys.exit(1)

    # Setup headers with token
    headers = {
        "Authorization": f"token {token}",
        "Content-Type": "application/json",
    }

    # Generate branch name
    branch_name = generate_branch_name()

    # Read PipelineRun file
    pipelinerun_path = Path(pipelinerun_file)
    if not pipelinerun_path.exists():
        click.echo(f"Error: PipelineRun file not found: {pipelinerun_file}", err=True)
        sys.exit(1)

    pipelinerun_content = pipelinerun_path.read_text()

    # Create file on new branch (this creates the branch automatically)
    click.echo(f"Creating branch '{branch_name}' with PipelineRun file...")
    result = create_file_on_branch(
        forgejo_url,
        headers,
        owner,
        repo,
        ".tekton/pr-noop.yaml",
        pipelinerun_content,
        branch_name,
        target_branch,  # Base branch to fork from
        "Add Tekton PipelineRun",
        verify_tls,
    )

    if not result:
        click.echo("Error: Failed to create file on branch", err=True)
        sys.exit(1)

    click.echo(f"File created on branch: {branch_name}")

    # Generate PR title if not provided
    if not title:
        title = f"Test PR - {branch_name}"

    # Create pull request
    click.echo("Creating pull request...")
    pr = create_pull_request_api(
        forgejo_url, headers, owner, repo, title, branch_name, target_branch, verify_tls
    )

    if not pr:
        click.echo("Error: Failed to create pull request", err=True)
        sys.exit(1)

    pr_url = pr.get("html_url", "")
    pr_number = pr.get("number", "")

    if no_open is False:
        webbrowser.open(pr_url)

    click.echo("\nPull Request Created!")
    click.echo(f"PR Number: {pr_number}")
    click.echo(f"PR URL: {pr_url}")
    click.echo(f"Branch: {branch_name}")
    click.echo(f"Target Branch: {target_branch}")


@cli.command("checkout")
@click.argument("repo")
@click.argument("destination")
@click.pass_context
def checkout_command(ctx, repo, destination):
    """Clone an existing Forgejo repository to local destination."""
    # Get common options from context
    forgejo_url = ctx.obj["forgejo_url"]
    username = ctx.obj["username"]
    password = ctx.obj["password"]
    repo_owner = ctx.obj["repo_owner"]
    skip_tls = ctx.obj["skip_tls"]

    # Validate required configuration
    validate_required_config(
        {
            "forgejo_url": forgejo_url,
            "username": username,
            "password": password,
            "repo_owner": repo_owner,
        }
    )

    forgejo_url = forgejo_url.rstrip("/")
    verify_tls = not skip_tls

    if skip_tls:
        warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    # Parse repository name and owner
    if "/" in repo:
        owner, repo_name = repo.split("/", 1)
    else:
        owner = repo_owner.split("/")[0] if "/" in repo_owner else repo_owner
        repo_name = repo

    # Validate destination path
    dest_path = Path(destination).resolve()
    if dest_path.exists():
        if dest_path.is_file():
            click.echo(f"Error: Destination {destination} is a file", err=True)
            sys.exit(1)
        if any(dest_path.iterdir()):
            click.echo("Error: Destination already exists and is not empty", err=True)
            sys.exit(1)
    else:
        dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Use basic auth for initial authentication
    auth = (username, password)

    # Create access token
    click.echo("Creating access token...")
    token = create_access_token(forgejo_url, auth, f"checkout-{repo_name}", verify_tls)
    if not token:
        click.echo("Error: Failed to create access token", err=True)
        sys.exit(1)

    # Construct clone URL
    parsed = urlparse(forgejo_url)
    clone_url = f"{parsed.scheme}://{parsed.netloc}/{owner}/{repo_name}.git"

    # Build authenticated URL
    auth_url = urlunparse(
        (
            parsed.scheme,
            f"git:{token}@{parsed.netloc}",
            f"/{owner}/{repo_name}.git",
            "",
            "",
            "",
        )
    )

    # Clone repository
    try:
        click.echo(f"Cloning {owner}/{repo_name} to {destination}...")
        subprocess.run(
            ["git", "clone", auth_url, str(dest_path)],
            check=True,
            capture_output=True,
        )
        click.echo(f"Repository cloned successfully to: {destination}")
        click.echo(f"Repository URL: {clone_url}")
    except subprocess.CalledProcessError as e:
        click.echo(f"Error cloning repository: {e}", err=True)
        if e.stderr:
            error_msg = e.stderr.decode()
            click.echo(error_msg, err=True)
            if (
                "not found" in error_msg.lower()
                or "repository not found" in error_msg.lower()
            ):
                click.echo(f"\nRepository {owner}/{repo_name} may not exist", err=True)
        sys.exit(1)


def create_access_token(forgejo_url, auth, name, verify_tls):
    """Create an access token with all scopes."""

    # First, try to delete existing token with the same name
    list_url = f"{forgejo_url}/api/v1/users/{auth[0]}/tokens"
    try:
        response = requests.get(list_url, auth=auth, verify=verify_tls)
        if response.status_code == 200:
            tokens = response.json()
            for token in tokens:
                if token.get("name") == name:
                    token_id = token.get("id")
                    delete_url = (
                        f"{forgejo_url}/api/v1/users/{auth[0]}/tokens/{token_id}"
                    )
                    requests.delete(delete_url, auth=auth, verify=verify_tls)
                    click.echo(f"Deleted existing token: {name}")
                    break
    except Exception:
        pass

    # Create new token
    url = f"{forgejo_url}/api/v1/users/{auth[0]}/tokens"
    token_data = {
        "name": name,
        "scopes": ["all"],
    }

    response = requests.post(url, json=token_data, auth=auth, verify=verify_tls)
    if response.status_code in (201, 200):
        return response.json().get("sha1")

    click.echo(
        f"Warning: Could not create token (status {response.status_code}), using password as fallback"
    )
    return auth[1]


def create_webhook(forgejo_url, headers, owner, repo, hook_url, verify_tls):
    """Create a webhook for the repository."""
    url = f"{forgejo_url}/api/v1/repos/{owner}/{repo}/hooks"
    webhook_data = {
        "type": "forgejo",
        "active": True,
        "config": {
            "url": hook_url,
            "content_type": "json",
        },
        "events": ["push", "issue_comment", "pull_request"],
    }

    response = requests.post(url, json=webhook_data, headers=headers, verify=verify_tls)
    if response.status_code == 201:
        click.echo(f"Webhook created: {hook_url}")
    else:
        click.echo(f"Warning: Could not create webhook (status {response.status_code})")


def create_pac_resources(namespace, repo_name, repo_url, internal_url, token):
    """Create PAC namespace, secret, and Repository CR using kubectl."""

    click.echo(f"Creating PAC resources in namespace: {namespace}")

    try:
        result = subprocess.run(
            ["kubectl", "create", "namespace", namespace],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            click.echo(f"Namespace {namespace} created")
        elif "AlreadyExists" in result.stderr:
            click.echo(f"Namespace {namespace} already exists")
        else:
            click.echo(
                f"Warning: Could not create namespace: {result.stderr}", err=True
            )
    except FileNotFoundError:
        click.echo(
            "Error: kubectl not found. Please install kubectl or use --no-create-pac-cr",
            err=True,
        )
        return

    subprocess.run(
        [
            "kubectl",
            "delete",
            "secret",
            repo_name,
            "-n",
            namespace,
            "--ignore-not-found=true",
        ],
        capture_output=True,
    )

    result = subprocess.run(
        [
            "kubectl",
            "create",
            "secret",
            "generic",
            repo_name,
            f"--from-literal=token={token}",
            "-n",
            namespace,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo(f"Secret {repo_name} created in namespace {namespace}")
    else:
        click.echo(f"Error creating secret: {result.stderr}", err=True)
        return

    subprocess.run(
        [
            "kubectl",
            "delete",
            "repository",
            repo_name,
            "-n",
            namespace,
            "--ignore-not-found=true",
        ],
        capture_output=True,
    )

    repository_yaml = f"""apiVersion: pipelinesascode.tekton.dev/v1alpha1
kind: Repository
metadata:
  name: {repo_name}
  namespace: {namespace}
spec:
  url: {repo_url}
  git_provider:
    type: gitea
    url: {internal_url}
    secret:
      name: {repo_name}
      key: token
"""

    result = subprocess.run(
        ["kubectl", "apply", "-f", "-"],
        input=repository_yaml,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        click.echo(f"Repository CR {repo_name} created in namespace {namespace}")
    else:
        click.echo(f"Error creating Repository CR: {result.stderr}", err=True)


if __name__ == "__main__":
    cli()
