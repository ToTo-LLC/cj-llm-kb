# Cross-domain confirmation modal — microcopy

> **Plan 12 Task 7** — Per D9, the user-facing strings for the cross-domain
> confirmation modal and its companion Settings toggle, drafted before
> Task 9's frontend implementation so the implementer has a finalized
> reference rather than inventing copy at code time.
>
> **Trigger (D7):** modal fires when a chat or draft session's scope contains
> two or more domains AND at least one of those domains is in
> `Config.privacy_railed`. Single-domain railed access does not trigger
> (the explicit slug inclusion already serves as the consent). Pure
> cross-domain access without rails (e.g. `[research, work]`) does not
> trigger either.
>
> **Acknowledgment (D8):** persists as `Config.cross_domain_warning_acknowledged: bool`
> (per-vault, default `False`). User can re-enable the modal via the
> "Show cross-domain warning" toggle in Settings → Domains.

---

## Voice and tone notes

These strings follow the voice rules from `docs/design/design-brief.md`
§ "Voice, tone, microcopy":

- **Calm, not alarming.** This is a confirmation, not a warning page. The
  user picked the scope themselves; we're confirming, not interrogating.
- **Plain English.** "Privacy-railed" is internal jargon. User-facing
  copy uses **"private"** consistently — short, accurate, doesn't require
  a glossary entry.
- **Respect the user.** Phrasing assumes the user knows what they're doing
  and wants a clean way to skip the confirmation next time. No "are you
  sure?" hand-wringing.
- **Verbs on buttons, not "OK / Cancel".** Primary action is **"Continue"**
  (the verb the user is doing — continuing into the chat); secondary is
  **"Back to scope"** (states what the secondary actually does — returns
  to the scope picker, doesn't just dismiss).
- **No exclamation points. No emoji. No "please".**
- **Lowercase "brain"** — product as noun.

---

## Modal text

### Eyebrow (small uppercase label above the title)

> Confirm scope

> *Note: the existing `Modal` component supports an optional eyebrow slot
> rendered as `text-xs uppercase tracking-wider text-muted-foreground`.
> Use it to anchor the dialog's purpose without bloating the title.*

### Title

> Including a private domain in this chat

### Body (1–3 short sentences)

> You picked **{railed_slugs_joined}** alongside **{other_slugs_joined}**
> for this chat's scope. **{railed_slugs_joined}** {is_or_are} kept private
> by default — notes there only show up when you explicitly include
> {it_or_them}, like you just did.
>
> If you'd rather keep this chat single-domain, head back and adjust the
> scope. Otherwise continue, and brain will treat the included private
> notes as in-scope for this chat. See **BRAIN.md** for how scope and
> privacy work in your vault.

#### Concrete render with example scope `[research, personal]`

> You picked **personal** alongside **research** for this chat's scope.
> **personal** is kept private by default — notes there only show up
> when you explicitly include it, like you just did.
>
> If you'd rather keep this chat single-domain, head back and adjust the
> scope. Otherwise continue, and brain will treat the included private
> notes as in-scope for this chat. See **BRAIN.md** for how scope and
> privacy work in your vault.

### Primary button (right, ember `--brand-ember`)

> Continue

### Secondary button (left, ghost variant)

> Back to scope

> *Rationale: shadcn convention is `variant="default"` for primary and
> `variant="ghost"` for secondary, mirroring `TypedConfirmDialog`. Plain
> "Cancel" is ambiguous here (does it cancel the chat? cancel the modal?);
> "Back to scope" names the destination.*

### "Don't show again" checkbox

**Label** (next to the checkbox, left-aligned in the footer):

> Don't show this again

**Tooltip** (on hover/focus of the label or a small `?` icon):

> Skip this check for future chats. You can turn it back on under
> Settings → Domains.

> *Behavior: when checked AND the user clicks **Continue**, the frontend
> calls `brain_config_set` with `key=cross_domain_warning_acknowledged,
> value=true`. Unchecked Continue does not change the setting. Clicking
> **Back to scope** does not change the setting regardless of the
> checkbox state — the modal will fire again next time the trigger fires.*

---

## Settings toggle text

Lives at the bottom of `panel-domains.tsx`, below the per-domain rows
and above the "Add domain" form. Uses the existing shadcn `Switch`
primitive (`apps/brain_web/src/components/ui/switch.tsx`).

### Section heading

> Cross-domain warning

### Toggle label (right of the switch)

> Show cross-domain warning

### Helper text

**When the toggle is ON** (`Config.cross_domain_warning_acknowledged = false`):

> Before starting a chat that mixes a private domain (like
> **personal**) with another domain, brain will ask you to confirm.

**When the toggle is OFF** (`Config.cross_domain_warning_acknowledged = true`):

> The confirmation is off. Mixed-scope chats including private domains
> will start without a prompt. Turn this back on if you want the check
> back.

> *Implementation note: the toggle is the inverse of the underlying
> Config field — toggle ON means "show the warning", which corresponds
> to `cross_domain_warning_acknowledged = false`. The frontend should
> store the bound value as `!cross_domain_warning_acknowledged` so the
> mental model in the UI is "show this thing: yes/no".*

---

## Variable substitution

The modal body has four runtime substitutions. The frontend computes
them from the session's chosen scope and `Config.privacy_railed`.

| Placeholder | Source | Example for scope `[research, personal]` |
|---|---|---|
| `{railed_slugs_joined}` | scope ∩ `privacy_railed`, joined with " and " | `personal` |
| `{other_slugs_joined}` | scope − `privacy_railed`, joined with " and " | `research` |
| `{is_or_are}` | "is" if 1 railed slug, else "are" | `is` |
| `{it_or_them}` | "it" if 1 railed slug, else "them" | `it` |

**Multi-railed example.** If the user has added `journal` to
`Config.privacy_railed` and picks scope `[research, work, personal, journal]`,
the body renders as:

> You picked **personal and journal** alongside **research and work** for
> this chat's scope. **personal and journal** are kept private by default
> — notes there only show up when you explicitly include them, like you
> just did.
>
> If you'd rather keep this chat single-domain, head back and adjust the
> scope. Otherwise continue, and brain will treat the included private
> notes as in-scope for this chat. See **BRAIN.md** for how scope and
> privacy work in your vault.

**Joining rule.** Use Oxford-comma-style "A, B and C" for ≥3 items
(e.g. `personal, journal and finance`). For exactly 2: "A and B". For
exactly 1: just the slug.

> *Rationale: keeps the body grammatical without per-count branching
> in the prose. Plurals adapt via `{is_or_are}` and `{it_or_them}`. Slug
> names render in **bold** (not in code/mono) — they're domain names,
> not paths.*

---

## Out of scope (what this doc does NOT cover)

These are intentionally deferred to other Plan 12 tasks or Plan 13+:

- **Spec § 4 line 187 amendment.** Task 10 owns the spec wording change
  (literal "personal content" → "privacy-railed content") and the new
  ~3 sentences documenting the D7 trigger and D8 acknowledgment storage.
  This microcopy doc informs that wording but does not write to the spec.
- **`docs/user-guide/domain-overrides.md` cross-domain-modal section.**
  Task 10 owns the user-guide addition.
- **Toast strings for "couldn't save acknowledgment" failure paths.** The
  existing toast pattern in `panel-domains.tsx` (lead + msg + variant)
  covers this; the implementer reuses it. Suggested defaults if the
  implementer wants a starting point: lead `"Couldn't save."` + msg
  `"The cross-domain setting didn't save. The check will run again next
  time."` + variant `"danger"`.
- **Modal copy for the "no scope chosen yet" pre-trigger state.** The
  modal only renders when the trigger condition is met; the upstream
  scope picker handles its own validation copy.
- **Per-thread persistence.** D8 chose per-vault; per-thread is
  explicitly out of scope (violates spec § 4 "one-time").
- **Renaming the existing "Privacy-railed" badge in `panel-domains.tsx`.**
  The badge is a power-user-facing label inside Settings → Domains; the
  word "private" in the modal applies only to the modal's user-facing
  surface. Cross-rename of the badge is a Plan 13+ consistency pass.

---

## Self-review pass (per Plan 12 Task 7 checklist)

- **Calm, not alarming.** Re-read the body: "kept private by default"
  is descriptive, not scary. "If you'd rather … head back" is gentle.
  No red text, no warning iconography in the spec for the mock — color
  cues are reserved for the privacy badge inside the modal so the
  modal's frame stays calm. ✅
- **Names the railed slugs.** Body explicitly substitutes the slug name
  (e.g. "personal") rather than saying "a private domain." ✅
- **"Don't show again" is unambiguous.** The tooltip names the recovery
  surface ("Settings → Domains") so "again" doesn't strand the user. ✅
- **Settings toggle helper covers both states.** ON and OFF copy are
  drafted separately so the implementer doesn't have to invent the
  off-state string. ✅
- **D7 trigger semantics are correct.** Body says "mixes a private
  domain … with another domain" — captures the ≥2-domains-and-≥1-railed
  rule without naming the rule. ✅
- **No spec amendments.** No edits to `docs/superpowers/specs/`. ✅
- **No code.** This file is documentation only. ✅

---

## Plan 15 D4 — Privacy-railed jargon alignment

> **Supersedes Plan 12 Task 7's "private" preference.** Plan 15 D4 locks
> a single user-facing term across both surfaces — "Privacy-railed" — so
> the modal copy and the Settings → Domains badge speak the same
> vocabulary. The earlier "Voice and tone" note that "Privacy-railed is
> internal jargon" is **no longer in effect** — Plan 15 reclassifies it
> as the user-facing term and pairs it with a glossary tooltip so first
> encounters don't strand a non-technical reader. Sections above (Modal
> text, Settings toggle text, Variable substitution) describe the
> Plan 12 shape; the strings in this section are the Plan 15 production
> copy that brain-frontend-engineer pastes into the TSX verbatim.

### Locked terminology

| Term | Use it like this | Don't say |
|---|---|---|
| **Privacy-railed** (proper-noun phrase, hyphenated, capital P) | "a Privacy-railed domain"; "Privacy-railed notes"; "**personal** is Privacy-railed" | "private domain", "kept private", "private notes", "the privacy rail's domain" |
| **the privacy rail** (lowercase, when naming the underlying mechanism — already in helper text on `panel-domains.tsx` line 564) | "Domains in the privacy rail are excluded from default and wildcard queries." | n/a — keep the existing usage |

The badge label "Privacy-railed" inside `panel-domains.tsx` (lines 635,
659, 683) is unchanged — Plan 15 D4 brings the rest of the copy into
alignment with what that badge already says.

### Glossary tooltip

A small `(?)` icon-button sits immediately after the **first** occurrence
of "Privacy-railed" in each surface (modal body and Settings helper
text). The icon's tooltip content is the same string in both places so
the user only learns the term once.

**Tooltip text (canonical, 85 chars):**

> Domains marked Privacy-railed never appear in chats unless you include them yourself.

Character count: 85 — under the 90-char ceiling, fits the existing
`<TooltipContent>` width without a line break on a 1280px target.

**Why this wording, not D4's literal "domains marked as private; never
appear in default queries":**
- "Marked Privacy-railed" repeats the term so the reader connects
  definition to label, instead of reintroducing "private" (which is the
  word we're moving away from).
- "Never appear in chats unless you include them yourself" replaces
  "default queries" (engineering jargon) with a behavior the user
  actually performs (picking scope for a chat). Same meaning, plainer
  vocabulary.
- One sentence, no semicolons, no parentheticals — readable end-to-end
  by a screen reader without punctuation gymnastics.

**Tooltip icon — accessibility + placement contract for the implementer:**

- Use the existing tooltip primitive in the codebase (the modal already
  imports `Tooltip` / `TooltipTrigger` / `TooltipContent` from
  `~/components/ui/tooltip`; reuse those — do not invent a new
  component). The trigger should be a `<button type="button">` with a
  small `?` glyph or the codebase's existing help icon, not a bare
  `<span>` — keyboard users need to focus and dismiss it.
- `aria-label="What does Privacy-railed mean?"` on the icon button.
- The `<TooltipContent>` should be the string above, no markdown, no
  bold, no extra spans.
- Placement: in the modal, the icon goes right after the first
  "Privacy-railed" in the body's first paragraph. In Settings, the icon
  goes right after the first "Privacy-railed" in the toggle's helper
  text (whichever of ON/OFF copy is rendering — both helper strings
  contain "Privacy-railed").
- Reduced-motion: the existing `Tooltip` primitive already honors
  `prefers-reduced-motion`; no extra work.

### Replacement strings — modal (`apps/brain_web/src/components/dialogs/cross-domain-modal.tsx`)

#### Line 182 — modal title

**Current:**

```tsx
title="Including a private domain in this chat"
```

**Replacement:**

```tsx
title="Including a Privacy-railed domain in this chat"
```

**Rationale:** swaps the deprecated phrase for the locked term while
keeping the sentence shape — the title still says "you're about to
include something that's normally excluded," which is the title's job.
Capital P signals it's a defined term the user can hover for a
definition. The `(?)` glyph follows this string in the rendered title
or, more graceful, follows the **first** occurrence inside the body
paragraph (line 233 area) so the title stays a clean line.
**Recommendation:** put the tooltip icon on the body's first occurrence
(see line-233 entry below), not the title — titles read better
unadorned.

#### Line 233 — body, first paragraph closer

**Current:**

```tsx
<BoldSlugs slugs={railedSlugsInScope} /> {isOrAre} kept private
by default — notes there only show up when you explicitly
include {itOrThem}, like you just did.
```

**Replacement:**

```tsx
<BoldSlugs slugs={railedSlugsInScope} /> {isOrAre} Privacy-railed
{/* glossary tooltip icon goes here — see "Glossary tooltip" section above */}
— notes there only show up when you explicitly include {itOrThem},
like you just did.
```

**Concrete render with example scope `[research, personal]`:**

> You picked **personal** alongside **research** for this chat's scope.
> **personal** is Privacy-railed (?) — notes there only show up when
> you explicitly include it, like you just did.

**Rationale:** "is/are Privacy-railed" reads naturally as a predicate
("X is Privacy-railed") and parallels how the badge in Settings reads.
"Kept private by default" was carrying two ideas at once (the term
*and* the default-exclusion behavior); we move "default exclusion" into
the tooltip definition so the prose stays compact. The em-dash clause
that follows still explains the user-visible consequence ("only show
up when you explicitly include them") for readers who don't open the
tooltip — the sentence works at both depths. `{isOrAre}` and
`<BoldSlugs />` are preserved verbatim.

#### Line 240 — body, second paragraph

**Current:**

```tsx
If you&apos;d rather keep this chat single-domain, head back
and adjust the scope. Otherwise continue, and brain will treat
the included private notes as in-scope for this chat. See{" "}
<strong>BRAIN.md</strong> for how scope and privacy work in
your vault.
```

**Replacement:**

```tsx
If you&apos;d rather keep this chat single-domain, head back
and adjust the scope. Otherwise continue, and brain will treat
the included Privacy-railed notes as in-scope for this chat. See{" "}
<strong>BRAIN.md</strong> for how scope and privacy work in
your vault.
```

**Rationale:** "Privacy-railed notes" mirrors "Privacy-railed domain"
from the title and reinforces the term on second mention without
re-defining it. The trailing "how scope and privacy work in your vault"
keeps the broader concept word "privacy" — that's general English about
what users are protecting, not the specific term, so it stays. JSX
`{" "}` and `<strong>BRAIN.md</strong>` are preserved verbatim.

### Replacement strings — Settings (`apps/brain_web/src/components/settings/panel-domains.tsx`)

#### Line 186 — success-toast `msg` (toggle ON branch)

**Current:**

```tsx
? "brain will confirm before mixing private domains."
```

**Replacement:**

```tsx
? "brain will confirm before mixing Privacy-railed domains."
```

**Rationale:** one-line toast — no room for the tooltip; the term alone
is enough at this point because the user has just toggled the setting
that governs Privacy-railed behavior, so they've already seen the term
in the surrounding helper text. Sentence shape unchanged.

#### Line 232 — toggle helper text (ON branch)

**Current:**

```tsx
? "Before starting a chat that mixes a private domain (like personal) with another domain, brain will ask you to confirm."
```

**Replacement:**

```tsx
? "Before starting a chat that mixes a Privacy-railed domain (like personal) with another domain, brain will ask you to confirm."
```

**Rationale:** preserves the parenthetical example (the user sees the
literal slug `personal`, which makes the abstract term concrete on
first encounter). This is the **first** occurrence of "Privacy-railed"
in the Settings panel helper text — the `(?)` glossary icon goes
immediately after the word "Privacy-railed" in this string (or, if the
toggle is OFF, in the line-233 string — whichever is rendered).

#### Line 233 — toggle helper text (OFF branch)

**Current:**

```tsx
: "The confirmation is off. Mixed-scope chats including private domains will start without a prompt. Turn this back on if you want the check back."}
```

**Replacement:**

```tsx
: "The confirmation is off. Mixed-scope chats including Privacy-railed domains will start without a prompt. Turn this back on if you want the check back."}
```

**Rationale:** straight swap. This branch shows when the warning is
suppressed; the user already knows what Privacy-railed means by the
time they've toggled the switch off, so the prose stays the same shape.
The `(?)` icon still anchors to the first occurrence of "Privacy-railed"
in whichever branch is currently rendered.

### Note: line 183 (modal `description` prop) — already aligned

```tsx
description="Confirm that this chat may include notes from a privacy-railed domain."
```

This string already uses "privacy-railed" (lowercase). Plan 15 D4 names
"Privacy-railed" as the proper-noun-phrase capitalization for
user-facing prose. **Recommendation:** capitalize the P here for
consistency with the title and body — change to:

```tsx
description="Confirm that this chat may include notes from a Privacy-railed domain."
```

This is a 1-character editorial fix, not part of the six strings in
scope, but worth folding into the same diff so the modal's own three
strings (title, description, body) all capitalize the term identically.
Flag for brain-frontend-engineer.

### Acceptance criteria (for brain-frontend-engineer)

1. **All six in-scope strings replaced** with the exact replacement
   text above, JSX expressions (`{isOrAre}`, `{itOrThem}`,
   `<BoldSlugs />`, `{" "}`, `<strong>BRAIN.md</strong>`) preserved
   character-for-character.
2. **Glossary tooltip wired up** at the first occurrence of
   "Privacy-railed" in *both* surfaces:
   - Cross-domain modal: in the body paragraph, after "Privacy-railed"
     on the line 233 replacement.
   - Settings panel: in the toggle helper paragraph, after
     "Privacy-railed" on whichever of line 232 / 233 is currently
     rendered.
3. **Tooltip icon is a focusable `<button>`** with
   `aria-label="What does Privacy-railed mean?"` and `type="button"`.
4. **Tooltip content** is exactly: `Domains marked Privacy-railed never
   appear in chats unless you include them yourself.` (no surrounding
   bold, no markdown).
5. **Reuses existing `Tooltip` primitive** from
   `apps/brain_web/src/components/ui/tooltip.tsx` (already imported in
   `cross-domain-modal.tsx`); no new component file.
6. **Grep proves no regressions** — running
   `grep -niE 'private domain|kept private|private notes' apps/brain_web/src/components/dialogs/cross-domain-modal.tsx apps/brain_web/src/components/settings/panel-domains.tsx`
   returns zero matches after the edit.
7. **(Editorial bonus, recommended):** capital-P in the modal's
   `description` on line 183 so all three modal strings agree on
   capitalization.
8. **axe-core a11y check passes.** Adding the tooltip introduces a new
   focusable button per surface; the existing axe gate must remain
   green. The button has an accessible name via `aria-label`, the
   tooltip content is associated via the existing `Tooltip` primitive's
   `aria-describedby` wiring (same pattern the modal already uses for
   "Don't show this again" on lines 193–203 of the modal).

### Self-review pass (Plan 15 D4 alignment)

- **Single locked term across both surfaces.** Modal title, modal body
  (×2), Settings success toast, and Settings helper text (ON + OFF) all
  read "Privacy-railed". The badge in `panel-domains.tsx` already says
  "Privacy-railed". ✅
- **First-encounter accessibility.** A user who's never seen the term
  hits the `(?)` tooltip on first occurrence in either surface and gets
  a one-sentence definition that names the term and the behavior. ✅
- **No remaining "private" jargon in the six in-scope strings.** Every
  replacement above swaps the deprecated phrase. ✅
- **Calm voice preserved.** Replacement strings are the same length
  and shape as the originals; nothing got more alarming or more
  technical. ✅
- **JSX preserved.** Every `{...}` expression and child component
  reference in the original line is reproduced verbatim in the
  replacement. ✅
- **Tooltip char count under 90.** 85 chars. ✅
