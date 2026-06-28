"use client";

import { Badge } from "@/components/ui/badge";

interface InjectionStatusProps {
  mcp: boolean;
  hook: boolean;
  config: boolean;
  loop_skill: boolean;
  skill: boolean;
  size?: "sm" | "md";
}

const METHOD_LABELS: Record<keyof Omit<InjectionStatusProps, "size">, string> = {
  mcp: "MCP",
  hook: "Hook",
  config: "Config",
  loop_skill: "Loop",
  skill: "Skill",
};

export function InjectionStatusBar({ mcp, hook, config, loop_skill, skill, size = "sm" }: InjectionStatusProps) {
  const methods = [
    { key: "mcp" as const, value: mcp },
    { key: "hook" as const, value: hook },
    { key: "config" as const, value: config },
    { key: "loop_skill" as const, value: loop_skill },
    { key: "skill" as const, value: skill },
  ];

  const injected = methods.filter((m) => m.value).length;

  if (size === "md") {
    return (
      <div className="flex flex-wrap gap-2">
        {methods.map(({ key, value }) => (
          <Badge
            key={key}
            variant={value ? "default" : "secondary"}
            className={value ? "bg-accent/20 text-accent" : "text-text-quaternary"}
          >
            {value ? "✓" : "✗"} {METHOD_LABELS[key]}
          </Badge>
        ))}
        <Badge variant="outline" className="text-xs">
          {injected}/5
        </Badge>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1">
      {methods.map(({ key, value }) => (
        <div
          key={key}
          title={`${METHOD_LABELS[key]}: ${value ? "injected" : "missing"}`}
          className={`h-1.5 flex-1 rounded-full transition-colors ${
            value ? "bg-green-400" : "bg-[rgba(255,255,255,0.08)]"
          }`}
        />
      ))}
      <span className="ml-2 text-[10px] text-text-quaternary tabular-nums">{injected}/5</span>
    </div>
  );
}
