"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Bot, CheckCircle, XCircle, AlertTriangle, RefreshCw } from "lucide-react";

interface Agent {
  agent_id: string;
  framework: string;
  agent_type: string;
  display_name: string;
  capabilities: string[];
  skills: string[];
  mcp_servers: string[];
  injection_status: {
    mcp: boolean;
    hook: boolean;
    config: boolean;
    loop_skill: boolean;
    skill: boolean;
  };
  status: string;
  node_id: string;
  user_id: string;
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);

  const loadAgents = async () => {
    setLoading(true);
    try {
      const data = await api.getAgents();
      setAgents(data.agents || []);
    } catch (e) {
      console.error("Failed to load agents", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadAgents(); }, []);

  const injectionColor = (count: number) => {
    if (count === 5) return "text-green-400";
    if (count >= 3) return "text-yellow-400";
    return "text-red-400";
  };

  const typeBadge = (type: string) => {
    const colors: Record<string, string> = {
      framework: "bg-[rgba(94,106,210,0.12)] text-accent",
      bridge: "bg-[rgba(34,197,94,0.12)] text-green-400",
      ide: "bg-[rgba(249,115,22,0.12)] text-orange-400",
    };
    return colors[type] || "bg-[rgba(255,255,255,0.06)] text-text-tertiary";
  };

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium text-foreground">Agents</h1>
          <p className="mt-1 text-xs text-text-quaternary">
            Discovered AI agent instances across all frameworks
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadAgents} disabled={loading}>
          <RefreshCw className={`mr-2 h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="flex h-40 items-center justify-center text-sm text-text-quaternary">
          Scanning for agents...
        </div>
      ) : agents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Bot className="mb-3 h-8 w-8 text-text-quaternary" />
            <p className="text-sm text-text-tertiary">No agents detected</p>
            <p className="mt-1 text-xs text-text-quaternary">
              Install a supported AI agent framework to get started
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => {
            const injected = Object.values(agent.injection_status || {}).filter(Boolean).length;
            return (
              <Card key={agent.agent_id} className="overflow-hidden">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-2.5">
                      <Bot className="h-4 w-4 text-accent" />
                      <CardTitle className="text-sm font-medium">{agent.display_name}</CardTitle>
                    </div>
                    <Badge className={typeBadge(agent.agent_type)} variant="secondary">
                      {agent.agent_type}
                    </Badge>
                  </div>
                  <p className="mt-1 text-[11px] text-text-quaternary">{agent.agent_id}</p>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Status */}
                  <div className="flex items-center gap-2">
                    <div className={`h-2 w-2 rounded-full ${agent.status === "online" ? "bg-green-400" : "bg-gray-600"}`} />
                    <span className="text-xs text-text-tertiary">{agent.status}</span>
                    <span className="text-xs text-text-quaternary">· {agent.framework}</span>
                  </div>

                  {/* Injection status */}
                  <div>
                    <div className="mb-1.5 flex items-center justify-between">
                      <span className="text-[11px] text-text-quaternary">Injection</span>
                      <span className={`text-xs font-medium ${injectionColor(injected)}`}>
                        {injected}/5
                      </span>
                    </div>
                    <div className="flex gap-1">
                      {(["mcp", "hook", "config", "loop_skill", "skill"] as const).map((method) => (
                        <div
                          key={method}
                          title={method}
                          className={`h-1.5 flex-1 rounded-full ${
                            agent.injection_status?.[method] ? "bg-accent" : "bg-[rgba(255,255,255,0.08)]"
                          }`}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Capabilities */}
                  {agent.capabilities.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {agent.capabilities.map((cap) => (
                        <Badge key={cap} variant="outline" className="text-[10px]">
                          {cap}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
