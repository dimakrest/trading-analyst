# Implementation Plans

This directory contains detailed implementation plans created by the `/create_plan` command.

## Structure
- Filename: `YYYY-MM-DD-description.md`
- Contains: Phased implementation plan with success criteria
- Purpose: Guide systematic implementation of features

## Usage
```bash
/create_plan thoughts/shared/tickets/2025-01-15-add-feature.md
# Creates: thoughts/shared/plans/2025-01-15-add-feature.md
```

## Plan Format
Implementation plans include:
- Overview and current state analysis
- Desired end state
- What we're NOT doing (scope boundaries)
- Implementation approach and phases
- Detailed changes per phase with code examples
- Success criteria (automated and manual verification)
- Testing strategy
- Performance considerations
- Migration notes (if applicable)
- References to tickets and related research

## Implementation Process
1. Create ticket describing the feature/task
2. Run `/create_plan` with ticket path
3. Review and iterate on plan until approved
4. Execute plan using `/implement_plan`
5. Complete phases sequentially with verification gates

Plans are living documents that can be updated during implementation if reality differs from expectations.
