# Review: pr-56-review-analysis.md

## [1] done — "16	Schema Field duplication across 2 request types	Consider	Pattern is now in 4 ..."
**Section:** PR #56 Review — Analysis & Recommendations > Recommendations Table
**Line:** 21

> ```
> line 19: ## Recommendations Table
> line 20: 
> line 21: | # | Item | Severity | Why it matters | Risk if ignored | Recommendation |
> line 22: |---|------|----------|----------------|-----------------|----------------|
> line 23: | 1 | MA50 `<Label>` not associated with toggle button (`ArenaSetupForm.tsx:1185-1201`) | **Must Fix** | Click-on-label is broken; assistive tech can't bind label↔control | Low blast (UX only) but blocks merge per reviewer | **Fix now** — 2-line change, swap to ShadCN `<Toggle>` or add `id`/`htmlFor` |
> ```

**[user]** we should address this

**[agent-context]** Reviewer wants item #16 (schema Field duplication across CreateSimulationRequest and CreateComparisonRequest) addressed in this PR rather than deferred to a follow-up. I'll promote it from 'Defer — separate cleanup PR' to 'Fix now', bundle it into the merge plan, and update the rationale to reflect that 4 layers of drift is the right time to extract the mixin.

**[agent]** Promoted item #16 from 'Defer' to 'Fix now in this PR'. Updated the table row to call out that 4 phases of drift is the inflection point where extracting an EntryFiltersMixin pays off, and moved item 16 from the follow-up bucket to the 'Bundle into this PR' bucket in the merge plan.

---
