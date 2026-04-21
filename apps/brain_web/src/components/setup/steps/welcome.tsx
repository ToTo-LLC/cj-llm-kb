"use client";

/**
 * Welcome step (1 / 6). Static copy + the "Already set up → open app" link
 * that bypasses the wizard entirely (rendered by the parent `<Wizard>` at
 * the bottom-right). No props needed — the escape hatch is wired at the
 * wizard level because it changes the overall flow.
 */
export function WelcomeStep() {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-medium tracking-tight">
        Welcome to <span className="italic">brain</span>.
      </h1>
      <p className="text-base leading-relaxed text-muted-foreground">
        A knowledge base that stays on your machine, run by an LLM you
        control.
        <br />
        Nothing leaves this computer unless you tell it to.
      </p>
    </div>
  );
}
