#!/usr/bin/env bash
#
# push_to_github.sh — Sube NuvaConnect a tu GitHub y dispara la compilación
# automática de los instaladores (.exe / .dmg) vía GitHub Actions.
#
# Uso:
#   1) Crea un repo vacío en https://github.com/new  (ej. nuvaconnect)
#   2) Ejecuta:
#        bash push_to_github.sh https://github.com/TU_USUARIO/nuvaconnect.git
#   3) (Opcional) Publica una versión para obtener un Release descargable:
#        git tag v0.1.0 && git push origin v0.1.0
#
set -euo pipefail

REMOTE="${1:-}"
if [[ -z "$REMOTE" ]]; then
  echo "Uso: bash push_to_github.sh <URL_DEL_REPO.git>" >&2
  exit 1
fi

if [[ ! -d .git ]]; then
  git init -q
fi

git add .
git commit -qm "NuvaConnect: herramienta de acceso remoto (servidor + cliente + seguridad + instaladores)" || echo "(nada nuevo que commitear)"
git branch -M main

if git remote | grep -q origin; then
  git remote set-url origin "$REMOTE"
else
  git remote add origin "$REMOTE"
fi

git push -u origin main

echo ""
echo "✔ Subido a $REMOTE"
echo "  Ve a la pestaña 'Actions' del repo para ver la compilación."
echo "  Para generar instaladores + Release descargable:"
echo "    git tag v0.1.0 && git push origin v0.1.0"
