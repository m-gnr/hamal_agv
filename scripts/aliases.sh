#!/usr/bin/env bash
set -u

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd -P)
REPO_DIR=$(cd "$SCRIPT_DIR/.." 2>/dev/null && pwd -P)
HAMALS_FILE="$REPO_DIR/scripts/shell/hamals.sh"
SHELL_NAME=$(basename "${SHELL:-bash}")

case "$SHELL_NAME" in
    zsh)
        RC_FILE="$HOME/.zshrc"
        RELOAD_COMMAND='source ~/.zshrc'
        ;;
    bash)
        RC_FILE="$HOME/.bashrc"
        RELOAD_COMMAND='source ~/.bashrc'
        ;;
    *)
        printf 'Hata: Desteklenmeyen shell: %s (Bash veya Zsh kullanın)\n' "$SHELL_NAME" >&2
        exit 1
        ;;
esac

if [ ! -f "$HAMALS_FILE" ]; then
    printf 'Hata: HAMALS CLI dosyası bulunamadı: %s\n' "$HAMALS_FILE" >&2
    exit 1
fi

# A standalone executable named h would take precedence in some invocation
# patterns and is almost certainly unrelated to this repository.
EXISTING_H=$(command -v h 2>/dev/null || true)
if [ -n "$EXISTING_H" ]; then
    printf "Hata: PATH üzerinde mevcut bir 'h' komutu var: %s\n" "$EXISTING_H" >&2
    printf 'Kullanıcı yapılandırması değiştirilmedi. Çakışmayı giderip yeniden deneyin.\n' >&2
    exit 1
fi

if [ -f "$RC_FILE" ] && grep -Eq \
    '^[[:space:]]*(alias[[:space:]]+h=|function[[:space:]]+h([[:space:]]|\()|h[[:space:]]*\(\)[[:space:]]*\{)' \
    "$RC_FILE"; then
    printf "Hata: %s içinde mevcut bir 'h' aliası veya function'ı var.\n" "$RC_FILE" >&2
    printf 'Kullanıcı yapılandırması değiştirilmedi. Çakışmayı giderip yeniden deneyin.\n' >&2
    exit 1
fi

if [ ! -e "$RC_FILE" ]; then
    : > "$RC_FILE" || exit 1
fi
if [ ! -f "$RC_FILE" ]; then
    printf 'Hata: Shell yapılandırma yolu normal bir dosya değil: %s\n' "$RC_FILE" >&2
    exit 1
fi

# Single quotes make spaces, $, backticks and backslashes in the repository
# path safe. POSIX single quotes inside a path are represented as '\''.
QUOTED_HAMALS_FILE=$(printf '%s' "$HAMALS_FILE" | sed "s/'/'\\\\''/g")
SOURCE_LINE="source '$QUOTED_HAMALS_FILE'"
TEMP_FILE=$(mktemp "${RC_FILE}.hamals.XXXXXX") || exit 1
BACKUP_FILE="${RC_FILE}.hamals-backup"

cp "$RC_FILE" "$BACKUP_FILE" || {
    rm -f "$TEMP_FILE"
    printf 'Hata: Shell yapılandırması yedeklenemedi.\n' >&2
    exit 1
}

# Remove only the exact legacy aliases produced by older versions of this
# repository, plus a previous copy of this installer's source line.
awk -v source_line="$SOURCE_LINE" -v hamals_file="$HAMALS_FILE" '
    $0 == source_line { next }
    /^[[:space:]]*source[[:space:]]+/ && index($0, hamals_file) { next }
    /^alias cbuild=/ && /\/ros2_ws && colcon build --cmake-args -DPython_EXECUTABLE=/ { next }
    /^alias cclean=/ && /\/ros2_ws\/build .*\/ros2_ws\/install .*\/ros2_ws\/log/ { next }
    /^alias cdev=/ && /\/docker\/compose.yml up/ { next }
    /^alias crobot=/ && /\/docker\/compose.pi.yml up/ { next }
    { print }
' "$RC_FILE" > "$TEMP_FILE" || {
    rm -f "$TEMP_FILE"
    printf 'Hata: Shell yapılandırması hazırlanamadı.\n' >&2
    exit 1
}

if [ -s "$TEMP_FILE" ] && [ "$(tail -c 1 "$TEMP_FILE" 2>/dev/null | wc -l | tr -d ' ')" = "0" ]; then
    printf '\n' >> "$TEMP_FILE"
fi
printf '%s\n' "$SOURCE_LINE" >> "$TEMP_FILE"

if ! cp "$TEMP_FILE" "$RC_FILE"; then
    cp "$BACKUP_FILE" "$RC_FILE" 2>/dev/null || true
    rm -f "$TEMP_FILE"
    printf 'Hata: Shell yapılandırması güncellenemedi; yedek geri yüklendi.\n' >&2
    exit 1
fi
rm -f "$TEMP_FILE"

printf '✓ HAMALS CLI kuruldu: %s\n' "$RC_FILE"
printf '✓ Yapılandırma yedeği: %s\n\n' "$BACKUP_FILE"
printf 'Mevcut terminalde kullanmak için:\n  %s\n' "$RELOAD_COMMAND"
