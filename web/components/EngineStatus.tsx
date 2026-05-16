"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface EngineStatusProps {
  onlineNodes: number;
  totalNodes: number;
  activeSessions: number;
}

export function EngineStatus({ onlineNodes, totalNodes, activeSessions }: EngineStatusProps) {
  const isHealthy = onlineNodes > 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Activity className="h-5 w-5" />
          引擎状态
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            {isHealthy ? (
              <CheckCircle className="h-5 w-5 text-success" />
            ) : (
              <AlertCircle className="h-5 w-5 text-destructive" />
            )}
            <span className={cn("text-sm font-medium", isHealthy ? "text-success" : "text-destructive")}>
              {isHealthy ? "运行中" : "离线"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-muted/50 p-3 text-center">
              <p className="text-2xl font-bold text-primary">{onlineNodes}</p>
              <p className="text-xs text-muted-foreground">在线节点</p>
            </div>
            <div className="rounded-lg bg-muted/50 p-3 text-center">
              <p className="text-2xl font-bold text-info">{activeSessions}</p>
              <p className="text-xs text-muted-foreground">活跃会话</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
