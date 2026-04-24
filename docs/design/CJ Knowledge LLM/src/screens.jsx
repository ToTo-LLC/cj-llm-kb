// Inbox + Browse + Bulk + Settings + Setup wizard screens

const InboxScreen = ({ state, dispatch }) => {
  const [tab, setTab] = React.useState("recent");
  const [dragOver, setDragOver] = React.useState(false);
  const sources = state.sources;
  const counts = {
    progress: sources.filter(s => ["queued","extracting","classifying","summarizing","integrating"].includes(s.status)).length,
    failed: sources.filter(s => s.status === "failed").length,
    recent: sources.filter(s => s.status === "done").length,
  };
  const filtered = {
    progress: sources.filter(s => ["queued","extracting","classifying","summarizing","integrating"].includes(s.status)),
    failed: sources.filter(s => s.status === "failed"),
    recent: sources.filter(s => s.status === "done"),
  }[tab] || [];

  const extOf = (t) => ({ url: "URL", pdf: "PDF", text: "TXT", email: "EML" })[t] || "FILE";

  return (
    <div className="inbox-screen">
      <div className="page-header">
        <div className="titles">
          <div className="eyebrow">Ingest sources</div>
          <h1>Inbox</h1>
        </div>
        <div className="actions">
          <div className="autonomous-switch">
            <div className={`switch ${state.autonomousMode?"on danger":""}`} onClick={() => dispatch({type:"set_auto",v:!state.autonomousMode})} />
            <div style={{ fontSize: 12 }}>Autonomous ingest</div>
          </div>
        </div>
      </div>

      <div className="inbox-body">
        <div className={`dropzone ${dragOver?"active":""}`}
             onDragOver={(e)=>{e.preventDefault(); setDragOver(true);}}
             onDragLeave={()=>setDragOver(false)}
             onDrop={(e)=>{e.preventDefault(); setDragOver(false); dispatch({type:"drop_file"});}}>
          <div className="dz-orbs" />
          <h2>Drop anything worth remembering.</h2>
          <p>PDFs, URLs, transcripts, tweets, emails. brain classifies and files them for you.</p>
          <div className="dz-actions">
            <button className="btn primary lg">Browse files</button>
            <button className="btn lg">Paste a URL</button>
          </div>
          <div className="paste-hint">or <kbd>⌘</kbd><kbd>V</kbd> anywhere to paste text or a link</div>
        </div>

        <div className="inbox-tabs">
          <button className={tab==="progress"?"on":""} onClick={() => setTab("progress")}>In progress <span className="n">{counts.progress}</span></button>
          <button className={tab==="failed"?"on":""} onClick={() => setTab("failed")}>Needs attention <span className="n">{counts.failed}</span></button>
          <button className={tab==="recent"?"on":""} onClick={() => setTab("recent")}>Recent <span className="n">{counts.recent}</span></button>
        </div>

        <div className="source-list">
          {filtered.length === 0 && (
            <div className="empty-state">
              <div className="orb" />
              <h2>Nothing here.</h2>
              <p>{tab==="progress"?"No sources being processed.":tab==="failed"?"Nothing has failed — good.":"Drop a source to get started."}</p>
            </div>
          )}
          {filtered.map(s => (
            <div className="source-row" key={s.id}>
              <div className={`sr-ico ${s.type}`}>{extOf(s.type)}</div>
              <div>
                <div className="sr-title">{s.title}</div>
                <div className="sr-sub">
                  {s.status === "failed" ? <span style={{ color: "var(--tt-orange)" }}>{s.error}</span> :
                   s.status === "done" ? <span>Filed to <strong>{s.domain}</strong> · ${s.cost.toFixed(3)} · {s.time}</span> :
                   <span>{s.status} · {s.time}</span>}
                </div>
              </div>
              {s.status === "done" ? (
                <span className={`chip dom-${s.domain}`}>{s.domain}</span>
              ) : s.domain ? (
                <span className={`chip dom-${s.domain}`}>{s.domain}</span>
              ) : (
                <span className="chip">unclassified</span>
              )}
              <div className={`progress ${s.status==="done"?"done":s.status==="failed"?"failed":""}`}>
                <span style={{ width: `${s.progress}%` }} />
              </div>
              <span className={`status-pill ${s.status==="done"?"done":s.status==="failed"?"failed":"progress"}`}>
                <span className="dot" />
                {s.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const BrowseScreen = ({ state }) => {
  const [active, setActive] = React.useState("conflict-avoidance-tells");
  return (
    <div className="browse-screen">
      <div className="file-tree">
        <div className="tree-group">
          <div className="tree-head"><span className="dot" style={{ background: "var(--dom-research)" }} />research</div>
          <div className="tree-folder"><Icon name="folder" size={12} /> concepts <span className="dim" style={{ marginLeft: "auto", fontSize: 10 }}>8</span></div>
          <div className={`tree-node ${active==="conflict-avoidance-tells"?"active":""}`} onClick={()=>setActive("conflict-avoidance-tells")}><Icon name="file" size={11} /> conflict-avoidance-tells</div>
          <div className="tree-node"><Icon name="file" size={11} /> concession-pairs</div>
          <div className="tree-node"><Icon name="file" size={11} /> tactical-empathy</div>
          <div className="tree-folder"><Icon name="folder" size={12} /> notes</div>
          <div className="tree-node"><Icon name="file" size={11} /> fisher-ury-interests</div>
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

      <div style={{ overflowY: "auto" }}>
        <div className="reader">
          <div className="meta-strip">
            <span className="chip dom-research">research</span>
            <span>concepts · 3 min read · modified 2d ago</span>
            <span className="spacer" />
          </div>
          <h1>Conflict-Avoidance Tells</h1>
          <div className="fm">
            <div><span className="k">type:</span> concept</div>
            <div><span className="k">domain:</span> research</div>
            <div><span className="k">created:</span> 2026-03-14</div>
            <div><span className="k">links:</span> [[fisher-ury-interests]], [[silent-buyer-synthesis]]</div>
          </div>
          <p>When a counterparty is avoiding a conflict they can't articulate, they emit a small set of structural tells before the conversation breaks down. Catching these early is the difference between a deal that stalls and one that re-opens.</p>
          <h2>The pattern</h2>
          <p>Avoidance shows up as <strong>shape-shifting</strong>, not as hostility. The counterparty widens the room, reframes urgency downward, or paraphrases your position back to you without movement. Each of these moves is doing the same thing: importing ambiguity into a place where a decision is trying to form.</p>
          <h2>Signals, in order of arrival</h2>
          <ul>
            <li><strong>Sudden attendee expansion.</strong> A new required stakeholder appears late. The decision is being outsourced to a room that can fail to decide.</li>
            <li><strong>Urgency reframing.</strong> "Let's regroup next month" replaces "let's book the next call." See <a className="wikilink" href="#">[[silent-buyer-synthesis]]</a>.</li>
            <li><strong>Accurate paraphrase, no movement.</strong> Your position is restated correctly; no counter-offer follows. A hidden risk interest is in play.</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

const BulkScreen = () => (
  <div className="page-main">
    <div className="empty-state" style={{ paddingTop: 80 }}>
      <Icon name="upload" size={40} style={{ color: "var(--text-muted)", marginBottom: 20 }} />
      <h2 style={{ fontWeight: 300 }}>Bulk Import</h2>
      <p>Point brain at a folder of sources — a year of meeting notes, a reading archive, an old Obsidian vault.<br/>It runs a dry-run first so you can review and adjust before anything lands in the vault.</p>
      <div style={{ marginTop: 24, display: "inline-flex", gap: 10 }}>
        <button className="btn primary lg">Pick a folder</button>
        <button className="btn ghost lg">Use a path</button>
      </div>
    </div>
  </div>
);

const SettingsScreen = ({ state, dispatch }) => {
  const [tab, setTab] = React.useState("general");
  const tabs = [
    { k: "general", l: "General" },
    { k: "providers", l: "LLM providers" },
    { k: "budget", l: "Budget & costs" },
    { k: "auto", l: "Autonomous mode" },
    { k: "integrations", l: "Integrations" },
    { k: "domains", l: "Domains" },
    { k: "brain", l: "BRAIN.md" },
    { k: "backups", l: "Backups" },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", height: "100%", overflow: "hidden" }}>
      <div style={{ borderRight: "1px solid var(--hairline)", padding: "20px 10px", background: "var(--surface-1)" }}>
        <div className="nav-section-label" style={{ paddingTop: 0 }}>Settings</div>
        {tabs.map(t => (
          <div key={t.k} className={`nav-item ${tab===t.k?"active":""}`} onClick={() => setTab(t.k)}>
            <span className="label">{t.l}</span>
          </div>
        ))}
      </div>
      <div style={{ overflowY: "auto", padding: "24px 32px 60px" }}>
        <div className="eyebrow" style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-dim)", marginBottom: 6 }}>Settings</div>
        <h1 style={{ fontSize: 28, fontWeight: 300, marginBottom: 20 }}>{tabs.find(t=>t.k===tab).l}</h1>

        {tab === "auto" && (
          <>
            <p className="muted" style={{ maxWidth: 600 }}>Autonomous mode lets brain write to the vault without staging a patch for review. Turn it on per-tool only when you trust that category of change.</p>
            <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 12, maxWidth: 640 }}>
              {[
                { k: "ingest", l: "Source ingest", d: "Auto-file summarized sources into the right domain.", safe: true },
                { k: "entities", l: "Entity updates", d: "Update per-person / per-org notes from call transcripts.", safe: true },
                { k: "concepts", l: "Concept notes", d: "Create brand-new concept notes from chat synthesis.", safe: false },
                { k: "index", l: "Domain index rewrites", d: "Re-structure index.md files. Rarely wanted.", safe: false, danger: true },
              ].map(row => (
                <div key={row.k} className="patch-card" style={{ cursor: "default" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                    <div className={`switch ${state.auto?.[row.k]?"on":""} ${row.danger?"danger":""}`} onClick={() => dispatch({type:"toggle_auto_cat",k:row.k})}></div>
                    <div>
                      <div style={{ fontWeight: 500, fontSize: 14 }}>{row.l}</div>
                      <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{row.d}</div>
                      {row.danger && <div style={{ fontSize: 11, color: "var(--tt-orange)", marginTop: 6 }}><Icon name="alert" size={10} /> Advanced — may rewrite curated files.</div>}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "budget" && (
          <div style={{ maxWidth: 640 }}>
            <p className="muted">Hard caps stop new LLM calls when exceeded. You'll see a clear message and can raise the cap or wait.</p>
            <div style={{ marginTop: 24, display: "grid", gap: 16 }}>
              <div className="patch-card" style={{ cursor: "default" }}>
                <div className="eyebrow" style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 6 }}>Daily cap</div>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <input className="input-field" style={{ width: 120 }} defaultValue="$2.50" />
                  <span className="dim">Today: ${state.costToday.toFixed(2)} used</span>
                </div>
              </div>
              <div className="patch-card" style={{ cursor: "default" }}>
                <div className="eyebrow" style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 6 }}>Monthly cap</div>
                <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                  <input className="input-field" style={{ width: 120 }} defaultValue="$60.00" />
                  <span className="dim">This month: $18.42 used</span>
                </div>
              </div>
              <div className="patch-card" style={{ cursor: "default" }}>
                <div className="eyebrow" style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 6 }}>Alert threshold</div>
                <div className="dim" style={{ fontSize: 13 }}>Warn when today's spend crosses <strong style={{ color: "var(--text)" }}>80%</strong> of cap.</div>
              </div>
            </div>
          </div>
        )}

        {tab === "general" && (
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
              <input className="input-field" defaultValue="~/Documents/brain" />
              <div className="hint">Your vault is a plain folder. Point Obsidian at it if you want.</div>
            </div>
          </div>
        )}

        {!["general","auto","budget"].includes(tab) && (
          <div className="empty-state">
            <p>Settings panel for <strong>{tabs.find(t=>t.k===tab).l}</strong> — form fields, same pattern.</p>
          </div>
        )}
      </div>
    </div>
  );
};

const SetupWizard = ({ onDone, onSkip }) => {
  const [step, setStep] = React.useState(1);
  const total = 6;
  const next = () => setStep(s => Math.min(total, s+1));
  const prev = () => setStep(s => Math.max(1, s-1));
  const [themePick, setThemePick] = React.useState("dark");

  return (
    <div className="setup-backdrop">
      <div className="setup-card">
        <div className="setup-orbs" />
        <div className="eyebrow">Step {step} of {total}</div>
        {step === 1 && (<>
          <h1>Welcome to <em style={{ fontStyle: "normal", fontWeight: 400 }}>brain</em>.</h1>
          <p className="lead">A knowledge base that stays on your machine, run by an LLM you control.<br/>Nothing leaves this computer unless you tell it to.</p>
        </>)}
        {step === 2 && (<>
          <h1>Where should your vault live?</h1>
          <p className="lead">brain writes Markdown files to this folder. It's a normal folder — Obsidian, Finder, git all still work.</p>
          <div className="setup-field">
            <label>Vault folder</label>
            <input className="input-field" defaultValue="~/Documents/brain" />
            <div className="hint">Default works for most people. Change it if you keep notes elsewhere.</div>
          </div>
        </>)}
        {step === 3 && (<>
          <h1>Connect a model.</h1>
          <p className="lead">brain runs on Anthropic's Claude for now. Paste an API key — it's stored only on your machine.</p>
          <div className="setup-field">
            <label>Anthropic API key</label>
            <input className="input-field" placeholder="sk-ant-…" />
            <div className="hint">Don't have one? <a style={{ color: "var(--tt-cyan)" }}>Get an API key →</a></div>
          </div>
        </>)}
        {step === 4 && (<>
          <h1>Pick a starting theme.</h1>
          <p className="lead">We'll seed your first domain with a welcome note. You can add more anytime.</p>
          <div className="theme-cards" style={{ marginTop: 12 }}>
            {[
              { k: "research", l: "Research", d: "reading · papers", c: "var(--tt-cyan)" },
              { k: "work", l: "Work", d: "calls · deals", c: "var(--tt-sage)" },
              { k: "personal", l: "Personal", d: "journal · ideas", c: "var(--tt-orange)" },
              { k: "blank", l: "Blank", d: "start empty", c: "var(--text-dim)" },
            ].map(t => (
              <div key={t.k} className={`theme-card ${themePick===t.k?"on":""}`} onClick={() => setThemePick(t.k)}>
                <div className="swatch" style={{ background: t.c, opacity: 0.85 }} />
                <div className="t-name">{t.l}</div>
                <div className="t-desc">{t.d}</div>
              </div>
            ))}
          </div>
        </>)}
        {step === 5 && (<>
          <h1>Tell brain about you.</h1>
          <p className="lead">Optional. This becomes your <code>BRAIN.md</code> — the voice brain uses when talking to you.</p>
          <div className="setup-field">
            <label>Your name</label>
            <input className="input-field" placeholder="CJ" />
          </div>
          <div className="setup-field">
            <label>What you're working on</label>
            <textarea className="input-field" style={{ height: 80, padding: 12, resize: "none" }} placeholder="Sales research, conflict identification in complex deals, a Q2 board memo…" />
          </div>
        </>)}
        {step === 6 && (<>
          <h1>Talk to brain from Claude Desktop?</h1>
          <p className="lead">brain can also be reached through Claude Desktop via MCP. We can install the connection for you now.</p>
          <div className="patch-card" style={{ cursor: "default", marginTop: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div className="status-pill done"><span className="dot" /> detected</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500 }}>Claude Desktop 1.0.38</div>
                <div className="muted" style={{ fontSize: 12 }}>Config at ~/Library/Application Support/Claude</div>
              </div>
              <button className="btn primary">Install MCP</button>
            </div>
          </div>
        </>)}

        <div className="setup-progress">
          {Array.from({length: total}).map((_, i) => (
            <div key={i} className={`dot ${i+1===step?"on":i+1<step?"done":""}`} />
          ))}
        </div>

        <div className="setup-actions">
          <div>
            {step > 1 && <button className="btn ghost" onClick={prev}>← Back</button>}
          </div>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            {step > 1 && step < total && <span className="setup-skip" onClick={next}>Skip this →</span>}
            {step < total ? (
              <button className="btn primary lg" onClick={next}>Continue</button>
            ) : (
              <button className="btn primary lg" onClick={onDone}>Start using brain</button>
            )}
          </div>
        </div>

        {step === 1 && (
          <div style={{ position: "absolute", bottom: 18, right: 28 }}>
            <span className="setup-skip" onClick={onSkip}>Already set up → open app</span>
          </div>
        )}
      </div>
    </div>
  );
};

Object.assign(window, { InboxScreen, BrowseScreen, BulkScreen, SettingsScreen, SetupWizard });
