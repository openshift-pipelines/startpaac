#!/usr/bin/env bash
# shellcheck disable=SC2059
CERT_DIR=${CERT_DIR:-/tmp/certs}

echo_color() {
  local echo=
  [[ ${1-""} == "-n" ]] && {
    echo="-n"
    shift
  }
  local color=$1
  local text=${2:-}
  case ${color} in
  red)
    echo ${echo} -e "\033[31m${text}\033[0m"
    ;;
  brightred)
    echo ${echo} -e "\033[1;31m${text}\033[0m"
    ;;
  green)
    echo ${echo} -e "\033[32m${text}\033[0m"
    ;;
  brightgreen)
    echo ${echo} -e "\033[1;32m${text}\033[0m"
    ;;
  blue)
    echo ${echo} -e "\033[34m${text}\033[0m"
    ;;
  brightblue)
    echo ${echo} -e "\033[1;34m${text}\033[0m"
    ;;
  brightwhite)
    echo ${echo} -e "\033[1;37m${text}\033[0m"
    ;;
  yellow)
    echo ${echo} -e "\033[33m${text}\033[0m"
    ;;
  brightyellow)
    echo ${echo} -e "\033[1;33m${text}\033[0m"
    ;;
  cyan)
    echo ${echo} -e "\033[36m${text}\033[0m"
    ;;
  bryightcyan)
    echo ${echo} -e "\033[1;36m${text}\033[0m"
    ;;
  purple)
    echo ${echo} -e "\033[35m${text}\033[0m"
    ;;
  brightcyan)
    echo ${echo} -e "\033[1;35m${text}\033[0m"
    ;;
  normal)
    echo ${echo} -e "\033[0m${text}\033[0m"
    ;;
  reset)
    echo ${echo} -e "\033[0m"
    ;;
  esac
}

show_step() {
  text="$1"
  length=$((${#text} + 4))

  # ANSI escape codes for colors
  green='\033[0;32m'
  blue='\033[0;34m'
  reset='\033[0m'

  # Top border
  printf "${green}╔${reset}" && printf "${green}═%.0s${reset}" $(seq 1 $((length - 2))) && printf "${green}╗${reset}\n"

  # Text with borders (using blue color)
  printf "${green}║ ${blue}%s${green} ║${reset}\n" "$text"

  # Bottom border
  printf "${green}╚${reset}" && printf "${green}═%.0s${reset}" $(seq 1 $((length - 2))) && printf "${green}╝${reset}\n"
}

create_tls_secret() {
  local host=$1
  local sec_name=$2
  local namespace=$3
  local key_file=${CERT_DIR}/${host}/key.pem
  local cert_file=${CERT_DIR}/${host}/cert.pem
  generate_certs_minica ${host}
  kubectl delete secret ${sec_name} -n ${namespace} || true
  kubectl create secret tls ${sec_name} --key ${key_file} --cert ${cert_file} -n ${namespace}
}

create_ingress() {
  local namespace=$1
  local component=$2
  local host=$3
  local targetPort=$4
  local sec_name=${component}-tls
  create_tls_secret "${host}" "${sec_name}" "${namespace}"

  echo "Creating ingress on $(echo_color brightgreen "https://${host}") for ${component}:${targetPort} in ${namespace}"
  kubectl apply -f - <<EOF
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: "${component}"
  namespace: "${namespace}"
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - "${host}"
      secretName: "${sec_name}"
  rules:
    - host: "${host}"
      http:
        paths:
          - pathType: ImplementationSpecific
            backend:
              service:
                name: "${component}"
                port:
                  number: ${targetPort}
EOF
}

generate_certs_minica() {
  local domain="$1"
  [[ -e ${CERT_DIR}/${domain}/cert.pem ]] && return 0
  mkdir -p ${CERT_DIR}
  if command -v pass >/dev/null 2>&1 && pass ls minica >/dev/null 2>&1; then
    pass show minica/cert >${CERT_DIR}/minica.pem
    pass show minica/key >${CERT_DIR}/minica-key.pem
  fi
  (cd ${CERT_DIR} && minica -domains ${domain})
}

wait_for_resource() {
  local resource_type=$1
  local namespace=$2
  local name=$3
  local display_name="${resource_type} ${name}"

  echo_color -n brightgreen "Waiting for ${display_name} to be ready in ${namespace}: "
  local i=0
  local max_wait=120 # seconds
  local interval=2   # seconds
  local max_retries=$((max_wait / interval))

  while true; do
    if [[ ${i} -ge ${max_retries} ]]; then
      echo_color brightred " FAILED (timeout after ${max_wait}s)"
      return 1
    fi

    local is_ready=0
    case ${resource_type} in
      endpoint|ep)
        local ep
        ep=$(kubectl get ep -n "${namespace}" "${name}" -o jsonpath='{.subsets[*].addresses[*].ip}' 2>/dev/null || true)
        [[ -n ${ep} ]] && is_ready=1
        ;;
      deployment|deploy)
        local desired ready
        desired=$(kubectl get deployment -n "${namespace}" "${name}" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
        ready=$(kubectl get deployment -n "${namespace}" "${name}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        [[ -n ${desired} ]] && [[ -n ${ready} ]] && [[ ${desired} -eq ${ready} ]] && [[ ${ready} -gt 0 ]] && is_ready=1
        ;;
      *)
        echo_color brightred " ERROR: Unknown resource type ${resource_type}"
        return 1
        ;;
    esac

    [[ ${is_ready} -eq 1 ]] && break
    sleep ${interval}
    echo_color -n brightwhite "."
    i=$((i + 1))
  done

  echo_color brightgreen " OK"
  return 0
}

# Backwards compatibility wrapper
wait_for_it() {
  wait_for_resource endpoint "$1" "$2"
}

# Backwards compatibility wrapper
wait_for_deployment() {
  wait_for_resource deployment "$1" "$2"
}

check_tools() {
  local tools=(
    "kubectl"
    "helm"
    "curl"
    "docker"
    "kind"
    "ko"
    "base64"
    "sed"
    "mktemp"
    "readlink"
    "jq"
  )

  # Only require gum in interactive mode
  if [[ ${CI_MODE:-false} != "true" ]]; then
    tools+=("gum")
  fi

  # minica is required for TLS certificate generation
  tools+=("minica")

  # Only require ssh/scp for remote targets
  if [[ ${TARGET_HOST:-local} != "local" ]]; then
    tools+=("ssh" "scp")
  fi

  for tool in "${tools[@]}"; do
    if ! command -v "$tool" &>/dev/null; then
      echo "Error: $tool is not installed or not in PATH."
      return 1
    fi
  done
  if [[ -n ${PAC_PASS_SECRET_FOLDER:-""} ]]; then
    if ! command -v pass &>/dev/null; then
      echo "Error: pass is not installed or not in PATH and you have the PAC_PASS_SECRET_FOLDER variable set."
      echo "Use PAC_SECRET_FOLDER instead if you want a folder instead of pass."
      return 1
    fi
  fi
  return 0
}

makeGosmee() {
  local deploymentName=$1
  local smeeURL=$2
  local controllerURL=$3
  local namespace=${4:-gosmee}
  cat <<EOF >/tmp/${deploymentName}.yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: $namespace
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $deploymentName
  namespace: $namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gosmee
  template:
    metadata:
      labels:
        app: gosmee
    spec:
      containers:
        - image: ghcr.io/chmouel/gosmee:main
          imagePullPolicy: Always
          name: gosmee
          args:
            [
              "client",
              "--output",
              "json",
              "--saveDir",
              "/tmp/save",
              "$smeeURL",
              "$controllerURL",
            ]
EOF
  kubectl apply -f /tmp/${deploymentName}.yaml
}
