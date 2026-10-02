#!/bin/zsh
set -e
album_project="$(cd "$(dirname "$0")" && pwd)"
album_python="$(command -v python3)"
if ! "$album_python" -c 'import PIL' >/dev/null 2>&1; then
  album_python="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
fi
"$album_python" "$album_project/publish.py"
print '\n发布已提交。可以在 GitHub Actions 页面查看部署结果。'
read -r '?按回车关闭窗口…'
