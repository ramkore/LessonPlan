"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { AdminStats, AdminUser, AdminPlan } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Users,
  FileText,
  ShieldCheck,
  UserCheck,
  Trash2,
  ArrowUpDown,
  Search,
  Eye,
  CalendarDays,
  PartyPopper,
  Clock,
  BookOpen,
  X,
  Database,
} from "lucide-react";

interface UserDetail {
  id: number;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
  calendar_count: number;
  holiday_count: number;
  timetable_count: number;
  subject_count: number;
  plan_count: number;
  calendars: Array<{ id: number; description: string; from_date: string; to_date: string; event_type: string }>;
  holidays: Array<{ id: number; occasion: string; holiday_date: string }>;
  timetables: Array<{ id: number; day: string; period: string; entry: string; branch: string; is_lab: boolean }>;
  subjects: Array<{ id: number; course_code: string; course_title: string }>;
  plans: Array<{ id: number; faculty_name: string; subject_name: string; branch: string; semester: string; is_lab: boolean; planned_lectures: number; generated_at: string }>;
}

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [plans, setPlans] = useState<AdminPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [userSearch, setUserSearch] = useState("");
  const [planSearch, setPlanSearch] = useState("");

  // User detail dialog
  const [detailUser, setDetailUser] = useState<UserDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ open: false, title: "", message: "", onConfirm: () => {} });

  // Calendar and Holidays state
  const [calendarEntries, setCalendarEntries] = useState<any[]>([]);
  const [holidays, setHolidays] = useState<any[]>([]);
  const [showCalendarForm, setShowCalendarForm] = useState(false);
  const [showHolidayForm, setShowHolidayForm] = useState(false);
  const [calendarForm, setCalendarForm] = useState({ description: "", from_date: "", to_date: "", event_type: "teaching" });
  const [holidayForm, setHolidayForm] = useState({ occasion: "", holiday_date: "" });

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
      const [s, u, p, c, h] = await Promise.all([
        api.get<AdminStats>("/api/admin/stats"),
        api.get<AdminUser[]>("/api/admin/users"),
        api.get<AdminPlan[]>("/api/admin/plans"),
        api.get<any[]>("/api/admin/calendar"),
        api.get<any[]>("/api/admin/holidays"),
      ]);
      setStats(s);
      setUsers(u);
      setPlans(p);
      setCalendarEntries(c);
      setHolidays(h);
    } catch {
      toast.error("Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }

  async function addCalendarEntry() {
    if (!calendarForm.description || !calendarForm.from_date || !calendarForm.to_date) {
      toast.error("Please fill all calendar fields");
      return;
    }
    try {
      await api.post("/api/admin/calendar", calendarForm);
      toast.success("Calendar entry added");
      setCalendarForm({ description: "", from_date: "", to_date: "", event_type: "teaching" });
      setShowCalendarForm(false);
      loadData();
    } catch {
      toast.error("Failed to add calendar entry");
    }
  }

  async function deleteCalendarEntry(id: number) {
    setConfirmDialog({
      open: true,
      title: "Delete Calendar Entry",
      message: "Delete this calendar entry? This cannot be undone.",
      onConfirm: async () => {
        try {
          await api.delete(`/api/admin/calendar/${id}`);
          toast.success("Calendar entry deleted");
          loadData();
        } catch {
          toast.error("Failed to delete calendar entry");
        }
        setConfirmDialog((d) => ({ ...d, open: false }));
      },
    });
  }

  async function addHoliday() {
    if (!holidayForm.occasion || !holidayForm.holiday_date) {
      toast.error("Please fill all holiday fields");
      return;
    }
    try {
      await api.post("/api/admin/holidays", holidayForm);
      toast.success("Holiday added");
      setHolidayForm({ occasion: "", holiday_date: "" });
      setShowHolidayForm(false);
      loadData();
    } catch {
      toast.error("Failed to add holiday");
    }
  }

  async function deleteHoliday(id: number) {
    setConfirmDialog({
      open: true,
      title: "Delete Holiday",
      message: "Delete this holiday? This cannot be undone.",
      onConfirm: async () => {
        try {
          await api.delete(`/api/admin/holidays/${id}`);
          toast.success("Holiday deleted");
          loadData();
        } catch {
          toast.error("Failed to delete holiday");
        }
        setConfirmDialog((d) => ({ ...d, open: false }));
      },
    });
  }

  async function viewUserDetail(u: AdminUser) {
    setDetailLoading(true);
    setDetailUser(null);
    try {
      const detail = await api.get<UserDetail>(`/api/admin/users/${u.id}/detail`);
      setDetailUser(detail);
    } catch {
      toast.error("Failed to load user details");
    } finally {
      setDetailLoading(false);
    }
  }

  async function deleteUserData(userId: number) {
    setConfirmDialog({
      open: true,
      title: "Delete All User Data",
      message: "Delete all calendar, holidays, timetable, syllabus, and lesson plan data for this user? The account will be kept. This cannot be undone.",
      onConfirm: async () => {
        try {
          await api.delete(`/api/admin/users/${userId}/data`);
          toast.success("All user data deleted");
          setDetailUser(null);
          loadData();
        } catch {
          toast.error("Failed to delete user data");
        }
        setConfirmDialog((d) => ({ ...d, open: false }));
      },
    });
  }

  async function deletePlan(planId: number) {
    setConfirmDialog({
      open: true,
      title: "Delete Plan",
      message: "Permanently delete this lesson plan? This cannot be undone.",
      onConfirm: async () => {
        try {
          await api.delete(`/api/admin/plans/${planId}`);
          toast.success("Plan deleted");
          loadData();
        } catch {
          toast.error("Failed to delete plan");
        }
        setConfirmDialog((d) => ({ ...d, open: false }));
      },
    });
  }

  async function toggleRole(u: AdminUser) {
    const newRole = u.role === "admin" ? "faculty" : "admin";
    setConfirmDialog({
      open: true,
      title: "Change Role",
      message: `Change ${u.full_name || u.email} from "${u.role}" to "${newRole}"?`,
      onConfirm: async () => {
        try {
          await api.put(`/api/admin/users/${u.id}/role`, { role: newRole });
          toast.success("Role updated");
          loadData();
        } catch {
          toast.error("Failed to update role");
        }
        setConfirmDialog((d) => ({ ...d, open: false }));
      },
    });
  }

  async function deleteUser(u: AdminUser) {
    setConfirmDialog({
      open: true,
      title: "Delete User",
      message: `Permanently delete ${u.full_name || u.email} and all their data? This cannot be undone.`,
      onConfirm: async () => {
        try {
          await api.delete(`/api/admin/users/${u.id}`);
          toast.success("User deleted");
          loadData();
        } catch {
          toast.error("Failed to delete user");
        }
        setConfirmDialog((d) => ({ ...d, open: false }));
      },
    });
  }

  if (!user || user.role !== "admin") return null;

  const filteredUsers = users.filter(
    (u) =>
      u.email.toLowerCase().includes(userSearch.toLowerCase()) ||
      u.full_name.toLowerCase().includes(userSearch.toLowerCase())
  );

  const filteredPlans = plans.filter(
    (p) =>
      p.subject_name.toLowerCase().includes(planSearch.toLowerCase()) ||
      p.faculty_name.toLowerCase().includes(planSearch.toLowerCase()) ||
      p.user_email.toLowerCase().includes(planSearch.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Admin Panel</h1>
        <p className="text-muted-foreground">
          Full management of users, data, and generated lesson plans
        </p>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="calendar">Academic Calendar</TabsTrigger>
          <TabsTrigger value="holidays">Holidays</TabsTrigger>
          <TabsTrigger value="users">Users</TabsTrigger>
          <TabsTrigger value="plans">Generated Plans</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-4">
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Card key={i}>
                  <CardHeader className="pb-2">
                    <Skeleton className="h-4 w-24" />
                  </CardHeader>
                  <CardContent>
                    <Skeleton className="h-8 w-16" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : stats ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium">Total Users</CardTitle>
                  <Users className="size-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.total_users}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium">Admins</CardTitle>
                  <ShieldCheck className="size-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.total_admins}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium">Faculty</CardTitle>
                  <UserCheck className="size-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.total_faculty}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium">Total Plans</CardTitle>
                  <FileText className="size-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stats.total_plans}</div>
                  <p className="text-xs text-muted-foreground">
                    {stats.plans_this_month} this month
                  </p>
                </CardContent>
              </Card>
            </div>
          ) : null}
        </TabsContent>

        {/* Calendar Tab */}
        <TabsContent value="calendar" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Academic Calendar (Institution-wide)</h3>
            <Button onClick={() => setShowCalendarForm(!showCalendarForm)} size="sm">
              <CalendarDays className="size-4 mr-2" />
              Add Entry
            </Button>
          </div>

          {showCalendarForm && (
            <Card>
              <CardContent className="pt-6 space-y-4">
                <div>
                  <label className="text-sm font-medium">Description</label>
                  <Input
                    value={calendarForm.description}
                    onChange={(e) => setCalendarForm({ ...calendarForm, description: e.target.value })}
                    placeholder="e.g., Semester 1"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">From Date</label>
                    <Input
                      type="date"
                      value={calendarForm.from_date}
                      onChange={(e) => setCalendarForm({ ...calendarForm, from_date: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium">To Date</label>
                    <Input
                      type="date"
                      value={calendarForm.to_date}
                      onChange={(e) => setCalendarForm({ ...calendarForm, to_date: e.target.value })}
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button onClick={addCalendarEntry} size="sm">Save</Button>
                  <Button onClick={() => setShowCalendarForm(false)} variant="outline" size="sm">Cancel</Button>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead>From Date</TableHead>
                  <TableHead>To Date</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {calendarEntries.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center text-muted-foreground">
                      No calendar entries yet
                    </TableCell>
                  </TableRow>
                ) : (
                  calendarEntries.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell>{entry.description}</TableCell>
                      <TableCell>{new Date(entry.from_date).toLocaleDateString()}</TableCell>
                      <TableCell>{new Date(entry.to_date).toLocaleDateString()}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteCalendarEntry(entry.id)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* Holidays Tab */}
        <TabsContent value="holidays" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Holiday List (Institution-wide)</h3>
            <Button onClick={() => setShowHolidayForm(!showHolidayForm)} size="sm">
              <PartyPopper className="size-4 mr-2" />
              Add Holiday
            </Button>
          </div>

          {showHolidayForm && (
            <Card>
              <CardContent className="pt-6 space-y-4">
                <div>
                  <label className="text-sm font-medium">Occasion</label>
                  <Input
                    value={holidayForm.occasion}
                    onChange={(e) => setHolidayForm({ ...holidayForm, occasion: e.target.value })}
                    placeholder="e.g., Republic Day"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Date</label>
                  <Input
                    type="date"
                    value={holidayForm.holiday_date}
                    onChange={(e) => setHolidayForm({ ...holidayForm, holiday_date: e.target.value })}
                  />
                </div>
                <div className="flex gap-2">
                  <Button onClick={addHoliday} size="sm">Save</Button>
                  <Button onClick={() => setShowHolidayForm(false)} variant="outline" size="sm">Cancel</Button>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Occasion</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {holidays.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-muted-foreground">
                      No holidays yet
                    </TableCell>
                  </TableRow>
                ) : (
                  holidays.map((holiday) => (
                    <TableRow key={holiday.id}>
                      <TableCell>{holiday.occasion}</TableCell>
                      <TableCell>{new Date(holiday.holiday_date).toLocaleDateString()}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteHoliday(holiday.id)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </TabsContent>

        {/* Users Tab */}
        <TabsContent value="users" className="space-y-4">
          <div className="flex items-center gap-2">
            <Search className="size-4 text-muted-foreground" />
            <Input
              placeholder="Search users..."
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
              className="max-w-sm"
            />
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Plans</TableHead>
                    <TableHead>Joined</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        No users found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredUsers.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell className="font-medium">{u.full_name || "—"}</TableCell>
                        <TableCell>{u.email}</TableCell>
                        <TableCell>
                          <Badge variant={u.role === "admin" ? "default" : "outline"}>
                            {u.role}
                          </Badge>
                        </TableCell>
                        <TableCell>{u.plan_count}</TableCell>
                        <TableCell>{new Date(u.created_at).toLocaleDateString()}</TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => viewUserDetail(u)}
                              title="View user data"
                            >
                              <Eye className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleRole(u)}
                              disabled={u.id === user.id}
                              title={u.id === user.id ? "Cannot change your own role" : u.role === "admin" ? "Demote to faculty" : "Promote to admin"}
                            >
                              <ArrowUpDown className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => deleteUser(u)}
                              disabled={u.id === user.id}
                              className="text-destructive hover:text-destructive"
                              title={u.id === user.id ? "Cannot delete yourself" : "Delete user"}
                            >
                              <Trash2 className="size-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>

        {/* Plans Tab */}
        <TabsContent value="plans" className="space-y-4">
          <div className="flex items-center gap-2">
            <Search className="size-4 text-muted-foreground" />
            <Input
              placeholder="Search plans..."
              value={planSearch}
              onChange={(e) => setPlanSearch(e.target.value)}
              className="max-w-sm"
            />
          </div>

          {loading ? (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Faculty</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Branch</TableHead>
                    <TableHead>Sem</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Lectures</TableHead>
                    <TableHead>Generated</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPlans.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center text-muted-foreground">
                        No plans found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredPlans.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell className="text-xs">{p.user_email}</TableCell>
                        <TableCell>{p.faculty_name}</TableCell>
                        <TableCell className="font-medium">{p.subject_name}</TableCell>
                        <TableCell>{p.branch}</TableCell>
                        <TableCell>{p.semester}</TableCell>
                        <TableCell>
                          <Badge variant={p.is_lab ? "default" : "outline"}>
                            {p.is_lab ? "Lab" : "Theory"}
                          </Badge>
                        </TableCell>
                        <TableCell>{p.planned_lectures}</TableCell>
                        <TableCell>{new Date(p.generated_at).toLocaleDateString()}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deletePlan(p.id)}
                            className="text-destructive hover:text-destructive"
                            title="Delete plan"
                          >
                            <Trash2 className="size-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* User Detail Dialog */}
      <Dialog open={detailUser !== null || detailLoading} onOpenChange={(open) => { if (!open) { setDetailUser(null); setDetailLoading(false); } }}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          {detailLoading ? (
            <div className="space-y-4 py-4">
              <Skeleton className="h-6 w-48" />
              <Skeleton className="h-32 w-full" />
            </div>
          ) : detailUser ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {detailUser.full_name || detailUser.email}
                  <Badge variant={detailUser.role === "admin" ? "default" : "outline"}>
                    {detailUser.role}
                  </Badge>
                </DialogTitle>
                <p className="text-sm text-muted-foreground">{detailUser.email}</p>
              </DialogHeader>

              {/* Data summary cards */}
              <div className="grid grid-cols-5 gap-2">
                <Card>
                  <CardContent className="flex flex-col items-center p-3">
                    <CalendarDays className="size-4 text-muted-foreground mb-1" />
                    <span className="text-lg font-bold">{detailUser.calendar_count}</span>
                    <span className="text-[10px] text-muted-foreground">Calendar</span>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="flex flex-col items-center p-3">
                    <PartyPopper className="size-4 text-muted-foreground mb-1" />
                    <span className="text-lg font-bold">{detailUser.holiday_count}</span>
                    <span className="text-[10px] text-muted-foreground">Holidays</span>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="flex flex-col items-center p-3">
                    <Clock className="size-4 text-muted-foreground mb-1" />
                    <span className="text-lg font-bold">{detailUser.timetable_count}</span>
                    <span className="text-[10px] text-muted-foreground">Timetable</span>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="flex flex-col items-center p-3">
                    <BookOpen className="size-4 text-muted-foreground mb-1" />
                    <span className="text-lg font-bold">{detailUser.subject_count}</span>
                    <span className="text-[10px] text-muted-foreground">Subjects</span>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="flex flex-col items-center p-3">
                    <FileText className="size-4 text-muted-foreground mb-1" />
                    <span className="text-lg font-bold">{detailUser.plan_count}</span>
                    <span className="text-[10px] text-muted-foreground">Plans</span>
                  </CardContent>
                </Card>
              </div>

              {/* Calendar entries */}
              {detailUser.calendars.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Calendar Entries</h4>
                  <div className="rounded-md border text-sm">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Description</TableHead>
                          <TableHead>From</TableHead>
                          <TableHead>To</TableHead>
                          <TableHead>Type</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailUser.calendars.map((c) => (
                          <TableRow key={c.id}>
                            <TableCell>{c.description}</TableCell>
                            <TableCell>{c.from_date}</TableCell>
                            <TableCell>{c.to_date}</TableCell>
                            <TableCell><Badge variant="outline">{c.event_type}</Badge></TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {/* Holidays */}
              {detailUser.holidays.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Holidays</h4>
                  <div className="rounded-md border text-sm">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Occasion</TableHead>
                          <TableHead>Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailUser.holidays.map((h) => (
                          <TableRow key={h.id}>
                            <TableCell>{h.occasion}</TableCell>
                            <TableCell>{h.holiday_date}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {/* Timetable */}
              {detailUser.timetables.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Timetable Entries</h4>
                  <div className="rounded-md border text-sm">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Day</TableHead>
                          <TableHead>Period</TableHead>
                          <TableHead>Entry</TableHead>
                          <TableHead>Branch</TableHead>
                          <TableHead>Lab</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailUser.timetables.map((t) => (
                          <TableRow key={t.id}>
                            <TableCell>{t.day}</TableCell>
                            <TableCell>{t.period}</TableCell>
                            <TableCell>{t.entry}</TableCell>
                            <TableCell>{t.branch}</TableCell>
                            <TableCell>{t.is_lab ? "Yes" : "No"}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {/* Subjects */}
              {detailUser.subjects.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Subjects</h4>
                  <div className="rounded-md border text-sm">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Code</TableHead>
                          <TableHead>Title</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailUser.subjects.map((s) => (
                          <TableRow key={s.id}>
                            <TableCell>{s.course_code}</TableCell>
                            <TableCell>{s.course_title}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {/* Plans */}
              {detailUser.plans.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Generated Plans</h4>
                  <div className="rounded-md border text-sm">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Subject</TableHead>
                          <TableHead>Branch</TableHead>
                          <TableHead>Sem</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead>Lectures</TableHead>
                          <TableHead>Date</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailUser.plans.map((p) => (
                          <TableRow key={p.id}>
                            <TableCell>{p.subject_name}</TableCell>
                            <TableCell>{p.branch}</TableCell>
                            <TableCell>{p.semester}</TableCell>
                            <TableCell><Badge variant={p.is_lab ? "default" : "outline"}>{p.is_lab ? "Lab" : "Theory"}</Badge></TableCell>
                            <TableCell>{p.planned_lectures}</TableCell>
                            <TableCell>{new Date(p.generated_at).toLocaleDateString()}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              <Separator />

              <DialogFooter className="gap-2">
                <Button
                  variant="destructive"
                  onClick={() => deleteUserData(detailUser.id)}
                >
                  <Database className="size-4 mr-2" />
                  Delete All Data
                </Button>
                <Button variant="outline" onClick={() => setDetailUser(null)}>
                  Close
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialog.open}
        onOpenChange={(open) => setConfirmDialog((d) => ({ ...d, open }))}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{confirmDialog.title}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">{confirmDialog.message}</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDialog((d) => ({ ...d, open: false }))}>
              Cancel
            </Button>
            <Button onClick={confirmDialog.onConfirm}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
