---
description: Review a PR using Google's Gemini CLI for an alternative AI perspective
---

# Gemini PR Review

Use the Gemini CLI to review a pull request, providing an alternative AI perspective on code changes.

## Steps to follow:

1. **Identify the PR to review:**
   - If a PR number is provided as argument, use it directly
   - If no PR number provided, run `gh pr list --limit 10` to show open PRs
   - Ask the user which PR they want Gemini to review

2. **Invoke Gemini CLI to review the PR:**

   Run the following Bash command (replace `<number>` with the actual PR number):

   ```bash
   gemini -y "You are a senior developer reviewing a colleague's code. Be critical and thorough - your job is to catch issues before they reach production.

   Review PR #<number> in this repository. Use gh pr view <number> to get the PR details and gh pr diff <number> to get the code changes.

   Your review should:

   1. **Understand the Feature**: What problem is this solving? Does the implementation actually solve it?

   2. **Find Blind Spots**: What edge cases might the author have missed? What assumptions are being made that could break?

   3. **Challenge Design Decisions**: Is this the right approach? Are there simpler alternatives? Is this over-engineered or under-engineered?

   4. **Look for Hidden Bugs**: Race conditions, off-by-one errors, null/undefined handling, error propagation, resource leaks.

   5. **Question Test Coverage**: Are the tests actually testing the right things? What scenarios are NOT tested? Could these tests pass with a broken implementation?

   6. **Security & Performance**: Any injection risks, data exposure, N+1 queries, unnecessary allocations, blocking operations?

   7. **Maintainability**: Will future developers understand this? Is it consistent with the codebase patterns?

   Be constructive but don't hold back. If something looks wrong, say it. If you're unsure about something, ask the question anyway.

   Format your review with clear sections. Reference specific files and line numbers when pointing out issues."
   ```

3. **Present the output:**
   - Display Gemini's review to the user
   - The review will appear directly from the Bash command output

## Example Invocations

```
/gemini_review 66        # Review PR #66
/gemini_review PR 66     # Also works with "PR" prefix
/gemini_review           # Interactive - lists open PRs and asks user
```

## Notes

- Uses `-y` (yolo) flag to auto-approve tool calls so Gemini can run `gh` commands
- Gemini CLI fetches PR details autonomously using `gh pr view` and `gh pr diff`
- Review quality depends on Gemini's analysis capabilities
- Useful for getting a second opinion on code changes
