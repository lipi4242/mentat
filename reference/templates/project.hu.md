# Project sablon (HU)

Meta fájl egy tartós munkához, amelynek saját mappája van.

## Mikor hozz létre ilyet

Tartós munka, amely saját mappát, esetleg saját git repót igényel (az assistent-től
külön). A könnyebb témák, amelyek még nem jutottak el idáig, maradjanak előbb
explorationként.

## Frontmatter

```yaml
---
type: project
name: <projekt-neve>
status: active   # active | paused | done | abandoned
repo_url: https://github.com/...   # opcionális
tags: [...]
---
```

## Tartalom

1. **Mi ez a projekt** — egy sor: mit épít vagy ér el.
2. **Célok** — 2–5 sikerkriterium felsorolása.
3. **Státusz / következő** — jelenlegi fázis és az egyetlen legfontosabb következő teendő.
4. **Kapcsolódó entitások** — kapcsolódó spec, todo és people fájlok elérési útjai.

## Fájlnév

`projects/<name>/_meta.md`

A projektmappa a `projects/<name>/` útvonalon van. Ez a sablon a projekt meta fájlja,
és belépési pontként szolgál az agent számára, amikor a projekten dolgozik.

## Példa

```yaml
---
type: project
name: acme-website
status: active
repo_url: https://github.com/example-org/acme-website
tags: [web, acme]
---
```

**Mi ez a projekt:** Nyilvános weboldal a Acme Studio-hoz — portfólió és kapcsolat.

**Célok:**
- Él a acme.example-on < 1 mp LCP-vel
- Havi posztokhoz blog szekció
- Gmailhez kapcsolt kapcsolatfelvételi űrlap

**Státusz / következő:** Tervezési fázis. Következő: Anna Figma-mockupjának átnézése (határidő: 2026-05-03).

**Kapcsolódó entitások:**
- `agy/specs/acme-blog.md`
- `agy/people/anna-kovacs.md`
- `agy/todos/review-figma-mockup.md`
