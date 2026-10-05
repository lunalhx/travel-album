#!/bin/zsh
set -e
album_project="$(cd "$(dirname "$0")" && pwd)"
album_python="$(command -v python3)"
if ! "$album_python" -c 'import PIL' >/dev/null 2>&1; then
  album_python="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
fi
if [[ ! -x "$album_python" ]]; then
  print '找不到带有 Pillow 的 Python，请查看 README.md 的本机使用说明。'
  exit 1
fi
exec "$album_python" "$album_project/manage_server.py" --port 8765
