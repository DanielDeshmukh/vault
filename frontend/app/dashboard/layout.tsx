"use client";

import { Sidebar, SidebarProvider } from "@/components/layout/sidebar";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen bg-background overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-x-hidden lg:pt-0 pt-14 min-w-0">{children}</main>
      </div>
    </SidebarProvider>
  );
}
