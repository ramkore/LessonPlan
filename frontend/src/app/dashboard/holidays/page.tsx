"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { Holiday } from "@/lib/types";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { FileUploadZone } from "@/components/upload/file-upload-zone";
import {
  PlusIcon,
  Pencil as PencilIcon,
  Trash2Icon,
  SaveIcon,
  Loader2Icon,
} from "lucide-react";

export default function HolidaysPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "admin";

  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [parsedHolidays, setParsedHolidays] = useState<Holiday[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Manual add form
  const [occasion, setOccasion] = useState("");
  const [holidayDate, setHolidayDate] = useState("");
  const [adding, setAdding] = useState(false);

  // Edit dialog
  const [editHoliday, setEditHoliday] = useState<Holiday | null>(null);
  const [editOccasion, setEditOccasion] = useState("");
  const [editHolidayDate, setEditHolidayDate] = useState("");
  const [updating, setUpdating] = useState(false);

  // Redirect non-admin users away from this page
  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/dashboard");
    }
  }, [user, isAdmin, router]);

  const apiBase = "/api/admin/holidays";

  const fetchHolidays = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.get<Holiday[]>(apiBase);
      setHolidays(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load holidays");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) fetchHolidays();
  }, [fetchHolidays, isAdmin]);

  const handleUpload = async (file: File) => {
    try {
      setUploading(true);
      const data = await api.upload<Holiday[]>(`${apiBase}/upload`, file);
      setParsedHolidays(data);
      toast.success(`Parsed ${data.length} holidays from file`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleSaveParsed = async () => {
    try {
      setSaving(true);
      await api.post(`${apiBase}/bulk`, parsedHolidays);
      toast.success("All parsed holidays saved successfully");
      setParsedHolidays([]);
      await fetchHolidays();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save holidays");
    } finally {
      setSaving(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!occasion || !holidayDate) {
      toast.error("Please fill in all required fields");
      return;
    }
    try {
      setAdding(true);
      await api.post(apiBase, {
        occasion,
        holiday_date: holidayDate,
      });
      toast.success("Holiday added successfully");
      setOccasion("");
      setHolidayDate("");
      await fetchHolidays();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add holiday");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`${apiBase}/${id}`);
      toast.success("Holiday deleted");
      await fetchHolidays();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete holiday");
    }
  };

  const openEdit = (holiday: Holiday) => {
    setEditHoliday(holiday);
    setEditOccasion(holiday.occasion);
    setEditHolidayDate(holiday.holiday_date);
  };

  const handleUpdate = async () => {
    if (!editHoliday) return;
    try {
      setUpdating(true);
      await api.put(`${apiBase}/${editHoliday.id}`, {
        occasion: editOccasion,
        holiday_date: editHolidayDate,
      });
      toast.success("Holiday updated successfully");
      setEditHoliday(null);
      await fetchHolidays();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update holiday");
    } finally {
      setUpdating(false);
    }
  };

  if (!user || !isAdmin) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Holidays</h1>
        <p className="text-muted-foreground">
          Upload or manually manage institution-wide holiday entries.
        </p>
      </div>

      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Holidays</CardTitle>
          <CardDescription>
            Upload a file to parse holiday entries automatically.
          </CardDescription>
        </CardHeader>
        <FileUploadZone
          onUpload={handleUpload}
          accept=".pdf,.xlsx,.csv,.docx,.txt,.jpg,.jpeg,.png"
          isLoading={uploading}
        />
      </Card>

      {/* Parsed Holidays */}
      {parsedHolidays.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Parsed Holidays ({parsedHolidays.length})</CardTitle>
            <CardDescription>
              Review the parsed holidays below before saving them.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Occasion</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {parsedHolidays.map((holiday, idx) => (
                    <TableRow key={idx}>
                      <TableCell>{holiday.occasion}</TableCell>
                      <TableCell>{holiday.holiday_date}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={handleSaveParsed} disabled={saving}>
                {saving && <Loader2Icon className="animate-spin" />}
                <SaveIcon />
                Save All Parsed Holidays
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Manual Add Form */}
      <Card>
        <CardHeader>
          <CardTitle>Add Holiday Manually</CardTitle>
          <CardDescription>
            Create a new holiday entry by filling in the fields below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="occasion">Occasion</Label>
                <Input
                  id="occasion"
                  placeholder="e.g., Republic Day"
                  value={occasion}
                  onChange={(e) => setOccasion(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="holidayDate">Date</Label>
                <Input
                  id="holidayDate"
                  type="date"
                  value={holidayDate}
                  onChange={(e) => setHolidayDate(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={adding}>
                {adding && <Loader2Icon className="animate-spin" />}
                <PlusIcon />
                Add Holiday
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Data Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Holidays</CardTitle>
          <CardDescription>
            {holidays.length} {holidays.length === 1 ? "holiday" : "holidays"} found.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : holidays.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-8">
              No holidays yet. Upload a file or add one manually.
            </p>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Occasion</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {holidays.map((holiday) => (
                    <TableRow key={holiday.id}>
                      <TableCell>{holiday.occasion}</TableCell>
                      <TableCell>{holiday.holiday_date}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => openEdit(holiday)}
                          >
                            <PencilIcon />
                          </Button>
                          <Button
                            variant="destructive"
                            size="icon-sm"
                            onClick={() => handleDelete(holiday.id)}
                          >
                            <Trash2Icon />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit Dialog */}
      <Dialog
        open={!!editHoliday}
        onOpenChange={(open) => !open && setEditHoliday(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Holiday</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="editOccasion">Occasion</Label>
              <Input
                id="editOccasion"
                value={editOccasion}
                onChange={(e) => setEditOccasion(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="editHolidayDate">Date</Label>
              <Input
                id="editHolidayDate"
                type="date"
                value={editHolidayDate}
                onChange={(e) => setEditHolidayDate(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditHoliday(null)}
              disabled={updating}
            >
              Cancel
            </Button>
            <Button onClick={handleUpdate} disabled={updating}>
              {updating && <Loader2Icon className="animate-spin" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
