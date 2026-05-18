"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { AppShell } from "@/components/AppShell";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import {
  Plus,
  Pencil,
  Trash2,
  X,
  Key,
  Cloud,
  Cpu,
  Share2,
  AlertTriangle,
} from "lucide-react";

type CredType = "api-key" | "access-key" | "token-plan";

interface Credential {
  cred_id: string;
  user_id: string;
  service: string;
  cred_type: string;
  name: string;
  description: string;
  api_key?: string | null;
  base_url?: string | null;
  access_key_id?: string | null;
  access_key_secret?: string | null;
  model?: string | null;
  cred_key?: string;
  cred_value_masked?: string | null;
  created_at: string;
  updated_at: string;
}

interface SharedCredential {
  sc_id: string;
  service: string;
  cred_type: string;
  name: string;
  description: string;
  created_by: string;
  created_at: string;
  updated_at: string;
  api_key?: string | null;
  base_url?: string | null;
  access_key_id?: string | null;
  access_key_secret?: string | null;
  model?: string | null;
  cred_key?: string;
  cred_value_masked?: string | null;
}

const VALID_TYPES: CredType[] = ["api-key", "access-key", "token-plan"];
const isLegacy = (t: string) => !VALID_TYPES.includes(t as CredType);

const EMPTY_FORM = {
  service: "",
  cred_type: "api-key" as CredType,
  name: "",
  api_key: "",
  base_url: "",
  access_key_id: "",
  access_key_secret: "",
  model: "",
  description: "",
};

const TYPE_COLORS: Record<string, string> = {
  "api-key": "bg-blue-500/15 text-blue-400 border-blue-500/30",
  "access-key": "bg-amber-500/15 text-amber-400 border-amber-500/30",
  "token-plan": "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  legacy: "bg-zinc-500/15 text-zinc-400 border-zinc-500/30",
};

const TYPE_ICONS: Record<string, React.ReactNode> = {
  "api-key": <Key className="h-3 w-3" />,
  "access-key": <Cloud className="h-3 w-3" />,
  "token-plan": <Cpu className="h-3 w-3" />,
  legacy: <Key className="h-3 w-3" />,
};

export default function CredentialsPage() {
  const t = useTranslations("credentials");
  const tc = useTranslations("common");
  const [creds, setCreds] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Credential | null>(null);
  const [formData, setFormData] = useState({ ...EMPTY_FORM });
  const [tab, setTab] = useState<"my" | "shared">("my");
  const [sharedCreds, setSharedCreds] = useState<SharedCredential[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);

  // Fix #4: use ref to prevent double-loading (React StrictMode / re-renders)
  const loadingRef = useRef(false);
  const sharedLoadingRef = useRef(false);

  const load = useCallback(() => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    api
      .getMyCredentials()
      .then((res) => {
        setCreds(Array.isArray(res) ? res : []);
      })
      .catch(() => setCreds([]))
      .finally(() => {
        setLoading(false);
        loadingRef.current = false;
      });
  }, []);

  const loadShared = useCallback(() => {
    if (sharedLoadingRef.current) return;
    sharedLoadingRef.current = true;
    api
      .getSharedCredentials()
      .then((res) => {
        setSharedCreds(Array.isArray(res) ? res : []);
      })
      .catch(() => setSharedCreds([]))
      .finally(() => {
        sharedLoadingRef.current = false;
      });
  }, []);

  useEffect(() => {
    // Check user role for admin features
    try {
      const userStr = localStorage.getItem("user");
      if (userStr) {
        const user = JSON.parse(userStr);
        setIsAdmin(
          user.role === "admin" || user.role === "core_admin"
        );
      }
    } catch {}
    load();
    loadShared();
  }, [load, loadShared]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload: Record<string, any> = {
        service: formData.service,
        cred_type: formData.cred_type,
        name: formData.name,
        description: formData.description,
      };

      if (formData.cred_type === "api-key") {
        payload.api_key = formData.api_key;
        payload.base_url = formData.base_url;
      } else if (formData.cred_type === "access-key") {
        payload.access_key_id = formData.access_key_id;
        payload.access_key_secret = formData.access_key_secret;
      } else if (formData.cred_type === "token-plan") {
        payload.api_key = formData.api_key;
        payload.base_url = formData.base_url;
        payload.model = formData.model;
      }

      if (editing) {
        await api.updateCredential(editing.cred_id, payload);
      } else {
        await api.createCredential(payload);
      }
      setShowForm(false);
      setEditing(null);
      setFormData({ ...EMPTY_FORM });
      loadingRef.current = false;
      load();
    } catch (err) {
      console.error("Failed to save credential:", err);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t("confirmDelete"))) return;
    try {
      await api.deleteCredential(id);
      loadingRef.current = false;
      load();
    } catch {}
  };

  // Fix #3: Delete shared credential
  const handleDeleteShared = async (id: string) => {
    if (!confirm(t("confirmDelete"))) return;
    try {
      await api.deleteSharedCredential(id);
      sharedLoadingRef.current = false;
      loadShared();
    } catch {}
  };

  // Fix #2: Share own credential to shared pool
  const handleShare = async (c: Credential) => {
    if (!confirm(t("confirmShare") || "Share this credential to the shared pool?")) return;
    try {
      await api.createSharedCredential({
        service: c.service,
        cred_type: c.cred_type,
        name: c.name,
        description: c.description,
      });
      sharedLoadingRef.current = false;
      loadShared();
    } catch (err) {
      console.error("Failed to share credential:", err);
    }
  };

  // Fix #1: Block editing legacy credentials
  const startEdit = (c: Credential) => {
    if (isLegacy(c.cred_type)) return; // legacy types are read-only
    setEditing(c);
    setFormData({
      service: c.service,
      cred_type: (c.cred_type as CredType) || "api-key",
      name: c.name || c.cred_key || "",
      api_key: "",
      base_url: c.base_url || "",
      access_key_id: c.access_key_id || "",
      access_key_secret: "",
      model: c.model || "",
      description: c.description || "",
    });
    setShowForm(true);
  };

  const startCreate = () => {
    setEditing(null);
    setFormData({ ...EMPTY_FORM });
    setShowForm(true);
  };

  const renderTypeFields = () => {
    switch (formData.cred_type) {
      case "api-key":
        return (
          <>
            <div className="space-y-1.5">
              <Label>{t("apiKey")}</Label>
              <Input
                type="password"
                value={formData.api_key}
                onChange={(e) =>
                  setFormData({ ...formData, api_key: e.target.value })
                }
                placeholder={t("placeholders.apiKey")}
                required={!editing}
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("baseUrl")}</Label>
              <Input
                value={formData.base_url}
                onChange={(e) =>
                  setFormData({ ...formData, base_url: e.target.value })
                }
                placeholder={t("placeholders.baseUrl")}
              />
            </div>
          </>
        );
      case "access-key":
        return (
          <>
            <div className="space-y-1.5">
              <Label>{t("accessKeyId")}</Label>
              <Input
                value={formData.access_key_id}
                onChange={(e) =>
                  setFormData({ ...formData, access_key_id: e.target.value })
                }
                placeholder={t("placeholders.accessKeyId")}
                required={!editing}
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("accessKeySecret")}</Label>
              <Input
                type="password"
                value={formData.access_key_secret}
                onChange={(e) =>
                  setFormData({
                    ...formData,
                    access_key_secret: e.target.value,
                  })
                }
                placeholder={t("placeholders.accessKeySecret")}
              />
            </div>
          </>
        );
      case "token-plan":
        return (
          <>
            <div className="space-y-1.5">
              <Label>{t("apiKey")}</Label>
              <Input
                type="password"
                value={formData.api_key}
                onChange={(e) =>
                  setFormData({ ...formData, api_key: e.target.value })
                }
                placeholder={t("placeholders.apiKey")}
                required={!editing}
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("baseUrl")}</Label>
              <Input
                value={formData.base_url}
                onChange={(e) =>
                  setFormData({ ...formData, base_url: e.target.value })
                }
                placeholder={t("placeholders.baseUrl")}
              />
            </div>
            <div className="space-y-1.5">
              <Label>{t("model")}</Label>
              <Input
                value={formData.model}
                onChange={(e) =>
                  setFormData({ ...formData, model: e.target.value })
                }
                placeholder={t("placeholders.model")}
              />
            </div>
          </>
        );
      default:
        return null;
    }
  };

  // ── My credentials columns ──
  const myColumns = [
    {
      key: "name",
      header: t("name"),
      render: (c: Credential) => (
        <span className="text-sm font-medium text-text-secondary">
          {c.name || c.cred_key || "-"}
        </span>
      ),
    },
    {
      key: "service",
      header: t("service"),
      render: (c: Credential) => (
        <span className="text-xs text-text-tertiary font-mono">
          {c.service}
        </span>
      ),
    },
    {
      key: "cred_type",
      header: t("type"),
      render: (c: Credential) => (
        <span
          className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border ${
            TYPE_COLORS[c.cred_type] || TYPE_COLORS.legacy
          }`}
        >
          {TYPE_ICONS[c.cred_type]}
          {t(`types.${c.cred_type}`)}
        </span>
      ),
    },
    {
      key: "details",
      header: "Details",
      render: (c: Credential) => {
        if (c.cred_type === "api-key" || c.cred_type === "token-plan") {
          return (
            <div className="flex flex-col gap-0.5">
              {c.api_key && (
                <span className="text-xs text-text-quaternary font-mono">
                  {c.api_key}
                </span>
              )}
              {c.base_url && (
                <span className="text-[11px] text-text-quaternary">
                  {c.base_url}
                </span>
              )}
              {c.model && (
                <span className="text-[11px] text-accent/70">{c.model}</span>
              )}
            </div>
          );
        }
        if (c.cred_type === "access-key") {
          return (
            <div className="flex flex-col gap-0.5">
              {c.access_key_id && (
                <span className="text-xs text-text-quaternary font-mono">
                  {c.access_key_id}
                </span>
              )}
              {c.access_key_secret && (
                <span className="text-xs text-text-quaternary font-mono">
                  {c.access_key_secret}
                </span>
              )}
            </div>
          );
        }
        // Legacy
        return (
          <span className="text-xs text-text-quaternary font-mono">
            {c.cred_value_masked || "****"}
          </span>
        );
      },
    },
    {
      key: "description",
      header: t("description"),
      render: (c: Credential) => (
        <span className="text-xs text-text-quaternary max-w-[200px] truncate block">
          {c.description || "-"}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Created",
      render: (c: Credential) => (
        <span className="text-xs text-text-quaternary">
          {formatDate(c.created_at)}
        </span>
      ),
    },
    {
      key: "actions",
      header: tc("actions"),
      className: "w-[120px]",
      render: (c: Credential) => {
        const legacy = isLegacy(c.cred_type);
        return (
          <div className="flex gap-0.5">
            {/* Fix #1: Legacy types — no edit, only delete */}
            {!legacy && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => startEdit(c)}
                title={t("editCredential")}
              >
                <Pencil className="h-3.5 w-3.5" />
              </Button>
            )}
            {legacy && (
              <span
                className="inline-flex items-center gap-1 px-2 text-[10px] text-amber-400/70"
                title="Legacy credentials cannot be edited"
              >
                <AlertTriangle className="h-3 w-3" />
              </span>
            )}
            {/* Fix #2: Share button for admins */}
            {isAdmin && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => handleShare(c)}
                title={t("shareToShared") || "Share to shared pool"}
              >
                <Share2 className="h-3.5 w-3.5 text-accent/70" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => handleDelete(c.cred_id)}
              title={t("deleteCredential")}
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
          </div>
        );
      },
    },
  ];

  // Fix #3: Shared credentials columns — with delete action
  const sharedColumns: { key: string; header: string; className?: string; render: (c: any) => React.ReactNode }[] = [
    {
      key: "name",
      header: t("name"),
      render: (c: any) => (
        <span className="text-sm font-medium text-text-secondary">
          {c.name || c.cred_key || "-"}
        </span>
      ),
    },
    {
      key: "service",
      header: t("service"),
      render: (c: any) => (
        <span className="text-xs text-text-tertiary font-mono">{c.service}</span>
      ),
    },
    {
      key: "cred_type",
      header: t("type"),
      render: (c: any) => (
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border ${TYPE_COLORS[c.cred_type] || TYPE_COLORS.legacy}`}>
          {TYPE_ICONS[c.cred_type]}
          {t(`types.${c.cred_type}`)}
        </span>
      ),
    },
    {
      key: "description",
      header: t("description"),
      render: (c: any) => (
        <span className="text-xs text-text-quaternary max-w-[200px] truncate block">
          {c.description || "-"}
        </span>
      ),
    },
    {
      key: "created_at",
      header: "Created",
      render: (c: any) => (
        <span className="text-xs text-text-quaternary">
          {formatDate(c.created_at)}
        </span>
      ),
    },
    {
      key: "actions",
      header: tc("actions"),
      className: "w-[80px]",
      render: (c: any) => (
        <div className="flex gap-0.5">
          {isAdmin && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => handleDeleteShared(c.sc_id)}
              title={t("deleteCredential")}
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <AppShell>
      <div className="space-y-4 max-w-[1400px]">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <p className="text-xs text-text-quaternary">
              {tc("total")}:{" "}
              {tab === "my" ? creds.length : sharedCreds.length}{" "}
              {tc("items")}
            </p>
            <div className="flex gap-1 rounded-lg border border-border p-0.5">
              <button
                onClick={() => setTab("my")}
                className={`rounded-md px-3 py-1 text-xs transition-colors ${
                  tab === "my"
                    ? "bg-accent/15 text-accent"
                    : "text-text-quaternary hover:text-text-secondary"
                }`}
              >
                {t("myCredentials")}
              </button>
              <button
                onClick={() => setTab("shared")}
                className={`rounded-md px-3 py-1 text-xs transition-colors ${
                  tab === "shared"
                    ? "bg-accent/15 text-accent"
                    : "text-text-quaternary hover:text-text-secondary"
                }`}
              >
                {t("shared")}
              </button>
            </div>
          </div>
          {tab === "my" && (
            <Button variant="default" size="sm" onClick={startCreate}>
              <Plus className="mr-1.5 h-3.5 w-3.5" /> {t("addCredential")}
            </Button>
          )}
        </div>

        {/* Form */}
        {showForm && tab === "my" && (
          <div className="rounded-lg border border-border bg-[rgba(255,255,255,0.02)] p-5">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium text-text-secondary">
                {editing ? t("editCredential") : t("addCredential")}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setShowForm(false);
                  setEditing(null);
                }}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Row 1: Type, Service, Name */}
              <div className="grid grid-cols-3 gap-4">
                <div className="space-y-1.5">
                  <Label>{t("type")}</Label>
                  <Select
                    value={formData.cred_type}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        cred_type: e.target.value as CredType,
                      })
                    }
                    options={[
                      { value: "api-key", label: t("types.api-key") },
                      { value: "access-key", label: t("types.access-key") },
                      { value: "token-plan", label: t("types.token-plan") },
                    ]}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>{t("service")}</Label>
                  <Input
                    value={formData.service}
                    onChange={(e) =>
                      setFormData({ ...formData, service: e.target.value })
                    }
                    placeholder={t("placeholders.service")}
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>{t("name")}</Label>
                  <Input
                    value={formData.name}
                    onChange={(e) =>
                      setFormData({ ...formData, name: e.target.value })
                    }
                    placeholder={t("placeholders.name")}
                    required
                  />
                </div>
              </div>

              {/* Row 2: Type-specific fields */}
              <div className="grid grid-cols-3 gap-4">
                {renderTypeFields()}
              </div>

              {/* Row 3: Description */}
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-2 space-y-1.5">
                  <Label>{t("description")}</Label>
                  <Input
                    value={formData.description}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        description: e.target.value,
                      })
                    }
                    placeholder={t("placeholders.description")}
                  />
                </div>
              </div>

              <div>
                <Button type="submit" variant="default">
                  {tc("save")}
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : tab === "my" ? (
          <DataTable columns={myColumns} data={creds} emptyMessage={tc("noData")} />
        ) : (
          <DataTable columns={sharedColumns} data={sharedCreds} emptyMessage={tc("noData")} />
        )}
      </div>
    </AppShell>
  );
}
