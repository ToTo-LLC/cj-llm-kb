// Seed data for the brain prototype — CJ-flavored (conflict, deals, sales research)
window.SEED = {
  domains: [
    { id: "research", name: "Research", color: "var(--dom-research)", count: 47 },
    { id: "work",     name: "Work",     color: "var(--dom-work)",     count: 89 },
    { id: "personal", name: "Personal", color: "var(--dom-personal)", count: 23 },
  ],

  threads: [
    {
      id: "t-1", title: "Patterns in deal-stall signals — weekly review",
      mode: "ask", domain: "work", scope: ["work", "research"],
      updated: "2m ago", group: "Today",
      turns: 14, cost: 0.084,
    },
    {
      id: "t-2", title: "Is conflict identification a moat?",
      mode: "brainstorm", domain: "research", scope: ["research"],
      updated: "1h ago", group: "Today", turns: 8, cost: 0.051,
    },
    {
      id: "t-3", title: "Q2 board memo — narrative options",
      mode: "draft", domain: "work", scope: ["work"],
      updated: "3h ago", group: "Today", turns: 22, cost: 0.212,
    },
    { id: "t-4", title: "Fisher & Ury — negotiation primitives", mode: "ask", domain: "research", group: "Yesterday", turns: 11 },
    { id: "t-5", title: "Follow-up cadence after a silent buyer", mode: "brainstorm", domain: "work", group: "Yesterday", turns: 6 },
    { id: "t-6", title: "Compounding curiosity — monthly synthesis", mode: "draft", domain: "personal", group: "This week", turns: 18 },
    { id: "t-7", title: "Why \"concession pairs\" beat single-axis trading", mode: "ask", domain: "research", group: "This week", turns: 9 },
    { id: "t-8", title: "Re-reading Never Split the Difference", mode: "brainstorm", domain: "research", group: "Last week", turns: 14 },
  ],

  // Active thread transcript (will be rendered turn-by-turn)
  activeThread: "t-1",
  transcript: [
    {
      role: "user", ts: "14:02",
      body: "Look at the last month of sales-call transcripts and pull the top patterns where deals stalled. Cross-reference with the conflict-identification notes in research/."
    },
    {
      role: "brain", ts: "14:02", mode: "ask",
      stream: true,
      toolCalls: [
        {
          tool: "brain_search", args: { query: "deal stalled", domains: ["work"], top_k: 8 },
          open: false,
          result: {
            hits: [
              { path: "work/sources/2026-04-18-acme-q2-call.md", title: "ACME Q2 kickoff call", score: 0.91, snippet: "…buyer went quiet after legal raised a red-line question about data residency…" },
              { path: "work/sources/2026-04-14-helios-renewal.md", title: "Helios renewal discovery", score: 0.88, snippet: "…'we need to loop in security' — next meeting never booked; three follow-ups unanswered…" },
              { path: "work/sources/2026-04-11-polaris-intro.md", title: "Polaris intro — product-led", score: 0.82, snippet: "…champion acknowledged budget but wouldn't commit to a decision date; classic avoidance cue…" },
              { path: "work/sources/2026-04-08-vestige-legal.md", title: "Vestige legal touch-base", score: 0.79, snippet: "…procurement added a new required attendee at the eleventh hour…" },
            ]
          }
        },
        {
          tool: "brain_search", args: { query: "conflict identification signals", domains: ["research"], top_k: 5 },
          open: false,
          result: {
            hits: [
              { path: "research/concepts/conflict-avoidance-tells.md", title: "Conflict-avoidance tells", score: 0.94, snippet: "…sudden widening of the attendee list; vague agreement without commitment; reframing urgency downward…" },
              { path: "research/notes/fisher-ury-interests.md", title: "Fisher & Ury — positions vs interests", score: 0.87, snippet: "…when a counterparty restates your position back to you without movement, the hidden interest is usually risk…" },
              { path: "research/synthesis/silent-buyer-synthesis.md", title: "The silent-buyer synthesis", score: 0.83, snippet: "…silence itself is a signal — it compresses four objections into one ambiguous blocker…" },
            ]
          }
        }
      ],
      body: `Three patterns jump out when I cross the last month of call transcripts against the conflict-avoidance research.

**1 — The \"loop-in\" stall.** In 3 of 7 stalled deals (ACME, Helios, Vestige) the champion went quiet after introducing a new required stakeholder. This maps cleanly to the [[conflict-avoidance-tells]] pattern: *sudden widening of the attendee list is an avoidance move, not a progress signal.*

**2 — Restating without movement.** Two deals (Polaris, Helios-renewal) had buyers paraphrasing your pricing position back accurately but never counter-offering. Per [[fisher-ury-interests]], that signals a hidden risk interest you haven't surfaced yet.

**3 — Agenda softening.** Where calls ended with \"let's regroup\" rather than a booked next step, follow-up response rate dropped from 72% to 19%. That's aligned with the [[silent-buyer-synthesis]] note on ambiguity compression.

Want me to stage a note at \`work/synthesis/2026-04-deal-stall-patterns.md\` that cross-links all four source calls into the three pattern concepts? You'd own the edit pass.`,
      proposedPatch: null,
      cost: 0.024, cumCost: 0.084,
    }
  ],

  // Pending patches queue
  patches: [
    {
      id: "p-01K8M",
      tool: "brain_propose_note",
      target: "work/synthesis/2026-04-deal-stall-patterns.md",
      reason: "Synthesis of three recurring stall patterns from April sales calls, cross-linked to conflict-identification research notes. Created from chat: 'Patterns in deal-stall signals'.",
      createdAt: "2m ago",
      domain: "work",
      mode: "ask",
      fromThread: "t-1",
      isNew: true,
      diff: [
        { type: "add", n: 1, code: "---" },
        { type: "add", n: 2, code: "type: synthesis" },
        { type: "add", n: 3, code: "domain: work" },
        { type: "add", n: 4, code: "created: 2026-04-21" },
        { type: "add", n: 5, code: "links: [[conflict-avoidance-tells]], [[fisher-ury-interests]], [[silent-buyer-synthesis]]" },
        { type: "add", n: 6, code: "sources: 4" },
        { type: "add", n: 7, code: "---" },
        { type: "add", n: 8, code: "" },
        { type: "add", n: 9, code: "# Deal-Stall Patterns — April 2026" },
        { type: "add", n: 10, code: "" },
        { type: "add", n: 11, code: "Three patterns recur across 7 stalled deals last month." },
        { type: "add", n: 12, code: "" },
        { type: "add", n: 13, code: "## 1. The \"loop-in\" stall" },
        { type: "add", n: 14, code: "Champion goes quiet after introducing a new required stakeholder." },
        { type: "add", n: 15, code: "Seen in: ACME, Helios, Vestige." },
        { type: "add", n: 16, code: "" },
        { type: "add", n: 17, code: "## 2. Restating without movement" },
        { type: "add", n: 18, code: "Accurate paraphrase of your pricing position, no counter-offer." },
      ]
    },
    {
      id: "p-01K8L",
      tool: "brain_ingest",
      target: "work/sources/2026-04-18-acme-q2-call.md",
      reason: "Transcript ingested from the shared folder; classified as 'work' at 0.96 confidence; summary + action items extracted.",
      createdAt: "18m ago",
      domain: "work",
      mode: null,
      isNew: false,
      diff: [
        { type: "add", n: 1, code: "---" },
        { type: "add", n: 2, code: "type: source" },
        { type: "add", n: 3, code: "source_type: transcript" },
        { type: "add", n: 4, code: "domain: work" },
        { type: "add", n: 5, code: "participants: [CJ, T. Ramirez, L. Okonkwo]" },
        { type: "add", n: 6, code: "---" },
        { type: "add", n: 7, code: "" },
        { type: "add", n: 8, code: "# ACME Q2 Kickoff Call" },
      ]
    },
    {
      id: "p-01K8K",
      tool: "brain_propose_note",
      target: "research/concepts/concession-pairs.md",
      reason: "New concept note capturing the 'concession pairs' framework from today's brainstorm on multi-axis negotiation.",
      createdAt: "42m ago",
      domain: "research",
      mode: "brainstorm",
      fromThread: "t-7",
      isNew: false,
      diff: [
        { type: "add", n: 1, code: "---" },
        { type: "add", n: 2, code: "type: concept" },
        { type: "add", n: 3, code: "domain: research" },
        { type: "add", n: 4, code: "---" },
        { type: "add", n: 5, code: "" },
        { type: "add", n: 6, code: "# Concession Pairs" },
      ]
    },
    {
      id: "p-01K8J",
      tool: "brain_propose_note",
      target: "work/entities/helios-account.md",
      reason: "Entity note updated: new contact (procurement lead A. Vu) + stalled-renewal flag.",
      createdAt: "1h ago",
      domain: "work",
      mode: null,
      isNew: false,
      diff: [
        { type: "ctx", n: 8, code: "## Key contacts" },
        { type: "del", n: 9, code: "- T. Ramirez — Champion" },
        { type: "add", n: 9, code: "- T. Ramirez — Champion (primary)" },
        { type: "add", n: 10, code: "- A. Vu — Procurement lead (added 2026-04-21)" },
        { type: "ctx", n: 11, code: "" },
        { type: "add", n: 12, code: "> **Status:** renewal stalled — see [[2026-04-deal-stall-patterns]]" },
      ]
    },
  ],

  // Inbox sources
  sources: [
    { id: "s-1", title: "Chris Voss — Tactical Empathy in Complex Deals", type: "url", url: "https://open.spotify.com/…", status: "integrating", progress: 82, domain: "research", cost: 0.012, time: "just now" },
    { id: "s-2", title: "Q2-kickoff-acme-transcript.txt", type: "text", status: "done", progress: 100, domain: "work", cost: 0.008, time: "18m ago" },
    { id: "s-3", title: "gong-export-2026-04-14.pdf", type: "pdf", status: "classifying", progress: 35, domain: null, cost: 0.002, time: "21m ago" },
    { id: "s-4", title: "Andrew Huberman — Decision-Making Under Time Pressure", type: "url", url: "https://www.youtube.com/…", status: "done", progress: 100, domain: "research", cost: 0.014, time: "2h ago" },
    { id: "s-5", title: "helios-renewal-thread.eml", type: "email", status: "failed", progress: 0, domain: null, error: "Couldn't extract quoted replies — forward-chain has 14 levels of nesting.", cost: 0.001, time: "3h ago" },
    { id: "s-6", title: "Fisher & Ury — Getting to Yes (Ch. 3 excerpt).pdf", type: "pdf", status: "done", progress: 100, domain: "research", cost: 0.019, time: "yesterday" },
    { id: "s-7", title: "Team weekly notes — 2026-04-15.md", type: "text", status: "done", progress: 100, domain: "work", cost: 0.005, time: "yesterday" },
  ],

  costToday: 0.84,
  costMonth: 18.42,
  budgetDaily: 2.50,

  autonomousMode: false,
};
