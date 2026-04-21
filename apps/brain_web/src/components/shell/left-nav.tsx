"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";

interface NavItem {
  href: string;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/chat", label: "Chat" },
  { href: "/inbox", label: "Inbox" },
  { href: "/browse", label: "Browse" },
  { href: "/pending", label: "Pending" },
  { href: "/bulk", label: "Bulk" },
  { href: "/settings", label: "Settings" },
  { href: "/setup", label: "Setup" },
];

export function LeftNav() {
  const pathname = usePathname();

  function handleNewChat() {
    // Task 13 wires this to the real thread-create action. For now, a no-op
    // with a console breadcrumb is enough for the shell skeleton.
    // eslint-disable-next-line no-console
    console.log("[shell] New chat clicked (Task 13 wires this)");
  }

  return (
    <nav
      aria-label="Primary"
      className="leftnav flex flex-col gap-2 border-r border-[var(--hairline)] bg-[var(--surface-1)] p-3 text-[var(--text)]"
    >
      <Button
        type="button"
        onClick={handleNewChat}
        aria-label="New chat"
        className="w-full justify-start"
        size="sm"
      >
        + New chat
      </Button>

      <ul className="mt-2 flex flex-col gap-1" role="list">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={[
                  "flex items-center rounded-md px-3 py-1.5 text-sm",
                  active
                    ? "bg-[var(--surface-3)] text-[var(--text)]"
                    : "text-[var(--text-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--text)]",
                ].join(" ")}
              >
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
