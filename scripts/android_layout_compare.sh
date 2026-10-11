#!/usr/bin/env bash
set -uo pipefail

size="$1"
density="$2"
font_scale="$3"
before_status=0
after_status=0
python3 scripts/android_ui_smoke.py --apk work/apks/before.apk --output evidence/before \
  --baseline --size "$size" --density "$density" --font-scale "$font_scale" \
  > evidence/test-before.log 2>&1 || before_status=$?
python3 scripts/android_ui_smoke.py --apk work/apks/after.apk --output evidence/after \
  --size "$size" --density "$density" --font-scale "$font_scale" \
  > evidence/test-after.log 2>&1 || after_status=$?
{
  echo "# Layout comparison: $size, $density dpi, font $font_scale"
  echo
  echo "Before capture exit code: $before_status"
  echo "After tests exit code: $after_status"
  echo
  echo "Before captures original UI only; geometry assertions apply to the corrected APK."
  echo
  cat evidence/after/report.md
} > evidence/report.md
cat evidence/test-after.log
if (( before_status != 0 || after_status != 0 )); then
  exit 1
fi
