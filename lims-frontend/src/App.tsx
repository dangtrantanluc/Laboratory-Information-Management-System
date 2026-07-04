import { Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { RequireAccess } from '@/components/RequireAccess';
import { Login } from '@/pages/Login';
import { ChangePassword } from '@/pages/ChangePassword';
import { Dashboard } from '@/pages/Dashboard';
import { SampleRequests } from '@/pages/SampleRequests';
import { SampleRequestDetail } from '@/pages/SampleRequestDetail';
import { SampleDetailPage } from '@/pages/SampleDetail';
import { Chemicals } from '@/pages/Chemicals';
import { ChemicalDetail } from '@/pages/ChemicalDetail';
import { Documents } from '@/pages/Documents';
import { DocumentDetail } from '@/pages/DocumentDetail';
import { Equipment } from '@/pages/Equipment';
import { EquipmentDetail } from '@/pages/EquipmentDetail';
import { DocumentPendingReview } from '@/pages/DocumentPendingReview';
import { DocumentAccessStats } from '@/pages/DocumentAccessStats';
import { Customers } from '@/pages/Customers';
import { UsersPage } from '@/pages/Users';
import { Departments } from '@/pages/Departments';
import { Notifications } from '@/pages/Notifications';
import { AuditLogs } from '@/pages/AuditLogs';
import { Settings } from '@/pages/Settings';
import { Profile } from '@/pages/Profile';
import { HrProfiles } from '@/pages/HrProfiles';
import { HrProfileDetail, MyProfile } from '@/pages/HrProfileDetail';
import { ResearchProjects } from '@/pages/ResearchProjects';
import { Publications } from '@/pages/Publications';
import { StudentMentorships } from '@/pages/StudentMentorships';
import { LabRegistrations } from '@/pages/LabRegistrations';
import { TeachingCourses } from '@/pages/TeachingCourses';
import { CommunityServices } from '@/pages/CommunityServices';
import { AchievementStats } from '@/pages/AchievementStats';
import { Reports } from '@/pages/Reports';
import {
  canViewAudit,
  canManageUsers,
  canViewChemicals,
  canViewCustomers,
  canViewSamples,
  canListHr,
  canViewResearch,
  canViewDocuments,
  canApproveDocuments,
  canViewDocumentStats,
  canViewEquipment,
  canViewReports,
} from '@/lib/rbac';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />

      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />

        <Route
          path="/samples"
          element={
            <RequireAccess allow={canViewSamples}>
              <SampleRequests />
            </RequireAccess>
          }
        />
        <Route
          path="/samples/request/:id"
          element={
            <RequireAccess allow={canViewSamples}>
              <SampleRequestDetail />
            </RequireAccess>
          }
        />
        <Route
          path="/samples/sample/:id"
          element={
            <RequireAccess allow={canViewSamples}>
              <SampleDetailPage />
            </RequireAccess>
          }
        />

        <Route
          path="/chemicals"
          element={
            <RequireAccess allow={canViewChemicals}>
              <Chemicals />
            </RequireAccess>
          }
        />
        <Route
          path="/chemicals/:id"
          element={
            <RequireAccess allow={canViewChemicals}>
              <ChemicalDetail />
            </RequireAccess>
          }
        />

        {/* ── M3: Quản lý tài liệu ── */}
        <Route
          path="/documents"
          element={
            <RequireAccess allow={canViewDocuments}>
              <Documents />
            </RequireAccess>
          }
        />
        <Route
          path="/documents/pending"
          element={
            <RequireAccess allow={canApproveDocuments}>
              <DocumentPendingReview />
            </RequireAccess>
          }
        />
        <Route
          path="/documents/stats"
          element={
            <RequireAccess allow={canViewDocumentStats}>
              <DocumentAccessStats />
            </RequireAccess>
          }
        />
        <Route
          path="/documents/:id"
          element={
            <RequireAccess allow={canViewDocuments}>
              <DocumentDetail />
            </RequireAccess>
          }
        />

        {/* ── M5: Thiết bị & Hiệu chuẩn ── */}
        <Route
          path="/equipment"
          element={
            <RequireAccess allow={canViewEquipment}>
              <Equipment />
            </RequireAccess>
          }
        />
        <Route
          path="/equipment/:id"
          element={
            <RequireAccess allow={canViewEquipment}>
              <EquipmentDetail />
            </RequireAccess>
          }
        />

        <Route
          path="/customers"
          element={
            <RequireAccess allow={canViewCustomers}>
              <Customers />
            </RequireAccess>
          }
        />
        <Route
          path="/users"
          element={
            <RequireAccess allow={canManageUsers}>
              <UsersPage />
            </RequireAccess>
          }
        />
        <Route
          path="/departments"
          element={
            <RequireAccess allow={canManageUsers}>
              <Departments />
            </RequireAccess>
          }
        />
        {/* ── M4: Nhân sự ── */}
        <Route
          path="/hr"
          element={
            <RequireAccess allow={canListHr}>
              <HrProfiles />
            </RequireAccess>
          }
        />
        <Route
          path="/hr/:userId"
          element={
            <RequireAccess allow={canListHr}>
              <HrProfileDetail />
            </RequireAccess>
          }
        />
        <Route path="/my-profile" element={<MyProfile />} />

        {/* ── M4: NCKH (ẩn với accountant) ── */}
        <Route
          path="/research/projects"
          element={
            <RequireAccess allow={canViewResearch}>
              <ResearchProjects />
            </RequireAccess>
          }
        />
        <Route
          path="/research/publications"
          element={
            <RequireAccess allow={canViewResearch}>
              <Publications />
            </RequireAccess>
          }
        />
        <Route
          path="/research/mentorships"
          element={
            <RequireAccess allow={canViewResearch}>
              <StudentMentorships />
            </RequireAccess>
          }
        />
        <Route
          path="/research/lab-registrations"
          element={
            <RequireAccess allow={canViewResearch}>
              <LabRegistrations />
            </RequireAccess>
          }
        />
        <Route
          path="/research/teaching"
          element={
            <RequireAccess allow={canViewResearch}>
              <TeachingCourses />
            </RequireAccess>
          }
        />
        <Route
          path="/research/community"
          element={
            <RequireAccess allow={canViewResearch}>
              <CommunityServices />
            </RequireAccess>
          }
        />
        <Route
          path="/research/stats"
          element={
            <RequireAccess allow={canViewResearch}>
              <AchievementStats />
            </RequireAccess>
          }
        />

        {/* ── M6: Báo cáo & Thống kê ── */}
        <Route
          path="/reports"
          element={
            <RequireAccess allow={canViewReports}>
              <Reports />
            </RequireAccess>
          }
        />

        <Route path="/notifications" element={<Notifications />} />
        <Route
          path="/audit"
          element={
            <RequireAccess allow={canViewAudit}>
              <AuditLogs />
            </RequireAccess>
          }
        />
        <Route path="/profile" element={<Profile />} />
        <Route path="/settings" element={<Settings />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
