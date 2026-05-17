"use client";

import { useTranslations } from "next-intl";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { usePathname } from "next/navigation";

const pageTitles: Record<string, string> = {
  "/": "dashboard",
  "/system": "system",
  "/nodes": "nodes",
  "/users": "users",
  "/credentials": "credentials",
  "/endpoints": "endpoints",
  "/audit": "audit",
};

export function TopBar() {
  const t = useTranslations("common");
  const pathname = usePathname();
  const titleKey = pageTitles[pathname] || "dashboard";

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border bg-background/80 px-8 backdrop-blur-sm">
      <h1 className="text-sm font-medium text-text-secondary">{t(titleKey)}</h1>
      <div className="flex items-center gap-3">
        <LanguageSwitcher />
      </div>
    </header>
  );
}
