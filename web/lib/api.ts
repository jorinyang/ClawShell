"use client";

const API_BASE = "/api/v1";

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Auth
  login: (account_id: string, password: string) =>
    request<{ token: string; user: any; must_change_pwd: boolean }>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ account_id, password }) }
    ),

  getMe: () => request<any>("/auth/me"),

  changePassword: (old_password: string, new_password: string) =>
    request<any>("/auth/password", {
      method: "PUT",
      body: JSON.stringify({ old_password, new_password }),
    }),

  // Dashboard
  getDashboard: () =>
    request<{
      total_users: number;
      active_users: number;
      total_credentials: number;
      total_nodes: number;
      online_nodes: number;
      active_sessions: number;
      recent_audit_count: number;
    }>("/admin/dashboard"),

  // System
  getSystem: () => request<any>("/admin/system"),

  // Users
  getUsers: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<{ users: any[]; total: number }>(`/admin/users${qs}`);
  },

  createUser: (data: any) =>
    request<any>("/admin/users", { method: "POST", body: JSON.stringify(data) }),

  updateUser: (id: string, data: any) =>
    request<any>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  deleteUser: (id: string) =>
    request<any>(`/admin/users/${id}`, { method: "DELETE" }),

  resetUserPassword: (id: string, password: string) =>
    request<any>(`/admin/users/${id}/password`, {
      method: "PUT",
      body: JSON.stringify({ new_password: password }),
    }),

  // Shared Credentials
  getSharedCredentials: () => request<any[]>("/admin/shared-credentials"),

  createSharedCredential: (data: any) =>
    request<any>("/admin/shared-credentials", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateSharedCredential: (id: string, data: any) =>
    request<any>(`/admin/shared-credentials/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteSharedCredential: (id: string) =>
    request<any>(`/admin/shared-credentials/${id}`, { method: "DELETE" }),

  // Nodes
  getNodes: () => request<any[]>("/admin/nodes"),

  updateNode: (id: string, data: any) =>
    request<any>(`/admin/nodes/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  deleteNode: (id: string) =>
    request<any>(`/admin/nodes/${id}`, { method: "DELETE" }),

  // Audit Logs
  getAuditLogs: (params?: Record<string, string>) => {
    const qs = params ? "?" + new URLSearchParams(params).toString() : "";
    return request<{ logs: any[]; total: number }>(`/admin/audit-logs${qs}`);
  },

  // Endpoints
  getEndpoints: () =>
    request<{ endpoints: Record<string, { enabled: boolean; config: any }> }>("/admin/endpoints"),

  updateEndpoint: (id: string, data: { enabled?: boolean; config?: any }) =>
    request<any>(`/admin/endpoints/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  // My Credentials
  getMyCredentials: () => request<any[]>("/credentials"),
};
