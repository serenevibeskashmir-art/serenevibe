#!/usr/bin/env bash
# Builds the production CSS and JS served by index.html.
#   css/site.min.css  = styles + assistant + enhance + redesign + vista + polish (in that order)
#   (css/theme.css was never linked from index.html, so it is left out to keep the look unchanged)
#   js/*.min.js       = minified copies of the scripts
# Edit the source files, then run:  bash scripts/build_assets.sh
# Needs Node (uses esbuild through npx, nothing is added to the project).
set -euo pipefail
cd "$(dirname "$0")/.."
cat css/styles.css css/assistant.css css/enhance.css css/redesign.css css/vista.css css/polish.css > /tmp/site.css
npx --yes esbuild@0.25.0 /tmp/site.css --minify --loader:.css=css --outfile=css/site.min.css
for f in main redesign hotels assistant; do
  npx --yes esbuild@0.25.0 "js/$f.js" --minify --target=es2018 --outfile="js/$f.min.js"
done
ls -l css/site.min.css js/*.min.js
