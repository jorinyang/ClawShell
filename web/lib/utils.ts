import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleString();
}

export function truncateId(id: string, len = 8): string {
  if (!id) return "-";
  return id.length > len ? id.slice(0, len) + "…" : id;
}
