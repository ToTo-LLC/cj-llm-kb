"use client";

import * as React from "react";
import { AlertTriangle, Check, FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { Modal } from "./modal";
import {
  listDomains,
  proposeNote,
} from "@/lib/api/tools";
import {
  buildVaultPath,
  checkCollision,
  kebabCoerce,
  SUBDIR_BY_TYPE,
  type VaultNoteType,
} from "@/lib/vault/path-builder";
import { useSystemStore } from "@/lib/state/system-store";
import type { FileToWikiResult } from "@/lib/state/dialogs-store";

/**
 * FileToWikiDialog (Plan 07 Task 20).
 *
 * Promotes a chat message into a curated vault note. Flow per design-delta
 * §M2 + v3 design:
 *
 *   1. Pick a note type — Source / Concept / Entity / Synthesis.
 *      (Delta-v2 V1: "Person" is renamed "Entity" to match the vault's
 *      ``entities/`` subdir convention.)
 *   2. Build a path — domain selector defaults to the thread's primary
 *      domain (passed via ``defaultDomain``), subdir is derived from type,
 *      source + synthesis types get a ``YYYY-MM-DD-`` prefix, and the slug
 *      is kebab-coerced on every keystroke.
 *   3. Collision detection — ``checkCollision(path)`` hits
 *      ``brain_read_note`` with a 404-tolerant wrapper; hitting a note
 *      surfaces an inline "already exists" warning.
 *   4. Preview — rendered frontmatter + first 3 paragraphs of the message
 *      body so the user sees exactly what will be staged.
 *   5. Submit — stages the note via ``brain_propose_note`` and toasts
 *      success.
 *
 * Sources primary domain note: the parent (``msg-actions``) passes the
 * current thread id and a ``defaultDomain`` prop. The chat-store doesn't
 * track a "thread's primary domain" field yet (threads API isn't wired
 * into the frontend — see Task 25 sweep); until then the default falls
 * back to "work" so the dialog always renders a sensible path.
 */

const NOTE_TYPES: ReadonlyArray<{
  kind: VaultNoteType;
  name: string;
  desc: string;
}> = [
  { kind: "source", name: "Source", desc: "raw, dated intake" },
  { kind: "concept", name: "Concept", desc: "reusable idea" },
  { kind: "entity", name: "Entity", desc: "rolling profile" },
  { kind: "synthesis", name: "Synthesis", desc: "cross-links others" },
];

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function inferSlugFromBody(body: string): string {
  const first = body.replace(/\[\[|\]\]|\*\*|\*|`/g, "").split(/[.\n]/)[0] ?? "";
  const words = first
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 6);
  const slug = words.join("-").slice(0, 48);
  return slug || "untitled-note";
}

function buildFrontmatter(opts: {
  type: VaultNoteType;
  domain: string;
  today: string;
  threadId: string;
}): string {
  const { type, domain, today, threadId } = opts;
  const tagsLine = type === "source" ? "tags: [call, ingest]" : "tags: []";
  return [
    "---",
    `type: ${type}`,
    `domain: ${domain}`,
    `created: ${today}`,
    `source_thread: ${threadId}`,
    tagsLine,
    "---",
  ].join("\n");
}

function previewBody(msgBody: string): string {
  return (msgBody || "").trim().split(/\n\n/).slice(0, 3).join("\n\n");
}

export interface FileToWikiDialogProps {
  kind: "file-to-wiki";
  msg: { body: string; threadId: string };
  threadId?: string;
  /** Pre-selected domain. Falls back to first listed allowed domain. */
  defaultDomain?: string;
  onConfirm?: (p: FileToWikiResult) => void;
  onClose: () => void;
}

export function FileToWikiDialog({
  msg,
  threadId,
  defaultDomain,
  onConfirm,
  onClose,
}: FileToWikiDialogProps) {
  const today = React.useMemo(todayStr, []);
  const inferredSlug = React.useMemo(() => inferSlugFromBody(msg.body), [msg.body]);
  const resolvedThreadId = threadId ?? msg.threadId ?? "t-new";

  const [type, setType] = React.useState<VaultNoteType>("synthesis");
  const [domains, setDomains] = React.useState<string[]>([]);
  const [domain, setDomain] = React.useState<string>(defaultDomain ?? "work");
  const [slug, setSlug] = React.useState<string>(inferredSlug);
  const [collision, setCollision] = React.useState<boolean>(false);
  const [submitting, setSubmitting] = React.useState<boolean>(false);

  // Load domains from the tool (scope-filtered server-side).
  React.useEffect(() => {
    let cancelled = false;
    listDomains()
      .then((resp) => {
        if (cancelled) return;
        const list = resp.data?.domains ?? [];
        setDomains(list);
        // If caller didn't pin a default, snap to the first allowed domain.
        if (!defaultDomain && list.length > 0 && !list.includes(domain)) {
          setDomain(list[0]!);
        }
      })
      .catch(() => {
        // Don't block the dialog on a failed list — user can still type.
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const path = React.useMemo(
    () => buildVaultPath(domain, type, slug || "untitled-note"),
    [domain, type, slug],
  );

  // Collision detection — debounced via effect cancel flag. The tool call
  // is idempotent + cheap, and the user only types a few chars here.
  React.useEffect(() => {
    let cancelled = false;
    setCollision(false);
    if (!slug.trim()) return;
    checkCollision(path)
      .then((hit) => {
        if (!cancelled) setCollision(hit);
      })
      .catch(() => {
        if (!cancelled) setCollision(false);
      });
    return () => {
      cancelled = true;
    };
  }, [path, slug]);

  const frontmatter = React.useMemo(
    () =>
      buildFrontmatter({
        type,
        domain,
        today,
        threadId: resolvedThreadId,
      }),
    [type, domain, today, resolvedThreadId],
  );

  const body = React.useMemo(() => previewBody(msg.body), [msg.body]);

  const content = React.useMemo(() => {
    const heading = slug.replace(/-/g, " ");
    return `${frontmatter}\n\n# ${heading}\n\n${body}\n`;
  }, [frontmatter, body, slug]);

  const canSave = slug.trim().length > 0 && !submitting;

  const handleSubmit = React.useCallback(async () => {
    if (!canSave) return;
    setSubmitting(true);
    try {
      await proposeNote({
        path,
        content,
        reason: `File to wiki · ${type}`,
      });
      useSystemStore.getState().pushToast({
        lead: "Note staged.",
        msg: `Review in Pending before it touches ${path}.`,
        variant: "success",
      });
      onConfirm?.({ path, domain, type, frontmatter, body });
      onClose();
    } catch (err) {
      useSystemStore.getState().pushToast({
        lead: "Couldn't stage note.",
        msg: err instanceof Error ? err.message : "Unknown error.",
        variant: "danger",
      });
    } finally {
      setSubmitting(false);
    }
  }, [canSave, path, content, type, domain, frontmatter, body, onConfirm, onClose]);

  const subdir = SUBDIR_BY_TYPE[type];
  const showDatePrefix = type === "source" || type === "synthesis";

  return (
    <Modal
      open
      onClose={onClose}
      eyebrow="File to wiki"
      title="Promote this reply into a vault note."
      description="Pick a note type, tune the path, and stage the patch for review."
      width={760}
      footer={
        <>
          <span className="mr-auto text-xs text-muted-foreground">
            Will be staged as a patch · you&apos;ll still approve the final file.
          </span>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!canSave} className="gap-2">
            <Check className="h-3.5 w-3.5" /> Stage patch
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Note type picker */}
        <div>
          <label className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground">
            Note type
          </label>
          <div
            className="grid grid-cols-4 gap-2"
            role="radiogroup"
            aria-label="Note type"
          >
            {NOTE_TYPES.map((t) => {
              const active = type === t.kind;
              return (
                <button
                  key={t.kind}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => setType(t.kind)}
                  className={cn(
                    "flex flex-col items-start gap-0.5 rounded-md border px-3 py-2 text-left transition-colors",
                    active
                      ? "border-primary bg-primary/10 text-foreground"
                      : "border-border bg-transparent text-muted-foreground hover:border-primary/60 hover:text-foreground",
                  )}
                >
                  <span className="text-sm font-medium">{t.name}</span>
                  <span className="text-[11px] text-muted-foreground">
                    {t.desc}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Path builder */}
        <div>
          <label
            className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground"
            htmlFor="ftw-slug"
          >
            Path
          </label>
          <div
            data-testid="ftw-path"
            className="flex items-center gap-1 rounded-md border border-border bg-muted/40 px-2 py-1.5 font-mono text-xs"
          >
            <select
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              className="bg-transparent text-xs focus:outline-none"
              aria-label="Domain"
            >
              {(domains.length > 0 ? domains : [domain]).map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <span className="text-muted-foreground">/</span>
            <span className="text-muted-foreground">{subdir}</span>
            <span className="text-muted-foreground">/</span>
            {showDatePrefix ? (
              <span className="text-muted-foreground">{today}-</span>
            ) : null}
            <Input
              id="ftw-slug"
              aria-label="Slug"
              value={slug}
              onChange={(e) => setSlug(kebabCoerce(e.target.value))}
              className="h-6 flex-1 border-0 bg-transparent px-0 font-mono text-xs focus-visible:ring-0 focus-visible:ring-offset-0"
              spellCheck={false}
            />
            <span className="text-muted-foreground">.md</span>
          </div>
          {collision ? (
            <div
              data-testid="ftw-collision"
              className="mt-1.5 flex items-center gap-1 text-xs text-amber-500"
            >
              <AlertTriangle className="h-3 w-3" />
              <span>
                A note already exists at this path. Change the slug or it&apos;ll
                be staged as an append.
              </span>
            </div>
          ) : null}
        </div>

        {/* Preview */}
        <div>
          <label className="mb-1.5 block text-xs uppercase tracking-wider text-muted-foreground">
            Preview
          </label>
          <div
            data-testid="ftw-preview"
            className="rounded-md border border-border bg-muted/40 p-3 text-xs"
          >
            <div className="mb-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <FileText className="h-3 w-3" />
              <span className="font-mono">{path}</span>
              <span className="flex-1" />
              <span>
                {(content.length).toLocaleString()} chars · new file
              </span>
            </div>
            <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-muted-foreground">
              {frontmatter}
            </pre>
            <h4 className="mt-2 text-sm font-medium">
              {slug.replace(/-/g, " ")}
            </h4>
            <div className="mt-1 space-y-2 text-[12px] leading-relaxed">
              {body.split(/\n\n/).map((p, i) => (
                <p key={i}>{p}</p>
              ))}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
}
