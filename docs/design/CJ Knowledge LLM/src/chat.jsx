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

const Composer = ({ mode, scope, onSend, streaming, onCancel, ctxPct }) => {
  const [text, setText] = React.useState("");
  const [focus, setFocus] = React.useState(false);
  const ref = React.useRef();

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
            <div className="ctx-meter">
              <span>context</span>
              <div className="ctx-bar"><span style={{ width: `${ctxPct}%` }} /></div>
              <span>{ctxPct}%</span>
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

const ChatScreen = ({ state, dispatch }) => {
  const { transcript, streaming, mode, scope, draggingFile } = state;
  const thread = window.SEED.threads.find(t => t.id === state.activeThread) || window.SEED.threads[0];
  const transcriptRef = React.useRef();

  React.useEffect(() => {
    if (transcriptRef.current) transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
  }, [transcript, state.streamingText]);

  const send = (text) => dispatch({ type: "send_turn", text });

  return (
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
        <div className="thread-title">
          <Icon name="chat" size={14} />
          <span>{thread.title}</span>
          <span className="sep">·</span>
          <span className="t-status">{thread.turns || 0} turns · ${(thread.cost||0).toFixed(3)}</span>
        </div>
        <div className="spacer" />
        <button className="iconbtn" title="Export"><Icon name="upload" size={14} /></button>
        <button className="iconbtn" title="Fork"><Icon name="fork" size={14} /></button>
      </div>

      <div className="transcript" ref={transcriptRef}>
        <div className="transcript-inner">
          {transcript.map((m, i) => (
            <Message key={i} msg={m}
              streamingText={i === transcript.length - 1 && streaming ? state.streamingText : null}
              isStreaming={i === transcript.length - 1 && streaming}
              onFile={() => dispatch({ type: "open_file_to_wiki", msg: m })}
              onFork={() => dispatch({ type: "toast", t: { lead: "Forked", msg: `from turn ${i+1}.`, icon: "fork" } })}
            />
          ))}
        </div>
      </div>

      <Composer mode={mode} scope={scope} streaming={streaming}
        onSend={send}
        onCancel={() => dispatch({ type: "cancel_turn" })}
        ctxPct={state.ctxPct} />
    </div>
  );
};

Object.assign(window, { ChatScreen });
