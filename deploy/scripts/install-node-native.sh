#!/usr/bin/env bash
# install-node-native.sh - Idempotent native installation of GVStress monitoring node
#
# Installs and configures Prometheus node_exporter natively (no Docker).
# Requires explicit parameters; no hardcoded interface names.
#
# Usage:
#   ./install-node-native.sh --config <path> [--dry-run] [--force]
#
# Options:
#   --config <path>   Path to YAML/INI config file (required)
#   --dry-run         Preview actions without applying
#   --force           Reinstall even if already installed
#   -h, --help        Show this help

set -euo pipefail

DRY_RUN=false
FORCE=false
CONFIG_FILE=""

readonly SERVICE_NAME="gvstress-node"
readonly INSTALL_PREFIX="/opt/gvstress"
readonly SYSTEMD_DIR="/etc/systemd/system"
readonly NODE_EXPORTER_USER="node_exporter"
readonly NODE_EXPORTER_VERSION="1.7.0"
readonly NODE_EXPORTER_ARCH="$(uname -m)"

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
        --force)
            FORCE=true
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
    local value
    value=$(grep -E "^\s*${key}\s*[:=]" "$CONFIG_FILE" \
        | head -1 \
        | sed -E "s/^\s*${key}\s*[:=]\s*//" \
        | sed 's/^["'\'']//;s/["'\'']$//' \
        | xargs)
    echo "$value"
}

EXPORTER_ENABLED="$(parse_config "node_exporter_enabled" || echo "true")"
PROMETHEUS_ENABLED="$(parse_config "prometheus_enabled" || echo "true")"
GRAFANA_ENABLED="$(parse_config "grafana_enabled" || echo "false")"
DATA_DIR="$(parse_config "data_dir" || echo "/var/lib/gvstress")"
LOG_DIR="$(parse_config "log_dir" || echo "/var/log/gvstress")"
LISTEN_PORT="$(parse_config "node_exporter_port" || echo "9100")"
LISTEN_ADDRESS="$(parse_config "node_exporter_address" || echo "0.0.0.0")"

preflight() {
    log_info "Running pre-flight checks..."

    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi

    if ! command -v systemctl &>/dev/null; then
        log_error "systemctl not found - systemd is required"
        exit 1
    fi

    if ! command -v tar &>/dev/null; then
        log_error "tar is required but not installed"
        exit 1
    fi

    if ! command -v curl &>/dev/null && ! command -v wget &>/dev/null; then
        log_error "curl or wget is required but not installed"
        exit 1
    fi

    log_info "Pre-flight checks passed"
}

create_user() {
    if id "$NODE_EXPORTER_USER" &>/dev/null; then
        log_info "User '$NODE_EXPORTER_USER' already exists"
        return 0
    fi

    log_info "Creating system user '$NODE_EXPORTER_USER'..."
    run_cmd useradd --system --no-create-home --shell /usr/sbin/nologin \
        --comment "node_exporter service user" "$NODE_EXPORTER_USER"
}

install_node_exporter() {
    local binary="${INSTALL_PREFIX}/node_exporter"

    if [[ -f "$binary" ]] && ! $FORCE; then
        local current_version
        current_version=$("$binary" --version 2>&1 | head -1 || echo "unknown")
        log_info "node_exporter already installed: $current_version"
        log_info "Use --force to reinstall"
        return 0
    fi

    log_info "Installing node_exporter v${NODE_EXPORTER_VERSION}..."

    run_cmd mkdir -p "$INSTALL_PREFIX"

    local tarball="node_exporter-${NODE_EXPORTER_VERSION}.linux-${NODE_EXPORTER_ARCH}.tar.gz"
    local url="https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/${tarball}"
    local tmp_dir
    tmp_dir=$(mktemp -d)

    log_info "Downloading from $url..."
    if command -v curl &>/dev/null; then
        run_cmd curl -sSL -o "${tmp_dir}/${tarball}" "$url"
    else
        run_cmd wget -q -O "${tmp_dir}/${tarball}" "$url"
    fi

    log_info "Extracting..."
    run_cmd tar xzf "${tmp_dir}/${tarball}" -C "$tmp_dir"

    run_cmd cp "${tmp_dir}/node_exporter-${NODE_EXPORTER_VERSION}.linux-${NODE_EXPORTER_ARCH}/node_exporter" \
        "$binary"
    run_cmd chown root:root "$binary"
    run_cmd chmod 755 "$binary"

    run_cmd rm -rf "$tmp_dir"

    log_info "node_exporter installed to $binary"
}

create_directories() {
    log_info "Creating directories..."
    run_cmd mkdir -p "$DATA_DIR" "$LOG_DIR" "$INSTALL_PREFIX"
    run_cmd chown "$NODE_EXPORTER_USER:$NODE_EXPORTER_USER" "$DATA_DIR" "$LOG_DIR" 2>/dev/null || true
}

install_systemd_service() {
    local service_file="${SYSTEMD_DIR}/${SERVICE_NAME}.service"
    local template_file
    template_file="$(dirname "$0")/../systemd/gvstress-node.service"

    if [[ -f "$service_file" ]] && ! $FORCE; then
        log_info "Systemd service already installed at $service_file"
        log_info "Use --force to reinstall"
        return 0
    fi

    if [[ ! -f "$template_file" ]]; then
        log_error "Service template not found: $template_file"
        exit 1
    fi

    log_info "Installing systemd service..."

    run_cmd sed \
        -e "s|__DATA_DIR__|${DATA_DIR}|g" \
        -e "s|__LOG_DIR__|${LOG_DIR}|g" \
        -e "s|__LISTEN_ADDRESS__|${LISTEN_ADDRESS}|g" \
        -e "s|__LISTEN_PORT__|${LISTEN_PORT}|g" \
        -e "s|__INSTALL_PREFIX__|${INSTALL_PREFIX}|g" \
        -e "s|__NODE_EXPORTER_USER__|${NODE_EXPORTER_USER}|g" \
        "$template_file" > "${tmp_service:-$service_file}"

    if $DRY_RUN; then
        log_dry "Would write service file to $service_file"
        return 0
    fi

    run_cmd cp "${tmp_service:-$service_file}" "$service_file"
    run_cmd chmod 644 "$service_file"

    log_info "Service file installed to $service_file"
}

enable_service() {
    log_info "Reloading systemd daemon..."
    run_cmd systemctl daemon-reload

    log_info "Enabling service ${SERVICE_NAME}..."
    run_cmd systemctl enable "$SERVICE_NAME"

    log_info "Starting service ${SERVICE_NAME}..."
    run_cmd systemctl restart "$SERVICE_NAME"

    if ! $DRY_RUN; then
        sleep 1
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            log_info "Service ${SERVICE_NAME} is running"
        else
            log_warn "Service ${SERVICE_NAME} failed to start. Check: journalctl -u ${SERVICE_NAME}"
        fi
    fi
}

main() {
    log_info "GVStress Native Node Installer"
    log_info "Config: $CONFIG_FILE"
    $DRY_RUN && log_info "Mode: DRY-RUN (no changes will be made)"

    preflight
    create_directories

    if [[ "$EXPORTER_ENABLED" == "true" ]]; then
        create_user
        install_node_exporter
        install_systemd_service
        enable_service
    else
        log_info "node_exporter disabled in config, skipping"
    fi

    log_info "Installation complete"
}

main "$@"
