#!/bin/sh
set -eu

collect_markdown() {
  if [ "$#" -eq 0 ]; then
    set -- .
  fi

  for target in "$@"; do
    if [ -d "$target" ]; then
      find "$target" -type f \( -name '*.md' -o -name '*.MD' \) -print
    elif [ -f "$target" ]; then
      printf '%s\n' "$target"
    fi
  done
}

file_list=$(collect_markdown "$@" | sort -u || true)

if [ -z "$file_list" ]; then
  echo "No markdown files found." >&2
  exit 0
fi

errored=0
checked=0

while IFS= read -r file; do
  [ -n "$file" ] || continue
  if [ ! -f "$file" ]; then
    echo "Skipping missing path: $file" >&2
    continue
  fi
  checked=$((checked + 1))

  heading_issues=$(grep -nE '^#+[^ #]' "$file" || true)
  if [ -n "$heading_issues" ]; then
    echo "[markdown] Headings missing space in $file:" >&2
    echo "$heading_issues" >&2
    errored=1
  fi

  empty_links=$(grep -nE '\[[^]]+\]\([[:space:]]*\)' "$file" || true)
  if [ -n "$empty_links" ]; then
    echo "[markdown] Empty link targets in $file:" >&2
    echo "$empty_links" >&2
    errored=1
  fi

  placeholder_anchors=$(grep -nE '\[[^]]+\]\(#\)' "$file" || true)
  if [ -n "$placeholder_anchors" ]; then
    echo "[markdown] Placeholder anchors in $file:" >&2
    echo "$placeholder_anchors" >&2
    errored=1
  fi

done <<EOF
$file_list
EOF

echo "Checked $checked markdown file(s)."

if [ "$errored" -ne 0 ]; then
  echo "Markdown sanity checks failed." >&2
  exit 1
fi
