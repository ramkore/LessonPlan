"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { AdminPlan } from "@/lib/types";
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
import { Trash2, Search } from "lucide-react";

export default function AdminPlansPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [plans, setPlans] = useState<AdminPlan[]>([]);
  const [loading, setLoading] = useState(true);
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
      loadPlans();
    }
  }, [user]);

  async function loadPlans() {
    setLoading(true);
    try {
      const p = await api.get<AdminPlan[]>("/api/admin/plans");
      setPlans(p);
    } catch {
      toast.error("Failed to load plans");
    } finally {
      setLoading(false);
    }
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
          loadPlans();
        } catch {
          toast.error("Failed to delete plan");
        }
        setConfirmDialog((d) => ({ ...d, open: false }));
      },
    });
  }

  if (!user || user.role !== "admin") return null;

  const filteredPlans = plans.filter(
    (p) =>
      p.subject_name.toLowerCase().includes(planSearch.toLowerCase()) ||
      p.faculty_name.toLowerCase().includes(planSearch.toLowerCase()) ||
      p.user_email.toLowerCase().includes(planSearch.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Generated Plans</h1>
        <p className="text-muted-foreground">View and manage all generated lesson plans</p>
      </div>

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
