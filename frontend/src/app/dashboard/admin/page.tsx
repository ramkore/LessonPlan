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
} from "lucide-react";

export default function AdminPage() {
  const { user } = useAuth();
  const router = useRouter();

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [plans, setPlans] = useState<AdminPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [userSearch, setUserSearch] = useState("");
  const [planSearch, setPlanSearch] = useState("");

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
      loadData();
    }
  }, [user]);

  async function loadData() {
    setLoading(true);
    try {
      const [s, u, p] = await Promise.all([
        api.get<AdminStats>("/api/admin/stats"),
        api.get<AdminUser[]>("/api/admin/users"),
        api.get<AdminPlan[]>("/api/admin/plans"),
      ]);
      setStats(s);
      setUsers(u);
      setPlans(p);
    } catch {
      toast.error("Failed to load admin data");
    } finally {
      setLoading(false);
    }
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
          Monitor users and generated lesson plans
        </p>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
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
                  <CardTitle className="text-sm font-medium">
                    Total Users
                  </CardTitle>
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
                  <div className="text-2xl font-bold">
                    {stats.total_faculty}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium">
                    Total Plans
                  </CardTitle>
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
                      <TableCell
                        colSpan={6}
                        className="text-center text-muted-foreground"
                      >
                        No users found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredUsers.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell className="font-medium">
                          {u.full_name || "—"}
                        </TableCell>
                        <TableCell>{u.email}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              u.role === "admin" ? "default" : "outline"
                            }
                          >
                            {u.role}
                          </Badge>
                        </TableCell>
                        <TableCell>{u.plan_count}</TableCell>
                        <TableCell>
                          {new Date(u.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => toggleRole(u)}
                              disabled={u.id === user.id}
                              title={
                                u.id === user.id
                                  ? "Cannot change your own role"
                                  : u.role === "admin"
                                    ? "Demote to faculty"
                                    : "Promote to admin"
                              }
                            >
                              <ArrowUpDown className="size-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => deleteUser(u)}
                              disabled={u.id === user.id}
                              className="text-destructive hover:text-destructive"
                              title={
                                u.id === user.id
                                  ? "Cannot delete yourself"
                                  : "Delete user"
                              }
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
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPlans.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={8}
                        className="text-center text-muted-foreground"
                      >
                        No plans found
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredPlans.map((p) => (
                      <TableRow key={p.id}>
                        <TableCell className="text-xs">
                          {p.user_email}
                        </TableCell>
                        <TableCell>{p.faculty_name}</TableCell>
                        <TableCell className="font-medium">
                          {p.subject_name}
                        </TableCell>
                        <TableCell>{p.branch}</TableCell>
                        <TableCell>{p.semester}</TableCell>
                        <TableCell>
                          <Badge variant={p.is_lab ? "default" : "outline"}>
                            {p.is_lab ? "Lab" : "Theory"}
                          </Badge>
                        </TableCell>
                        <TableCell>{p.planned_lectures}</TableCell>
                        <TableCell>
                          {new Date(p.generated_at).toLocaleDateString()}
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

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialog.open}
        onOpenChange={(open) =>
          setConfirmDialog((d) => ({ ...d, open }))
        }
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{confirmDialog.title}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {confirmDialog.message}
          </p>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() =>
                setConfirmDialog((d) => ({ ...d, open: false }))
              }
            >
              Cancel
            </Button>
            <Button onClick={confirmDialog.onConfirm}>Confirm</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
