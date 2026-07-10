# Interactive and direct ROS 2 tools.

hamals_refresh_workspace_packages() {
    local workspace raw_records
    workspace="$HAMALS_REPO_ROOT/ros2_ws"
    if ! hamals_command_exists colcon; then
        hamals_error "colcon bulunamadı."
        return 127
    fi
    raw_records=$(cd "$workspace" && colcon list 2>/dev/null) || {
        hamals_error "Workspace paketleri 'colcon list' ile okunamadı: $workspace"
        return 1
    }
    HAMALS_COLCON_RECORDS=$(printf '%s\n' "$raw_records" | awk 'NF >= 3 {
        name=$1
        type=$NF
        gsub(/^\(/, "", type)
        gsub(/\)$/, "", type)
        path=$2
        for (i=3; i<NF; i++) path=path " " $i
        printf "%s\t%s\t%s\n", name, path, type
    }' | sort -t '	' -k1,1 -u)
    if [ -z "$HAMALS_COLCON_RECORDS" ]; then
        hamals_error "colcon list workspace içinde paket döndürmedi: $workspace"
        return 1
    fi
}

hamals_workspace_packages() {
    printf '%s\n' "$HAMALS_COLCON_RECORDS" | awk -F '\t' 'NF >= 2 { print $1 }'
}

hamals_get_package_metadata() {
    local package record source_path
    package=$1
    record=$(printf '%s\n' "$HAMALS_COLCON_RECORDS" |
        awk -F '\t' -v package="$package" '$1 == package { print; exit }')
    if [ -z "$record" ]; then
        HAMALS_PACKAGE_NAME=$package
        HAMALS_PACKAGE_SOURCE=
        HAMALS_PACKAGE_TYPE=
        HAMALS_PACKAGE_PREFIX=$(ros2 pkg prefix "$package" 2>/dev/null) || HAMALS_PACKAGE_PREFIX=
        return 1
    fi

    HAMALS_PACKAGE_NAME=$(printf '%s\n' "$record" | awk -F '\t' '{ print $1 }')
    source_path=$(printf '%s\n' "$record" | awk -F '\t' '{ print $2 }')
    HAMALS_PACKAGE_TYPE=$(printf '%s\n' "$record" | awk -F '\t' '{ print $3 }')
    case "$source_path" in
        /*) ;;
        *) source_path="$HAMALS_REPO_ROOT/ros2_ws/$source_path" ;;
    esac
    if [ -d "$source_path" ]; then
        source_path=$(cd "$source_path" 2>/dev/null && pwd -P)
    fi
    HAMALS_PACKAGE_SOURCE=$source_path
    HAMALS_PACKAGE_PREFIX=$(ros2 pkg prefix "$package" 2>/dev/null) || HAMALS_PACKAGE_PREFIX=
    return 0
}

hamals_package_executables() {
    ros2 pkg executables "$1" 2>/dev/null |
        awk -v package="$1" '$1 == package { print $2 }' |
        sort -u
}

hamals_source_declares_executables() {
    local source_path
    source_path=$1
    if [ -f "$source_path/CMakeLists.txt" ] &&
        grep -Eq '^[[:space:]]*add_executable[[:space:]]*\(' "$source_path/CMakeLists.txt"; then
        return 0
    fi
    if [ -f "$source_path/setup.py" ] && awk '
        /console_scripts/ { in_scripts=1; next }
        in_scripts && /=/ { found=1 }
        in_scripts && /]/ { exit }
        END { exit(found ? 0 : 1) }
    ' "$source_path/setup.py"; then
        return 0
    fi
    return 1
}

hamals_debug_executable_package() {
    local package executables executable_count
    package=$1
    executables=$2
    executable_count=$(hamals_count_lines "$executables")
    hamals_get_package_metadata "$package" >/dev/null 2>&1 || :
    printf '\nWorkspace: %s\n' "$HAMALS_REPO_ROOT/ros2_ws" >&2
    printf 'Package: %s\n' "$package" >&2
    printf 'Package type: %s\n' "${HAMALS_PACKAGE_TYPE:-(bilinmiyor)}" >&2
    printf 'Source path: %s\n' "${HAMALS_PACKAGE_SOURCE:-(workspace dışı)}" >&2
    printf 'Install prefix: %s\n' "${HAMALS_PACKAGE_PREFIX:-(kurulu değil)}" >&2
    printf 'Executable count: %s\n' "$executable_count" >&2
}

hamals_executable_packages() {
    local debug package result executables
    debug=$1
    result=
    for package in $(hamals_workspace_packages); do
        hamals_get_package_metadata "$package" >/dev/null 2>&1 || continue
        executables=$(hamals_package_executables "$package")
        if [ "$debug" -eq 1 ]; then
            hamals_debug_executable_package "$package" "$executables"
        fi
        if [ -z "$HAMALS_PACKAGE_PREFIX" ]; then
            hamals_warn "$package kaynakta var ancak install edilmemiş; 'h cbuild $package' çalıştırın." >&2
        elif [ -z "$executables" ] && hamals_source_declares_executables "$HAMALS_PACKAGE_SOURCE"; then
            hamals_warn "$package executable tanımlıyor ancak ROS indexinde bulunamadı; build/install eski olabilir." >&2
        fi
        if [ -n "$executables" ]; then
            result="${result}${result:+
}${package}"
        fi
    done
    printf '%s\n' "$result"
}

hamals_choose_executable() {
    local package debug executables menu_status
    package=$1
    debug=$2
    hamals_get_package_metadata "$package" >/dev/null 2>&1 || {
        hamals_error "'$package' mevcut workspace paketleri arasında bulunamadı."
        return 1
    }
    executables=$(hamals_package_executables "$package")
    if [ "$debug" -eq 1 ]; then
        hamals_debug_executable_package "$package" "$executables"
    fi
    if [ -z "$executables" ]; then
        if [ -z "$HAMALS_PACKAGE_PREFIX" ]; then
            hamals_error "'$package' kaynakta var ancak install edilmemiş. 'h cbuild $package' çalıştırın."
        elif hamals_source_declares_executables "$HAMALS_PACKAGE_SOURCE"; then
            hamals_error "'$package' executable tanımlıyor fakat kurulu ROS indexinde yok; paketi yeniden build edin."
        else
            hamals_error "'$package' paketinde executable bulunamadı."
        fi
        return 1
    fi
    hamals_menu_from_lines "Executable seçin ($package)" "Geri" "$executables"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return "$menu_status"
    HAMALS_SELECTED_EXECUTABLE=$HAMALS_MENU_RESULT
}

hamals_cmd_crun() {
    local debug package executable packages menu_status
    hamals_source_environment || return 1
    debug=0
    if [ "${1:-}" = "--debug" ]; then
        debug=1
        shift
    fi
    hamals_refresh_workspace_packages || return $?

    if [ "$#" -ge 2 ]; then
        package=$1
        executable=$2
        shift 2
        if [ "$debug" -eq 1 ]; then
            hamals_debug_executable_package "$package" "$(hamals_package_executables "$package")"
        fi
        ros2 run "$package" "$executable" "$@"
        return $?
    fi

    if [ "$#" -eq 1 ]; then
        package=$1
    else
        packages=$(hamals_executable_packages "$debug")
        if [ -z "$packages" ]; then
            hamals_error "Workspace içinde executable içeren paket bulunamadı."
            return 1
        fi
        hamals_menu_from_lines "Executable içeren paketler" "Çıkış" "$packages"
        menu_status=$?
        [ "$menu_status" -eq 0 ] || return 0
        package=$HAMALS_MENU_RESULT
    fi

    hamals_choose_executable "$package" "$debug"
    menu_status=$?
    if [ "$menu_status" -eq 2 ]; then
        return 0
    elif [ "$menu_status" -ne 0 ]; then
        return "$menu_status"
    fi
    ros2 run "$package" "$HAMALS_SELECTED_EXECUTABLE"
}

hamals_find_launch_files() {
    [ -d "$1" ] || return 0
    find "$1" -maxdepth 1 \( -type f -o -type l \) \( \
        -name '*.launch.py' -o -name '*.launch.xml' -o \
        -name '*.launch.yaml' -o -name '*.launch.yml' \
    \) -exec basename {} \; 2>/dev/null | sort -u
}

hamals_package_launch_files() {
    local package install_dir source_dir installed_files source_files
    package=$1
    hamals_get_package_metadata "$package" >/dev/null 2>&1 || return 0
    install_dir=
    [ -n "$HAMALS_PACKAGE_PREFIX" ] && install_dir="$HAMALS_PACKAGE_PREFIX/share/$package/launch"
    source_dir="$HAMALS_PACKAGE_SOURCE/launch"
    installed_files=$(hamals_find_launch_files "$install_dir")
    source_files=$(hamals_find_launch_files "$source_dir")
    printf '%s\n%s\n' "$installed_files" "$source_files" | awk 'NF' | sort -u
}

hamals_package_source_only_launches() {
    local package install_dir source_dir installed_files source_files launch_file
    package=$1
    hamals_get_package_metadata "$package" >/dev/null 2>&1 || return 0
    install_dir=
    [ -n "$HAMALS_PACKAGE_PREFIX" ] && install_dir="$HAMALS_PACKAGE_PREFIX/share/$package/launch"
    source_dir="$HAMALS_PACKAGE_SOURCE/launch"
    installed_files=$(hamals_find_launch_files "$install_dir")
    source_files=$(hamals_find_launch_files "$source_dir")
    for launch_file in $(printf '%s\n' "$source_files"); do
        if ! printf '%s\n' "$installed_files" | grep -Fxq "$launch_file"; then
            printf '%s\n' "$launch_file"
        fi
    done
}

hamals_debug_launch_package() {
    local package launch_files install_dir source_dir launch_count
    package=$1
    launch_files=$2
    launch_count=$(hamals_count_lines "$launch_files")
    hamals_get_package_metadata "$package" >/dev/null 2>&1 || :
    install_dir="${HAMALS_PACKAGE_PREFIX:+$HAMALS_PACKAGE_PREFIX/share/$package/launch}"
    source_dir="${HAMALS_PACKAGE_SOURCE:+$HAMALS_PACKAGE_SOURCE/launch}"
    printf '\nWorkspace: %s\n' "$HAMALS_REPO_ROOT/ros2_ws" >&2
    printf 'Package: %s\n' "$package" >&2
    printf 'Package type: %s\n' "${HAMALS_PACKAGE_TYPE:-(bilinmiyor)}" >&2
    printf 'Source path: %s\n' "${HAMALS_PACKAGE_SOURCE:-(workspace dışı)}" >&2
    printf 'Install prefix: %s\n' "${HAMALS_PACKAGE_PREFIX:-(kurulu değil)}" >&2
    printf 'Launch directory checked (install): %s\n' "${install_dir:-(yok)}" >&2
    printf 'Launch directory checked (source): %s\n' "${source_dir:-(yok)}" >&2
    printf 'Launch file count: %s\n' "$launch_count" >&2
}

hamals_launch_packages() {
    local debug package result launch_files source_only
    debug=$1
    result=
    for package in $(hamals_workspace_packages); do
        hamals_get_package_metadata "$package" >/dev/null 2>&1 || continue
        launch_files=$(hamals_package_launch_files "$package")
        if [ "$debug" -eq 1 ]; then
            hamals_debug_launch_package "$package" "$launch_files"
        fi
        source_only=$(hamals_package_source_only_launches "$package")
        if [ -n "$source_only" ]; then
            hamals_warn "$package için source'da bulunan bazı launch dosyaları install edilmemiş; 'h cbuild $package' çalıştırın." >&2
        fi
        if [ -n "$launch_files" ]; then
            result="${result}${result:+
}${package}"
        fi
    done
    printf '%s\n' "$result"
}

hamals_choose_launch() {
    local package debug launch_files source_only menu_status
    package=$1
    debug=$2
    hamals_get_package_metadata "$package" >/dev/null 2>&1 || {
        hamals_error "'$package' mevcut workspace paketleri arasında bulunamadı."
        return 1
    }
    launch_files=$(hamals_package_launch_files "$package")
    if [ "$debug" -eq 1 ]; then
        hamals_debug_launch_package "$package" "$launch_files"
    fi
    if [ -z "$launch_files" ]; then
        hamals_error "'$package' paketinde desteklenen launch dosyası bulunamadı."
        return 1
    fi
    source_only=$(hamals_package_source_only_launches "$package")
    if [ -n "$source_only" ]; then
        hamals_warn "Install edilmemiş source launch dosyaları: $(printf '%s' "$source_only" | tr '\n' ' ')"
    fi
    hamals_menu_from_lines "Launch dosyası seçin ($package)" "Geri" "$launch_files"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return "$menu_status"
    HAMALS_SELECTED_LAUNCH=$HAMALS_MENU_RESULT
}

hamals_cmd_claunch() {
    local debug package launch_file packages source_only menu_status
    hamals_source_environment || return 1
    debug=0
    if [ "${1:-}" = "--debug" ]; then
        debug=1
        shift
    fi
    hamals_refresh_workspace_packages || return $?

    if [ "$#" -ge 2 ]; then
        package=$1
        launch_file=$2
        shift 2
        if hamals_get_package_metadata "$package" >/dev/null 2>&1; then
            if [ "$debug" -eq 1 ]; then
                hamals_debug_launch_package "$package" "$(hamals_package_launch_files "$package")"
            fi
            source_only=$(hamals_package_source_only_launches "$package")
            if printf '%s\n' "$source_only" | grep -Fxq "$launch_file"; then
                hamals_error "'$launch_file' source dizininde var fakat install edilmemiş. 'h cbuild $package' sonrası tekrar deneyin."
                return 1
            fi
        fi
        ros2 launch "$package" "$launch_file" "$@"
        return $?
    fi

    if [ "$#" -eq 1 ]; then
        package=$1
    else
        packages=$(hamals_launch_packages "$debug")
        if [ -z "$packages" ]; then
            hamals_error "Workspace içinde launch dosyası bulunan paket yok."
            return 1
        fi
        hamals_menu_from_lines "Launch dosyası bulunan paketler" "Çıkış" "$packages"
        menu_status=$?
        [ "$menu_status" -eq 0 ] || return 0
        package=$HAMALS_MENU_RESULT
    fi

    hamals_choose_launch "$package" "$debug"
    menu_status=$?
    if [ "$menu_status" -eq 2 ]; then
        return 0
    elif [ "$menu_status" -ne 0 ]; then
        return "$menu_status"
    fi
    source_only=$(hamals_package_source_only_launches "$package")
    if printf '%s\n' "$source_only" | grep -Fxq "$HAMALS_SELECTED_LAUNCH"; then
        hamals_error "'$HAMALS_SELECTED_LAUNCH' source dizininde var fakat install edilmemiş. 'h cbuild $package' sonrası tekrar deneyin."
        return 1
    fi
    ros2 launch "$package" "$HAMALS_SELECTED_LAUNCH"
}

hamals_choose_graph_item() {
    local kind title items menu_status
    kind=$1
    title=$2
    case "$kind" in
        topic) items=$(ros2 topic list 2>/dev/null | sort -u) ;;
        node) items=$(ros2 node list 2>/dev/null | sort -u) ;;
        *) hamals_error "Bilinmeyen ROS graph türü: $kind"; return 1 ;;
    esac
    if [ -z "$items" ]; then
        hamals_warn "Aktif $kind bulunamadı."
        return 1
    fi
    hamals_menu_from_lines "$title" "Geri" "$items"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return "$menu_status"
    HAMALS_SELECTED_GRAPH_ITEM=$HAMALS_MENU_RESULT
}

hamals_topic_operation() {
    local operation topic
    operation=$1
    topic=${2:-}
    case "$operation" in
        list)
            ros2 topic list
            ;;
        echo|info|hz|type)
            if [ -z "$topic" ]; then
                hamals_error "Kullanım: h ctopic $operation <topic>"
                return 2
            fi
            ros2 topic "$operation" "$topic"
            ;;
        *)
            hamals_error "Bilinmeyen topic işlemi: $operation"
            return 2
            ;;
    esac
}

hamals_cmd_ctopic() {
    local operation menu_status
    hamals_source_environment || return 1
    if [ "$#" -gt 0 ]; then
        hamals_topic_operation "$@"
        return $?
    fi

    hamals_menu "ROS 2 Topic İşlemleri" "Çıkış" \
        "Topic listesini göster" \
        "Topic verisini izle" \
        "Topic bilgisini göster" \
        "Topic frekansını ölç" \
        "Topic tipini göster"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return 0
    case "$HAMALS_MENU_RESULT" in
        "Topic listesini göster") operation=list ;;
        "Topic verisini izle") operation=echo ;;
        "Topic bilgisini göster") operation=info ;;
        "Topic frekansını ölç") operation=hz ;;
        "Topic tipini göster") operation=type ;;
    esac
    if [ "$operation" = list ]; then
        hamals_topic_operation list
        return $?
    fi
    hamals_choose_graph_item topic "Topic seçin"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return 0
    hamals_topic_operation "$operation" "$HAMALS_SELECTED_GRAPH_ITEM"
}

hamals_cmd_cnode() {
    local operation node menu_status
    hamals_source_environment || return 1
    if [ "$#" -gt 0 ]; then
        operation=$1
        node=${2:-}
        case "$operation" in
            list) ros2 node list ;;
            info)
                if [ -z "$node" ]; then
                    hamals_error "Kullanım: h cnode info <node>"
                    return 2
                fi
                ros2 node info "$node"
                ;;
            *) hamals_error "Bilinmeyen node işlemi: $operation"; return 2 ;;
        esac
        return $?
    fi

    hamals_menu "ROS 2 Node İşlemleri" "Çıkış" \
        "Node listesini göster" \
        "Node seçip detaylarını göster"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return 0
    if [ "$HAMALS_MENU_RESULT" = "Node listesini göster" ]; then
        ros2 node list
        return $?
    fi
    hamals_choose_graph_item node "Node seçin"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return 0
    ros2 node info "$HAMALS_SELECTED_GRAPH_ITEM"
}

hamals_tf_frames() {
    local output topic
    output=
    for topic in /tf /tf_static; do
        output="${output}
$(hamals_timeout 2 ros2 topic echo "$topic" --once 2>/dev/null)"
    done
    printf '%s\n' "$output" |
        awk '/(^|[[:space:]])frame_id:|(^|[[:space:]])child_frame_id:/ {
            value=$0
            sub(/^[^:]*:[[:space:]]*/, "", value)
            gsub(/["'"'"']/, "", value)
            if (value != "") print value
        }' | sort -u
}

hamals_tf_available() {
    local source_frame target_frame output
    source_frame=$1
    target_frame=$2
    output=$(hamals_timeout "${3:-1}" ros2 run tf2_ros tf2_echo \
        "$source_frame" "$target_frame" 2>&1) || :
    printf '%s\n' "$output" | grep -Eq 'Translation:|At time|translation:'
}

hamals_tf_check_all() {
    local pair source_frame target_frame
    for pair in "map odom" "odom base_footprint" \
        "base_footprint base_link" "base_link lidar_link"; do
        source_frame=${pair%% *}
        target_frame=${pair#* }
        if hamals_tf_available "$source_frame" "$target_frame" 2; then
            printf '✓ %s -> %s\n' "$source_frame" "$target_frame"
        else
            printf '✗ %s -> %s\n' "$source_frame" "$target_frame"
        fi
    done
}

hamals_tf_tree() {
    local output_dir temp_dir stamp generated file_name destination
    output_dir="$HAMALS_REPO_ROOT/output/tf"
    mkdir -p "$output_dir" || return 1
    temp_dir="$output_dir/.view_frames.$$"
    mkdir "$temp_dir" || return 1

    (cd "$temp_dir" && ros2 run tf2_tools view_frames)
    if [ "$?" -ne 0 ]; then
        rmdir "$temp_dir" 2>/dev/null
        hamals_error "TF ağacı oluşturulamadı. tf2_tools kurulumunu ve aktif TF verisini kontrol edin."
        return 1
    fi

    stamp=$(date '+%Y%m%d-%H%M%S')
    generated=0
    for file_name in $(find "$temp_dir" -maxdepth 1 -type f -name 'frames*' \
        -exec basename {} \; 2>/dev/null); do
        destination="$output_dir/${stamp}-${file_name}"
        mv "$temp_dir/$file_name" "$destination" || continue
        printf 'TF ağacı: %s\n' "$destination"
        generated=1
    done
    rmdir "$temp_dir" 2>/dev/null
    if [ "$generated" -eq 0 ]; then
        hamals_error "tf2_tools tamamlandı ancak bir çıktı dosyası bulunamadı."
        return 1
    fi
}

hamals_tf_echo_menu() {
    local frames menu_status source_frame target_frame
    frames=$(hamals_tf_frames)
    if [ -z "$frames" ]; then
        hamals_error "Kısa sürede TF frame verisi alınamadı."
        return 1
    fi
    hamals_menu_from_lines "Kaynak frame seçin" "Geri" "$frames"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return 0
    source_frame=$HAMALS_MENU_RESULT
    hamals_menu_from_lines "Hedef frame seçin" "Geri" "$frames"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return 0
    target_frame=$HAMALS_MENU_RESULT
    ros2 run tf2_ros tf2_echo "$source_frame" "$target_frame"
}

hamals_cmd_ctf() {
    local operation source_frame target_frame frames menu_status
    hamals_source_environment || return 1
    if [ "$#" -gt 0 ]; then
        operation=$1
        shift
        case "$operation" in
            echo)
                if [ "$#" -ne 2 ]; then
                    hamals_error "Kullanım: h ctf echo <source> <target>"
                    return 2
                fi
                ros2 run tf2_ros tf2_echo "$1" "$2"
                ;;
            frames)
                frames=$(hamals_tf_frames)
                if [ -z "$frames" ]; then
                    hamals_warn "Kısa sürede /tf veya /tf_static verisi alınamadı."
                    return 1
                fi
                printf 'TF frame listesi\n\n%s\n' "$frames"
                ;;
            tree) hamals_tf_tree ;;
            check) hamals_tf_check_all ;;
            *) hamals_error "Bilinmeyen TF işlemi: $operation"; return 2 ;;
        esac
        return $?
    fi

    hamals_menu "TF İşlemleri" "Çıkış" \
        "İki frame arasındaki transformu izle" \
        "TF frame listesini göster" \
        "TF ağacını oluştur" \
        "Temel HAMALS TF bağlantılarını kontrol et"
    menu_status=$?
    [ "$menu_status" -eq 0 ] || return 0
    case "$HAMALS_MENU_RESULT" in
        "İki frame arasındaki transformu izle") hamals_tf_echo_menu ;;
        "TF frame listesini göster")
            frames=$(hamals_tf_frames)
            [ -n "$frames" ] && printf 'TF frame listesi\n\n%s\n' "$frames" || hamals_warn "TF verisi alınamadı."
            ;;
        "TF ağacını oluştur") hamals_tf_tree ;;
        "Temel HAMALS TF bağlantılarını kontrol et") hamals_tf_check_all ;;
    esac
}
