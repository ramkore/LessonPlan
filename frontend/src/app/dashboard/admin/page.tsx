"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { AdminStats } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
  Users,
  FileText,
  ShieldCheck,
  UserCheck,
  CalendarDays,
  PartyPopper,
} from "lucide-react";

export default function AdminDashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [calendarCount, setCalendarCount] = useState(0);
  const [holidayCount, setHolidayCount] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (user && user.role !== "admin") {
      router.push("/dashboard");
    }
  }, [user, router]);

  useEffect(() => {
    if (user?.role === "admin") {
      loadData();
    }
  }, [user]);

  async function loadData() {
    setLoading(true);
    try {
      const [s, c, h] = await Promise.all([
        api.get<AdminStats>("/api/admin/stats"),
        api.get<any[]>("/api/admin/calendar"),
        api.get<any[]>("/api/admin/holidays"),
      ]);
      setStats(s);
      setCalendarCount(c.length);
      setHolidayCount(h.length);
    } catch {
      toast.error("Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }

  if (!user || user.role !== "admin") return null;

  const summaryCards = [
    { label: "Total Users", value: stats?.total_users ?? 0, icon: Users, href: "/dashboard/admin/users", color: "text-blue-600", bg: "bg-blue-50" },
    { label: "Faculty", value: stats?.total_faculty ?? 0, icon: UserCheck, href: "/dashboard/admin/users", color: "text-green-600", bg: "bg-green-50" },
    { label: "Admins", value: stats?.total_admins ?? 0, icon: ShieldCheck, href: "/dashboard/admin/users", color: "text-orange-600", bg: "bg-orange-50" },
    { label: "Total Plans", value: stats?.total_plans ?? 0, sub: stats ? `${stats.plans_this_month} this month` : undefined, icon: FileText, href: "/dashboard/admin/plans", color: "text-purple-600", bg: "bg-purple-50" },
    { label: "Calendar Entries", value: calendarCount, icon: CalendarDays, href: "/dashboard/calendar", color: "text-indigo-600", bg: "bg-indigo-50" },
    { label: "Holidays", value: holidayCount, icon: PartyPopper, href: "/dashboard/holidays", color: "text-pink-600", bg: "bg-pink-50" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Admin Dashboard</h1>
        <p className="text-muted-foreground">
          Institution overview and administration
        </p>
      </div>

      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2"><Skeleton className="h-4 w-24" /></CardHeader>
              <CardContent><Skeleton className="h-8 w-16" /></CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {summaryCards.map((card) => (
            <Link key={card.label} href={card.href}>
              <Card className="transition-shadow hover:shadow-md">
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium">{card.label}</CardTitle>
                  <div className={`flex size-9 items-center justify-center rounded-lg ${card.bg}`}>
                    <card.icon className={`size-4 ${card.color}`} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{card.value}</div>
                  {card.sub && (
                    <p className="text-xs text-muted-foreground">{card.sub}</p>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
