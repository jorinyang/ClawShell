"use client";

import { useLocale } from "next-intl";
import { useRouter } from "next/navigation";
import { Globe } from "lucide-react";

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();

  const toggle = () => {
    const next = locale === "zh" ? "en" : "zh";
    document.cookie = `locale=${next};path=/;max-age=31536000`;
    router.refresh();
  };

  return (
    <button
      onClick={toggle}
      className="flex h-8 items-center gap-1.5 rounded-[6px] border border-border px-2.5 text-xs text-text-tertiary transition-colors hover:bg-[rgba(255,255,255,0.04)] hover:text-text-secondary"
    >
      <Globe className="h-3.5 w-3.5" />
      {locale === "zh" ? "中文" : "EN"}
    </button>
  );
}
