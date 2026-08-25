# Issue tracker: GitHub

Issues for this repo live in GitHub Issues. Use the `gh` CLI for all issue operations.

The canonical repository is `yuewen-ye/patent-tutor-agent`; `gh` infers it from the current clone.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments`, with `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

## Wayfinding operations

Wayfinder maps and decision tickets are GitHub issues. The map carries the `wayfinder:map` label;
child decision tickets carry one of `wayfinder:research`, `wayfinder:prototype`,
`wayfinder:grilling`, or `wayfinder:task`. Create issues with `gh issue create`, link child tickets
in the map body, record resolutions as comments, and close resolved tickets with `gh issue close`.

Infer the repo from `git remote -v` — `gh` does this automatically when run inside a clone.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.
