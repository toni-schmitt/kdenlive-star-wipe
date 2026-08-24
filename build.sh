#!/usr/bin/env bash
# Regenerate the whole star-wipe luma set plus its GIF previews.
set -euo pipefail
cd "$(dirname "$0")"

GEN="python3 generate_star_wipe.py"
HD=lumas/HD
PAL=lumas/PAL
mkdir -p "$HD" "$PAL" preview

# name              points  extra options
variants=(
  "star_wipe|5|"
  "star_wipe_spin|5|--spin 120"
  "star_wipe_corner|5|--center 0.14,0.82"
  "star_wipe_4point|4|"
  "star_wipe_6point|6|"
  "star_wipe_8point|8|-i 0.48"
)

for v in "${variants[@]}"; do
  IFS='|' read -r name points extra <<<"$v"
  # shellcheck disable=SC2086
  $GEN -o "$HD/$name.pgm"  -s 1920x1080 -p "$points" $extra
  # shellcheck disable=SC2086
  $GEN -o "$PAL/$name.pgm" -s 720x576 --par 1.0667 -p "$points" $extra
done

for name in star_wipe star_wipe_spin star_wipe_corner star_wipe_6point; do
  python3 make_preview.py "$HD/$name.pgm" "preview/$name.gif"
done

echo
echo "Done. Install with ./install.sh"
