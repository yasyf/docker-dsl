#!/usr/bin/env bash
# Invoked by stubgen.py via: bash -lic 'source _completions.sh <output.json>'
# Must run via -c so bash stays fully interactive for completion loading.

OUTPUT="${1:?usage: source _completions.sh <output.json>}"

# Collect all command names
mapfile -t ALL_CMDS < <(compgen -c | sort -u)

# Trigger lazy loading for common dev tools that might not be registered yet
PRIORITY_CMDS=(git make cmake curl tar docker uv pip npm cargo gcc g++ clang
    python python3 ruby node rustc go java javac scp ssh rsync sed awk
    find xargs sort uniq wc head tail cat less grep diff patch chmod chown
    cp mv rm mkdir rmdir ln touch kill ps mount umount df du free top htop
    systemctl journalctl apt dpkg yum dnf pacman brew port)

for cmd in "${PRIORITY_CMDS[@]}"; do
    _completion_loader "$cmd" 2>/dev/null || true
done

# Collect all function-based completion specs
declare -A COMP_FUNCS
while IFS= read -r line; do
    fn=$(echo "$line" | sed -n 's/.*-F \([^ ]*\).*/\1/p')
    cmd=$(echo "$line" | awk '{print $NF}')
    [ -n "$fn" ] && [ -n "$cmd" ] && COMP_FUNCS["$cmd"]="$fn"
done < <(complete -p 2>/dev/null)

extract_completions() {
    local cmd="$1" fn="$2"

    COMPREPLY=()
    COMP_WORDS=("$cmd" "")
    COMP_CWORD=1
    COMP_LINE="$cmd "
    COMP_POINT=$((${#cmd} + 1))
    "$fn" >/dev/null 2>&1 || true

    local subs=()
    local is_filesystem=true
    for s in "${COMPREPLY[@]}"; do
        s="${s%% }"
        [ -z "$s" ] && continue
        [[ "$s" == */* ]] && continue
        [[ "$s" == *.* ]] && continue
        [ ! -e "$s" ] && is_filesystem=false
        subs+=("$s")
    done
    $is_filesystem && [ ${#subs[@]} -gt 0 ] && subs=()

    COMPREPLY=()
    COMP_WORDS=("$cmd" "--")
    COMP_CWORD=1
    COMP_LINE="$cmd --"
    COMP_POINT=$((${#cmd} + 3))
    "$fn" >/dev/null 2>&1 || true

    local flags=()
    for f in "${COMPREPLY[@]}"; do
        f="${f%% }"
        f="${f%%=}"
        [[ "$f" == --* ]] || continue
        flags+=("$f")
    done

    # Discard if too many subcommands (dictionary/manpage completion noise)
    [ ${#subs[@]} -gt 500 ] && subs=()
    [ ${#subs[@]} -eq 0 ] && [ ${#flags[@]} -eq 0 ] && return

    local subs_json flags_json
    subs_json=$(printf '%s\n' "${subs[@]}" | sort -u | jq -Rsc 'split("\n") | map(select(. != ""))')
    flags_json=$(printf '%s\n' "${flags[@]}" | sort -u | jq -Rsc 'split("\n") | map(select(. != ""))')

    printf '"%s": {"subcommands": %s, "flags": %s}' "$cmd" "$subs_json" "$flags_json"
}

{
    first=true
    printf '{"commands": ['
    for cmd in "${ALL_CMDS[@]}"; do
        $first || printf ','
        printf '"%s"' "$cmd"
        first=false
    done
    printf '], "completions": {'

    first=true
    for cmd in "${!COMP_FUNCS[@]}"; do
        result=$(extract_completions "$cmd" "${COMP_FUNCS[$cmd]}" 2>/dev/null </dev/null) || true
        [ -z "$result" ] && continue
        $first || printf ','
        printf '%s' "$result"
        first=false
    done

    printf '}}\n'
} > "$OUTPUT"
