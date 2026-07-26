import { useEffect } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { registerServiceWorker } from '@/lib/push';
import { AppShell } from '@/components/layout/AppShell';
import { RequireAccess } from '@/components/RequireAccess';
import { Login } from '@/pages/Login';
import { ChangePassword } from '@/pages/ChangePassword';
import { Register } from '@/pages/Register';
import { ForgotPassword } from '@/pages/ForgotPassword';
import { ResetPassword } from '@/pages/ResetPassword';
import { VerifyEmail } from '@/pages/VerifyEmail';
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
import { Nonconformities } from '@/pages/Nonconformities';
import { NonconformityDetail } from '@/pages/NonconformityDetail';
import { Risks } from '@/pages/Risks';
import { RiskDetail } from '@/pages/RiskDetail';
import { Improvements } from '@/pages/Improvements';
import { DocumentPendingReview } from '@/pages/DocumentPendingReview';
import { DocumentAccessStats } from '@/pages/DocumentAccessStats';
import { Customers } from '@/pages/Customers';
import { Forms } from '@/pages/Forms';
import { LabAccessCards } from '@/pages/LabAccessCards';
import { SampleFlow } from '@/pages/SampleFlow';
import { UsersPage } from '@/pages/Users';
import { Departments } from '@/pages/Departments';
import { Notifications } from '@/pages/Notifications';
import { AuditLogs } from '@/pages/AuditLogs';
import { Settings } from '@/pages/Settings';
import { Profile } from '@/pages/Profile';
import { HrProfiles } from '@/pages/HrProfiles';
import { HrProfileDetail } from '@/pages/HrProfileDetail';
import { ResearchProjects } from '@/pages/ResearchProjects';
import { Publications } from '@/pages/Publications';
import { StudentMentorships } from '@/pages/StudentMentorships';
import { LabRegistrations } from '@/pages/LabRegistrations';
import { TeachingCourses } from '@/pages/TeachingCourses';
import { CommunityServices } from '@/pages/CommunityServices';
import { ResearchContracts } from '@/pages/ResearchContracts';
import { TrainingCertificates } from '@/pages/TrainingCertificates';
import { StaffActivities } from '@/pages/StaffActivities';
import { TestParameters } from '@/pages/TestParameters';
import { Quotations } from '@/pages/Quotations';
import { ActivityReports } from '@/pages/ActivityReports';
import { MonthlyReport } from '@/pages/MonthlyReport';
import { AchievementStats } from '@/pages/AchievementStats';
import { Reports } from '@/pages/Reports';
import {
  canViewAudit,
  canManageUsers,
  canViewChemicals,
  canViewCustomers,
  canViewForms,
  canViewLabAccessCards,
  canViewIntake,
  canViewLabReg,
  canViewSamples,
  canListHr,
  canViewResearch,
  canManageActivities,
  canViewActivities,
  canViewTestParameters,
  canViewQuotations,
  canSubmitActivityReport,
  canViewActivityReports,
  canViewMentorship,
  canViewTeaching,
  canViewDocuments,
  canApproveDocuments,
  canViewDocumentStats,
  canViewEquipment,
  canViewReports,
  canViewNC,
  canViewRisk,
  canViewImprovement,
} from '@/lib/rbac';

export default function App() {
  const navigate = useNavigate();

  useEffect(() => {
    registerServiceWorker();
    function onMessage(event: MessageEvent) {
      if (event.data?.type === 'notification-click' && event.data?.url) {
        navigate(event.data.url);
      }
    }
    navigator.serviceWorker?.addEventListener('message', onMessage);
    return () => navigator.serviceWorker?.removeEventListener('message', onMessage);
  }, [navigate]);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/change-password" element={<ChangePassword />} />
      {/* m30 — luồng tự phục vụ tài khoản, KHÔNG cần đăng nhập */}
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/verify-email" element={<VerifyEmail />} />

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
          path="/forms"
          element={
            <RequireAccess allow={canViewForms}>
              <Forms />
            </RequireAccess>
          }
        />
        <Route
          path="/sample-flow"
          element={
            <RequireAccess allow={canViewIntake}>
              <SampleFlow />
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
        {/* Gộp vào "Hồ sơ cá nhân" — giữ redirect cho link/bookmark cũ */}
        <Route path="/my-profile" element={<Navigate to="/profile" replace />} />

        {/* ── M4: NCKH (ẩn với office) ── */}
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
            <RequireAccess allow={canViewMentorship}>
              <StudentMentorships />
            </RequireAccess>
          }
        />
        <Route
          path="/research/lab-registrations"
          element={
            <RequireAccess allow={canViewLabReg}>
              <LabRegistrations />
            </RequireAccess>
          }
        />
        <Route
          path="/lab-access-cards"
          element={
            <RequireAccess allow={canViewLabAccessCards}>
              <LabAccessCards />
            </RequireAccess>
          }
        />
        <Route
          path="/research/teaching"
          element={
            <RequireAccess allow={canViewTeaching}>
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
          path="/research/contracts"
          element={
            <RequireAccess allow={canManageActivities}>
              <ResearchContracts />
            </RequireAccess>
          }
        />
        <Route
          path="/research/certificates"
          element={
            <RequireAccess allow={canViewActivities}>
              <TrainingCertificates />
            </RequireAccess>
          }
        />
        <Route path="/staff-activities" element={<StaffActivities />} />
        <Route
          path="/quotations"
          element={
            <RequireAccess allow={canViewQuotations}>
              <Quotations />
            </RequireAccess>
          }
        />
        <Route
          path="/test-parameters"
          element={
            <RequireAccess allow={canViewTestParameters}>
              <TestParameters />
            </RequireAccess>
          }
        />
        <Route
          path="/activity-reports"
          element={
            <RequireAccess allow={canViewActivityReports}>
              <ActivityReports />
            </RequireAccess>
          }
        />
        <Route
          path="/activity-reports/new"
          element={
            <RequireAccess allow={canSubmitActivityReport}>
              <MonthlyReport />
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

        {/* ── M8: QMS — Không phù hợp & CAPA ── */}
        <Route
          path="/nonconformities"
          element={
            <RequireAccess allow={canViewNC}>
              <Nonconformities />
            </RequireAccess>
          }
        />
        <Route
          path="/nonconformities/:id"
          element={
            <RequireAccess allow={canViewNC}>
              <NonconformityDetail />
            </RequireAccess>
          }
        />
        <Route
          path="/risks"
          element={
            <RequireAccess allow={canViewRisk}>
              <Risks />
            </RequireAccess>
          }
        />
        <Route
          path="/risks/:id"
          element={
            <RequireAccess allow={canViewRisk}>
              <RiskDetail />
            </RequireAccess>
          }
        />
        <Route
          path="/improvements"
          element={
            <RequireAccess allow={canViewImprovement}>
              <Improvements />
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
