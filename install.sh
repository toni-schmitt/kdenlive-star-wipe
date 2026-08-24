#!/usr/bin/env bash
# Copy the star wipe lumas into Kdenlive's user luma folders.
# Kdenlive picks the folder that matches the project profile (HD / PAL) and
# lists every .pgm it finds there in the Wipe transition's dropdown.
set -euo pipefail
cd "$(dirname "$0")"

DEST="${XDG_DATA_HOME:-$HOME/.local/share}/kdenlive/lumas"

for profile in HD PAL; do
  [ -d "lumas/$profile" ] || continue
  mkdir -p "$DEST/$profile"
  cp -v lumas/"$profile"/*.pgm "$DEST/$profile/"
done

echo
echo "Installed to $DEST"
echo "Restart Kdenlive, then: add a Wipe transition -> Luma/Wipe file -> star_wipe.pgm"
