"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  CalendarDays,
  Clock,
  Download,
  FileSpreadsheet,
  FileText,
  Loader2,
  PartyPopper,
  Sparkles,
  TriangleAlert,
} from "lucide-react";

import { api } from "@/lib/api";
import type {
  CalendarEntry,
  FacultyInfo,
  Holiday,
  LessonPlanHistoryItem,
  LessonPlanPreview,
  Subject,
  TimetableEntry,
} from "@/lib/types";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function cleanBranch(entry: string): string {
  return entry.replace(/\s*(lab|laboratory|practical)\s*$/i, "").trim();
}

function formatColumnHeader(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function DynamicTable({ data }: { data: Record<string, string>[] }) {
  if (!data || data.length === 0) {
    return (
      <p className="py-8 text-center text-muted-foreground">
        No records to display.
      </p>
    );
  }

  const columns = Object.keys(data[0]);

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col) => (
              <TableHead key={col}>{formatColumnHeader(col)}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((row, idx) => (
            <TableRow key={idx}>
              {columns.map((col) => (
                <TableCell key={col}>{row[col]}</TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function GeneratePage() {
  // Faculty info form state
  const [facultyName, setFacultyName] = useState("");
  const [designation, setDesignation] = useState("");
  const [subjectName, setSubjectName] = useState("");
  const [courseCode, setCourseCode] = useState("");
  const [selectedEntry, setSelectedEntry] = useState("");
  const [semester, setSemester] = useState("");
  const [section, setSection] = useState("");
  const [studentCount, setStudentCount] = useState("");

  // Data summary
  const [calendarEntries, setCalendarEntries] = useState<CalendarEntry[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [timetableEntries, setTimetableEntries] = useState<TimetableEntry[]>(
    [],
  );
  const [summaryLoading, setSummaryLoading] = useState(true);

  // Syllabus
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [selectedSyllabusId, setSelectedSyllabusId] = useState<string>("");
  const [syllabusLoading, setSyllabusLoading] = useState(true);

  // Generation
  const [generating, setGenerating] = useState(false);
  const [preview, setPreview] = useState<LessonPlanPreview | null>(null);

  // Export
  const [exporting, setExporting] = useState<
    "pdf" | "excel" | "word" | null
  >(null);

  // History
  const [history, setHistory] = useState<LessonPlanHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  // -----------------------------------------------------------------------
  // Fetch data on mount
  // -----------------------------------------------------------------------

  const fetchSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const [cal, hol, tt] = await Promise.all([
        api.get<CalendarEntry[]>("/api/calendar"),
        api.get<Holiday[]>("/api/holidays"),
        api.get<TimetableEntry[]>("/api/timetable"),
      ]);
      setCalendarEntries(cal);
      setHolidays(hol);
      setTimetableEntries(tt);
    } catch {
      toast.error("Failed to load data summary.");
    } finally {
      setSummaryLoading(false);
    }
  }, []);

  const fetchSyllabus = useCallback(async () => {
    setSyllabusLoading(true);
    try {
      const data = await api.get<Subject[]>("/api/syllabus");
      setSubjects(data);
    } catch {
      toast.error("Failed to load syllabus list.");
    } finally {
      setSyllabusLoading(false);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const data = await api.get<LessonPlanHistoryItem[]>(
        "/api/generate/history",
      );
      setHistory(data);
    } catch {
      // History is non-critical; silently ignore
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSummary();
    fetchSyllabus();
    fetchHistory();
  }, [fetchSummary, fetchSyllabus, fetchHistory]);

  // -----------------------------------------------------------------------
  // Dropdown options
  // -----------------------------------------------------------------------

  const uniqueEntries = useMemo(
    () =>
      [...new Set(timetableEntries.map((e) => e.entry).filter(Boolean))].sort(),
    [timetableEntries],
  );

  const designationOptions = [
    "Professor",
    "Assoc Professor",
    "Asst Professor",
    "Sr Asst Professor",
    "HOD",
    "Lecturer",
  ];

  const semesterOptions = [
    "I Year I Sem",
    "I Year II Sem",
    "II Year I Sem",
    "II Year II Sem",
    "III Year I Sem",
    "III Year II Sem",
    "IV Year I Sem",
    "IV Year II Sem",
  ];

  const sectionOptions = ["A", "B", "C", "D", "E"];

  function handleSubjectSelect(courseTitle: string) {
    setSubjectName(courseTitle);
    const subject = subjects.find((s) => s.course_title === courseTitle);
    if (subject) {
      setCourseCode(subject.course_code);
    }
  }

  // -----------------------------------------------------------------------
  // Derived state
  // -----------------------------------------------------------------------

  const facultyInfo: FacultyInfo = useMemo(
    () => ({
      faculty_name: facultyName,
      designation,
      subject_name: subjectName,
      course_code: courseCode,
      branch: cleanBranch(selectedEntry),
      semester,
      section,
      student_count: studentCount,
      selected_entry: selectedEntry,
    }),
    [
      facultyName,
      designation,
      subjectName,
      courseCode,
      selectedEntry,
      semester,
      section,
      studentCount,
    ],
  );

  const canGenerate =
    facultyName.trim() !== "" &&
    subjectName.trim() !== "" &&
    selectedSyllabusId !== "" &&
    calendarEntries.length > 0 &&
    timetableEntries.length > 0 &&
    !generating;

  const requestBody = useMemo(
    () => ({
      faculty_info: facultyInfo,
      syllabus_id: selectedSyllabusId
        ? Number(selectedSyllabusId)
        : undefined,
    }),
    [facultyInfo, selectedSyllabusId],
  );

  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------

  async function handleGenerate() {
    setGenerating(true);
    setPreview(null);
    try {
      const result = await api.post<LessonPlanPreview>(
        "/api/generate",
        requestBody,
      );
      setPreview(result);
      toast.success("Lesson plan generated successfully!");
      fetchHistory();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Generation failed.",
      );
    } finally {
      setGenerating(false);
    }
  }

  async function handleExport(
    format: "pdf" | "excel" | "word",
    path: string,
    filename: string,
  ) {
    setExporting(format);
    try {
      await api.downloadBlob(path, requestBody, filename);
      toast.success(`${filename} downloaded.`);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Download failed.",
      );
    } finally {
      setExporting(null);
    }
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 p-4 md:p-8">
      {/* Page heading */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Generate Lesson Plan
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Fill in faculty details, verify your data, select a syllabus, and
          generate your lesson plan.
        </p>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* 1. Faculty Information Form                                        */}
      {/* ----------------------------------------------------------------- */}
      <Card>
        <CardHeader>
          <CardTitle>Faculty Information</CardTitle>
          <CardDescription>
            Provide the details that will appear on the lesson plan document.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {/* Faculty Name */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="faculty_name">
                Faculty Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="faculty_name"
                placeholder="Dr. Jane Doe"
                value={facultyName}
                onChange={(e) => setFacultyName(e.target.value)}
              />
            </div>

            {/* Designation */}
            <div className="flex flex-col gap-1.5">
              <Label>Designation</Label>
              <Select
                value={designation}
                onValueChange={(v) => setDesignation(v ?? "")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select designation..." />
                </SelectTrigger>
                <SelectContent>
                  {designationOptions.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Subject Name */}
            <div className="flex flex-col gap-1.5">
              <Label>
                Subject Name <span className="text-destructive">*</span>
              </Label>
              {subjects.length === 0 ? (
                <Input
                  placeholder="Upload a syllabus first"
                  value={subjectName}
                  onChange={(e) => setSubjectName(e.target.value)}
                />
              ) : (
                <Select
                  value={subjectName}
                  onValueChange={(v) => handleSubjectSelect(v ?? "")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select subject..." />
                  </SelectTrigger>
                  <SelectContent>
                    {subjects.map((s) => (
                      <SelectItem key={s.id} value={s.course_title}>
                        {s.course_title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Course Code (auto-filled from subject) */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="course_code">Course Code</Label>
              <Input
                id="course_code"
                placeholder="Auto-filled from subject"
                value={courseCode}
                readOnly
              />
            </div>

            {/* Branch / Entry */}
            <div className="flex flex-col gap-1.5">
              <Label>Branch</Label>
              {uniqueEntries.length === 0 ? (
                <Input
                  placeholder="Upload timetable first"
                  value={selectedEntry}
                  onChange={(e) => setSelectedEntry(e.target.value)}
                />
              ) : (
                <Select
                  value={selectedEntry}
                  onValueChange={(v) => setSelectedEntry(v ?? "")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select branch..." />
                  </SelectTrigger>
                  <SelectContent>
                    {uniqueEntries.map((b) => (
                      <SelectItem key={b} value={b}>
                        {b}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Semester */}
            <div className="flex flex-col gap-1.5">
              <Label>Semester</Label>
              <Select
                value={semester}
                onValueChange={(v) => setSemester(v ?? "")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select semester..." />
                </SelectTrigger>
                <SelectContent>
                  {semesterOptions.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Section */}
            <div className="flex flex-col gap-1.5">
              <Label>Section</Label>
              <Select
                value={section}
                onValueChange={(v) => setSection(v ?? "")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select section..." />
                </SelectTrigger>
                <SelectContent>
                  {sectionOptions.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Student Count */}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="student_count">Student Count</Label>
              <Input
                id="student_count"
                placeholder="60"
                value={studentCount}
                onChange={(e) => setStudentCount(e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ----------------------------------------------------------------- */}
      {/* 2. Data Summary                                                    */}
      {/* ----------------------------------------------------------------- */}
      <div className="grid gap-4 sm:grid-cols-3">
        {/* Calendar */}
        <Card size="sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <CalendarDays className="size-4 text-muted-foreground" />
              Calendar Entries
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <Skeleton className="h-6 w-16" />
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-2xl font-semibold">
                  {calendarEntries.length}
                </span>
                {calendarEntries.length === 0 && (
                  <Badge variant="destructive">
                    <TriangleAlert className="size-3" />
                    No data
                  </Badge>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Holidays */}
        <Card size="sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <PartyPopper className="size-4 text-muted-foreground" />
              Holidays
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <Skeleton className="h-6 w-16" />
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-2xl font-semibold">
                  {holidays.length}
                </span>
                {holidays.length === 0 && (
                  <Badge variant="destructive">
                    <TriangleAlert className="size-3" />
                    No data
                  </Badge>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Timetable */}
        <Card size="sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm">
              <Clock className="size-4 text-muted-foreground" />
              Timetable Entries
            </CardTitle>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <Skeleton className="h-6 w-16" />
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-2xl font-semibold">
                  {timetableEntries.length}
                </span>
                {timetableEntries.length === 0 && (
                  <Badge variant="destructive">
                    <TriangleAlert className="size-3" />
                    No data
                  </Badge>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* 3. Syllabus Selection + 4. Generate Button                        */}
      {/* ----------------------------------------------------------------- */}
      <Card>
        <CardHeader>
          <CardTitle>Syllabus &amp; Generation</CardTitle>
          <CardDescription>
            Choose the syllabus to base the lesson plan on, then generate.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
            {/* Select */}
            <div className="flex flex-1 flex-col gap-1.5">
              <Label>
                Syllabus <span className="text-destructive">*</span>
              </Label>
              {syllabusLoading ? (
                <Skeleton className="h-8 w-full" />
              ) : subjects.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No syllabi uploaded yet. Please upload one first.
                </p>
              ) : (
                <Select
                  value={selectedSyllabusId}
                  onValueChange={(v) => setSelectedSyllabusId(v ?? "")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select a syllabus..." />
                  </SelectTrigger>
                  <SelectContent>
                    {subjects.map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>
                        {s.course_title}
                        {s.course_code ? ` (${s.course_code})` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Generate button */}
            <Button
              size="lg"
              disabled={!canGenerate}
              onClick={handleGenerate}
              className="sm:w-auto"
            >
              {generating ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="size-4" />
                  Generate Lesson Plan
                </>
              )}
            </Button>
          </div>

          {/* Validation hints */}
          {!summaryLoading &&
            (calendarEntries.length === 0 ||
              timetableEntries.length === 0) && (
              <p className="mt-3 text-xs text-destructive">
                <TriangleAlert className="mr-1 inline size-3" />
                Calendar and timetable data are required before generating.
                Please upload them first.
              </p>
            )}
        </CardContent>
      </Card>

      {/* ----------------------------------------------------------------- */}
      {/* 5. Preview Tabs                                                    */}
      {/* ----------------------------------------------------------------- */}
      {preview && (
        <>
          <Separator />

          <Card>
            <CardHeader>
              <CardTitle>Generated Preview</CardTitle>
              <CardDescription>
                Review the generated data across the three tabs before
                exporting.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="lesson_plan">
                <TabsList>
                  <TabsTrigger value="lesson_plan">Lesson Plan</TabsTrigger>
                  <TabsTrigger value="monthly_plan">Monthly Plan</TabsTrigger>
                  <TabsTrigger value="coverage_report">
                    Coverage Report
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="lesson_plan" className="mt-4">
                  <DynamicTable data={preview.lesson_plan} />
                </TabsContent>

                <TabsContent value="monthly_plan" className="mt-4">
                  <DynamicTable data={preview.monthly_plan} />
                </TabsContent>

                <TabsContent value="coverage_report" className="mt-4">
                  <DynamicTable data={preview.coverage_report} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          {/* --------------------------------------------------------------- */}
          {/* 6. Export Buttons                                                */}
          {/* --------------------------------------------------------------- */}
          <div className="flex flex-wrap gap-3">
            <Button
              variant="outline"
              disabled={exporting !== null}
              onClick={() =>
                handleExport(
                  "pdf",
                  "/api/generate/export/pdf",
                  "lesson_plan.pdf",
                )
              }
            >
              {exporting === "pdf" ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileText className="size-4" />
              )}
              Download PDF
            </Button>

            <Button
              variant="outline"
              disabled={exporting !== null}
              onClick={() =>
                handleExport(
                  "excel",
                  "/api/generate/export/excel",
                  "lesson_plan.xlsx",
                )
              }
            >
              {exporting === "excel" ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <FileSpreadsheet className="size-4" />
              )}
              Download Excel
            </Button>

            <Button
              variant="outline"
              disabled={exporting !== null}
              onClick={() =>
                handleExport(
                  "word",
                  "/api/generate/export/word",
                  "lesson_plan.docx",
                )
              }
            >
              {exporting === "word" ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Download className="size-4" />
              )}
              Download Word
            </Button>
          </div>
        </>
      )}

      {/* ----------------------------------------------------------------- */}
      {/* 7. Generation History                                              */}
      {/* ----------------------------------------------------------------- */}
      <Separator />

      <Card>
        <CardHeader>
          <CardTitle>Generation History</CardTitle>
          <CardDescription>
            Recent lesson plans you have generated.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {historyLoading ? (
            <div className="flex flex-col gap-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : history.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No lesson plans generated yet.
            </p>
          ) : (
            <div className="rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Faculty</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Branch</TableHead>
                    <TableHead>Semester</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead className="text-right">Lectures</TableHead>
                    <TableHead>Generated At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.faculty_name}</TableCell>
                      <TableCell>{item.subject_name}</TableCell>
                      <TableCell>{item.branch || "-"}</TableCell>
                      <TableCell>{item.semester || "-"}</TableCell>
                      <TableCell>
                        <Badge variant={item.is_lab ? "secondary" : "outline"}>
                          {item.is_lab ? "Lab" : "Theory"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        {item.planned_lectures}
                      </TableCell>
                      <TableCell>
                        {new Date(item.generated_at).toLocaleDateString(
                          undefined,
                          {
                            year: "numeric",
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          },
                        )}
                      </TableCell>
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
