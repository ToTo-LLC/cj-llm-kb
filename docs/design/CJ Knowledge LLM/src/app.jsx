// Main app entry — state, store, and routing

const initialTranscript = window.SEED.transcript;

const initialState = {
  view: "chat",                 // chat | inbox | pending | browse | bulk | settings
  activeThread: "t-1",
  mode: "ask",
  scope: ["research", "work"],
  theme: localStorage.getItem("brain-theme") || "dark",
  density: localStorage.getItem("brain-density") || "comfortable",
  railMode: localStorage.getItem("brain-rail") || "popin",
  railOpen: true,
  transcript: initialTranscript,
  streaming: false,
  streamingText: "",
  ctxPct: 18,
  costToday: window.SEED.costToday,
  budget: window.SEED.budgetDaily,
  patches: window.SEED.patches,
  sources: window.SEED.sources,
  autonomousMode: false,
  auto: { ingest: false, entities: false, concepts: false, index: false },
  toasts: [],
  showTweaks: false,
  showSetup: !localStorage.getItem("brain-setup-done"),
  draggingFile: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "set_view": return { ...state, view: action.v };
    case "set_mode": return { ...state, mode: action.v };
    case "set_scope": return { ...state, scope: action.v };
    case "set_theme": {
      localStorage.setItem("brain-theme", action.v);
      return { ...state, theme: action.v };
    }
    case "set_density": {
      localStorage.setItem("brain-density", action.v);
      return { ...state, density: action.v };
    }
    case "set_rail_mode": {
      localStorage.setItem("brain-rail", action.v);
      return { ...state, railMode: action.v };
    }
    case "toggle_rail": return { ...state, railOpen: !state.railOpen };
    case "set_active_thread": return { ...state, activeThread: action.v };
    case "set_auto": return { ...state, autonomousMode: action.v };
    case "toggle_auto_cat":
      return { ...state, auto: { ...state.auto, [action.k]: !state.auto[action.k] } };
    case "set_drag": return { ...state, draggingFile: action.v };
    case "toast": {
      const t = { ...action.t, id: Date.now() + Math.random() };
      return { ...state, toasts: [...state.toasts, t] };
    }
    case "dismiss_toast":
      return { ...state, toasts: state.toasts.filter(t => t.id !== action.id) };
    case "send_turn": {
      const userMsg = { role: "user", ts: new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}), body: action.text };
      const asstMsg = { role: "brain", ts: new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}), body: "", mode: state.mode, toolCalls: [] };
      return { ...state, transcript: [...state.transcript, userMsg, asstMsg], streaming: true, streamingText: "", ctxPct: Math.min(100, state.ctxPct + 3) };
    }
    case "stream_delta":
      return { ...state, streamingText: state.streamingText + action.t };
    case "stream_end": {
      const t = [...state.transcript];
      const last = { ...t[t.length - 1], body: state.streamingText, cost: 0.018 };
      t[t.length - 1] = last;
      return { ...state, transcript: t, streaming: false, streamingText: "", costToday: state.costToday + 0.018 };
    }
    case "cancel_turn":
      return { ...state, streaming: false, streamingText: "", toasts: [...state.toasts, { id: Date.now(), lead: "Cancelled.", msg: "That turn was stopped.", icon: "stop" }] };
    case "approve": {
      const approved = state.patches.find(p => p.id === action.id);
      if (!approved) return state;
      const remaining = state.patches.filter(p => p.id !== action.id);
      const toast = { id: Date.now(), lead: "Applied.", msg: `${approved.target}`, icon: "check", countdown: 5, undo: () => {} };
      return { ...state, patches: remaining, toasts: [...state.toasts, toast] };
    }
    case "reject": {
      const remaining = state.patches.filter(p => p.id !== action.id);
      return { ...state, patches: remaining, toasts: [...state.toasts, { id: Date.now(), lead: "Rejected.", msg: "Patch discarded.", icon: "x" }] };
    }
    case "add_patch":
      return { ...state, patches: [action.patch, ...state.patches] };
    case "drop_file": {
      const s = { id: "s-" + Date.now(), title: "Dropped file.pdf", type: "pdf", status: "classifying", progress: 20, domain: null, cost: 0, time: "just now" };
      return { ...state, sources: [s, ...state.sources], toasts: [...state.toasts, { id: Date.now(), lead: "Ingesting.", msg: "Classifying…", icon: "inbox" }], draggingFile: false };
    }
    case "close_setup": {
      localStorage.setItem("brain-setup-done", "1");
      return { ...state, showSetup: false };
    }
    case "toggle_tweaks":
      return { ...state, showTweaks: !state.showTweaks };
    default: return state;
  }
}

function App() {
  const [state, dispatch] = React.useReducer(reducer, initialState);

  // Apply theme + density to root
  React.useEffect(() => { document.documentElement.dataset.theme = state.theme; }, [state.theme]);
  React.useEffect(() => { document.documentElement.dataset.density = state.density; }, [state.density]);

  // Expose store for leaf access
  React.useEffect(() => {
    window.brainStore = {
      setView: (v) => dispatch({ type: "set_view", v }),
      dispatch,
    };
  }, []);

  // Edit-mode / Tweaks protocol
  React.useEffect(() => {
    const onMsg = (e) => {
      if (e.data?.type === "__activate_edit_mode") dispatch({ type: "toggle_tweaks" });
      if (e.data?.type === "__deactivate_edit_mode") dispatch({ type: "toggle_tweaks" });
    };
    window.addEventListener("message", onMsg);
    try { window.parent.postMessage({ type: "__edit_mode_available" }, "*"); } catch {}
    return () => window.removeEventListener("message", onMsg);
  }, []);

  // Streaming simulator
  const streamRef = React.useRef();
  React.useEffect(() => {
    if (!state.streaming) return;
    const reply = `Here's what I'm seeing in the vault on that angle.

I pulled the most recent **conflict-identification** concept notes and cross-referenced them with this month's calls. Three signals match what you asked about — the [[loop-in-stall]] pattern shows up clearest in ACME and Helios, where a new stakeholder appeared late and the champion went quiet.

I can stage a synthesis note at \`work/synthesis/2026-04-deal-stall-patterns.md\` that cross-links all four source calls into the three pattern concepts. Want me to draft it?`;
    let i = 0;
    const step = () => {
      if (!state.streaming) return;
      i += 3 + Math.floor(Math.random() * 4);
      if (i >= reply.length) {
        dispatch({ type: "stream_delta", t: reply.slice(0, reply.length).slice(state.streamingText.length) });
        dispatch({ type: "stream_end" });
        // After stream end, stage a fake patch after a beat
        setTimeout(() => {
          const patch = {
            id: "p-" + Date.now(),
            tool: "brain_propose_note",
            target: "work/synthesis/2026-04-deal-stall-patterns.md",
            reason: "Cross-links the four April stall-pattern call sources into three recurring concepts. Staged from the current chat.",
            createdAt: "just now",
            domain: "work", mode: state.mode, fromThread: state.activeThread,
            isNew: true,
            diff: window.SEED.patches[0].diff,
          };
          dispatch({ type: "add_patch", patch });
          dispatch({ type: "toast", t: { lead: "Patch staged.", msg: "A new synthesis note is pending your review.", icon: "diff" } });
        }, 600);
        return;
      }
      dispatch({ type: "stream_delta", t: reply.slice(state.streamingText.length, i) });
      streamRef.current = setTimeout(step, 22 + Math.random() * 20);
    };
    streamRef.current = setTimeout(step, 150);
    return () => clearTimeout(streamRef.current);
  }, [state.streaming]);

  // Auto-dismiss toasts after 6s
  React.useEffect(() => {
    if (state.toasts.length === 0) return;
    const last = state.toasts[state.toasts.length - 1];
    const t = setTimeout(() => dispatch({ type: "dismiss_toast", id: last.id }), 6000);
    return () => clearTimeout(t);
  }, [state.toasts.length]);

  const setView = (v) => dispatch({ type: "set_view", v });
  const setTheme = (v) => dispatch({ type: "set_theme", v });
  const setMode = (v) => dispatch({ type: "set_mode", v });
  const setScope = (v) => dispatch({ type: "set_scope", v });

  const railContent = (() => {
    if (state.view === "chat") {
      return <PendingRail
        patches={state.patches}
        auto={state.autonomousMode}
        setAuto={(v) => dispatch({ type: "set_auto", v })}
        onApprove={(p) => dispatch({ type: "approve", id: p.id })}
        onReject={(p) => dispatch({ type: "reject", id: p.id })}
        onOpenAll={() => setView("pending")}
      />;
    }
    if (state.view === "browse") {
      return (
        <>
          <div className="rail-header"><Icon name="link" size={14} /><span className="title">Linked</span></div>
          <div style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <div className="eyebrow" style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 8 }}>Backlinks · 4</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {["silent-buyer-synthesis","2026-04-deal-stall-patterns","helios-account","polaris-intro"].map(n => (
                  <a key={n} className="wikilink" style={{ fontSize: 13 }}>{n}</a>
                ))}
              </div>
            </div>
            <div>
              <div className="eyebrow" style={{ fontSize: 10, color: "var(--text-dim)", marginBottom: 8 }}>Outlinks · 2</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {["fisher-ury-interests","silent-buyer-synthesis"].map(n => (
                  <a key={n} className="wikilink" style={{ fontSize: 13 }}>{n}</a>
                ))}
              </div>
            </div>
          </div>
        </>
      );
    }
    return null;
  })();

  const showRail = state.railOpen && railContent && (state.railMode !== "badge" || state.view === "chat");

  return (
    <>
      {state.showSetup && (
        <SetupWizard
          onDone={() => dispatch({ type: "close_setup" })}
          onSkip={() => dispatch({ type: "close_setup" })}
        />
      )}
      <div className="app">
        <Topbar
          scope={state.scope} setScope={setScope}
          view={state.view}
          activeThread={state.activeThread}
          mode={state.mode} setMode={setMode}
          costToday={state.costToday} budget={state.budget}
          theme={state.theme} setTheme={setTheme}
          toggleRail={() => dispatch({ type: "toggle_rail" })}
          railOpen={state.railOpen}
        />
        <LeftNav
          view={state.view} setView={setView}
          pendingCount={state.patches.length}
          threads={window.SEED.threads}
          activeThread={state.activeThread}
          setActiveThread={(id) => dispatch({ type: "set_active_thread", v: id })}
        />
        <div className="main">
          {state.view === "chat" && <ChatScreen state={state} dispatch={dispatch} />}
          {state.view === "inbox" && <InboxScreen state={state} dispatch={dispatch} />}
          {state.view === "pending" && <PendingScreen state={state} dispatch={dispatch} />}
          {state.view === "browse" && <BrowseScreen state={state} />}
          {state.view === "bulk" && <BulkScreen />}
          {state.view === "settings" && <SettingsScreen state={state} dispatch={dispatch} />}
        </div>
        <div className={`rail ${showRail?"":"collapsed"}`}>{railContent}</div>
      </div>

      <Toasts toasts={state.toasts} dismiss={(id) => dispatch({ type: "dismiss_toast", id })} />

      {state.showTweaks && (
        <TweaksPanel
          theme={state.theme} setTheme={setTheme}
          density={state.density} setDensity={(v) => dispatch({ type: "set_density", v })}
          railMode={state.railMode} setRailMode={(v) => dispatch({ type: "set_rail_mode", v })}
          onClose={() => dispatch({ type: "toggle_tweaks" })}
        />
      )}
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
