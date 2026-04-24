// Dialogs, error states, system-level overlays
// - Modal (base)
// - RejectReasonDialog
// - EditApprovePanel (inline diff editor)
// - TypedConfirmDialog ("type DELETE to confirm")
// - OfflineBanner + connection indicator
// - BudgetWall (blocking modal when daily cap hit)
// - RateLimitToast
// - DropOverlay (drag-to-attach)
// - MidTurnToast (stream issues)

/* ---------- base Modal ---------- */

const Modal = ({ open, onClose, title, eyebrow, width = 520, children, footer }) => {
  if (!open) return null;
  return (
    <div className="modal-backdrop" onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card" style={{ width }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            {eyebrow && <div className="eyebrow" style={{ marginBottom: 4 }}>{eyebrow}</div>}
            <h2>{title}</h2>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <Icon name="x" size={14} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
};

/* ---------- Reject reason ---------- */

const RejectReasonDialog = ({ patch, onClose, onConfirm }) => {
  const [reason, setReason] = React.useState("");
  const presets = [
    "Wrong domain",
    "Already noted elsewhere",
    "Source is unreliable",
    "Too speculative",
    "Formatting is off",
  ];
  return (
    <Modal
      open={!!patch}
      onClose={onClose}
      eyebrow={`Reject patch · ${patch?.target || ""}`}
      title="Tell brain why."
      width={540}
      footer={
        <>
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn danger" onClick={() => onConfirm(reason)}>
            <Icon name="x" size={13} /> Reject patch
          </button>
        </>
      }
    >
      <p className="muted" style={{ marginBottom: 14 }}>
        Optional, but the next turn uses your reason as feedback. One sentence is plenty.
      </p>
      <div className="chip-row" style={{ marginBottom: 10 }}>
        {presets.map(p => (
          <button key={p} className={`chip-btn ${reason === p ? "on" : ""}`} onClick={() => setReason(p)}>
            {p}
          </button>
        ))}
      </div>
      <textarea
        className="input-field"
        style={{ height: 110, padding: 12, resize: "none", width: "100%" }}
        placeholder="Or in your own words…"
        value={reason}
        onChange={e => setReason(e.target.value)}
        autoFocus
      />
      <div className="dim" style={{ fontSize: 12, marginTop: 8, display: "flex", alignItems: "center", gap: 8 }}>
        <Icon name="info" size={11} /> Your reason is stored locally in the thread, not sent anywhere.
      </div>
    </Modal>
  );
};

/* ---------- Edit-then-approve ---------- */

const EditApproveDialog = ({ patch, onClose, onConfirm }) => {
  const [draft, setDraft] = React.useState(patch?.diff?.after || "");
  React.useEffect(() => { setDraft(patch?.diff?.after || ""); }, [patch]);
  return (
    <Modal
      open={!!patch}
      onClose={onClose}
      eyebrow={`Edit · ${patch?.target || ""}`}
      title="Tweak the note, then approve."
      width={760}
      footer={
        <>
          <div className="dim" style={{ fontSize: 12, marginRight: "auto" }}>
            Saves to vault on approve · {draft.length} chars
          </div>
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" onClick={() => onConfirm(draft)}>
            <Icon name="check" size={13} /> Save & approve
          </button>
        </>
      }
    >
      <div className="edit-approve-wrap">
        <div className="ea-col">
          <div className="ea-label">Current (empty — new file)</div>
          <pre className="ea-pre dim-pre">{patch?.diff?.before || "(file doesn't exist yet)"}</pre>
        </div>
        <div className="ea-col">
          <div className="ea-label">Your edit</div>
          <textarea
            className="ea-editor"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
          />
        </div>
      </div>
    </Modal>
  );
};

/* ---------- Typed-confirm (destructive) ---------- */

const TypedConfirmDialog = ({ open, onClose, onConfirm, title, eyebrow, word = "DELETE", body, danger = true }) => {
  const [text, setText] = React.useState("");
  React.useEffect(() => { if (!open) setText(""); }, [open]);
  const ok = text === word;
  return (
    <Modal
      open={open}
      onClose={onClose}
      eyebrow={eyebrow}
      title={title}
      width={460}
      footer={
        <>
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button className={`btn ${danger ? "danger" : "primary"}`} disabled={!ok} onClick={onConfirm}>
            {danger ? "Delete permanently" : "Confirm"}
          </button>
        </>
      }
    >
      <div style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.55, marginBottom: 14 }}>
        {body}
      </div>
      <label className="eyebrow" style={{ display: "block", marginBottom: 6 }}>
        Type <code style={{ color: "var(--tt-orange)", background: "transparent" }}>{word}</code> to confirm
      </label>
      <input
        className="input-field"
        value={text}
        onChange={e => setText(e.target.value)}
        placeholder={word}
        autoFocus
        style={{ letterSpacing: "0.05em" }}
      />
    </Modal>
  );
};

/* ---------- Offline banner ---------- */

const OfflineBanner = ({ state = "offline" }) => {
  // state: 'offline' | 'reconnecting' | null
  if (!state) return null;
  return (
    <div className={`system-banner ${state}`}>
      <div className="sb-dot" />
      <div className="sb-body">
        {state === "offline" && (
          <>
            <strong>brain is offline.</strong>
            <span>Your last turn didn't send. Reads from vault still work.</span>
          </>
        )}
        {state === "reconnecting" && (
          <>
            <strong>Reconnecting…</strong>
            <span>Dropped connection to the local runtime. Queued turns will resend.</span>
          </>
        )}
      </div>
      <button className="btn ghost tiny">Retry now</button>
    </div>
  );
};

/* ---------- Budget wall ---------- */

const BudgetWall = ({ open, costToday, budget, onRaise, onClose }) => (
  <Modal
    open={open}
    onClose={onClose}
    eyebrow="Daily spend cap hit"
    title={`$${costToday?.toFixed(2)} used of $${budget?.toFixed(2)}.`}
    width={540}
    footer={
      <>
        <button className="btn ghost" onClick={onClose}>Wait it out</button>
        <button className="btn primary" onClick={onRaise}>Raise cap by $5 for today</button>
      </>
    }
  >
    <p className="muted" style={{ marginBottom: 12 }}>
      brain paused all LLM calls because you hit the hard cap you set. Everything you've already
      written is safe. You can raise the cap (one-off, resets tomorrow), wait for the clock to roll
      over, or switch to a cheaper model.
    </p>
    <div className="budget-wall-break">
      <div>
        <div className="eyebrow">This session</div>
        <ul className="mini-breakdown">
          <li><span>Ask turns</span><span>$1.04</span></li>
          <li><span>Brainstorm turns</span><span>$0.38</span></li>
          <li><span>Draft turns</span><span>$0.92</span></li>
          <li><span>Ingest</span><span>$0.48</span></li>
        </ul>
      </div>
      <div>
        <div className="eyebrow">Heaviest turn</div>
        <div className="heavy-turn">
          <div className="ht-title">"Cross-link April stall-pattern calls"</div>
          <div className="ht-meta">12 tool calls · 48k tokens · $0.31</div>
        </div>
        <div className="eyebrow" style={{ marginTop: 14 }}>Switch model</div>
        <div className="model-row">
          <div className="mr-opt on">Claude Sonnet 4.5 <span className="dim">· current</span></div>
          <div className="mr-opt">Haiku 4.5 <span className="dim">· ~8× cheaper</span></div>
        </div>
      </div>
    </div>
  </Modal>
);

/* ---------- Connection pip (for topbar) ---------- */

const ConnectionIndicator = ({ state }) => {
  // 'ok' | 'reconnecting' | 'offline'
  if (state === "ok" || !state) return null;
  return (
    <div className={`conn-pip ${state}`} title={state}>
      <span className="pip-dot" />
      <span>{state === "reconnecting" ? "reconnecting…" : "offline"}</span>
    </div>
  );
};

/* ---------- Drop-to-attach overlay ---------- */

const DropOverlay = ({ visible }) => {
  if (!visible) return null;
  return (
    <div className="drop-overlay">
      <div className="do-card">
        <div className="do-orb" />
        <h2>Drop to attach</h2>
        <p>brain will ingest and summarize before filing.</p>
        <div className="do-chips">
          <span className="chip">pdf</span>
          <span className="chip">txt · md</span>
          <span className="chip">eml</span>
          <span className="chip">url</span>
        </div>
      </div>
    </div>
  );
};

/* ---------- Mid-turn issue toast ---------- */

const MidTurnToast = ({ kind, onDismiss, onRetry }) => {
  if (!kind) return null;
  const iconName = (name) => ({ clock: "alert" }[name] || name);
  const copy = {
    "rate-limit": {
      lead: "Rate limit.",
      msg: "Anthropic slowed us down. Retrying in 8s — or retry now.",
      icon: "alert",
      tone: "warn",
    },
    "context-full": {
      lead: "Context full.",
      msg: "Compact the thread to keep going, or start a fresh one.",
      icon: "layers",
      tone: "warn",
    },
    "tool-failed": {
      lead: "Tool failed.",
      msg: "brain_propose_note couldn't write — the vault path isn't reachable.",
      icon: "x",
      tone: "danger",
    },
    "invalid-state-turn": {
      lead: "Finish this turn first.",
      msg: "Wait for it to complete, or cancel to start fresh.",
      icon: "clock",
      tone: "warn",
    },
    "invalid-state-mode": {
      lead: "Can't switch mid-turn.",
      msg: "Mode change takes effect on the next turn.",
      icon: "alert",
      tone: "warn",
    },
  }[kind];
  if (!copy) return null;
  return (
    <div className={`mid-turn-toast ${copy.tone}`}>
      <Icon name={iconName(copy.icon)} size={14} />
      <div>
        <div className="mtt-lead">{copy.lead}</div>
        <div className="mtt-msg">{copy.msg}</div>
      </div>
      <div style={{ flex: 1 }} />
      {onRetry && <button className="btn ghost tiny" onClick={onRetry}>Retry</button>}
      <button className="btn ghost tiny" onClick={onDismiss}>Dismiss</button>
    </div>
  );
};

/* ---------- Host: system overlays ----------
   Single mount point for app-level dialogs. Reads from state + dispatches.
*/

const SystemOverlays = ({ state, dispatch }) => {
  const sysState = state.sys || {};
  const closeSys = (k) => dispatch({ type: "sys_close", k });
  return (
    <>
      {sysState.connection && sysState.connection !== "ok" && (
        <div className="system-banner-wrap">
          <OfflineBanner state={sysState.connection} />
        </div>
      )}

      <BudgetWall
        open={!!sysState.budgetWall}
        costToday={state.costToday}
        budget={state.budget}
        onRaise={() => { dispatch({ type: "raise_budget" }); }}
        onClose={() => closeSys("budgetWall")}
      />

      <TypedConfirmDialog
        open={!!sysState.typedConfirm}
        word={sysState.typedConfirm?.word || "DELETE"}
        title={sysState.typedConfirm?.title}
        eyebrow={sysState.typedConfirm?.eyebrow}
        body={sysState.typedConfirm?.body}
        onClose={() => closeSys("typedConfirm")}
        onConfirm={() => { sysState.typedConfirm?.onConfirm?.(); closeSys("typedConfirm"); }}
      />

      <RejectReasonDialog
        patch={sysState.rejectPatch || null}
        onClose={() => closeSys("rejectPatch")}
        onConfirm={(reason) => {
          dispatch({ type: "reject", id: sysState.rejectPatch.id, reason });
          closeSys("rejectPatch");
        }}
      />

      <EditApproveDialog
        patch={sysState.editPatch || null}
        onClose={() => closeSys("editPatch")}
        onConfirm={(draft) => {
          dispatch({ type: "approve", id: sysState.editPatch.id, editedBody: draft });
          closeSys("editPatch");
        }}
      />

      {sysState.midTurn && (
        <MidTurnToast
          kind={sysState.midTurn}
          onDismiss={() => closeSys("midTurn")}
          onRetry={() => { closeSys("midTurn"); dispatch({ type: "toast", t: { lead: "Retried.", msg: "Resuming turn.", icon: "undo" } }); }}
        />
      )}

      <DropOverlay visible={state.draggingFile} />

      <FileToWikiDialog
        payload={sysState.fileToWiki || null}
        onClose={() => closeSys("fileToWiki")}
        onConfirm={(result) => {
          // Stage a patch for the new note.
          const patch = {
            id: "p-" + Date.now(),
            tool: "brain_propose_note",
            target: result.path,
            reason: `Filed from chat (${result.type}).`,
            createdAt: "just now",
            domain: result.domain,
            isNew: true,
            diff: { before: "", after: result.frontmatter + "\n\n" + result.body },
          };
          dispatch({ type: "add_patch", patch });
          dispatch({ type: "toast", t: { lead: "Filed.", msg: `Staged at ${result.path}`, icon: "flag" } });
          closeSys("fileToWiki");
        }}
      />

      <ForkDialog
        payload={sysState.forkDialog || null}
        onClose={() => closeSys("forkDialog")}
        onConfirm={(opts) => {
          dispatch({ type: "toast", t: { lead: "Forked.", msg: `New ${opts.mode} thread · ${opts.carry} context.`, icon: "fork" } });
          closeSys("forkDialog");
        }}
      />

      <RenameDomainDialog
        payload={sysState.renameDomain || null}
        onClose={() => closeSys("renameDomain")}
        onConfirm={(r) => {
          dispatch({ type: "toast", t: { lead: "Rename staged.", msg: `${r.from} → ${r.to} · review the patch.`, icon: "diff" } });
          closeSys("renameDomain");
        }}
      />
    </>
  );
};

Object.assign(window, {
  Modal,
  RejectReasonDialog,
  EditApproveDialog,
  TypedConfirmDialog,
  OfflineBanner,
  BudgetWall,
  ConnectionIndicator,
  DropOverlay,
  MidTurnToast,
  SystemOverlays,
});
