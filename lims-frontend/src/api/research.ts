import { apiDelete, apiDownload, apiGet, apiGetPaged, apiPatch, apiPost, saveBlob } from '@/lib/api';
import type {
  AchievementStats,
  CatalogItem,
  CommunityService,
  LabRegistration,
  ProjectMember,
  Publication,
  PublicationAuthor,
  PublicationType,
  ResearchProject,
  StudentMentorship,
  TeachingCourse,
} from '@/types';

// ── Danh mục ────────────────────────────────────────────────────
export function listProjectLevels() {
  return apiGet<CatalogItem[]>('/catalogs/project-levels');
}
export function listPubIndexes() {
  return apiGet<CatalogItem[]>('/catalogs/pub-indexes');
}
export function listMentorshipTypes() {
  return apiGet<CatalogItem[]>('/catalogs/mentorship-types');
}

// ── Đề tài NCKH ─────────────────────────────────────────────────
export interface ProjectFilters {
  q?: string;
  department_id?: string;
  level?: string;
  year?: number;
  lead_user_id?: string;
  status?: string;
  page?: number;
  limit?: number;
}
export function listProjects(f: ProjectFilters = {}) {
  return apiGetPaged<ResearchProject[]>('/research-projects', { ...f });
}
export function getProject(id: string) {
  return apiGet<ResearchProject>(`/research-projects/${id}`);
}
export interface CreateProjectBody {
  code?: string | null;
  title: string;
  level: string;
  lead_user_id: string;
  department_id?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  status?: string | null;
  members: ProjectMember[];
}
export function createProject(body: CreateProjectBody) {
  return apiPost<ResearchProject>('/research-projects', body);
}
export function updateProject(id: string, body: Partial<Omit<CreateProjectBody, 'members'>>) {
  return apiPatch<ResearchProject>(`/research-projects/${id}`, body);
}
export function deleteProject(id: string) {
  return apiDelete(`/research-projects/${id}`);
}
export function replaceProjectMembers(id: string, members: ProjectMember[]) {
  return apiPost<ResearchProject>(`/research-projects/${id}/members`, { members });
}

// ── Bài báo / Sáng chế ──────────────────────────────────────────
export interface PublicationFilters {
  q?: string;
  type?: string;
  year?: number;
  index_code?: string;
  category?: string;
  department_id?: string;
  author_user_id?: string;
  page?: number;
  limit?: number;
}
export function listPublications(f: PublicationFilters = {}) {
  return apiGetPaged<Publication[]>('/publications', { ...f });
}
export function getPublication(id: string) {
  return apiGet<Publication>(`/publications/${id}`);
}
export interface CreatePublicationBody {
  type: PublicationType;
  title: string;
  journal?: string | null;
  year: number;
  doi?: string | null;
  index_code?: string | null;
  category?: string | null;
  patent_no?: string | null;
  issuing_authority?: string | null;
  department_id?: string | null;
  authors: PublicationAuthor[];
}
export function createPublication(body: CreatePublicationBody) {
  return apiPost<Publication>('/publications', body);
}
export function updatePublication(id: string, body: Partial<Omit<CreatePublicationBody, 'authors' | 'type'>>) {
  return apiPatch<Publication>(`/publications/${id}`, body);
}
export function deletePublication(id: string) {
  return apiDelete(`/publications/${id}`);
}
export function replacePublicationAuthors(id: string, authors: PublicationAuthor[]) {
  return apiPost<Publication>(`/publications/${id}/authors`, { authors });
}

// ── Hướng dẫn sinh viên ─────────────────────────────────────────
export interface MentorshipFilters {
  mentor_id?: string;
  year?: number;
  type?: string;
  department_id?: string;
  page?: number;
  limit?: number;
}
export function listMentorships(f: MentorshipFilters = {}) {
  return apiGetPaged<StudentMentorship[]>('/student-mentorships', { ...f });
}
export interface CreateMentorshipBody {
  mentor_id: string;
  student_name: string;
  topic?: string | null;
  year: number;
  type: string;
}
export function createMentorship(body: CreateMentorshipBody) {
  return apiPost<StudentMentorship>('/student-mentorships', body);
}
export function updateMentorship(id: string, body: Partial<Omit<CreateMentorshipBody, 'mentor_id'>>) {
  return apiPatch<StudentMentorship>(`/student-mentorships/${id}`, body);
}
export function deleteMentorship(id: string) {
  return apiDelete(`/student-mentorships/${id}`);
}

// ── Môn giảng dạy ───────────────────────────────────────────────
export interface TeachingFilters {
  user_id?: string;
  year?: number;
  semester?: string;
  department_id?: string;
  page?: number;
  limit?: number;
}
export function listTeaching(f: TeachingFilters = {}) {
  return apiGetPaged<TeachingCourse[]>('/teaching-courses', { ...f });
}
export interface CreateTeachingBody {
  user_id: string;
  course_name: string;
  semester: string;
  year: number;
}
export function createTeaching(body: CreateTeachingBody) {
  return apiPost<TeachingCourse>('/teaching-courses', body);
}
export function updateTeaching(id: string, body: Partial<Omit<CreateTeachingBody, 'user_id'>>) {
  return apiPatch<TeachingCourse>(`/teaching-courses/${id}`, body);
}
export function deleteTeaching(id: string) {
  return apiDelete(`/teaching-courses/${id}`);
}

// ── Phục vụ cộng đồng ───────────────────────────────────────────
export interface CommunityFilters {
  performer_user_id?: string;
  year?: number;
  from?: string;
  to?: string;
  department_id?: string;
  page?: number;
  limit?: number;
}
export function listCommunity(f: CommunityFilters = {}) {
  return apiGetPaged<CommunityService[]>('/community-services', { ...f });
}
export interface CreateCommunityBody {
  content: string;
  performed_at: string;
  host?: string | null;
  performer_user_id: string;
}
export function createCommunity(body: CreateCommunityBody) {
  return apiPost<CommunityService>('/community-services', body);
}
export function updateCommunity(id: string, body: Partial<Omit<CreateCommunityBody, 'performer_user_id'>>) {
  return apiPatch<CommunityService>(`/community-services/${id}`, body);
}
export function deleteCommunity(id: string) {
  return apiDelete(`/community-services/${id}`);
}

// ── Đăng ký lab (có duyệt) ──────────────────────────────────────
export interface RegistrationFilters {
  status?: string;
  mentor_id?: string;
  department_id?: string;
  page?: number;
  limit?: number;
}
export function listRegistrations(f: RegistrationFilters = {}) {
  return apiGetPaged<LabRegistration[]>('/lab-registrations', { ...f });
}
export interface CreateRegistrationBody {
  student_name: string;
  mentor_id: string;
  registered_from: string;
  registered_to?: string | null;
  purpose: string;
}
export function createRegistration(body: CreateRegistrationBody) {
  return apiPost<LabRegistration>('/lab-registrations', body);
}
export function approveRegistration(id: string, reason?: string) {
  return apiPost<LabRegistration>(`/lab-registrations/${id}/approve`, { reason: reason ?? null });
}
export function rejectRegistration(id: string, reason?: string) {
  return apiPost<LabRegistration>(`/lab-registrations/${id}/reject`, { reason: reason ?? null });
}

// ── Thống kê thành tích ─────────────────────────────────────────
export interface StatsFilters {
  group_by: 'individual' | 'department';
  user_id?: string;
  department_id?: string;
  from?: string;
  to?: string;
  level?: string;
  index_code?: string;
}
export function getAchievementStats(f: StatsFilters) {
  return apiGet<AchievementStats>('/research-achievements/stats', { ...f });
}
export async function exportAchievementStatsXlsx(f: StatsFilters) {
  const { blob, filename } = await apiDownload('/research-achievements/stats.xlsx', { ...f });
  saveBlob(blob, filename);
}
