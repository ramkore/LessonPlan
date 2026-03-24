"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { AdminUser } from "@/lib/types";
import { Card, CardContent } from "@/components/ui/card";
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
  Trash2,
  ArrowUpDown,
  Search,
  Eye,
  CalendarDays,
  PartyPopper,
  Clock,
  BookOpen,
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

export default function AdminUsersPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [userSearch, setUserSearch] = useState("");
  const [detailUser, setDetailUser] = useState<UserDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ open: false, title: "", message: "", onConfirm: () => {} });

  useEffect(() => {
    if (user && user.role !== "admin") {
      router.push("/dashboard");
    }
  }, [user, router]);

  useEffect(() => {
    if (user?.role === "admin") {
      loadUsers();
    }
  }, [user]);

  async function loadUsers() {
    setLoading(true);
    try {
      const u = await api.get<AdminUser[]>("/api/admin/users");
      setUsers(u);
    } catch {
      toast.error("Failed to load users");
    } finally {
      setLoading(false);
    }
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
      message: "Delete all timetable, syllabus, and lesson plan data for this user? The account will be kept. This cannot be undone.",
      onConfirm: async () => {
        try {
          await api.delete(`/api/admin/users/${userId}/data`);
          toast.success("All user data deleted");
          setDetailUser(null);
          loadUsers();
        } catch {
          toast.error("Failed to delete user data");
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
          loadUsers();
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
          loadUsers();
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Users</h1>
        <p className="text-muted-foreground">Manage registered users and their roles</p>
      </div>

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
                        <Button variant="ghost" size="sm" onClick={() => viewUserDetail(u)} title="View user data">
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

              <div className="grid grid-cols-5 gap-2">
                <Card><CardContent className="flex flex-col items-center p-3"><CalendarDays className="size-4 text-muted-foreground mb-1" /><span className="text-lg font-bold">{detailUser.calendar_count}</span><span className="text-[10px] text-muted-foreground">Calendar</span></CardContent></Card>
                <Card><CardContent className="flex flex-col items-center p-3"><PartyPopper className="size-4 text-muted-foreground mb-1" /><span className="text-lg font-bold">{detailUser.holiday_count}</span><span className="text-[10px] text-muted-foreground">Holidays</span></CardContent></Card>
                <Card><CardContent className="flex flex-col items-center p-3"><Clock className="size-4 text-muted-foreground mb-1" /><span className="text-lg font-bold">{detailUser.timetable_count}</span><span className="text-[10px] text-muted-foreground">Timetable</span></CardContent></Card>
                <Card><CardContent className="flex flex-col items-center p-3"><BookOpen className="size-4 text-muted-foreground mb-1" /><span className="text-lg font-bold">{detailUser.subject_count}</span><span className="text-[10px] text-muted-foreground">Subjects</span></CardContent></Card>
                <Card><CardContent className="flex flex-col items-center p-3"><FileText className="size-4 text-muted-foreground mb-1" /><span className="text-lg font-bold">{detailUser.plan_count}</span><span className="text-[10px] text-muted-foreground">Plans</span></CardContent></Card>
              </div>

              {detailUser.timetables.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Timetable Entries</h4>
                  <div className="rounded-md border text-sm">
                    <Table>
                      <TableHeader><TableRow><TableHead>Day</TableHead><TableHead>Period</TableHead><TableHead>Entry</TableHead><TableHead>Branch</TableHead><TableHead>Lab</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {detailUser.timetables.map((t) => (
                          <TableRow key={t.id}><TableCell>{t.day}</TableCell><TableCell>{t.period}</TableCell><TableCell>{t.entry}</TableCell><TableCell>{t.branch}</TableCell><TableCell>{t.is_lab ? "Yes" : "No"}</TableCell></TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {detailUser.subjects.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Subjects</h4>
                  <div className="rounded-md border text-sm">
                    <Table>
                      <TableHeader><TableRow><TableHead>Code</TableHead><TableHead>Title</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {detailUser.subjects.map((s) => (
                          <TableRow key={s.id}><TableCell>{s.course_code}</TableCell><TableCell>{s.course_title}</TableCell></TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              {detailUser.plans.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold mb-2">Generated Plans</h4>
                  <div className="rounded-md border text-sm">
                    <Table>
                      <TableHeader><TableRow><TableHead>Subject</TableHead><TableHead>Branch</TableHead><TableHead>Sem</TableHead><TableHead>Type</TableHead><TableHead>Lectures</TableHead><TableHead>Date</TableHead></TableRow></TableHeader>
                      <TableBody>
                        {detailUser.plans.map((p) => (
                          <TableRow key={p.id}><TableCell>{p.subject_name}</TableCell><TableCell>{p.branch}</TableCell><TableCell>{p.semester}</TableCell><TableCell><Badge variant={p.is_lab ? "default" : "outline"}>{p.is_lab ? "Lab" : "Theory"}</Badge></TableCell><TableCell>{p.planned_lectures}</TableCell><TableCell>{new Date(p.generated_at).toLocaleDateString()}</TableCell></TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              )}

              <Separator />

              <DialogFooter className="gap-2">
                <Button variant="destructive" onClick={() => deleteUserData(detailUser.id)}>
                  <Database className="size-4 mr-2" />
                  Delete All Data
                </Button>
                <Button variant="outline" onClick={() => setDetailUser(null)}>Close</Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      {/* Confirmation Dialog */}
      <Dialog open={confirmDialog.open} onOpenChange={(open) => setConfirmDialog((d) => ({ ...d, open }))}>
        <DialogContent>
          <DialogHeader><DialogTitle>{confirmDialog.title}</DialogTitle></DialogHeader>
          <p className="text-sm text-muted-foreground">{confirmDialog.message}</p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDialog((d) => ({ ...d, open: false }))}>Cancel</Button>
            <Button onClick={confirmDialog.onConfirm}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
