"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { AppShell } from "@/components/AppShell";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import { Plus, Pencil, Trash2, KeyRound, X } from "lucide-react";

export default function UsersPage() {
  const t = useTranslations("users");
  const tc = useTranslations("common");
  const { user: currentUser } = useAuthStore();
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<any>(null);
  const [formData, setFormData] = useState({
    account_id: "",
    display_name: "",
    password: "",
    role: "user",
  });

  const isCoreAdmin = currentUser?.role === "core_admin";
  const isAdmin = currentUser?.role === "admin" || isCoreAdmin;

  const load = () => {
    setLoading(true);
    api
      .getUsers()
      .then((res) => setUsers(res.users || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editing) {
        const { password, ...rest } = formData;
        const updateData = password ? { ...rest, password } : rest;
        await api.updateUser(editing.user_id, updateData);
      } else {
        await api.createUser(formData);
      }
      setShowForm(false);
      setEditing(null);
      setFormData({ account_id: "", display_name: "", password: "", role: "user" });
      load();
    } catch {}
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t("confirmDelete"))) return;
    try {
      await api.deleteUser(id);
      load();
    } catch {}
  };

  const handleResetPassword = async (id: string) => {
    const pwd = prompt("New password:");
    if (!pwd) return;
    try {
      await api.resetUserPassword(id, pwd);
    } catch {}
  };

  const startEdit = (u: any) => {
    setEditing(u);
    setFormData({
      account_id: u.account_id,
      display_name: u.display_name,
      password: "",
      role: u.role,
    });
    setShowForm(true);
  };

  const columns = [
    {
      key: "user_id",
      header: t("userId"),
      render: (u: any) => <span className="font-mono text-xs text-text-quaternary">{u.user_id?.slice(0, 8)}…</span>,
    },
    { key: "account_id", header: t("accountId"), className: "text-text-secondary" },
    { key: "display_name", header: t("displayName"), className: "text-text-secondary" },
    {
      key: "role",
      header: t("role"),
      render: (u: any) => (
        <Badge variant={u.role === "core_admin" ? "default" : u.role === "admin" ? "secondary" : "outline"}>
          {t(`roles.${u.role}`)}
        </Badge>
      ),
    },
    {
      key: "must_change_pwd",
      header: t("mustChangePwd"),
      render: (u: any) => (
        <span className="text-xs text-text-quaternary">
          {u.must_change_pwd ? tc("yes") : tc("no")}
        </span>
      ),
    },
    {
      key: "created_at",
      header: t("createdAt"),
      render: (u: any) => <span className="text-xs text-text-quaternary">{formatDate(u.created_at)}</span>,
    },
    {
      key: "actions",
      header: tc("actions"),
      className: "w-[100px]",
      render: (u: any) => (
        <div className="flex gap-0.5">
          {isAdmin && (
            <Button variant="ghost" size="icon" onClick={() => startEdit(u)} title={t("editUser")}>
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          )}
          {isAdmin && (
            <Button variant="ghost" size="icon" onClick={() => handleResetPassword(u.user_id)} title={t("resetPassword")}>
              <KeyRound className="h-3.5 w-3.5" />
            </Button>
          )}
          {isCoreAdmin && (
            <Button variant="ghost" size="icon" onClick={() => handleDelete(u.user_id)} title={t("deleteUser")}>
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <AppShell>
      <div className="space-y-4 max-w-[1200px]">
        {/* Header */}
        <div className="flex items-center justify-between">
          <p className="text-xs text-text-quaternary">{tc("total")}: {users.length} {tc("items")}</p>
          {isCoreAdmin && (
            <Button
              variant="default"
              size="sm"
              onClick={() => {
                setEditing(null);
                setFormData({ account_id: "", display_name: "", password: "", role: "user" });
                setShowForm(true);
              }}
            >
              <Plus className="mr-1.5 h-3.5 w-3.5" /> {t("addUser")}
            </Button>
          )}
        </div>

        {/* Form */}
        {showForm && (
          <div className="rounded-lg border border-border bg-[rgba(255,255,255,0.02)] p-5">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium text-text-secondary">
                {editing ? t("editUser") : t("addUser")}
              </span>
              <Button variant="ghost" size="icon" onClick={() => { setShowForm(false); setEditing(null); }}>
                <X className="h-4 w-4" />
              </Button>
            </div>
            <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>{t("accountId")}</Label>
                <Input
                  value={formData.account_id}
                  onChange={(e) => setFormData({ ...formData, account_id: e.target.value })}
                  disabled={!!editing}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label>{t("displayName")}</Label>
                <Input
                  value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label>{tc("password")}{editing ? " (leave empty to keep)" : ""}</Label>
                <Input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required={!editing}
                />
              </div>
              <div className="space-y-1.5">
                <Label>{t("role")}</Label>
                <Select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                  options={[
                    { value: "user", label: t("roles.user") },
                    { value: "admin", label: t("roles.admin") },
                    ...(isCoreAdmin ? [{ value: "core_admin", label: t("roles.core_admin") }] : []),
                  ]}
                />
              </div>
              <div className="col-span-2">
                <Button type="submit" variant="default">{tc("save")}</Button>
              </div>
            </form>
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div className="flex h-64 items-center justify-center">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-accent border-t-transparent" />
          </div>
        ) : (
          <DataTable columns={columns} data={users} emptyMessage={tc("noData")} />
        )}
      </div>
    </AppShell>
  );
}
