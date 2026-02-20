# LLM CLI Integration

Use this repo's compact skill to help LLM CLI agents work with `sia-code` reliably.

## 1) Copy the skill file

Source file in this repo:

- `skills/sia-code/SKILL.md`

Copy it into your local CLI skill directory.

### OpenCode example

```bash
mkdir -p ~/.config/opencode/skills/sia-code
cp skills/sia-code/SKILL.md ~/.config/opencode/skills/sia-code/SKILL.md
```

Then restart OpenCode (or reload skills if your setup supports hot reload).

## 2) Use the skill in your prompt/session

Typical invocation:

```text
Load skill sia-code
```

## 3) Recommended agent workflow

```bash
uv tool install chunkhound
uvx sia-code status
uvx sia-code init
uvx sia-code index .
uvx sia-code search --regex "your symbol"
uvx sia-code research "how does X work?"
```

Notes:

- `search` and `research` are ChunkHound-backed.
- Memory commands stay in Sia's local memory database.

## 4) Optional memory workflow

```bash
uvx sia-code memory sync-git
uvx sia-code memory search "topic"
uvx sia-code memory add-decision "Decision title" -d "Context" -r "Reason"
```

## 5) Multiple worktrees / multiple Claude Code instances

Use one of these index strategies per session:

```bash
# Shared index across worktrees/instances (best for reuse)
export SIA_CODE_INDEX_SCOPE=shared

# Isolated index per worktree/instance
export SIA_CODE_INDEX_SCOPE=worktree
```

If you need full control, set an explicit directory:

```bash
export SIA_CODE_INDEX_DIR=/absolute/path/to/sia-index
```

Recommendation:

- Shared mode for many search/read sessions
- Worktree mode when you want strict isolation per branch/agent
- For shared mode, avoid many simultaneous index writers

## Notes

- Keep the skill file short and practical for agent speed.
- Update this file when CLI behavior changes.
