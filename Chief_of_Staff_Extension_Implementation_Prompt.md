# Fibonacci — Chief of Staff Extension: Implementation Prompt

## Instruction to the internal implementation LLM
You are modifying an EXISTING, WORKING Fibonacci Chief of Staff agent in an on-premises OpenMausBot deployment. Do not rewrite its SOUL.md or replace its routing implementation. First inspect the actual Chief of Staff instructions, agent registry, tool/handoff conventions, and relevant existing tests. Make a minimal, reviewable ADDITIVE change that introduces a planning route. Follow actual project naming, file locations, and configuration; do not invent them.

### Existing behavior — preserve exactly
The live automation path works end-to-end:
Chief of Staff → Capability Map/Discovery (Graphify) → Test Designer (complete pytest code, including when gaps exist) → Implementor → Jira Ticket Opener.
A natural-language request such as "Create a new target, acquire it, verify acquisition status, then export device data" must continue to enter this path. The user must NEVER need to name an internal agent. Preserve existing tool permissions, approval prompts, task identity propagation, implementation status semantics, and Jira task behavior. Do not modify the five existing agents' SOUL files or code unless a demonstrably necessary, separately explained integration change is approved.

### New capability — intent-based route
Add routing based on USER INTENT, not simplistic keyword or URL presence:
- Requests to plan QA testing or derive test cases from requirements (natural-language description, Jira issue, Confluence PRD, Tech Spec, or any combination) → Test Planner.
- Requests to directly create an automation test from a described flow → existing Capability Map route.
- A URL alone does not always imply planning; interpret the user's instruction and ask one concise clarification if genuinely ambiguous.
- A planning request without a URL can still enter Test Planner if sufficient requirements are supplied as text; otherwise ask for required details.
- Do not route every mention of "test" or "PRD" to planning if the actual request is to implement automation.

### Planning workflow
1. Chief of Staff passes user request, all supplied source links, optional platform/environment context, and stable task ID to Test Planner. Sources are independent/optional: Jira only, PRD only, Tech Spec only, combinations, and Jira linking to Confluence must all work.
2. Test Planner uses authorized Jira and Confluence READ tools, follows relevant bounded links, reconciles requirements, and drafts a high-level Test Plan. Material source contradictions require a STOP and QA clarification; do not choose a source silently.
3. Present the draft Test Plan and WAIT for explicit QA approval. QA feedback goes back to Test Planner for revision; repeat until approval. Preserve exact approved plan revision and references.
4. Invoke Test Case Generator ONLY with the approved plan snapshot, explicit approval signal, original source references, and task identity.
5. Present generated manual Test Cases with preconditions, steps, and expected results. Allow QA revisions until explicit case-set approval.
6. Ask QA to select specific case IDs for automation. Automatically mark each selected automation case as regression. Do not auto-select every case. No selection means no automation run.
7. Pass ONLY selected approved cases into the existing Capability Map route, then let the original pipeline continue unchanged. Preserve per-case traceability and a stable task identity through the handoff. If existing pipeline expects a single flow, adapt inputs at the orchestration boundary without changing its behavior; avoid accidental creation of duplicate Jira tasks and use the existing stable identity semantics.
8. Zephyr synchronization and test duplicate detection are explicitly OUT OF SCOPE for this change.

### Integration requirements
- Discover actual names/IDs of the new agents and their invocation interface. If not yet registered, describe precise registration changes rather than pretending they exist.
- Use existing native approval/HITL mechanism; never simulate user approval by writing `approved=true` unilaterally.
- Preserve state across pauses and revisions (task ID, plan ID/revision, case set/revision, selected case IDs, source references, and current stage). Support safe resume without repeating upstream implementation steps.
- Separate planning approval from test-case approval/selection; neither is implicit.
- Respect native MCP tool permissions and avoid unauthorized Jira/Confluence writes.
- If a source cannot be read, report which one and ask for user guidance where material; do not invent content.
- On contradictions, pause before plan approval. On material requirement changes after approval, return for re-planning rather than silently altering the approved plan.
- Do not assume a specific agent config format, OpenMausBot API, JSON schema, branch, repository path, or Jira key. Inspect first and adapt the logical contracts in the two new SOUL files to the actual framework.

### Implementation sequence
1. Read the current Chief of Staff SOUL.md and routing/orchestration implementation.
2. Map current inputs, outputs, agent invocation, state persistence, and native approvals.
3. Identify the smallest new section(s)/routing branch and required registration/interface changes.
4. Add only those changes; leave existing automation route untouched.
5. Add focused tests or dry-run examples for both routes and HITL behavior. Do not execute real repository writes, PR creation, or Jira writes during routing tests without authorization.
6. Return a concise diff summary, changed files, assumptions, unresolved integration requirements, and verification evidence. If the new agents are not installed, state that explicitly.

### Required acceptance checks
- Existing natural-language automation flow still routes directly to Capability Map and reaches all existing stages.
- Jira-only, Confluence-PRD-only, Tech-Spec-only, mixed sources, and linked Jira→Confluence route to planning.
- A natural-language Test Plan request without links routes to planning.
- Material PRD/Spec conflict pauses for clarification.
- Plan feedback causes re-plan; Test Case Generator is not invoked until explicit plan approval.
- Case feedback causes revision; automation does not start until explicit case approval AND selection.
- Selected automation cases are also regression; unselected cases are not sent downstream.
- No selected cases → no automation pipeline invocation.
- Existing task identity, Jira single-task behavior, and implementation permissions remain intact.
- Zephyr and duplicate-detection are not accidentally implemented or invoked.

### Deliverable
Provide the precise additive SOUL.md section or patch, any minimal routing/config changes needed, and a short implementation/verification report. Do NOT output an entirely new Chief of Staff SOUL.md unless explicitly requested.
