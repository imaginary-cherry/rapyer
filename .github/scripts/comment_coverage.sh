#!/usr/bin/env bash
# Post (or update) a sticky PR comment with the total coverage percentage.
#
# Required environment variables:
#   GH_TOKEN     - token with pull-requests:write (e.g. secrets.GITHUB_TOKEN)
#   REPO         - owner/repo (e.g. github.repository)
#   PR_NUMBER    - pull request number (e.g. github.event.pull_request.number)
#   COVERAGE_TXT - path to the captured `coverage ... term` output
set -euo pipefail

MARKER="<!-- coverage-comment -->"

pct=$(grep '^TOTAL' "$COVERAGE_TXT" | awk '{print $NF}')
table=$(sed -n '/^Name\s/,/^TOTAL/p' "$COVERAGE_TXT" || tail -n 40 "$COVERAGE_TXT")

body=$(cat <<EOF
${MARKER}
## Coverage report

**Total coverage: ${pct:-unknown}**

<details><summary>Full report</summary>

\`\`\`
${table}
\`\`\`
</details>
EOF
)

# Reuse the existing coverage comment if one exists, otherwise create it (sticky).
id=$(gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" \
      --jq ".[] | select(.body | contains(\"${MARKER}\")) | .id" | head -n1)

if [ -n "$id" ]; then
  gh api -X PATCH "repos/${REPO}/issues/comments/${id}" -f body="$body" >/dev/null
else
  gh api -X POST "repos/${REPO}/issues/${PR_NUMBER}/comments" -f body="$body" >/dev/null
fi
