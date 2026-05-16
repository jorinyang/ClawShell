"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ResourceBarProps {
  label: string;
  value: number;
  max?: number;
  color?: string;
}

export function ResourceBar({ label, value, max = 100, color }: ResourceBarProps) {
  const pct = Math.min(Math.max((value / max) * 100, 0), 100);
  const barColor =
    color || (pct > 80 ? "bg-destructive" : pct > 60 ? "bg-warning" : "bg-success");

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{pct.toFixed(1)}%</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
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
}

export function ResourceChart({ cpu = 0, memory = 0, disk = 0 }: ResourceChartProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">资源使用</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <ResourceBar label="CPU" value={cpu} />
        <ResourceBar label="Memory" value={memory} />
        <ResourceBar label="Disk" value={disk} />
      </CardContent>
    </Card>
  );
}
