"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "Query", href: "/dashboard" },
  { name: "Documents", href: "/dashboard/documents" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-border bg-surface-1">
      <div className="flex h-14 items-center border-b border-border px-4">
        <Link href="/" className="font-bold font-display text-lg">
          Vault
        </Link>
      </div>
      <nav className="p-4 space-y-1">
        {navigation.map((item) => (
          <Link
            key={item.name}
            href={item.href}
            className={cn(
              "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
              pathname === item.href
                ? "bg-surface-2 text-foreground"
                : "text-ink-muted hover:bg-surface-2 hover:text-foreground"
            )}
          >
            {item.name}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
