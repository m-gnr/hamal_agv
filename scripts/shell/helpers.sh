# Shared helpers for the HAMALS shell CLI.

hamals_error() {
    printf 'Hata: %s\n' "$*" >&2
}

hamals_warn() {
    printf '! %s\n' "$*"
}

hamals_ok() {
    printf '✓ %s\n' "$*"
}

hamals_command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Usage: hamals_menu "Title" "Exit label" "option 1" "option 2" ...
# The selected value is returned in HAMALS_MENU_RESULT. This deliberately uses
# positional parameters instead of shell-specific array indexing.
hamals_menu() {
    local title zero_label choice count index option
    title=$1
    zero_label=$2
    shift 2
    count=$#
    HAMALS_MENU_RESULT=

    if [ "$count" -eq 0 ]; then
        hamals_warn "Gösterilecek seçenek yok."
        return 1
    fi

    while :; do
        printf '\n%s\n\n' "$title"
        index=1
        for option in "$@"; do
            printf '%s) %s\n' "$index" "$option"
            index=$((index + 1))
        done
        printf '0) %s\n\nSeçim: ' "$zero_label"
        IFS= read -r choice || return 1

        case "$choice" in
            0)
                return 2
                ;;
            ''|*[!0-9]*)
                hamals_warn "Lütfen listeden bir numara girin."
                ;;
            *)
                if [ "$choice" -ge 1 ] 2>/dev/null && [ "$choice" -le "$count" ]; then
                    index=1
                    for option in "$@"; do
                        if [ "$index" -eq "$choice" ]; then
                            HAMALS_MENU_RESULT=$option
                            return 0
                        fi
                        index=$((index + 1))
                    done
                fi
                hamals_warn "Geçersiz seçim: $choice"
                ;;
        esac
    done
}

# Converts newline-delimited command output into positional menu arguments.
# Values used by this project (ROS package, executable, topic, node and frame
# names) cannot contain whitespace, so this is consistent in Bash and Zsh.
hamals_menu_from_lines() {
    local title zero_label lines
    title=$1
    zero_label=$2
    lines=$3

    if [ -z "$lines" ]; then
        hamals_warn "Gösterilecek seçenek yok."
        return 1
    fi

    # Unquoted command substitution splits on newlines in both Bash and Zsh.
    # ROS identifiers do not contain spaces or tabs.
    # shellcheck disable=SC2046
    set -- $(printf '%s\n' "$lines")
    hamals_menu "$title" "$zero_label" "$@"
}

# GNU timeout is not installed by default on macOS. The fallback keeps stdout
# and stderr attached while a watchdog terminates long-running ROS commands.
hamals_timeout() {
    local seconds command_pid timer_pid exit_status
    seconds=$1
    shift

    if [ -n "${ZSH_VERSION:-}" ]; then
        # Avoid Zsh trying to lower the priority of background watchdog jobs.
        setopt localoptions nobgnice 2>/dev/null
    fi

    if hamals_command_exists timeout; then
        timeout "$seconds" "$@"
        return $?
    fi
    if hamals_command_exists gtimeout; then
        gtimeout "$seconds" "$@"
        return $?
    fi
    if hamals_command_exists perl && \
        perl -MTime::HiRes=time,sleep -MPOSIX=:sys_wait_h,setpgid \
            -e 'exit 0' 2>/dev/null; then
        perl -MTime::HiRes=time,sleep -MPOSIX=:sys_wait_h,setpgid -e '
            $seconds = shift @ARGV;
            $pid = fork();
            defined $pid or exit 127;
            if ($pid == 0) {
                setpgid(0, 0);
                exec @ARGV;
                exit 127;
            }
            setpgid($pid, $pid);
            $deadline = time() + $seconds;
            while (1) {
                $waited = waitpid($pid, WNOHANG);
                if ($waited == $pid) {
                    if ($? & 127) { exit 128 + ($? & 127); }
                    exit $? >> 8;
                }
                if (time() >= $deadline) {
                    kill "TERM", -$pid;
                    sleep 0.05;
                    kill "KILL", -$pid;
                    waitpid($pid, 0);
                    exit 124;
                }
                sleep 0.02;
            }
        ' "$seconds" "$@"
        return $?
    fi

    "$@" &
    command_pid=$!
    (
        timer_sleep_pid=
        trap 'kill "$timer_sleep_pid" 2>/dev/null; exit 0' TERM INT
        sleep "$seconds" &
        timer_sleep_pid=$!
        wait "$timer_sleep_pid"
        kill -TERM "$command_pid" 2>/dev/null
    ) &
    timer_pid=$!
    wait "$command_pid"
    exit_status=$?
    kill "$timer_pid" 2>/dev/null
    wait "$timer_pid" 2>/dev/null
    return "$exit_status"
}

hamals_count_lines() {
    if [ -z "$1" ]; then
        printf '0\n'
    else
        printf '%s\n' "$1" | awk 'NF { count++ } END { print count + 0 }'
    fi
}

hamals_is_macos() {
    [ "$(uname -s 2>/dev/null)" = "Darwin" ]
}

hamals_is_linux() {
    [ "$(uname -s 2>/dev/null)" = "Linux" ]
}
