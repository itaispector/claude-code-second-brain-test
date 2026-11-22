# Does Claude Code need an Obsidian second brain?

A small, repeatable test of four memory setups on the same project. It's the test behind the Medium article *Claude Code Doesn't Need an Obsidian Second Brain. It Has One It Forgets to Use*.

## Results (2026-11-22, Claude Code with Sonnet, 3 trials)

| | none | native | vault | native_rules |
|---|---|---|---|---|
| Overall recall (24 questions) | 12% | 25% | 96% | 88% |
| Inside the project (21) | 3/21 | 6/21 | 21/21 | 21/21 |
| Cross-project (3) | 0/3 | 0/3 | 2/3 | 0/3 |
| Avg input tokens per question | 44.5k | 29.2k | 37.4k | 28.8k |
| Total cost, teaching + questions | $1.17 | $1.20 | $1.39 | $1.37 |

Full report with every answer word for word: [`results/report-2026-11-22.md`](results/report-2026-11-22.md). Raw data: [`results/results-2026-11-22.json`](results/results-2026-11-22.json).

In short: left alone, Claude Code's auto memory saved almost nothing useful (in one trial it saved nothing at all). With four lines of instructions in CLAUDE.md ([`templates/native-rules-CLAUDE.md`](templates/native-rules-CLAUDE.md)), it matched a full Markdown vault on every question inside the project, with fewer tokens. The vault's only measurable edge was cross-project recall.

## The four setups

| arm | auto memory | vault | what it stands for |
|---|---|---|---|
| `none` | off | no | control: Claude only has the code and git history |
| `native` | on | no | Claude's built-in memory (`~/.claude/projects/<repo>/memory/`), no instructions |
| `vault` | off | yes | the "Obsidian second brain" pattern: a shared Markdown vault plus CLAUDE.md rules telling Claude to read and update it |
| `native_rules` | on | no | built-in memory plus the same save-everything rules, pointed at Claude's own memory. Separates "the vault helps" from "the instructions help" |

## How it works

1. Every trial copies a fresh fixture repo (`release-tracker`) for each setup, plus a second repo (`label-site`) for the cross-project question.
2. Four **teaching sessions** run one after another. Each one is a separate `claude -p` process, so nothing carries over except memory files, the vault, and the code Claude changed. They plant facts of different kinds: a rule, a decision with a reason that never goes into code, an outside document, a changed decision (pnpm to bun), and a correction.
3. Eight **questions** run in fresh, read-only sessions and are graded PASS / UNKNOWN / STALE / FAIL. Question sessions can't open the source document, so document questions test memory, not file access.
4. `report.md` shows recall per question and per setup, tokens, cost and time, and every answer word for word.

## Run it yourself

Requirements: Claude Code logged in, Python 3, git. No Obsidian install needed: Claude only ever sees the Markdown files, never the app.

```bash
python3 run.py --mock --trials 1          # 10 second pipeline check with a fake Claude, numbers are fake
python3 run.py --trials 3 --purge-old     # the full run, Sonnet by default, about $5 and 25 minutes
python3 run.py --trials 3 --arms native_rules --model opus
```

Runs go to `~/second-brain-test-runs/<run id>/`. Your real `~/.claude/CLAUDE.md` and settings are never touched.

Isolation: after each setup finishes its questions, its memory folder and vault are archived to `<arm>.tar.gz` (the saved memory is inside `_saved_memory/`) and removed, so no later setup or trial can find them. The run refuses to start while memory folders from earlier runs exist in `~/.claude/projects`; `--purge-old` deletes those first.

## Limits, stated plainly

- **Small n.** Three trials show direction, not statistics.
- **Synthetic fixture.** Eight planted facts on a toy repo is not a real workflow. The same questions on a real project after a week of normal use would be a better test.
- **Sonnet only.** Other models may save memory differently.
- **Regex grading.** It can be wrong in both directions. Every answer is in the report so you can check each grade by hand.
- **Questions favor different setups.** p7 (a document detail never discussed) favors the vault, p2, p4 and p6 (said in chat) suit memory, p8 (cross-project) favors a shared vault by design. Read them separately, not just as one score.
- **Earlier runs had harness bugs** (an answer leaked in a fixture comment, question sessions could read the source document, leftover memory leaked between trials, and a folder lookup missed the `native_rules` memory). All are fixed in this version, and only the 2026-11-22 run in `results/` was made with it.

## Files

- `config.json` - teaching prompts, questions, grading patterns
- `fixture/` - the toy repo; `inputs/call-notes.md` - the outside document
- `templates/vault-CLAUDE.md` - the vault rules; `templates/native-rules-CLAUDE.md` - the same rules for built-in memory
- `run.py` - runner, grader and report; `mock_claude.py` - fake Claude for pipeline tests
- `results/` - the published run

MIT licensed.
