// v3 dialogs — File-to-wiki, Fork, Rename-domain
//
// Kept separate from dialogs.jsx so the base file stays focused on
// system-level overlays (budget wall, offline, typed-confirm, etc).
//
// All three are content-surfacing dialogs triggered by message-level
// or browse-level actions. They reuse the base <Modal /> from dialogs.jsx.

/* ---------- File-to-wiki (M2) ----------
   Promote a piece of chat output into a curated vault note.
   Flow:
     chat msg → "File to wiki" →
       pick note type (source | concept | person | synthesis) →
       resolve target path + collision →
       preview with frontmatter →
       approve → adds a patch + chips the source message as "filed to …".
*/

const FileToWikiDialog = ({ payload, onClose, onConfirm }) => {
  const msg = payload?.msg;
  const thread = payload?.thread;

  // ---- infer a sensible default from the message content ----
  const inferredTitle = React.useMemo(() => {
    if (!msg?.body) return "untitled-note";
    // First sentence, kebab-cased, max ~6 words.
    const first = msg.body.replace(/\[\[|\]\]|\*\*|\*|`/g, "").split(/[.\n]/)[0];
    return first.trim().toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .split(/\s+/).slice(0, 6).join("-")
      .slice(0, 48) || "untitled-note";
  }, [msg]);

  const [type, setType] = React.useState("synthesis");
  const [domain, setDomain] = React.useState(thread?.domain || "work");
  const [slug, setSlug] = React.useState(inferredTitle);
  const [expanded, setExpanded] = React.useState(false);

  React.useEffect(() => { setSlug(inferredTitle); }, [inferredTitle]);

  const subdirByType = {
    source:    "sources",
    concept:   "concepts",
    person:    "people",
    synthesis: "synthesis",
  };

  const today = new Date().toISOString().slice(0, 10);
  const datedSlug = type === "source" || type === "synthesis" ? `${today}-${slug}` : slug;
  const fullPath = `${domain}/${subdirByType[type]}/${datedSlug}.md`;

  // Fake collision heuristic — in the real product this hits the vault indexer.
  const collision = slug.includes("silent-buyer") || slug.includes("deal-stall-patterns");

  const frontmatter = React.useMemo(() => {
    const lines = [
      "---",
      `type: ${type}`,
      `domain: ${domain}`,
      `created: ${today}`,
      `source_thread: ${thread?.id || "t-new"}`,
      type === "source" ? "tags: [call, ingest]" : "tags: []",
      "---",
    ];
    return lines.join("\n");
  }, [type, domain, thread, today]);

  // Shortened, markdown-ish preview of the message body.
  const previewBody = React.useMemo(() => {
    const raw = (msg?.body || "").trim();
    return raw.split(/\n\n/).slice(0, 3).join("\n\n");
  }, [msg]);

  const canSave = slug.trim().length > 0 && !collision;

  return (
    <Modal
      open={!!payload}
      onClose={onClose}
      eyebrow="File to wiki"
      title="Promote this reply into a vault note."
      width={760}
      footer={
        <>
          <div className="dim" style={{ fontSize: 12, marginRight: "auto", fontFamily: "var(--mono)" }}>
            Will be staged as a patch · you'll still approve the final file.
          </div>
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn primary"
            disabled={!canSave}
            onClick={() => onConfirm({ type, domain, slug, path: fullPath, body: previewBody, frontmatter })}
          >
            <Icon name="check" size={13} /> Stage patch
          </button>
        </>
      }
    >
      <div className="ftw-wrap">
        {/* note type */}
        <div className="ftw-row">
          <label>Note type</label>
          <div className="ftw-type-picker">
            {[
              { k: "source",    n: "Source",    d: "raw, dated intake" },
              { k: "concept",   n: "Concept",   d: "reusable idea" },
              { k: "person",    n: "Person",    d: "rolling profile" },
              { k: "synthesis", n: "Synthesis", d: "cross-links others" },
            ].map(t => (
              <button
                key={t.k}
                className={`ftw-type ${type === t.k ? "on" : ""}`}
                onClick={() => setType(t.k)}
              >
                <div className="t-name">{t.n}</div>
                <div className="t-desc">{t.d}</div>
              </button>
            ))}
          </div>
        </div>

        {/* path builder */}
        <div className="ftw-row">
          <label>Path</label>
          <div>
            <div className="ftw-path-input">
              <select value={domain} onChange={(e) => setDomain(e.target.value)}>
                {window.SEED.domains.map(d => <option key={d.id} value={d.id}>{d.id}</option>)}
              </select>
              <span className="ftw-slash">/</span>
              <span className="ftw-slash" style={{ color: "var(--text-muted)" }}>{subdirByType[type]}</span>
              <span className="ftw-slash">/</span>
              {(type === "source" || type === "synthesis") && (
                <span className="ftw-slash" style={{ color: "var(--text-muted)" }}>{today}-</span>
              )}
              <input
                value={slug}
                onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
                spellCheck={false}
                autoFocus
              />
              <span className="ftw-ext">.md</span>
            </div>
            {collision && (
              <div className="ftw-collision">
                <Icon name="alert" size={12} />
                A note already exists at this path. Change the slug or it'll be staged as an append.
              </div>
            )}
          </div>
        </div>

        {/* preview */}
        <div className="ftw-row">
          <label>Preview</label>
          <div className="ftw-preview">
            <div className="ftw-preview-head">
              <Icon name="file" size={11} />
              <span className="tag">{fullPath}</span>
              <div style={{ flex: 1 }} />
              <span>{(previewBody.length + frontmatter.length)} chars · new file</span>
            </div>
            <div className={`ftw-preview-body ${expanded ? "" : "collapsed"}`}>
              <span className="frontmatter">{frontmatter}</span>
              <h2>{slug.replace(/-/g, " ")}</h2>
              {previewBody.split(/\n\n/).map((p, i) => (
                <p key={i}>{p}</p>
              ))}
            </div>
            <div className="ftw-preview-foot">
              <span>brain will wrap the body with frontmatter and any [[wikilinks]] you left in the reply.</span>
              <button onClick={() => setExpanded(v => !v)}>{expanded ? "collapse" : "show more"}</button>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
};


/* ---------- Fork from here (M5) ----------
   Branch off a specific turn into a new thread. Users pick:
     - new mode (often they fork *because* they want to switch modes)
     - new scope (default: current)
     - whether to carry the prior context (summary vs. full)
     - a title hint
*/

const ForkDialog = ({ payload, onClose, onConfirm }) => {
  const thread = payload?.thread;
  const turnIndex = payload?.turnIndex ?? 0;
  const msg = payload?.msg;

  // Find the user message that triggered this turn (prior message if we got the brain reply).
  const transcript = window.SEED.transcript || [];
  const userTurn = msg?.role === "user"
    ? msg
    : (turnIndex > 0 ? transcript[turnIndex - 1] : transcript[0]);
  const brainTurn = msg?.role === "brain" ? msg : transcript[turnIndex];

  const [mode, setMode] = React.useState(thread?.mode || "ask");
  const [scope, setScope] = React.useState(thread?.scope || ["work"]);
  const [carry, setCarry] = React.useState("summary"); // summary | full | none
  const [title, setTitle] = React.useState(thread ? `${thread.title} — fork` : "New fork");

  const truncate = (s, n) => (s || "").length > n ? (s || "").slice(0, n) + "…" : (s || "");

  return (
    <Modal
      open={!!payload}
      onClose={onClose}
      eyebrow={`Fork from turn ${turnIndex + 1}`}
      title="Start a fresh thread from this point."
      width={620}
      footer={
        <>
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn primary"
            onClick={() => onConfirm({ mode, scope, carry, title, fromThread: thread?.id, fromTurn: turnIndex })}
          >
            <Icon name="fork" size={13} /> Fork thread
          </button>
        </>
      }
    >
      <div className="fork-wrap">
        {/* source summary */}
        <div className="fork-source">
          <div className="fs-eyebrow">Forking from</div>
          {userTurn && (
            <div className="fs-user">{truncate(userTurn.body, 180)}</div>
          )}
          {brainTurn && brainTurn.role === "brain" && (
            <div className="fs-reply">{truncate(brainTurn.body, 140)}</div>
          )}
          <div className="fs-turn">
            <Icon name="chat" size={11} />
            <span>{thread?.title || "current thread"}</span>
            <span>·</span>
            <span>turn {turnIndex + 1}</span>
          </div>
        </div>

        {/* controls */}
        <div className="fork-grid">
          <label>New mode</label>
          <div className="seg">
            <button className={mode === "ask" ? "on" : ""} onClick={() => setMode("ask")}>Ask</button>
            <button className={mode === "brainstorm" ? "on" : ""} onClick={() => setMode("brainstorm")}>Brainstorm</button>
            <button className={mode === "draft" ? "on" : ""} onClick={() => setMode("draft")}>Draft</button>
          </div>

          <label>Scope</label>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {window.SEED.domains.map(d => (
              <button
                key={d.id}
                className={`chip dom-${d.id} ${scope.includes(d.id) ? "" : "off"}`}
                style={{ height: 24, opacity: scope.includes(d.id) ? 1 : 0.45, cursor: "pointer" }}
                onClick={() => setScope(s => s.includes(d.id) ? s.filter(x => x !== d.id) : [...s, d.id])}
              >
                <span className="dot" style={{ width: 6, height: 6, borderRadius: 999, background: `var(--dom-${d.id})` }} />
                {d.name}
              </button>
            ))}
          </div>

          <label>Carry context</label>
          <div className="seg">
            <button className={carry === "summary" ? "on" : ""} onClick={() => setCarry("summary")}>Summary</button>
            <button className={carry === "full" ? "on" : ""} onClick={() => setCarry("full")}>Full thread</button>
            <button className={carry === "none" ? "on" : ""} onClick={() => setCarry("none")}>Fresh start</button>
          </div>

          <label>Title</label>
          <input
            className="input-field"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="brain will name it after your first message if empty"
          />
        </div>

        <div className="dim" style={{ fontSize: 12, lineHeight: 1.55, display: "flex", gap: 8 }}>
          <Icon name="info" size={12} />
          <span>
            {carry === "summary" && "A ~400-token recap of the source thread is prepended — cheap, keeps continuity."}
            {carry === "full" && "Full transcript is copied. Costs more on the first turn; perfect recall."}
            {carry === "none" && "Clean slate — only the mode + scope carry over."}
          </span>
        </div>
      </div>
    </Modal>
  );
};


/* ---------- Rename domain (C2) ----------
   Destructive-adjacent: renaming a domain rewrites paths across the vault
   and (optionally) rewrites `domain: …` frontmatter. Warn clearly;
   gate behind a real button, not a typed-confirm — this is recoverable
   via git/backup.
*/

const RenameDomainDialog = ({ payload, onClose, onConfirm }) => {
  const domain = payload?.domain;
  const [newId, setNewId] = React.useState(domain?.id || "");
  const [rewriteFrontmatter, setRewriteFrontmatter] = React.useState(true);
  React.useEffect(() => { setNewId(domain?.id || ""); }, [domain]);
  const valid = /^[a-z][a-z0-9-]{1,24}$/.test(newId) && newId !== domain?.id;

  return (
    <Modal
      open={!!payload}
      onClose={onClose}
      eyebrow={`Rename domain · ${domain?.name || ""}`}
      title="Rename and rewrite references."
      width={520}
      footer={
        <>
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn primary"
            disabled={!valid}
            onClick={() => onConfirm({ from: domain.id, to: newId, rewriteFrontmatter })}
          >
            <Icon name="check" size={13} /> Rename domain
          </button>
        </>
      }
    >
      <div className="setup-field" style={{ marginTop: 0 }}>
        <label>New slug</label>
        <input
          className="input-field"
          value={newId}
          onChange={(e) => setNewId(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))}
          autoFocus
          spellCheck={false}
          style={{ fontFamily: "var(--mono)" }}
        />
        <div className="hint">Lowercase, hyphen-separated. Will become the folder name.</div>
      </div>

      <label style={{ display: "flex", alignItems: "flex-start", gap: 10, marginTop: 16, cursor: "pointer" }}>
        <input
          type="checkbox"
          checked={rewriteFrontmatter}
          onChange={(e) => setRewriteFrontmatter(e.target.checked)}
          style={{ marginTop: 3 }}
        />
        <div>
          <div style={{ fontSize: 13 }}>Also rewrite <code style={{ fontFamily: "var(--mono)", fontSize: 12 }}>domain:</code> frontmatter</div>
          <div className="dim" style={{ fontSize: 12, marginTop: 2 }}>
            Every note's YAML header gets updated to match the new slug.
          </div>
        </div>
      </label>

      <div className="rename-warn">
        <Icon name="alert" size={14} />
        <div>
          This rewrites <strong>{domain?.count || 0}</strong> files and every <code>[[wikilink]]</code> that
          points into <code>{domain?.id}/</code>. brain stages it as one big patch — you still
          approve it before anything touches disk. It's reversible via your backup.
        </div>
      </div>
    </Modal>
  );
};


Object.assign(window, {
  FileToWikiDialog,
  ForkDialog,
  RenameDomainDialog,
});
