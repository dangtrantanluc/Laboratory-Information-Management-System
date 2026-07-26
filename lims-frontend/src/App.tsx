import { lazy, Suspense, useEffect } from 'react';
import { Navigate, Route, Routes, useNavigate } from 'react-router-dom';
import { registerServiceWorker } from '@/lib/push';
import { LoadingState } from '@/components/ui/States';
import { AppShell } from '@/components/layout/AppShell';
import { RequireAccess } from '@/components/RequireAccess';
import { Login } from '@/pages/Login';
import { ChangePassword } from '@/pages/ChangePassword';

// Lazy-load phần còn lại: gộp 50 trang vào một chunk 1,1 MB nghĩa là mỗi lần
// deploy toàn bộ người dùng tải lại tất cả, kể cả khi chỉ sửa một trang.
// Login/Dashboard/ChangePassword giữ tĩnh vì là màn hình vào app đầu tiên.
const AchievementStats = lazy(() => import('@/pages/AchievementStats').then((m) => ({ default: m.AchievementStats })));
const ActivityReports = lazy(() => import('@/pages/ActivityReports').then((m) => ({ default: m.ActivityReports })));
const AuditLogs = lazy(() => import('@/pages/AuditLogs').then((m) => ({ default: m.AuditLogs })));
const ChemicalDetail = lazy(() => import('@/pages/ChemicalDetail').then((m) => ({ default: m.ChemicalDetail })));
const Chemicals = lazy(() => import('@/pages/Chemicals').then((m) => ({ default: m.Chemicals })));
const CommunityServices = lazy(() => import('@/pages/CommunityServices').then((m) => ({ default: m.CommunityServices })));
const Customers = lazy(() => import('@/pages/Customers').then((m) => ({ default: m.Customers })));
const Departments = lazy(() => import('@/pages/Departments').then((m) => ({ default: m.Departments })));
const DocumentAccessStats = lazy(() => import('@/pages/DocumentAccessStats').then((m) => ({ default: m.DocumentAccessStats })));
const DocumentDetail = lazy(() => import('@/pages/DocumentDetail').then((m) => ({ default: m.DocumentDetail })));
const DocumentPendingReview = lazy(() => import('@/pages/DocumentPendingReview').then((m) => ({ default: m.DocumentPendingReview })));
const Documents = lazy(() => import('@/pages/Documents').then((m) => ({ default: m.Documents })));
const Equipment = lazy(() => import('@/pages/Equipment').then((m) => ({ default: m.Equipment })));
const EquipmentDetail = lazy(() => import('@/pages/EquipmentDetail').then((m) => ({ default: m.EquipmentDetail })));
const ForgotPassword = lazy(() => import('@/pages/ForgotPassword').then((m) => ({ default: m.ForgotPassword })));
const Forms = lazy(() => import('@/pages/Forms').then((m) => ({ default: m.Forms })));
const HrProfileDetail = lazy(() => import('@/pages/HrProfileDetail').then((m) => ({ default: m.HrProfileDetail })));
const HrProfiles = lazy(() => import('@/pages/HrProfiles').then((m) => ({ default: m.HrProfiles })));
const Improvements = lazy(() => import('@/pages/Improvements').then((m) => ({ default: m.Improvements })));
const LabAccessCards = lazy(() => import('@/pages/LabAccessCards').then((m) => ({ default: m.LabAccessCards })));
const LabRegistrations = lazy(() => import('@/pages/LabRegistrations').then((m) => ({ default: m.LabRegistrations })));
const MonthlyReport = lazy(() => import('@/pages/MonthlyReport').then((m) => ({ default: m.MonthlyReport })));
const Nonconformities = lazy(() => import('@/pages/Nonconformities').then((m) => ({ default: m.Nonconformities })));
const NonconformityDetail = lazy(() => import('@/pages/NonconformityDetail').then((m) => ({ default: m.NonconformityDetail })));
const Notifications = lazy(() => import('@/pages/Notifications').then((m) => ({ default: m.Notifications })));
const Profile = lazy(() => import('@/pages/Profile').then((m) => ({ default: m.Profile })));
const Publications = lazy(() => import('@/pages/Publications').then((m) => ({ default: m.Publications })));
const Quotations = lazy(() => import('@/pages/Quotations').then((m) => ({ default: m.Quotations })));
const Register = lazy(() => import('@/pages/Register').then((m) => ({ default: m.Register })));
const Reports = lazy(() => import('@/pages/Reports').then((m) => ({ default: m.Reports })));
const ResearchContracts = lazy(() => import('@/pages/ResearchContracts').then((m) => ({ default: m.ResearchContracts })));
const ResearchProjects = lazy(() => import('@/pages/ResearchProjects').then((m) => ({ default: m.ResearchProjects })));
const ResetPassword = lazy(() => import('@/pages/ResetPassword').then((m) => ({ default: m.ResetPassword })));
const RiskDetail = lazy(() => import('@/pages/RiskDetail').then((m) => ({ default: m.RiskDetail })));
const Risks = lazy(() => import('@/pages/Risks').then((m) => ({ default: m.Risks })));
const SampleDetailPage = lazy(() => import('@/pages/SampleDetail').then((m) => ({ default: m.SampleDetailPage })));
const SampleFlow = lazy(() => import('@/pages/SampleFlow').then((m) => ({ default: m.SampleFlow })));
const SampleRequestDetail = lazy(() => import('@/pages/SampleRequestDetail').then((m) => ({ default: m.SampleRequestDetail })));
const SampleRequests = lazy(() => import('@/pages/SampleRequests').then((m) => ({ default: m.SampleRequests })));
const Settings = lazy(() => import('@/pages/Settings').then((m) => ({ default: m.Settings })));
const StaffActivities = lazy(() => import('@/pages/StaffActivities').then((m) => ({ default: m.StaffActivities })));
const StudentMentorships = lazy(() => import('@/pages/StudentMentorships').then((m) => ({ default: m.StudentMentorships })));
const TeachingCourses = lazy(() => import('@/pages/TeachingCourses').then((m) => ({ default: m.TeachingCourses })));
const TestParameters = lazy(() => import('@/pages/TestParameters').then((m) => ({ default: m.TestParameters })));
const TrainingCertificates = lazy(() => import('@/pages/TrainingCertificates').then((m) => ({ default: m.TrainingCertificates })));
const UsersPage = lazy(() => import('@/pages/Users').then((m) => ({ default: m.UsersPage })));
const VerifyEmail = lazy(() => import('@/pages/VerifyEmail').then((m) => ({ default: m.VerifyEmail })));
import { Dashboard } from '@/pages/Dashboard';
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
    // Suspense bắt buộc cho lazy(): hiện trạng thái tải trong lúc kéo chunk trang.
    <Suspense fallback={<div className="py-20"><LoadingState /></div>}>
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
    </Suspense>
  );
}
