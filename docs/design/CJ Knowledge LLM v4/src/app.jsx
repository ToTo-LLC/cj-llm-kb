// Main app entry — state, store, and routing

const initialTranscript = window.SEED.transcript;

const initialState = {
  view: "chat",                 // chat | inbox | pending | browse | bulk | settings
  activeThread: "t-1",
  mode: "ask",
  scope: ["research", "work"],
  theme: localStorage.getItem("brain-theme") || "dark",
  density: localStorage.getItem("brain-density") || "comfortable",
  railOpen: true,
  transcript: initialTranscript,
  streaming: false,
  streamingText: "",
  // Approximate context-fill: derived from cumulative tokens / 200k (Sonnet).
  // Not a real backend metric — we keep this display-only and mark as "≈".
  tokensUsed: 36000,
  costToday: window.SEED.costToday,
  budget: window.SEED.budgetDaily,
  patches: window.SEED.patches,
  sources: window.SEED.sources,
  autonomousMode: false,
  auto: { ingest: false, entities: false, concepts: false, index: false },
  toasts: [],
  // showTweaks removed for v3 — design-time overlay only; theme/density now live in Settings → General.
  showSetup: !localStorage.getItem("brain-setup-done"),
  draggingFile: false,
  sys: {
    connection: "ok",       // ok | reconnecting | offline
    budgetWall: false,
    typedConfirm: null,     // { word, title, eyebrow, body, onConfirm }
    rejectPatch: null,      // a patch object
    editPatch: null,        // a patch object
    midTurn: null,          // 'rate-limit' | 'context-full' | 'tool-failed'
    fileToWiki: null,       // { msg, thread }
    forkDialog: null,       // { thread, turnIndex, msg? }
    renameDomain: null,     // { domain }
  },
  // Draft mode: the doc you're collaborating on. Null = show empty prompt.
  // Shape: { path, domain, body, frontmatter, pendingEdits: [{op, text, anchor}] }
  activeDoc: null,
};

function reducer(state, action) {
  switch (action.type) {
    case "set_view": return { ...state, view: action.v };
    case "set_mode": {
      // Mid-turn switches are rejected server-side with invalid_state — mirror that in UI.
      if (state.streaming) {
        return { ...state, sys: { ...state.sys, midTurn: "invalid-state-mode" } };
      }
      return { ...state, mode: action.v };
    }
    case "set_scope": return { ...state, scope: action.v };
    case "set_theme": {
      localStorage.setItem("brain-theme", action.v);
      return { ...state, theme: action.v };
    }
    case "set_density": {
      localStorage.setItem("brain-density", action.v);
      return { ...state, density: action.v };
    }
    case "toggle_rail": return { ...state, railOpen: !state.railOpen };
    case "set_active_thread": {
      // Switching threads clears the transcript. For "New chat" (null id), we also reset
      // the composer context — new thread_id materializes on first send.
      return { ...state, activeThread: action.v, transcript: action.v ? initialTranscript : [], streaming: false, streamingText: "" };
    }
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
      // Server rejects turn_start while a turn is active — show the mid-turn warn instead.
      if (state.streaming) {
        return { ...state, sys: { ...state.sys, midTurn: "invalid-state-turn" } };
      }
      const userMsg = { role: "user", ts: new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}), body: action.text };
      const asstMsg = { role: "brain", ts: new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}), body: "", mode: state.mode, toolCalls: [] };
      return { ...state, transcript: [...state.transcript, userMsg, asstMsg], streaming: true, streamingText: "", tokensUsed: state.tokensUsed + 4200 };
    }
    case "stream_delta":
      return { ...state, streamingText: state.streamingText + action.t };
    case "stream_end": {
      const t = [...state.transcript];
      const last = { ...t[t.length - 1], body: state.streamingText, cost: 0.018 };
      t[t.length - 1] = last;
      // Auto-dismiss any invalid-state mid-turn warn on completion.
      const sys = (state.sys?.midTurn === "invalid-state-turn" || state.sys?.midTurn === "invalid-state-mode")
        ? { ...state.sys, midTurn: null } : state.sys;
      return { ...state, transcript: t, streaming: false, streamingText: "", costToday: state.costToday + 0.018, sys };
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
    case "sys_open":
      return { ...state, sys: { ...state.sys, [action.k]: action.v } };
    case "sys_close":
      return { ...state, sys: { ...state.sys, [action.k]: action.k === "connection" ? "ok" : null } };
    case "set_connection":
      return { ...state, sys: { ...state.sys, connection: action.v } };
    case "raise_budget":
      return { ...state, budget: state.budget + 5, sys: { ...state.sys, budgetWall: false }, toasts: [...state.toasts, { id: Date.now(), lead: "Cap raised.", msg: `Today's cap is now $${(state.budget+5).toFixed(2)}.`, icon: "check" }] };
    case "open_doc":
      return { ...state, activeDoc: action.doc, mode: "draft" };
    case "close_doc":
      return { ...state, activeDoc: null };
    case "apply_doc_edits":
      return { ...state, activeDoc: state.activeDoc ? { ...state.activeDoc, body: action.body, pendingEdits: [] } : null, toasts: [...state.toasts, { id: Date.now(), lead: "Applied.", msg: "Edits merged into your draft.", icon: "check" } ] };
    case "reject_doc_edits":
      return { ...state, activeDoc: state.activeDoc ? { ...state.activeDoc, pendingEdits: [] } : null };
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

  // Edit-mode listener kept as a no-op — v3 removed the Tweaks panel (design-time only).
  // If the design host sends an activate message we simply acknowledge availability.
  React.useEffect(() => {
    try { window.parent.postMessage({ type: "__edit_mode_available" }, "*"); } catch {}
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

  const showRail = state.railOpen && railContent && !state.activeDoc;

  return (
    <>
      {state.showSetup && (
        <SetupWizard
          onDone={() => dispatch({ type: "close_setup" })}
          onSkip={() => dispatch({ type: "close_setup" })}
        />
      )}
      <div
        className="app"
        onDragEnter={(e) => { if (e.dataTransfer?.types?.includes("Files")) dispatch({ type: "set_drag", v: true }); }}
        onDragOver={(e) => { if (e.dataTransfer?.types?.includes("Files")) { e.preventDefault(); } }}
        onDragLeave={(e) => { if (e.relatedTarget === null) dispatch({ type: "set_drag", v: false }); }}
        onDrop={(e) => { e.preventDefault(); if (state.draggingFile) dispatch({ type: "drop_file" }); }}
      >
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

      <SystemOverlays state={state} dispatch={dispatch} />
    </>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
