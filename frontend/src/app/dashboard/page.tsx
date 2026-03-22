"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { CalendarDays, PartyPopper, Clock, BookOpen } from "lucide-react";
import type {
  CalendarEntry,
  Holiday,
  TimetableEntry,
  Subject,
} from "@/lib/types";

interface DashboardCounts {
  calendar: number;
  holidays: number;
  timetable: number;
  subjects: number;
}

const summaryCards = [
  {
    key: "calendar" as const,
    label: "Calendar Entries",
    description: "Academic calendar events",
    href: "/dashboard/calendar",
    icon: CalendarDays,
    color: "text-blue-600",
    bg: "bg-blue-50",
  },
  {
    key: "holidays" as const,
    label: "Holidays",
    description: "Registered holidays",
    href: "/dashboard/holidays",
    icon: PartyPopper,
    color: "text-orange-600",
    bg: "bg-orange-50",
  },
  {
    key: "timetable" as const,
    label: "Timetable Entries",
    description: "Scheduled periods",
    href: "/dashboard/timetable",
    icon: Clock,
    color: "text-green-600",
    bg: "bg-green-50",
  },
  {
    key: "subjects" as const,
    label: "Subjects",
    description: "Uploaded syllabi",
    href: "/dashboard/syllabus",
    icon: BookOpen,
    color: "text-purple-600",
    bg: "bg-purple-50",
  },
];

export default function DashboardPage() {
  const [counts, setCounts] = useState<DashboardCounts | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchCounts() {
      try {
        const [calendar, holidays, timetable, subjects] = await Promise.all([
          api.get<CalendarEntry[]>("/api/calendar").catch(() => []),
          api.get<Holiday[]>("/api/holidays").catch(() => []),
          api.get<TimetableEntry[]>("/api/timetable").catch(() => []),
          api.get<Subject[]>("/api/subjects").catch(() => []),
        ]);
        setCounts({
          calendar: calendar.length,
          holidays: holidays.length,
          timetable: timetable.length,
          subjects: subjects.length,
        });
      } catch {
        toast.error("Failed to load dashboard data");
      } finally {
        setIsLoading(false);
      }
    }
    fetchCounts();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Overview of your lesson plan data
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {summaryCards.map((card) => (
          <Link key={card.key} href={card.href}>
            <Card className="transition-shadow hover:shadow-md">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardDescription>{card.label}</CardDescription>
                  <div
                    className={`flex size-9 items-center justify-center rounded-lg ${card.bg}`}
                  >
                    <card.icon className={`size-4 ${card.color}`} />
                  </div>
                </div>
                <CardTitle className="text-3xl font-bold tabular-nums">
                  {isLoading ? (
                    <Skeleton className="h-9 w-16" />
                  ) : (
                    counts?.[card.key] ?? 0
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-xs text-muted-foreground">
                  {card.description}
                </p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
