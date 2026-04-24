// Bulk import — 4-step flow (pick → scope → dry-run → apply)

const bulkFixture = [
  // folder of 47 files mixed meeting notes, pdfs, txt exports
  { id: 1,  name: "2025-09-03 — weekly exec notes.md", type: "text", size: "4.2 KB", classified: "work",     confidence: 0.92, include: true,  dup: false },
  { id: 2,  name: "2025-09-10 — weekly exec notes.md", type: "text", size: "3.8 KB", classified: "work",     confidence: 0.94, include: true,  dup: false },
  { id: 3,  name: "2025-09-17 — weekly exec notes.md", type: "text", size: "5.1 KB", classified: "work",     confidence: 0.93, include: true,  dup: false },
  { id: 4,  name: "huberman-decision-notes.md",       type: "text",  size: "11 KB",  classified: "research", confidence: 0.88, include: true,  dup: false },
  { id: 5,  name: "Fisher-Ury-ch3.pdf",                 type: "pdf",  size: "742 KB", classified: "research", confidence: 0.97, include: true,  dup: false },
  { id: 6,  name: "acme-q2-call.txt",                   type: "text", size: "22 KB",  classified: "work",     confidence: 0.91, include: true,  dup: true  },
  { id: 7,  name: "journal-2025-09.md",                 type: "text", size: "8.1 KB", classified: "personal", confidence: 0.86, include: true,  dup: false, flagged: "personal" },
  { id: 8,  name: "journal-2025-10.md",                 type: "text", size: "9.3 KB", classified: "personal", confidence: 0.89, include: true,  dup: false, flagged: "personal" },
  { id: 9,  name: "quarterly-retro.docx",               type: "doc",  size: "34 KB",  classified: "work",     confidence: 0.62, include: true,  dup: false, uncertain: true },
  { id: 10, name: "reading-list-screenshot.png",        type: "img",  size: "1.1 MB", classified: null,      confidence: null, include: false, dup: false, skip: "Unsupported — image with no OCR." },
  { id: 11, name: "helios-renewal-thread.eml",          type: "email", size: "19 KB", classified: "work",     confidence: 0.79, include: true,  dup: false },
  { id: 12, name: "polaris-intro.eml",                  type: "email", size: "12 KB", classified: "work",     confidence: 0.82, include: true,  dup: false },
  { id: 13, name: "voss-tactical-empathy.pdf",          type: "pdf",   size: "890 KB", classified: "research", confidence: 0.95, include: true,  dup: false },
  { id: 14, name: "kahneman-system-1-2.pdf",            type: "pdf",   size: "1.2 MB", classified: "research", confidence: 0.96, include: true,  dup: false },
  { id: 15, name: "Q3-goals.md",                        type: "text", size: "2.2 KB", classified: "work",     confidence: 0.88, include: true,  dup: false },
  { id: 16, name: "Q4-goals.md",                        type: "text", size: "2.8 KB", classified: "work",     confidence: 0.87, include: true,  dup: false },
  { id: 17, name: "vestige-legal-touchbase.txt",        type: "text", size: "18 KB",  classified: "work",     confidence: 0.90, include: true,  dup: false },
  { id: 18, name: "birthday-ideas.md",                  type: "text", size: "1.4 KB", classified: "personal", confidence: 0.71, include: true,  dup: false, flagged: "personal" },
  { id: 19, name: "never-split-highlights.md",          type: "text", size: "6.7 KB", classified: "research", confidence: 0.92, include: true,  dup: false },
  { id: 20, name: ".DS_Store",                          type: "sys",   size: "6 KB",   classified: null, confidence: null, include: false, dup: false, skip: "System file — ignored." },
];

const typeIcon = (t) => {
  const m = { pdf: "PDF", text: "TXT", doc: "DOC", img: "IMG", email: "EML", url: "URL", sys: "SYS" };
  return m[t] || "FILE";
};

const BulkScreen = () => {
  const [step, setStep] = React.useState(1);
  const [folder, setFolder] = React.useState(null);
  const [domain, setDomain] = React.useState("auto"); // auto | research | work | personal
  const [files, setFiles] = React.useState(bulkFixture);
  const [cap, setCap] = React.useState(20);
  const [applying, setApplying] = React.useState(false);
  const [applyIdx, setApplyIdx] = React.useState(0);
  const [cancelled, setCancelled] = React.useState(false);
  const [done, setDone] = React.useState(false);

  const total = files.length;
  const totalEligible = files.filter(f => !f.skip).length;
  const included = files.filter(f => f.include && !f.skip);
  const skipped = files.filter(f => f.skip);

  const toggleInclude = (id) => setFiles(f => f.map(x => x.id===id ? { ...x, include: !x.include } : x));
  const setRoute = (id, newDom) => setFiles(f => f.map(x => x.id===id ? { ...x, classified: newDom, confidence: 1 } : x));

  // Simulate apply progress
  React.useEffect(() => {
    if (!applying || cancelled || done) return;
    if (applyIdx >= included.length) { setDone(true); setApplying(false); return; }
    const t = setTimeout(() => setApplyIdx(i => i + 1), 280);
    return () => clearTimeout(t);
  }, [applying, applyIdx, cancelled, done, included.length]);

  const pickFolder = () => {
    setFolder({ path: "~/Archive/old-vault", fileCount: total, picked: "just now" });
    setStep(2);
  };

  return (
    <div className="bulk-screen">
      <div className="bulk-header">
        <div className="bulk-stepper">
          {["Pick folder", "Target domain", "Dry-run review", "Apply"].map((label, i) => {
            const n = i + 1;
            return (
              <div key={n} className={`b-step ${step===n?"on":""} ${step>n?"done":""}`}>
                <div className="b-num">{step>n ? <Icon name="check" size={11} /> : n}</div>
                <div className="b-lbl">{label}</div>
              </div>
            );
          })}
        </div>
        <div className="spacer" />
        {step > 1 && !applying && !done && (
          <button className="btn ghost" onClick={() => setStep(s => Math.max(1, s-1))}>← Back</button>
        )}
      </div>

      <div className="bulk-body">
        {/* STEP 1 — pick folder */}
        {step === 1 && (
          <div className="bulk-pane center">
            <div className="b-icon"><Icon name="upload" size={36} /></div>
            <h1>Import a folder of sources.</h1>
            <p className="lead">Point brain at a year of meeting notes, a reading archive, or an old Obsidian vault. It runs a dry-run first so nothing lands in your vault without review.</p>
            <div style={{ marginTop: 28, display: "inline-flex", gap: 10 }}>
              <button className="btn primary lg" onClick={pickFolder}>
                <Icon name="folder" size={14} /> Pick a folder
              </button>
              <button className="btn ghost lg">Use a path</button>
            </div>
            <div className="quiet-row">
              <Icon name="shield" size={11} /> Files are read from disk — nothing is uploaded to the API until you approve.
            </div>
          </div>
        )}

        {/* STEP 2 — target domain */}
        {step === 2 && folder && (
          <div className="bulk-pane narrow">
            <div className="b-eyebrow">Step 2 · Target domain</div>
            <h2>Where should these files land?</h2>

            <div className="folder-card">
              <Icon name="folder" size={16} />
              <div style={{ flex: 1 }}>
                <div className="mono" style={{ fontSize: 13 }}>{folder.path}</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>{total} files · picked {folder.picked}</div>
              </div>
              <button className="btn ghost sm" onClick={() => setStep(1)}>Change</button>
            </div>

            <div className="route-grid">
              <div className={`route-card ${domain==="auto"?"on":""}`} onClick={() => setDomain("auto")}>
                <div className="route-dot auto" />
                <div className="route-title">Auto-classify</div>
                <div className="route-desc">Let brain route each file by content. Recommended.</div>
              </div>
              {window.SEED.domains.map(d => (
                <div key={d.id} className={`route-card ${domain===d.id?"on":""}`} onClick={() => setDomain(d.id)}>
                  <div className="route-dot" style={{ background: `var(--dom-${d.id})` }} />
                  <div className="route-title">
                    {d.name}
                    {d.id === "personal" && <Icon name="lock" size={10} style={{ marginLeft: 6 }} />}
                  </div>
                  <div className="route-desc">Send everything into <strong>{d.name.toLowerCase()}</strong>, skip classifier.</div>
                </div>
              ))}
            </div>

            {total > 20 && (
              <div className="cap-row">
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>This folder has {total} files.</div>
                  <div className="muted" style={{ fontSize: 12 }}>brain caps bulk imports at 20 by default. Raise the cap if you want more in one run.</div>
                </div>
                <div className="spacer" />
                <div className="cap-input">
                  <button onClick={() => setCap(c => Math.max(1, c - 5))}>−</button>
                  <input value={cap} onChange={e => setCap(Math.max(1, Math.min(total, +e.target.value || 1)))} />
                  <button onClick={() => setCap(c => Math.min(total, c + 5))}>+</button>
                </div>
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 28, gap: 10 }}>
              <button className="btn primary lg" onClick={() => setStep(3)}>
                Run dry-run on {Math.min(cap, total)} files →
              </button>
            </div>
          </div>
        )}

        {/* STEP 3 — dry-run review */}
        {step === 3 && (
          <div className="bulk-pane">
            <div className="dry-head">
              <div>
                <div className="b-eyebrow">Step 3 · Dry-run review</div>
                <h2 style={{ marginBottom: 4 }}>{included.length} of {totalEligible} files will be imported.</h2>
                <p className="muted" style={{ fontSize: 13 }}>
                  Uncheck anything you don't want to ingest. Re-route files to a different domain if the classifier got it wrong.
                  {skipped.length > 0 && <> {skipped.length} files were skipped automatically.</>}
                </p>
              </div>
              <div className="dry-summary">
                <div className="ds-row"><span className="ds-dot" style={{ background: "var(--dom-research)" }} />research · {files.filter(f => f.include && f.classified==="research").length}</div>
                <div className="ds-row"><span className="ds-dot" style={{ background: "var(--dom-work)" }} />work · {files.filter(f => f.include && f.classified==="work").length}</div>
                <div className="ds-row"><span className="ds-dot" style={{ background: "var(--dom-personal)" }} />personal · {files.filter(f => f.include && f.classified==="personal").length}</div>
                <div className="ds-row muted"><span className="ds-dot" style={{ background: "var(--text-dim)" }} />skipped · {skipped.length}</div>
              </div>
            </div>

            <div className="dry-table">
              <div className="dry-row dry-head-row">
                <div><input type="checkbox" checked={files.filter(f=>!f.skip).every(f=>f.include)} onChange={(e) => setFiles(f => f.map(x => x.skip ? x : { ...x, include: e.target.checked }))} /></div>
                <div>File</div>
                <div>Type</div>
                <div>Size</div>
                <div>Route to</div>
                <div>Confidence</div>
                <div>Notes</div>
              </div>
              {files.map(f => (
                <div key={f.id} className={`dry-row ${f.skip?"skipped":""} ${f.uncertain?"uncertain":""} ${f.flagged==="personal"?"sensitive":""}`}>
                  <div>
                    {f.skip ? <span className="dim">—</span> :
                      <input type="checkbox" checked={f.include} onChange={() => toggleInclude(f.id)} />}
                  </div>
                  <div className="mono" style={{ fontSize: 12 }}>{f.name}</div>
                  <div><span className={`type-badge ${f.type}`}>{typeIcon(f.type)}</span></div>
                  <div className="dim mono" style={{ fontSize: 11 }}>{f.size}</div>
                  <div>
                    {f.skip ? <span className="dim">—</span> :
                      <select className="route-sel" value={f.classified || ""} onChange={(e) => setRoute(f.id, e.target.value)}>
                        {window.SEED.domains.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
                      </select>}
                  </div>
                  <div>
                    {f.skip ? <span className="dim">—</span> : (
                      <div className="confidence">
                        <div className="conf-bar"><span style={{ width: `${(f.confidence||0)*100}%` }} /></div>
                        <span>{Math.round((f.confidence||0)*100)}%</span>
                      </div>
                    )}
                  </div>
                  <div style={{ fontSize: 11 }}>
                    {f.skip && <span className="skip-chip">{f.skip}</span>}
                    {f.dup && <span className="warn-chip">duplicate of existing source</span>}
                    {f.uncertain && <span className="warn-chip">classifier unsure</span>}
                    {f.flagged === "personal" && <span className="sens-chip"><Icon name="lock" size={9} /> personal</span>}
                  </div>
                </div>
              ))}
            </div>

            <div className="dry-footer">
              <div className="muted" style={{ fontSize: 12, lineHeight: 1.5 }}>
                <div><span className="dim">Rough estimate</span> — based on file size + Sonnet token rates.</div>
                <div><strong style={{ color: "var(--text)" }}>~${(included.length * 0.011).toFixed(2)}</strong> total · ~{Math.ceil(included.length * 4)}s total</div>
              </div>
              <div className="spacer" />
              <button className="btn ghost" onClick={() => setStep(2)}>Back</button>
              <button className="btn primary lg" onClick={() => { setStep(4); setApplying(true); setApplyIdx(0); }}>
                <Icon name="check" size={13} /> Import {included.length} files
              </button>
            </div>
          </div>
        )}

        {/* STEP 4 — apply */}
        {step === 4 && (
          <div className="bulk-pane">
            <div className="b-eyebrow">Step 4 · Apply</div>
            <h2>{done ? "Import complete." : cancelled ? "Import cancelled." : "Importing your sources…"}</h2>
            <p className="muted" style={{ fontSize: 13 }}>
              {done ? "Every file went through extract → classify → summarize → integrate. You can review each as a patch in Pending." :
                cancelled ? `${applyIdx} of ${included.length} applied before you cancelled. The rest are untouched.` :
                "Each file is extracted, summarized, and staged as a patch. You can cancel after the in-flight file finishes."}
            </p>

            <div className="apply-progress">
              <div className="apply-bar">
                <span style={{ width: `${(applyIdx / Math.max(1, included.length)) * 100}%` }} />
              </div>
              <div className="apply-count">{applyIdx} of {included.length} applied</div>
            </div>

            <div className="apply-list">
              {included.slice(0, 14).map((f, i) => {
                const state = i < applyIdx ? "done" : i === applyIdx && applying ? "running" : "queued";
                const runStage = ["extracting", "classifying", "summarizing", "integrating"][Math.floor(Date.now()/600)%4];
                return (
                  <div key={f.id} className={`apply-row ${state}`}>
                    <span className={`type-badge ${f.type}`}>{typeIcon(f.type)}</span>
                    <span className="mono" style={{ fontSize: 12, flex: 1 }}>{f.name}</span>
                    <span className={`chip dom-${f.classified}`} style={{ height: 18, fontSize: 10 }}>{f.classified}</span>
                    <span className="apply-state">
                      {state === "done" && <><Icon name="check" size={12} /> applied</>}
                      {state === "running" && <><span className="spinner" /> {runStage}</>}
                      {state === "queued" && <span className="dim">queued</span>}
                    </span>
                  </div>
                );
              })}
              {included.length > 14 && !done && (
                <div className="muted" style={{ fontSize: 12, padding: 10, textAlign: "center" }}>+ {included.length - 14} more queued</div>
              )}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 20 }}>
              {applying && !done && (
                <button className="btn ghost" onClick={() => setCancelled(true)}>
                  <Icon name="stop" size={12} /> Cancel after current file
                </button>
              )}
              <div className="spacer" style={{ flex: 1 }} />
              {done && (
                <>
                  <div className="apply-summary">
                    <span className="ok">{applyIdx} applied</span>
                    <span className="sep">·</span>
                    <span>{skipped.length} skipped</span>
                    {cancelled && <><span className="sep">·</span><span className="warn">{included.length - applyIdx} not run</span></>}
                  </div>
                  <button className="btn ghost" onClick={() => { setStep(1); setApplyIdx(0); setDone(false); setCancelled(false); setFolder(null); }}>Import another folder</button>
                  <button className="btn primary" onClick={() => window.brainStore.setView("pending")}>
                    Review in Pending →
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

Object.assign(window, { BulkScreen });
