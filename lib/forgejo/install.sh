#!/usr/bin/env bash
# Copyright 2024 Chmouel Boudjnah <chmouel@chmouel.com>
set -eufo pipefail
NS=forgejo
fpath=$(dirname "$0")
# shellcheck disable=SC1091
source "${fpath}"/../common.sh
[[ -n ${1:-""} ]] && FORGE_HOST=${1}
FORGE_HOST=${FORGE_HOST:-""}
[[ -z ${FORGE_HOST} ]] && { echo "You need to specify a FORGE_HOST" && exit 1; }
forge_secret_name=forge-tls

kubectl create namespace ${NS} 2>/dev/null || true

# Create TLS secret and configure Helm args
create_tls_secret $FORGE_HOST ${forge_secret_name} ${NS}
HELM_TLS_ARGS=(
  --set "ingress.tls[0].hosts[0]=${FORGE_HOST}"
  --set "ingress.tls[0].secretName=${forge_secret_name}"
)

helm uninstall forgejo -n ${NS} >/dev/null 2>&1 || true
helm install --wait -f ${fpath}/values.yaml \
  --replace \
  --version 15.1.0 \
  --set "ingress.hosts[0].host=${FORGE_HOST}" \
  --set "ingress.hosts[0].paths[0].path=/" \
  --set "ingress.hosts[0].paths[0].pathType=Prefix" \
  "${HELM_TLS_ARGS[@]}" \
  --create-namespace -n ${NS} forgejo oci://code.forgejo.org/forgejo-helm/forgejo
