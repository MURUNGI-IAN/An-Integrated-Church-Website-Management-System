from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32), default="admin")
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", name="fk_admin_users_branch_id_branches", use_alter=True),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), index=True)
    action: Mapped[str] = mapped_column(String(48))
    entity_type: Mapped[str] = mapped_column(String(48))
    entity_id: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InstitutionMissionRecord(Base):
    __tablename__ = "institution_mission_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    record_type: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SafeguardingReport(Base):
    __tablename__ = "safeguarding_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    involves_restricted_staff: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    serious_child_protection: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    retention_until: Mapped[date] = mapped_column(Date, index=True)
    external_referral_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    investigation_started_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    senior_resolution_approval_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    trustee_resolution_approval_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VolunteerVettingRecord(Base):
    __tablename__ = "volunteer_vetting_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    encrypted_details: Mapped[str] = mapped_column(Text)
    background_check_status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    references_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    training_completed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    service_started_at: Mapped[date] = mapped_column(Date)
    service_ended_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    retention_until: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SitePage(Base):
    __tablename__ = "site_pages"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ContentTranslation(Base):
    __tablename__ = "content_translations"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", "field", "language", name="uq_content_translation_target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(24), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    field: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8), index=True)
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="human")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SermonCaption(Base):
    __tablename__ = "sermon_captions"
    __table_args__ = (
        UniqueConstraint("sermon_id", "language", name="uq_sermon_caption_language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sermon_id: Mapped[int] = mapped_column(ForeignKey("sermons.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(8), index=True)
    file_format: Mapped[str] = mapped_column(String(8))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default="human")
    status: Mapped[str] = mapped_column(String(24), default="draft", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Sermon(Base):
    __tablename__ = "sermons"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    speaker: Mapped[str] = mapped_column(String(120))
    scripture: Mapped[str | None] = mapped_column(String(120), nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    media_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)


class ChurchEvent(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    registration_open: Mapped[bool] = mapped_column(Boolean, default=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    registrations: Mapped[list["EventRegistration"]] = relationship(back_populates="event", cascade="all, delete-orphan")


class EventRegistration(Base):
    __tablename__ = "event_registrations"
    __table_args__ = (UniqueConstraint("event_id", "email_digest", name="uq_event_registration_email_digest"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    email_digest: Mapped[str] = mapped_column(String(64))
    encrypted_payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    event: Mapped[ChurchEvent] = relationship(back_populates="registrations")


class PrayerRequest(Base):
    __tablename__ = "prayer_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContactInquiry(Base):
    __tablename__ = "contact_inquiries"

    id: Mapped[int] = mapped_column(primary_key=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VisitorVisit(Base):
    __tablename__ = "visitor_visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    encrypted_email: Mapped[str] = mapped_column(Text)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SmallGroup(Base):
    __tablename__ = "small_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    meeting_area: Mapped[str] = mapped_column(String(160))
    meeting_day: Mapped[str] = mapped_column(String(16))
    meeting_time: Mapped[str] = mapped_column(String(40))
    age_group: Mapped[str] = mapped_column(String(80), default="All ages")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class GroupWaitlist(Base):
    __tablename__ = "group_waitlist"
    __table_args__ = (UniqueConstraint("group_id", "contact_digest", name="uq_group_waitlist_contact"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("small_groups.id", ondelete="CASCADE"), index=True)
    contact_digest: Mapped[str] = mapped_column(String(64))
    encrypted_payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_digest: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    encrypted_profile: Mapped[str] = mapped_column(Text)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MemberCommunicationConsent(Base):
    __tablename__ = "member_communication_consents"
    __table_args__ = (UniqueConstraint("member_id", "channel", name="uq_member_communication_channel"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    is_consented: Mapped[bool] = mapped_column(Boolean, default=False)
    consent_source: Mapped[str] = mapped_column(String(32))
    delivery_frequency: Mapped[str] = mapped_column(String(24), default="essential_only", server_default="essential_only")
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default="21:00", server_default="21:00")
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default="07:00", server_default="07:00")
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Kampala", server_default="Africa/Kampala")
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MemberAttendance(Base):
    __tablename__ = "member_attendance"
    __table_args__ = (UniqueConstraint("member_id", "service_name", "service_date", name="uq_member_attendance_service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(120))
    service_date: Mapped[date] = mapped_column(Date)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    check_in_method: Mapped[str] = mapped_column(String(24))
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChildProfile(Base):
    __tablename__ = "child_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    primary_guardian_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    encrypted_profile: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ChildPickupAuthorization(Base):
    __tablename__ = "child_pickup_authorizations"
    __table_args__ = (UniqueConstraint("child_id", "member_id", name="uq_child_pickup_member"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("child_profiles.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)


class ChildAttendance(Base):
    __tablename__ = "child_attendance"
    __table_args__ = (UniqueConstraint("child_id", "service_name", "service_date", name="uq_child_attendance_service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("child_profiles.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(120))
    service_date: Mapped[date] = mapped_column(Date)
    checked_in_by_member_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    checked_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    checked_out_by_member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmergencyAlert(Base):
    __tablename__ = "emergency_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VolunteerAvailability(Base):
    __tablename__ = "volunteer_availability"
    __table_args__ = (UniqueConstraint("member_id", "service_name", "service_date", name="uq_volunteer_availability_service"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    service_name: Mapped[str] = mapped_column(String(120))
    service_date: Mapped[date] = mapped_column(Date, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AvailabilityInvite(Base):
    __tablename__ = "availability_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    service_name: Mapped[str] = mapped_column(String(120))
    service_date: Mapped[date] = mapped_column(Date)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RotaAssignment(Base):
    __tablename__ = "rota_assignments"
    __table_args__ = (
        UniqueConstraint("service_name", "service_date", "role_name", name="uq_rota_service_role"),
        UniqueConstraint("member_id", "service_name", "service_date", name="uq_rota_member_service"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    service_name: Mapped[str] = mapped_column(String(120))
    service_date: Mapped[date] = mapped_column(Date, index=True)
    role_name: Mapped[str] = mapped_column(String(120))
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FinanceEntry(Base):
    __tablename__ = "finance_entries"
    __table_args__ = (UniqueConstraint("correction_of_id", name="uq_finance_entry_correction"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_type: Mapped[str] = mapped_column(String(16), index=True)
    amount_ugx: Mapped[int] = mapped_column(Integer)
    fund: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    payment_method: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="recorded", index=True)
    encrypted_details: Mapped[str] = mapped_column(Text)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    correction_of_id: Mapped[int | None] = mapped_column(ForeignKey("finance_entries.id"), nullable=True, index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PayrollRecord(Base):
    __tablename__ = "payroll_records"
    __table_args__ = (
        UniqueConstraint("member_id", "period_start", "period_end", name="uq_payroll_member_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    salary_ugx: Mapped[int] = mapped_column(Integer)
    allowances_ugx: Mapped[int] = mapped_column(Integer, default=0)
    deductions_ugx: Mapped[int] = mapped_column(Integer, default=0)
    paye_ugx: Mapped[int] = mapped_column(Integer, default=0)
    nssf_ugx: Mapped[int] = mapped_column(Integer, default=0)
    gross_ugx: Mapped[int] = mapped_column(Integer)
    net_ugx: Mapped[int] = mapped_column(Integer)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    updated_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FinanceBudget(Base):
    __tablename__ = "finance_budgets"
    __table_args__ = (UniqueConstraint("fund", "category", "period_start", "period_end", name="uq_finance_budget_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fund: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    amount_ugx: Mapped[int] = mapped_column(Integer)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    period_start: Mapped[date] = mapped_column(Date, index=True)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FinancePledge(Base):
    __tablename__ = "finance_pledges"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign: Mapped[str] = mapped_column(String(160), index=True)
    amount_ugx: Mapped[int] = mapped_column(Integer)
    amount_fulfilled_ugx: Mapped[int] = mapped_column(Integer, default=0)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pledged", index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    encrypted_details: Mapped[str] = mapped_column(Text)
    recorded_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OfferingCountBatch(Base):
    __tablename__ = "offering_count_batches"
    __table_args__ = (UniqueConstraint("finance_entry_id", name="uq_offering_count_finance_entry"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    service_name: Mapped[str] = mapped_column(String(120))
    service_date: Mapped[date] = mapped_column(Date, index=True)
    fund: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    amount_counted_ugx: Mapped[int] = mapped_column(Integer)
    verified_amount_ugx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_amount_ugx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    counted_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    finance_entry_id: Mapped[int | None] = mapped_column(ForeignKey("finance_entries.id"), nullable=True, unique=True)
    encrypted_details: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PastoralCareTask(Base):
    __tablename__ = "pastoral_care_tasks"
    __table_args__ = (
        UniqueConstraint("member_id", "care_type", "attendance_alert_key", name="uq_pastoral_attendance_alert"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    care_type: Mapped[str] = mapped_column(String(48), index=True)
    priority: Mapped[str] = mapped_column(String(16), default="normal", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    attendance_alert_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    encrypted_details: Mapped[str] = mapped_column(Text)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CounselingAppointment(Base):
    __tablename__ = "counseling_appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    counselee_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    appointment_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    appointment_type: Mapped[str] = mapped_column(String(24), index=True)
    assigned_counselor_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"), index=True)
    assigned_counselor_role: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="booked", index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ChurchResource(Base):
    __tablename__ = "church_resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ResourceBooking(Base):
    __tablename__ = "resource_bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("church_resources.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    encrypted_details: Mapped[str] = mapped_column(Text)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StaffDocument(Base):
    __tablename__ = "staff_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_type: Mapped[str] = mapped_column(String(48), index=True)
    encrypted_payload: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MemberCertificate(Base):
    __tablename__ = "member_certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id"), index=True)
    certificate_type: Mapped[str] = mapped_column(String(80), index=True)
    issued_on: Mapped[date] = mapped_column(Date, index=True)
    certificate_number: Mapped[str] = mapped_column(String(80), unique=True)
    encrypted_details: Mapped[str] = mapped_column(Text)
    issued_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GovernanceMeeting(Base):
    __tablename__ = "governance_meetings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    meeting_date: Mapped[date] = mapped_column(Date, index=True)
    location: Mapped[str] = mapped_column(String(200), default="")
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="scheduled", index=True)
    encrypted_minutes: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class GovernanceResolution(Base):
    __tablename__ = "governance_resolutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("governance_meetings.id", ondelete="CASCADE"), index=True)
    encrypted_content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="proposed", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)