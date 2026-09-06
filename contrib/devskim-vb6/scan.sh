#!/usr/bin/env sh
# Scan a classic Visual Basic 6 source tree with DevSkim and the ts-scan VB6 rule pack.
#
#   contrib/devskim-vb6/scan.sh <source dir> [output.sarif]
#
# Requires the DevSkim CLI: dotnet tool install --global Microsoft.CST.DevSkim.CLI
set -eu

if [ "$#" -lt 1 ]; then
    echo "usage: $0 <source dir> [output.sarif]" >&2
    exit 2
fi

src=$1
out=${2:-vb6-findings.sarif}
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if command -v devskim >/dev/null 2>&1; then
    devskim_cmd=devskim
else
    devskim_cmd="dotnet devskim"
fi

exec $devskim_cmd analyze \
    -I "$src" \
    -O "$out" \
    -f sarif \
    -r "$here/rules" \
    --languages "$here/languages.json" \
    --comments "$here/comments.json" \
    --base-path "$src"
