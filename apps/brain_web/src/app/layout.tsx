import type { Metadata } from "next";
import "@/styles/tokens.css";
import "@/styles/globals.css";
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
