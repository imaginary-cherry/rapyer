# Deferred Items -- quick-260715-taa

## tests/integration/foreign_keys/test_foreign_key.py: pre-existing combined-label comments

Out of scope for this plan (not in the 15-file `files_modified` list; contains zero
cascade-related tests). Found via the directory-wide grep check while verifying Task 2:

- line 23: `# Arrange / Act`
- line 37: `# Act / Assert`
- line 80: `# Arrange / Act`
- line 93: `# Act / Assert`

Not fixed here per the SCOPE BOUNDARY rule (pre-existing issue in an unrelated file).
If the reviewer wants full-suite AAA-label consistency beyond the cascade tests, this
file should be scoped into a follow-up quick task.
