"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/auth-store";

export default function HomePage() {
  const router = useRouter();
  const { token, user } = useAuthStore();

  useEffect(() => {
    if (!token) {
      router.replace("/login");
    } else if (user?.must_change_pwd) {
      router.replace("/change-password");
    }
  }, [token, user, router]);

  if (!token) return null;

  return <DashboardContent />;
}

function DashboardContent() {
  return <DashboardPage />;
}

import DashboardPage from "./dashboard-page";
