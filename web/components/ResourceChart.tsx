"use client";

import { cn } from "@/lib/utils";

interface ResourceBarProps {
  label: string;
  value: number;
  max?: number;
}

export function ResourceBar({ label, value, max = 100 }: ResourceBarProps) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  const barColor =
    pct > 80 ? "bg-destructive" : pct > 60 ? "bg-warning" : "bg-success";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-tertiary">{label}</span>
        <span className="text-xs font-medium text-text-secondary">{pct.toFixed(1)}%</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-[rgba(255,255,255,0.06)]">
        <div
          className={cn("h-full rounded-full transition-all duration-500", barColor)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

interface ResourceChartProps {
  cpu?: number;
  memory?: number;
  disk?: number;
  t?: (key: string) => string;
}

export function ResourceChart({ cpu = 0, memory = 0, disk = 0, t }: ResourceChartProps) {
  return (
    <div className="rounded-lg border border-border bg-[rgba(255,255,255,0.02)] p-5">
      <div className="mb-4">
        <span className="text-sm font-medium text-text-secondary">{t?.("resourceUsage") || "Resource Usage"}</span>
      </div>
      <div className="space-y-3">
        <ResourceBar label={t?.("cpu") || "CPU"} value={cpu} />
        <ResourceBar label={t?.("memory") || "Memory"} value={memory} />
        <ResourceBar label={t?.("disk") || "Disk"} value={disk} />
      </div>
    </div>
  );
}
