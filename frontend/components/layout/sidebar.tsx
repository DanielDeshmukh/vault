"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useEffect, useState, createContext, useContext, useCallback } from "react";
import { api, User } from "@/lib/api";

interface SidebarContextType {
  collapsed: boolean;
  setCollapsed: (v: boolean) => void;
  toggleCollapsed: () => void;
}

const SidebarContext = createContext<SidebarContextType>({
  collapsed: false,
  setCollapsed: () => {},
  toggleCollapsed: () => {},
});

export const useSidebar = () => useContext(SidebarContext);

const navigation = [
  {
    name: "Query",
    href: "/dashboard",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
      </svg>
    ),
  },
  {
    name: "Documents",
    href: "/dashboard/documents",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    ),
  },
];

const adminNavigation = [
  {
    name: "Users",
    href: "/dashboard/admin/users",
    icon: (
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
      </svg>
    ),
  },
];

function SidebarContent({ user, pathname, onLogout, collapsed }: { user: User | null; pathname: string; onLogout: () => void; collapsed?: boolean }) {
  return (
    <>
      <div className="flex h-14 items-center border-b border-border px-4">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          {!collapsed && <span className="font-bold font-display text-lg tracking-tight">Vault</span>}
        </Link>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {!collapsed && (
          <p className="px-3 text-[10px] font-semibold uppercase tracking-wider text-ink-tertiary mb-1">General</p>
        )}
        {navigation.map((item) => (
          <Link
            key={item.name}
            href={item.href}
            title={collapsed ? item.name : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              collapsed && "justify-center",
              pathname === item.href
                ? "bg-surface-2 text-foreground"
                : "text-ink-muted hover:bg-surface-2/50 hover:text-foreground"
            )}
          >
            <span className={cn("flex-shrink-0", pathname === item.href ? "text-primary" : "text-ink-tertiary")}>
              {item.icon}
            </span>
            {!collapsed && item.name}
          </Link>
        ))}

        {user?.is_admin && (
          <>
            {!collapsed && (
              <p className="px-3 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-tertiary">Admin</p>
            )}
            {adminNavigation.map((item) => (
              <Link
                key={item.name}
                href={item.href}
                title={collapsed ? item.name : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  collapsed && "justify-center",
                  pathname === item.href
                    ? "bg-surface-2 text-foreground"
                    : "text-ink-muted hover:bg-surface-2/50 hover:text-foreground"
                )}
              >
                <span className={cn("flex-shrink-0", pathname === item.href ? "text-primary" : "text-ink-tertiary")}>
                  {item.icon}
                </span>
                {!collapsed && item.name}
              </Link>
            ))}
          </>
        )}
      </nav>

      {user && (
        <div className="border-t border-border p-3">
          <div className={cn("flex items-center", collapsed ? "justify-center" : "gap-3")}>
            <div className="w-8 h-8 rounded-full bg-surface-3 flex items-center justify-center text-sm font-medium text-ink-muted flex-shrink-0">
              {user.full_name?.charAt(0)?.toUpperCase() || "?"}
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{user.full_name}</p>
                <p className="text-xs text-ink-tertiary truncate">{user.email}</p>
              </div>
            )}
            <button onClick={onLogout} className="p-1.5 rounded-md text-ink-tertiary hover:text-foreground hover:bg-surface-2 transition-colors" title="Sign out">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
              </svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}

export function SidebarProvider({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const toggleCollapsed = useCallback(() => setCollapsed((c) => !c), []);

  return (
    <SidebarContext.Provider value={{ collapsed, setCollapsed, toggleCollapsed }}>
      {children}
    </SidebarContext.Provider>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { collapsed } = useSidebar();

  useEffect(() => {
    const stored = localStorage.getItem("vault_user");
    if (stored) {
      try { setUser(JSON.parse(stored)); } catch {}
    }
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const handleLogout = () => {
    api.logout();
    router.push("/login");
  };

  return (
    <>
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 h-14 bg-surface-1 border-b border-border flex items-center px-4 gap-3">
        <button onClick={() => setMobileOpen(true)} className="p-2 -ml-2 rounded-md text-ink-muted hover:bg-surface-2">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
          </svg>
        </button>
        <Link href="/dashboard" className="font-bold font-display text-lg tracking-tight">Vault</Link>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-50 bg-black/60" onClick={() => setMobileOpen(false)} />
      )}

      {/* Mobile sidebar */}
      <aside className={cn(
        "lg:hidden fixed top-0 left-0 bottom-0 z-50 w-64 bg-surface-1 border-r border-border flex flex-col transition-transform duration-200",
        mobileOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <SidebarContent user={user} pathname={pathname} onLogout={handleLogout} />
      </aside>

      {/* Desktop sidebar */}
      <aside className={cn(
        "hidden lg:flex flex-col h-screen sticky top-0 bg-surface-1 border-r border-border transition-all duration-200",
        collapsed ? "w-16" : "w-64"
      )}>
        <SidebarContent user={user} pathname={pathname} onLogout={handleLogout} collapsed={collapsed} />
      </aside>
    </>
  );
}
