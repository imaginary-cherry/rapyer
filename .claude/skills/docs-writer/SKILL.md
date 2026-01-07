---
name: docs-writer
description: Documentation writing skill for creating consistent, clean documentation across projects. Use when asked to write docs, documentation, README files, API references, or any technical documentation.
---

# Documentation Writing

## Core Principles

- Write clear, concise documentation
- Use consistent formatting across all docs

## Default Conventions

### What to Omit (Unless Explicitly Requested)

- **"When to use this feature"** sections - Do not include unless the user explicitly asks for it
- **Return types in API references** - Omit from function/method signatures unless explicitly requested


### API Reference Format

```markdown
## `function_name(param1, param2)`

Description of what the function does.

**Parameters:**
- `param1` (type): Description
- `param2` (type): Description

**Example:**
```python
result = function_name("value", 42)
```
```

### Writing Style

- Use imperative mood ("Run the command" not "You should run the command")
- Keep sentences short and direct
- Lead with the most important information
- Use code blocks for all code, commands, and file paths
- Dont write too much code, create code block if necessary.