---
name: pr-creator
description: Pull request creation skill. Use when asked to create a PR, pull request, merge request, or submit changes for review.
---

# Pull Request Creation

## Core Principles

- Analyze actual code changes to understand the PR's purpose
- Write clear, context-aware PR descriptions
- Never mention Claude or AI involvement in PR content

## Workflow

1. **Identify the current branch** - Run `git branch --show-current`
2. **Identify the base branch** - Default to `develop` unless specified otherwise
3. **Get the diff** - Run `git diff <base>...<current>` to see changes
4. **Get commit history** - Run `git log <base>..<current> --oneline` for context
5. **Analyze changes** - Understand what was added, modified, or removed
6. **Ask clarifying questions** if the purpose is unclear or context is needed
7. **Generate PR** - Create via `gh pr create` with appropriate title and body

## Default Settings

- **Base branch:** `develop`
- **Draft mode:** No (unless requested)

## PR Format
```markdown
## Summary

Brief description of what this PR accomplishes.

## Changes

- Specific change 1
- Specific change 2

## Testing

How the changes were tested or should be tested.
```

## Commands
```bash
# Create PR
gh pr create --base <base-branch> --title "<title>" --body "<body>"

# Create draft PR
gh pr create --base <base-branch> --title "<title>" --body "<body>" --draft
```

## Clarifying Questions to Consider

- What problem does this solve?
- Are there any breaking changes?
- Is there a related issue or ticket number?
- Should this be a draft PR?
- Any specific reviewers to assign?