# 🚀 StartPAAC - All in one setup for Pipelines as Code on Kind

[![ShellCheck](https://github.com/chmouel/startpaac/actions/workflows/shellcheck.yml/badge.svg)](https://github.com/chmouel/startpaac/actions/workflows/shellcheck.yml)

`startpaac` is a script to set up and configure [Pipelines as Code (PAC)](https://pipelinesascode.com) on a
Kubernetes cluster using Kind. It features an interactive menu to select which
components to install, with preferences that can be saved for future runs.

> **What is Pipelines as Code?** Pipelines as Code is a Tekton-based CI/CD system that allows you to define your pipelines as code in your source repository, triggered by GitHub/GitLab events.

**Core components** (always installed):

- Kind cluster
- Nginx ingress gateway
- Docker registry to push images to
- Tekton Pipelines latest release

**Optional components** (choose via interactive menu):

- Pipelines-as-Code (PAC) using ko from your local revision
- Tekton Dashboard
- Tekton Triggers
- Tekton Chains
- Forgejo for local dev
- PostgreSQL
- Custom Kubernetes objects
- GitHub Second Controller

## System Requirements

**Minimum**:

- 4 CPU cores
- 8GB RAM
- 20GB available disk space

**Recommended**:

- 8 CPU cores
- 16GB RAM
- 50GB available disk space

## Prerequisites

The following tools are required. Install them before running `startpaac`:

- [Docker](https://docs.docker.com/get-docker/) >= 20.10 - Container runtime (tested with Docker, Podman may work but untested)
- [Kind](https://kind.sigs.k8s.io/) >= 0.20.0 - Kubernetes in Docker
- [Helm](https://helm.sh/) >= 3.10 - Kubernetes package manager
- [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl/) >= 1.24 - Kubernetes command-line tool
- [ko](https://github.com/google/ko) >= 0.14 - Build and deploy Go applications on Kubernetes
- [gum](https://github.com/charmbracelet/gum) >= 0.11 - Interactive component selection menus
- [jq](https://stedolan.github.io/jq/) >= 1.6 - JSON processor for preferences management
- [minica](https://github.com/jsha/minica) - Self-signed certificate generation
- [pass](https://www.passwordstore.org/) (optional) - Password manager for secrets
- GNU Tools (macOS/BSD users: install from homebrew - [coreutils](https://formulae.brew.sh/formula/coreutils), [gnu-sed](https://formulae.brew.sh/formula/gnu-sed#default))

## Security Notice

⚠️ **This tool is designed for local development environments only.**

- Default passwords in the values.yaml files are **weak and for development only**
- Self-signed TLS certificates are generated automatically
- Secrets can be stored in plain text files (use `pass` for better security)
- **DO NOT use this setup in production environments**
- Review and change all default credentials in `lib/*/values.yaml` if deploying anywhere accessible

For production deployments, please refer to the [Pipelines as Code production installation guide](https://pipelinesascode.com/docs/install/installation/).

## Getting Started

Execute or adapt the following, adjust the path of the PAC folder where you
have checked out pipelines-as-code:

```shell
mkdir -p $HOME/.config/startpaac
cat <<EOF > $HOME/.config/startpaac/config
TARGET_HOST=local
PAC_DIR=~/go/src/github.com/openshift-pipelines/pipelines-as-code
PAC_SECRET_FOLDER=~/secrets
EOF
```

Create your GitHub application and grab all the info needed and put them in
each secret file for example:

```shell
mkdir -p ~/secrets
for i in github-application-id github-private-key smee webhook.secret;do
  echo "Editing $i file"
  ${EDITOR:-vi} ~/secrets/$i
done
```

execute to interactively select and deploy components:

```shell
./startpaac
```

This will present an interactive menu where you can choose which components to install. For a non-interactive install of everything, use:

```shell
./startpaac -a
```

if you need to deploy a change you made to your code to the local registry you
do:

```bash
startpaac -p
```

this has redeployed everything, if you only want to redeploy the controller you can do:

```bash
startpaac -c controller # same goes for watcher or webhook
```

if you want to spin down the kind cluster you can do:

```bash
startpaac --stop-kind
```

if you have an existing cluster with pac installed (for example openshift) you
can configure paac directly there:

```bash
startpaac --configure-pac-target $KUBECONFIG $TARGET_NAMESPACE $DIRECTORY_OR_PASS_FOLDER
```

-The KUBECONFIG is the kubeconfig to use to connect to your cluster.
-The `$TARGET_NAMESPACE` is the namespace where pac is installed (for example
 openshift-pipelines if configured with operator).
-The `$DIRECTORY_OR_PASS_FOLDER` is the secret folder with the same structure as documented
 [earlier](#getting-started) but this can be a password store folder too.

## Interactive Component Selection

When running `startpaac` without any arguments, you'll be presented with an interactive menu to select which optional components to install:

```bash
./startpaac
```

The menu allows you to choose from:

- **Pipelines-as-Code (PAC)** - Install and configure PAC (default: on)
- **Tekton Triggers** - Event triggering for Tekton
- **Tekton Chains** - Supply chain security for Tekton
- **Tekton Dashboard** - Web UI for Tekton (default: on)
- **Forgejo** - Git forge for local development (default: on)
- **PostgreSQL** - Database for PAC
- **Custom Objects** - Install custom Kubernetes objects (only shown if `INSTALL_CUSTOM_OBJECT` is configured)
- **GitHub Second Controller** - Additional controller for GitHub (only shown if secrets are configured)

**Core components** (Kind, Nginx, Registry, Tekton Pipelines) are always installed.

After making your selections, you'll be asked if you want to save your preferences for future runs. Preferences are stored in `~/.config/startpaac/preferences.json`.

### Managing Preferences

```bash
# Force interactive menu even if preferences exist
./startpaac --menu

# Reset saved preferences
./startpaac --reset-preferences
```

On subsequent runs, if you have saved preferences, the script will automatically use them without showing the menu. You can always override this with `--menu` or clear preferences with `--reset-preferences`.

### Preferences File Format

Preferences are stored as JSON in `~/.config/startpaac/preferences.json`:

```json
{
  "pac": true,
  "tekton_triggers": false,
  "tekton_chains": false,
  "tekton_dashboard": true,
  "forgejo": true,
  "postgresql": false,
  "custom_objects": false,
  "github_second_ctrl": false
}
```

## Configuration

Create a configuration file at `$HOME/.config/startpaac/config` with the following content:
(this will be auto created by paac if you don't have one)

## Full Configuration

```bash
# PAC_DIR is the path to the pipelines-as-code directory, it will try to detect
# it otherwise
# PAC_DIR=~/path/to/pipelines-as-code
#
# PAC_PASS_SECRET_FOLDER is the path to a folder in https://passwordstore.org/
# where you have your pac secrets. The folder contains those keys:
# github/apps/my-app
# ├── github-application-id
# ├── github-private-key
# ├── smee
# └── webhook.secret
# github-application-id and github-private-key are the github application id and private key when you create your github app
# smee is the smee.io or https://hook.pipelinesascode.com generated webhook URL as set in your github apps.
# webhook.secret is the shared secret as set in your github apps.
# PAC_PASS_SECRET_FOLDER=github/apps/my-app
#
# PAC_SECRET_FOLDER is an alternative to PASS_SECRET_FOLDER where you have your
# pac secrets in plain text. The folder has the same structure as the
# PASS_SECRET_FOLDER the only difference is that the files are in plain text.
#
# PAC_SECRET_FOLDER=~/path/to/secrets
#
# TARGET_HOST is your vm where kind will be running, you need to have kind working there
# set as local and unset all other variable to have it running on your local VM
# TARGET_HOST=my.vm.lan
#
# KO_EXTRA_FLAGS are the extra flags to pass to ko
#
# KO_EXTRA_FLAGS=() # extra ko flags for example --platform linux/arm64 --insecure-registry
## Hosts (not needed if TARGET_HOST is set to local)
# setup a wildcard dns *.lan.mydomain.com to go to your TARGET_HOST vm
# tips: if you don't want to install a dns server you can simply use
# https://nextdns.io to let you create wildcard dns for your local network.
#
# DOMAIN_NAME=lan.mydomain.com
# PAAC=paac.${DOMAIN_NAME}
# REGISTRY=registry.${DOMAIN_NAME}
# FORGE_HOST=gitea.${DOMAIN_NAME}
# DASHBOARD=dashboard.${DASHBOARD}
#
# Example:
# TARGET_HOST=civuole.lan
# KO_EXTRA_FLAGS=(--insecure-registry --platform linux/arm64)
# DOMAIN_NAME=vm.lan
# PAAC=paac.${DOMAIN_NAME}
# REGISTRY=registry.${DOMAIN_NAME}
# FORGE_HOST=gitea.${DOMAIN_NAME}
# TARGET_BIND_IP=192.168.1.5
# TARGET_BIND_IP=192.168.1.5,10.0.0.5 # Comma-separated for multiple IPs
# DASHBOARD=dashboard.${DOMAIN_NAME}
# PAC_DIR=$GOPATH/src/github.com/openshift-pipelines/pac/main
```

You can have an alternative config file with the `STARTPAAC_CONFIG_FILE`
environment variable.

## PostgreSQL Configuration

You can configure the PostgreSQL connection details in the `values.yaml` file
located in `lib/postgresql/values.yaml`. The following parameters are available
under `global.postgresql.auth`:

- `username`: The PostgreSQL username.
- `password`: The PostgreSQL password.
- `database`: The PostgreSQL database name.

If you want to customize the PostgreSQL configuration, you can modify the
`lib/postgresql/values.yaml` file. For example:

```yaml
global:
  postgresql:
    auth:
      username: "myuser"
      password: "mypassword"
      database: "mydatabase"
```

## Secrets Management

### Using `pass`

If you prefer to manage your secrets using `pass`, set the
`PAC_PASS_SECRET_FOLDER` variable in your configuration file to the path of
your secrets folder in `pass`. The folder should contain the following files:

- `github-application-id`
- `github-private-key`
- `smee`
- `webhook.secret`

Example structure:

```console
github/apps/my-app
├── github-application-id
├── github-private-key
├── smee
└── webhook.secret
```

### Using Plain Text

Alternatively, you can store your secrets in plain text files. Set the
`PAC_SECRET_FOLDER` variable in your configuration file to the path of your
secrets folder. The folder should have the same structure as the `pass` folder,
but the files should be in plain text.

Example structure:

```console
~/path/to/secrets
├── github-application-id
├── github-private-key
├── smee
└── webhook.secret
```

## Usage

Run the script with the desired options:

```sh
./startpaac [options]
```

When run without arguments, the script presents an interactive menu to select components. On first run, you can save your preferences which will be used automatically on subsequent runs.

For non-interactive installation of everything, use the `-a` option.

### Options

- `-a|--all`                Install everything (non-interactive)
- `-A|--all-but-kind`       Install everything but kind
- `-i|--menu|--interactive` Force interactive component selection menu
- `-R|--reset-preferences`  Reset saved component preferences
- `-k|--kind`               (Re)Install Kind
- `-g|--install-forge`      Install Forgejo
- `-c|--deploy-component`  Deploy a component (controller, watcher, webhook)
- `-p|--install-paac`       Deploy and configure PAC
- `-h|--help`               Show help message
- `-s|--sync-kubeconfig`    Sync kubeconfig from the remote host
- `-G|--start-user-gosmee`  Start gosmee locally for user $USER
- `-S|--github-second-ctrl` Deploy second controller for GitHub
- `--install-nginx`         Install Nginx
- `--install-dashboard`     Install Tekton dashboard
- `--install-tekton`        Install Tekton
- `--install-triggers`      Install Tekton Triggers
- `--install-chains`        Install Tekton Chains
- `--install-custom-crds`   Install custom CRDs
- `--redeploy-kind`         Redeploy Kind
- `--scale-down`            Scale down a component (controller, watcher, webhook)
- `--second-secret=SECRET`  Pass name for the second controller secret
- `--stop-kind`             Stop Kind

## Examples

### Interactive Installation (Recommended for First Time)

Run without arguments to get an interactive menu:

```sh
./startpaac
```

This will:

1. Show you the current configuration
2. Present a multi-select menu of optional components
3. Ask if you want to save your preferences
4. Show a summary of what will be installed
5. Ask for final confirmation before proceeding

### Install Everything (Non-Interactive)

```sh
./startpaac --all
```

### Use Saved Preferences

After saving preferences once, simply run:

```sh
./startpaac
```

It will use your saved preferences without showing the menu.

### Change Component Selection

Force the menu to appear even with saved preferences:

```sh
./startpaac --menu
```

### Reset to Defaults

Clear your saved preferences:

```sh
./startpaac --reset-preferences
```

### Install PAC and Configure

```sh
./startpaac --install-paac
```

### Install Nginx

```sh
./startpaac --install-nginx
```

### Install Tekton

```sh
./startpaac --install-tekton
```

### Install Tekton Triggers

```sh
./startpaac --install-triggers
```

### Install Tekton Chains

```sh
./startpaac --install-chains
```

### Install Custom CRDs

```sh
./startpaac --install-custom-crds
```

### Deploy a Specific Component

```sh
./startpaac --deploy-component controller
```

### Sync Kubeconfig from Remote Host

```sh
./startpaac --sync-kubeconfig
```

### Start User Gosmee

```sh
./startpaac --start-user-gosmee
```

it will try to start gosmee for the user if you have a systemd user one, or
give you the command line to start it.

### Deploy Second Controller for GitHub

```sh
./startpaac --github-second-ctrl
```

you need the `PAC_PASS_SECOND_FOLDER` which is the same
`PAC_PASS_SECRET_FOLDER` but for a second controller to use.

### PAC Installation Configuration

You can configure the PAC installation with the following options:

- `--debug-image`: Use a debug image for the PAC controller.
- `--show-config`: Show the PAC configuration.
- `--apply-non-root`: Apply non-root configuration to the PAC controller.

## ZSH Completion

There is a [ZSH completion script](./misc/_startpaac) that can get installed in your

path for completion.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Author

OpenShift Pipelines Team
