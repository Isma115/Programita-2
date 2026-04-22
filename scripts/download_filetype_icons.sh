#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$ROOT_DIR/assets/icons/filetypes"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TARGET_DIR"

download_and_convert() {
    local key="$1"
    shift
    local svg_path="$TMP_DIR/$key.svg"
    local png_path="$TARGET_DIR/$key.png"

    for url in "$@"; do
        if curl -fsSL "$url" -o "$svg_path"; then
            if rsvg-convert -w 20 -h 20 "$svg_path" -o "$png_path"; then
                echo "ok $key"
                return 0
            fi
        fi
    done

    echo "missing $key" >&2
    return 1
}

ensure_fallback() {
    local key="$1"
    local source_key="$2"
    local png_path="$TARGET_DIR/$key.png"
    local source_path="$TARGET_DIR/$source_key.png"

    if [[ -f "$png_path" ]]; then
        return 0
    fi

    if [[ -f "$source_path" ]]; then
        cp "$source_path" "$png_path"
        echo "fallback $key <- $source_key"
        return 0
    fi

    echo "missing $key (no fallback)" >&2
    return 1
}

status=0

download_and_convert javascript \
    "https://cdn.simpleicons.org/javascript/F7DF1E" || status=1
download_and_convert react \
    "https://cdn.simpleicons.org/react/61DAFB" || status=1
download_and_convert typescript \
    "https://cdn.simpleicons.org/typescript/3178C6" || status=1
download_and_convert python \
    "https://cdn.simpleicons.org/python/3776AB" || status=1
download_and_convert java \
    "https://cdn.simpleicons.org/openjdk/ED8B00" \
    "https://cdn.simpleicons.org/java/ED8B00" || status=1
download_and_convert kotlin \
    "https://cdn.simpleicons.org/kotlin/7F52FF" || status=1
download_and_convert groovy \
    "https://cdn.simpleicons.org/apachegroovy/4298B8" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_groovy.svg" || status=1
download_and_convert gradle \
    "https://cdn.simpleicons.org/gradle/02303A" || status=1
download_and_convert scala \
    "https://cdn.simpleicons.org/scala/DC322F" || status=1
download_and_convert c \
    "https://cdn.simpleicons.org/c/A8B9CC" || status=1
download_and_convert cpp \
    "https://cdn.simpleicons.org/cplusplus/00599C" || status=1
download_and_convert csharp \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_csharp.svg" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_cs.svg" || status=1
download_and_convert dotnet \
    "https://cdn.simpleicons.org/dotnet/512BD4" || status=1
download_and_convert fsharp \
    "https://cdn.simpleicons.org/fsharp/378BBA" || status=1
download_and_convert go \
    "https://cdn.simpleicons.org/go/00ADD8" || status=1
download_and_convert rust \
    "https://cdn.simpleicons.org/rust/DEA584" || status=1
download_and_convert zig \
    "https://cdn.simpleicons.org/zig/F7A41D" || status=1
download_and_convert swift \
    "https://cdn.simpleicons.org/swift/F05138" || status=1
download_and_convert objectivec \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_objectivec.svg" || status=1
download_and_convert php \
    "https://cdn.simpleicons.org/php/777BB4" || status=1
download_and_convert ruby \
    "https://cdn.simpleicons.org/ruby/CC342D" || status=1
download_and_convert perl \
    "https://cdn.simpleicons.org/perl/39457E" || status=1
download_and_convert lua \
    "https://cdn.simpleicons.org/lua/2C2D72" || status=1
download_and_convert r \
    "https://cdn.simpleicons.org/r/276DC3" || status=1
download_and_convert julia \
    "https://cdn.simpleicons.org/julia/9558B2" || status=1
download_and_convert dart \
    "https://cdn.simpleicons.org/dart/0175C2" || status=1
download_and_convert elixir \
    "https://cdn.simpleicons.org/elixir/4B275F" || status=1
download_and_convert erlang \
    "https://cdn.simpleicons.org/erlang/A90533" || status=1
download_and_convert html \
    "https://cdn.simpleicons.org/html5/E34F26" || status=1
download_and_convert css \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_css.svg" \
    "https://cdn.simpleicons.org/css/1572B6" || status=1
download_and_convert sass \
    "https://cdn.simpleicons.org/sass/CC6699" || status=1
download_and_convert less \
    "https://cdn.simpleicons.org/less/1D365D" || status=1
download_and_convert vue \
    "https://cdn.simpleicons.org/vuedotjs/4FC08D" || status=1
download_and_convert svelte \
    "https://cdn.simpleicons.org/svelte/FF3E00" || status=1
download_and_convert astro \
    "https://cdn.simpleicons.org/astro/BC52EE" || status=1
download_and_convert template \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_template.svg" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_ejs.svg" || status=1
download_and_convert handlebars \
    "https://cdn.simpleicons.org/handlebarsdotjs/000000" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_hbs.svg" || status=1
download_and_convert sql \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_sql.svg" || status=1
download_and_convert graphql \
    "https://cdn.simpleicons.org/graphql/E10098" || status=1
download_and_convert protobuf \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_protobuf.svg" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_proto.svg" || status=1
download_and_convert json \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_json.svg" || status=1
download_and_convert xml \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_xml.svg" || status=1
download_and_convert yaml \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_yaml.svg" || status=1
download_and_convert toml \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_toml.svg" || status=1
download_and_convert config \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_settings.svg" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_config.svg" || status=1
download_and_convert shell \
    "https://cdn.simpleicons.org/gnubash/4EAA25" || status=1
download_and_convert batch \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_bat.svg" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_cmd.svg" \
    "https://cdn.simpleicons.org/windows/0078D6" || status=1
download_and_convert powershell \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_powershell.svg" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_ps1.svg" \
    "https://cdn.simpleicons.org/powershell/5391FE" || status=1
download_and_convert docker \
    "https://cdn.simpleicons.org/docker/2496ED" || status=1
download_and_convert editorconfig \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_editorconfig.svg" || status=1
download_and_convert markdown \
    "https://cdn.simpleicons.org/markdown/000000" || status=1
download_and_convert makefile \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_makefile.svg" \
    "https://raw.githubusercontent.com/vscode-icons/vscode-icons/master/icons/file_type_make.svg" || status=1
download_and_convert cmake \
    "https://cdn.simpleicons.org/cmake/064F8C" || status=1
download_and_convert jenkins \
    "https://cdn.simpleicons.org/jenkins/D24939" || status=1
download_and_convert homebrew \
    "https://cdn.simpleicons.org/homebrew/FBB040" || status=1
download_and_convert vagrant \
    "https://cdn.simpleicons.org/vagrant/1868F2" || status=1

status=0
ensure_fallback groovy gradle || status=1
ensure_fallback csharp dotnet || status=1
ensure_fallback css sass || status=1
ensure_fallback protobuf graphql || status=1
ensure_fallback batch shell || status=1
ensure_fallback powershell shell || status=1
ensure_fallback makefile cmake || status=1

exit "$status"
