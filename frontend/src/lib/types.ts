export interface CalendarEntry {
  id: number;
  description: string;
  from_date: string;
  to_date: string;
  event_type: string;
}

export interface Holiday {
  id: number;
  occasion: string;
  holiday_date: string;
}

export interface TimetableEntry {
  id: number;
  day: string;
  period: string;
  entry: string;
  branch: string;
  time_slot: string;
  is_lab: boolean;
}

export interface Subject {
  id: number;
  course_code: string;
  course_title: string;
  regulation: string;
  units: Array<{ unit: string; topics: string[]; co: string }>;
  flat_topics: Array<{ unit: string; topic: string; co: string }>;
  experiments: Array<{ exp_no: string; topic: string }>;
  course_objectives: string[];
  course_outcomes: string[];
  text_books: string[];
  reference_books: string[];
}

export interface FacultyInfo {
  faculty_name: string;
  designation: string;
  subject_name: string;
  course_code: string;
  branch: string;
  semester: string;
  section: string;
  student_count: string;
  selected_entry?: string;
}

export interface LessonPlanPreview {
  lesson_plan: Record<string, string>[];
  monthly_plan: Record<string, string>[];
  coverage_report: Record<string, string>[];
  metadata: Record<string, unknown>;
}

export interface LessonPlanHistoryItem {
  id: number;
  faculty_name: string;
  subject_name: string;
  branch: string;
  semester: string;
  is_lab: boolean;
  planned_lectures: number;
  generated_at: string;
}

export interface AdminStats {
  total_users: number;
  total_admins: number;
  total_faculty: number;
  total_plans: number;
  plans_this_month: number;
}

export interface AdminUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
  plan_count: number;
}

export interface AdminPlan {
  id: number;
  user_id: number;
  user_email: string;
  faculty_name: string;
  subject_name: string;
  course_code: string;
  branch: string;
  semester: string;
  is_lab: boolean;
  planned_lectures: number;
  generated_at: string;
}
