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
