# Working with Codex in VS Code

This is a project workflow, not a guarantee that AI generates correct code without review. This ChatGPT conversation and Google documents are not automatically transferred to the IDE.

## 1. Open the project locally

Extract the handoff ZIP. Open the `multi-channel-order-platform` folder in VS Code, with `AGENTS.md` at the workspace root. Keep the supplied `docs/` and `fixtures/` paths intact. Do not use the older Retail & Finance/UCI project context as this project's specification.

Install or enable the official OpenAI Codex extension using the installation link in the [official IDE guide](https://learn.chatgpt.com/docs/codex/ide). Open the Codex sidebar (Command Palette: `Codex: Open Codex Sidebar` if needed) and sign in through the supported flow. Open the status/plan files so you can review them beside code.

For this container/Linux-oriented DE project, WSL2 with VS Code's WSL workflow is a recommendation if already available. Codex also supports native Windows; WSL is not a prerequisite to read docs or edit code. Inspect current Git/Python/Docker/Compose availability first. Follow the [official WSL guide](https://learn.chatgpt.com/docs/windows/wsl) for that option.

## 2. Create the first Git checkpoint

If this folder is already inside a repository, inspect `git status` and reuse it; do not initialize a nested repository. Otherwise, after checking files and configuring your own Git identity if needed:

```bash
git init -b main
git add README.md AGENTS.md docs fixtures .gitignore
git diff --cached --stat
git diff --cached --check
git commit -m "docs: establish S01 project contract and milestones"
```

Review staged paths before committing. These commands do not create a GitHub repository or push data. Create an empty remote repository under your own account if desired, then configure its actual URL. Push only when you choose to publish; never paste credentials into a prompt or commit them.

## 3. First implementation prompt

Use after reviewing the proposed architecture/report/plan. If you want to change the tool or release strategy first, specify that change instead of implying approval.

```text
Read AGENTS.md, docs/STATUS.md and milestone M01 in docs/04_PLAN.md.
For this task I accept the proposed M01 technical direction; preserve the
approved S01/source contracts. Implement M01 only.

Inspect the current repository, Git status and available local tools first.
Finalize the target field dictionary and constraints before dependent DDL.
Implement storage/bootstrap, run the milestone acceptance checks, and
record exact results and any checks you could not run in docs/STATUS.md.
Explain important choices and results to me in Vietnamese.

Inspect the diff, run git diff --check, and leave all changes unstaged for
my review. Report the review points, exact checks, suggested commit message,
and remaining risks. Stop before M02. Do not stage, commit, or push.
```

The approval sentence above is a template for the owner to use if they agree. The existence of this file does not approve the pending design.

## 4. Milestone loop

Select one milestone → implement → run checks → inspect diff and demo → update status/contracts → leave changes unstaged → owner review → owner stages/commits/pushes. Use a branch such as `milestone/m01-foundation` if desired. Codex suggests the milestone commit message but performs Git write actions only when explicitly requested in the current task.

At review, ask Codex to explain what changed, why it meets acceptance, actual test evidence, known limitations and the next task. A failing required check means the milestone is not complete. Code generation alone is not acceptance. Use `git diff`, `git diff --check`, and `git status --short` before you stage and commit the reviewed checkpoint.

## 5. Resume in a new chat

Current checkpoint (2026-10-28): M05A CLI/runtime and M05B periodic website/eBay
orchestration have runtime evidence in STATUS; changes are unstaged for review.
Do not automatically start M06. When selected by the owner, read M06 and
`docs/06_AUTOMATION.md`, preserving the manual S01 and scheduled modes.
Runner text `M05 PASS` validates A; `M05B PASS` validates scheduled/recovery checks.

```text
Continue this repository. Read AGENTS.md, docs/STATUS.md and the relevant
milestone in docs/04_PLAN.md. Inspect the current branch, commit and files.
Summarize the actual checkpoint, then implement only M<NUMBER> using its
acceptance criteria. Preserve approved behavior. Run the required checks,
update STATUS, leave changes unstaged for my review, and stop before the next
milestone. Do not stage, commit, or push.
```

`AGENTS.md` is recognized repository guidance. Other filenames here are our conventions; root instructions tell the agent to read them. Context files do not replace checking the live code/environment. See the [official AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md) and [iterative workflow example](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex).
