import base64
import binascii
import json
import math
import re
import secrets
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.certificate_pdf import render_certificate_pdf
from app.database import Base, engine, get_db
from app.models import AdminUser, AuditLog, AvailabilityInvite, Branch, ChildAttendance, ChildPickupAuthorization, ChildProfile, ChurchEvent, ChurchResource, ContactInquiry, EmergencyAlert, EventRegistration, FinanceBudget, FinanceEntry, FinancePledge, GovernanceMeeting, GovernanceResolution, GroupWaitlist, Member, MemberAttendance, MemberCertificate, MemberCommunicationConsent, NewsletterSubscriber, OfferingCountBatch, PastoralCareTask, PrayerRequest, ResourceBooking, RotaAssignment, Sermon, SitePage, SmallGroup, StaffDocument, VisitorVisit, VolunteerAvailability
from app.schemas import (
    EventInput,
    EventOutput,
    FinanceBudgetInput,
    FinanceBudgetOutput,
    FinanceEntryCorrectionInput,
    FinanceEntryInput,
    FinanceEntryOutput,
    FinancePledgeInput,
    FinancePledgeOutput,
    FinancePledgeStatusInput,
    FinanceReportOutput,
    GovernanceMeetingInput,
    GovernanceMeetingOutput,
    GovernanceResolutionInput,
    GovernanceResolutionOutput,
    GovernanceResolutionStatusInput,
    OfferingCountInput,
    OfferingCountOutput,
    OfferingCountResolutionInput,
    OfferingCountVerificationInput,
    ContactInput,
    ContactOutput,
    CommunicationConsentOutput,
    CommunicationConsentUpdate,
    EmergencyAlertInput,
    EmergencyAlertOutput,
    AnalyticsOverviewOutput,
    BranchInput,
    BranchOutput,
    GroupWaitlistInput,
    GroupWaitlistOutput,
    RotaAssignmentOutput,
    RotaGenerationInput,
    VolunteerAvailabilityInput,
    VolunteerAvailabilityOutput,
    AttendanceInput,
    AttendanceOutput,
    AvailabilityInviteDetails,
    AvailabilityInviteInput,
    AvailabilityInviteOutput,
    AvailabilityInviteToken,
    AvailabilityResponseInput,
    ChildAttendanceInput,
    ChildAttendanceOutput,
    ChildCheckoutInput,
    ChildOutput,
    ChildProfileInput,
    LoginInput,
    MemberCreateInput,
    MemberOutput,
    MemberProfileInput,
    NewsletterInput,
    PageInput,
    PageOutput,
    MemberCertificateInput,
    MemberCertificateOutput,
    PrayerInput,
    PrayerOutput,
    PastoralCareTaskInput,
    PastoralCareTaskOutput,
    PastoralCareTaskUpdate,
    RegistrationInput,
    ResourceBookingInput,
    ResourceBookingOutput,
    ResourceBookingStatusInput,
    ChurchResourceInput,
    ChurchResourceOutput,
    SermonInput,
    SermonOutput,
    SmallGroupInput,
    SmallGroupOutput,
    TokenOutput,
    StaffDocumentInput,
    StaffDocumentOutput,
    VisitorVisitInput,
    VisitorVisitOutput,
)
from app.security import create_access_token, decrypt_text, encrypt_text, hash_password, keyed_digest, require_roles, verify_password

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def create_app(database_engine=None) -> FastAPI:
    app_engine = database_engine or engine

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield

    app = FastAPI(
        title="Bwala Deliverance and Healing Ministries API",
        version="0.1.0",
        description="Public church information and authenticated staff workflows.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def db_session():
        with sessionmaker(bind=app_engine, autoflush=False, expire_on_commit=False)() as db:
            yield db

    app.dependency_overrides[get_db] = db_session
    editor = require_roles("admin", "editor")
    pastor = require_roles("admin", "pastor")
    contact_manager = require_roles("admin", "pastor")
    member_manager = require_roles("admin", "pastor")
    attendance_manager = require_roles("admin", "editor", "pastor")
    child_manager = require_roles("admin", "pastor")
    alert_manager = require_roles("admin", "pastor")
    volunteer_manager = require_roles("admin", "editor", "pastor")
    group_manager = require_roles("admin", "editor", "pastor")
    finance_manager = require_roles("admin", "treasurer")
    pastoral_manager = require_roles("admin", "pastor")
    resource_manager = require_roles("admin", "editor", "pastor")
    document_manager = require_roles("admin", "pastor")

    def record_audit(db: Session, actor: AdminUser, action: str, entity_type: str, entity_id: int) -> None:
        db.add(AuditLog(actor_id=actor.id, action=action, entity_type=entity_type, entity_id=entity_id))

    def active_member(db: Session, member_id: int) -> Member:
        member = db.get(Member, member_id)
        if member is None or member.status != "active":
            raise HTTPException(status_code=404, detail="Active member not found")
        return member

    def validate_branch_assignment(
        db: Session,
        branch_id: int | None,
        current_branch_id: int | None = None,
    ) -> int | None:
        if branch_id is None:
            return None
        branch = db.get(Branch, branch_id)
        if branch is None:
            raise HTTPException(status_code=404, detail="Branch not found")
        if not branch.is_active and branch_id != current_branch_id:
            raise HTTPException(status_code=422, detail="New records cannot be assigned to an inactive branch")
        return branch.id

    def child_profile_output(db: Session, child: ChildProfile) -> ChildOutput:
        pickup_ids = db.scalars(
            select(ChildPickupAuthorization.member_id)
            .where(ChildPickupAuthorization.child_id == child.id)
            .order_by(ChildPickupAuthorization.member_id)
        ).all()
        return ChildOutput(
            id=child.id,
            name=json.loads(decrypt_text(child.encrypted_profile))["name"],
            primary_guardian_id=child.primary_guardian_id,
            authorized_pickup_member_ids=list(pickup_ids),
            is_active=child.is_active,
            consented_at=child.consented_at,
            created_at=child.created_at,
            updated_at=child.updated_at,
        )

    def child_attendance_output(db: Session, attendance: ChildAttendance, child: ChildProfile) -> ChildAttendanceOutput:
        checked_in_member = db.get(Member, attendance.checked_in_by_member_id)
        checked_out_member = db.get(Member, attendance.checked_out_by_member_id) if attendance.checked_out_by_member_id else None
        return ChildAttendanceOutput(
            id=attendance.id,
            child_id=child.id,
            child_name=json.loads(decrypt_text(child.encrypted_profile))["name"],
            service_name=attendance.service_name,
            service_date=attendance.service_date,
            checked_in_by_member_id=attendance.checked_in_by_member_id,
            checked_in_by_name=json.loads(decrypt_text(checked_in_member.encrypted_profile))["name"],
            checked_in_at=attendance.checked_in_at,
            checked_out_by_member_id=attendance.checked_out_by_member_id,
            checked_out_by_name=(
                json.loads(decrypt_text(checked_out_member.encrypted_profile))["name"] if checked_out_member else None
            ),
            checked_out_at=attendance.checked_out_at,
        )

    def rota_assignment_output(assignment: RotaAssignment, member: Member) -> RotaAssignmentOutput:
        return RotaAssignmentOutput(
            id=assignment.id,
            member_id=member.id,
            member_name=json.loads(decrypt_text(member.encrypted_profile))["name"],
            service_name=assignment.service_name,
            service_date=assignment.service_date,
            role_name=assignment.role_name,
            created_at=assignment.created_at,
        )

    def group_output(group: SmallGroup, distance_km: float | None = None) -> SmallGroupOutput:
        return SmallGroupOutput(
            id=group.id,
            name=group.name,
            description=group.description,
            meeting_area=group.meeting_area,
            meeting_day=group.meeting_day,
            meeting_time=group.meeting_time,
            age_group=group.age_group,
            latitude=group.latitude,
            longitude=group.longitude,
            is_open=group.is_open,
            is_published=group.is_published,
            created_at=group.created_at,
            updated_at=group.updated_at,
            distance_km=distance_km,
        )

    def finance_entry_output(entry: FinanceEntry) -> FinanceEntryOutput:
        return FinanceEntryOutput(
            id=entry.id,
            entry_type=entry.entry_type,
            amount_ugx=entry.amount_ugx,
            fund=entry.fund,
            category=entry.category,
            entry_date=entry.entry_date,
            payment_method=entry.payment_method,
            status=entry.status,
            details=json.loads(decrypt_text(entry.encrypted_details))["details"],
            recorded_by_id=entry.recorded_by_id,
            reviewed_by_id=entry.reviewed_by_id,
            correction_of_id=entry.correction_of_id,
            created_at=entry.created_at,
            reviewed_at=entry.reviewed_at,
            branch_id=entry.branch_id,
        )

    def offering_count_output(batch: OfferingCountBatch) -> OfferingCountOutput:
        details = json.loads(decrypt_text(batch.encrypted_details))
        return OfferingCountOutput(
            id=batch.id,
            service_name=batch.service_name,
            service_date=batch.service_date,
            fund=batch.fund,
            category=batch.category,
            amount_counted_ugx=batch.amount_counted_ugx,
            verified_amount_ugx=batch.verified_amount_ugx,
            final_amount_ugx=batch.final_amount_ugx,
            status=batch.status,
            counted_by_id=batch.counted_by_id,
            verified_by_id=batch.verified_by_id,
            resolved_by_id=batch.resolved_by_id,
            finance_entry_id=batch.finance_entry_id,
            notes=details["notes"],
            created_at=batch.created_at,
            verified_at=batch.verified_at,
            resolved_at=batch.resolved_at,
            branch_id=batch.branch_id,
        )

    def finance_budget_output(db: Session, budget: FinanceBudget) -> FinanceBudgetOutput:
        spent = db.scalar(
            select(func.coalesce(func.sum(FinanceEntry.amount_ugx), 0)).where(
                FinanceEntry.entry_type == "expense",
                FinanceEntry.status == "approved",
                FinanceEntry.fund == budget.fund,
                FinanceEntry.category == budget.category,
                FinanceEntry.entry_date >= budget.period_start,
                FinanceEntry.entry_date <= budget.period_end,
                FinanceEntry.branch_id == budget.branch_id,
            )
        )
        return FinanceBudgetOutput(
            id=budget.id,
            fund=budget.fund,
            category=budget.category,
            amount_ugx=budget.amount_ugx,
            period_start=budget.period_start,
            period_end=budget.period_end,
            created_by_id=budget.created_by_id,
            created_at=budget.created_at,
            spent_ugx=spent or 0,
            branch_id=budget.branch_id,
        )

    def finance_pledge_output(pledge: FinancePledge) -> FinancePledgeOutput:
        details = json.loads(decrypt_text(pledge.encrypted_details))
        return FinancePledgeOutput(
            id=pledge.id,
            campaign=pledge.campaign,
            amount_ugx=pledge.amount_ugx,
            amount_fulfilled_ugx=pledge.amount_fulfilled_ugx,
            due_date=pledge.due_date,
            status=pledge.status,
            donor_name=details["donor_name"],
            donor_contact=details["donor_contact"],
            details=details["details"],
            recorded_by_id=pledge.recorded_by_id,
            created_at=pledge.created_at,
            branch_id=pledge.branch_id,
        )

    def pastoral_task_output(db: Session, task: PastoralCareTask) -> PastoralCareTaskOutput:
        member = db.get(Member, task.member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Member record not found")
        return PastoralCareTaskOutput(
            id=task.id,
            member_id=task.member_id,
            member_name=json.loads(decrypt_text(member.encrypted_profile))["name"],
            care_type=task.care_type,
            priority=task.priority,
            due_date=task.due_date,
            status=task.status,
            notes=json.loads(decrypt_text(task.encrypted_details))["notes"],
            assigned_to_id=task.assigned_to_id,
            created_by_id=task.created_by_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    def create_attendance_care_alerts(db: Session, actor: AdminUser, attendance_date: date) -> None:
        if attendance_date.weekday() != 6 or attendance_date > datetime.now(timezone.utc).date():
            return
        recorded_service_dates = db.scalars(
            select(MemberAttendance.service_date)
            .where(MemberAttendance.service_date <= attendance_date)
            .distinct()
            .order_by(MemberAttendance.service_date.desc())
        ).all()
        sunday_dates = [
            service_date for service_date in recorded_service_dates if service_date.weekday() == 6
        ][:3]
        if len(sunday_dates) < 3:
            return
        sunday_dates.sort()
        window_key = ",".join(service_date.isoformat() for service_date in sunday_dates)
        attendance_exists = (
            select(MemberAttendance.id)
            .where(
                MemberAttendance.member_id == Member.id,
                MemberAttendance.service_date.in_(sunday_dates),
            )
            .exists()
        )
        absent_members = db.scalars(
            select(Member).where(
                Member.status == "active",
                Member.created_at <= datetime.combine(sunday_dates[0], datetime.min.time(), tzinfo=timezone.utc),
                ~attendance_exists,
            )
        ).all()
        for absent_member in absent_members:
            existing = db.scalar(
                select(PastoralCareTask.id).where(
                    PastoralCareTask.member_id == absent_member.id,
                    PastoralCareTask.care_type == "attendance",
                    PastoralCareTask.attendance_alert_key == window_key,
                )
            )
            if existing is not None:
                continue
            task = PastoralCareTask(
                member_id=absent_member.id,
                care_type="attendance",
                priority="normal",
                due_date=attendance_date,
                status="open",
                attendance_alert_key=window_key,
                encrypted_details=encrypt_text(json.dumps({
                    "notes": f"No recorded attendance on {', '.join(day.isoformat() for day in sunday_dates)}. Please check in pastorally before drawing conclusions.",
                })),
                created_by_id=actor.id,
            )
            db.add(task)
            db.flush()
            record_audit(db, actor, "attendance_alert_created", "pastoral_care_task", task.id)

    def resource_booking_output(db: Session, booking: ResourceBooking) -> ResourceBookingOutput:
        resource = db.get(ChurchResource, booking.resource_id)
        if resource is None:
            raise HTTPException(status_code=404, detail="Church resource not found")
        return ResourceBookingOutput(
            id=booking.id,
            resource_id=booking.resource_id,
            resource_name=resource.name,
            starts_at=booking.starts_at.replace(tzinfo=timezone.utc) if booking.starts_at.tzinfo is None else booking.starts_at,
            ends_at=booking.ends_at.replace(tzinfo=timezone.utc) if booking.ends_at.tzinfo is None else booking.ends_at,
            status=booking.status,
            purpose=json.loads(decrypt_text(booking.encrypted_details))["purpose"],
            requested_by_id=booking.requested_by_id,
            reviewed_by_id=booking.reviewed_by_id,
            created_at=booking.created_at,
            reviewed_at=booking.reviewed_at,
        )

    def staff_document_output(document: StaffDocument) -> StaffDocumentOutput:
        payload = json.loads(decrypt_text(document.encrypted_payload))
        return StaffDocumentOutput(
            id=document.id,
            document_type=document.document_type,
            title=payload["title"],
            filename=payload["filename"],
            content_type=payload["content_type"],
            size_bytes=payload["size_bytes"],
            created_by_id=document.created_by_id,
            created_at=document.created_at,
        )

    def member_certificate_output(db: Session, certificate: MemberCertificate) -> MemberCertificateOutput:
        member = db.get(Member, certificate.member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Member record not found")
        return MemberCertificateOutput(
            id=certificate.id,
            member_id=certificate.member_id,
            member_name=json.loads(decrypt_text(member.encrypted_profile))["name"],
            certificate_type=certificate.certificate_type,
            issued_on=certificate.issued_on,
            certificate_number=certificate.certificate_number,
            details=json.loads(decrypt_text(certificate.encrypted_details))["details"],
            issued_by_id=certificate.issued_by_id,
            created_at=certificate.created_at,
        )

    def distance_between_km(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
        earth_radius_km = 6371.0
        latitude_delta = math.radians(latitude_b - latitude_a)
        longitude_delta = math.radians(longitude_b - longitude_a)
        haversine = (
            math.sin(latitude_delta / 2) ** 2
            + math.cos(math.radians(latitude_a))
            * math.cos(math.radians(latitude_b))
            * math.sin(longitude_delta / 2) ** 2
        )
        return earth_radius_km * 2 * math.asin(math.sqrt(haversine))

    def validate_pickup_members(db: Session, guardian_id: int, pickup_ids: list[int]) -> list[int]:
        unique_ids = list(dict.fromkeys(pickup_ids))
        unique_ids = [member_id for member_id in unique_ids if member_id != guardian_id]
        if unique_ids:
            active_ids = set(db.scalars(
                select(Member.id).where(Member.id.in_(unique_ids), Member.status == "active")
            ).all())
            if active_ids != set(unique_ids):
                raise HTTPException(status_code=422, detail="Every authorized pickup contact must be an active member")
        return unique_ids

    @app.get("/api/v1/health", tags=["system"])
    def health(db: Session = Depends(get_db)):
        db.execute(select(1))
        return {"status": "ok"}

    @app.get("/api/v1/alerts/current", response_model=list[EmergencyAlertOutput], tags=["alerts"])
    def list_current_alerts(db: Session = Depends(get_db)):
        now = datetime.now(timezone.utc)
        comparison_now = now.replace(tzinfo=None) if db.get_bind().dialect.name == "sqlite" else now
        return db.scalars(
            select(EmergencyAlert)
            .where(
                EmergencyAlert.is_active.is_(True),
                or_(EmergencyAlert.expires_at.is_(None), EmergencyAlert.expires_at > comparison_now),
            )
            .order_by(EmergencyAlert.created_at.desc())
        ).all()

    @app.get("/api/v1/admin/alerts", response_model=list[EmergencyAlertOutput], tags=["alerts"])
    def list_alerts(_: Annotated[AdminUser, Depends(alert_manager)], db: Session = Depends(get_db)):
        return db.scalars(select(EmergencyAlert).order_by(EmergencyAlert.created_at.desc()).limit(100)).all()

    @app.post("/api/v1/admin/alerts", response_model=EmergencyAlertOutput, status_code=201, tags=["alerts"])
    def create_alert(
        payload: EmergencyAlertInput,
        actor: Annotated[AdminUser, Depends(alert_manager)],
        db: Session = Depends(get_db),
    ):
        title = payload.title.strip()
        message = payload.message.strip()
        if not title or not message:
            raise HTTPException(status_code=422, detail="Alert title and message cannot be blank")
        if payload.expires_at and payload.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="Alert expiration must be in the future")
        alert = EmergencyAlert(
            title=title,
            message=message,
            expires_at=payload.expires_at,
            is_active=payload.is_active,
            created_by_id=actor.id,
        )
        db.add(alert)
        db.flush()
        record_audit(db, actor, "create", "emergency_alert", alert.id)
        db.commit()
        db.refresh(alert)
        return alert

    @app.put("/api/v1/admin/alerts/{alert_id}", response_model=EmergencyAlertOutput, tags=["alerts"])
    def update_alert(
        alert_id: int,
        payload: EmergencyAlertInput,
        actor: Annotated[AdminUser, Depends(alert_manager)],
        db: Session = Depends(get_db),
    ):
        alert = db.get(EmergencyAlert, alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        title = payload.title.strip()
        message = payload.message.strip()
        if not title or not message:
            raise HTTPException(status_code=422, detail="Alert title and message cannot be blank")
        if payload.expires_at and payload.expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="Alert expiration must be in the future")
        alert.title = title
        alert.message = message
        alert.expires_at = payload.expires_at
        alert.is_active = payload.is_active
        record_audit(db, actor, "update", "emergency_alert", alert.id)
        db.commit()
        db.refresh(alert)
        return alert

    @app.patch("/api/v1/admin/alerts/{alert_id}/status", tags=["alerts"])
    def update_alert_status(
        alert_id: int,
        new_status: str = Query(pattern="^(active|inactive)$"),
        actor: Annotated[AdminUser, Depends(alert_manager)] = None,
        db: Session = Depends(get_db),
    ):
        alert = db.get(EmergencyAlert, alert_id)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        if new_status == "active" and alert.expires_at:
            expires_at = alert.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                raise HTTPException(status_code=409, detail="Expired alert cannot be activated")
        alert.is_active = new_status == "active"
        record_audit(db, actor, "status_change", "emergency_alert", alert.id)
        db.commit()
        return {"id": alert.id, "is_active": alert.is_active}

    @app.get("/api/v1/pages", response_model=list[PageOutput], tags=["website"])
    def list_published_pages(db: Session = Depends(get_db)):
        return db.scalars(
            select(SitePage).where(SitePage.is_published.is_(True)).order_by(SitePage.title)
        ).all()

    @app.get("/api/v1/pages/{slug}", response_model=PageOutput, tags=["website"])
    def read_page(slug: str, db: Session = Depends(get_db)):
        page = db.scalar(select(SitePage).where(SitePage.slug == slug, SitePage.is_published.is_(True)))
        if page is None:
            raise HTTPException(status_code=404, detail="Page not found")
        return page

    @app.get("/api/v1/sermons", response_model=list[SermonOutput], tags=["sermons"])
    def list_sermons(
        q: str | None = Query(default=None, max_length=120),
        speaker: str | None = Query(default=None, max_length=120),
        scripture: str | None = Query(default=None, max_length=120),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        db: Session = Depends(get_db),
    ):
        query = select(Sermon).where(Sermon.is_published.is_(True))
        if q:
            term = f"%{q.strip()}%"
            query = query.where(or_(Sermon.title.ilike(term), Sermon.summary.ilike(term), Sermon.speaker.ilike(term), Sermon.scripture.ilike(term)))
        if speaker:
            query = query.where(Sermon.speaker.ilike(f"%{speaker.strip()}%"))
        if scripture:
            query = query.where(Sermon.scripture.ilike(f"%{scripture.strip()}%"))
        return db.scalars(query.order_by(Sermon.published_at.desc()).limit(limit).offset(offset)).all()

    @app.get("/api/v1/events", response_model=list[EventOutput], tags=["events"])
    def list_events(db: Session = Depends(get_db)):
        now = datetime.now(timezone.utc)
        comparison_now = now.replace(tzinfo=None) if db.get_bind().dialect.name == "sqlite" else now
        return db.scalars(
            select(ChurchEvent)
            .where(ChurchEvent.is_published.is_(True), ChurchEvent.starts_at >= comparison_now)
            .order_by(ChurchEvent.starts_at)
        ).all()

    @app.get("/api/v1/groups", response_model=list[SmallGroupOutput], tags=["groups"])
    def list_public_groups(
        q: str | None = Query(default=None, max_length=120),
        meeting_day: str | None = Query(default=None, pattern="^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$"),
        age_group: str | None = Query(default=None, max_length=80),
        open_only: bool = False,
        near_latitude: float | None = Query(default=None, ge=-90, le=90),
        near_longitude: float | None = Query(default=None, ge=-180, le=180),
        radius_km: float = Query(default=25, gt=0, le=100),
        limit: int = Query(default=50, ge=1, le=100),
        db: Session = Depends(get_db),
    ):
        if (near_latitude is None) != (near_longitude is None):
            raise HTTPException(status_code=422, detail="Both approximate location coordinates are required")
        query = select(SmallGroup).where(SmallGroup.is_published.is_(True))
        if open_only:
            query = query.where(SmallGroup.is_open.is_(True))
        if meeting_day:
            query = query.where(SmallGroup.meeting_day == meeting_day)
        if age_group:
            query = query.where(SmallGroup.age_group.ilike(f"%{age_group.strip()}%"))
        if q:
            search = f"%{q.strip()}%"
            query = query.where(or_(SmallGroup.name.ilike(search), SmallGroup.description.ilike(search), SmallGroup.meeting_area.ilike(search)))
        groups = db.scalars(query.order_by(SmallGroup.name).limit(500)).all()
        results = []
        for group in groups:
            distance_km = None
            if near_latitude is not None and group.latitude is not None and group.longitude is not None:
                distance_km = distance_between_km(near_latitude, near_longitude, group.latitude, group.longitude)
                if distance_km > radius_km:
                    continue
            results.append(group_output(group, distance_km))
        if near_latitude is not None:
            results.sort(key=lambda group: group.distance_km if group.distance_km is not None else float("inf"))
        return results[:limit]

    @app.post("/api/v1/groups/{group_id}/waitlist", status_code=201, tags=["groups"])
    def request_group_waitlist(group_id: int, payload: GroupWaitlistInput, db: Session = Depends(get_db)):
        group = db.get(SmallGroup, group_id)
        if group is None or not group.is_published:
            raise HTTPException(status_code=404, detail="Small group not found")
        if group.is_open:
            raise HTTPException(status_code=409, detail="This group is open; contact the church to ask about joining")
        if not payload.consent:
            raise HTTPException(status_code=422, detail="Consent is required to join a group waitlist")
        name = payload.name.strip()
        contact = payload.contact.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name cannot be blank")
        if "@" in contact:
            if not EMAIL_PATTERN.fullmatch(contact):
                raise HTTPException(status_code=422, detail="Enter a valid email address or phone number")
            contact = contact.lower()
        else:
            digits = re.sub(r"\D", "", contact)
            if not re.fullmatch(r"\+?[0-9][0-9 ()-]{5,38}", contact) or len(digits) < 7:
                raise HTTPException(status_code=422, detail="Enter a valid email address or phone number")
        request = GroupWaitlist(
            group_id=group.id,
            contact_digest=keyed_digest(contact, "group-waitlist-contact-v1"),
            encrypted_payload=encrypt_text(json.dumps({"name": name, "contact": contact})),
        )
        db.add(request)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="This contact is already on the group waitlist") from exc
        db.refresh(request)
        return {"id": request.id, "status": request.status}

    @app.get("/api/v1/admin/groups", response_model=list[SmallGroupOutput], tags=["groups"])
    def list_groups_for_staff(_: Annotated[AdminUser, Depends(group_manager)], db: Session = Depends(get_db)):
        groups = db.scalars(select(SmallGroup).order_by(SmallGroup.name)).all()
        return [group_output(group) for group in groups]

    @app.post("/api/v1/admin/groups", response_model=SmallGroupOutput, status_code=201, tags=["groups"])
    def create_small_group(
        payload: SmallGroupInput,
        actor: Annotated[AdminUser, Depends(group_manager)],
        db: Session = Depends(get_db),
    ):
        group = SmallGroup(**payload.model_dump(), updated_by_id=actor.id)
        db.add(group)
        db.flush()
        record_audit(db, actor, "create", "small_group", group.id)
        db.commit()
        db.refresh(group)
        return group_output(group)

    @app.put("/api/v1/admin/groups/{group_id}", response_model=SmallGroupOutput, tags=["groups"])
    def update_small_group(
        group_id: int,
        payload: SmallGroupInput,
        actor: Annotated[AdminUser, Depends(group_manager)],
        db: Session = Depends(get_db),
    ):
        group = db.get(SmallGroup, group_id)
        if group is None:
            raise HTTPException(status_code=404, detail="Small group not found")
        for field, value in payload.model_dump().items():
            setattr(group, field, value)
        group.updated_by_id = actor.id
        record_audit(db, actor, "update", "small_group", group.id)
        db.commit()
        db.refresh(group)
        return group_output(group)

    @app.get("/api/v1/admin/groups/{group_id}/waitlist", response_model=list[GroupWaitlistOutput], tags=["groups"])
    def list_group_waitlist(
        group_id: int,
        _: Annotated[AdminUser, Depends(child_manager)],
        db: Session = Depends(get_db),
    ):
        if db.get(SmallGroup, group_id) is None:
            raise HTTPException(status_code=404, detail="Small group not found")
        requests = db.scalars(select(GroupWaitlist).where(GroupWaitlist.group_id == group_id).order_by(GroupWaitlist.created_at)).all()
        return [
            GroupWaitlistOutput(id=request.id, status=request.status, consented_at=request.consented_at,
                                created_at=request.created_at, **json.loads(decrypt_text(request.encrypted_payload)))
            for request in requests
        ]

    @app.patch("/api/v1/admin/groups/{group_id}/waitlist/{request_id}/status", tags=["groups"])
    def update_group_waitlist_status(
        group_id: int,
        request_id: int,
        new_status: str = Query(pattern="^(new|contacted|placed|closed)$"),
        actor: Annotated[AdminUser, Depends(child_manager)] = None,
        db: Session = Depends(get_db),
    ):
        request = db.scalar(select(GroupWaitlist).where(GroupWaitlist.id == request_id, GroupWaitlist.group_id == group_id))
        if request is None:
            raise HTTPException(status_code=404, detail="Waitlist request not found")
        request.status = new_status
        record_audit(db, actor, "status_change", "group_waitlist", request.id)
        db.commit()
        return {"id": request.id, "status": request.status}

    @app.post("/api/v1/events/{event_id}/registrations", status_code=201, tags=["events"])
    def register_for_event(event_id: int, payload: RegistrationInput, db: Session = Depends(get_db)):
        email = payload.email.strip().lower()
        if not EMAIL_PATTERN.fullmatch(email):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        if not payload.consent:
            raise HTTPException(status_code=422, detail="Consent is required to register")
        event = db.scalar(select(ChurchEvent).where(ChurchEvent.id == event_id).with_for_update())
        now = datetime.now(timezone.utc)
        if event is None or not event.is_published:
            raise HTTPException(status_code=404, detail="Event not found")
        event_starts_at = event.starts_at
        if event_starts_at.tzinfo is None:
            event_starts_at = event_starts_at.replace(tzinfo=timezone.utc)
        if not event.registration_open or event_starts_at < now:
            raise HTTPException(status_code=409, detail="Registration is closed")
        email_digest = keyed_digest(email, "event-registration-email-v1")
        duplicate = db.scalar(select(EventRegistration.id).where(
            EventRegistration.event_id == event_id,
            EventRegistration.email_digest == email_digest,
        ))
        if duplicate:
            raise HTTPException(status_code=409, detail="This email is already registered for the event")
        registration_count = db.scalar(
            select(func.count()).select_from(EventRegistration).where(EventRegistration.event_id == event_id)
        ) or 0
        if event.capacity is not None and registration_count >= event.capacity:
            raise HTTPException(status_code=409, detail="This event is full")
        registration = EventRegistration(
            event_id=event_id,
            email_digest=email_digest,
            encrypted_payload=encrypt_text(json.dumps({"name": payload.name.strip(), "email": email})),
        )
        db.add(registration)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="This email is already registered for the event") from exc
        return {"id": registration.id, "event_title": event.title, "status": "registered"}

    @app.post("/api/v1/prayer-requests", status_code=201, tags=["prayer"])
    def submit_prayer_request(payload: PrayerInput, db: Session = Depends(get_db)):
        if not payload.consent:
            raise HTTPException(status_code=422, detail="Consent is required to submit a prayer request")
        encrypted = encrypt_text(json.dumps({
            "name": payload.name.strip() if payload.name else None,
            "contact": payload.contact.strip() if payload.contact else None,
            "message": payload.message.strip(),
        }))
        request = PrayerRequest(encrypted_payload=encrypted)
        db.add(request)
        db.commit()
        db.refresh(request)
        return {"id": request.id, "status": "received"}

    @app.post("/api/v1/contact", status_code=201, tags=["contact"])
    def submit_contact_inquiry(payload: ContactInput, db: Session = Depends(get_db)):
        if not payload.consent:
            raise HTTPException(status_code=422, detail="Consent is required to send a message")
        email = payload.email.strip().lower()
        if not EMAIL_PATTERN.fullmatch(email):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        inquiry = ContactInquiry(encrypted_payload=encrypt_text(json.dumps({
            "name": payload.name.strip(),
            "email": email,
            "subject": payload.subject.strip(),
            "message": payload.message.strip(),
        })))
        db.add(inquiry)
        db.commit()
        db.refresh(inquiry)
        return {"id": inquiry.id, "status": "received"}

    @app.post("/api/v1/visitors", status_code=201, tags=["visitors"])
    def submit_visitor_visit(payload: VisitorVisitInput, db: Session = Depends(get_db)):
        if not payload.consent:
            raise HTTPException(status_code=422, detail="Consent is required to request a visit follow-up")
        name = payload.name.strip()
        contact = payload.contact.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name cannot be blank")
        if "@" in contact:
            if not EMAIL_PATTERN.fullmatch(contact):
                raise HTTPException(status_code=422, detail="Enter a valid email address or phone number")
            contact = contact.lower()
        else:
            digits = re.sub(r"\D", "", contact)
            if not re.fullmatch(r"\+?[0-9][0-9 ()-]{5,38}", contact) or len(digits) < 7:
                raise HTTPException(status_code=422, detail="Enter a valid email address or phone number")
        request = VisitorVisit(encrypted_payload=encrypt_text(json.dumps({
            "name": name,
            "contact": contact,
            "visit_date": payload.visit_date.isoformat() if payload.visit_date else None,
        })))
        db.add(request)
        db.commit()
        db.refresh(request)
        return {"id": request.id, "status": "received"}

    @app.get("/api/v1/admin/visitors", response_model=list[VisitorVisitOutput], tags=["visitors"])
    def list_visitor_visits(_: Annotated[AdminUser, Depends(contact_manager)], db: Session = Depends(get_db)):
        visits = db.scalars(select(VisitorVisit).order_by(VisitorVisit.created_at.desc()).limit(100)).all()
        return [
            VisitorVisitOutput(id=visit.id, status=visit.status, consented_at=visit.consented_at,
                               created_at=visit.created_at, **json.loads(decrypt_text(visit.encrypted_payload)))
            for visit in visits
        ]

    @app.patch("/api/v1/admin/visitors/{visit_id}/status", tags=["visitors"])
    def update_visitor_status(
        visit_id: int,
        new_status: str = Query(pattern="^(new|contacted|closed)$"),
        actor: Annotated[AdminUser, Depends(contact_manager)] = None,
        db: Session = Depends(get_db),
    ):
        visit = db.get(VisitorVisit, visit_id)
        if visit is None:
            raise HTTPException(status_code=404, detail="Visitor request not found")
        visit.status = new_status
        record_audit(db, actor, "status_change", "visitor_visit", visit.id)
        db.commit()
        return {"id": visit.id, "status": visit.status}

    @app.post("/api/v1/newsletter", status_code=201, tags=["newsletter"])
    def subscribe_newsletter(payload: NewsletterInput, db: Session = Depends(get_db)):
        email = payload.email.strip().lower()
        if not EMAIL_PATTERN.fullmatch(email):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        if not payload.consent:
            raise HTTPException(status_code=422, detail="Consent is required to subscribe")
        digest = keyed_digest(email, "newsletter-email-v1")
        subscriber = db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email_digest == digest))
        if subscriber:
            subscriber.is_active = True
        else:
            db.add(NewsletterSubscriber(email_digest=digest, encrypted_email=encrypt_text(email)))
        db.commit()
        return {"status": "subscribed"}

    @app.get("/api/v1/giving/status", tags=["giving"])
    def giving_status():
        return {"available": False, "message": "Online giving is not configured. Contact the church to arrange giving."}

    @app.post("/api/v1/auth/token", response_model=TokenOutput, tags=["staff"])
    def login(payload: LoginInput, db: Session = Depends(get_db)):
        email = payload.email.strip().lower()
        user = db.scalar(select(AdminUser).where(AdminUser.email == email))
        if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Email or password is incorrect", headers={"WWW-Authenticate": "Bearer"})
        return TokenOutput(access_token=create_access_token(user))

    @app.get("/api/v1/auth/me", tags=["staff"])
    def current_staff(actor: Annotated[AdminUser, Depends(require_roles("admin", "editor", "pastor", "treasurer"))]):
        return {"id": actor.id, "email": actor.email, "display_name": actor.display_name, "role": actor.role}

    @app.post("/api/v1/admin/pages", response_model=PageOutput, status_code=201, tags=["staff CMS"])
    def create_page(payload: PageInput, actor: Annotated[AdminUser, Depends(editor)], db: Session = Depends(get_db)):
        page = SitePage(**payload.model_dump())
        db.add(page)
        db.flush()
        record_audit(db, actor, "create", "page", page.id)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A page with this slug already exists") from exc
        db.refresh(page)
        return page

    @app.put("/api/v1/admin/pages/{page_id}", response_model=PageOutput, tags=["staff CMS"])
    def update_page(page_id: int, payload: PageInput, actor: Annotated[AdminUser, Depends(editor)], db: Session = Depends(get_db)):
        page = db.get(SitePage, page_id)
        if page is None:
            raise HTTPException(status_code=404, detail="Page not found")
        for field, value in payload.model_dump().items():
            setattr(page, field, value)
        record_audit(db, actor, "update", "page", page.id)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A page with this slug already exists") from exc
        db.refresh(page)
        return page

    @app.post("/api/v1/admin/sermons", response_model=SermonOutput, status_code=201, tags=["staff CMS"])
    def create_sermon(payload: SermonInput, actor: Annotated[AdminUser, Depends(editor)], db: Session = Depends(get_db)):
        sermon = Sermon(**payload.model_dump())
        db.add(sermon)
        db.flush()
        record_audit(db, actor, "create", "sermon", sermon.id)
        db.commit()
        db.refresh(sermon)
        return sermon

    @app.post("/api/v1/admin/events", response_model=EventOutput, status_code=201, tags=["staff CMS"])
    def create_event(payload: EventInput, actor: Annotated[AdminUser, Depends(editor)], db: Session = Depends(get_db)):
        values = payload.model_dump()
        values["branch_id"] = validate_branch_assignment(db, payload.branch_id)
        event = ChurchEvent(**values)
        db.add(event)
        db.flush()
        record_audit(db, actor, "create", "event", event.id)
        db.commit()
        db.refresh(event)
        return event

    @app.get("/api/v1/admin/prayer-requests", response_model=list[PrayerOutput], tags=["pastoral care"])
    def list_prayer_requests(_: Annotated[AdminUser, Depends(pastor)], db: Session = Depends(get_db)):
        requests = db.scalars(select(PrayerRequest).order_by(PrayerRequest.created_at.desc()).limit(100)).all()
        results = []
        for request in requests:
            private_data = json.loads(decrypt_text(request.encrypted_payload))
            results.append(PrayerOutput(id=request.id, status=request.status, created_at=request.created_at, **private_data))
        return results

    @app.patch("/api/v1/admin/prayer-requests/{request_id}/status", tags=["pastoral care"])
    def update_prayer_status(
        request_id: int,
        new_status: str = Query(pattern="^(new|follow_up|closed)$"),
        actor: Annotated[AdminUser, Depends(pastor)] = None,
        db: Session = Depends(get_db),
    ):
        request = db.get(PrayerRequest, request_id)
        if request is None:
            raise HTTPException(status_code=404, detail="Prayer request not found")
        request.status = new_status
        record_audit(db, actor, "status_change", "prayer_request", request.id)
        db.commit()
        return {"id": request.id, "status": request.status}

    @app.get("/api/v1/admin/contact-inquiries", response_model=list[ContactOutput], tags=["contact"])
    def list_contact_inquiries(_: Annotated[AdminUser, Depends(contact_manager)], db: Session = Depends(get_db)):
        inquiries = db.scalars(select(ContactInquiry).order_by(ContactInquiry.created_at.desc()).limit(100)).all()
        return [
            ContactOutput(id=inquiry.id, status=inquiry.status, created_at=inquiry.created_at,
                          **json.loads(decrypt_text(inquiry.encrypted_payload)))
            for inquiry in inquiries
        ]

    @app.patch("/api/v1/admin/contact-inquiries/{inquiry_id}/status", tags=["contact"])
    def update_contact_status(
        inquiry_id: int,
        new_status: str = Query(pattern="^(new|follow_up|closed)$"),
        actor: Annotated[AdminUser, Depends(contact_manager)] = None,
        db: Session = Depends(get_db),
    ):
        inquiry = db.get(ContactInquiry, inquiry_id)
        if inquiry is None:
            raise HTTPException(status_code=404, detail="Contact inquiry not found")
        inquiry.status = new_status
        record_audit(db, actor, "status_change", "contact_inquiry", inquiry.id)
        db.commit()
        return {"id": inquiry.id, "status": inquiry.status}

    @app.get("/api/v1/admin/pages", response_model=list[PageOutput], tags=["staff CMS"])
    def list_pages(_: Annotated[AdminUser, Depends(editor)], db: Session = Depends(get_db)):
        return db.scalars(select(SitePage).order_by(SitePage.slug)).all()

    @app.get("/api/v1/admin/sermons", response_model=list[SermonOutput], tags=["staff CMS"])
    def list_all_sermons(_: Annotated[AdminUser, Depends(editor)], db: Session = Depends(get_db)):
        return db.scalars(select(Sermon).order_by(Sermon.published_at.desc())).all()

    @app.put("/api/v1/admin/sermons/{sermon_id}", response_model=SermonOutput, tags=["staff CMS"])
    def update_sermon(
        sermon_id: int,
        payload: SermonInput,
        actor: Annotated[AdminUser, Depends(editor)],
        db: Session = Depends(get_db),
    ):
        sermon = db.get(Sermon, sermon_id)
        if sermon is None:
            raise HTTPException(status_code=404, detail="Sermon not found")
        for field, value in payload.model_dump().items():
            setattr(sermon, field, value)
        record_audit(db, actor, "update", "sermon", sermon.id)
        db.commit()
        db.refresh(sermon)
        return sermon

    @app.get("/api/v1/admin/events", response_model=list[EventOutput], tags=["staff CMS"])
    def list_all_events(
        _: Annotated[AdminUser, Depends(editor)],
        branch_id: int | None = None,
        db: Session = Depends(get_db),
    ):
        query = select(ChurchEvent)
        if branch_id is not None:
            query = query.where(ChurchEvent.branch_id == branch_id)
        return db.scalars(query.order_by(ChurchEvent.starts_at.desc())).all()

    @app.put("/api/v1/admin/events/{event_id}", response_model=EventOutput, tags=["staff CMS"])
    def update_event(
        event_id: int,
        payload: EventInput,
        actor: Annotated[AdminUser, Depends(editor)],
        db: Session = Depends(get_db),
    ):
        event = db.get(ChurchEvent, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        values = payload.model_dump()
        values["branch_id"] = validate_branch_assignment(db, payload.branch_id, event.branch_id)
        for field, value in values.items():
            setattr(event, field, value)
        record_audit(db, actor, "update", "event", event.id)
        db.commit()
        db.refresh(event)
        return event

    @app.get("/api/v1/admin/events/{event_id}/registrations", tags=["staff CMS"])
    def list_event_registrations(event_id: int, _: Annotated[AdminUser, Depends(editor)], db: Session = Depends(get_db)):
        event = db.get(ChurchEvent, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        registrations = db.scalars(
            select(EventRegistration).where(EventRegistration.event_id == event_id).order_by(EventRegistration.created_at)
        ).all()
        return [
            {"id": item.id, "created_at": item.created_at, **json.loads(decrypt_text(item.encrypted_payload))}
            for item in registrations
        ]

    @app.get("/api/v1/admin/audit-logs", tags=["staff"])
    def list_audit_logs(_: Annotated[AdminUser, Depends(require_roles("admin"))], db: Session = Depends(get_db)):
        records = db.scalars(select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(100)).all()
        return [
            {"id": item.id, "actor_id": item.actor_id, "action": item.action, "entity_type": item.entity_type,
             "entity_id": item.entity_id, "occurred_at": item.occurred_at}
            for item in records
        ]

    @app.post(
        "/api/v1/admin/branches",
        response_model=BranchOutput,
        status_code=201,
        tags=["branches"],
    )
    def create_branch(
        payload: BranchInput,
        actor: Annotated[AdminUser, Depends(require_roles("admin"))],
        db: Session = Depends(get_db),
    ):
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Branch name cannot be blank")
        branch = Branch(
            name=name,
            location=payload.location.strip(),
            is_active=payload.is_active,
            created_by_id=actor.id,
        )
        db.add(branch)
        try:
            db.flush()
            record_audit(db, actor, "create", "branch", branch.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A branch with that name already exists") from exc
        db.refresh(branch)
        return branch

    @app.get(
        "/api/v1/admin/branches",
        response_model=list[BranchOutput],
        tags=["branches"],
    )
    def list_branches(
        _: Annotated[AdminUser, Depends(require_roles("admin", "pastor", "editor", "treasurer"))],
        include_inactive: bool = False,
        db: Session = Depends(get_db),
    ):
        query = select(Branch)
        if not include_inactive:
            query = query.where(Branch.is_active.is_(True))
        return db.scalars(query.order_by(Branch.name, Branch.id)).all()

    @app.put(
        "/api/v1/admin/branches/{branch_id}",
        response_model=BranchOutput,
        tags=["branches"],
    )
    def update_branch(
        branch_id: int,
        payload: BranchInput,
        actor: Annotated[AdminUser, Depends(require_roles("admin"))],
        db: Session = Depends(get_db),
    ):
        branch = db.get(Branch, branch_id)
        if branch is None:
            raise HTTPException(status_code=404, detail="Branch not found")
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Branch name cannot be blank")
        branch.name = name
        branch.location = payload.location.strip()
        branch.is_active = payload.is_active
        try:
            record_audit(db, actor, "update", "branch", branch.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A branch with that name already exists") from exc
        db.refresh(branch)
        return branch

    @app.get(
        "/api/v1/admin/analytics/overview",
        response_model=AnalyticsOverviewOutput,
        tags=["analytics"],
    )
    def analytics_overview(
        _: Annotated[AdminUser, Depends(pastoral_manager)],
        period_start: date | None = None,
        period_end: date | None = None,
        branch_id: int | None = None,
        db: Session = Depends(get_db),
    ):
        today = datetime.now(timezone.utc).date()
        end_date = period_end or today
        start_date = period_start or (end_date - timedelta(days=29))
        if start_date > end_date:
            raise HTTPException(status_code=422, detail="Period start must be on or before period end")
        if (end_date - start_date).days > 365:
            raise HTTPException(status_code=422, detail="Analytics period cannot exceed 366 days")
        start_at = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_at = datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        members_query = select(func.count()).select_from(Member).where(Member.status == "active")
        attendance_query = select(func.count()).select_from(MemberAttendance).where(
            MemberAttendance.service_date >= start_date,
            MemberAttendance.service_date <= end_date,
        )
        attendees_query = select(func.count(func.distinct(MemberAttendance.member_id))).where(
            MemberAttendance.service_date >= start_date,
            MemberAttendance.service_date <= end_date,
        )
        service_days_query = select(func.count(func.distinct(MemberAttendance.service_date))).where(
            MemberAttendance.service_date >= start_date,
            MemberAttendance.service_date <= end_date,
        )
        events_query = select(func.count()).select_from(ChurchEvent).where(
            ChurchEvent.is_published.is_(True),
            ChurchEvent.starts_at >= start_at,
            ChurchEvent.starts_at < end_at,
        )
        registrations_query = (
            select(func.count())
            .select_from(EventRegistration)
            .join(ChurchEvent, ChurchEvent.id == EventRegistration.event_id)
            .where(
                ChurchEvent.is_published.is_(True),
                ChurchEvent.starts_at >= start_at,
                ChurchEvent.starts_at < end_at,
            )
        )
        governance_query = (
            select(func.count())
            .select_from(GovernanceResolution)
            .join(GovernanceMeeting, GovernanceMeeting.id == GovernanceResolution.meeting_id)
            .where(GovernanceResolution.status.in_(("approved", "in_progress")))
        )
        if branch_id is not None:
            members_query = members_query.where(Member.branch_id == branch_id)
            attendance_query = attendance_query.where(MemberAttendance.branch_id == branch_id)
            attendees_query = attendees_query.where(MemberAttendance.branch_id == branch_id)
            service_days_query = service_days_query.where(MemberAttendance.branch_id == branch_id)
            events_query = events_query.where(ChurchEvent.branch_id == branch_id)
            registrations_query = registrations_query.where(ChurchEvent.branch_id == branch_id)
            governance_query = governance_query.where(GovernanceMeeting.branch_id == branch_id)

        return AnalyticsOverviewOutput(
            period_start=start_date,
            period_end=end_date,
            active_members=db.scalar(members_query) or 0,
            attendance_check_ins=db.scalar(attendance_query) or 0,
            distinct_attendees=db.scalar(attendees_query) or 0,
            service_days_recorded=db.scalar(service_days_query) or 0,
            visitor_requests=db.scalar(
                select(func.count()).select_from(VisitorVisit).where(
                    VisitorVisit.created_at >= start_at,
                    VisitorVisit.created_at < end_at,
                )
            ) or 0,
            new_visitor_follow_ups=db.scalar(
                select(func.count()).select_from(VisitorVisit).where(
                    VisitorVisit.status == "new",
                    VisitorVisit.created_at >= start_at,
                    VisitorVisit.created_at < end_at,
                )
            ) or 0,
            published_events=db.scalar(events_query) or 0,
            event_registrations=db.scalar(registrations_query) or 0,
            published_small_groups=db.scalar(
                select(func.count()).select_from(SmallGroup).where(SmallGroup.is_published.is_(True))
            ) or 0,
            open_governance_actions=db.scalar(governance_query) or 0,
        )

    @app.post("/api/v1/admin/members", response_model=MemberOutput, status_code=201, tags=["members"])
    def create_member(
        payload: MemberCreateInput,
        actor: Annotated[AdminUser, Depends(member_manager)],
        db: Session = Depends(get_db),
    ):
        if not payload.consent_confirmed:
            raise HTTPException(status_code=422, detail="Consent is required to create a member record")
        profile = {
            "name": payload.name.strip(),
            "email": payload.email.strip().lower() if payload.email else None,
            "phone": payload.phone.strip() if payload.phone else None,
        }
        if not profile["name"]:
            raise HTTPException(status_code=422, detail="Member name cannot be blank")
        email = profile["email"]
        if email and not EMAIL_PATTERN.fullmatch(email):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        member = Member(
            email_digest=keyed_digest(email, "member-email-v1") if email else None,
            encrypted_profile=encrypt_text(json.dumps(profile)),
            status="active",
            branch_id=validate_branch_assignment(db, payload.branch_id),
        )
        db.add(member)
        try:
            db.flush()
            record_audit(db, actor, "create", "member", member.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A member with this email already exists") from exc
        db.refresh(member)
        return MemberOutput(id=member.id, status=member.status, consented_at=member.consented_at,
                            created_at=member.created_at, updated_at=member.updated_at,
                            branch_id=member.branch_id, **profile)

    @app.get("/api/v1/admin/members", response_model=list[MemberOutput], tags=["members"])
    def list_members(
        status: str = Query(default="active", pattern="^(active|inactive|all)$"),
        branch_id: int | None = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        _: Annotated[AdminUser, Depends(member_manager)] = None,
        db: Session = Depends(get_db),
    ):
        query = select(Member)
        if status != "all":
            query = query.where(Member.status == status)
        if branch_id is not None:
            query = query.where(Member.branch_id == branch_id)
        members = db.scalars(query.order_by(Member.created_at.desc()).limit(limit).offset(offset)).all()
        return [
            MemberOutput(
                id=member.id,
                status=member.status,
                consented_at=member.consented_at,
                created_at=member.created_at,
                updated_at=member.updated_at,
                branch_id=member.branch_id,
                **json.loads(decrypt_text(member.encrypted_profile)),
            )
            for member in members
        ]

    @app.get("/api/v1/admin/members/{member_id}", response_model=MemberOutput, tags=["members"])
    def read_member(
        member_id: int,
        _: Annotated[AdminUser, Depends(member_manager)],
        db: Session = Depends(get_db),
    ):
        member = db.get(Member, member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")
        return MemberOutput(
            id=member.id,
            status=member.status,
            consented_at=member.consented_at,
            created_at=member.created_at,
            updated_at=member.updated_at,
            branch_id=member.branch_id,
            **json.loads(decrypt_text(member.encrypted_profile)),
        )

    @app.put("/api/v1/admin/members/{member_id}", response_model=MemberOutput, tags=["members"])
    def update_member(
        member_id: int,
        payload: MemberProfileInput,
        actor: Annotated[AdminUser, Depends(member_manager)],
        db: Session = Depends(get_db),
    ):
        member = db.get(Member, member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")
        profile = {
            "name": payload.name.strip(),
            "email": payload.email.strip().lower() if payload.email else None,
            "phone": payload.phone.strip() if payload.phone else None,
        }
        if not profile["name"]:
            raise HTTPException(status_code=422, detail="Member name cannot be blank")
        member.branch_id = validate_branch_assignment(db, payload.branch_id, member.branch_id)
        email = profile["email"]
        if email and not EMAIL_PATTERN.fullmatch(email):
            raise HTTPException(status_code=422, detail="Enter a valid email address")
        member.email_digest = keyed_digest(email, "member-email-v1") if email else None
        member.encrypted_profile = encrypt_text(json.dumps(profile))
        record_audit(db, actor, "update", "member", member.id)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A member with this email already exists") from exc
        db.refresh(member)
        return MemberOutput(id=member.id, status=member.status, consented_at=member.consented_at,
                            created_at=member.created_at, updated_at=member.updated_at,
                            branch_id=member.branch_id, **profile)

    @app.patch("/api/v1/admin/members/{member_id}/status", tags=["members"])
    def update_member_status(
        member_id: int,
        new_status: str = Query(pattern="^(active|inactive)$"),
        actor: Annotated[AdminUser, Depends(member_manager)] = None,
        db: Session = Depends(get_db),
    ):
        member = db.get(Member, member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")
        member.status = new_status
        record_audit(db, actor, "status_change", "member", member.id)
        db.commit()
        return {"id": member.id, "status": member.status}

    @app.get("/api/v1/admin/members/{member_id}/communication-consents", response_model=list[CommunicationConsentOutput], tags=["communications"])
    def get_member_communication_consents(
        member_id: int,
        _: Annotated[AdminUser, Depends(member_manager)],
        db: Session = Depends(get_db),
    ):
        if db.get(Member, member_id) is None:
            raise HTTPException(status_code=404, detail="Member not found")
        records = db.scalars(
            select(MemberCommunicationConsent)
            .where(MemberCommunicationConsent.member_id == member_id)
            .order_by(MemberCommunicationConsent.channel)
        ).all()
        by_channel = {record.channel: record for record in records}
        return [
            CommunicationConsentOutput(
                channel=channel,
                is_consented=by_channel[channel].is_consented if channel in by_channel else False,
                consent_source=by_channel[channel].consent_source if channel in by_channel else "not_provided",
                consented_at=by_channel[channel].consented_at if channel in by_channel else None,
                updated_at=by_channel[channel].updated_at if channel in by_channel else None,
            )
            for channel in ("email", "sms")
        ]

    @app.put("/api/v1/admin/members/{member_id}/communication-consents", response_model=list[CommunicationConsentOutput], tags=["communications"])
    def update_member_communication_consents(
        member_id: int,
        payload: CommunicationConsentUpdate,
        actor: Annotated[AdminUser, Depends(member_manager)],
        db: Session = Depends(get_db),
    ):
        member = db.get(Member, member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")
        profile = json.loads(decrypt_text(member.encrypted_profile))
        now = datetime.now(timezone.utc)
        updated = []
        for preference in payload.preferences:
            if preference.is_consented:
                if preference.consent_source in {"member_request", "not_provided"}:
                    raise HTTPException(status_code=422, detail="An affirmative consent source is required to opt in")
                contact_field = "email" if preference.channel == "email" else "phone"
                if not profile.get(contact_field):
                    raise HTTPException(status_code=422, detail=f"A {contact_field} address is required for {preference.channel} consent")
            record = db.scalar(select(MemberCommunicationConsent).where(
                MemberCommunicationConsent.member_id == member.id,
                MemberCommunicationConsent.channel == preference.channel,
            ))
            if record is None:
                record = MemberCommunicationConsent(
                    member_id=member.id,
                    channel=preference.channel,
                    is_consented=preference.is_consented,
                    consent_source=preference.consent_source,
                    consented_at=now if preference.is_consented else None,
                    updated_by_id=actor.id,
                )
                db.add(record)
            else:
                record.is_consented = preference.is_consented
                record.consent_source = preference.consent_source
                record.consented_at = now if preference.is_consented else None
                record.updated_by_id = actor.id
                record.updated_at = now
            updated.append(record)
        record_audit(db, actor, "communication_consent_update", "member", member.id)
        db.commit()
        for record in updated:
            db.refresh(record)
        return [
            CommunicationConsentOutput(
                channel=record.channel,
                is_consented=record.is_consented,
                consent_source=record.consent_source,
                consented_at=record.consented_at,
                updated_at=record.updated_at,
            )
            for record in sorted(updated, key=lambda item: item.channel)
        ]

    @app.get("/api/v1/admin/attendance/members", tags=["attendance"])
    def list_attendance_members(
        _: Annotated[AdminUser, Depends(attendance_manager)],
        db: Session = Depends(get_db),
    ):
        members = db.scalars(
            select(Member).where(Member.status == "active").order_by(Member.created_at.desc()).limit(500)
        ).all()
        return [
            {"id": member.id, "name": json.loads(decrypt_text(member.encrypted_profile))["name"]}
            for member in members
        ]

    @app.post("/api/v1/admin/attendance", response_model=AttendanceOutput, status_code=201, tags=["attendance"])
    def check_in_member(
        payload: AttendanceInput,
        actor: Annotated[AdminUser, Depends(attendance_manager)],
        db: Session = Depends(get_db),
    ):
        member = db.get(Member, payload.member_id)
        if member is None or member.status != "active":
            raise HTTPException(status_code=404, detail="Active member not found")
        service_name = payload.service_name.strip()
        if not service_name:
            raise HTTPException(status_code=422, detail="Service name cannot be blank")
        attendance = MemberAttendance(
            member_id=member.id,
            service_name=service_name,
            service_date=payload.service_date,
            check_in_method=payload.check_in_method,
            branch_id=validate_branch_assignment(db, payload.branch_id),
        )
        db.add(attendance)
        try:
            db.flush()
            record_audit(db, actor, "check_in", "member_attendance", attendance.id)
            create_attendance_care_alerts(db, actor, payload.service_date)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Member is already checked in for this service and date") from exc
        db.refresh(attendance)
        profile = json.loads(decrypt_text(member.encrypted_profile))
        return AttendanceOutput(
            id=attendance.id,
            member_id=member.id,
            member_name=profile["name"],
            service_name=attendance.service_name,
            service_date=attendance.service_date,
            check_in_method=attendance.check_in_method,
            checked_in_at=attendance.checked_in_at,
            checked_out_at=attendance.checked_out_at,
            branch_id=attendance.branch_id,
        )

    @app.get("/api/v1/admin/attendance", response_model=list[AttendanceOutput], tags=["attendance"])
    def list_member_attendance(
        service_date: date,
        _: Annotated[AdminUser, Depends(attendance_manager)],
        branch_id: int | None = None,
        db: Session = Depends(get_db),
    ):
        query = (
            select(MemberAttendance, Member)
            .join(Member, Member.id == MemberAttendance.member_id)
            .where(MemberAttendance.service_date == service_date)
        )
        if branch_id is not None:
            query = query.where(MemberAttendance.branch_id == branch_id)
        records = db.execute(query.order_by(MemberAttendance.checked_in_at)).all()
        return [
            AttendanceOutput(
                id=attendance.id,
                member_id=member.id,
                member_name=json.loads(decrypt_text(member.encrypted_profile))["name"],
                service_name=attendance.service_name,
                service_date=attendance.service_date,
                check_in_method=attendance.check_in_method,
                checked_in_at=attendance.checked_in_at,
                checked_out_at=attendance.checked_out_at,
                branch_id=attendance.branch_id,
            )
            for attendance, member in records
        ]

    @app.patch("/api/v1/admin/attendance/{attendance_id}/check-out", response_model=AttendanceOutput, tags=["attendance"])
    def check_out_member(
        attendance_id: int,
        actor: Annotated[AdminUser, Depends(attendance_manager)],
        db: Session = Depends(get_db),
    ):
        attendance = db.get(MemberAttendance, attendance_id)
        if attendance is None:
            raise HTTPException(status_code=404, detail="Attendance record not found")
        member = db.get(Member, attendance.member_id)
        if member is None:
            raise HTTPException(status_code=404, detail="Member not found")
        if attendance.checked_out_at is None:
            attendance.checked_out_at = datetime.now(timezone.utc)
            record_audit(db, actor, "check_out", "member_attendance", attendance.id)
            db.commit()
            db.refresh(attendance)
        profile = json.loads(decrypt_text(member.encrypted_profile))
        return AttendanceOutput(
            id=attendance.id,
            member_id=member.id,
            member_name=profile["name"],
            service_name=attendance.service_name,
            service_date=attendance.service_date,
            check_in_method=attendance.check_in_method,
            checked_in_at=attendance.checked_in_at,
            checked_out_at=attendance.checked_out_at,
        )

    @app.post("/api/v1/admin/children", response_model=ChildOutput, status_code=201, tags=["safeguarding"])
    def create_child(
        payload: ChildProfileInput,
        actor: Annotated[AdminUser, Depends(child_manager)],
        db: Session = Depends(get_db),
    ):
        if not payload.consent_confirmed:
            raise HTTPException(status_code=422, detail="Guardian consent is required to register a child")
        guardian = active_member(db, payload.primary_guardian_id)
        pickup_ids = validate_pickup_members(db, guardian.id, payload.authorized_pickup_member_ids)
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Child name cannot be blank")
        child = ChildProfile(
            primary_guardian_id=guardian.id,
            encrypted_profile=encrypt_text(json.dumps({"name": name})),
            is_active=True,
        )
        db.add(child)
        db.flush()
        db.add_all([
            ChildPickupAuthorization(child_id=child.id, member_id=member_id)
            for member_id in pickup_ids
        ])
        record_audit(db, actor, "create", "child_profile", child.id)
        db.commit()
        db.refresh(child)
        return child_profile_output(db, child)

    @app.get("/api/v1/admin/children", response_model=list[ChildOutput], tags=["safeguarding"])
    def list_children(
        active_only: bool = True,
        _: Annotated[AdminUser, Depends(child_manager)] = None,
        db: Session = Depends(get_db),
    ):
        query = select(ChildProfile)
        if active_only:
            query = query.where(ChildProfile.is_active.is_(True))
        children = db.scalars(query.order_by(ChildProfile.created_at.desc())).all()
        return [child_profile_output(db, child) for child in children]

    @app.put("/api/v1/admin/children/{child_id}", response_model=ChildOutput, tags=["safeguarding"])
    def update_child(
        child_id: int,
        payload: ChildProfileInput,
        actor: Annotated[AdminUser, Depends(child_manager)],
        db: Session = Depends(get_db),
    ):
        child = db.get(ChildProfile, child_id)
        if child is None:
            raise HTTPException(status_code=404, detail="Child profile not found")
        if not payload.consent_confirmed:
            raise HTTPException(status_code=422, detail="Guardian consent is required to update a child profile")
        guardian = active_member(db, payload.primary_guardian_id)
        pickup_ids = validate_pickup_members(db, guardian.id, payload.authorized_pickup_member_ids)
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Child name cannot be blank")
        child.primary_guardian_id = guardian.id
        child.encrypted_profile = encrypt_text(json.dumps({"name": name}))
        child.consented_at = datetime.now(timezone.utc)
        existing_authorizations = db.scalars(
            select(ChildPickupAuthorization).where(ChildPickupAuthorization.child_id == child.id)
        ).all()
        for authorization in existing_authorizations:
            db.delete(authorization)
        db.add_all([
            ChildPickupAuthorization(child_id=child.id, member_id=member_id)
            for member_id in pickup_ids
        ])
        record_audit(db, actor, "update", "child_profile", child.id)
        db.commit()
        db.refresh(child)
        return child_profile_output(db, child)

    @app.patch("/api/v1/admin/children/{child_id}/status", tags=["safeguarding"])
    def update_child_status(
        child_id: int,
        new_status: str = Query(pattern="^(active|inactive)$"),
        actor: Annotated[AdminUser, Depends(child_manager)] = None,
        db: Session = Depends(get_db),
    ):
        child = db.get(ChildProfile, child_id)
        if child is None:
            raise HTTPException(status_code=404, detail="Child profile not found")
        child.is_active = new_status == "active"
        record_audit(db, actor, "status_change", "child_profile", child.id)
        db.commit()
        return {"id": child.id, "is_active": child.is_active}

    @app.post("/api/v1/admin/child-attendance", response_model=ChildAttendanceOutput, status_code=201, tags=["safeguarding"])
    def check_in_child(
        payload: ChildAttendanceInput,
        actor: Annotated[AdminUser, Depends(child_manager)],
        db: Session = Depends(get_db),
    ):
        child = db.get(ChildProfile, payload.child_id)
        if child is None or not child.is_active:
            raise HTTPException(status_code=404, detail="Active child profile not found")
        pickup_member = active_member(db, payload.checked_in_by_member_id)
        authorized = pickup_member.id == child.primary_guardian_id or db.scalar(
            select(ChildPickupAuthorization.id).where(
                ChildPickupAuthorization.child_id == child.id,
                ChildPickupAuthorization.member_id == pickup_member.id,
            )
        ) is not None
        if not authorized:
            raise HTTPException(status_code=403, detail="This member is not authorized to check in the child")
        service_name = payload.service_name.strip()
        if not service_name:
            raise HTTPException(status_code=422, detail="Service name cannot be blank")
        attendance = ChildAttendance(
            child_id=child.id,
            service_name=service_name,
            service_date=payload.service_date,
            checked_in_by_member_id=pickup_member.id,
        )
        db.add(attendance)
        try:
            db.flush()
            record_audit(db, actor, "check_in", "child_attendance", attendance.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Child is already checked in for this service and date") from exc
        db.refresh(attendance)
        return child_attendance_output(db, attendance, child)

    @app.get("/api/v1/admin/child-attendance", response_model=list[ChildAttendanceOutput], tags=["safeguarding"])
    def list_child_attendance(
        service_date: date,
        _: Annotated[AdminUser, Depends(child_manager)],
        db: Session = Depends(get_db),
    ):
        records = db.execute(
            select(ChildAttendance, ChildProfile)
            .join(ChildProfile, ChildProfile.id == ChildAttendance.child_id)
            .where(ChildAttendance.service_date == service_date)
            .order_by(ChildAttendance.checked_in_at)
        ).all()
        return [child_attendance_output(db, attendance, child) for attendance, child in records]

    @app.patch("/api/v1/admin/child-attendance/{attendance_id}/check-out", response_model=ChildAttendanceOutput, tags=["safeguarding"])
    def check_out_child(
        attendance_id: int,
        payload: ChildCheckoutInput,
        actor: Annotated[AdminUser, Depends(child_manager)],
        db: Session = Depends(get_db),
    ):
        attendance = db.get(ChildAttendance, attendance_id)
        if attendance is None:
            raise HTTPException(status_code=404, detail="Child attendance record not found")
        child = db.get(ChildProfile, attendance.child_id)
        if child is None:
            raise HTTPException(status_code=404, detail="Child profile not found")
        pickup_member = active_member(db, payload.checked_out_by_member_id)
        authorized = pickup_member.id == child.primary_guardian_id or db.scalar(
            select(ChildPickupAuthorization.id).where(
                ChildPickupAuthorization.child_id == child.id,
                ChildPickupAuthorization.member_id == pickup_member.id,
            )
        ) is not None
        if not authorized:
            raise HTTPException(status_code=403, detail="This member is not authorized to pick up the child")
        if attendance.checked_out_at is not None:
            raise HTTPException(status_code=409, detail="Child has already been checked out")
        attendance.checked_out_by_member_id = pickup_member.id
        attendance.checked_out_at = datetime.now(timezone.utc)
        record_audit(db, actor, "check_out", "child_attendance", attendance.id)
        db.commit()
        db.refresh(attendance)
        return child_attendance_output(db, attendance, child)

    @app.post("/api/v1/admin/volunteer-availability", response_model=VolunteerAvailabilityOutput, tags=["volunteers"])
    def set_volunteer_availability(
        payload: VolunteerAvailabilityInput,
        actor: Annotated[AdminUser, Depends(volunteer_manager)],
        db: Session = Depends(get_db),
    ):
        member = active_member(db, payload.member_id)
        service_name = payload.service_name.strip()
        if not service_name:
            raise HTTPException(status_code=422, detail="Service name cannot be blank")
        availability = db.scalar(select(VolunteerAvailability).where(
            VolunteerAvailability.member_id == member.id,
            VolunteerAvailability.service_name == service_name,
            VolunteerAvailability.service_date == payload.service_date,
        ))
        action = "update"
        if availability is None:
            availability = VolunteerAvailability(
                member_id=member.id,
                service_name=service_name,
                service_date=payload.service_date,
                is_available=payload.is_available,
                updated_by_id=actor.id,
            )
            db.add(availability)
            action = "create"
        else:
            availability.is_available = payload.is_available
            availability.updated_by_id = actor.id
        try:
            db.flush()
            record_audit(db, actor, action, "volunteer_availability", availability.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Availability was updated concurrently; reload and try again") from exc
        db.refresh(availability)
        return VolunteerAvailabilityOutput(
            member_id=member.id,
            member_name=json.loads(decrypt_text(member.encrypted_profile))["name"],
            service_name=availability.service_name,
            service_date=availability.service_date,
            is_available=availability.is_available,
            updated_at=availability.updated_at,
        )

    @app.post("/api/v1/admin/volunteer-availability/invites", response_model=AvailabilityInviteOutput, status_code=201, tags=["volunteers"])
    def create_availability_invite(
        payload: AvailabilityInviteInput,
        actor: Annotated[AdminUser, Depends(volunteer_manager)],
        db: Session = Depends(get_db),
    ):
        member = active_member(db, payload.member_id)
        service_name = payload.service_name.strip()
        if not service_name:
            raise HTTPException(status_code=422, detail="Service name cannot be blank")
        if payload.service_date < datetime.now(timezone.utc).date():
            raise HTTPException(status_code=422, detail="Availability links can only be created for today or a future date")
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        invite = AvailabilityInvite(
            token_digest=keyed_digest(token, "volunteer-availability-invite-v1"),
            member_id=member.id,
            service_name=service_name,
            service_date=payload.service_date,
            expires_at=expires_at,
            created_by_id=actor.id,
        )
        db.add(invite)
        db.flush()
        record_audit(db, actor, "create", "availability_invite", invite.id)
        db.commit()
        return AvailabilityInviteOutput(token=token, expires_at=expires_at)

    @app.post("/api/v1/volunteer-availability/invites/inspect", response_model=AvailabilityInviteDetails, tags=["volunteers"])
    def read_availability_invite(payload: AvailabilityInviteToken, db: Session = Depends(get_db)):
        digest = keyed_digest(payload.token, "volunteer-availability-invite-v1")
        invite = db.scalar(select(AvailabilityInvite).where(AvailabilityInvite.token_digest == digest))
        if invite is None or invite.used_at is not None:
            raise HTTPException(status_code=404, detail="Availability link is unavailable")
        expires_at = invite.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Availability link has expired")
        return AvailabilityInviteDetails(service_name=invite.service_name, service_date=invite.service_date)

    @app.post("/api/v1/volunteer-availability/respond", tags=["volunteers"])
    def respond_to_availability(payload: AvailabilityResponseInput, db: Session = Depends(get_db)):
        digest = keyed_digest(payload.token, "volunteer-availability-invite-v1")
        invite = db.scalar(select(AvailabilityInvite).where(AvailabilityInvite.token_digest == digest))
        if invite is None or invite.used_at is not None:
            raise HTTPException(status_code=404, detail="Availability link is unavailable")
        now = datetime.now(timezone.utc)
        expires_at = invite.expires_at
        comparison_now = now.replace(tzinfo=None) if db.get_bind().dialect.name == "sqlite" else now
        if expires_at.tzinfo is None and db.get_bind().dialect.name != "sqlite":
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= comparison_now:
            raise HTTPException(status_code=410, detail="Availability link has expired")
        member = active_member(db, invite.member_id)
        availability = db.scalar(select(VolunteerAvailability).where(
            VolunteerAvailability.member_id == member.id,
            VolunteerAvailability.service_name == invite.service_name,
            VolunteerAvailability.service_date == invite.service_date,
        ))
        if availability is None:
            availability = VolunteerAvailability(
                member_id=member.id,
                service_name=invite.service_name,
                service_date=invite.service_date,
                is_available=payload.is_available,
                updated_by_id=None,
            )
            db.add(availability)
        else:
            availability.is_available = payload.is_available
            availability.updated_by_id = None
        claim = db.execute(
            update(AvailabilityInvite)
            .where(
                AvailabilityInvite.id == invite.id,
                AvailabilityInvite.used_at.is_(None),
                AvailabilityInvite.expires_at > comparison_now,
            )
            .values(used_at=now)
        )
        if claim.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=404, detail="Availability link is unavailable")
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Availability link was already used") from exc
        return {"status": "recorded"}

    @app.get("/api/v1/admin/volunteer-availability", response_model=list[VolunteerAvailabilityOutput], tags=["volunteers"])
    def list_volunteer_availability(
        service_date: date,
        _: Annotated[AdminUser, Depends(volunteer_manager)],
        service_name: str | None = Query(default=None, max_length=120),
        db: Session = Depends(get_db),
    ):
        query = (
            select(VolunteerAvailability, Member)
            .join(Member, Member.id == VolunteerAvailability.member_id)
            .where(VolunteerAvailability.service_date == service_date)
        )
        if service_name:
            query = query.where(VolunteerAvailability.service_name == service_name.strip())
        records = db.execute(query.order_by(VolunteerAvailability.service_name, Member.id)).all()
        return [
            VolunteerAvailabilityOutput(
                member_id=member.id,
                member_name=json.loads(decrypt_text(member.encrypted_profile))["name"],
                service_name=availability.service_name,
                service_date=availability.service_date,
                is_available=availability.is_available,
                updated_at=availability.updated_at,
            )
            for availability, member in records
        ]

    @app.post("/api/v1/admin/rota/generate", response_model=list[RotaAssignmentOutput], status_code=201, tags=["volunteers"])
    def generate_rota(
        payload: RotaGenerationInput,
        actor: Annotated[AdminUser, Depends(volunteer_manager)],
        db: Session = Depends(get_db),
    ):
        service_name = payload.service_name.strip()
        if not service_name:
            raise HTTPException(status_code=422, detail="Service name cannot be blank")
        existing = db.scalar(select(RotaAssignment.id).where(
            RotaAssignment.service_name == service_name,
            RotaAssignment.service_date == payload.service_date,
        ).limit(1))
        if existing:
            raise HTTPException(status_code=409, detail="A rota already exists for this service and date")
        available = db.execute(
            select(Member, VolunteerAvailability)
            .join(VolunteerAvailability, VolunteerAvailability.member_id == Member.id)
            .where(
                Member.status == "active",
                VolunteerAvailability.is_available.is_(True),
                VolunteerAvailability.service_name == service_name,
                VolunteerAvailability.service_date == payload.service_date,
            )
            .order_by(Member.id)
        ).all()
        if len(available) < len(payload.role_names):
            raise HTTPException(
                status_code=409,
                detail=f"Need {len(payload.role_names)} available volunteers but found {len(available)}",
            )

        window_start = payload.service_date - timedelta(days=30)
        workload_rows = db.execute(
            select(RotaAssignment.member_id, func.count(RotaAssignment.id), func.max(RotaAssignment.service_date))
            .where(
                RotaAssignment.service_date >= window_start,
                RotaAssignment.service_date < payload.service_date,
            )
            .group_by(RotaAssignment.member_id)
        ).all()
        workload = {member_id: (count, last_date or date.min) for member_id, count, last_date in workload_rows}
        available.sort(key=lambda item: (*workload.get(item[0].id, (0, date.min)), item[0].id))

        assignments = []
        for role_name in payload.role_names:
            member, _ = available.pop(0)
            assignment = RotaAssignment(
                member_id=member.id,
                service_name=service_name,
                service_date=payload.service_date,
                role_name=role_name,
                assigned_by_id=actor.id,
            )
            db.add(assignment)
            assignments.append((assignment, member))
        try:
            db.flush()
            for assignment, _ in assignments:
                record_audit(db, actor, "assign", "rota_assignment", assignment.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Rota changed concurrently; reload and try again") from exc
        for assignment, _ in assignments:
            db.refresh(assignment)
        return [rota_assignment_output(assignment, member) for assignment, member in assignments]

    @app.get("/api/v1/admin/rota", response_model=list[RotaAssignmentOutput], tags=["volunteers"])
    def list_rota(
        service_date: date,
        _: Annotated[AdminUser, Depends(volunteer_manager)],
        service_name: str | None = Query(default=None, max_length=120),
        db: Session = Depends(get_db),
    ):
        query = (
            select(RotaAssignment, Member)
            .join(Member, Member.id == RotaAssignment.member_id)
            .where(RotaAssignment.service_date == service_date)
        )
        if service_name:
            query = query.where(RotaAssignment.service_name == service_name.strip())
        records = db.execute(query.order_by(RotaAssignment.service_name, RotaAssignment.role_name)).all()
        return [rota_assignment_output(assignment, member) for assignment, member in records]

    @app.post(
        "/api/v1/admin/finance/offering-counts",
        response_model=OfferingCountOutput,
        status_code=201,
        tags=["finance"],
    )
    def create_offering_count(
        payload: OfferingCountInput,
        actor: Annotated[AdminUser, Depends(finance_manager)],
        db: Session = Depends(get_db),
    ):
        service_name = payload.service_name.strip()
        fund = payload.fund.strip()
        category = payload.category.strip()
        if not service_name or not fund or not category:
            raise HTTPException(status_code=422, detail="Service, fund and category cannot be blank")
        batch = OfferingCountBatch(
            service_name=service_name,
            service_date=payload.service_date,
            fund=fund,
            category=category,
            amount_counted_ugx=payload.amount_ugx,
            status="pending",
            counted_by_id=actor.id,
            encrypted_details=encrypt_text(json.dumps({"notes": payload.notes.strip()})),
            branch_id=validate_branch_assignment(db, payload.branch_id),
        )
        db.add(batch)
        db.flush()
        record_audit(db, actor, "count_recorded", "offering_count_batch", batch.id)
        db.commit()
        db.refresh(batch)
        return offering_count_output(batch)

    @app.get(
        "/api/v1/admin/finance/offering-counts",
        response_model=list[OfferingCountOutput],
        tags=["finance"],
    )
    def list_offering_counts(
        _: Annotated[AdminUser, Depends(finance_manager)],
        status: str | None = Query(default=None, pattern="^(pending|discrepancy|recorded|resolved)$"),
        service_date: date | None = None,
        branch_id: int | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        db: Session = Depends(get_db),
    ):
        query = select(OfferingCountBatch)
        if status:
            query = query.where(OfferingCountBatch.status == status)
        if service_date:
            query = query.where(OfferingCountBatch.service_date == service_date)
        if branch_id is not None:
            query = query.where(OfferingCountBatch.branch_id == branch_id)
        batches = db.scalars(
            query.order_by(OfferingCountBatch.service_date.desc(), OfferingCountBatch.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [offering_count_output(batch) for batch in batches]

    @app.post(
        "/api/v1/admin/finance/offering-counts/{batch_id}/verify",
        response_model=OfferingCountOutput,
        tags=["finance"],
    )
    def verify_offering_count(
        batch_id: int,
        payload: OfferingCountVerificationInput,
        actor: Annotated[AdminUser, Depends(finance_manager)],
        db: Session = Depends(get_db),
    ):
        batch = db.get(OfferingCountBatch, batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Offering count not found")
        if batch.status != "pending":
            raise HTTPException(status_code=409, detail="Only pending offering counts can be verified")
        if batch.counted_by_id == actor.id:
            raise HTTPException(status_code=403, detail="A different finance staff member must verify the count")
        claim = db.execute(
            update(OfferingCountBatch)
            .where(OfferingCountBatch.id == batch.id, OfferingCountBatch.status == "pending")
            .values(status="processing")
        )
        if claim.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Offering count is already being verified")
        now = datetime.now(timezone.utc)
        batch.verified_by_id = actor.id
        batch.verified_amount_ugx = payload.amount_ugx
        batch.verified_at = now
        if payload.amount_ugx != batch.amount_counted_ugx:
            batch.status = "discrepancy"
            record_audit(db, actor, "count_discrepancy", "offering_count_batch", batch.id)
            db.commit()
            db.refresh(batch)
            return offering_count_output(batch)

        batch.status = "recorded"
        batch.final_amount_ugx = payload.amount_ugx
        entry = FinanceEntry(
            entry_type="income",
            amount_ugx=payload.amount_ugx,
            fund=batch.fund,
            category=batch.category,
            entry_date=batch.service_date,
            payment_method="cash",
            status="recorded",
            encrypted_details=encrypt_text(json.dumps({
                "details": f"Dual-witness offering count batch #{batch.id}",
            })),
            recorded_by_id=batch.counted_by_id,
            reviewed_by_id=actor.id,
            reviewed_at=now,
            branch_id=batch.branch_id,
        )
        db.add(entry)
        db.flush()
        batch.finance_entry_id = entry.id
        record_audit(db, actor, "count_verified", "offering_count_batch", batch.id)
        record_audit(db, actor, "record", "finance_entry", entry.id)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Offering count was concurrently verified; refresh and review it") from exc
        db.refresh(batch)
        return offering_count_output(batch)

    @app.post(
        "/api/v1/admin/finance/offering-counts/{batch_id}/resolve",
        response_model=OfferingCountOutput,
        tags=["finance"],
    )
    def resolve_offering_count(
        batch_id: int,
        payload: OfferingCountResolutionInput,
        actor: Annotated[AdminUser, Depends(finance_manager)],
        db: Session = Depends(get_db),
    ):
        batch = db.get(OfferingCountBatch, batch_id)
        if batch is None:
            raise HTTPException(status_code=404, detail="Offering count not found")
        if batch.status != "discrepancy":
            raise HTTPException(status_code=409, detail="Only discrepant counts can be resolved")
        if actor.id in {batch.counted_by_id, batch.verified_by_id}:
            raise HTTPException(status_code=403, detail="A third finance staff member must resolve the discrepancy")
        claim = db.execute(
            update(OfferingCountBatch)
            .where(OfferingCountBatch.id == batch.id, OfferingCountBatch.status == "discrepancy")
            .values(status="processing")
        )
        if claim.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Offering count is already being resolved")
        reason = payload.reason.strip()
        if len(reason) < 5:
            raise HTTPException(status_code=422, detail="Resolution reason must contain at least five characters")
        now = datetime.now(timezone.utc)
        batch.status = "resolved"
        batch.final_amount_ugx = payload.amount_ugx
        batch.resolved_by_id = actor.id
        batch.resolved_at = now
        entry = FinanceEntry(
            entry_type="income",
            amount_ugx=payload.amount_ugx,
            fund=batch.fund,
            category=batch.category,
            entry_date=batch.service_date,
            payment_method="cash",
            status="recorded",
            encrypted_details=encrypt_text(json.dumps({
                "details": f"Resolved offering count batch #{batch.id}: {reason}",
            })),
            recorded_by_id=batch.counted_by_id,
            reviewed_by_id=actor.id,
            reviewed_at=now,
            branch_id=batch.branch_id,
        )
        db.add(entry)
        db.flush()
        batch.finance_entry_id = entry.id
        record_audit(db, actor, "count_discrepancy_resolved", "offering_count_batch", batch.id)
        record_audit(db, actor, "record", "finance_entry", entry.id)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Offering count was concurrently resolved; refresh and review it") from exc
        db.refresh(batch)
        return offering_count_output(batch)

    @app.post("/api/v1/admin/finance/entries", response_model=FinanceEntryOutput, status_code=201, tags=["finance"])
    def create_finance_entry(
        payload: FinanceEntryInput,
        actor: Annotated[AdminUser, Depends(finance_manager)],
        db: Session = Depends(get_db),
    ):
        fund = payload.fund.strip()
        category = payload.category.strip()
        details = payload.details.strip()
        if not fund or not category:
            raise HTTPException(status_code=422, detail="Fund and category cannot be blank")
        entry = FinanceEntry(
            entry_type=payload.entry_type,
            amount_ugx=payload.amount_ugx,
            fund=fund,
            category=category,
            entry_date=payload.entry_date,
            payment_method=payload.payment_method,
            status="recorded" if payload.entry_type == "income" else "pending",
            encrypted_details=encrypt_text(json.dumps({"details": details})),
            recorded_by_id=actor.id,
            branch_id=validate_branch_assignment(db, payload.branch_id),
        )
        db.add(entry)
        db.flush()
        record_audit(db, actor, "record", "finance_entry", entry.id)
        db.commit()
        db.refresh(entry)
        return finance_entry_output(entry)

    @app.post(
        "/api/v1/admin/finance/entries/{entry_id}/correction",
        response_model=FinanceEntryOutput,
        status_code=201,
        tags=["finance"],
    )
    def correct_finance_entry(
        entry_id: int,
        payload: FinanceEntryCorrectionInput,
        actor: Annotated[AdminUser, Depends(finance_manager)],
        db: Session = Depends(get_db),
    ):
        original = db.get(FinanceEntry, entry_id)
        if original is None:
            raise HTTPException(status_code=404, detail="Finance entry not found")
        if original.correction_of_id is not None:
            raise HTTPException(status_code=409, detail="A correction entry cannot itself be corrected")
        if original.entry_type == "expense" and original.status != "approved":
            raise HTTPException(status_code=409, detail="Only approved expenses can be corrected")
        if original.entry_type == "income" and original.status != "recorded":
            raise HTTPException(status_code=409, detail="Only recorded income entries can be corrected")
        existing_correction = db.scalar(
            select(FinanceEntry.id).where(FinanceEntry.correction_of_id == original.id)
        )
        if existing_correction:
            raise HTTPException(status_code=409, detail="This entry already has a correction")
        reason = payload.reason.strip()
        if len(reason) < 5:
            raise HTTPException(status_code=422, detail="Correction reason must contain at least five characters")
        correction = FinanceEntry(
            entry_type="expense" if original.entry_type == "income" else "income",
            amount_ugx=original.amount_ugx,
            fund=original.fund,
            category=original.category,
            entry_date=datetime.now(timezone.utc).date(),
            payment_method=original.payment_method,
            status="pending",
            encrypted_details=encrypt_text(json.dumps({
                "details": f"Correction for finance entry #{original.id}: {reason}",
            })),
            recorded_by_id=actor.id,
            correction_of_id=original.id,
            branch_id=original.branch_id,
        )
        db.add(correction)
        try:
            db.flush()
            record_audit(db, actor, "correction_requested", "finance_entry", original.id)
            record_audit(db, actor, "correction_created", "finance_entry", correction.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="This entry already has a correction") from exc
        db.refresh(correction)
        return finance_entry_output(correction)

    @app.get("/api/v1/admin/finance/entries", response_model=list[FinanceEntryOutput], tags=["finance"])
    def list_finance_entries(
        _: Annotated[AdminUser, Depends(finance_manager)],
        from_date: date | None = None,
        to_date: date | None = None,
        entry_type: str | None = Query(default=None, pattern="^(income|expense)$"),
        status: str | None = Query(default=None, pattern="^(recorded|pending|approved|rejected)$"),
        branch_id: int | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        db: Session = Depends(get_db),
    ):
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=422, detail="from_date must be on or before to_date")
        query = select(FinanceEntry)
        if from_date:
            query = query.where(FinanceEntry.entry_date >= from_date)
        if to_date:
            query = query.where(FinanceEntry.entry_date <= to_date)
        if entry_type:
            query = query.where(FinanceEntry.entry_type == entry_type)
        if status:
            query = query.where(FinanceEntry.status == status)
        if branch_id is not None:
            query = query.where(FinanceEntry.branch_id == branch_id)
        entries = db.scalars(query.order_by(FinanceEntry.entry_date.desc(), FinanceEntry.id.desc()).limit(limit).offset(offset))
        return [finance_entry_output(entry) for entry in entries]

    @app.patch("/api/v1/admin/finance/entries/{entry_id}/approval", response_model=FinanceEntryOutput, tags=["finance"])
    def review_finance_entry(
        entry_id: int,
        status: str = Query(pattern="^(approved|rejected)$"),
        actor: Annotated[AdminUser, Depends(finance_manager)] = None,
        db: Session = Depends(get_db),
    ):
        entry = db.get(FinanceEntry, entry_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Finance entry not found")
        if entry.status != "pending" or (entry.entry_type != "expense" and entry.correction_of_id is None):
            raise HTTPException(status_code=409, detail="Only pending expenses and correction entries can be reviewed")
        if entry.recorded_by_id == actor.id:
            raise HTTPException(status_code=403, detail="Expenses must be reviewed by a different staff member")
        entry.status = status
        entry.reviewed_by_id = actor.id
        entry.reviewed_at = datetime.now(timezone.utc)
        record_audit(db, actor, status, "finance_entry", entry.id)
        db.commit()
        db.refresh(entry)
        return finance_entry_output(entry)

    @app.post("/api/v1/admin/finance/budgets", response_model=FinanceBudgetOutput, status_code=201, tags=["finance"])
    def create_finance_budget(
        payload: FinanceBudgetInput,
        actor: Annotated[AdminUser, Depends(finance_manager)],
        db: Session = Depends(get_db),
    ):
        budget = FinanceBudget(
            fund=payload.fund.strip(),
            category=payload.category.strip(),
            amount_ugx=payload.amount_ugx,
            period_start=payload.period_start,
            period_end=payload.period_end,
            created_by_id=actor.id,
            branch_id=validate_branch_assignment(db, payload.branch_id),
        )
        if not budget.fund or not budget.category:
            raise HTTPException(status_code=422, detail="Fund and category cannot be blank")
        db.add(budget)
        try:
            db.flush()
            record_audit(db, actor, "create", "finance_budget", budget.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A budget already exists for this fund, category and period") from exc
        db.refresh(budget)
        return finance_budget_output(db, budget)

    @app.get("/api/v1/admin/finance/budgets", response_model=list[FinanceBudgetOutput], tags=["finance"])
    def list_finance_budgets(
        _: Annotated[AdminUser, Depends(finance_manager)],
        from_date: date | None = None,
        to_date: date | None = None,
        branch_id: int | None = None,
        db: Session = Depends(get_db),
    ):
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=422, detail="from_date must be on or before to_date")
        query = select(FinanceBudget)
        if from_date:
            query = query.where(FinanceBudget.period_end >= from_date)
        if to_date:
            query = query.where(FinanceBudget.period_start <= to_date)
        if branch_id is not None:
            query = query.where(FinanceBudget.branch_id == branch_id)
        budgets = db.scalars(query.order_by(FinanceBudget.period_start.desc(), FinanceBudget.fund, FinanceBudget.category))
        return [finance_budget_output(db, budget) for budget in budgets]

    @app.post("/api/v1/admin/finance/pledges", response_model=FinancePledgeOutput, status_code=201, tags=["finance"])
    def create_finance_pledge(
        payload: FinancePledgeInput,
        actor: Annotated[AdminUser, Depends(finance_manager)],
        db: Session = Depends(get_db),
    ):
        campaign = payload.campaign.strip()
        donor_name = payload.donor_name.strip()
        if not campaign or not donor_name:
            raise HTTPException(status_code=422, detail="Campaign and donor name cannot be blank")
        pledge = FinancePledge(
            campaign=campaign,
            amount_ugx=payload.amount_ugx,
            amount_fulfilled_ugx=0,
            due_date=payload.due_date,
            status="pledged",
            encrypted_details=encrypt_text(json.dumps({
                "donor_name": donor_name,
                "donor_contact": payload.donor_contact.strip() if payload.donor_contact else None,
                "details": payload.details.strip(),
            })),
            recorded_by_id=actor.id,
            branch_id=validate_branch_assignment(db, payload.branch_id),
        )
        db.add(pledge)
        db.flush()
        record_audit(db, actor, "record", "finance_pledge", pledge.id)
        db.commit()
        db.refresh(pledge)
        return finance_pledge_output(pledge)

    @app.get("/api/v1/admin/finance/pledges", response_model=list[FinancePledgeOutput], tags=["finance"])
    def list_finance_pledges(
        _: Annotated[AdminUser, Depends(finance_manager)],
        status: str | None = Query(default=None, pattern="^(pledged|partially_fulfilled|fulfilled|cancelled)$"),
        branch_id: int | None = None,
        db: Session = Depends(get_db),
    ):
        query = select(FinancePledge)
        if status:
            query = query.where(FinancePledge.status == status)
        if branch_id is not None:
            query = query.where(FinancePledge.branch_id == branch_id)
        pledges = db.scalars(query.order_by(FinancePledge.created_at.desc()).limit(500))
        return [finance_pledge_output(pledge) for pledge in pledges]

    @app.patch("/api/v1/admin/finance/pledges/{pledge_id}/status", response_model=FinancePledgeOutput, tags=["finance"])
    def update_finance_pledge_status(
        pledge_id: int,
        payload: FinancePledgeStatusInput,
        actor: Annotated[AdminUser, Depends(finance_manager)],
        db: Session = Depends(get_db),
    ):
        pledge = db.get(FinancePledge, pledge_id)
        if pledge is None:
            raise HTTPException(status_code=404, detail="Pledge not found")
        if pledge.status in {"fulfilled", "cancelled"}:
            raise HTTPException(status_code=409, detail="Completed pledges cannot be changed")
        amount_fulfilled = payload.amount_fulfilled_ugx
        if amount_fulfilled > pledge.amount_ugx:
            raise HTTPException(status_code=422, detail="Fulfilled amount cannot exceed the pledge amount")
        if payload.status == "pledged" and amount_fulfilled != 0:
            raise HTTPException(status_code=422, detail="A pledged record cannot have a fulfilled amount")
        if payload.status == "partially_fulfilled" and not 0 < amount_fulfilled < pledge.amount_ugx:
            raise HTTPException(status_code=422, detail="Partial fulfillment must be greater than zero and below the full pledge")
        if payload.status == "fulfilled" and amount_fulfilled != pledge.amount_ugx:
            raise HTTPException(status_code=422, detail="A fulfilled pledge must match the full pledge amount")
        pledge.status = payload.status
        pledge.amount_fulfilled_ugx = amount_fulfilled
        record_audit(db, actor, "status_change", "finance_pledge", pledge.id)
        db.commit()
        db.refresh(pledge)
        return finance_pledge_output(pledge)

    @app.get("/api/v1/admin/finance/report", response_model=FinanceReportOutput, tags=["finance"])
    def finance_report(
        period_start: date,
        period_end: date,
        _: Annotated[AdminUser, Depends(finance_manager)],
        branch_id: int | None = None,
        db: Session = Depends(get_db),
    ):
        if period_start > period_end:
            raise HTTPException(status_code=422, detail="period_start must be on or before period_end")
        def total_for(entry_type: str, statuses: tuple[str, ...]) -> int:
            query = select(func.coalesce(func.sum(FinanceEntry.amount_ugx), 0)).where(
                FinanceEntry.entry_type == entry_type,
                FinanceEntry.status.in_(statuses),
                FinanceEntry.entry_date >= period_start,
                FinanceEntry.entry_date <= period_end,
            )
            if branch_id is not None:
                query = query.where(FinanceEntry.branch_id == branch_id)
            return db.scalar(query) or 0
        budget_query = select(func.coalesce(func.sum(FinanceBudget.amount_ugx), 0)).where(
                FinanceBudget.period_start >= period_start,
                FinanceBudget.period_end <= period_end,
            )
        pledge_query = select(func.coalesce(func.sum(FinancePledge.amount_ugx - FinancePledge.amount_fulfilled_ugx), 0)).where(
                FinancePledge.due_date >= period_start,
                FinancePledge.due_date <= period_end,
                FinancePledge.status.in_(("pledged", "partially_fulfilled")),
            )
        corrections_query = select(func.coalesce(func.sum(FinanceEntry.amount_ugx), 0)).where(
            FinanceEntry.correction_of_id.is_not(None),
            FinanceEntry.status == "pending",
            FinanceEntry.entry_date >= period_start,
            FinanceEntry.entry_date <= period_end,
        )
        if branch_id is not None:
            budget_query = budget_query.where(FinanceBudget.branch_id == branch_id)
            pledge_query = pledge_query.where(FinancePledge.branch_id == branch_id)
            corrections_query = corrections_query.where(FinanceEntry.branch_id == branch_id)
        budgeted = db.scalar(budget_query) or 0
        pledge_total = db.scalar(pledge_query) or 0
        return FinanceReportOutput(
            period_start=period_start,
            period_end=period_end,
            income_ugx=total_for("income", ("recorded", "approved")),
            approved_expenses_ugx=total_for("expense", ("approved",)),
            pending_expenses_ugx=total_for("expense", ("pending",)),
            pending_corrections_ugx=db.scalar(corrections_query) or 0,
            budgeted_ugx=budgeted,
            pledge_total_ugx=pledge_total,
        )

    @app.post("/api/v1/admin/pastoral-care/tasks", response_model=PastoralCareTaskOutput, status_code=201, tags=["pastoral care"])
    def create_pastoral_care_task(
        payload: PastoralCareTaskInput,
        actor: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        active_member(db, payload.member_id)
        notes = payload.notes.strip()
        if not notes:
            raise HTTPException(status_code=422, detail="Care notes cannot be blank")
        if payload.assigned_to_id is not None:
            assignee = db.get(AdminUser, payload.assigned_to_id)
            if assignee is None or not assignee.is_active or assignee.role not in {"admin", "pastor"}:
                raise HTTPException(status_code=422, detail="Care tasks can only be assigned to active pastors or administrators")
        task = PastoralCareTask(
            member_id=payload.member_id,
            care_type=payload.care_type,
            priority=payload.priority,
            due_date=payload.due_date,
            status="open",
            encrypted_details=encrypt_text(json.dumps({"notes": notes})),
            assigned_to_id=payload.assigned_to_id,
            created_by_id=actor.id,
        )
        db.add(task)
        db.flush()
        record_audit(db, actor, "create", "pastoral_care_task", task.id)
        db.commit()
        db.refresh(task)
        return pastoral_task_output(db, task)

    @app.get("/api/v1/admin/pastoral-care/tasks", response_model=list[PastoralCareTaskOutput], tags=["pastoral care"])
    def list_pastoral_care_tasks(
        _: Annotated[AdminUser, Depends(pastoral_manager)],
        status: str | None = Query(default=None, pattern="^(open|in_progress|completed|cancelled)$"),
        member_id: int | None = Query(default=None, ge=1),
        db: Session = Depends(get_db),
    ):
        query = select(PastoralCareTask)
        if status:
            query = query.where(PastoralCareTask.status == status)
        if member_id:
            query = query.where(PastoralCareTask.member_id == member_id)
        tasks = db.scalars(query.order_by(PastoralCareTask.due_date, PastoralCareTask.created_at.desc()).limit(500))
        return [pastoral_task_output(db, task) for task in tasks]

    @app.put("/api/v1/admin/pastoral-care/tasks/{task_id}", response_model=PastoralCareTaskOutput, tags=["pastoral care"])
    def update_pastoral_care_task(
        task_id: int,
        payload: PastoralCareTaskUpdate,
        actor: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        task = db.get(PastoralCareTask, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Pastoral care task not found")
        if payload.assigned_to_id is not None:
            assignee = db.get(AdminUser, payload.assigned_to_id)
            if assignee is None or not assignee.is_active or assignee.role not in {"admin", "pastor"}:
                raise HTTPException(status_code=422, detail="Care tasks can only be assigned to active pastors or administrators")
        notes = payload.notes.strip()
        if not notes:
            raise HTTPException(status_code=422, detail="Care notes cannot be blank")
        task.priority = payload.priority
        task.due_date = payload.due_date
        task.status = payload.status
        task.encrypted_details = encrypt_text(json.dumps({"notes": notes}))
        task.assigned_to_id = payload.assigned_to_id
        record_audit(db, actor, "update", "pastoral_care_task", task.id)
        db.commit()
        db.refresh(task)
        return pastoral_task_output(db, task)

    @app.post("/api/v1/admin/resources", response_model=ChurchResourceOutput, status_code=201, tags=["resources"])
    def create_church_resource(
        payload: ChurchResourceInput,
        actor: Annotated[AdminUser, Depends(resource_manager)],
        db: Session = Depends(get_db),
    ):
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Resource name cannot be blank")
        resource = ChurchResource(
            name=name,
            description=payload.description.strip(),
            is_active=payload.is_active,
            created_by_id=actor.id,
        )
        db.add(resource)
        try:
            db.flush()
            record_audit(db, actor, "create", "church_resource", resource.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A resource with that name already exists") from exc
        db.refresh(resource)
        return resource

    @app.get("/api/v1/admin/resources", response_model=list[ChurchResourceOutput], tags=["resources"])
    def list_church_resources(
        _: Annotated[AdminUser, Depends(resource_manager)],
        include_inactive: bool = False,
        db: Session = Depends(get_db),
    ):
        query = select(ChurchResource)
        if not include_inactive:
            query = query.where(ChurchResource.is_active.is_(True))
        return db.scalars(query.order_by(ChurchResource.name)).all()

    @app.put("/api/v1/admin/resources/{resource_id}", response_model=ChurchResourceOutput, tags=["resources"])
    def update_church_resource(
        resource_id: int,
        payload: ChurchResourceInput,
        actor: Annotated[AdminUser, Depends(resource_manager)],
        db: Session = Depends(get_db),
    ):
        resource = db.get(ChurchResource, resource_id)
        if resource is None:
            raise HTTPException(status_code=404, detail="Church resource not found")
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Resource name cannot be blank")
        resource.name = name
        resource.description = payload.description.strip()
        resource.is_active = payload.is_active
        try:
            record_audit(db, actor, "update", "church_resource", resource.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A resource with that name already exists") from exc
        db.refresh(resource)
        return resource

    @app.post("/api/v1/admin/resource-bookings", response_model=ResourceBookingOutput, status_code=201, tags=["resources"])
    def create_resource_booking(
        payload: ResourceBookingInput,
        actor: Annotated[AdminUser, Depends(resource_manager)],
        db: Session = Depends(get_db),
    ):
        resource = db.get(ChurchResource, payload.resource_id)
        if resource is None or not resource.is_active:
            raise HTTPException(status_code=404, detail="Active church resource not found")
        starts_at = payload.starts_at.astimezone(timezone.utc)
        ends_at = payload.ends_at.astimezone(timezone.utc)
        conflict = db.scalar(
            select(ResourceBooking.id).where(
                ResourceBooking.resource_id == resource.id,
                ResourceBooking.status.in_(("pending", "approved")),
                ResourceBooking.starts_at < ends_at,
                ResourceBooking.ends_at > starts_at,
            ).limit(1)
        )
        if conflict:
            raise HTTPException(status_code=409, detail="This resource already has a booking during that time")
        if starts_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=422, detail="Resource bookings must start in the future")
        purpose = payload.purpose.strip()
        if not purpose:
            raise HTTPException(status_code=422, detail="Booking purpose cannot be blank")
        booking = ResourceBooking(
            resource_id=resource.id,
            starts_at=starts_at,
            ends_at=ends_at,
            status="pending",
            encrypted_details=encrypt_text(json.dumps({"purpose": purpose})),
            requested_by_id=actor.id,
        )
        db.add(booking)
        db.flush()
        record_audit(db, actor, "create", "resource_booking", booking.id)
        db.commit()
        db.refresh(booking)
        return resource_booking_output(db, booking)

    @app.get("/api/v1/admin/resource-bookings", response_model=list[ResourceBookingOutput], tags=["resources"])
    def list_resource_bookings(
        _: Annotated[AdminUser, Depends(resource_manager)],
        resource_id: int | None = Query(default=None, ge=1),
        status: str | None = Query(default=None, pattern="^(pending|approved|rejected|cancelled)$"),
        db: Session = Depends(get_db),
    ):
        query = select(ResourceBooking)
        if resource_id:
            query = query.where(ResourceBooking.resource_id == resource_id)
        if status:
            query = query.where(ResourceBooking.status == status)
        bookings = db.scalars(query.order_by(ResourceBooking.starts_at).limit(500))
        return [resource_booking_output(db, booking) for booking in bookings]

    @app.patch("/api/v1/admin/resource-bookings/{booking_id}/status", response_model=ResourceBookingOutput, tags=["resources"])
    def update_resource_booking_status(
        booking_id: int,
        payload: ResourceBookingStatusInput,
        actor: Annotated[AdminUser, Depends(resource_manager)],
        db: Session = Depends(get_db),
    ):
        booking = db.get(ResourceBooking, booking_id)
        if booking is None:
            raise HTTPException(status_code=404, detail="Resource booking not found")
        if booking.status not in {"pending", "approved"}:
            raise HTTPException(status_code=409, detail="This booking has already been closed")
        if booking.status == "approved" and payload.status != "cancelled":
            raise HTTPException(status_code=409, detail="Approved bookings can only be cancelled")
        if booking.status == "pending" and payload.status == "cancelled":
            raise HTTPException(status_code=409, detail="Pending bookings must be approved or rejected")
        if payload.status == "approved":
            conflict = db.scalar(
                select(ResourceBooking.id).where(
                    ResourceBooking.id != booking.id,
                    ResourceBooking.resource_id == booking.resource_id,
                    ResourceBooking.status == "approved",
                    ResourceBooking.starts_at < booking.ends_at,
                    ResourceBooking.ends_at > booking.starts_at,
                ).limit(1)
            )
            if conflict:
                raise HTTPException(status_code=409, detail="Another booking was approved for this time")
        booking.status = payload.status
        booking.reviewed_by_id = actor.id
        booking.reviewed_at = datetime.now(timezone.utc)
        record_audit(db, actor, "status_change", "resource_booking", booking.id)
        db.commit()
        db.refresh(booking)
        return resource_booking_output(db, booking)

    @app.post("/api/v1/admin/documents", response_model=StaffDocumentOutput, status_code=201, tags=["documents"])
    def create_staff_document(
        payload: StaffDocumentInput,
        actor: Annotated[AdminUser, Depends(document_manager)],
        db: Session = Depends(get_db),
    ):
        try:
            content = base64.b64decode(payload.content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(status_code=422, detail="Document content must be valid base64") from exc
        if not content or len(content) > 2_000_000:
            raise HTTPException(status_code=413, detail="Documents must be between 1 byte and 2 MB")
        filename = payload.filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
        title = payload.title.strip()
        document_type = payload.document_type.strip().lower()
        if not filename or not title or not document_type or any(ord(char) < 32 for char in filename):
            raise HTTPException(status_code=422, detail="Document title, type and filename must be valid")
        if any(ord(char) < 32 for char in title) or any(ord(char) < 32 for char in document_type):
            raise HTTPException(status_code=422, detail="Document title and type cannot contain control characters")
        document = StaffDocument(
            document_type=document_type,
            encrypted_payload=encrypt_text(json.dumps({
                "title": title,
                "filename": filename,
                "content_type": payload.content_type,
                "size_bytes": len(content),
                "content_base64": base64.b64encode(content).decode("ascii"),
            })),
            created_by_id=actor.id,
        )
        db.add(document)
        db.flush()
        record_audit(db, actor, "create", "staff_document", document.id)
        db.commit()
        db.refresh(document)
        return staff_document_output(document)

    @app.get("/api/v1/admin/documents", response_model=list[StaffDocumentOutput], tags=["documents"])
    def list_staff_documents(
        _: Annotated[AdminUser, Depends(document_manager)],
        document_type: str | None = Query(default=None, max_length=48),
        db: Session = Depends(get_db),
    ):
        query = select(StaffDocument)
        if document_type:
            query = query.where(StaffDocument.document_type == document_type.strip().lower())
        documents = db.scalars(query.order_by(StaffDocument.created_at.desc()).limit(200))
        return [staff_document_output(document) for document in documents]

    @app.get("/api/v1/admin/documents/{document_id}/download", tags=["documents"])
    def download_staff_document(
        document_id: int,
        actor: Annotated[AdminUser, Depends(document_manager)],
        db: Session = Depends(get_db),
    ):
        document = db.get(StaffDocument, document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Staff document not found")
        payload = json.loads(decrypt_text(document.encrypted_payload))
        try:
            content = base64.b64decode(payload["content_base64"], validate=True)
        except (ValueError, binascii.Error, KeyError) as exc:
            raise HTTPException(status_code=500, detail="Stored document could not be read") from exc
        record_audit(db, actor, "download", "staff_document", document.id)
        db.commit()
        filename = quote(payload["filename"], safe="")
        return Response(
            content=content,
            media_type=payload["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
            },
        )

    @app.post(
        "/api/v1/admin/governance/meetings",
        response_model=GovernanceMeetingOutput,
        status_code=201,
        tags=["governance"],
    )
    def create_governance_meeting(
        payload: GovernanceMeetingInput,
        actor: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Meeting title cannot be blank")
        meeting = GovernanceMeeting(
            title=title,
            meeting_date=payload.meeting_date,
            location=payload.location.strip(),
            status=payload.status,
            encrypted_minutes=encrypt_text(json.dumps({"minutes": payload.minutes.strip()})),
            created_by_id=actor.id,
            branch_id=validate_branch_assignment(db, payload.branch_id),
        )
        db.add(meeting)
        db.flush()
        record_audit(db, actor, "create", "governance_meeting", meeting.id)
        db.commit()
        db.refresh(meeting)
        return GovernanceMeetingOutput(
            id=meeting.id,
            title=meeting.title,
            meeting_date=meeting.meeting_date,
            location=meeting.location,
            status=meeting.status,
            minutes=json.loads(decrypt_text(meeting.encrypted_minutes))["minutes"],
            created_by_id=meeting.created_by_id,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
            branch_id=meeting.branch_id,
        )

    @app.get(
        "/api/v1/admin/governance/meetings",
        response_model=list[GovernanceMeetingOutput],
        tags=["governance"],
    )
    def list_governance_meetings(
        _: Annotated[AdminUser, Depends(pastoral_manager)],
        branch_id: int | None = None,
        db: Session = Depends(get_db),
    ):
        query = select(GovernanceMeeting)
        if branch_id is not None:
            query = query.where(GovernanceMeeting.branch_id == branch_id)
        meetings = db.scalars(
            query.order_by(GovernanceMeeting.meeting_date.desc(), GovernanceMeeting.id.desc())
            .limit(200)
        ).all()
        return [
            GovernanceMeetingOutput(
                id=meeting.id,
                title=meeting.title,
                meeting_date=meeting.meeting_date,
                location=meeting.location,
                status=meeting.status,
                minutes=json.loads(decrypt_text(meeting.encrypted_minutes))["minutes"],
                created_by_id=meeting.created_by_id,
                created_at=meeting.created_at,
                updated_at=meeting.updated_at,
                branch_id=meeting.branch_id,
            )
            for meeting in meetings
        ]

    @app.put(
        "/api/v1/admin/governance/meetings/{meeting_id}",
        response_model=GovernanceMeetingOutput,
        tags=["governance"],
    )
    def update_governance_meeting(
        meeting_id: int,
        payload: GovernanceMeetingInput,
        actor: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        meeting = db.get(GovernanceMeeting, meeting_id)
        if meeting is None:
            raise HTTPException(status_code=404, detail="Governance meeting not found")
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Meeting title cannot be blank")
        meeting.title = title
        meeting.meeting_date = payload.meeting_date
        meeting.location = payload.location.strip()
        meeting.status = payload.status
        meeting.encrypted_minutes = encrypt_text(json.dumps({"minutes": payload.minutes.strip()}))
        meeting.branch_id = validate_branch_assignment(db, payload.branch_id, meeting.branch_id)
        record_audit(db, actor, "update", "governance_meeting", meeting.id)
        db.commit()
        db.refresh(meeting)
        return GovernanceMeetingOutput(
            id=meeting.id,
            title=meeting.title,
            meeting_date=meeting.meeting_date,
            location=meeting.location,
            status=meeting.status,
            minutes=json.loads(decrypt_text(meeting.encrypted_minutes))["minutes"],
            created_by_id=meeting.created_by_id,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
            branch_id=meeting.branch_id,
        )

    @app.post(
        "/api/v1/admin/governance/meetings/{meeting_id}/resolutions",
        response_model=GovernanceResolutionOutput,
        status_code=201,
        tags=["governance"],
    )
    def create_governance_resolution(
        meeting_id: int,
        payload: GovernanceResolutionInput,
        actor: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        meeting = db.get(GovernanceMeeting, meeting_id)
        if meeting is None:
            raise HTTPException(status_code=404, detail="Governance meeting not found")
        title = payload.title.strip()
        description = payload.description.strip()
        if not title or not description:
            raise HTTPException(status_code=422, detail="Resolution title and description cannot be blank")
        resolution = GovernanceResolution(
            meeting_id=meeting.id,
            encrypted_content=encrypt_text(json.dumps({"title": title, "description": description})),
            status="proposed",
            due_date=payload.due_date,
            created_by_id=actor.id,
        )
        db.add(resolution)
        db.flush()
        record_audit(db, actor, "create", "governance_resolution", resolution.id)
        db.commit()
        db.refresh(resolution)
        content = json.loads(decrypt_text(resolution.encrypted_content))
        return GovernanceResolutionOutput(
            id=resolution.id,
            meeting_id=resolution.meeting_id,
            title=content["title"],
            description=content["description"],
            status=resolution.status,
            due_date=resolution.due_date,
            created_by_id=resolution.created_by_id,
            created_at=resolution.created_at,
            updated_at=resolution.updated_at,
        )

    @app.get(
        "/api/v1/admin/governance/meetings/{meeting_id}/resolutions",
        response_model=list[GovernanceResolutionOutput],
        tags=["governance"],
    )
    def list_governance_resolutions(
        meeting_id: int,
        _: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        if db.get(GovernanceMeeting, meeting_id) is None:
            raise HTTPException(status_code=404, detail="Governance meeting not found")
        resolutions = db.scalars(
            select(GovernanceResolution)
            .where(GovernanceResolution.meeting_id == meeting_id)
            .order_by(GovernanceResolution.created_at, GovernanceResolution.id)
        ).all()
        return [
            GovernanceResolutionOutput(
                id=resolution.id,
                meeting_id=resolution.meeting_id,
                title=(content := json.loads(decrypt_text(resolution.encrypted_content)))["title"],
                description=content["description"],
                status=resolution.status,
                due_date=resolution.due_date,
                created_by_id=resolution.created_by_id,
                created_at=resolution.created_at,
                updated_at=resolution.updated_at,
            )
            for resolution in resolutions
        ]

    @app.patch(
        "/api/v1/admin/governance/resolutions/{resolution_id}/status",
        response_model=GovernanceResolutionOutput,
        tags=["governance"],
    )
    def update_governance_resolution_status(
        resolution_id: int,
        payload: GovernanceResolutionStatusInput,
        actor: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        resolution = db.get(GovernanceResolution, resolution_id)
        if resolution is None:
            raise HTTPException(status_code=404, detail="Governance resolution not found")
        allowed_transitions = {
            "proposed": {"approved", "rejected"},
            "approved": {"in_progress", "completed"},
            "in_progress": {"completed"},
        }
        if payload.status not in allowed_transitions.get(resolution.status, set()):
            raise HTTPException(
                status_code=409,
                detail=f"Cannot change a {resolution.status} resolution to {payload.status}",
            )
        resolution.status = payload.status
        record_audit(db, actor, "status_change", "governance_resolution", resolution.id)
        db.commit()
        db.refresh(resolution)
        content = json.loads(decrypt_text(resolution.encrypted_content))
        return GovernanceResolutionOutput(
            id=resolution.id,
            meeting_id=resolution.meeting_id,
            title=content["title"],
            description=content["description"],
            status=resolution.status,
            due_date=resolution.due_date,
            created_by_id=resolution.created_by_id,
            created_at=resolution.created_at,
            updated_at=resolution.updated_at,
        )

    @app.post("/api/v1/admin/certificates", response_model=MemberCertificateOutput, status_code=201, tags=["certificates"])
    def create_member_certificate(
        payload: MemberCertificateInput,
        actor: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        active_member(db, payload.member_id)
        certificate_type = payload.certificate_type.strip()
        certificate_number = payload.certificate_number.strip()
        if not certificate_type or not certificate_number:
            raise HTTPException(status_code=422, detail="Certificate type and number cannot be blank")
        certificate = MemberCertificate(
            member_id=payload.member_id,
            certificate_type=certificate_type,
            issued_on=payload.issued_on,
            certificate_number=certificate_number,
            encrypted_details=encrypt_text(json.dumps({"details": payload.details.strip()})),
            issued_by_id=actor.id,
        )
        db.add(certificate)
        try:
            db.flush()
            record_audit(db, actor, "issue", "member_certificate", certificate.id)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Certificate number is already in use") from exc
        db.refresh(certificate)
        return member_certificate_output(db, certificate)

    @app.get("/api/v1/admin/certificates", response_model=list[MemberCertificateOutput], tags=["certificates"])
    def list_member_certificates(
        _: Annotated[AdminUser, Depends(pastoral_manager)],
        member_id: int | None = Query(default=None, ge=1),
        db: Session = Depends(get_db),
    ):
        query = select(MemberCertificate)
        if member_id:
            query = query.where(MemberCertificate.member_id == member_id)
        certificates = db.scalars(query.order_by(MemberCertificate.issued_on.desc()).limit(500))
        return [member_certificate_output(db, certificate) for certificate in certificates]

    @app.get("/api/v1/admin/certificates/{certificate_id}/download", tags=["certificates"])
    def download_member_certificate(
        certificate_id: int,
        _: Annotated[AdminUser, Depends(pastoral_manager)],
        db: Session = Depends(get_db),
    ):
        certificate = db.get(MemberCertificate, certificate_id)
        if certificate is None:
            raise HTTPException(status_code=404, detail="Certificate not found")
        output = member_certificate_output(db, certificate)
        pdf = render_certificate_pdf(
            church_name="Bwala Deliverance and Healing Ministries International",
            certificate_type=output.certificate_type,
            member_name=output.member_name,
            details=output.details,
            issued_on=output.issued_on.strftime("%d %B %Y"),
            certificate_number=output.certificate_number,
        )
        safe_number = re.sub(r"[^A-Za-z0-9_-]", "-", output.certificate_number).strip("-") or str(certificate.id)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="certificate-{safe_number}.pdf"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return app


app = create_app()