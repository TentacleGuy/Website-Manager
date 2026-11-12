#!/bin/bash
set -euo pipefail

[[ "$(/usr/bin/uname -s)" == Darwin ]] || exit 1
action=${1:-start}
case "$action" in start|restart|stop) ;; *) exit 1 ;; esac
helper_dir=$(cd "$(dirname "$0")/.." && pwd -P)
root=$(cd "$helper_dir/../../.." && pwd -P)
builder="$helper_dir/helpers/build-helfer.sh"
bundle="$root/Helfer.app"
status="$root/data/safari-alarm.json"
lock="$root/data/safari-alarm.lock"
log="$root/data/safari-alarm.log"
resources="$bundle/Contents/Resources"
[[ -d "$root/data" ]] || exit 1

# Serialize control requests separately from the lock held by the running helper.
umask 077
exec 9>>"$root/data/safari-alarm-control.lock"
/usr/bin/lockf -s -t 20 9

alarm_pid() {
    local pid
    pid=$(/usr/bin/plutil -extract pid raw -expect integer "$status" 2>/dev/null) || return 1
    [[ "$pid" =~ ^[1-9][0-9]{0,8}$ ]] || return 1
    printf '%s\n' "$pid"
}

owns_helper_process() {
    local process owner command
    process=$(/bin/ps -ww -p "$1" -o uid= -o command=) || return 1
    read -r owner command <<< "$process"
    [[ "$owner" == "$(/usr/bin/id -u)" &&
       "$command" == "/usr/bin/osascript -l JavaScript $resources/safari-alarm.js $status $resources/safari-alarm.wav" ]]
}

alarm_ready() {
    local pid timestamp now lock_status=0
    pid=$(alarm_pid) || return 1
    timestamp=$(/usr/bin/plutil -extract time raw -expect integer "$status" 2>/dev/null) || return 1
    [[ "$timestamp" =~ ^[1-9][0-9]{0,11}$ ]] || return 1
    now=$(/bin/date +%s)
    (( timestamp <= now && now - timestamp <= 12 )) && owns_helper_process "$pid" || return 1
    /usr/bin/lockf -kns -t 0 "$lock" /usr/bin/true || lock_status=$?
    [[ "$lock_status" == 75 ]]
}

stop_alarm() {
    local pid lock_status=0
    /usr/bin/lockf -ks -t 0 "$lock" /bin/rm -f -- "$status" || lock_status=$?
    if [[ "$lock_status" == 0 ]]; then return 0; fi
    if [[ "$lock_status" != 75 ]] || ! pid=$(alarm_pid) || ! owns_helper_process "$pid"; then
        printf '%s\n' 'Der laufende Helfer konnte nicht eindeutig ermittelt werden.' >&2
        return 1
    fi

    kill -TERM "$pid" 2>/dev/null || true
    /usr/bin/lockf -ks -t 8 "$lock" /bin/rm -f -- "$status"
}

start_alarm() {
    local attempt
    [[ -f "$builder" ]] || return 1
    if alarm_ready; then
        return 0
    fi

    # Hold the lifetime lock until the observer exits. Close the control lock in the child.
    /usr/bin/nohup /usr/bin/lockf -ks -t 0 "$lock" \
        /bin/bash -c '
            exec > "$4" 2>&1
            /bin/bash "$1" "$2" && exec /bin/bash "$2/Contents/MacOS/Helfer" "$3"
        ' Helfer "$builder" "$bundle" "$status" "$log" </dev/null >/dev/null 2>&1 9>&- &

    for ((attempt=0; attempt<40; attempt++)); do
        if alarm_ready; then
            return 0
        fi
        /bin/sleep 0.2
    done

    printf '%s\n' 'Safari-Alarm konnte nicht gestartet werden.' >&2
    return 1
}

case "$action" in
  start) start_alarm ;;
  restart) stop_alarm && start_alarm ;;
  stop) stop_alarm ;;
esac
