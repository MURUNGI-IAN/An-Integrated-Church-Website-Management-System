from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PageInput(BaseModel):
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(max_length=50000)
    is_published: bool = False


class PageOutput(PageInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: datetime


class LanguageOutput(BaseModel):
    code: str
    name: str
    phase: int
    enabled: bool


class TranslationInput(BaseModel):
    entity_type: Literal["page", "sermon"]
    entity_id: int = Field(ge=1)
    field: Literal["title", "body", "speaker", "scripture", "summary"]
    language: Literal["lg", "nyn", "rw", "sw"]
    value: str = Field(min_length=1, max_length=50000)
    source: Literal["human", "ai_draft"] = "human"
    status: Literal["draft", "pending_review"] = "draft"


class TranslationOutput(TranslationInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["draft", "pending_review", "approved", "rejected"]
    created_by_id: int
    approved_by_id: int | None
    approved_at: datetime | None
    updated_at: datetime


class TranslationReviewInput(BaseModel):
    status: Literal["approved", "rejected"]


class CaptionInput(BaseModel):
    sermon_id: int = Field(ge=1)
    language: Literal["en", "lg", "nyn", "rw"]
    file_format: Literal["srt", "vtt"]
    content: str = Field(min_length=1, max_length=500000)
    source: Literal["human", "ai_draft"] = "human"
    status: Literal["draft", "pending_review"] = "draft"


class CaptionOutput(CaptionInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: Literal["draft", "pending_review", "approved", "rejected"]
    created_by_id: int
    approved_by_id: int | None
    approved_at: datetime | None
    updated_at: datetime


class CaptionReviewInput(BaseModel):
    status: Literal["approved", "rejected"]


class SermonFields(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    speaker: str = Field(min_length=1, max_length=120)
    scripture: str | None = Field(default=None, max_length=120)
    summary: str = Field(default="", max_length=10000)
    media_url: str | None = Field(default=None, max_length=1000)
    published_at: datetime
    is_published: bool = False

class SermonInput(SermonFields):
    @field_validator("published_at")
    @classmethod
    def published_at_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("A timezone is required")
        return value

    @field_validator("media_url")
    @classmethod
    def media_url_must_use_https(cls, value: str | None) -> str | None:
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("Media URLs must use HTTPS")
        return value


class SermonOutput(SermonFields):
    model_config = ConfigDict(from_attributes=True)

    id: int

    @field_validator("published_at", mode="before")
    @classmethod
    def normalize_stored_timezone(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class EventFields(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    location: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    capacity: int | None = Field(default=None, ge=1)
    registration_open: bool = True
    is_published: bool = False
    branch_id: int | None = Field(default=None, ge=1)

class EventInput(EventFields):
    @field_validator("starts_at")
    @classmethod
    def event_start_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("A timezone is required")
        return value


class EventOutput(EventFields):
    model_config = ConfigDict(from_attributes=True)

    id: int

    @field_validator("starts_at", mode="before")
    @classmethod
    def normalize_stored_timezone(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class RegistrationInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    consent: bool


class PrayerInput(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    contact: str | None = Field(default=None, max_length=320)
    message: str = Field(min_length=1, max_length=5000)
    consent: bool


class ContactInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)
    consent: bool


class NewsletterInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    consent: bool


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PrayerOutput(BaseModel):
    id: int
    name: str | None
    contact: str | None
    message: str
    status: str
    created_at: datetime


class ContactOutput(BaseModel):
    id: int
    name: str
    email: str
    subject: str
    message: str
    status: str
    created_at: datetime


class VisitorVisitInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    contact: str = Field(min_length=7, max_length=320)
    visit_date: date | None = None
    consent: bool


class VisitorVisitOutput(BaseModel):
    id: int
    name: str
    contact: str
    visit_date: date | None
    status: str
    consented_at: datetime
    created_at: datetime


class SmallGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=3000)
    meeting_area: str = Field(min_length=1, max_length=160)
    meeting_day: Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    meeting_time: str = Field(min_length=1, max_length=40)
    age_group: str = Field(default="All ages", min_length=1, max_length=80)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    is_open: bool = True
    is_published: bool = False
    branch_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def coordinates_must_be_paired(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Approximate latitude and longitude must be provided together")
        return self


class SmallGroupOutput(SmallGroupInput):
    id: int
    created_at: datetime
    updated_at: datetime
    coordinates_approximate: bool = True
    distance_km: float | None = None


class GroupWaitlistInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    contact: str = Field(min_length=7, max_length=320)
    consent: bool


class GroupWaitlistOutput(BaseModel):
    id: int
    name: str
    contact: str
    status: str
    consented_at: datetime
    created_at: datetime


class MemberProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    branch_id: int | None = Field(default=None, ge=1)


class MemberCreateInput(MemberProfileInput):
    consent_confirmed: bool


class MemberOutput(MemberProfileInput):
    id: int
    status: str
    consented_at: datetime
    created_at: datetime
    updated_at: datetime


class CommunicationConsentInput(BaseModel):
    channel: Literal["email", "sms", "whatsapp"]
    is_consented: bool
    consent_source: Literal["in_person", "paper_form", "web_form", "member_request", "not_provided"]
    delivery_frequency: Literal["weekly", "monthly", "essential_only"] = "essential_only"
    quiet_hours_start: str = Field(default="21:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str = Field(default="07:00", pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    timezone: Literal["Africa/Kampala"] = "Africa/Kampala"


class CommunicationConsentUpdate(BaseModel):
    preferences: list[CommunicationConsentInput] = Field(min_length=1, max_length=3)

    @field_validator("preferences")
    @classmethod
    def channels_must_be_unique(cls, value: list[CommunicationConsentInput]) -> list[CommunicationConsentInput]:
        channels = [preference.channel for preference in value]
        if len(set(channels)) != len(channels):
            raise ValueError("Each communication channel may appear only once")
        return value


class CommunicationConsentOutput(CommunicationConsentInput):
    consented_at: datetime | None
    updated_at: datetime | None


class AttendanceInput(BaseModel):
    member_id: int = Field(ge=1)
    service_name: str = Field(min_length=1, max_length=120)
    service_date: date
    check_in_method: Literal["manual", "phone", "qr"] = "manual"
    branch_id: int | None = Field(default=None, ge=1)


class AttendanceOutput(BaseModel):
    id: int
    member_id: int
    member_name: str
    service_name: str
    service_date: date
    check_in_method: str
    checked_in_at: datetime
    checked_out_at: datetime | None
    branch_id: int | None = None


class ChildProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    primary_guardian_id: int = Field(ge=1)
    authorized_pickup_member_ids: list[int] = Field(default_factory=list, max_length=50)
    consent_confirmed: bool


class ChildOutput(BaseModel):
    id: int
    name: str
    primary_guardian_id: int
    authorized_pickup_member_ids: list[int]
    is_active: bool
    consented_at: datetime
    created_at: datetime
    updated_at: datetime


class ChildAttendanceInput(BaseModel):
    child_id: int = Field(ge=1)
    service_name: str = Field(min_length=1, max_length=120)
    service_date: date
    checked_in_by_member_id: int = Field(ge=1)


class ChildCheckoutInput(BaseModel):
    checked_out_by_member_id: int = Field(ge=1)


class ChildAttendanceOutput(BaseModel):
    id: int
    child_id: int
    child_name: str
    service_name: str
    service_date: date
    checked_in_by_member_id: int
    checked_in_by_name: str
    checked_in_at: datetime
    checked_out_by_member_id: int | None
    checked_out_by_name: str | None
    checked_out_at: datetime | None


class EmergencyAlertInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=2000)
    expires_at: datetime | None = None
    is_active: bool = False

    @field_validator("expires_at")
    @classmethod
    def expiration_must_have_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("A timezone is required")
        return value


class EmergencyAlertOutput(BaseModel):
    id: int
    title: str
    message: str
    expires_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_validator("expires_at", "created_at", "updated_at", mode="before")
    @classmethod
    def normalize_stored_timezone(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


class VolunteerAvailabilityInput(BaseModel):
    member_id: int = Field(ge=1)
    service_name: str = Field(min_length=1, max_length=120)
    service_date: date
    is_available: bool


class VolunteerAvailabilityOutput(BaseModel):
    member_id: int
    member_name: str
    service_name: str
    service_date: date
    is_available: bool
    updated_at: datetime
    branch_id: int | None = None


class AvailabilityInviteInput(BaseModel):
    member_id: int = Field(ge=1)
    service_name: str = Field(min_length=1, max_length=120)
    service_date: date


class AvailabilityInviteOutput(BaseModel):
    token: str
    expires_at: datetime


class AvailabilityInviteToken(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class AvailabilityInviteDetails(BaseModel):
    service_name: str
    service_date: date


class AvailabilityResponseInput(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    is_available: bool


class RotaGenerationInput(BaseModel):
    service_name: str = Field(min_length=1, max_length=120)
    service_date: date
    role_names: list[str] = Field(min_length=1, max_length=30)

    @field_validator("role_names")
    @classmethod
    def roles_must_be_unique_and_nonblank(cls, value: list[str]) -> list[str]:
        roles = [role.strip() for role in value]
        if any(not role for role in roles) or len({role.casefold() for role in roles}) != len(roles):
            raise ValueError("Role names must be nonblank and unique")
        return roles


class RotaAssignmentOutput(BaseModel):
    id: int
    member_id: int
    member_name: str
    service_name: str
    service_date: date
    role_name: str
    created_at: datetime
    branch_id: int | None = None


class FinanceEntryInput(BaseModel):
    entry_type: Literal["income", "expense"]
    amount_ugx: int = Field(gt=0, le=10_000_000_000)
    fund: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    entry_date: date
    payment_method: Literal["cash", "bank", "mobile_money_manual", "card_manual", "other"] = "cash"
    details: str = Field(default="", max_length=2000)
    branch_id: int | None = Field(default=None, ge=1)


class FinanceEntryOutput(BaseModel):
    id: int
    entry_type: Literal["income", "expense"]
    amount_ugx: int
    fund: str
    category: str
    entry_date: date
    payment_method: str
    status: str
    details: str
    recorded_by_id: int
    reviewed_by_id: int | None
    correction_of_id: int | None
    created_at: datetime
    reviewed_at: datetime | None
    branch_id: int | None = None


class FinanceEntryCorrectionInput(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class PayrollInput(BaseModel):
    member_id: int = Field(ge=1)
    period_start: date
    period_end: date
    salary_ugx: int = Field(ge=0, le=10_000_000_000)
    allowances_ugx: int = Field(default=0, ge=0, le=10_000_000_000)
    deductions_ugx: int = Field(default=0, ge=0, le=10_000_000_000)
    paye_ugx: int = Field(default=0, ge=0, le=10_000_000_000)
    nssf_ugx: int = Field(default=0, ge=0, le=10_000_000_000)

    @model_validator(mode="after")
    def period_and_totals_are_valid(self):
        if self.period_end < self.period_start:
            raise ValueError("Payroll period end must be on or after the start")
        if self.deductions_ugx + self.paye_ugx + self.nssf_ugx > self.salary_ugx + self.allowances_ugx:
            raise ValueError("Total deductions cannot exceed gross pay")
        return self


class PayrollOutput(BaseModel):
    id: int
    member_id: int
    period_start: date
    period_end: date
    salary_ugx: int
    allowances_ugx: int
    deductions_ugx: int
    paye_ugx: int
    nssf_ugx: int
    gross_ugx: int
    net_ugx: int
    created_by_id: int
    updated_by_id: int
    created_at: datetime
    updated_at: datetime


class PayrollReportOutput(BaseModel):
    period_start: date
    period_end: date
    record_count: int
    gross_ugx: int
    allowances_ugx: int
    deductions_ugx: int
    paye_ugx: int
    nssf_ugx: int
    net_ugx: int


class CounselingAppointmentInput(BaseModel):
    counselee_id: int = Field(ge=1)
    appointment_at: datetime
    appointment_type: Literal["pre_marital", "marriage", "grief", "pastoral"]
    assigned_counselor_id: int = Field(ge=1)
    assigned_counselor_role: Literal["senior_pastor", "associate_pastor", "licensed_counselor", "safeguarding_lead"]
    status: Literal["booked", "completed", "cancelled"] = "booked"

    @field_validator("appointment_at")
    @classmethod
    def appointment_must_have_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Appointment time must include a timezone")
        return value


class CounselingAppointmentOutput(CounselingAppointmentInput):
    id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class OfferingCountInput(BaseModel):
    service_name: str = Field(min_length=1, max_length=120)
    service_date: date
    fund: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    amount_ugx: int = Field(gt=0, le=10_000_000_000)
    notes: str = Field(default="", max_length=2000)
    branch_id: int | None = Field(default=None, ge=1)


class OfferingCountVerificationInput(BaseModel):
    amount_ugx: int = Field(gt=0, le=10_000_000_000)


class OfferingCountResolutionInput(BaseModel):
    amount_ugx: int = Field(gt=0, le=10_000_000_000)
    reason: str = Field(min_length=5, max_length=1000)


class OfferingCountOutput(BaseModel):
    id: int
    service_name: str
    service_date: date
    fund: str
    category: str
    amount_counted_ugx: int
    verified_amount_ugx: int | None
    final_amount_ugx: int | None
    status: str
    counted_by_id: int
    verified_by_id: int | None
    resolved_by_id: int | None
    finance_entry_id: int | None
    notes: str
    created_at: datetime
    verified_at: datetime | None
    resolved_at: datetime | None
    branch_id: int | None = None


class FinanceBudgetInput(BaseModel):
    fund: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=120)
    amount_ugx: int = Field(gt=0, le=10_000_000_000)
    period_start: date
    period_end: date
    branch_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def period_is_ordered(self):
        if self.period_end < self.period_start:
            raise ValueError("Budget period end must be on or after its start")
        return self


class FinanceBudgetOutput(FinanceBudgetInput):
    id: int
    created_by_id: int
    created_at: datetime
    spent_ugx: int = 0


class FinancePledgeInput(BaseModel):
    campaign: str = Field(min_length=1, max_length=160)
    amount_ugx: int = Field(gt=0, le=10_000_000_000)
    due_date: date | None = None
    donor_name: str = Field(min_length=1, max_length=160)
    donor_contact: str | None = Field(default=None, max_length=320)
    details: str = Field(default="", max_length=1000)
    branch_id: int | None = Field(default=None, ge=1)


class FinancePledgeStatusInput(BaseModel):
    status: Literal["pledged", "partially_fulfilled", "fulfilled", "cancelled"]
    amount_fulfilled_ugx: int = Field(default=0, ge=0, le=10_000_000_000)


class FinancePledgeOutput(BaseModel):
    id: int
    campaign: str
    amount_ugx: int
    amount_fulfilled_ugx: int
    due_date: date | None
    status: str
    donor_name: str
    donor_contact: str | None
    details: str
    branch_id: int | None = None
    recorded_by_id: int
    created_at: datetime


class FinanceReportOutput(BaseModel):
    period_start: date
    period_end: date
    income_ugx: int
    approved_expenses_ugx: int
    pending_expenses_ugx: int
    pending_corrections_ugx: int
    budgeted_ugx: int
    pledge_total_ugx: int


class PastoralCareTaskInput(BaseModel):
    member_id: int = Field(ge=1)
    care_type: Literal["attendance", "pastoral_follow_up", "counseling", "bereavement", "welfare", "other"]
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    due_date: date | None = None
    notes: str = Field(min_length=1, max_length=3000)
    assigned_to_id: int | None = Field(default=None, ge=1)


class PastoralCareTaskUpdate(BaseModel):
    priority: Literal["low", "normal", "high", "urgent"]
    due_date: date | None = None
    status: Literal["open", "in_progress", "completed", "cancelled"]
    notes: str = Field(min_length=1, max_length=3000)
    assigned_to_id: int | None = Field(default=None, ge=1)


class PastoralCareTaskOutput(BaseModel):
    id: int
    member_id: int
    member_name: str
    care_type: str
    priority: str
    due_date: date | None
    status: str
    notes: str
    assigned_to_id: int | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class ChurchResourceInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    is_active: bool = True
    branch_id: int | None = Field(default=None, ge=1)


class ChurchResourceOutput(ChurchResourceInput):
    id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class ResourceBookingInput(BaseModel):
    resource_id: int = Field(ge=1)
    starts_at: datetime
    ends_at: datetime
    purpose: str = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def booking_times_are_valid(self):
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("Booking times must include a timezone")
        if self.ends_at <= self.starts_at:
            raise ValueError("Booking end must be after its start")
        return self


class ResourceBookingStatusInput(BaseModel):
    status: Literal["approved", "rejected", "cancelled"]


class ResourceBookingOutput(BaseModel):
    id: int
    resource_id: int
    resource_name: str
    starts_at: datetime
    ends_at: datetime
    status: str
    purpose: str
    requested_by_id: int
    reviewed_by_id: int | None
    created_at: datetime
    reviewed_at: datetime | None
    branch_id: int | None = None


class StaffDocumentInput(BaseModel):
    document_type: str = Field(min_length=1, max_length=48)
    title: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["application/pdf", "text/plain", "image/jpeg", "image/png"]
    content_base64: str = Field(min_length=1, max_length=2_800_000)


class StaffDocumentOutput(BaseModel):
    id: int
    document_type: str
    title: str
    filename: str
    content_type: str
    size_bytes: int
    created_by_id: int
    created_at: datetime


class MemberCertificateInput(BaseModel):
    member_id: int = Field(ge=1)
    certificate_type: str = Field(min_length=1, max_length=80)
    issued_on: date
    certificate_number: str = Field(min_length=1, max_length=80)
    details: str = Field(default="", max_length=2000)


class MemberCertificateOutput(BaseModel):
    id: int
    member_id: int
    member_name: str
    certificate_type: str
    issued_on: date
    certificate_number: str
    details: str
    issued_by_id: int
    created_at: datetime


class GovernanceMeetingInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    meeting_date: date
    location: str = Field(default="", max_length=200)
    status: Literal["scheduled", "held", "cancelled"] = "scheduled"
    minutes: str = Field(default="", max_length=20000)
    branch_id: int | None = Field(default=None, ge=1)


class GovernanceMeetingOutput(BaseModel):
    id: int
    title: str
    meeting_date: date
    location: str
    status: str
    minutes: str
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    branch_id: int | None = None


class GovernanceResolutionInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    due_date: date | None = None


class GovernanceResolutionStatusInput(BaseModel):
    status: Literal["approved", "rejected", "in_progress", "completed"]


class GovernanceResolutionOutput(BaseModel):
    id: int
    meeting_id: int
    title: str
    description: str
    status: str
    due_date: date | None
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class AnalyticsOverviewOutput(BaseModel):
    period_start: date
    period_end: date
    active_members: int
    attendance_check_ins: int
    distinct_attendees: int
    service_days_recorded: int
    visitor_requests: int
    new_visitor_follow_ups: int
    published_events: int
    event_registrations: int
    published_small_groups: int
    open_governance_actions: int


class BranchInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    location: str = Field(default="", max_length=200)
    is_active: bool = True


class BranchOutput(BranchInput):
    id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class InstitutionMissionInput(BaseModel):
    record_type: Literal["school", "clinic", "savings_group", "church_plant", "mission_field"]
    name: str = Field(min_length=1, max_length=160)
    location: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=3000)
    is_active: bool = True
    branch_id: int | None = Field(default=None, ge=1)


class InstitutionMissionOutput(InstitutionMissionInput):
    id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime


class SafeguardingReportInput(BaseModel):
    report_type: Literal["incident", "complaint"]
    incident_date: date
    incident_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    location: str = Field(min_length=1, max_length=200)
    people_involved: str = Field(min_length=1, max_length=5000)
    witness_names: str = Field(default="", max_length=3000)
    factual_description: str = Field(min_length=10, max_length=10000)
    action_taken: str = Field(default="", max_length=5000)
    reporter_name: str = Field(min_length=1, max_length=160)
    reporter_contact: str = Field(min_length=5, max_length=320)
    involves_restricted_staff: bool = False
    serious_child_protection: bool = False
    privacy_acknowledged: bool


class SafeguardingReportOutput(BaseModel):
    id: int
    report_type: Literal["incident", "complaint"]
    incident_date: date
    incident_time: str
    location: str
    people_involved: str
    witness_names: str
    factual_description: str
    action_taken: str
    reporter_name: str
    reporter_contact: str
    involves_restricted_staff: bool
    serious_child_protection: bool
    status: str
    retention_until: date
    external_referral_at: datetime | None
    investigation_started_by_id: int | None
    senior_resolution_approval_by_id: int | None
    trustee_resolution_approval_by_id: int | None
    created_at: datetime
    updated_at: datetime


class SafeguardingReportStatusInput(BaseModel):
    status: Literal[
        "investigating",
        "pending_resolution",
        "approve_resolution",
        "reject_resolution",
        "referred_to_authorities",
    ]


class VolunteerVettingInput(BaseModel):
    member_id: int = Field(ge=1)
    government_id: str = Field(min_length=1, max_length=80)
    reference_names: str = Field(min_length=1, max_length=2000)
    reference_contacts: str = Field(min_length=1, max_length=3000)
    background_check_consent: bool
    service_started_at: date | None = None


class VolunteerVettingOutput(BaseModel):
    id: int
    member_id: int
    member_name: str
    government_id: str
    reference_names: str
    reference_contacts: str
    background_check_consent: bool
    background_check_status: str
    references_checked: bool
    training_completed_at: date | None
    service_started_at: date
    service_ended_at: date | None
    retention_until: date | None
    status: str
    created_by_id: int
    reviewed_by_id: int | None
    created_at: datetime
    updated_at: datetime


class VolunteerVettingStatusInput(BaseModel):
    status: Literal["approved", "rejected", "service_ended"]
    service_ended_at: date | None = None


class VolunteerVettingReviewInput(BaseModel):
    background_check_status: Literal["pending", "clear", "flagged"]
    references_checked: bool
    training_completed_at: date | None = None