#!/usr/bin/env bash
# start-single-node.sh - Start GVStress monitoring stack on a single node
#
# Starts node_exporter, Prometheus, and optionally Grafana natively.
# All configuration comes from a config file; no hardcoded interfaces.
#
# Usage:
#   ./start-single-node.sh --config <path> [--dry-run] [--stop]
#
# Options:
#   --config <path>   Path to config file (required)
#   --dry-run         Preview actions without applying
#   --stop            Stop all services instead of starting
#   -h, --help        Show this help

set -euo pipefail

DRY_RUN=false
STOP=false
CONFIG_FILE=""

readonly SERVICE_NODE="gvstress-node"
readonly SERVICE_PROMETHEUS="gvstress-prometheus"
readonly SERVICE_GRAFANA="gvstress-grafana"

log_info()  { echo "[INFO]  $*"; }
log_warn()  { echo "[WARN]  $*"; }
log_error() { echo "[ERROR] $*" >&2; }
log_dry()   { echo "[DRY-RUN] $*"; }

run_cmd() {
    if $DRY_RUN; then
        log_dry "Would execute: $*"
        return 0
    fi
    "$@"
}

usage() {
    head -15 "$0" | tail -12
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --stop)
            STOP=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ -z "$CONFIG_FILE" ]]; then
    log_error "--config is required"
    usage
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

parse_config() {
    local key="$1"
    grep -E "^\s*${key}\s*[:=]" "$CONFIG_FILE" \
        | head -1 \
        | sed -E "s/^\s*${key}\s*[:=]\s*//" \
        | sed 's/^["'\'']//;s/["'\'']$//' \
        | xargs
}

NODE_ENABLED="$(parse_config "node_exporter_enabled" || echo "true")"
PROMETHEUS_ENABLED="$(parse_config "prometheus_enabled" || echo "true")"
GRAFANA_ENABLED="$(parse_config "grafana_enabled" || echo "false")"

preflight() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    if ! command -v systemctl &>/dev/null; then
        log_error "systemctl not found - systemd is required"
        exit 1
    fi
}

manage_service() {
    local service="$1"
    local action="$2"

    if ! systemctl list-unit-files "${service}.service" &>/dev/null; then
        log_warn "Service ${service} not found, skipping"
        return 0
    fi

    if $STOP; then
        log_info "Stopping ${service}..."
        run_cmd systemctl stop "$service" || true
        run_cmd systemctl disable "$service" || true
    else
        log_info "Starting ${service}..."
        run_cmd systemctl enable "$service"
        run_cmd systemctl restart "$service"
    fi
}

verify_services() {
    if $DRY_RUN || $STOP; then
        return 0
    fi

    sleep 2
    local services=()

    [[ "$NODE_ENABLED" == "true" ]] && services+=("$SERVICE_NODE")
    [[ "$PROMETHEUS_ENABLED" == "true" ]] && services+=("$SERVICE_PROMETHEUS")
    [[ "$GRAFANA_ENABLED" == "true" ]] && services+=("$SERVICE_GRAFANA")

    local failed=0
    for svc in "${services[@]}"; do
        if systemctl is-active --quiet "$svc"; then
            log_info "${svc}: running"
        else
            log_warn "${svc}: NOT running (journalctl -u ${svc})"
            failed=$((failed + 1))
        fi
    done

    if [[ $failed -gt 0 ]]; then
        log_warn "${failed} service(s) failed to start"
        return 1
    fi

    log_info "All services started successfully"
}

main() {
    log_info "GVStress Single-Node Controller"
    log_info "Config: $CONFIG_FILE"
    $DRY_RUN && log_info "Mode: DRY-RUN"
    $STOP && log_info "Mode: STOP"

    preflight

    if [[ "$NODE_ENABLED" == "true" ]]; then
        manage_service "$SERVICE_NODE" "start"
    fi

    if [[ "$PROMETHEUS_ENABLED" == "true" ]]; then
        manage_service "$SERVICE_PROMETHEUS" "start"
    fi

    if [[ "$GRAFANA_ENABLED" == "true" ]]; then
        manage_service "$SERVICE_GRAFANA" "start"
    fi

    verify_services
}

main "$@"
