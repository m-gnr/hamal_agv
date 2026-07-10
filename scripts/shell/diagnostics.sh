# Installation and runtime diagnostics.

hamals_doctor_check_command() {
    local command_name label
    command_name=$1
    label=$2
    if hamals_command_exists "$command_name"; then
        hamals_ok "$label bulundu"
        return 0
    fi
    printf '✗ %s bulunamadı\n' "$label"
    return 1
}

hamals_doctor_compose() {
    if ! hamals_command_exists docker; then
        printf '✗ Docker bulunamadı\n'
        return 1
    fi
    hamals_ok "Docker bulundu"
    if docker info >/dev/null 2>&1; then
        hamals_ok "Docker çalışıyor"
    else
        printf '✗ Docker daemon çalışmıyor\n'
    fi
    if docker compose version >/dev/null 2>&1; then
        hamals_ok "Docker Compose bulundu"
    else
        printf '✗ Docker Compose bulunamadı\n'
    fi
}

hamals_cmd_cdoctor() {
    local workspace setup_found setup_found_candidate device package missing_packages
    if [ "$#" -ne 0 ]; then
        hamals_error "Kullanım: h cdoctor"
        return 2
    fi
    workspace="$HAMALS_REPO_ROOT/ros2_ws"
    setup_found=0

    printf 'HAMALS DOCTOR\n\n'
    hamals_doctor_check_command git Git || :

    if hamals_is_macos; then
        hamals_doctor_check_command conda Conda || :
        if [ "${CONDA_DEFAULT_ENV:-}" = "ros2" ]; then
            hamals_ok "Doğru Conda ortamı aktif (ros2)"
        else
            printf '✗ Aktif Conda ortamı ros2 değil\n'
        fi
        hamals_warn "Docker robot, serial cihaz ve dialout kontrolleri macOS'ta atlandı."
    else
        hamals_doctor_compose
    fi

    if hamals_command_exists ros2; then
        if [ -n "${ROS_DISTRO:-}" ]; then
            hamals_ok "ROS 2 ${ROS_DISTRO} aktif"
        else
            hamals_ok "ROS 2 komutları erişilebilir"
        fi
    else
        printf '✗ ros2 komutu bulunamadı\n'
    fi
    hamals_doctor_check_command colcon colcon || :

    if [ -d "$HAMALS_REPO_ROOT/.git" ] && [ -f "$HAMALS_REPO_ROOT/README.md" ]; then
        hamals_ok "Repo kökü doğrulandı"
    else
        printf '✗ Repo kökü doğrulanamadı\n'
    fi
    if [ -d "$workspace/src" ]; then
        hamals_ok "Workspace bulundu"
    else
        printf '✗ Workspace bulunamadı: %s\n' "$workspace/src"
    fi
    if [ -d "$workspace/build" ] && [ -d "$workspace/install" ]; then
        hamals_ok "Workspace build edilmiş"
    else
        printf '✗ Workspace build edilmemiş\n'
    fi
    for setup_found_candidate in "$workspace/install/setup.bash" \
        "$workspace/install/setup.zsh" "$workspace/install/setup.sh"; do
        if [ -f "$setup_found_candidate" ]; then
            setup_found=1
            break
        fi
    done
    if [ "$setup_found" -eq 1 ]; then
        hamals_ok "Workspace setup dosyası bulundu"
    else
        printf '✗ Workspace setup dosyası bulunamadı\n'
    fi
    [ -f "$HAMALS_REPO_ROOT/docker/compose.yml" ] && \
        hamals_ok "Development compose dosyası bulundu" || \
        printf '✗ Development compose dosyası bulunamadı\n'
    [ -f "$HAMALS_REPO_ROOT/docker/compose.pi.yml" ] && \
        hamals_ok "Robot compose dosyası bulundu" || \
        printf '✗ Robot compose dosyası bulunamadı\n'

    if hamals_command_exists ros2; then
        missing_packages=
        for package in tf2_ros tf2_tools nav2_bringup slam_toolbox \
            robot_localization rplidar_ros robot_state_publisher \
            joint_state_publisher xacro; do
            if ros2 pkg prefix "$package" >/dev/null 2>&1; then
                hamals_ok "ROS paketi bulundu: $package"
            else
                printf '✗ ROS paketi bulunamadı: %s\n' "$package"
                missing_packages="${missing_packages} $package"
            fi
        done
    else
        missing_packages=" tf2_ros tf2_tools nav2_bringup slam_toolbox robot_localization rplidar_ros robot_state_publisher joint_state_publisher xacro"
        hamals_warn "Temel ROS paketleri ros2 erişilemediği için kontrol edilemedi."
    fi

    if hamals_is_linux; then
        for device in /dev/ttyACM0 /dev/ttyUSB0; do
            if [ -e "$device" ]; then
                hamals_ok "Serial cihaz bulundu: $device"
                if [ -r "$device" ] && [ -w "$device" ]; then
                    hamals_ok "Serial cihaz erişim izni var: $device"
                else
                    printf '✗ Serial cihaz erişim izni yok: %s\n' "$device"
                fi
            else
                hamals_warn "Serial cihaz bulunamadı: $device"
            fi
        done
        if id -nG 2>/dev/null | tr ' ' '\n' | grep -qx dialout; then
            hamals_ok "Kullanıcı dialout grubunda"
        else
            hamals_warn "Kullanıcı dialout grubunda değil"
        fi
    fi

    printf '\nÖnerilen çözümler:\n'
    if ! hamals_command_exists ros2; then
        if hamals_is_macos; then
            printf '  conda activate ros2\n'
        else
            printf '  source /opt/ros/<distro>/setup.bash\n'
        fi
    fi
    if ! hamals_command_exists colcon; then
        printf '  ROS 2 colcon paketini kurun ve shell ortamını yeniden source edin.\n'
    fi
    if [ "$setup_found" -ne 1 ]; then
        printf '  h cbuild\n'
    fi
    if hamals_is_linux && ! id -nG 2>/dev/null | tr ' ' '\n' | grep -qx dialout; then
        printf '  sudo usermod -aG dialout "$USER"\n'
        printf '  Grup değişikliğinden sonra oturumu kapatıp yeniden açın.\n'
    fi
    if [ -n "$missing_packages" ]; then
        printf '  Eksik ROS paketlerini sisteminizin ROS 2 paket yöneticisiyle kurun:%s\n' "$missing_packages"
    fi
}

hamals_workspace_is_sourced() {
    local workspace
    workspace="$HAMALS_REPO_ROOT/ros2_ws"
    if [ "${HAMALS_WORKSPACE_SOURCED:-}" = "$workspace" ]; then
        return 0
    fi
    case ":${AMENT_PREFIX_PATH:-}:${COLCON_PREFIX_PATH:-}:" in
        *"$workspace/install"*) return 0 ;;
    esac
    return 1
}

hamals_compose_service_running() {
    local compose_file service
    compose_file=$1
    service=$2
    hamals_command_exists docker || return 1
    docker compose -f "$compose_file" ps --services --filter status=running 2>/dev/null |
        grep -qx "$service"
}

hamals_status_line() {
    local label state detail
    label=$1
    state=$2
    detail=${3:-}
    if [ "$state" = ok ]; then
        printf '  %-23s ✓ %s\n' "$label" "$detail"
    elif [ "$state" = warn ]; then
        printf '  %-23s ! %s\n' "$label" "$detail"
    else
        printf '  %-23s ✗ %s\n' "$label" "$detail"
    fi
}

hamals_status_tf_line() {
    local source_frame target_frame
    source_frame=$1
    target_frame=$2
    if hamals_tf_available "$source_frame" "$target_frame" 1; then
        hamals_status_line "$source_frame -> $target_frame" ok available
    else
        hamals_status_line "$source_frame -> $target_frame" fail unavailable
    fi
}

hamals_status_topic_rate() {
    local topic topics output rate
    topic=$1
    topics=$2
    if ! printf '%s\n' "$topics" | grep -Fxq "$topic"; then
        hamals_status_line "$topic rate" fail "topic unavailable"
        return
    fi
    output=$(hamals_timeout 1 ros2 topic hz "$topic" --window 3 2>&1) || :
    rate=$(printf '%s\n' "$output" | awk '/average rate:/ { print $3; exit }')
    if [ -n "$rate" ]; then
        hamals_status_line "$topic rate" ok "${rate} Hz"
    else
        hamals_status_line "$topic rate" warn "topic exists but no data received"
    fi
}

hamals_cmd_cstatus() {
    local full nodes topics node_count topic_count topic state
    full=0
    if [ "${1:-}" = "--full" ]; then
        full=1
        shift
    fi
    if [ "$#" -ne 0 ]; then
        hamals_error "Kullanım: h cstatus [--full]"
        return 2
    fi

    printf 'HAMALS SYSTEM STATUS\n\nEnvironment\n'
    if hamals_command_exists ros2; then
        hamals_status_line "ROS 2" ok active
    else
        hamals_status_line "ROS 2" fail inactive
    fi
    if hamals_workspace_is_sourced; then
        hamals_status_line "Workspace" ok sourced
    else
        hamals_status_line "Workspace" fail "not sourced"
    fi
    if hamals_command_exists docker && docker info >/dev/null 2>&1; then
        hamals_status_line "Docker" ok running
    else
        hamals_status_line "Docker" fail "not running"
    fi
    if hamals_compose_service_running "$HAMALS_DEV_COMPOSE" "$HAMALS_DEV_SERVICE"; then
        hamals_status_line "Development container" ok running
    else
        hamals_status_line "Development container" fail stopped
    fi
    if hamals_compose_service_running "$HAMALS_ROBOT_COMPOSE" "$HAMALS_ROBOT_SERVICE"; then
        hamals_status_line "Robot container" ok running
    else
        hamals_status_line "Robot container" fail stopped
    fi

    printf '\nHardware\n'
    if hamals_is_macos; then
        hamals_status_line "Serial checks" warn "skipped on macOS"
    else
        if [ -e /dev/ttyACM0 ]; then
            hamals_status_line "/dev/ttyACM0" ok connected
            if [ -r /dev/ttyACM0 ] && [ -w /dev/ttyACM0 ]; then
                hamals_status_line "Serial permission" ok available
            else
                hamals_status_line "Serial permission" fail unavailable
            fi
        else
            hamals_status_line "/dev/ttyACM0" fail disconnected
        fi
    fi

    nodes=
    topics=
    if hamals_command_exists ros2; then
        nodes=$(hamals_timeout 1 ros2 node list 2>/dev/null) || nodes=
        topics=$(hamals_timeout 1 ros2 topic list 2>/dev/null) || topics=
    fi
    node_count=$(hamals_count_lines "$nodes")
    topic_count=$(hamals_count_lines "$topics")
    printf '\nROS Graph\n'
    if ! hamals_command_exists ros2; then
        hamals_status_line "Nodes" fail "ROS 2 inactive"
        hamals_status_line "Topics" fail "ROS 2 inactive"
    else
        [ "$node_count" -gt 0 ] && state=ok || state=warn
        hamals_status_line "Nodes" "$state" "$node_count active"
        [ "$topic_count" -gt 0 ] && state=ok || state=warn
        hamals_status_line "Topics" "$state" "$topic_count active"
    fi
    for topic in /cmd_vel /odom_raw /imu/data /scan; do
        if printf '%s\n' "$topics" | grep -Fxq "$topic"; then
            hamals_status_line "$topic" ok available
        else
            hamals_status_line "$topic" fail unavailable
        fi
    done

    if [ "$full" -eq 1 ]; then
        printf '\nTopic Rates\n'
        hamals_status_topic_rate /odom_raw "$topics"
        hamals_status_topic_rate /imu/data "$topics"
        hamals_status_topic_rate /scan "$topics"
    fi

    printf '\nTransforms\n'
    if hamals_command_exists ros2; then
        hamals_status_tf_line map odom
        hamals_status_tf_line odom base_footprint
        hamals_status_tf_line base_footprint base_link
        hamals_status_tf_line base_link lidar_link
    else
        for state in "map -> odom" "odom -> base_footprint" \
            "base_footprint -> base_link" "base_link -> lidar_link"; do
            hamals_status_line "$state" fail "ROS 2 inactive"
        done
    fi
}
