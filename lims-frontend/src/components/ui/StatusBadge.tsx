import {
  SAMPLE_STATUS_LABELS,
  REQUEST_STATUS_LABELS,
  TXN_TYPE_LABELS,
  REGISTRATION_STATUS_LABELS,
  PUBLICATION_TYPE_LABELS,
  COMPETENCE_KIND_LABELS,
  DOC_VERSION_STATUS_LABELS,
  SECURITY_LEVEL_LABELS,
  EQUIPMENT_STATUS_LABELS,
  CALIBRATION_STATUS_LABELS,
  type EquipmentStatus,
  type CalibrationStatus,
  type SampleStatus,
  type RequestStatus,
  type TransactionType,
  type ApprovalStatus,
  type ChemicalStatus,
  type RegistrationStatus,
  type PublicationType,
  type CompetenceKind,
  type DocVersionStatus,
  type SecurityLevel,
} from '@/types';
import { Badge, type BadgeTone } from './Badge';

const SAMPLE_TONE: Record<SampleStatus, BadgeTone> = {
  received: 'warning',
  assigned: 'info',
  testing: 'pending',
  done: 'success',
  overdue: 'overdue',
  returned: 'muted',
};

export function SampleStatusBadge({ status }: { status: SampleStatus }) {
  return (
    <Badge tone={SAMPLE_TONE[status] ?? 'neutral'} dot>
      {SAMPLE_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

const REQUEST_TONE: Record<RequestStatus, BadgeTone> = {
  draft: 'muted',
  active: 'pending',
};

export function RequestStatusBadge({ status }: { status: RequestStatus }) {
  return <Badge tone={REQUEST_TONE[status] ?? 'neutral'}>{REQUEST_STATUS_LABELS[status] ?? status}</Badge>;
}

const TXN_TONE: Record<TransactionType, BadgeTone> = {
  in: 'success',
  out: 'info',
  adjust: 'warning',
};

export function TxnTypeBadge({ type }: { type: TransactionType }) {
  return <Badge tone={TXN_TONE[type] ?? 'neutral'}>{TXN_TYPE_LABELS[type] ?? type}</Badge>;
}

const APPROVAL_TONE: Record<ApprovalStatus, BadgeTone> = {
  pending: 'warning',
  approved: 'success',
  returned: 'overdue',
};
const APPROVAL_LABELS: Record<ApprovalStatus, string> = {
  pending: 'Chờ duyệt',
  approved: 'Đã duyệt',
  returned: 'Trả lại',
};
export function ApprovalBadge({ status }: { status: ApprovalStatus }) {
  return <Badge tone={APPROVAL_TONE[status] ?? 'neutral'}>{APPROVAL_LABELS[status] ?? status}</Badge>;
}

export function ChemicalStatusBadge({ status }: { status: ChemicalStatus }) {
  return (
    <Badge tone={status === 'active' ? 'success' : 'muted'}>
      {status === 'active' ? 'Đang dùng' : 'Ngừng dùng'}
    </Badge>
  );
}

const REGISTRATION_TONE: Record<RegistrationStatus, BadgeTone> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'overdue',
};
export function RegistrationStatusBadge({ status }: { status: RegistrationStatus }) {
  return (
    <Badge tone={REGISTRATION_TONE[status] ?? 'neutral'} dot>
      {REGISTRATION_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export function PublicationTypeBadge({ type }: { type: PublicationType }) {
  return (
    <Badge tone={type === 'paper' ? 'info' : 'pending'}>{PUBLICATION_TYPE_LABELS[type] ?? type}</Badge>
  );
}

// ── M3: Document Control ────────────────────────────────────────
const DOC_VERSION_TONE: Record<DocVersionStatus, BadgeTone> = {
  draft: 'muted',
  review: 'warning',
  approved: 'success',
  obsolete: 'overdue',
};
export function DocVersionStatusBadge({ status }: { status: DocVersionStatus }) {
  return (
    <Badge tone={DOC_VERSION_TONE[status] ?? 'neutral'} dot>
      {DOC_VERSION_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export function SecurityLevelBadge({ level }: { level: SecurityLevel }) {
  return (
    <Badge tone={level === 'restricted' ? 'overdue' : 'info'}>
      {SECURITY_LEVEL_LABELS[level] ?? level}
    </Badge>
  );
}

// ── M5: Thiết bị & Hiệu chuẩn ───────────────────────────────────
const EQUIPMENT_STATUS_TONE: Record<EquipmentStatus, BadgeTone> = {
  active: 'success',
  maintenance: 'warning',
  broken: 'overdue',
  retired: 'muted',
};
export function EquipmentStatusBadge({ status }: { status: EquipmentStatus }) {
  return (
    <Badge tone={EQUIPMENT_STATUS_TONE[status] ?? 'neutral'} dot>
      {EQUIPMENT_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

const CALIBRATION_STATUS_TONE: Record<CalibrationStatus, BadgeTone> = {
  not_applicable: 'neutral',
  never_calibrated: 'muted',
  ok: 'success',
  due_soon: 'warning',
  overdue: 'overdue',
  failed: 'overdue',
};
/** Badge cảnh báo hiệu chuẩn — backend tính, FE chỉ hiển thị. */
export function CalibrationStatusBadge({ status }: { status: CalibrationStatus }) {
  if (status === 'not_applicable') {
    return <span className="text-xs text-subink">Không hiệu chuẩn</span>;
  }
  return (
    <Badge tone={CALIBRATION_STATUS_TONE[status] ?? 'neutral'} dot>
      {CALIBRATION_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

const COMPETENCE_TONE: Record<CompetenceKind, BadgeTone> = {
  degree: 'info',
  certificate: 'success',
  authorization: 'warning',
};
export function CompetenceKindBadge({ kind }: { kind: CompetenceKind }) {
  return (
    <Badge tone={COMPETENCE_TONE[kind] ?? 'neutral'}>{COMPETENCE_KIND_LABELS[kind] ?? kind}</Badge>
  );
}
