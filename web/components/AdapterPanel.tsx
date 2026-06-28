"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckCircle, XCircle, RefreshCw, Puzzle, Wrench, Code } from "lucide-react";

type InjectionStatus = {
  mcp: boolean;
  hook: boolean;
  config: boolean;
  loop_skill: boolean;
  skill: boolean;
};

type AdapterInfo = {
  name: string;
  type: "framework" | "bridge" | "ide";
  detected: boolean;
  injection: InjectionStatus;
  issues: string[];
};

interface AdapterPanelProps {
  adapters: AdapterInfo[];
  onInject: (name: string) => void;
  onVerify: (name: string) => void;
  onRollback: (name: string) => void;
  loading?: boolean;
}

const TYPE_ICONS = {
  framework: Puzzle,
  bridge: Wrench,
  ide: Code,
};

const TYPE_LABELS = {
  framework: "Frameworks",
  bridge: "Bridges",
  ide: "IDE Tools",
};

export function AdapterPanel({ adapters, onInject, onVerify, onRollback, loading }: AdapterPanelProps) {
  const adapterTypes = ["framework", "bridge", "ide"] as const;
  const [activeTab, setActiveTab] = useState("framework");

  return (
    <div>
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          {adapterTypes.map((type) => {
            const items = adapters.filter((a) => a.type === type);
            const Icon = TYPE_ICONS[type];
            return (
              <TabsTrigger key={type} value={type} className="gap-1.5">
                <Icon className="h-3.5 w-3.5" />
                {TYPE_LABELS[type]}
                <Badge variant="secondary" className="ml-1 text-[10px]">{items.length}</Badge>
              </TabsTrigger>
            );
          })}
        </TabsList>

        {adapterTypes.map((type) => (
          <TabsContent key={type} value={type} className="space-y-3">
            {adapters
              .filter((a) => a.type === type)
              .map((adapter) => (
                <AdapterCard
                  key={adapter.name}
                  adapter={adapter}
                  onInject={onInject}
                  onVerify={onVerify}
                  onRollback={onRollback}
                  loading={loading}
                />
              ))}
            {adapters.filter((a) => a.type === type).length === 0 && (
              <Card>
                <CardContent className="flex items-center justify-center py-8">
                  <p className="text-sm text-text-quaternary">No {type} adapters registered</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}

function AdapterCard({
  adapter,
  onInject,
  onVerify,
  onRollback,
  loading,
}: {
  adapter: AdapterInfo;
  onInject: (name: string) => void;
  onVerify: (name: string) => void;
  onRollback: (name: string) => void;
  loading?: boolean;
}) {
  const injected = Object.values(adapter.injection).filter(Boolean).length;

  return (
    <Card className={!adapter.detected ? "opacity-50" : ""}>
      <CardContent className="flex items-center justify-between py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[rgba(94,106,210,0.08)]">
            <Puzzle className="h-4 w-4 text-accent" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-foreground">{adapter.name}</p>
              {adapter.detected ? (
                <Badge variant="secondary" className="text-[10px] text-green-400">Detected</Badge>
              ) : (
                <Badge variant="secondary" className="text-[10px] text-text-quaternary">Not Found</Badge>
              )}
            </div>
            <p className="mt-0.5 flex items-center gap-2 text-xs text-text-quaternary">
              Injection: {injected}/5
              {(["mcp", "hook", "config", "loop_skill", "skill"] as const).map((m) => (
                <span
                  key={m}
                  className={adapter.injection[m] ? "text-green-400" : "text-text-quaternary"}
                  title={m}
                >
                  {adapter.injection[m] ? <CheckCircle className="inline h-3 w-3" /> : <XCircle className="inline h-3 w-3" />}
                </span>
              ))}
            </p>
            {adapter.issues.length > 0 && (
              <p className="mt-1 text-[11px] text-destructive">{adapter.issues.join(", ")}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => onVerify(adapter.name)} disabled={loading}>
            Verify
          </Button>
          <Button size="sm" variant="default" onClick={() => onInject(adapter.name)} disabled={loading || !adapter.detected}>
            Inject
          </Button>
          <Button size="sm" variant="outline" onClick={() => onRollback(adapter.name)} disabled={loading}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
