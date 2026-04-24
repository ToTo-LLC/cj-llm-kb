import type { Metadata } from "next";
import "@/styles/tokens.css";
import "@/styles/globals.css";
// brand-skin.css MUST load after tokens.css + globals.css. It remaps the
// --surface-0..4, --text*, --hairline*, and domain tokens to the brain.
// brand palette (paper / ember / sage / wheat / sky), and the cascade
// order ensures the v4 visual identity wins over the v3 TT skin underneath.
// Source: docs/design/CJ Knowledge LLM v4/styles/brand-skin.css.
import "@/styles/brand-skin.css";
import { ThemeProvider } from "@/components/theme-provider";
import { AppShell } from "@/components/shell/app-shell";
import { BootGate } from "@/components/shell/boot-gate";
import { BootstrapProvider } from "@/lib/bootstrap/bootstrap-context";

export const metadata: Metadata = {
  title: "brain",
  description: "Your LLM-maintained personal knowledge base.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <BootstrapProvider>
            <BootGate>
              <AppShell>{children}</AppShell>
            </BootGate>
          </BootstrapProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
