---
description: Review implementation plans using Google's Gemini CLI for an alternative AI perspective
---

# Gemini Plan Review

Use the Gemini CLI to review an implementation plan, ensuring it follows project guidelines and technical best practices.

## Steps to follow:

1. **Identify the plan to review:**
   - If a plan path is provided as argument, use it directly
   - If no path provided, check for plans in `thoughts/shared/plans/` and list recent ones
   - Ask the user which plan they want Gemini to review

2. **Invoke Gemini CLI to review the plan:**

   Run the following Bash command (replace `<plan_path>` with the actual plan file path):

   ```bash
   gemini -y "You are a senior software architect reviewing an implementation plan for a trading system that handles real money. Be critical and thorough.

   Review the implementation plan at: <plan_path>

   First, read the plan file. Then read these project guidelines:
   - CLAUDE.md (project rules and YAGNI principles)
   - .claude/context/ARCHITECTURE.md (architecture guidelines)
   - docs/guides/testing.md (testing standards)

   Your review should check:

   1. **Completeness**: Does the plan address all requirements from the ticket? Are there gaps?

   2. **Technical Soundness**: Are the proposed changes technically correct? Will they work?

   3. **YAGNI Compliance**: Is the plan adding unnecessary complexity? Is it over-engineered?
      - Check against YAGNI DOES Apply To list (what NOT to build)
      - Check against YAGNI NEVER Applies To list (what MUST be done)

   4. **Quality Standards**: Does the plan include:
      - Proper error handling?
      - Input validation?
      - Tests for new functionality?
      - Edge case handling?

   5. **Risk Assessment**: What could go wrong? What are the failure modes?

   6. **Testing Strategy**: Are success criteria measurable? Are tests comprehensive?

   7. **Implementation Order**: Is the phase sequence logical? Are dependencies handled?

   8. **Security Considerations**: Any security implications for a trading system?

   Provide specific, actionable feedback. Reference specific sections of the plan when pointing out issues. Categorize feedback as:
   - CRITICAL: Must fix before implementation
   - IMPORTANT: Should fix, significant improvement
   - MINOR: Nice to have, low priority

   Be constructive but don't hold back. This system handles real money."
   ```

3. **Present the output:**
   - Display Gemini's review to the user
   - The review will appear directly from the Bash command output

## Example Invocations

```
/gemini_plan_review thoughts/shared/plans/2025-12-18-backtest-hunter-integration.md
/gemini_plan_review    # Interactive - lists recent plans and asks user
```

## Notes

- Uses `-y` (yolo) flag to auto-approve tool calls so Gemini can read files
- Gemini reads the plan and project guidelines autonomously
- Review checks plan against project-specific rules (YAGNI, testing, security)
- Useful for getting a second opinion before implementing a plan
