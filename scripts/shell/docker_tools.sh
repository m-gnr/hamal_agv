# Docker Compose commands. Service names match docker/compose*.yml.

HAMALS_DEV_COMPOSE="$HAMALS_REPO_ROOT/docker/compose.yml"
HAMALS_ROBOT_COMPOSE="$HAMALS_REPO_ROOT/docker/compose.pi.yml"
HAMALS_DEV_SERVICE=hamal_dev
HAMALS_ROBOT_SERVICE=hamal_robot

hamals_require_docker() {
    if ! hamals_command_exists docker; then
        hamals_error "Docker bulunamadı."
        return 127
    fi
    if ! docker compose version >/dev/null 2>&1; then
        hamals_error "Docker Compose eklentisi bulunamadı."
        return 1
    fi
    if ! docker info >/dev/null 2>&1; then
        hamals_error "Docker daemon çalışmıyor."
        return 1
    fi
}

hamals_require_linux_docker() {
    if ! hamals_is_linux; then
        hamals_error "Bu komut Linux içindir. macOS geliştirme ortamında Conda kullanın."
        return 1
    fi
    hamals_require_docker
}

hamals_cmd_cdev() {
    if [ "$#" -ne 0 ]; then
        hamals_error "Kullanım: h cdev"
        return 2
    fi
    hamals_require_linux_docker || return 1
    docker compose -f "$HAMALS_DEV_COMPOSE" up -d "$HAMALS_DEV_SERVICE" || return $?
    hamals_ok "Development container çalışıyor; shell'e bağlanılıyor."
    docker compose -f "$HAMALS_DEV_COMPOSE" exec "$HAMALS_DEV_SERVICE" bash
}

hamals_cmd_crobot() {
    if [ "$#" -ne 0 ]; then
        hamals_error "Kullanım: h crobot"
        return 2
    fi
    hamals_require_linux_docker || return 1
    docker compose -f "$HAMALS_ROBOT_COMPOSE" up -d "$HAMALS_ROBOT_SERVICE" || return $?
    hamals_ok "Robot container başlatıldı: $HAMALS_ROBOT_SERVICE"
}

hamals_docker_target() {
    local target menu_status
    target=${1:-}
    if [ -z "$target" ]; then
        hamals_menu "Compose ortamı seçin" "Çıkış" "development" "robot"
        menu_status=$?
        [ "$menu_status" -eq 0 ] || return 2
        target=$HAMALS_MENU_RESULT
    fi
    case "$target" in
        dev|development)
            HAMALS_SELECTED_COMPOSE=$HAMALS_DEV_COMPOSE
            HAMALS_SELECTED_SERVICE=$HAMALS_DEV_SERVICE
            ;;
        robot|pi)
            HAMALS_SELECTED_COMPOSE=$HAMALS_ROBOT_COMPOSE
            HAMALS_SELECTED_SERVICE=$HAMALS_ROBOT_SERVICE
            ;;
        *)
            hamals_error "Bilinmeyen compose ortamı: $target (development veya robot kullanın)"
            return 1
            ;;
    esac
}

hamals_cmd_clogs() {
    if [ "$#" -gt 1 ]; then
        hamals_error "Kullanım: h clogs [development|robot]"
        return 2
    fi
    hamals_require_linux_docker || return 1
    hamals_docker_target "${1:-}"
    case $? in
        0) ;;
        2) return 0 ;;
        *) return 1 ;;
    esac
    docker compose -f "$HAMALS_SELECTED_COMPOSE" logs -f "$HAMALS_SELECTED_SERVICE"
}

hamals_cmd_cps() {
    if [ "$#" -ne 0 ]; then
        hamals_error "Kullanım: h cps"
        return 2
    fi
    hamals_require_docker || return 1
    printf 'Development (%s)\n' "$HAMALS_DEV_SERVICE"
    docker compose -f "$HAMALS_DEV_COMPOSE" ps
    printf '\nRobot (%s)\n' "$HAMALS_ROBOT_SERVICE"
    docker compose -f "$HAMALS_ROBOT_COMPOSE" ps
}

hamals_cmd_cstop() {
    local exit_status
    if [ "$#" -ne 0 ]; then
        hamals_error "Kullanım: h cstop"
        return 2
    fi
    hamals_require_docker || return 1
    exit_status=0
    docker compose -f "$HAMALS_DEV_COMPOSE" stop "$HAMALS_DEV_SERVICE" || exit_status=$?
    docker compose -f "$HAMALS_ROBOT_COMPOSE" stop "$HAMALS_ROBOT_SERVICE" || exit_status=$?
    if [ "$exit_status" -eq 0 ]; then
        hamals_ok "HAMALS servisleri durduruldu; container, volume ve image'lar korundu."
    fi
    return "$exit_status"
}
