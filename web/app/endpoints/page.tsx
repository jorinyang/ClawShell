"use client";

import { useEffect, useState, useCallback } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface Endpoint {
  name: string;
  enabled: boolean;
  config: any;
}

export default function EndpointsPage() {
  const t = useTranslations("endpoints");
  const tc = useTranslations("common");
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .getEndpoints()
      .then((data: any) => {
        const raw = data?.endpoints ?? data ?? {};
        const list: Endpoint[] = Object.entries(raw).map(
          ([name, val]: [string, any]) => ({
            name,
            enabled: val?.enabled ?? true,
            config: val?.config ?? {},
          })
        );
        setEndpoints(list);
      })
      .catch(() => setEndpoints([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const handleToggle = async (ep: Endpoint) => {
    setToggling(ep.name);
    try {
      await api.updateEndpoint(ep.name, {
        enabled: !ep.enabled,
        config: ep.config,
      });
      setEndpoints((prev) =>
        prev.map((e) =>
          e.name === ep.name ? { ...e, enabled: !e.enabled } : e
        )
      );
    } catch {
    } finally {
      setToggling(null);
    }
  };

  return (
    <AppShell>
      <div className="space-y-6 max-w-[1200px]">
        {/* Header */}
        <div>
          <h1 className="text-lg font-semibold text-text-primary">
            {t("title")}
          </h1>
          <p className="text-sm text-text-tertiary mt-1">
            Manage API endpoint availability and configuration
          </p>
        </div>

        {/* Table */}
        <div className="rounded-lg border border-border overflow-hidden">
          {loading ? (
            <div className="flex h-64 items-center justify-center">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-b border-border hover:bg-transparent">
                  <TableHead className="bg-[rgba(255,255,255,0.02)] w-[200px]">
                    {t("name")}
                  </TableHead>
                  <TableHead className="bg-[rgba(255,255,255,0.02)] w-[120px]">
                    Enabled
                  </TableHead>
                  <TableHead className="bg-[rgba(255,255,255,0.02)]">
                    Config
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {endpoints.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={3}
                      className="h-24 text-center text-text-quaternary"
                    >
                      {tc("noData")}
                    </TableCell>
                  </TableRow>
                ) : (
                  endpoints.map((ep) => (
                    <TableRow key={ep.name}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm text-text-secondary font-medium">
                            {ep.name}
                          </span>
                          <Badge variant="outline" className="text-[10px]">
                            /api/v1/admin/{ep.name}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell>
                        <button
                          onClick={() => handleToggle(ep)}
                          disabled={toggling === ep.name}
                          className={`
                            relative inline-flex h-6 w-11 items-center rounded-full transition-colors
                            focus:outline-none focus:ring-2 focus:ring-accent focus:ring-offset-2 focus:ring-offset-[#08090a]
                            ${ep.enabled ? "bg-accent" : "bg-[rgba(255,255,255,0.1)]"}
                            ${toggling === ep.name ? "opacity-60 cursor-wait" : "cursor-pointer"}
                          `}
                          aria-label={`Toggle ${ep.name}`}
                        >
                          <span
                            className={`
                              inline-block h-4 w-4 rounded-full bg-white shadow-sm transform transition-transform
                              ${ep.enabled ? "translate-x-6" : "translate-x-1"}
                            `}
                          />
                        </button>
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-text-tertiary font-mono">
                          {ep.config && Object.keys(ep.config).length > 0
                            ? JSON.stringify(ep.config)
                            : "{}"}
                        </span>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </AppShell>
  );
}
