"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Subject } from "@/lib/types";
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
import { FileUploadZone } from "@/components/upload/file-upload-zone";
import {
  PlusIcon,
  Trash2Icon,
  SaveIcon,
  Loader2Icon,
  XIcon,
  BookOpenIcon,
} from "lucide-react";

interface UnitForm {
  unit: string;
  topics: string[];
  co: string;
}

interface ParsedSyllabus {
  course_title: string;
  course_code: string;
  regulation: string;
  units: Array<{ unit: string; topics: string[]; co: string }>;
  course_objectives: string[];
  course_outcomes: string[];
  text_books: string[];
  reference_books: string[];
}

export default function SyllabusPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [parsedData, setParsedData] = useState<ParsedSyllabus | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [savingParsed, setSavingParsed] = useState(false);

  // Manual form state
  const [courseTitle, setCourseTitle] = useState("");
  const [courseCode, setCourseCode] = useState("");
  const [regulation, setRegulation] = useState("");
  const [units, setUnits] = useState<UnitForm[]>([
    { unit: "Unit 1", topics: [""], co: "" },
  ]);
  const [adding, setAdding] = useState(false);

  const fetchSubjects = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.get<Subject[]>("/api/syllabus");
      setSubjects(data);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to load subjects"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSubjects();
  }, [fetchSubjects]);

  const handleUpload = async (file: File) => {
    try {
      setUploading(true);
      const data = await api.upload<ParsedSyllabus>("/api/syllabus/upload", file);
      setParsedData(data);
      toast.success("Syllabus parsed successfully");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleSaveParsed = async () => {
    if (!parsedData) return;
    try {
      setSavingParsed(true);
      await api.post("/api/syllabus", parsedData);
      toast.success("Parsed syllabus saved successfully");
      setParsedData(null);
      await fetchSubjects();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to save parsed syllabus"
      );
    } finally {
      setSavingParsed(false);
    }
  };

  // Unit management
  const addUnit = () => {
    setUnits([
      ...units,
      { unit: `Unit ${units.length + 1}`, topics: [""], co: "" },
    ]);
  };

  const removeUnit = (unitIdx: number) => {
    if (units.length <= 1) return;
    setUnits(units.filter((_, i) => i !== unitIdx));
  };

  const updateUnitName = (unitIdx: number, name: string) => {
    setUnits(units.map((u, i) => (i === unitIdx ? { ...u, unit: name } : u)));
  };

  const updateUnitCO = (unitIdx: number, co: string) => {
    setUnits(units.map((u, i) => (i === unitIdx ? { ...u, co } : u)));
  };

  // Topic management within units
  const addTopic = (unitIdx: number) => {
    setUnits(
      units.map((u, i) =>
        i === unitIdx ? { ...u, topics: [...u.topics, ""] } : u
      )
    );
  };

  const removeTopic = (unitIdx: number, topicIdx: number) => {
    setUnits(
      units.map((u, i) =>
        i === unitIdx
          ? { ...u, topics: u.topics.filter((_, ti) => ti !== topicIdx) }
          : u
      )
    );
  };

  const updateTopic = (unitIdx: number, topicIdx: number, value: string) => {
    setUnits(
      units.map((u, i) =>
        i === unitIdx
          ? {
              ...u,
              topics: u.topics.map((t, ti) => (ti === topicIdx ? value : t)),
            }
          : u
      )
    );
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!courseTitle || !courseCode) {
      toast.error("Please fill in course title and code");
      return;
    }

    const hasEmptyUnits = units.some(
      (u) => !u.unit || u.topics.every((t) => !t.trim())
    );
    if (hasEmptyUnits) {
      toast.error("Please fill in all unit names and at least one topic per unit");
      return;
    }

    try {
      setAdding(true);
      await api.post("/api/syllabus", {
        course_title: courseTitle,
        course_code: courseCode,
        regulation,
        units: units.map((u) => ({
          unit: u.unit,
          topics: u.topics.filter((t) => t.trim()),
          co: u.co,
        })),
      });
      toast.success("Subject added successfully");
      setCourseTitle("");
      setCourseCode("");
      setRegulation("");
      setUnits([{ unit: "Unit 1", topics: [""], co: "" }]);
      await fetchSubjects();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add subject");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/api/syllabus/${id}`);
      toast.success("Subject deleted");
      await fetchSubjects();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete subject"
      );
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Syllabus Management
        </h1>
        <p className="text-muted-foreground">
          Upload or manually manage course syllabi and subjects.
        </p>
      </div>

      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Syllabus</CardTitle>
          <CardDescription>
            Upload a syllabus file to parse course details automatically.
          </CardDescription>
        </CardHeader>
        <FileUploadZone
          onUpload={handleUpload}
          accept=".pdf,.xlsx,.csv,.docx,.txt,.jpg,.jpeg,.png"
          isLoading={uploading}
        />
      </Card>

      {/* Parsed Data */}
      {parsedData && (
        <Card>
          <CardHeader>
            <CardTitle>Parsed Syllabus</CardTitle>
            <CardDescription>
              Review the parsed syllabus data before saving.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">Course Title</p>
                <p className="font-medium">{parsedData.course_title}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Course Code</p>
                <p className="font-medium">{parsedData.course_code}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Regulation</p>
                <p className="font-medium">{parsedData.regulation || "N/A"}</p>
              </div>
            </div>

            <Separator />

            <div className="space-y-3">
              <p className="text-sm font-medium">
                Units ({parsedData.units.length})
              </p>
              {parsedData.units.map((unit, idx) => (
                <div key={idx} className="rounded-lg border p-3 space-y-1">
                  <p className="text-sm font-medium">{unit.unit}</p>
                  {unit.co && (
                    <p className="text-xs text-muted-foreground">CO: {unit.co}</p>
                  )}
                  <ul className="list-disc list-inside text-sm text-muted-foreground">
                    {unit.topics.map((topic, tIdx) => (
                      <li key={tIdx}>{topic}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setParsedData(null)}
              >
                Discard
              </Button>
              <Button onClick={handleSaveParsed} disabled={savingParsed}>
                {savingParsed && <Loader2Icon className="animate-spin" />}
                <SaveIcon />
                Save Parsed Syllabus
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Separator />

      {/* Manual Add Form */}
      <Card>
        <CardHeader>
          <CardTitle>Add Subject Manually</CardTitle>
          <CardDescription>
            Create a new subject with unit-wise topics.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAdd} className="space-y-6">
            {/* Basic Info */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="courseTitle">Course Title</Label>
                <Input
                  id="courseTitle"
                  placeholder="e.g., Data Structures"
                  value={courseTitle}
                  onChange={(e) => setCourseTitle(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="courseCode">Course Code</Label>
                <Input
                  id="courseCode"
                  placeholder="e.g., CS201"
                  value={courseCode}
                  onChange={(e) => setCourseCode(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="regulation">Regulation</Label>
                <Input
                  id="regulation"
                  placeholder="e.g., R20"
                  value={regulation}
                  onChange={(e) => setRegulation(e.target.value)}
                />
              </div>
            </div>

            <Separator />

            {/* Dynamic Units */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-base">Units</Label>
                <Button type="button" variant="outline" size="sm" onClick={addUnit}>
                  <PlusIcon />
                  Add Unit
                </Button>
              </div>

              {units.map((unit, unitIdx) => (
                <div
                  key={unitIdx}
                  className="rounded-lg border p-4 space-y-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex-1 grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div className="space-y-1">
                        <Label className="text-xs">Unit Name</Label>
                        <Input
                          placeholder="e.g., Unit 1"
                          value={unit.unit}
                          onChange={(e) =>
                            updateUnitName(unitIdx, e.target.value)
                          }
                        />
                      </div>
                      <div className="space-y-1">
                        <Label className="text-xs">CO (Course Outcome)</Label>
                        <Input
                          placeholder="e.g., CO1"
                          value={unit.co}
                          onChange={(e) =>
                            updateUnitCO(unitIdx, e.target.value)
                          }
                        />
                      </div>
                    </div>
                    {units.length > 1 && (
                      <Button
                        type="button"
                        variant="destructive"
                        size="icon-sm"
                        onClick={() => removeUnit(unitIdx)}
                      >
                        <XIcon />
                      </Button>
                    )}
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label className="text-xs">Topics</Label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        onClick={() => addTopic(unitIdx)}
                      >
                        <PlusIcon />
                        Add Topic
                      </Button>
                    </div>
                    {unit.topics.map((topic, topicIdx) => (
                      <div key={topicIdx} className="flex items-center gap-2">
                        <Input
                          placeholder={`Topic ${topicIdx + 1}`}
                          value={topic}
                          onChange={(e) =>
                            updateTopic(unitIdx, topicIdx, e.target.value)
                          }
                        />
                        {unit.topics.length > 1 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon-sm"
                            onClick={() => removeTopic(unitIdx, topicIdx)}
                          >
                            <XIcon />
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={adding}>
                {adding && <Loader2Icon className="animate-spin" />}
                <PlusIcon />
                Add Subject
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Saved Subjects */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Saved Subjects</h2>

        {loading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Skeleton className="h-48 w-full" />
            <Skeleton className="h-48 w-full" />
          </div>
        ) : subjects.length === 0 ? (
          <Card>
            <CardContent className="py-8">
              <p className="text-center text-sm text-muted-foreground">
                No subjects yet. Upload a syllabus file or add one manually.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {subjects.map((subject) => (
              <Card key={subject.id}>
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <BookOpenIcon className="size-4" />
                      </div>
                      <div>
                        <CardTitle>{subject.course_title}</CardTitle>
                        <CardDescription className="mt-1 flex items-center gap-2">
                          <Badge variant="outline">{subject.course_code}</Badge>
                          {subject.regulation && (
                            <Badge variant="secondary">
                              {subject.regulation}
                            </Badge>
                          )}
                        </CardDescription>
                      </div>
                    </div>
                    <Button
                      variant="destructive"
                      size="icon-sm"
                      onClick={() => handleDelete(subject.id)}
                    >
                      <Trash2Icon />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground">
                      {subject.units.length}{" "}
                      {subject.units.length === 1 ? "unit" : "units"}
                    </p>
                    {subject.units.map((unit, idx) => (
                      <div key={idx} className="text-sm">
                        <span className="font-medium">{unit.unit}</span>
                        <span className="text-muted-foreground">
                          {" "}
                          &mdash; {unit.topics.length}{" "}
                          {unit.topics.length === 1 ? "topic" : "topics"}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
