# Workspace and colcon commands.

hamals_source_setup() {
    local setup_root setup_file
    setup_root=$1
    setup_file=

    if [ -n "${ZSH_VERSION:-}" ] && [ -f "${setup_root}.zsh" ]; then
        setup_file="${setup_root}.zsh"
    elif [ -n "${BASH_VERSION:-}" ] && [ -f "${setup_root}.bash" ]; then
        setup_file="${setup_root}.bash"
    elif [ -f "${setup_root}.bash" ]; then
        setup_file="${setup_root}.bash"
    elif [ -f "${setup_root}.zsh" ]; then
        setup_file="${setup_root}.zsh"
    elif [ -f "${setup_root}.sh" ]; then
        setup_file="${setup_root}.sh"
    fi

    if [ -z "$setup_file" ]; then
        return 1
    fi

    # shellcheck disable=SC1090
    . "$setup_file"
}

hamals_source_ros() {
    local distro setup_root candidate

    if hamals_is_macos; then
        if [ "${CONDA_DEFAULT_ENV:-}" != "ros2" ]; then
            if ! hamals_command_exists conda; then
                hamals_error "Conda bulunamadı. Önce environment.yml ortamını kurun."
                return 1
            fi
            if ! conda activate ros2 2>/dev/null; then
                hamals_error "'ros2' Conda ortamı etkinleştirilemedi. Önce 'conda activate ros2' çalıştırın."
                return 1
            fi
        fi
        if ! hamals_command_exists ros2; then
            hamals_error "ROS 2 komutları 'ros2' Conda ortamında bulunamadı."
            return 1
        fi
        return 0
    fi

    if hamals_command_exists ros2; then
        return 0
    fi

    distro=${ROS_DISTRO:-}
    if [ -n "$distro" ]; then
        setup_root="/opt/ros/$distro/setup"
        if hamals_source_setup "$setup_root"; then
            return 0
        fi
    fi

    for candidate in $(find /opt/ros -mindepth 2 -maxdepth 2 -type f \
        \( -name setup.bash -o -name setup.zsh -o -name setup.sh \) \
        2>/dev/null); do
        setup_root=${candidate%.*}
        if hamals_source_setup "$setup_root" && hamals_command_exists ros2; then
            return 0
        fi
    done

    hamals_error "ROS 2 ortamı bulunamadı. /opt/ros altındaki kurulumu source edin."
    return 1
}

hamals_source_workspace() {
    local workspace
    workspace="$HAMALS_REPO_ROOT/ros2_ws"
    if ! hamals_source_setup "$workspace/install/setup"; then
        hamals_error "Workspace henüz derlenmemiş. Önce 'h cbuild' çalıştırın."
        return 1
    fi
    export HAMALS_WORKSPACE_SOURCED="$workspace"
    return 0
}

hamals_source_environment() {
    hamals_source_ros || return 1
    hamals_source_workspace || return 1
}

hamals_cmd_csource() {
    if [ "$#" -ne 0 ]; then
        hamals_error "Kullanım: h csource"
        return 2
    fi
    hamals_source_environment || return 1
    hamals_ok "ROS 2 ve HAMALS workspace ortamı source edildi."
}

hamals_cmd_cbuild() {
    local workspace exit_status
    workspace="$HAMALS_REPO_ROOT/ros2_ws"
    hamals_source_ros || return 1
    if ! hamals_command_exists colcon; then
        hamals_error "colcon bulunamadı."
        return 127
    fi
    if [ ! -d "$workspace/src" ]; then
        hamals_error "Workspace kaynak dizini bulunamadı: $workspace/src"
        return 1
    fi

    if [ "$#" -eq 0 ]; then
        (cd "$workspace" && colcon build --symlink-install)
    else
        (cd "$workspace" && colcon build --symlink-install --packages-select "$@")
    fi
    exit_status=$?
    if [ "$exit_status" -ne 0 ]; then
        hamals_error "Build başarısız."
        return "$exit_status"
    fi

    hamals_source_workspace || return 1
    hamals_ok "Build tamamlandı ve workspace source edildi."
}

hamals_cmd_cclean() {
    local workspace expected
    if [ "$#" -ne 0 ]; then
        hamals_error "Kullanım: h cclean"
        return 2
    fi
    workspace="$HAMALS_REPO_ROOT/ros2_ws"
    expected="$(cd "$HAMALS_REPO_ROOT" 2>/dev/null && pwd -P)/ros2_ws"

    if [ -z "$HAMALS_REPO_ROOT" ] || [ "$workspace" != "$expected" ] || [ ! -d "$workspace/src" ]; then
        hamals_error "Güvenlik kontrolü başarısız; workspace temizlenmedi."
        return 1
    fi
    case "$workspace" in
        /|/ros2_ws|"$HOME"|"$HOME/ros2_ws")
            hamals_error "Güvenli olmayan workspace yolu; temizleme iptal edildi: $workspace"
            return 1
            ;;
    esac

    rm -rf -- "$workspace/build" "$workspace/install" "$workspace/log"
    hamals_ok "Workspace build, install ve log klasörleri temizlendi."
}

hamals_cmd_ctest() {
    local workspace test_status result_status
    workspace="$HAMALS_REPO_ROOT/ros2_ws"
    hamals_source_environment || return 1
    if ! hamals_command_exists colcon; then
        hamals_error "colcon bulunamadı."
        return 127
    fi

    if [ "$#" -eq 0 ]; then
        (cd "$workspace" && colcon test)
    else
        (cd "$workspace" && colcon test --packages-select "$@")
    fi
    test_status=$?
    (cd "$workspace" && colcon test-result --verbose)
    result_status=$?

    if [ "$test_status" -ne 0 ]; then
        return "$test_status"
    fi
    return "$result_status"
}
