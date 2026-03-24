"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import type { CalendarEntry } from "@/lib/types";
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
import { Badge } from "@/components/ui/badge";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FileUploadZone } from "@/components/upload/file-upload-zone";
import {
  PlusIcon,
  Pencil as PencilIcon,
  Trash2Icon,
  SaveIcon,
  Loader2Icon,
} from "lucide-react";

const EVENT_TYPES = ["teaching", "exam", "vacation", "other"] as const;

export default function CalendarPage() {
  const { user } = useAuth();
  const router = useRouter();
  const isAdmin = user?.role === "admin";

  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [parsedEntries, setParsedEntries] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Manual add form state
  const [description, setDescription] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [eventType, setEventType] = useState<string>("teaching");
  const [adding, setAdding] = useState(false);

  // Edit dialog state
  const [editEntry, setEditEntry] = useState<CalendarEntry | null>(null);
  const [editDescription, setEditDescription] = useState("");
  const [editFromDate, setEditFromDate] = useState("");
  const [editToDate, setEditToDate] = useState("");
  const [editEventType, setEditEventType] = useState<string>("teaching");
  const [updating, setUpdating] = useState(false);

  // Redirect non-admin users away from this page
  useEffect(() => {
    if (user && !isAdmin) {
      router.push("/dashboard");
    }
  }, [user, isAdmin, router]);

  const apiBase = "/api/admin/calendar";

  const fetchEntries = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.get<CalendarEntry[]>(apiBase);
      setEntries(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load calendar entries");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) fetchEntries();
  }, [fetchEntries, isAdmin]);

  const handleUpload = async (file: File) => {
    try {
      setUploading(true);
      const data = await api.upload<CalendarEntry[]>(`${apiBase}/upload`, file);
      setParsedEntries(data);
      toast.success(`Parsed ${data.length} entries from file`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleSaveParsed = async () => {
    try {
      setSaving(true);
      await api.post(`${apiBase}/bulk`, parsedEntries);
      toast.success("All parsed entries saved successfully");
      setParsedEntries([]);
      await fetchEntries();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save entries");
    } finally {
      setSaving(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description || !fromDate || !toDate) {
      toast.error("Please fill in all required fields");
      return;
    }
    try {
      setAdding(true);
      await api.post(apiBase, {
        description,
        from_date: fromDate,
        to_date: toDate,
        event_type: eventType,
      });
      toast.success("Entry added successfully");
      setDescription("");
      setFromDate("");
      setToDate("");
      setEventType("teaching");
      await fetchEntries();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add entry");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`${apiBase}/${id}`);
      toast.success("Entry deleted");
      await fetchEntries();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete entry");
    }
  };

  const openEdit = (entry: CalendarEntry) => {
    setEditEntry(entry);
    setEditDescription(entry.description);
    setEditFromDate(entry.from_date);
    setEditToDate(entry.to_date);
    setEditEventType(entry.event_type);
  };

  const handleUpdate = async () => {
    if (!editEntry) return;
    try {
      setUpdating(true);
      await api.put(`${apiBase}/${editEntry.id}`, {
        description: editDescription,
        from_date: editFromDate,
        to_date: editToDate,
        event_type: editEventType,
      });
      toast.success("Entry updated successfully");
      setEditEntry(null);
      await fetchEntries();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update entry");
    } finally {
      setUpdating(false);
    }
  };

  const eventTypeBadgeVariant = (type: string) => {
    switch (type) {
      case "teaching":
        return "default" as const;
      case "exam":
        return "secondary" as const;
      case "vacation":
        return "outline" as const;
      default:
        return "secondary" as const;
    }
  };

  if (!user || !isAdmin) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Academic Calendar</h1>
        <p className="text-muted-foreground">
          Upload or manually manage institution-wide academic calendar entries.
        </p>
      </div>

      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Calendar</CardTitle>
          <CardDescription>
            Upload a file to parse academic calendar entries automatically.
          </CardDescription>
        </CardHeader>
        <FileUploadZone
          onUpload={handleUpload}
          accept=".pdf,.xlsx,.csv,.docx,.txt,.jpg,.jpeg,.png"
          isLoading={uploading}
        />
      </Card>

      {/* Parsed Entries */}
      {parsedEntries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Parsed Entries ({parsedEntries.length})</CardTitle>
            <CardDescription>
              Review the parsed entries below before saving them.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border">
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
                  {parsedEntries.map((entry, idx) => (
                    <TableRow key={idx}>
                      <TableCell className="max-w-xs truncate">
                        {entry.description}
                      </TableCell>
                      <TableCell>{entry.from_date}</TableCell>
                      <TableCell>{entry.to_date}</TableCell>
                      <TableCell>
                        <Badge variant={eventTypeBadgeVariant(entry.event_type)}>
                          {entry.event_type}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="mt-4 flex justify-end">
              <Button onClick={handleSaveParsed} disabled={saving}>
                {saving && <Loader2Icon className="animate-spin" />}
                <SaveIcon />
                Save All Parsed Entries
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Manual Add Form */}
      <Card>
        <CardHeader>
          <CardTitle>Add Entry Manually</CardTitle>
          <CardDescription>
            Create a new calendar entry by filling in the fields below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="description">Description</Label>
                <Input
                  id="description"
                  placeholder="e.g., Mid-Semester Examinations"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="fromDate">From Date</Label>
                <Input
                  id="fromDate"
                  type="date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="toDate">To Date</Label>
                <Input
                  id="toDate"
                  type="date"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label>Event Type</Label>
                <Select value={eventType} onValueChange={(val) => val && setEventType(val)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select type" />
                  </SelectTrigger>
                  <SelectContent>
                    {EVENT_TYPES.map((t) => (
                      <SelectItem key={t} value={t}>
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={adding}>
                {adding && <Loader2Icon className="animate-spin" />}
                <PlusIcon />
                Add Entry
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Data Table */}
      <Card>
        <CardHeader>
          <CardTitle>All Calendar Entries</CardTitle>
          <CardDescription>
            {entries.length} {entries.length === 1 ? "entry" : "entries"} found.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : entries.length === 0 ? (
            <p className="text-center text-sm text-muted-foreground py-8">
              No calendar entries yet. Upload a file or add one manually.
            </p>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Description</TableHead>
                    <TableHead>From</TableHead>
                    <TableHead>To</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.map((entry) => (
                    <TableRow key={entry.id}>
                      <TableCell className="max-w-xs truncate">
                        {entry.description}
                      </TableCell>
                      <TableCell>{entry.from_date}</TableCell>
                      <TableCell>{entry.to_date}</TableCell>
                      <TableCell>
                        <Badge variant={eventTypeBadgeVariant(entry.event_type)}>
                          {entry.event_type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => openEdit(entry)}
                          >
                            <PencilIcon />
                          </Button>
                          <Button
                            variant="destructive"
                            size="icon-sm"
                            onClick={() => handleDelete(entry.id)}
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
      <Dialog open={!!editEntry} onOpenChange={(open) => !open && setEditEntry(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Calendar Entry</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="editDescription">Description</Label>
              <Input
                id="editDescription"
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="editFromDate">From Date</Label>
                <Input
                  id="editFromDate"
                  type="date"
                  value={editFromDate}
                  onChange={(e) => setEditFromDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="editToDate">To Date</Label>
                <Input
                  id="editToDate"
                  type="date"
                  value={editToDate}
                  onChange={(e) => setEditToDate(e.target.value)}
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label>Event Type</Label>
              <Select value={editEventType} onValueChange={(val) => val && setEditEventType(val)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {EVENT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {t.charAt(0).toUpperCase() + t.slice(1)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setEditEntry(null)}
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
