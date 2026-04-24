// Chat screen — streaming, tool calls, patches, composer

const WIKILINK_RE = /\[\[([^\]]+)\]\]/g;

const renderBody = (text) => {
  // Split by paragraphs
  const parts = text.split(/\n\n+/);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**") && !p.slice(2).includes("**")) {
      return <p key={i}><strong>{p.slice(2, -2)}</strong></p>;
    }
    // Inline wikilinks + bold
    const nodes = [];
    let remaining = p;
    let key = 0;
    const regex = /(\[\[[^\]]+\]\]|\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
    let lastIdx = 0;
    let m;
    while ((m = regex.exec(remaining)) !== null) {
      if (m.index > lastIdx) nodes.push(remaining.slice(lastIdx, m.index));
      const tok = m[0];
      if (tok.startsWith("[[")) {
        const label = tok.slice(2, -2);
        const broken = label === "future-work";
        nodes.push(<a key={`w${key++}`} className={`wikilink ${broken?"broken":""}`} href="#">{label}</a>);
      } else if (tok.startsWith("**")) {
        nodes.push(<strong key={`b${key++}`}>{tok.slice(2,-2)}</strong>);
      } else if (tok.startsWith("`")) {
        nodes.push(<code key={`c${key++}`}>{tok.slice(1,-1)}</code>);
      } else if (tok.startsWith("*")) {
        nodes.push(<em key={`i${key++}`}>{tok.slice(1,-1)}</em>);
      }
      lastIdx = m.index + tok.length;
    }
    if (lastIdx < remaining.length) nodes.push(remaining.slice(lastIdx));
    return <p key={i}>{nodes}</p>;
  });
};

const ToolCall = ({ call, defaultOpen }) => {
  const [open, setOpen] = React.useState(defaultOpen);
  const argStr = Object.entries(call.args).map(([k,v]) => `${k}: ${JSON.stringify(v)}`).join(", ");
  return (
    <div className={`tool-card ${open?"open":""}`}>
      <div className="tool-head" onClick={() => setOpen(!open)}>
        <Icon name="bolt" size={12} />
        <span className="tname">{call.tool}</span>
        <span className="arg">({argStr})</span>
        <span className="caret"><Icon name="caret" size={12} /></span>
      </div>
      <div className="tool-body">
        {call.result?.hits && call.result.hits.map((h, i) => (
          <div key={i} className="result-hit">
            <span className="score">{h.score.toFixed(2)}</span>
            <span className="path">{h.path}</span>
            <span className="snip">{h.snippet}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const Message = ({ msg, onFile, onFork, streamingText, isStreaming }) => {
  const isUser = msg.role === "user";
  const mode = msg.mode || "ask";
  const modeLabel = { ask: "Ask", brainstorm: "Brainstorm", draft: "Draft" }[mode];
  const body = isStreaming ? streamingText : msg.body;
  return (
    <div className="msg-row">
      <div className={`msg-role ${isUser?"user":"brain"}`}>
        <div className="avatar">{isUser ? "CJ" : ""}</div>
        <span>{isUser ? "You" : "brain"}</span>
        {!isUser && <span className="chip" style={{ height: 18, padding: "0 6px", fontSize: 10 }}>{modeLabel}</span>}
        <span className="ts">{msg.ts}</span>
        {msg.cost && <span className="ts">· ${msg.cost.toFixed(3)}</span>}
      </div>
      <div className="msg-body">
        {!isUser && msg.toolCalls && msg.toolCalls.map((c, i) => <ToolCall key={i} call={c} />)}
        {renderBody(body || "")}
        {isStreaming && <span className="stream-caret" />}
        {!isUser && msg.proposedPatch && (
          <div className="inline-patch">
            <Icon name="diff" size={14} className="ico" />
            <span className="reason">Staged a new note at</span>
            <span className="tpath">{msg.proposedPatch.target}</span>
            <span className="spacer" />
            <button className="btn primary mini-btn sm">Review in panel →</button>
          </div>
        )}
      </div>
      {!isUser && !isStreaming && (
        <div className="msg-actions">
          <button onClick={() => onFile(msg)}><Icon name="flag" size={12} /> File to wiki</button>
          <button onClick={() => onFork(msg)}><Icon name="fork" size={12} /> Fork from here</button>
          <button><Icon name="copy" size={12} /> Copy</button>
          <button><Icon name="quote" size={12} /> Quote</button>
        </div>
      )}
    </div>
  );
};

const Composer = ({ mode, scope, onSend, streaming, onCancel, tokensUsed }) => {
  const [text, setText] = React.useState("");
  const [focus, setFocus] = React.useState(false);
  const ref = React.useRef();

  // Approximate context fill — backend doesn't emit a ratio, so we derive from tokens
  // and mark visually as an estimate ("≈"). Sonnet's 200k window is the denominator.
  const MAX_CTX = 200000;
  const ctxPct = Math.min(100, Math.round((tokensUsed / MAX_CTX) * 100));

  const placeholders = {
    ask: "Ask the vault — it will cite what it uses…",
    brainstorm: "Bring a half-formed idea — brain will push back and co-develop…",
    draft: "Open a document and collaborate inline…",
  };

  const autosize = () => {
    if (!ref.current) return;
    ref.current.style.height = "auto";
    ref.current.style.height = Math.min(220, ref.current.scrollHeight) + "px";
  };

  const handle = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (text.trim() && !streaming) { onSend(text); setText(""); setTimeout(autosize, 0); }
    }
  };

  return (
    <div className="composer-wrap">
      <div className={`composer ${focus?"focus":""}`}>
        <textarea
          ref={ref}
          placeholder={placeholders[mode]}
          value={text}
          onChange={e => { setText(e.target.value); autosize(); }}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          onKeyDown={handle}
          rows={1}
        />
        <div className="composer-toolbar">
          <div className="left">
            <span className={`chip dom-${scope[0]||"research"}`} style={{ height: 22 }}>
              <Icon name="layers" size={11} />
              {scope.length === 0 ? "no scope" : scope.length === 1 ? scope[0] : `${scope.length} domains`}
              {scope.includes("personal") && <Icon name="lock" size={10} />}
            </span>
            <button className="iconbtn" title="Attach"><Icon name="paperclip" size={14} /></button>
            <div className="ctx-meter" title={`~${tokensUsed.toLocaleString()} of ${(MAX_CTX/1000)|0}k tokens`}>
              <span>context</span>
              <div className="ctx-bar"><span style={{ width: `${ctxPct}%` }} /></div>
              <span>≈{ctxPct}%</span>
            </div>
          </div>
          <div className="right">
            {streaming ? (
              <button className="send-btn cancel" onClick={onCancel} title="Cancel">
                <Icon name="stop" size={14} />
              </button>
            ) : (
              <button className="send-btn" disabled={!text.trim()} onClick={() => { if(text.trim()){ onSend(text); setText(""); setTimeout(autosize,0);} }}>
                <Icon name="send" size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

const NewThreadEmpty = ({ mode, scope, onPrompt }) => {
  const modes = {
    ask:        { lead: "Ask",        desc: "cite from the vault",              tone: "var(--tt-cyan)" },
    brainstorm: { lead: "Brainstorm", desc: "push back, propose notes",         tone: "var(--tt-cream)" },
    draft:      { lead: "Draft",      desc: "collaborate on a document",        tone: "var(--tt-sage)" },
  };
  const starters = {
    ask: [
      "What has the vault said this year about silent-buyer patterns?",
      "Cross-reference Fisher-Ury with the April Helios call.",
      "Summarize concepts tagged #decision-theory · last 30 days.",
    ],
    brainstorm: [
      "Argue with me about compounding curiosity as a meta-practice.",
      "What am I missing in the deal-stall pattern synthesis?",
      "Propose three angles I haven't considered on tactical empathy.",
    ],
    draft: [
      "Rewrite the intro to fisher-ury-interests.md for a non-expert reader.",
      "Draft a board-memo section on Q2 research threads.",
      "Turn the silent-buyer synthesis into a short public post.",
    ],
  };
  const m = modes[mode];
  const domainNames = scope.map(id => (window.SEED.domains.find(d => d.id === id) || {}).name || id);
  const scopeLabel = scope.length === 0 ? "No domain selected"
    : scope.length === window.SEED.domains.length ? "All domains"
    : domainNames.join(" + ");

  return (
    <div className="nt-empty">
      <div className="nt-orbs" />
      <div className="nt-card">
        <div className="nt-eyebrow">New thread</div>
        <h1 className="nt-title">What are we working on?</h1>
        <div className="nt-meta">
          <div className="nt-meta-row">
            <span className="nt-label">Scope</span>
            <div className="nt-scope">
              {scope.length === 0 ? <span className="dim">No domain selected — pick one in the topbar.</span> : (
                <>
                  {scope.map(id => (
                    <span key={id} className={`chip dom-${id}`} style={{ height: 20 }}>
                      <span className="dot" style={{ width: 6, height: 6, borderRadius: 999, background: `var(--dom-${id})` }} />
                      {(window.SEED.domains.find(d => d.id === id) || {}).name || id}
                      {id === "personal" && <Icon name="lock" size={9} />}
                    </span>
                  ))}
                  <span className="dim" style={{ fontSize: 11 }}>brain will draw only from {scope.length === 1 ? "this domain" : "these domains"}.</span>
                </>
              )}
            </div>
          </div>
          <div className="nt-meta-row">
            <span className="nt-label">Mode</span>
            <div className="nt-mode" style={{ ["--mode-tone"]: m.tone }}>
              <span className="nt-mode-dot" />
              <strong>{m.lead}</strong>
              <span className="dim"> · {m.desc}</span>
            </div>
          </div>
        </div>

        <div className="nt-starters-label">Starter prompts</div>
        <div className="nt-starters">
          {starters[mode].map((p, i) => (
            <button key={i} className="nt-starter" onClick={() => onPrompt(p)}>
              <Icon name="quote" size={11} />
              <span>{p}</span>
              <Icon name="caret" size={11} style={{ transform: "rotate(-90deg)", opacity: 0.5 }} />
            </button>
          ))}
        </div>

        <div className="nt-tip">
          <Icon name="info" size={11} />
          <span>Your first message becomes the thread title. brain uses <code>BRAIN.md</code> as its system prompt.</span>
        </div>
      </div>
    </div>
  );
};

const ChatScreen = ({ state, dispatch }) => {
  const { transcript, streaming, mode, scope, draggingFile, activeDoc } = state;
  const isNewThread = !state.activeThread || transcript.length === 0;
  const thread = window.SEED.threads.find(t => t.id === state.activeThread) || (isNewThread ? null : window.SEED.threads[0]);
  const transcriptRef = React.useRef();
  const [pickerOpen, setPickerOpen] = React.useState(false);

  React.useEffect(() => {
    if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
  }, [transcript, state.streamingText]);

  const send = (text) => dispatch({ type: "send_turn", text });

  // In draft mode: if we have an active doc, render the split layout;
  // if we have no doc, render the empty prompt inside the transcript area.
  const inDraftMode = mode === "draft";
  const showDocPanel = inDraftMode && !!activeDoc;

  const chatInner = (
    <div className="chat" onDragEnter={() => dispatch({ type: "set_drag", v: true })}>
      {draggingFile && (
        <div className="drop-overlay" onDragLeave={() => dispatch({ type: "set_drag", v: false })}>
          <div style={{ textAlign: "center" }}>
            <Icon name="upload" size={32} />
            <div style={{ marginTop: 12 }}>Drop to attach to this turn</div>
          </div>
        </div>
      )}

      <div className="chat-sub">
        {thread ? (
          <>
            <div className="thread-title">
              <Icon name="chat" size={14} />
              <span>{thread.title}</span>
              <span className="sep">·</span>
              <span className="t-status">{thread.turns || 0} turns · ${(thread.cost||0).toFixed(3)}</span>
            </div>
            <div className="spacer" />
            <button className="iconbtn" title="Export"><Icon name="upload" size={14} /></button>
            <button className="iconbtn" title="Fork" onClick={() => dispatch({ type: "sys_open", k: "forkDialog", v: { thread, turnIndex: Math.max(0, transcript.length - 2) } })}><Icon name="fork" size={14} /></button>
          </>
        ) : (
          <>
            <div className="thread-title">
              <Icon name="plus" size={14} />
              <span className="dim" style={{ fontWeight: 400 }}>New thread · untitled</span>
              <span className="sep">·</span>
              <span className="t-status">brain will name it after your first message</span>
            </div>
            <div className="spacer" />
          </>
        )}
      </div>

      <div className="transcript" ref={transcriptRef}>
        <div className="transcript-inner">
          {inDraftMode && !activeDoc ? (
            <DraftEmpty
              onPick={() => setPickerOpen(true)}
              onNewDoc={() => dispatch({ type: "open_doc", doc: makeScratchDoc(scope[0] || "work") })}
            />
          ) : isNewThread ? (
            <NewThreadEmpty
              mode={mode}
              scope={scope}
              onPrompt={(p) => dispatch({ type: "send_turn", text: p })}
            />
          ) : (
            transcript.map((m, i) => (
              <Message key={i} msg={m}
                streamingText={i === transcript.length - 1 && streaming ? state.streamingText : null}
                isStreaming={i === transcript.length - 1 && streaming}
                onFile={() => dispatch({ type: "sys_open", k: "fileToWiki", v: { msg: m, thread } })}
                onFork={() => dispatch({ type: "sys_open", k: "forkDialog", v: { thread, turnIndex: i, msg: m } })}
              />
            ))
          )}
        </div>
      </div>

      <Composer mode={mode} scope={scope} streaming={streaming}
        onSend={send}
        onCancel={() => dispatch({ type: "cancel_turn" })}
        tokensUsed={state.tokensUsed} />
    </div>
  );

  return (
    <>
      {showDocPanel ? (
        <div className="chat-with-doc">
          {chatInner}
          <DocPanel
            doc={activeDoc}
            onClose={() => dispatch({ type: "close_doc" })}
            onChangeDoc={() => setPickerOpen(true)}
            onApplyEdits={() => {
              const cleanBody = (activeDoc.body || "").replace(/⟦\+([^⟧]+)⟧/g, "$1").replace(/⟦-[^⟧]+⟧/g, "");
              dispatch({ type: "apply_doc_edits", body: cleanBody });
            }}
            onRejectEdits={() => {
              const cleanBody = (activeDoc.body || "").replace(/⟦\+[^⟧]+⟧/g, "").replace(/⟦-([^⟧]+)⟧/g, "$1");
              dispatch({ type: "apply_doc_edits", body: cleanBody });
            }}
          />
        </div>
      ) : chatInner}

      <DocPickerDialog
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onPick={(entry) => { dispatch({ type: "open_doc", doc: makeSampleDoc(entry) }); setPickerOpen(false); }}
        onNewBlank={() => { dispatch({ type: "open_doc", doc: makeScratchDoc(scope[0] || "work") }); setPickerOpen(false); }}
      />
    </>
  );
};

Object.assign(window, { ChatScreen });
