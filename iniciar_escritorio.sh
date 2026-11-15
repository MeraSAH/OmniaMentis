#!/usr/bin/env bash
# UBICACIÓN: OmniaMentis/iniciar_escritorio.sh
# PROPÓSITO: Abrir OmniaMentis como aplicación de escritorio (Linux).  Uso: bash iniciar_escritorio.sh
cd "$(dirname "$0")" || exit 1
[ -f .venv/bin/activate ] && . .venv/bin/activate
exec python3 scripts/omnia_desktop.py "$@"
