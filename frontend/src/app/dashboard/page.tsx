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
import { Clock, BookOpen } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  CalendarEntry,
  Holiday,
  TimetableEntry,
  Subject,
} from "@/lib/types";

interface DashboardCounts {
  timetable: number;
  subjects: number;
}

const summaryCards = [
  {
    key: "timetable" as const,
    label: "Timetable Entries",
    description: "Your scheduled periods",
    href: "/dashboard/timetable",
    icon: Clock,
    color: "text-green-600",
    bg: "bg-green-50",
  },
  {
    key: "subjects" as const,
    label: "Subjects",
    description: "Your uploaded syllabi",
    href: "/dashboard/syllabus",
    icon: BookOpen,
    color: "text-purple-600",
    bg: "bg-purple-50",
  },
];

export default function DashboardPage() {
  const [counts, setCounts] = useState<DashboardCounts | null>(null);
  const [calendar, setCalendar] = useState<CalendarEntry[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchCounts() {
      try {
        const [calendarData, holidaysData, timetableData, subjectsData] = await Promise.all([
          api.get<CalendarEntry[]>("/api/calendar").catch(() => []),
          api.get<Holiday[]>("/api/holidays").catch(() => []),
          api.get<TimetableEntry[]>("/api/timetable").catch(() => []),
          api.get<Subject[]>("/api/subjects").catch(() => []),
        ]);
        setCalendar(calendarData);
        setHolidays(holidaysData);
        setCounts({
          timetable: timetableData.length,
          subjects: subjectsData.length,
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
          Overview of your lesson plan data and institution calendar
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
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

      {/* Institution Calendar (Read-only) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Institution Academic Calendar</CardTitle>
          <CardDescription>Provided by administration</CardDescription>
        </CardHeader>
        <CardContent>
          {calendar.length === 0 ? (
            <p className="text-sm text-muted-foreground">No calendar entries available</p>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Description</TableHead>
                    <TableHead>From</TableHead>
                    <TableHead>To</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {calendar.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="font-medium">{entry.description}</TableCell>
                      <TableCell>{new Date(entry.from_date).toLocaleDateString()}</TableCell>
                      <TableCell>{new Date(entry.to_date).toLocaleDateString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Holidays (Read-only) */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Institution Holidays</CardTitle>
          <CardDescription>Provided by administration</CardDescription>
        </CardHeader>
        <CardContent>
          {holidays.length === 0 ? (
            <p className="text-sm text-muted-foreground">No holidays available</p>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Occasion</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {holidays.map((holiday) => (
                    <TableRow key={holiday.id}>
                      <TableCell className="font-medium">{holiday.occasion}</TableCell>
                      <TableCell>{new Date(holiday.holiday_date).toLocaleDateString()}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
