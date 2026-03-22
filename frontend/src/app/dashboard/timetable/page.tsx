"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Subject, TimetableEntry } from "@/lib/types";
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
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
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

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

export default function TimetablePage() {
  const [entries, setEntries] = useState<TimetableEntry[]>([]);
  const [parsedEntries, setParsedEntries] = useState<TimetableEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);

  // Upload extra fields
  const [uploadSubjectName, setUploadSubjectName] = useState("");
  const [uploadFacultyName, setUploadFacultyName] = useState("");
  const [uploadBranch, setUploadBranch] = useState("");
  const [subjects, setSubjects] = useState<Subject[]>([]);

  // Manual add form
  const [day, setDay] = useState<string>("Mon");
  const [period, setPeriod] = useState("");
  const [entry, setEntry] = useState("");
  const [branch, setBranch] = useState("");
  const [timeSlot, setTimeSlot] = useState("");
  const [isLab, setIsLab] = useState(false);
  const [adding, setAdding] = useState(false);

  // Edit dialog
  const [editEntry, setEditEntry] = useState<TimetableEntry | null>(null);
  const [editDay, setEditDay] = useState<string>("Mon");
  const [editPeriod, setEditPeriod] = useState("");
  const [editEntryText, setEditEntryText] = useState("");
  const [editBranch, setEditBranch] = useState("");
  const [editTimeSlot, setEditTimeSlot] = useState("");
  const [editIsLab, setEditIsLab] = useState(false);
  const [updating, setUpdating] = useState(false);

  const fetchEntries = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.get<TimetableEntry[]>("/api/timetable");
      setEntries(data);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to load timetable"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries();
    api.get<Subject[]>("/api/syllabus").then(setSubjects).catch(() => {});
  }, [fetchEntries]);

  const handleUpload = async (file: File) => {
    if (!uploadSubjectName.trim()) {
      toast.error("Subject name is required before uploading");
      return;
    }
    try {
      setUploading(true);
      const extraFields: Record<string, string> = {
        subject_name: uploadSubjectName,
      };
      if (uploadFacultyName.trim())
        extraFields.faculty_name = uploadFacultyName;
      if (uploadBranch.trim()) extraFields.branch = uploadBranch;

      const data = await api.upload<TimetableEntry[]>(
        "/api/timetable/upload",
        file,
        extraFields
      );
      setParsedEntries(data);
      toast.success(`Parsed ${data.length} timetable entries from file`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleSaveParsed = async () => {
    try {
      setSaving(true);
      await api.post("/api/timetable/bulk", parsedEntries);
      toast.success("All parsed entries saved successfully");
      setParsedEntries([]);
      setUploadSubjectName("");
      setUploadFacultyName("");
      setUploadBranch("");
      await fetchEntries();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to save entries"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!day || !period || !entry) {
      toast.error("Please fill in day, period, and entry");
      return;
    }
    try {
      setAdding(true);
      await api.post("/api/timetable", {
        day,
        period,
        entry,
        branch,
        time_slot: timeSlot,
        is_lab: isLab,
      });
      toast.success("Timetable entry added successfully");
      setPeriod("");
      setEntry("");
      setBranch("");
      setTimeSlot("");
      setIsLab(false);
      await fetchEntries();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add entry");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/api/timetable/${id}`);
      toast.success("Entry deleted");
      await fetchEntries();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete entry"
      );
    }
  };

  const openEdit = (item: TimetableEntry) => {
    setEditEntry(item);
    setEditDay(item.day);
    setEditPeriod(item.period);
    setEditEntryText(item.entry);
    setEditBranch(item.branch);
    setEditTimeSlot(item.time_slot);
    setEditIsLab(item.is_lab);
  };

  const handleUpdate = async () => {
    if (!editEntry) return;
    try {
      setUpdating(true);
      await api.put(`/api/timetable/${editEntry.id}`, {
        day: editDay,
        period: editPeriod,
        entry: editEntryText,
        branch: editBranch,
        time_slot: editTimeSlot,
        is_lab: editIsLab,
      });
      toast.success("Entry updated successfully");
      setEditEntry(null);
      await fetchEntries();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to update entry"
      );
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Timetable</h1>
        <p className="text-muted-foreground">
          Upload or manually manage timetable entries.
        </p>
      </div>

      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Timetable</CardTitle>
          <CardDescription>
            Provide subject details and upload a timetable file to parse entries.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>
                Subject Name <span className="text-destructive">*</span>
              </Label>
              {subjects.length > 0 ? (
                <Select
                  value={uploadSubjectName}
                  onValueChange={(v) => setUploadSubjectName(v ?? "")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select subject..." />
                  </SelectTrigger>
                  <SelectContent>
                    {subjects.map((s) => (
                      <SelectItem key={s.id} value={s.course_title}>
                        {s.course_title}
                        {s.course_code ? ` (${s.course_code})` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input
                  placeholder="e.g., Data Structures"
                  value={uploadSubjectName}
                  onChange={(e) => setUploadSubjectName(e.target.value)}
                  required
                />
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="uploadFaculty">Faculty Name</Label>
              <Input
                id="uploadFaculty"
                placeholder="Optional"
                value={uploadFacultyName}
                onChange={(e) => setUploadFacultyName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="uploadBranch">Branch</Label>
              <Input
                id="uploadBranch"
                placeholder="Optional"
                value={uploadBranch}
                onChange={(e) => setUploadBranch(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
        <FileUploadZone
          onUpload={handleUpload}
          accept=".pdf,.xlsx,.xls,.csv,.docx"
          isLoading={uploading}
        />
      </Card>

      {/* Parsed Entries */}
      {parsedEntries.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Parsed Timetable ({parsedEntries.length})</CardTitle>
            <CardDescription>
              Review the parsed timetable entries before saving.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Day</TableHead>
                    <TableHead>Period</TableHead>
                    <TableHead>Entry</TableHead>
                    <TableHead>Branch</TableHead>
                    <TableHead>Time Slot</TableHead>
                    <TableHead>Lab</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {parsedEntries.map((item, idx) => (
                    <TableRow key={idx}>
                      <TableCell>{item.day}</TableCell>
                      <TableCell>{item.period}</TableCell>
                      <TableCell>{item.entry}</TableCell>
                      <TableCell>{item.branch}</TableCell>
                      <TableCell>{item.time_slot}</TableCell>
                      <TableCell>
                        <Checkbox
                          checked={item.is_lab}
                          onCheckedChange={(checked) => {
                            setParsedEntries((prev) =>
                              prev.map((e, i) =>
                                i === idx ? { ...e, is_lab: checked === true } : e
                              )
                            );
                          }}
                        />
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
            Create a new timetable entry by filling in the fields below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-2">
                <Label>Day</Label>
                <Select value={day} onValueChange={(val) => val && setDay(val)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select day" />
                  </SelectTrigger>
                  <SelectContent>
                    {DAYS.map((d) => (
                      <SelectItem key={d} value={d}>
                        {d}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="period">Period</Label>
                <Input
                  id="period"
                  placeholder="e.g., P1"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="entryText">Entry</Label>
                <Input
                  id="entryText"
                  placeholder="e.g., DS Lab"
                  value={entry}
                  onChange={(e) => setEntry(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="branchField">Branch</Label>
                <Input
                  id="branchField"
                  placeholder="e.g., CSE"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="timeSlotField">Time Slot</Label>
                <Input
                  id="timeSlotField"
                  placeholder="e.g., 9:30 - 10:20"
                  value={timeSlot}
                  onChange={(e) => setTimeSlot(e.target.value)}
                />
              </div>
              <div className="flex items-center gap-2 pt-6">
                <Checkbox
                  id="isLabField"
                  checked={isLab}
                  onCheckedChange={(checked) => setIsLab(checked === true)}
                />
                <Label htmlFor="isLabField">Lab Session</Label>
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
          <CardTitle>All Timetable Entries</CardTitle>
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
              No timetable entries yet. Upload a file or add one manually.
            </p>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Day</TableHead>
                    <TableHead>Period</TableHead>
                    <TableHead>Entry</TableHead>
                    <TableHead>Branch</TableHead>
                    <TableHead>Time Slot</TableHead>
                    <TableHead>Lab</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {entries.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.day}</TableCell>
                      <TableCell>{item.period}</TableCell>
                      <TableCell>{item.entry}</TableCell>
                      <TableCell>{item.branch}</TableCell>
                      <TableCell>{item.time_slot}</TableCell>
                      <TableCell>
                        {item.is_lab && <Badge variant="secondary">Lab</Badge>}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => openEdit(item)}
                          >
                            <PencilIcon />
                          </Button>
                          <Button
                            variant="destructive"
                            size="icon-sm"
                            onClick={() => handleDelete(item.id)}
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
        open={!!editEntry}
        onOpenChange={(open) => !open && setEditEntry(null)}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit Timetable Entry</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Day</Label>
              <Select value={editDay} onValueChange={(val) => val && setEditDay(val)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DAYS.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="editPeriod">Period</Label>
              <Input
                id="editPeriod"
                value={editPeriod}
                onChange={(e) => setEditPeriod(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="editEntryText">Entry</Label>
              <Input
                id="editEntryText"
                value={editEntryText}
                onChange={(e) => setEditEntryText(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="editBranchField">Branch</Label>
              <Input
                id="editBranchField"
                value={editBranch}
                onChange={(e) => setEditBranch(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="editTimeSlotField">Time Slot</Label>
              <Input
                id="editTimeSlotField"
                value={editTimeSlot}
                onChange={(e) => setEditTimeSlot(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="editIsLabField"
                checked={editIsLab}
                onCheckedChange={(checked) => setEditIsLab(checked === true)}
              />
              <Label htmlFor="editIsLabField">Lab Session</Label>
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
