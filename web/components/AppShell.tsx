"use client";

import { Sidebar } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { PageTransition } from "@/components/PageTransition";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="ml-60 flex flex-1 flex-col min-w-0">
        <TopBar />
        <main className="flex-1 p-8">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>
    </div>
  );
}
