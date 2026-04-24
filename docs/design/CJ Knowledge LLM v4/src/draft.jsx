// Draft-mode components:
//   - DraftEmpty  — shown in transcript when draft is active but no doc open
//   - DocPickerDialog — modal for picking a vault doc (or new scratch)
//   - DocPanel — sidebar that renders the active doc with pending edits highlighted
//
// These are triggered from ChatScreen when state.mode === "draft".

// Seed list of vault docs the picker offers. In the real product this is a
// fuzzy-indexed query against the vault; here we hand-curate a list drawn
// from the existing SEED paths so the examples feel coherent with the rest
// of the prototype.
const VAULT_DOCS = [
  { path: "research/notes/fisher-ury-interests.md",                 domain: "research", updated: "3d ago",   words: 1420 },
  { path: "research/synthesis/silent-buyer-synthesis.md",           domain: "research", updated: "1w ago",   words: 980 },
  { path: "research/concepts/conflict-avoidance-tells.md",          domain: "research", updated: "2w ago",   words: 640 },
  { path: "work/synthesis/2026-04-deal-stall-patterns.md",          domain: "work",     updated: "2d ago",   words: 1120 },
  { path: "work/sources/2026-04-18-acme-q2-call.md",                domain: "work",     updated: "4d ago",   words: 2210 },
  { path: "work/people/helios-champion.md",                         domain: "work",     updated: "1w ago",   words: 420 },
  { path: "personal/journal/2026-04-reading-log.md",                domain: "personal", updated: "today",    words: 310 },
  { path: "personal/notes/compounding-curiosity.md",                domain: "personal", updated: "2w ago",   words: 580 },
];


/* ---------- Draft empty state ---------- */

const DraftEmpty = ({ onPick, onNewDoc }) => (
  <div className="draft-empty">
    <div className="de-icon">
      <Icon name="edit" size={28} />
    </div>
    <h2>Pick a document to draft on.</h2>
    <p>
      Draft mode works against one open doc. brain proposes inline edits you review
      before they touch disk — wikilinks and frontmatter stay intact.
    </p>
    <div className="de-actions">
      <button className="btn primary" onClick={onPick}>
        <Icon name="file" size={13} /> Open from vault
      </button>
      <button className="btn ghost" onClick={onNewDoc}>
        <Icon name="plus" size={13} /> New blank doc
      </button>
    </div>
  </div>
);


/* ---------- Doc picker dialog ---------- */

const DocPickerDialog = ({ open, onClose, onPick, onNewBlank }) => {
  const [q, setQ] = React.useState("");
  const matches = React.useMemo(() => {
    const n = q.trim().toLowerCase();
    if (!n) return VAULT_DOCS;
    return VAULT_DOCS.filter(d =>
      d.path.toLowerCase().includes(n) || d.domain.includes(n)
    );
  }, [q]);

  return (
    <Modal
      open={open}
      onClose={onClose}
      eyebrow="Draft mode"
      title="Open a document."
      width={620}
    >
      <div className="docpick-search">
        <Icon name="search" size={13} />
        <input
          placeholder="filter by path or domain… (try 'synthesis' or 'helios')"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          autoFocus
        />
        <span className="dim" style={{ fontSize: 11, fontFamily: "var(--mono)" }}>
          {matches.length}
        </span>
      </div>

      <div className="docpick-list">
        {matches.length === 0 && (
          <div style={{ padding: "30px 14px", textAlign: "center", color: "var(--text-dim)", fontSize: 13 }}>
            No docs match <code style={{ fontFamily: "var(--mono)" }}>{q}</code>.
          </div>
        )}
        {matches.map((d, i) => {
          const parts = d.path.split("/");
          const slug = parts[parts.length - 1];
          const dir = parts.slice(0, -1).join("/") + "/";
          return (
            <div key={i} className="docpick-row" onClick={() => onPick(d)}>
              <Icon name="file" size={13} />
              <div className="dp-path">
                <span className="dim">{dir}</span>{slug}
              </div>
              <span className={`chip dom-${d.domain} dp-domain`} style={{ height: 18 }}>
                {d.domain}
              </span>
              <span className="dp-meta">{d.words}w · {d.updated}</span>
            </div>
          );
        })}
      </div>

      <div className="docpick-divider">or</div>

      <div className="docpick-new" onClick={onNewBlank}>
        <div className="dp-icon"><Icon name="plus" size={16} /></div>
        <div className="dp-body">
          <div className="dp-title">Start a blank scratch doc</div>
          <div className="dp-sub">lands at <code>work/scratch/{new Date().toISOString().slice(0,10)}-untitled.md</code> on first save</div>
        </div>
        <Icon name="caret" size={12} style={{ transform: "rotate(-90deg)", color: "var(--text-dim)" }} />
      </div>
    </Modal>
  );
};


/* ---------- Active-doc panel ---------- */

const DocPanel = ({ doc, onClose, onChangeDoc, onApplyEdits, onRejectEdits }) => {
  const [view, setView] = React.useState("reading"); // reading | outline
  if (!doc) return null;
  const hasPending = (doc.pendingEdits || []).length > 0;

  // Word-count is a quick derivation — good enough for display.
  const words = (doc.body || "").trim().split(/\s+/).filter(Boolean).length;

  // Render body with pending edits inline. The demo uses sentinel tokens
  // ⟦+text⟧ for an insertion and ⟦-text⟧ for a deletion that brain staged;
  // we split on those and wrap them.
  const renderBodyWithEdits = (body) => {
    const nodes = [];
    const re = /⟦([+-])([^⟧]+)⟧/g;
    let last = 0, m, key = 0;
    while ((m = re.exec(body)) !== null) {
      if (m.index > last) nodes.push(body.slice(last, m.index));
      if (m[1] === "+") {
        nodes.push(<span key={`+${key++}`} className="pending-edit">{m[2]}</span>);
      } else {
        nodes.push(<del key={`-${key++}`}>{m[2]}</del>);
      }
      last = m.index + m[0].length;
    }
    if (last < body.length) nodes.push(body.slice(last));
    return nodes;
  };

  const paragraphs = (doc.body || "").split(/\n\n+/).filter(Boolean);

  return (
    <div className="doc-panel">
      <div className="doc-panel-head">
        <button className="iconbtn" title="Close" onClick={onClose}><Icon name="x" size={13} /></button>
        <div className="doc-panel-path" title="Change document" onClick={onChangeDoc}>
          <Icon name="file" size={12} />
          <span className="dim">{doc.path.split("/").slice(0, -1).join("/")}/</span>
          <span>{doc.path.split("/").pop()}</span>
          <Icon name="caret" size={10} style={{ opacity: 0.5 }} />
        </div>
        <button className="iconbtn" title="Open in Obsidian"><Icon name="link" size={13} /></button>
      </div>

      {hasPending && (
        <div className="doc-panel-diff-banner">
          <Icon name="diff" size={14} style={{ color: "var(--tt-sage)" }} />
          <span className="lead">{doc.pendingEdits.length} pending edit{doc.pendingEdits.length === 1 ? "" : "s"}</span>
          <span className="msg">Review inline, then apply to the file.</span>
          <div className="actions">
            <button className="btn ghost tiny" onClick={onRejectEdits}>Discard</button>
            <button className="btn primary tiny" onClick={onApplyEdits}>Apply</button>
          </div>
        </div>
      )}

      <div className="doc-panel-toolbar">
        <div className="seg">
          <button className={view === "reading" ? "on" : ""} onClick={() => setView("reading")}>Reading</button>
          <button className={view === "outline" ? "on" : ""} onClick={() => setView("outline")}>Outline</button>
        </div>
        <div style={{ flex: 1 }} />
        <span style={{ fontFamily: "var(--mono)" }}>{words}w</span>
      </div>

      <div className="doc-panel-body">
        {doc.frontmatter && <span className="frontmatter">{doc.frontmatter}</span>}
        {view === "reading" && paragraphs.map((p, i) => {
          if (p.startsWith("# "))  return <h1 key={i}>{p.slice(2)}</h1>;
          if (p.startsWith("## ")) return <h2 key={i}>{p.slice(3)}</h2>;
          return <p key={i}>{renderBodyWithEdits(p)}</p>;
        })}
        {view === "outline" && (
          <ul style={{ paddingLeft: 18, fontFamily: "var(--sans)", fontSize: 13 }}>
            {paragraphs.filter(p => p.startsWith("#")).map((p, i) => (
              <li key={i} style={{ margin: "6px 0", color: p.startsWith("## ") ? "var(--text-dim)" : "var(--text)" }}>
                {p.replace(/^#+\s*/, "")}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="doc-panel-foot">
        <span className="stats">saved · {doc.path.split("/").pop()}</span>
        <button className="btn ghost tiny" onClick={onChangeDoc}>
          <Icon name="file" size={11} /> Change doc
        </button>
      </div>
    </div>
  );
};


/* ---------- Helper: build a sample doc body with pending edits ----------
   Used when the user picks a vault doc — we seed a couple of inline suggested
   edits so Draft mode shows off its diffing UI without needing a round-trip.
*/

const makeSampleDoc = (entry) => {
  const today = new Date().toISOString().slice(0, 10);
  const frontmatter = [
    "---",
    `type: note`,
    `domain: ${entry.domain}`,
    `updated: ${entry.updated === "today" ? today : entry.updated}`,
    "tags: [draft]",
    "---",
  ].join("\n");

  // Per-doc sample bodies — just enough to feel real. ⟦+…⟧ = pending insertion;
  // ⟦-…⟧ = pending deletion. These render highlighted in DocPanel.
  const SAMPLES = {
    "research/notes/fisher-ury-interests.md": `# Positions vs. interests

The single most useful idea from *Getting to Yes* is the split between a **position** — what someone says they want — and an **interest** — why they want it. ⟦+A position is bargaining surface; an interest is where the real deal lives.⟧

## How to surface interests

Ask *why* three times without making it feel like an interrogation. When a counterparty restates your position back to you without movement, the hidden interest is ⟦-almost always price⟧⟦+usually risk, not price⟧ — even when they say it's price.

## Cross-refs

See [[silent-buyer-synthesis]] for how this plays out when the buyer goes quiet rather than counter-offering.`,
    "research/synthesis/silent-buyer-synthesis.md": `# The silent-buyer synthesis

Silence is not the absence of an answer. It's a compressed bundle of four common objections — risk, authority, fit, and timing — that the buyer can't yet untangle into a single question.

## Three tells

1. They paraphrase your pricing position accurately but never counter.
2. A new stakeholder appears mid-cycle and the champion's cadence drops.
3. ⟦+The follow-up windows get softer — "let's regroup" instead of a booked next step.⟧

## What works

Surface the compressed objections one at a time. Don't ask "are we still on track?" — ask "what's the one thing that would have to be true for this to move forward?"`,
    "work/synthesis/2026-04-deal-stall-patterns.md": `# April 2026 — deal-stall patterns

Three recurring patterns across the four stalled deals this month.

## 1 — Loop-in stall

In 3 of 7 stalled deals (ACME, Helios, Vestige) the champion went quiet right after introducing a new required stakeholder. ⟦+This is the clearest match to [[conflict-avoidance-tells]] we've logged this quarter.⟧

## 2 — Restating without movement

Polaris and Helios-renewal both had buyers paraphrasing the pricing position accurately but never counter-offering. Per [[fisher-ury-interests]], that signals ⟦-a price objection⟧⟦+a hidden risk interest⟧.

## 3 — Agenda softening

Where calls ended with "let's regroup" rather than a booked next step, follow-up response rate dropped from 72% → 19%.`,
  };

  const body = SAMPLES[entry.path] || `# ${entry.path.split("/").pop().replace(/\.md$/, "").replace(/-/g, " ")}

This is a scratch view of **${entry.path}**. In the real product, Draft mode renders the actual file contents here.

⟦+brain can stage inline edits that highlight on this surface — you review before anything touches disk.⟧`;

  // Pull out "pending edits" as a derived list for the diff banner.
  const re = /⟦([+-])([^⟧]+)⟧/g;
  const pendingEdits = [];
  let m;
  while ((m = re.exec(body)) !== null) {
    pendingEdits.push({ op: m[1] === "+" ? "insert" : "delete", text: m[2] });
  }

  return {
    path: entry.path,
    domain: entry.domain,
    frontmatter,
    body,
    pendingEdits,
  };
};

// Blank scratch doc for "new doc" path.
const makeScratchDoc = (domain = "work") => {
  const today = new Date().toISOString().slice(0, 10);
  return {
    path: `${domain}/scratch/${today}-untitled.md`,
    domain,
    frontmatter: `---\ntype: scratch\ndomain: ${domain}\ncreated: ${today}\n---`,
    body: `# Untitled

Start drafting — brain will stage suggested edits as you go. Nothing hits disk until you approve.`,
    pendingEdits: [],
  };
};

Object.assign(window, {
  DraftEmpty,
  DocPickerDialog,
  DocPanel,
  makeSampleDoc,
  makeScratchDoc,
  VAULT_DOCS,
});
