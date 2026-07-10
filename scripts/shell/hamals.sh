# HAMALS CLI entry point. This file must be sourced so `h csource` and the
# automatic source after `h cbuild` can modify the current shell environment.

if [ -n "${ZSH_VERSION:-}" ]; then
    # shellcheck disable=SC2296
    HAMALS_CLI_FILE=${(%):-%N}
elif [ -n "${BASH_VERSION:-}" ]; then
    HAMALS_CLI_FILE=${BASH_SOURCE[0]}
else
    printf 'HAMALS CLI yalnızca Bash ve Zsh ile desteklenir.\n' >&2
    return 1 2>/dev/null || exit 1
fi

HAMALS_CLI_DIR=$(cd "$(dirname "$HAMALS_CLI_FILE")" 2>/dev/null && pwd -P)
HAMALS_REPO_ROOT=$(cd "$HAMALS_CLI_DIR/../.." 2>/dev/null && pwd -P)
export HAMALS_REPO_ROOT

if [ -z "$HAMALS_CLI_DIR" ] || [ ! -d "$HAMALS_REPO_ROOT/ros2_ws/src" ]; then
    printf 'HAMALS repo kökü bulunamadı; CLI yüklenemedi.\n' >&2
    return 1 2>/dev/null || exit 1
fi

# shellcheck source=helpers.sh
. "$HAMALS_CLI_DIR/helpers.sh"
# shellcheck source=workspace.sh
. "$HAMALS_CLI_DIR/workspace.sh"
# shellcheck source=ros_tools.sh
. "$HAMALS_CLI_DIR/ros_tools.sh"
# shellcheck source=diagnostics.sh
. "$HAMALS_CLI_DIR/diagnostics.sh"
# shellcheck source=docker_tools.sh
. "$HAMALS_CLI_DIR/docker_tools.sh"

hamals_help_general() {
    cat <<'EOF'
HAMALS CLI

Colcon
  h csource
  h cbuild [paket...]
  h cclean
  h ctest [paket...]

ROS 2
  h crun [--debug] [paket [executable [argümanlar...]]]
  h claunch [--debug] [paket [launch_dosyası [argümanlar...]]]
  h ctopic [list|echo|info|hz|type]
  h cnode [list|info]
  h ctf [echo|frames|tree|check]

Diagnostics
  h cdoctor
  h cstatus [--full]

Docker
  h cdev
  h crobot
  h clogs [development|robot]
  h cps
  h cstop

Yardım
  h help <komut>
  h <komut> --help
EOF
}

hamals_help_command() {
    case "$1" in
        csource)
            cat <<'EOF'
Kullanım: h csource

ROS 2 temel ortamını ve derlenmiş HAMALS workspace'ini mevcut terminalde
source eder. Bash için setup.bash, Zsh için setup.zsh tercih edilir.

Örnek:
  h csource
EOF
            ;;
        cbuild)
            cat <<'EOF'
Kullanım: h cbuild [paket...]

Workspace'i --symlink-install ile derler. Paket verilirse --packages-select
kullanır. Başarılı build sonrası workspace mevcut terminalde source edilir.

Örnekler:
  h cbuild
  h cbuild <paket>
  h cbuild <paket_1> <paket_2>
EOF
            ;;
        cclean)
            cat <<'EOF'
Kullanım: h cclean

Güvenlik kontrollerinden sonra yalnızca ros2_ws/build, ros2_ws/install ve
ros2_ws/log klasörlerini temizler.
EOF
            ;;
        ctest)
            cat <<'EOF'
Kullanım: h ctest [paket...]

Tüm workspace testlerini veya seçilen paketlerin testlerini çalıştırır;
ardından colcon test-result --verbose sonucunu gösterir.

Örnekler:
  h ctest
  h ctest <paket_1> <paket_2>
EOF
            ;;
        crun)
            cat <<'EOF'
Kullanım:
  h crun [--debug]
  h crun [--debug] <paket>
  h crun [--debug] <paket> <executable> [argümanlar...]

Parametresiz kullanım executable içeren workspace paketlerini menüde gösterir.
Paket verilirse o paketin executable menüsünü açar. Tam adlar verilirse
ek argümanları değiştirmeden ros2 run komutuna aktarır.
--debug her paketin colcon kaynak yolu, install prefix'i ve executable sayısını
gösterir. Keşif her çağrıda ros2_ws içindeki colcon list sonucunu kullanır.

Örnek:
  h crun <paket> <executable> --ros-args -p port:=/dev/ttyACM0
EOF
            ;;
        claunch)
            cat <<'EOF'
Kullanım:
  h claunch [--debug]
  h claunch [--debug] <paket>
  h claunch [--debug] <paket> <launch_dosyası> [argümanlar...]

Launch dosyası bulunan paketleri ve desteklenen .launch.py/.xml/.yaml/.yml
dosyalarını menüyle seçtirir veya doğrudan ros2 launch çalıştırır.
Kurulu share dizini ile colcon list'in verdiği gerçek source yolunu dinamik tarar.
--debug kontrol edilen dizinleri ve bulunan launch dosyası sayısını gösterir.

Örnek:
  h claunch <paket> <launch_dosyası> use_sim_time:=false
EOF
            ;;
        ctopic)
            cat <<'EOF'
Kullanım:
  h ctopic
  h ctopic list
  h ctopic echo|info|hz|type <topic>

Parametresiz kullanım topic işlemleri ve mevcut topic'ler için menü açar.

Örnekler:
  h ctopic echo /odom_raw
  h ctopic info /scan
  h ctopic hz /imu/data
EOF
            ;;
        cnode)
            cat <<'EOF'
Kullanım:
  h cnode
  h cnode list
  h cnode info <node>

Node listesini gösterir veya menüden/doğrudan seçilen node'un detaylarını
ros2 node info ile yazdırır.
EOF
            ;;
        ctf)
            cat <<'EOF'
Kullanım:
  h ctf
  h ctf echo <source> <target>
  h ctf frames
  h ctf tree
  h ctf check

TF transformunu izler, /tf ve /tf_static verisinden frame'leri listeler,
tf2_tools ile output/tf altında ağaç oluşturur veya temel HAMALS frame
bağlantılarını timeout ile kontrol eder.
EOF
            ;;
        cdoctor)
            cat <<'EOF'
Kullanım: h cdoctor

ROS 2, colcon, workspace, Docker/Compose, serial izinleri ve temel ROS
paketlerini kontrol eder. Sistemi değiştirmez; sorunlar için kısa öneriler verir.
EOF
            ;;
        cstatus)
            cat <<'EOF'
Kullanım: h cstatus [--full]

Ortam, container, donanım, ROS graph, kritik topic ve TF durumunu gösterir.
--full, /odom_raw, /imu/data ve /scan frekanslarını da kısa timeoutlarla ölçer.
EOF
            ;;
        cdev)
            cat <<'EOF'
Kullanım: h cdev

Linux'ta hamal_dev servisini başlatır ve container içindeki Bash shell'e
bağlanır. macOS'ta Conda geliştirme ortamı kullanılmalıdır.
EOF
            ;;
        crobot)
            cat <<'EOF'
Kullanım: h crobot

Linux/Raspberry Pi ortamında compose.pi.yml içindeki hamal_robot servisini
arka planda başlatır.
EOF
            ;;
        clogs)
            cat <<'EOF'
Kullanım: h clogs [development|robot]

Seçilen hamal_dev veya hamal_robot servisinin Compose loglarını takip eder.
Ortam verilmezse numaralı menü açılır.
EOF
            ;;
        cps)
            cat <<'EOF'
Kullanım: h cps

Development ve robot Compose projelerindeki container durumlarını gösterir.
EOF
            ;;
        cstop)
            cat <<'EOF'
Kullanım: h cstop

Yalnızca hamal_dev ve hamal_robot servislerini durdurur. Container, volume
ve image silmez; docker compose down çalıştırmaz.
EOF
            ;;
        '')
            hamals_help_general
            ;;
        *)
            printf 'Bilinmeyen HAMALS komutu: %s\n\n' "$1" >&2
            printf 'Kullanılabilir komutları görmek için:\n  h\n' >&2
            return 2
            ;;
    esac
}

h() {
    local command_name
    command_name=${1:-}
    if [ -z "$command_name" ] || [ "$command_name" = "-h" ] || [ "$command_name" = "--help" ]; then
        hamals_help_general
        return 0
    fi
    shift

    if [ "$command_name" = help ]; then
        hamals_help_command "${1:-}"
        return $?
    fi
    if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
        hamals_help_command "$command_name"
        return $?
    fi

    case "$command_name" in
        csource) hamals_cmd_csource "$@" ;;
        cbuild) hamals_cmd_cbuild "$@" ;;
        cclean) hamals_cmd_cclean "$@" ;;
        ctest) hamals_cmd_ctest "$@" ;;
        crun) hamals_cmd_crun "$@" ;;
        claunch) hamals_cmd_claunch "$@" ;;
        ctopic) hamals_cmd_ctopic "$@" ;;
        cnode) hamals_cmd_cnode "$@" ;;
        ctf) hamals_cmd_ctf "$@" ;;
        cdoctor) hamals_cmd_cdoctor "$@" ;;
        cstatus) hamals_cmd_cstatus "$@" ;;
        cdev) hamals_cmd_cdev "$@" ;;
        crobot) hamals_cmd_crobot "$@" ;;
        clogs) hamals_cmd_clogs "$@" ;;
        cps) hamals_cmd_cps "$@" ;;
        cstop) hamals_cmd_cstop "$@" ;;
        *)
            printf 'Bilinmeyen HAMALS komutu: %s\n\n' "$command_name" >&2
            printf 'Kullanılabilir komutları görmek için:\n  h\n' >&2
            return 2
            ;;
    esac
}

unset HAMALS_CLI_FILE
