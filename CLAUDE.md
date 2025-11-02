
## Git Workflow - CRITICAL REQUIREMENTS
⚠️ **STRICT ADHERENCE REQUIRED** - These git workflow rules are mandatory and must be followed exactly:

- **Auto-commit after EVERY change**: You MUST commit immediately after ANY file modification, no matter how small - NO EXCEPTIONS. This includes:
  - Single line edits
  - Configuration changes
  - Code refactoring
  - ANY file creation or deletion
- **Run git operations on the background**: ALWAYS run git commands on the background so productivity is not impacted - NEVER call git directly from main thread
- **Commit first, ask questions later**: Do NOT wait for user confirmation before committing. Commit immediately after making changes
- **Push frequently**: Push after every few commits or when completing a logical unit of work
- **Include lint/test status in commits**: Run lint before committing. If there are failures, fix them if possible or note in commit message and proceed
- You must use uv if using python tools