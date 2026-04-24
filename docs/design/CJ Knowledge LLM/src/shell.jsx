// App-wide shared components

const Topbar = ({ scope, setScope, view, activeThread, mode, setMode, costToday, budget, theme, setTheme, toggleRail, railOpen }) => {
  const [openScope, setOpenScope] = React.useState(false);
  const [openCost, setOpenCost] = React.useState(false);
  const showModeSwitch = view === "chat";
  const costPct = Math.min(100, (costToday / budget) * 100);
  const gaugeClass = costPct > 85 ? "danger" : costPct > 65 ? "warn" : "";

  return (
    <div className="topbar">
      <div className="brand">
        <div className="orbs" />
        <div className="name">brain<em> · v0.7</em></div>
      </div>
      <div className="topbar-sep" />

      {/* Scope picker */}
      <div style={{ position: "relative" }}>
        <button className="scope-picker" onClick={() => setOpenScope(v => !v)}>
          <div className="dom-dots">
            {window.SEED.domains.map(d => (
              <div key={d.id}
                   className={`dot ${d.id} ${scope.includes(d.id) ? "on" : ""}`}
                   style={{ opacity: scope.includes(d.id) ? 1 : 0.25 }} />
            ))}
          </div>
          <span>{scope.length === 0 ? "No domain" : scope.length === 1 ? window.SEED.domains.find(d=>d.id===scope[0]).name : scope.length === window.SEED.domains.length ? "All domains" : `${scope.length} domains`}</span>
          {scope.includes("personal") && <Icon name="lock" size={11} style={{ color: "var(--dom-personal)" }} />}
          <Icon name="caretDown" size={12} className="caret" />
        </button>
        {openScope && (
          <div className="dropdown" style={{ top: 36, left: 0 }}>
            <div className="group-label">Visible domains</div>
            {window.SEED.domains.map(d => (
              <div key={d.id} className="item" onClick={() => {
                const next = scope.includes(d.id) ? scope.filter(x=>x!==d.id) : [...scope, d.id];
                setScope(next);
              }}>
                <div className={`dot ${d.id}`} style={{ width: 8, height: 8, borderRadius: 999, background: `var(--dom-${d.id})` }} />
                <span style={{ flex: 1 }}>{d.name}</span>
                <span className="dim" style={{ fontSize: 11 }}>{d.count}</span>
                {scope.includes(d.id) && <Icon name="check" size={14} className="check" />}
              </div>
            ))}
            <div className="divider" />
            <div className="item" onClick={() => { setScope(["research","work"]); setOpenScope(false); }}>
              <Icon name="globe" size={14} /> <span>research + work (default)</span>
            </div>
            <div className="item" onClick={() => { setScope(["research","work","personal"]); setOpenScope(false); }}>
              <Icon name="lock" size={14} style={{ color: "var(--dom-personal)" }} />
              <span>All domains <em style={{ opacity: 0.6, fontStyle: "normal", marginLeft: 4 }}>(includes personal)</em></span>
            </div>
          </div>
        )}
      </div>

      {/* Mode switch — only on chat */}
      {showModeSwitch && (
        <>
          <div className="topbar-sep" />
          <div className="seg mode">
            {[
              { id: "ask", label: "Ask", color: "var(--tt-cyan)" },
              { id: "brainstorm", label: "Brainstorm", color: "var(--tt-cream)" },
              { id: "draft", label: "Draft", color: "var(--tt-sage)" },
            ].map(m => (
              <button key={m.id} className={mode===m.id?"on":""} data-mode={m.id} onClick={() => setMode(m.id)}>
                <span className="dot" style={{ background: m.color }} /> {m.label}
              </button>
            ))}
          </div>
        </>
      )}

      <div className="topbar-spacer" />

      {/* Cost meter */}
      <div style={{ position: "relative" }}>
        <button className="cost-meter" onClick={() => setOpenCost(v => !v)}>
          <span className="label">Today</span>
          <span>${costToday.toFixed(2)}</span>
          <div className={`gauge ${gaugeClass}`}>
            <span style={{ width: `${costPct}%` }} />
          </div>
          <span className="label">/ ${budget.toFixed(2)}</span>
        </button>
        {openCost && (
          <div className="dropdown" style={{ top: 36, right: 0, minWidth: 260 }}>
            <div className="group-label">Spend</div>
            <div className="item" style={{ cursor: "default" }}>
              <span style={{ flex: 1 }}>Today</span>
              <span className="mono">${costToday.toFixed(3)}</span>
            </div>
            <div className="item" style={{ cursor: "default" }}>
              <span style={{ flex: 1 }}>This month</span>
              <span className="mono">${window.SEED.costMonth.toFixed(2)}</span>
            </div>
            <div className="divider" />
            <div className="group-label">By domain · today</div>
            <div className="item" style={{ cursor: "default" }}>
              <div className="dot" style={{ width: 8, height: 8, borderRadius: 999, background: "var(--dom-research)" }} />
              <span style={{ flex: 1 }}>research</span>
              <span className="mono dim">$0.38</span>
            </div>
            <div className="item" style={{ cursor: "default" }}>
              <div className="dot" style={{ width: 8, height: 8, borderRadius: 999, background: "var(--dom-work)" }} />
              <span style={{ flex: 1 }}>work</span>
              <span className="mono dim">$0.44</span>
            </div>
            <div className="item" style={{ cursor: "default" }}>
              <div className="dot" style={{ width: 8, height: 8, borderRadius: 999, background: "var(--dom-personal)" }} />
              <span style={{ flex: 1 }}>personal</span>
              <span className="mono dim">$0.02</span>
            </div>
          </div>
        )}
      </div>

      <button className="topbtn" title={theme==="dark"?"Switch to light":"Switch to dark"} onClick={() => setTheme(theme==="dark"?"light":"dark")}>
        <Icon name={theme==="dark"?"sun":"moon"} size={16} />
      </button>
      <button className="topbtn" onClick={toggleRail} title={railOpen?"Hide panel":"Show panel"}>
        <Icon name="layers2" size={16} />
      </button>
      <button className="topbtn" title="Settings" onClick={() => window.brainStore.setView("settings")}>
        <Icon name="gear" size={16} />
      </button>
    </div>
  );
};

const LeftNav = ({ view, setView, pendingCount, threads, activeThread, setActiveThread }) => {
  const grouped = threads.reduce((acc, t) => { (acc[t.group]=acc[t.group]||[]).push(t); return acc; }, {});
  return (
    <div className="nav">
      <button className="nav-new" onClick={() => { setView("chat"); setActiveThread(null); }}>
        <Icon name="plus" size={14} /> New chat
      </button>

      <div className="nav-item" onClick={() => setView("chat")} data-active={view==="chat"}>
        {/* separate from thread list below */}
      </div>

      <div className="nav-section-label" style={{ paddingTop: 0 }}>Workspace</div>

      <div className={`nav-item ${view==="inbox"?"active":""}`} onClick={() => setView("inbox")}>
        <Icon name="inbox" className="ico" />
        <span className="label">Inbox</span>
        <span className="badge" style={{ background: "var(--surface-4)", color: "var(--text-muted)" }}>3</span>
      </div>
      <div className={`nav-item ${view==="browse"?"active":""}`} onClick={() => setView("browse")}>
        <Icon name="browse" className="ico" />
        <span className="label">Browse</span>
      </div>
      <div className={`nav-item ${view==="pending"?"active":""}`} onClick={() => setView("pending")}>
        <Icon name="diff" className="ico" />
        <span className="label">Pending</span>
        {pendingCount > 0 && <span className="badge">{pendingCount}</span>}
      </div>
      <div className={`nav-item ${view==="bulk"?"active":""}`} onClick={() => setView("bulk")}>
        <Icon name="upload" className="ico" />
        <span className="label">Bulk import</span>
      </div>

      <div className="nav-section-label">Threads</div>
      <div className="nav-threads">
        {Object.entries(grouped).map(([date, items]) => (
          <React.Fragment key={date}>
            <div className="nav-thread-date">{date}</div>
            {items.map(t => (
              <div key={t.id}
                   className={`nav-thread ${view==="chat" && activeThread===t.id?"active":""}`}
                   onClick={() => { setView("chat"); setActiveThread(t.id); }}>
                <div className="t-title">{t.title}</div>
                <div className="t-meta">
                  <span className={`mode-chip`}>{t.mode}</span>
                  <div className="dot" style={{ width: 5, height: 5, borderRadius: 999, background: `var(--dom-${t.domain})` }} />
                  <span>{t.updated || ""}</span>
                </div>
              </div>
            ))}
          </React.Fragment>
        ))}
      </div>

      <div style={{ flex: 1 }} />

      <div className={`nav-item ${view==="settings"?"active":""}`} onClick={() => setView("settings")}>
        <Icon name="gear" className="ico" />
        <span className="label">Settings</span>
      </div>
    </div>
  );
};

const Toasts = ({ toasts, dismiss }) => (
  <div className="toasts">
    {toasts.map(t => (
      <div key={t.id} className={`toast ${t.variant||""}`}>
        {t.icon && <Icon name={t.icon} size={14} />}
        <span><strong className="lead">{t.lead}</strong> {t.msg}</span>
        {t.undo && <span className="undo" onClick={() => { t.undo(); dismiss(t.id); }}>Undo ({t.countdown}s)</span>}
        <button className="iconbtn" onClick={() => dismiss(t.id)} style={{ marginLeft: 4 }}><Icon name="close" size={12} /></button>
      </div>
    ))}
  </div>
);

const TweaksPanel = ({ theme, setTheme, density, setDensity, railMode, setRailMode, onClose }) => (
  <div className="tweaks-panel">
    <div style={{ display: "flex", alignItems: "center", marginBottom: 8 }}>
      <h3 style={{ margin: 0, flex: 1 }}>Tweaks</h3>
      <button className="iconbtn" onClick={onClose}><Icon name="close" size={12} /></button>
    </div>
    <div className="tweaks-row">
      <span className="lbl">Theme</span>
      <div className="seg" style={{ transform: "scale(0.9)" }}>
        <button className={theme==="dark"?"on":""} onClick={() => setTheme("dark")}>Dark</button>
        <button className={theme==="light"?"on":""} onClick={() => setTheme("light")}>Light</button>
      </div>
    </div>
    <div className="tweaks-row">
      <span className="lbl">Density</span>
      <div className="seg" style={{ transform: "scale(0.9)" }}>
        <button className={density==="comfortable"?"on":""} onClick={() => setDensity("comfortable")}>Comfy</button>
        <button className={density==="compact"?"on":""} onClick={() => setDensity("compact")}>Compact</button>
      </div>
    </div>
    <div className="tweaks-row">
      <span className="lbl">Pending panel</span>
      <div className="seg" style={{ transform: "scale(0.9)" }}>
        <button className={railMode==="popin"?"on":""} onClick={() => setRailMode("popin")}>Pop in</button>
        <button className={railMode==="badge"?"on":""} onClick={() => setRailMode("badge")}>Badge</button>
      </div>
    </div>
  </div>
);

Object.assign(window, { Topbar, LeftNav, Toasts, TweaksPanel });
