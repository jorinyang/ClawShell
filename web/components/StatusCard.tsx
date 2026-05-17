"use client";

import { cn } from "@/lib/utils";

interface StatusCardProps {
  title: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  color?: "default" | "success" | "warning" | "info" | "destructive";
}

const colorMap = {
  default: "text-foreground",
  success: "text-success",
  warning: "text-warning",
  info: "text-accent",
  destructive: "text-destructive",
};

const iconColorMap = {
  default: "text-text-tertiary",
  success: "text-success",
  warning: "text-warning",
  info: "text-accent",
  destructive: "text-destructive",
};

export function StatusCard({
  title,
  value,
  icon: Icon,
  color = "default",
}: StatusCardProps) {
  return (
    <div className="rounded-lg border border-border bg-[rgba(255,255,255,0.02)] p-5">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-xs font-medium text-text-quaternary">{title}</p>
          <p className={cn("text-2xl font-medium tracking-tight", colorMap[color])}>
            {value}
          </p>
        </div>
        <Icon className={cn("h-4 w-4 mt-0.5", iconColorMap[color])} />
      </div>
    </div>
  );
}
