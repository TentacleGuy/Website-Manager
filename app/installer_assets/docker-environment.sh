#!/bin/bash
# Shared by macOS and Linux; compatible with Bash 3.2.
manager_environment() {
    local root=$1 os arch version major compose context endpoint system socket file key value temp
    os=$("$DOCKER" info --format '{{.OSType}}') || return 1
    [ "$os" = linux ] || { printf '%s\n' 'Docker muss Linux-Container verwenden.' >&2; return 1; }
    arch=$("$DOCKER" info --format '{{.Architecture}}') || return 1
    case "$arch" in arm64|aarch64|amd64|x86_64) ;; *) printf 'Nicht unterstuetzte Docker-Architektur: %s\n' "$arch" >&2; return 1 ;; esac
    version=$("$DOCKER" version --format '{{.Server.Version}}') || return 1
    major=${version%%.*}
    case "$major" in ''|*[!0-9]*) printf '%s\n' 'Docker-Version nicht erkannt.' >&2; return 1 ;; esac
    [ "$major" -ge 24 ] || { printf '%s\n' 'Docker Engine ab Version 24 wird benoetigt.' >&2; return 1; }
    compose=$("$DOCKER" compose version --short) || return 1
    if ! printf '%s' "$compose" | /usr/bin/awk -F. '{gsub(/^v/,"",$1);exit !(($1>2)||($1==2&&$2>=20))}'; then
        printf '%s\n' 'Docker Compose ab Version 2.20 wird benoetigt.' >&2; return 1
    fi
    context=$("$DOCKER" context show) || return 1
    endpoint=${DOCKER_HOST:-$("$DOCKER" context inspect "$context" --format '{{.Endpoints.docker.Host}}')}
    system=$("$DOCKER" info --format '{{.OperatingSystem}}') || return 1
    case "$endpoint" in
        unix://*) socket=${endpoint#unix://} ;;
        npipe:*) socket=/var/run/docker.sock ;;
        *) printf '%s\n' 'Der gewaehlte Docker-Kontext ist nicht lokal. Lokale Projektdateien benoetigen einen lokalen Linux-Docker-Dienst.' >&2; return 1 ;;
    esac
    case "$system" in *Docker\ Desktop*) socket=/var/run/docker.sock ;; esac
    if [ "$(uname -s)" = Darwin ]; then case "$socket" in /run/user/*) ;; *) socket=/var/run/docker.sock ;; esac;fi
    socket=${VMM_DOCKER_SOCKET:-$socket}
    case "$socket" in /*) ;; *) return 1 ;; esac
    case "$socket" in *','*|*$'\n'*|*$'\r'*) printf '%s\n' 'Nicht unterstuetzter Docker-Socket-Pfad.' >&2; return 1 ;; esac
    DOCKER_CLI_IMAGE="docker:$major-cli"
    DOCKER_SOCKET=$socket
    file="$root/.env"
    [ -f "$file" ] || : > "$file"
    for key in VMM_DOCKER_CLI_IMAGE VMM_DOCKER_SOCKET; do
        if [ "$key" = VMM_DOCKER_CLI_IMAGE ]; then value=$DOCKER_CLI_IMAGE; else value=$socket; fi
        temp="$file.environment-new"
        /usr/bin/awk -v key="$key" -v value="$value" 'BEGIN{found=0} index($0,key"=")==1{print key"="value;found=1;next} {print} END{if(!found)print key"="value}' "$file" > "$temp" || return 1
        /bin/chmod 600 "$temp"; /bin/mv "$temp" "$file"
    done
    /bin/mkdir -p "$root/data"
    local escaped_context escaped_socket host_platform
    escaped_context=$(printf '%s' "$context" | /usr/bin/sed 's/\\/\\\\/g;s/"/\\"/g')
    escaped_socket=$(printf '%s' "$socket" | /usr/bin/sed 's/\\/\\\\/g;s/"/\\"/g')
    host_platform=$(uname -s | tr '[:upper:]' '[:lower:]')
    printf '{"status":"ok","platform":"%s","context":"%s","socket":"%s","docker_version":"%s","architecture":"%s","compose":"%s","cli_image":"%s"}\n' "$host_platform" "$escaped_context" "$escaped_socket" "$version" "$arch" "$compose" "$DOCKER_CLI_IMAGE" > "$root/data/setup-report.json"
    printf 'Docker %s · %s · Compose %s · Kontext %s\n' "$version" "$arch" "$compose" "$context"
}
