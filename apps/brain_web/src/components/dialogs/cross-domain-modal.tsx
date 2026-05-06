"use client";

import * as React from "react";
import { HelpCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Modal } from "./modal";

/**
 * Plan 15 Task 5 (D4 jargon alignment): glossary tooltip rendered
 * immediately after the first occurrence of "Privacy-railed" on the
 * modal body and on the Settings → Domains toggle helper text. The
 * tooltip text is the same canonical 85-char string in both surfaces
 * so the user only learns the term once.
 *
 * Trigger MUST be a focusable ``<button type="button">`` (not a bare
 * span) — keyboard users need to focus and dismiss it, and icon-only
 * buttons without an accessible name fail axe-core. ``aria-label`` is
 * required.
 *
 * Exported so ``panel-domains.tsx`` can reuse the same component
 * verbatim — guarantees the canonical text never drifts between the
 * two surfaces.
 */
export function PrivacyRailedGlossaryTooltip(): React.ReactElement {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="What does Privacy-railed mean?"
          className="ml-0.5 inline-flex items-center align-baseline text-muted-foreground hover:text-foreground focus:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ring,_currentColor)] rounded-sm"
        >
          <HelpCircle className="h-4 w-4" aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent>
        Domains marked Privacy-railed never appear in chats unless you include them yourself.
      </TooltipContent>
    </Tooltip>
  );
}

/**
 * CrossDomainModal — Plan 12 Task 9 + Task 7 microcopy.
 *
 * One-time confirmation surfaced when a chat / draft / brainstorm session's
 * scope contains ≥2 domains AND ≥1 of those domains is in
 * ``Config.privacy_railed``. Trigger gate (D7) lives on the calling site;
 * the acknowledgment flag (``Config.cross_domain_warning_acknowledged``,
 * D8) suppresses future fires when the user opts in via the
 * "Don't show this again" checkbox.
 *
 * Microcopy is locked by ``docs/design/cross-domain-modal/microcopy.md``
 * (Task 7). Text changes go through that doc, not inline edits — the
 * copy is the implementer's brief, not invention space.
 *
 * Visual pattern reuses ``Modal`` (eyebrow + title + body + footer slot)
 * so this dialog inherits the shadcn/Radix focus-trap, Esc-to-close,
 * backdrop-click, and a11y plumbing without re-implementing them.
 *
 * Variable substitution rules (Task 7 microcopy.md § "Variable
 * substitution"):
 *
 *   - ``{railed_slugs_joined}`` = scope ∩ privacy_railed, joined with the
 *     join rule below.
 *   - ``{other_slugs_joined}`` = scope − privacy_railed, joined with the
 *     join rule.
 *   - ``{is_or_are}`` = "is" if 1 railed slug, else "are".
 *   - ``{it_or_them}`` = "it" if 1 railed slug, else "them".
 *
 *   Join rule: 1 → bare slug; 2 → "A and B"; ≥3 → "A, B and C".
 *   Slugs render in **bold**, not in code/mono — they're domain names,
 *   not paths.
 */

export interface CrossDomainModalProps {
  /** Whether the modal is open. The caller controls visibility because
   *  the trigger gate (scope + railed slugs + ack flag) lives on the
   *  call site, not in the dialog itself. */
  open: boolean;
  /** Full scope being finalized for the new session. Used to compute
   *  the "other slugs" half of the body. */
  scope: string[];
  /** Subset of ``scope`` that's in ``Config.privacy_railed``. The
   *  caller computes this so the dialog stays decoupled from the
   *  config-fetch path. */
  railedSlugsInScope: string[];
  /** Fired when the user clicks "Continue". ``alsoAcknowledge`` is the
   *  state of the "Don't show this again" checkbox at click time. The
   *  caller is responsible for both: (a) persisting the
   *  acknowledgment when ``true``, and (b) finalizing the session. */
  onContinue: (alsoAcknowledge: boolean) => void;
  /** Fired when the user clicks "Back to scope" or dismisses via Esc /
   *  backdrop click. Caller returns the user to the scope picker; no
   *  session is created and no acknowledgment is persisted regardless
   *  of the checkbox state (matches Task 7 microcopy semantics). */
  onCancel: () => void;
}

/**
 * Pure trigger gate — exported so call sites and tests share one
 * source of truth for "should the cross-domain modal fire?". Returns
 * ``true`` iff scope has ≥2 domains AND ≥1 of them is in the
 * railed-slug list AND the user hasn't already acknowledged.
 *
 * Single-domain railed access does NOT fire (the explicit slug
 * inclusion is itself the consent — D7). Pure cross-domain without
 * any railed slug does NOT fire either.
 */
export function shouldFireCrossDomainModal(
  scope: readonly string[],
  privacyRailed: readonly string[],
  acknowledged: boolean,
): boolean {
  if (acknowledged) return false;
  if (scope.length < 2) return false;
  return scope.some((slug) => privacyRailed.includes(slug));
}

/** Compute the railed subset of a scope. Helper for trigger sites. */
export function computeRailedSlugsInScope(
  scope: readonly string[],
  privacyRailed: readonly string[],
): string[] {
  return scope.filter((slug) => privacyRailed.includes(slug));
}

/** Join slugs per the Task 7 microcopy rule:
 *    - 0 → "" (caller should never reach this — guard upstream)
 *    - 1 → bare slug
 *    - 2 → "A and B"
 *    - ≥3 → "A, B and C" (Oxford-comma-free; no comma before "and")
 */
export function joinSlugs(slugs: readonly string[]): string {
  if (slugs.length === 0) return "";
  if (slugs.length === 1) return slugs[0]!;
  if (slugs.length === 2) return `${slugs[0]} and ${slugs[1]}`;
  const head = slugs.slice(0, -1).join(", ");
  return `${head} and ${slugs[slugs.length - 1]}`;
}

/** Render a list of slug names as bolded inline spans separated per
 *  ``joinSlugs``. Used inside the body prose so each slug name stays
 *  visually anchored without forcing a per-count branch. */
function BoldSlugs({ slugs }: { slugs: readonly string[] }): React.ReactNode {
  if (slugs.length === 0) return null;
  if (slugs.length === 1) return <strong>{slugs[0]}</strong>;
  if (slugs.length === 2) {
    return (
      <>
        <strong>{slugs[0]}</strong> and <strong>{slugs[1]}</strong>
      </>
    );
  }
  // ≥3: "A, B and C" — interleave with ", " and finally " and ".
  const head = slugs.slice(0, -1);
  const tail = slugs[slugs.length - 1]!;
  return (
    <>
      {head.map((slug, idx) => (
        <React.Fragment key={slug}>
          <strong>{slug}</strong>
          {idx < head.length - 1 ? ", " : null}
        </React.Fragment>
      ))}
      {" and "}
      <strong>{tail}</strong>
    </>
  );
}

export function CrossDomainModal({
  open,
  scope,
  railedSlugsInScope,
  onContinue,
  onCancel,
}: CrossDomainModalProps): React.ReactElement {
  const [dontShowAgain, setDontShowAgain] = React.useState(false);
  const continueButtonRef = React.useRef<HTMLButtonElement | null>(null);

  // Reset the checkbox state every time the modal re-opens so a stale
  // "checked" doesn't leak across separate trigger fires. The user has
  // to opt in fresh each time. Only flips on the open→true transition;
  // closing the modal preserves the state for the synchronous parent
  // re-render that may immediately follow.
  React.useEffect(() => {
    if (open) setDontShowAgain(false);
  }, [open]);

  // Plan 15 D4: the body now contains a focusable tooltip trigger
  // (``PrivacyRailedGlossaryTooltip``) before the footer's buttons.
  // Radix's default ``onOpenAutoFocus`` would land the dialog's initial
  // focus on that tooltip trigger, which (a) immediately opens the
  // tooltip and (b) makes Escape dismiss the tooltip via Radix's
  // ``DismissableLayer`` instead of dismissing the dialog itself.
  // Override: prevent the default focus and route initial focus to the
  // Continue button — also a UX win for keyboard users (Enter advances).
  const handleOpenAutoFocus = React.useCallback((event: Event) => {
    event.preventDefault();
    continueButtonRef.current?.focus();
  }, []);

  // Other slugs = scope − railed (computed for the body's "alongside"
  // clause). Stable order: matches scope order minus railed entries.
  const otherSlugs = React.useMemo(
    () => scope.filter((slug) => !railedSlugsInScope.includes(slug)),
    [scope, railedSlugsInScope],
  );

  const isOrAre = railedSlugsInScope.length === 1 ? "is" : "are";
  const itOrThem = railedSlugsInScope.length === 1 ? "it" : "them";

  const handleContinue = () => {
    onContinue(dontShowAgain);
  };

  return (
    <TooltipProvider delayDuration={300}>
      <Modal
        open={open}
        onClose={onCancel}
        eyebrow="Confirm scope"
        title="Including a Privacy-railed domain in this chat"
        description="Confirm that this chat may include notes from a Privacy-railed domain."
        width={520}
        onOpenAutoFocus={handleOpenAutoFocus}
        footer={
          <div className="flex w-full items-center justify-between gap-3">
            <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
              <Checkbox
                id="cross-domain-dont-show-again"
                checked={dontShowAgain}
                onCheckedChange={(v) => setDontShowAgain(Boolean(v))}
                data-testid="cross-domain-dont-show-checkbox"
                aria-describedby="cross-domain-dont-show-tooltip"
              />
              <Tooltip>
                <TooltipTrigger asChild>
                  <span className="cursor-help">Don&apos;t show this again</span>
                </TooltipTrigger>
                <TooltipContent id="cross-domain-dont-show-tooltip">
                  Skip this check for future chats. You can turn it back
                  on under Settings → Domains.
                </TooltipContent>
              </Tooltip>
            </label>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                onClick={onCancel}
                data-testid="cross-domain-back-button"
              >
                Back to scope
              </Button>
              <Button
                ref={continueButtonRef}
                variant="default"
                onClick={handleContinue}
                data-testid="cross-domain-continue-button"
              >
                Continue
              </Button>
            </div>
          </div>
        }
      >
        <p className="mb-3 text-foreground">
          You picked <BoldSlugs slugs={railedSlugsInScope} />
          {otherSlugs.length > 0 ? (
            <>
              {" alongside "}
              <BoldSlugs slugs={otherSlugs} />
            </>
          ) : null}
          {" for this chat's scope. "}
          <BoldSlugs slugs={railedSlugsInScope} /> {isOrAre} Privacy-railed
          <PrivacyRailedGlossaryTooltip />
          {" "}— notes there only show up when you explicitly
          include {itOrThem}, like you just did.
        </p>
        <p className="text-foreground">
          If you&apos;d rather keep this chat single-domain, head back
          and adjust the scope. Otherwise continue, and brain will treat
          the included Privacy-railed notes as in-scope for this chat. See{" "}
          <strong>BRAIN.md</strong> for how scope and privacy work in
          your vault.
        </p>
      </Modal>
    </TooltipProvider>
  );
}
