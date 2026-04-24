// Pending changes screen + rail

const PatchCard = ({ patch, selected, onSelect, onApprove, onReject, isInRail }) => {
  const dom = patch.domain;
  return (
    <div className={`patch-card ${selected?"selected":""}`} onClick={() => onSelect(patch.id)}>
      {patch.isNew && <div className="patch-bell">!</div>}
      <div className="p-head">
        <span className="p-tool">{patch.tool.replace("brain_", "")}</span>
        <span className={`chip dom-${dom}`} style={{ height: 18, padding: "0 7px", fontSize: 10 }}>
          {dom === "personal" && <Icon name="lock" size={9} />}
          {dom}
        </span>
        <span className="p-ts">{patch.createdAt}</span>
      </div>
      <div className="p-path">{patch.target}</div>
      <div className="p-reason">{patch.reason}</div>
      <div className="p-actions">
        <button className="tiny p-approve" onClick={(e) => { e.stopPropagation(); onApprove(patch); }}>
          <Icon name="check" size={12} /> Approve
        </button>
        <button className="tiny p-edit" onClick={(e) => e.stopPropagation()}>
          <Icon name="edit" size={12} /> Edit
        </button>
        <button className="tiny p-reject" onClick={(e) => { e.stopPropagation(); onReject(patch); }}>
          <Icon name="x" size={12} /> Reject
        </button>
      </div>
    </div>
  );
};

const PendingRail = ({ patches, auto, setAuto, onApprove, onReject, onOpenAll }) => {
  if (patches.length === 0) {
    return (
      <>
        <div className="rail-header">
          <Icon name="diff" size={14} />
          <span className="title">Pending</span>
          <span className="count">0</span>
        </div>
        <div className="rail-empty">
          <div className="orb" />
          <div style={{ fontSize: 14, color: "var(--text-muted)", marginBottom: 4 }}>All clear.</div>
          <div>brain isn't proposing anything right now. Ingest a source or start a chat to stage new changes.</div>
        </div>
      </>
    );
  }
  return (
    <>
      <div className="rail-header">
        <Icon name="diff" size={14} />
        <span className="title">Pending</span>
        <span className="count">{patches.length}</span>
        <button className="iconbtn" onClick={onOpenAll} title="Open full view"><Icon name="caret" size={12} /></button>
      </div>
      <div className={`auto-banner ${auto?"":"off"}`}>
        <Icon name="alert" size={14} />
        <div>
          <strong>Autonomous mode is on.</strong> New ingest & entity patches apply without review.
        </div>
      </div>
      <div className="rail-pending">
        {patches.map(p => (
          <PatchCard key={p.id} patch={p} selected={false}
            onSelect={() => {}}
            onApprove={onApprove} onReject={onReject} isInRail />
        ))}
      </div>
    </>
  );
};

const PendingScreen = ({ state, dispatch }) => {
  const [sel, setSel] = React.useState(state.patches[0]?.id);
  const [filter, setFilter] = React.useState("all");
  const patches = state.patches.filter(p => filter === "all" || p.tool.includes(filter));
  const selected = patches.find(p => p.id === sel) || patches[0];

  return (
    <div className="pending-screen">
      <div className="page-header">
        <div className="titles">
          <div className="eyebrow">Your approval queue</div>
          <h1>Pending Changes <span className="cnt">· {state.patches.length}</span></h1>
        </div>
        <div className="actions">
          <div className={`autonomous-switch ${state.autonomousMode?"on":""}`}>
            <div className={`switch ${state.autonomousMode?"on danger":""}`}
                 onClick={() => dispatch({ type: "set_auto", v: !state.autonomousMode })} />
            <div>
              <div style={{ fontSize: 12 }}>Autonomous mode</div>
              <div style={{ fontSize: 10, color: "var(--text-dim)" }}>
                {state.autonomousMode ? <span className="warn">brain writes without review</span> : "every change staged"}
              </div>
            </div>
          </div>
          <button className="btn ghost"><Icon name="undo" size={13} /> Undo last</button>
          <button className="btn ghost">Reject all</button>
          <button className="btn primary"><Icon name="check" size={13} /> Approve all ({patches.length})</button>
        </div>
      </div>

      <div className="pending-content">
        <div className="pending-list-col">
          <div className="filter-bar">
            {[
              { k: "all", l: "All" },
              { k: "propose_note", l: "Notes" },
              { k: "ingest", l: "Ingested" },
            ].map(f => (
              <div key={f.k} className={`chip ${filter===f.k?"on":""}`} onClick={() => setFilter(f.k)} style={{ cursor: "pointer" }}>
                {f.l}
              </div>
            ))}
          </div>
          {patches.map(p => (
            <PatchCard key={p.id} patch={p} selected={selected?.id === p.id}
              onSelect={setSel}
              onApprove={(pp) => dispatch({ type: "approve", id: pp.id })}
              onReject={(pp) => dispatch({ type: "reject", id: pp.id })} />
          ))}
        </div>

        <div className="pending-detail-col">
          {selected && (
            <>
              <div className="detail-section">
                <div className="s-eyebrow">Target path</div>
                <div className="target-path">{selected.target}</div>
              </div>
              <div className="detail-section">
                <div className="s-eyebrow">Why</div>
                <div className="big-reason">{selected.reason}</div>
              </div>
              <div className="detail-section">
                <div className="s-eyebrow">Diff · {selected.diff.filter(l=>l.type==="add").length} added, {selected.diff.filter(l=>l.type==="del").length} removed</div>
                <div className="diff">
                  <div className="diff-head">
                    <Icon name="file" size={14} /> <span>{selected.target}</span>
                    <span className="spacer" />
                    <span className="dim" style={{ fontSize: 11 }}>read-only preview</span>
                  </div>
                  <div className="diff-body">
                    {selected.diff.map((l, i) => (
                      <div key={i} className={`diff-line ${l.type}`}>
                        <span className="gutter">{l.type === "add" ? "" : l.n}</span>
                        <span className="gutter">{l.type === "del" ? "" : l.n}</span>
                        <span className="code">{l.code}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {selected.fromThread && (
                <div className="detail-section">
                  <div className="s-eyebrow">Source</div>
                  <div className="chip" style={{ height: 26 }}>
                    <Icon name="chat" size={11} />
                    <span>Chat: {window.SEED.threads.find(t=>t.id===selected.fromThread)?.title}</span>
                  </div>
                </div>
              )}

              <div className="detail-actions">
                <button className="btn primary lg" onClick={() => dispatch({ type: "approve", id: selected.id })}>
                  <Icon name="check" size={14} /> Approve & write to vault
                </button>
                <button className="btn ghost lg" onClick={() => dispatch({ type: "sys_open", k: "editPatch", v: selected })}>
                  <Icon name="edit" size={14} /> Edit, then approve
                </button>
                <div className="spacer" style={{ flex: 1 }} />
                <button className="btn danger lg" onClick={() => dispatch({ type: "sys_open", k: "rejectPatch", v: selected })}>
                  Reject with reason
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { PendingScreen, PendingRail, PatchCard });
