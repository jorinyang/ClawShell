"use client";

import { Activity, CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface EngineStatusProps {
  onlineNodes: number;
  totalNodes: number;
  activeSessions: number;
  t?: (key: string) => string;
}

export function EngineStatus({ onlineNodes, totalNodes, activeSessions, t }: EngineStatusProps) {
  const isHealthy = onlineNodes > 0;
  return (
    <div className="rounded-lg border border-border bg-[rgba(255,255,255,0.02)] p-5">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="h-4 w-4 text-text-tertiary" />
        <span className="text-sm font-medium text-text-secondary">{t?.("engineStatus") || "Engine Status"}</span>
      </div>
      <div className="space-y-4">
        <div className="flex items-center gap-2.5">
          {isHealthy ? (
            <CheckCircle className="h-4 w-4 text-success" />
          ) : (
            <AlertCircle className="h-4 w-4 text-destructive" />
          )}
          <span className={cn("text-sm font-medium", isHealthy ? "text-success" : "text-destructive")}>
            {isHealthy ? (t?.("running") || "Running") : (t?.("offline") || "Offline")}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-[6px] bg-[rgba(255,255,255,0.03)] p-3">
            <p className="text-xl font-medium text-foreground">{onlineNodes}</p>
            <p className="text-xs text-text-quaternary mt-0.5">{t?.("onlineNodes") || "Online Nodes"}</p>
          </div>
          <div className="rounded-[6px] bg-[rgba(255,255,255,0.03)] p-3">
            <p className="text-xl font-medium text-foreground">{activeSessions}</p>
            <p className="text-xs text-text-quaternary mt-0.5">{t?.("activeSessions") || "Active Sessions"}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
