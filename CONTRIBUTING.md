# Contributing

Thanks for wanting to help. Here's everything you need to know.

---

## Bugs

Open an issue. Include:

- The video URL (or a similar one that reproduces it)
- What you expected to happen
- What actually happened — the full traceback, not just the last line
- Your Python version

If you can reproduce it in five lines of code, paste that too. I'll get to it
faster.

## Pull requests

Keep them small and focused. A PR that does one thing is much easier to review
than one that does five. If you're planning something large, open an issue first
so we can talk about whether it's the right direction before you spend time on
it.

Before submitting:

```bash
poetry run pytest tests/ -v        # all tests should pass
poetry run mypy pytube/ --ignore-missing-imports  # no new type errors
```

I use conventional commit messages loosely — `fix:`, `feat:`, `chore:`. Not
strictly required, but helps when I'm scanning history.

## What I'm likely to accept

- Fixes for broken streams or extraction failures
- Keeping up with YouTube's InnerTube API changes
- Genuine improvements to the CLI or progress output
- Test coverage for untested paths

## What I'm likely to decline

- Cosmetic cleanups that don't fix anything
- Large refactors without a clear benefit
- New features that add complexity for edge cases I don't use

If you're unsure, ask in an issue before writing code.

---

That's it. PRs welcome.
