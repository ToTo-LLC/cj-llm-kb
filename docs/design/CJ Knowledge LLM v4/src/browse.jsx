// Enhanced Browse screen — file tree, reader, search, edit mode, wikilink hover, Obsidian link

const FIXTURE_NOTES = {
  "conflict-avoidance-tells": {
    domain: "research", folder: "concepts",
    path: "research/concepts/conflict-avoidance-tells.md",
    title: "Conflict-Avoidance Tells",
    fm: { type: "concept", domain: "research", created: "2026-03-14",
          links: ["fisher-ury-interests", "silent-buyer-synthesis"] },
    readTime: "3 min read", modified: "2d ago",
    body: `When a counterparty is avoiding a conflict they can't articulate, they emit a small set of structural tells before the conversation breaks down. Catching these early is the difference between a deal that stalls and one that re-opens.

## The pattern
Avoidance shows up as **shape-shifting**, not as hostility. The counterparty widens the room, reframes urgency downward, or paraphrases your position back to you without movement. Each of these moves is doing the same thing: importing ambiguity into a place where a decision is trying to form.

## Signals, in order of arrival
- **Sudden attendee expansion.** A new required stakeholder appears late. The decision is being outsourced to a room that can fail to decide.
- **Urgency reframing.** "Let's regroup next month" replaces "let's book the next call." See [[silent-buyer-synthesis]].
- **Accurate paraphrase, no movement.** Your position is restated correctly; no counter-offer follows. A hidden risk interest is in play.

## See also
- [[fisher-ury-interests]]
- [[future-work]] — hasn't been written yet.`,
    rawSource: `---
type: concept
domain: research
created: 2026-03-14
links: [[fisher-ury-interests]], [[silent-buyer-synthesis]]
---

# Conflict-Avoidance Tells

When a counterparty is avoiding a conflict they can't articulate, they emit a small set of structural tells before the conversation breaks down. Catching these early is the difference between a deal that stalls and one that re-opens.

## The pattern
Avoidance shows up as **shape-shifting**, not as hostility. The counterparty widens the room, reframes urgency downward, or paraphrases your position back to you without movement. Each of these moves is doing the same thing: importing ambiguity into a place where a decision is trying to form.

## Signals, in order of arrival
- **Sudden attendee expansion.** A new required stakeholder appears late. The decision is being outsourced to a room that can fail to decide.
- **Urgency reframing.** "Let's regroup next month" replaces "let's book the next call." See [[silent-buyer-synthesis]].
- **Accurate paraphrase, no movement.** Your position is restated correctly; no counter-offer follows. A hidden risk interest is in play.

## See also
- [[fisher-ury-interests]]
- [[future-work]] — hasn't been written yet.`,
  },
  "fisher-ury-interests": {
    domain: "research", folder: "notes",
    path: "research/notes/fisher-ury-interests.md",
    title: "Fisher & Ury — Positions vs. Interests",
    fm: { type: "note", domain: "research", created: "2026-02-09", links: ["conflict-avoidance-tells"] },
    readTime: "2 min read", modified: "6d ago",
    body: "The whole Fisher & Ury frame is that positions (what they say they want) are downstream of interests (why they want it). When a counterparty restates your position accurately without moving, the hidden interest is usually risk.",
  },
};

const WIKILINK_SET = new Set(["conflict-avoidance-tells","concession-pairs","tactical-empathy","fisher-ury-interests","voss-never-split","silent-buyer-synthesis","helios-account","2026-04-18-acme-q2-call"]);

const BROKEN_WIKILINKS = new Set(["future-work"]);

const renderMd = (md, onHover, onLeave) => {
  const lines = md.split("\n");
  const out = [];
  let list = null;
  const flushList = () => { if (list) { out.push(<ul key={`ul-${out.length}`}>{list}</ul>); list = null; } };
  const inline = (s) => {
    const nodes = []; let last = 0; let k = 0;
    const re = /(\[\[[^\]]+\]\]|\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
    let m;
    while ((m = re.exec(s))) {
      if (m.index > last) nodes.push(s.slice(last, m.index));
      const t = m[0];
      if (t.startsWith("[[")) {
        const label = t.slice(2,-2);
        const broken = BROKEN_WIKILINKS.has(label);
        nodes.push(<a key={k++} className={`wikilink ${broken?"broken":""}`} href="#"
          onMouseEnter={(e)=>!broken && onHover(label, e.currentTarget)}
          onMouseLeave={onLeave}>{label}</a>);
      } else if (t.startsWith("**")) nodes.push(<strong key={k++}>{t.slice(2,-2)}</strong>);
      else if (t.startsWith("`")) nodes.push(<code key={k++}>{t.slice(1,-1)}</code>);
      else if (t.startsWith("*")) nodes.push(<em key={k++}>{t.slice(1,-1)}</em>);
      last = m.index + t.length;
    }
    if (last < s.length) nodes.push(s.slice(last));
    return nodes;
  };
  lines.forEach((line, i) => {
    if (line.startsWith("## ")) { flushList(); out.push(<h2 key={i}>{inline(line.slice(3))}</h2>); }
    else if (line.startsWith("# ")) { flushList(); out.push(<h1 key={i}>{inline(line.slice(2))}</h1>); }
    else if (line.startsWith("- ")) { list = list || []; list.push(<li key={i}>{inline(line.slice(2))}</li>); }
    else if (line.trim() === "") { flushList(); }
    else { flushList(); out.push(<p key={i}>{inline(line)}</p>); }
  });
  flushList();
  return out;
};

const SearchResults = ({ query, onPick, onClose }) => {
  const hits = [
    { path: "research/concepts/conflict-avoidance-tells.md", score: 0.94, snip: "…widening of the attendee list; vague agreement without commitment; reframing urgency downward…", slug: "conflict-avoidance-tells" },
    { path: "research/synthesis/silent-buyer-synthesis.md", score: 0.88, snip: "…silence itself is a signal — it compresses four objections into one ambiguous blocker…", slug: "silent-buyer-synthesis" },
    { path: "work/sources/2026-04-18-acme-q2-call.md", score: 0.81, snip: "…champion went quiet after legal raised a red-line question…", slug: "2026-04-18-acme-q2-call" },
    { path: "research/notes/fisher-ury-interests.md", score: 0.76, snip: "…hidden risk interest when the counterparty restates the position without moving…", slug: "fisher-ury-interests" },
  ].filter(h => !query || h.path.toLowerCase().includes(query.toLowerCase()) || h.snip.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="search-overlay">
      <div className="search-panel">
        <div className="search-head">
          <Icon name="search" size={14} />
          <input autoFocus className="search-input" placeholder="Search the vault…" value={query} onChange={e => onPick(null, e.target.value)} />
          <span className="dim" style={{ fontSize: 11 }}>{hits.length} results</span>
          <button className="iconbtn" onClick={onClose}><Icon name="close" size={12} /></button>
        </div>
        <div className="search-body">
          {hits.length === 0 && <div className="search-empty">No matches. Try different words.</div>}
          {hits.map((h, i) => (
            <div key={i} className="search-hit" onClick={() => onPick(h.slug)}>
              <div className="sh-top">
                <span className="sh-score">{h.score.toFixed(2)}</span>
                <span className="sh-path mono">{h.path}</span>
              </div>
              <div className="sh-snip">{h.snip.split(new RegExp(`(${query})`,"i")).map((p,j) => j%2 ? <mark key={j}>{p}</mark> : <span key={j}>{p}</span>)}</div>
            </div>
          ))}
          <div className="search-shortcuts">
            <span><kbd>↑</kbd><kbd>↓</kbd> navigate</span>
            <span><kbd>↵</kbd> open</span>
            <span><kbd>Esc</kbd> close</span>
          </div>
        </div>
      </div>
    </div>
  );
};

const WikilinkHover = ({ slug, anchor, onClose }) => {
  const note = FIXTURE_NOTES[slug];
  if (!note || !anchor) return null;
  const rect = anchor.getBoundingClientRect();
  return (
    <div className="wiki-hover" style={{ top: rect.bottom + 6, left: rect.left }}>
      <div className="wh-path mono">{note.path}</div>
      <div className="wh-title">{note.title}</div>
      <div className="wh-body">{note.body.split("\n\n")[0].slice(0, 220)}…</div>
      <div className="wh-foot">
        <span className={`chip dom-${note.domain}`} style={{ height: 18, fontSize: 10 }}>{note.domain}</span>
        <span className="spacer" />
        <span className="muted" style={{ fontSize: 11 }}>↵ to open</span>
      </div>
    </div>
  );
};

const BrowseScreen = ({ state, dispatch }) => {
  const [active, setActive] = React.useState("conflict-avoidance-tells");
  const [editing, setEditing] = React.useState(false);
  const [searchOpen, setSearchOpen] = React.useState(false);
  const [searchQ, setSearchQ] = React.useState("");
  const [hover, setHover] = React.useState({ slug: null, anchor: null });
  const [editBuf, setEditBuf] = React.useState("");

  const note = FIXTURE_NOTES[active] || FIXTURE_NOTES["conflict-avoidance-tells"];

  React.useEffect(() => {
    setEditBuf(note.rawSource || note.body);
    setEditing(false);
  }, [active]);

  React.useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); setSearchOpen(true); }
      if (e.key === "Escape") { setSearchOpen(false); setHover({ slug: null, anchor: null }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="browse-screen">
      <div className="file-tree">
        <div className="tree-search" onClick={() => setSearchOpen(true)}>
          <Icon name="search" size={12} />
          <span>Search vault…</span>
          <span className="kbd-hint"><kbd>⌘</kbd><kbd>K</kbd></span>
        </div>
        <div className="tree-group">
          <div className="tree-head"><span className="dot" style={{ background: "var(--dom-research)" }} />research</div>
          <div className="tree-folder"><Icon name="folder" size={12} /> concepts <span className="dim" style={{ marginLeft: "auto", fontSize: 10 }}>8</span></div>
          <div className={`tree-node ${active==="conflict-avoidance-tells"?"active":""}`} onClick={()=>setActive("conflict-avoidance-tells")}><Icon name="file" size={11} /> conflict-avoidance-tells</div>
          <div className="tree-node"><Icon name="file" size={11} /> concession-pairs</div>
          <div className="tree-node"><Icon name="file" size={11} /> tactical-empathy</div>
          <div className="tree-folder"><Icon name="folder" size={12} /> notes</div>
          <div className={`tree-node ${active==="fisher-ury-interests"?"active":""}`} onClick={()=>setActive("fisher-ury-interests")}><Icon name="file" size={11} /> fisher-ury-interests</div>
          <div className="tree-node"><Icon name="file" size={11} /> voss-never-split</div>
          <div className="tree-folder"><Icon name="folder" size={12} /> synthesis</div>
          <div className="tree-node"><Icon name="file" size={11} /> silent-buyer-synthesis</div>
        </div>
        <div className="tree-group">
          <div className="tree-head"><span className="dot" style={{ background: "var(--dom-work)" }} />work</div>
          <div className="tree-folder"><Icon name="folder" size={12} /> entities</div>
          <div className="tree-node"><Icon name="file" size={11} /> helios-account</div>
          <div className="tree-folder"><Icon name="folder" size={12} /> sources</div>
          <div className="tree-node"><Icon name="file" size={11} /> 2026-04-18-acme-q2-call</div>
        </div>
        <div className="tree-group">
          <div className="tree-head"><span className="dot" style={{ background: "var(--dom-personal)" }} /><Icon name="lock" size={10} /> personal</div>
          <div className="tree-node dim" style={{ paddingLeft: 10, fontStyle: "italic" }}>— 23 notes, hidden by default</div>
        </div>
      </div>

      <div style={{ overflowY: "auto", position: "relative" }}>
        <div className="reader">
          <div className="meta-strip">
            <span className={`chip dom-${note.domain}`}>{note.domain}</span>
            <span>{note.folder} · {note.readTime} · modified {note.modified}</span>
            <span className="spacer" />
            <button className="iconbtn obs-link" title="Open in Obsidian">
              <Icon name="obsidian" size={14} /> <span style={{ fontSize: 11 }}>Obsidian</span>
            </button>
            <button className={`edit-toggle ${editing?"on":""}`} onClick={() => setEditing(e => !e)}>
              {editing ? <><Icon name="check" size={12} /> Preview</> : <><Icon name="edit" size={12} /> Edit</>}
            </button>
          </div>

          {editing ? (
            <div className="editor-shell">
              <div className="editor-warn">
                <Icon name="alert" size={12} />
                <span>You're editing the vault directly. Save will stage a patch for review — no LLM in the loop.</span>
              </div>
              <div className="monaco-shim">
                <div className="monaco-gutter">
                  {editBuf.split("\n").map((_, i) => <div key={i}>{i+1}</div>)}
                </div>
                <textarea className="monaco-text mono" value={editBuf} onChange={e => setEditBuf(e.target.value)} />
              </div>
              <div className="editor-actions">
                <span className="muted" style={{ fontSize: 12, flex: 1 }}>{editBuf.split("\n").length} lines · {editBuf.length} chars</span>
                <button className="btn ghost" onClick={() => { setEditing(false); setEditBuf(note.rawSource||note.body); }}>Discard</button>
                <button className="btn primary" onClick={() => {
                  setEditing(false);
                  dispatch({ type: "add_patch", patch: {
                    id: "p-"+Date.now(), tool: "brain_propose_note", target: note.path,
                    reason: "Direct edit from Browse. User-authored — no LLM synthesis.",
                    createdAt: "just now", domain: note.domain, mode: null, isNew: true,
                    diff: [
                      { type: "ctx", n: 10, code: "## The pattern" },
                      { type: "del", n: 11, code: "Avoidance shows up as **shape-shifting**, not as hostility." },
                      { type: "add", n: 11, code: "Avoidance shows up as **shape-shifting** — not hostility, not resistance." },
                    ]
                  }});
                  dispatch({ type: "toast", t: { lead: "Saved as patch.", msg: "Queued in Pending for your review.", icon: "diff" } });
                }}>
                  <Icon name="diff" size={13} /> Save as patch
                </button>
              </div>
            </div>
          ) : (
            <>
              <h1>{note.title}</h1>
              <div className="fm">
                {Object.entries(note.fm).map(([k,v]) => (
                  <div key={k}><span className="k">{k}:</span> {Array.isArray(v)
                    ? v.map((x,i) => <React.Fragment key={i}>{i>0 && ", "}<a className={`wikilink ${BROKEN_WIKILINKS.has(x)?"broken":""}`}>[[{x}]]</a></React.Fragment>)
                    : String(v)}</div>
                ))}
              </div>
              {renderMd(note.body,
                (slug, anchor) => setHover({ slug, anchor }),
                () => setTimeout(() => setHover({ slug: null, anchor: null }), 150))}
            </>
          )}
        </div>
        {hover.slug && <WikilinkHover slug={hover.slug} anchor={hover.anchor} onClose={() => setHover({ slug: null, anchor: null })} />}
      </div>

      {searchOpen && <SearchResults query={searchQ} onPick={(slug, q) => { if (q !== undefined) setSearchQ(q); else { setActive(slug); setSearchOpen(false); setSearchQ(""); } }} onClose={() => { setSearchOpen(false); setSearchQ(""); }} />}
    </div>
  );
};

Object.assign(window, { BrowseScreen });
