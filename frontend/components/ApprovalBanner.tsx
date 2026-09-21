"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, User } from "@/lib/api";

const APPROVAL_TTL_SECONDS = 300;

export function ApprovalBanner() {
  const [remaining, setRemaining] = useState<number | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const router = useRouter();

  useEffect(() => {
    try {
      const stored = localStorage.getItem("vault_user");
      if (!stored) return;
      const u: User = JSON.parse(stored);
      if (u.is_approved || !u.approval_screen_started_at) return;
      setUser(u);
      const startedAt = new Date(u.approval_screen_started_at).getTime();
      const tick = () => {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000);
        const left = APPROVAL_TTL_SECONDS - elapsed;
        if (left <= 0) {
          api.logout();
          router.push("/login");
          return;
        }
        setRemaining(left);
      };
      tick();
      const id = setInterval(tick, 1000);
      return () => clearInterval(id);
    } catch {}
  }, [router]);

  if (!user || user.is_approved || remaining === null) return null;

  const min = String(Math.floor(remaining / 60)).padStart(2, "0");
  const sec = String(remaining % 60).padStart(2, "0");
  const urgent = remaining <= 60;

  return (
    <div
      className={`sticky top-16 z-40 border-b-2 px-4 py-2.5 text-center text-sm font-medium mono tracking-wide ${
        urgent
          ? "bg-red-900/40 border-red-700 text-red-300"
          : "bg-primary/10 border-primary text-primary"
      }`}
    >
      Account pending admin approval. Access expires in{" "}
      <span className={`font-bold ${urgent ? "text-red-400 blink" : "accent"}`}>
        {min}:{sec}
      </span>
    </div>
  );
}
