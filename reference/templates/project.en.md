# Project Template (EN)

Meta file for a sustained piece of work with its own folder.

## When to create one

A sustained piece of work that warrants its own folder and possibly its own git repo
(separate from the assistant). Lighter topics that haven't committed to this scope
should stay as explorations first.

## Frontmatter

```yaml
---
type: project
name: <project-name>
status: active   # active | paused | done | abandoned
repo_url: https://github.com/...   # optional
tags: [...]
---
```

## Body structure

1. **What this project is** — one line: what it builds or achieves.
2. **Goals** — bullet list of 2–5 success criteria.
3. **Status / next** — current phase and the single most important next action.
4. **Linked entities** — paths to related specs, todos, and people files.

## Filename

`projects/<name>/_meta.md`

The project folder lives at `projects/<name>/`. This template is the project's meta
file and serves as the entry point for the agent when working on the project.

## Example

```yaml
---
type: project
name: acme-website
status: active
repo_url: https://github.com/example-org/acme-website
tags: [web, acme]
---
```

**What this project is:** Public website for Acme Studio — portfolio and contact.

**Goals:**
- Live at acme.example with < 1s LCP
- Blog section for monthly posts
- Contact form connected to Gmail

**Status / next:** Design phase. Next: review Anna's Figma mockup (due 2026-05-03).

**Linked entities:**
- `brain/specs/acme-blog.md`
- `brain/people/anna-kovacs.md`
- `brain/todos/review-figma-mockup.md`
