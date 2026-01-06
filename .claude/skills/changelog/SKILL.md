---
name: changelog
description: Update CHANGELOG.md with new entries using emoji-prefixed sections and semantic versioning. Use when adding features, fixes, or changes to the changelog.
---

# Changelog Updates

## Format

### Version Header
```markdown
## [X.Y.Z]
```

### Section Headers (use only relevant ones)
- `### 🚀 Major Changes` - Breaking changes, major milestones
- `### ✨ Added` - New features
- `### 🐛 Fixed` - Bug fixes
- `### 🔄 Changed` - Modified behavior (prefix **BREAKING** if breaking)
- `### ⚠️ Deprecated` - Features being phased out
- `### 🛠️ Technical Improvements` - Internal improvements, refactoring

### Entry Format
```markdown
- **Feature Name**: Description of the change.
  - Optional sub-details
  - Example: `code_example()`
```

## Version Determination

1. Read `pyproject.toml` for current version
2. Read `CHANGELOG.md` for latest documented version
3. If changelog has newer version than pyproject.toml → add to that section
4. If changelog matches pyproject.toml → create new patch version (e.g., 0.0.4 → 0.0.5)

## Rules

- New versions go at top, below `# Changelog` header
- Bold the feature/fix name: `**Name**:`
- Preserve existing entries
- One blank line between sections, two between versions
- File is usually `CHANGELOG.md` or `CHANGELOG` in repo root
