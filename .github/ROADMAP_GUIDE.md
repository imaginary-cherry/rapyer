# Roadmap Management Guide

This repository uses **GitHub Issues as the source of truth** for the roadmap. The roadmap documentation is automatically generated during the CI/CD process.

## How It Works

```
GitHub Issues (labeled: roadmap)
           ↓
    [Docs CI/CD triggers]
           ↓
  Generate docs/roadmap.md
           ↓
    Build & deploy docs
           ↓
  Roadmap visible on docs site
```

**Key Points:**
- ✅ `docs/roadmap.md` is **generated automatically** - never edit it manually
- ✅ Issues with the `roadmap` label appear in the documentation
- ✅ The roadmap updates automatically when issues are created, edited, or closed
- ✅ Milestones group related features together

## Creating Roadmap Items

### Using the Issue Template

1. Go to [New Issue](https://github.com/imaginary-cherry/rapyer/issues/new/choose)
2. Select "Roadmap Feature" template
3. Fill in the details:
   - **Feature Goal**: High-level category (e.g., "Bulk Operations")
   - **Description**: What the feature does and why
   - **Example Usage**: Code showing how it would work
   - **Benefits**: Key advantages
   - **Priority**: How important it is

### Manually Creating Issues

You can also create regular issues and add the `roadmap` label:

1. Create a new issue
2. Add the `roadmap` label
3. Optionally assign to a milestone
4. Use checkboxes in the issue body for sub-tasks:
   ```markdown
   - [ ] Task 1
   - [ ] Task 2
   - [x] Completed task
   ```

## Organizing with Milestones

Use GitHub Milestones to group related features:

1. Go to [Milestones](https://github.com/imaginary-cherry/rapyer/milestones)
2. Create a milestone (e.g., "v2.0 - Advanced Features")
3. Assign roadmap issues to the milestone
4. Issues will be grouped by milestone in the roadmap

## Labels

- **`roadmap`** (required): Includes the issue in the roadmap
- **`enhancement`**: Feature addition
- **`in-progress`**: Currently being worked on (adds 🚧 emoji)
- **`high-priority`**: Important features
- **Custom labels**: Add your own for categorization

## Issue Status

- **Open issues**: Shown with `[ ]` checkbox
- **Closed issues**: Shown with `[x]` checkbox and ✓ emoji
- **In-progress**: Open issues with `in-progress` label get 🚧 emoji

## Automatic Updates

The roadmap updates automatically when:
- ✅ A roadmap issue is created, edited, or closed
- ✅ Docs are pushed to the main branch
- ✅ Manually triggered via workflow dispatch

## Migration from Old Roadmap

If you have items in the old `docs/roadmap.md`:

1. Create GitHub issues for each major feature/goal
2. Add the `roadmap` label
3. Assign to appropriate milestones
4. The old roadmap file is now ignored by git

## Benefits of This Approach

✅ **Single Source of Truth**: Issues are the authoritative source
✅ **Rich Features**: Comments, assignments, references, automation
✅ **Always in Sync**: Docs update automatically
✅ **Better Organization**: Milestones, labels, project boards
✅ **Community Engagement**: Users can discuss and contribute
✅ **No Manual Updates**: CI/CD handles everything

## Example Issue Structure

```yaml
Title: [Roadmap] Bulk Operations Support
Labels: roadmap, enhancement, high-priority
Milestone: v2.0 - Performance Features

Body:
**Goal**: Enable efficient bulk operations for multiple models

### Description
This feature allows users to insert, update, and delete multiple
models in a single Redis transaction.

### Tasks
- [ ] Bulk insert implementation
- [ ] Bulk update implementation
- [ ] Bulk delete implementation
- [ ] Documentation and examples

### Example Usage
\```python
users = [User(name=f"user{i}") for i in range(100)]
await User.bulk_insert(users)
\```

### Benefits
- Better performance for large datasets
- Reduced Redis round trips
- Cleaner API for batch operations
```

## Questions?

Check out the [Documentation](https://imaginary-cherry.github.io/rapyer/) or open a [Discussion](https://github.com/imaginary-cherry/rapyer/discussions).
