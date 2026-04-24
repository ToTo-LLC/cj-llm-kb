// Settings detail panels: Providers, Integrations, Domains, BRAIN.md, Backups
// These are loaded as window globals and used by SettingsScreen via window.settingsPanels

const ProvidersPanel = () => {
  const [key, setKey] = React.useState("");
  const [saved, setSaved] = React.useState(true);
  const [testing, setTesting] = React.useState(null);
  const ping = () => {
    setTesting("running");
    setTimeout(() => setTesting("ok"), 900);
  };
  const models = [
    { stage: "Ask (chat)",         m: "claude-sonnet-4-5",      cost: "standard" },
    { stage: "Brainstorm (chat)",  m: "claude-sonnet-4-5",      cost: "standard" },
    { stage: "Draft (chat)",       m: "claude-opus-4-5",        cost: "higher — careful edits" },
    { stage: "Ingest · classify",  m: "claude-haiku-4-5",       cost: "cheap" },
    { stage: "Ingest · summarize", m: "claude-sonnet-4-5",      cost: "standard" },
    { stage: "Ingest · integrate", m: "claude-sonnet-4-5",      cost: "standard" },
  ];
  return (
    <div style={{ maxWidth: 720 }}>
      <p className="muted">API keys are stored only on this machine. They never leave your computer except to reach Anthropic.</p>
      <div className="sect-card">
        <div className="sect-head">Anthropic API key</div>
        <div className="row-grid">
          <label>Key</label>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input className="input-field mono" style={{ flex: 1 }} type="password"
                   placeholder="sk-ant-••••••••••••••••"
                   value={saved ? "sk-ant-•••••••••••qXf2" : key}
                   onChange={e => { setKey(e.target.value); setSaved(false); }} />
            {!saved && <button className="btn primary" onClick={() => setSaved(true)}>Save</button>}
            <button className="btn ghost" onClick={ping}>
              {testing === "running" ? <><span className="spinner sm" /> testing…</> :
               testing === "ok" ? <><Icon name="check" size={12} /> reachable</> : "Test"}
            </button>
          </div>
          <div className="hint" style={{ gridColumn: "2" }}>Stored locally in <code>~/Documents/brain/.brain/secrets.env</code> (mode 0600). Visible only the first time you paste it.</div>
        </div>
      </div>

      <div className="sect-card">
        <div className="sect-head">Model per stage</div>
        <p className="muted" style={{ fontSize: 12, marginBottom: 12 }}>Use Sonnet as the default, Haiku for cheap classify steps, Opus only where you want extra careful synthesis.</p>
        <div className="model-table">
          {models.map((row, i) => (
            <div className="mrow" key={i}>
              <div className="mstage">{row.stage}</div>
              <select className="route-sel" defaultValue={row.m}>
                <option>claude-haiku-4-5</option>
                <option>claude-sonnet-4-5</option>
                <option>claude-opus-4-5</option>
              </select>
              <div className="muted mono" style={{ fontSize: 11 }}>{row.cost}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const IntegrationsPanel = () => {
  const [installed, setInstalled] = React.useState(true);
  const [verifying, setVerifying] = React.useState(null);
  return (
    <div style={{ maxWidth: 720 }}>
      <p className="muted">brain speaks MCP — other apps can talk to your vault through a local, token-gated channel.</p>

      <div className="sect-card">
        <div className="int-row">
          <div className="int-icon">
            <div style={{ width: 40, height: 40, borderRadius: 8, background: "linear-gradient(135deg,#1a1a1a,#2a2a2a)", display: "grid", placeItems: "center", fontFamily: "var(--mono)", fontSize: 11, color: "var(--text-muted)" }}>CD</div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 500 }}>Claude Desktop</div>
            <div className="muted" style={{ fontSize: 12 }}>~/Library/Application Support/Claude · v1.0.38 detected</div>
          </div>
          <div className={`status-pill ${installed?"done":""}`}>
            <span className="dot" /> {installed ? "installed · verified" : "not installed"}
          </div>
        </div>
        <div className="int-actions">
          {installed ? (
            <>
              <button className="btn ghost sm" onClick={() => { setVerifying("running"); setTimeout(() => setVerifying("ok"), 800); }}>
                {verifying === "running" ? <><span className="spinner sm" /> checking…</> :
                 verifying === "ok" ? <><Icon name="check" size={11} /> responded in 42ms</> : "Self-test"}
              </button>
              <button className="btn ghost sm">Regenerate config</button>
              <div className="spacer" style={{ flex: 1 }} />
              <button className="btn ghost sm danger" onClick={() => window.brainStore.dispatch({ type: "open_confirm", confirm: {
                title: "Uninstall Claude Desktop integration?",
                body: "Claude Desktop will no longer see your vault. You can reinstall anytime. Type UNINSTALL to confirm.",
                phrase: "UNINSTALL",
                onConfirm: () => setInstalled(false),
              }})}>Uninstall</button>
            </>
          ) : (
            <button className="btn primary sm" onClick={() => setInstalled(true)}>Install</button>
          )}
        </div>
      </div>

      <div className="sect-card">
        <div className="sect-head">Other MCP clients</div>
        <p className="muted" style={{ fontSize: 12, marginBottom: 10 }}>Copy this into any MCP-compatible client (Cursor, Zed, Continue, etc.).</p>
        <pre className="code-block">{`"brain": {
  "command": "python",
  "args": ["-m", "brain_mcp"],
  "env": {
    "BRAIN_VAULT_ROOT": "~/Documents/brain",
    "BRAIN_ALLOWED_DOMAINS": "research,work"
  }
}`}</pre>
        <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
          <button className="btn ghost sm"><Icon name="copy" size={11} /> Copy snippet</button>
          <button className="btn ghost sm">Open docs</button>
        </div>
      </div>
    </div>
  );
};

const RenameDomainDialog = ({ domain, onClose, onConfirm }) => {
  const [name, setName] = React.useState(domain?.name || "");
  const [folder, setFolder] = React.useState(domain?.id || "");
  const [confirmText, setConfirmText] = React.useState("");
  React.useEffect(() => {
    if (domain) {
      setName(domain.name);
      setFolder(domain.id);
      setConfirmText("");
    }
  }, [domain]);
  if (!domain) return null;
  const needsTypedConfirm = domain.count > 50;
  const canConfirm = name.trim() && folder.trim() && folder !== domain.id && (!needsTypedConfirm || confirmText === domain.id);

  return (
    <Modal
      open={!!domain}
      onClose={onClose}
      eyebrow={`Rename · ${domain.name}`}
      title="Rename this domain."
      width={520}
      footer={
        <>
          <button className="btn ghost" onClick={onClose}>Cancel</button>
          <button className="btn primary" disabled={!canConfirm}
                  onClick={() => onConfirm({ name, folder })}>
            <Icon name="check" size={13} /> Rename domain
          </button>
        </>
      }
    >
      <div className="row-grid" style={{ marginBottom: 8 }}>
        <label>Display name</label>
        <input className="input-field" value={name} onChange={e => setName(e.target.value)} autoFocus />
        <label>Folder</label>
        <input className="input-field mono" value={folder} onChange={e => setFolder(e.target.value.toLowerCase().replace(/[^a-z0-9-_]/g, ""))} />
      </div>
      <div className="rename-warn">
        <Icon name="alert" size={12} />
        <div>
          <strong>This moves <code>{domain.id}/</code> → <code>{folder || "…"}/</code> and rewrites every <code>[[wikilink]]</code> pointing into it.</strong>
          <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
            {domain.count} notes + their backlinks get rewritten. On large domains this can take a moment — brain runs it as a single atomic operation and backs up the vault first.
          </div>
        </div>
      </div>
      {needsTypedConfirm && (
        <div style={{ marginTop: 14 }}>
          <label className="eyebrow" style={{ display: "block", marginBottom: 6 }}>
            Type <code style={{ color: "var(--tt-orange)", background: "transparent" }}>{domain.id}</code> to confirm — this domain has {domain.count} notes
          </label>
          <input className="input-field mono" value={confirmText} onChange={e => setConfirmText(e.target.value)} placeholder={domain.id} />
        </div>
      )}
    </Modal>
  );
};

const DomainsPanel = ({ dispatch }) => {
  const [domains, setDomains] = React.useState([
    { id: "research", name: "Research", count: 47, color: "#00AFF0", rail: false },
    { id: "work",     name: "Work",     count: 89, color: "#96B6A6", rail: false },
    { id: "personal", name: "Personal", count: 23, color: "#FF4503", rail: true  },
  ]);
  const [addOpen, setAddOpen] = React.useState(false);
  const [renaming, setRenaming] = React.useState(null); // domain object
  return (
    <div style={{ maxWidth: 720 }}>
      <p className="muted">Domains are top-level folders in your vault. The personal domain is hidden from wildcard queries — you have to ask for it explicitly.</p>

      <div className="sect-card" style={{ padding: 0 }}>
        <div className="dom-list">
          {domains.map((d, i) => (
            <div className="dom-row" key={d.id}>
              <Icon name="grip" size={14} style={{ color: "var(--text-dim)", cursor: "grab" }} />
              <span className="dom-swatch" style={{ background: d.color }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500 }}>
                  {d.name}
                  {d.rail && <span className="rail-badge"><Icon name="lock" size={9} /> privacy-railed</span>}
                </div>
                <div className="muted" style={{ fontSize: 11 }}>{d.count} notes · <code>{d.id}/</code></div>
              </div>
              <button className="btn ghost sm" onClick={() => setRenaming(d)}>Rename</button>
              {!d.rail && (
                <button className="btn ghost sm danger" onClick={() => dispatch({ type: "open_confirm", confirm: {
                  title: `Delete the '${d.name}' domain?`,
                  body: `This removes ${d.count} notes permanently. There is no undo. Type the domain name to confirm.`,
                  phrase: d.id,
                  onConfirm: () => setDomains(ds => ds.filter(x => x.id !== d.id)),
                }})}>Delete</button>
              )}
            </div>
          ))}
        </div>
      </div>

      {!addOpen ? (
        <button className="btn ghost" style={{ marginTop: 12 }} onClick={() => setAddOpen(true)}>
          <Icon name="plus" size={12} /> Add domain
        </button>
      ) : (
        <div className="sect-card" style={{ marginTop: 12 }}>
          <div className="sect-head">New domain</div>
          <div className="row-grid">
            <label>Name</label>
            <input className="input-field" placeholder="e.g. music" />
            <label>Folder</label>
            <input className="input-field mono" placeholder="music/" />
            <label>Accent color</label>
            <div style={{ display: "flex", gap: 6 }}>
              {["#D4A373","#7F9A77","#C06C84","#8E7DBE","#E8B84E"].map(c => (
                <div key={c} className="swatch-pick" style={{ background: c }} />
              ))}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 14 }}>
            <button className="btn ghost" onClick={() => setAddOpen(false)}>Cancel</button>
            <button className="btn primary" onClick={() => setAddOpen(false)}>Create domain</button>
          </div>
        </div>
      )}

      <RenameDomainDialog
        domain={renaming}
        onClose={() => setRenaming(null)}
        onConfirm={({ name, folder }) => {
          setDomains(ds => ds.map(x => x.id === renaming.id ? { ...x, name, id: folder } : x));
          dispatch({ type: "toast", t: { lead: "Renamed.", msg: `${renaming.id}/ → ${folder}/ · ${renaming.count} backlinks rewritten.`, icon: "check" } });
          setRenaming(null);
        }}
      />
    </div>
  );
};

const BrainMdPanel = () => {
  const [val, setVal] = React.useState(`# CJ — brain persona

## Who I am
I lead GTM for a SaaS company selling into enterprise sales teams. I read broadly — negotiation theory, decision science, organizational behavior.

## How I like to be spoken to
- Direct. No hedging unless the evidence actually warrants it.
- Argue with me when you disagree. Cite the vault when you agree.
- No emoji, no "great question", no exclamation points.

## Topics I care about
- Conflict identification in complex deals
- How buyers signal avoidance
- The intersection of negotiation theory and sales methodology
- Compounding curiosity as a meta-practice`);
  const [dirty, setDirty] = React.useState(false);
  return (
    <div style={{ maxWidth: 720 }}>
      <p className="muted">This is the system prompt brain uses when it talks to you. Keep it short, specific, and in your voice — it shows up in every chat.</p>
      <div className="monaco-shim" style={{ height: 420 }}>
        <div className="monaco-gutter">
          {val.split("\n").map((_, i) => <div key={i}>{i+1}</div>)}
        </div>
        <textarea className="monaco-text mono" value={val}
                  onChange={e => { setVal(e.target.value); setDirty(true); }} />
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: 12, alignItems: "center" }}>
        <span className="muted" style={{ fontSize: 12, flex: 1 }}>{val.split("\n").length} lines · ~{Math.ceil(val.length/4)} tokens</span>
        <button className="btn ghost" disabled={!dirty} onClick={() => setDirty(false)}>Discard</button>
        <button className="btn primary" disabled={!dirty} onClick={() => setDirty(false)}>
          <Icon name="diff" size={12} /> Save as patch
        </button>
      </div>
    </div>
  );
};

const BackupsPanel = ({ dispatch }) => {
  const [backups, setBackups] = React.useState([
    { id: "b-4", date: "2026-04-21 09:02", size: "12.4 MB", notes: 159, trigger: "manual" },
    { id: "b-3", date: "2026-04-20 09:02", size: "12.1 MB", notes: 157, trigger: "auto · daily" },
    { id: "b-2", date: "2026-04-19 09:02", size: "11.9 MB", notes: 154, trigger: "auto · daily" },
    { id: "b-1", date: "2026-04-14 18:22", size: "11.2 MB", notes: 148, trigger: "pre-bulk-import" },
  ]);
  const [running, setRunning] = React.useState(false);
  return (
    <div style={{ maxWidth: 720 }}>
      <p className="muted">Backups are timestamped tarballs in <code>~/Documents/brain/.brain/backups/</code>. Auto-runs daily at 9am. Keep as many as you like — they're local.</p>

      <div className="sect-card" style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 500 }}>Back up now</div>
          <div className="muted" style={{ fontSize: 12 }}>Snapshot the entire vault + state DB. ~13 MB compressed.</div>
        </div>
        <button className="btn primary" disabled={running} onClick={() => {
          setRunning(true);
          setTimeout(() => {
            setRunning(false);
            setBackups(bs => [{ id: "b-"+Date.now(), date: new Date().toISOString().slice(0,16).replace("T"," "), size: "12.5 MB", notes: 159, trigger: "manual" }, ...bs]);
          }, 1400);
        }}>
          {running ? <><span className="spinner sm" /> backing up…</> : <>Back up now</>}
        </button>
      </div>

      <div className="sect-card" style={{ padding: 0, marginTop: 12 }}>
        <div className="sect-head" style={{ padding: "12px 16px 10px", borderBottom: "1px solid var(--hairline)" }}>Past backups</div>
        {backups.map(b => (
          <div className="bk-row" key={b.id}>
            <Icon name="archive" size={14} style={{ color: "var(--text-muted)" }} />
            <div style={{ flex: 1 }}>
              <div className="mono" style={{ fontSize: 13 }}>{b.date}</div>
              <div className="muted" style={{ fontSize: 11 }}>{b.size} · {b.notes} notes · {b.trigger}</div>
            </div>
            <button className="btn ghost sm">Reveal</button>
            <button className="btn ghost sm danger" onClick={() => dispatch({ type: "open_confirm", confirm: {
              title: "Restore from this backup?",
              body: `This replaces your current vault with the snapshot from ${b.date}. Your current state is backed up first, but this is still a big move. Type RESTORE to confirm.`,
              phrase: "RESTORE",
              onConfirm: () => {},
            }})}>Restore</button>
          </div>
        ))}
      </div>
    </div>
  );
};

// Replace the existing SettingsScreen with one that mounts all 8 tabs
const SettingsScreen = ({ state, dispatch }) => {
  const [tab, setTab] = React.useState("general");
  const tabs = [
    { k: "general",      l: "General",        i: "gear" },
    { k: "providers",    l: "LLM providers",  i: "bolt" },
    { k: "budget",       l: "Budget & costs", i: "file" },
    { k: "auto",         l: "Autonomous mode", i: "alert" },
    { k: "integrations", l: "Integrations",   i: "link" },
    { k: "domains",      l: "Domains",        i: "layers" },
    { k: "brain",        l: "BRAIN.md",       i: "chat" },
    { k: "backups",      l: "Backups",        i: "archive" },
  ];
  const cur = tabs.find(t => t.k === tab);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", height: "100%", overflow: "hidden" }}>
      <div style={{ borderRight: "1px solid var(--hairline)", padding: "20px 10px", background: "var(--surface-1)", overflowY: "auto" }}>
        <div className="nav-section-label" style={{ paddingTop: 0 }}>Settings</div>
        {tabs.map(t => (
          <div key={t.k} className={`nav-item ${tab===t.k?"active":""}`} onClick={() => setTab(t.k)}>
            <Icon name={t.i} className="ico" size={14} />
            <span className="label">{t.l}</span>
          </div>
        ))}
      </div>
      <div style={{ overflowY: "auto", padding: "24px 32px 60px" }}>
        <div className="eyebrow" style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-dim)", marginBottom: 6 }}>Settings</div>
        <h1 style={{ fontSize: 28, fontWeight: 300, marginBottom: 20 }}>{cur.l}</h1>

        {tab === "general" && <window.GeneralPanel state={state} dispatch={dispatch} />}
        {tab === "providers" && <ProvidersPanel />}
        {tab === "budget" && <window.BudgetPanel state={state} />}
        {tab === "auto" && <window.AutonomousPanel state={state} dispatch={dispatch} />}
        {tab === "integrations" && <IntegrationsPanel />}
        {tab === "domains" && <DomainsPanel dispatch={dispatch} />}
        {tab === "brain" && <BrainMdPanel />}
        {tab === "backups" && <BackupsPanel dispatch={dispatch} />}
      </div>
    </div>
  );
};

// Extract General / Budget / Autonomous from the old screens.jsx location so all live here
const GeneralPanel = ({ state, dispatch }) => (
  <div style={{ maxWidth: 560 }}>
    <div className="setup-field">
      <label>Theme</label>
      <div className="seg" style={{ marginTop: 4 }}>
        <button className={state.theme==="dark"?"on":""} onClick={() => dispatch({type:"set_theme",v:"dark"})}><Icon name="moon" size={12}/> Dark</button>
        <button className={state.theme==="light"?"on":""} onClick={() => dispatch({type:"set_theme",v:"light"})}><Icon name="sun" size={12}/> Light</button>
      </div>
    </div>
    <div className="setup-field">
      <label>Density</label>
      <div className="seg" style={{ marginTop: 4 }}>
        <button className={state.density==="comfortable"?"on":""} onClick={() => dispatch({type:"set_density",v:"comfortable"})}>Comfortable</button>
        <button className={state.density==="compact"?"on":""} onClick={() => dispatch({type:"set_density",v:"compact"})}>Compact</button>
      </div>
    </div>
    <div className="setup-field">
      <label>Vault location</label>
      <input className="input-field mono" defaultValue="~/Documents/brain" />
      <div className="hint">Your vault is a plain folder. Point Obsidian at it if you want.</div>
    </div>
  </div>
);

const BudgetPanel = ({ state }) => (
  <div style={{ maxWidth: 640 }}>
    <p className="muted">Hard caps stop new LLM calls when exceeded. You'll see a clear message and can raise the cap or wait.</p>
    <div style={{ marginTop: 24, display: "grid", gap: 16 }}>
      <div className="sect-card">
        <div className="sect-head">Daily cap</div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input className="input-field mono" style={{ width: 140 }} defaultValue="$2.50" />
          <span className="dim">Today: ${state.costToday.toFixed(2)} used</span>
        </div>
      </div>
      <div className="sect-card">
        <div className="sect-head">Monthly cap</div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input className="input-field mono" style={{ width: 140 }} defaultValue="$60.00" />
          <span className="dim">This month: $18.42 used</span>
        </div>
      </div>
      <div className="sect-card">
        <div className="sect-head">Alert threshold</div>
        <div className="dim" style={{ fontSize: 13 }}>Warn when today's spend crosses <strong style={{ color: "var(--text)" }}>80%</strong> of cap.</div>
      </div>
    </div>
  </div>
);

const AutonomousPanel = ({ state, dispatch }) => (
  <div>
    <p className="muted" style={{ maxWidth: 600 }}>Autonomous mode lets brain write to the vault without staging a patch for review. Turn it on per-tool only when you trust that category of change.</p>
    <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 12, maxWidth: 640 }}>
      {[
        { k: "ingest",   l: "Source ingest",        d: "Auto-file summarized sources into the right domain.",  safe: true },
        { k: "entities", l: "Entity updates",       d: "Update per-person / per-org notes from transcripts.",  safe: true },
        { k: "concepts", l: "Concept notes",        d: "Create new concept notes from chat synthesis.",        safe: false },
        { k: "index",    l: "Domain index rewrites", d: "Re-structure index.md files. Rarely wanted.",          safe: false, danger: true },
      ].map(row => (
        <div key={row.k} className="sect-card">
          <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
            <div className={`switch ${state.auto?.[row.k]?"on":""} ${row.danger?"danger":""}`} onClick={() => dispatch({type:"toggle_auto_cat",k:row.k})}></div>
            <div>
              <div style={{ fontWeight: 500, fontSize: 14 }}>{row.l}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{row.d}</div>
              {row.danger && <div style={{ fontSize: 11, color: "var(--dom-personal)", marginTop: 6 }}><Icon name="alert" size={10} /> Advanced — may rewrite curated files.</div>}
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
);

Object.assign(window, { SettingsScreen, GeneralPanel, BudgetPanel, AutonomousPanel });
