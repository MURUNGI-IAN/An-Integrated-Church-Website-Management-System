import json
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AdminUser, AuditLog, AvailabilityInvite, Branch, ChildAttendance, ChildProfile, ChurchEvent, ChurchResource, ContactInquiry, EmergencyAlert, EventRegistration, FinanceBudget, FinanceEntry, FinancePledge, GovernanceMeeting, GovernanceResolution, GroupWaitlist, Member, MemberAttendance, MemberCertificate, MemberCommunicationConsent, NewsletterSubscriber, OfferingCountBatch, PastoralCareTask, PrayerRequest, ResourceBooking, RotaAssignment, Sermon, SmallGroup, StaffDocument, VisitorVisit, VolunteerAvailability
from app.security import decrypt_text, encrypt_text
from tests.conftest import provision_user


def test_public_sermon_search_hides_drafts(client: TestClient) -> None:
    with Session(client.app.state.database_engine) as db:
        db.add_all([
            Sermon(title="Hope in the valley", speaker="Pastor Grace", scripture="Psalm 23", is_published=True),
            Sermon(title="Private draft", speaker="Pastor Grace", scripture="Psalm 1", is_published=False),
        ])
        db.commit()

    response = client.get("/api/v1/sermons", params={"q": "valley", "scripture": "23"})
    assert response.status_code == 200
    assert [sermon["title"] for sermon in response.json()] == ["Hope in the valley"]


def test_cms_requires_provisioned_staff_and_publication(client: TestClient) -> None:
    payload = {"slug": "about-us", "title": "About us", "body": "A church family.", "is_published": True}
    assert client.post("/api/v1/admin/pages", json=payload).status_code == 401

    token = provision_user(client, "editor@example.org", role="editor")
    response = client.post("/api/v1/admin/pages", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 201, response.text
    page_id = response.json()["id"]
    assert client.get("/api/v1/pages/about-us").json()["body"] == "A church family."
    assert [page["slug"] for page in client.get("/api/v1/pages").json()] == ["about-us"]

    draft = {**payload, "slug": "private-draft", "is_published": False}
    created_draft = client.post("/api/v1/admin/pages", json=draft, headers={"Authorization": f"Bearer {token}"})
    assert created_draft.status_code == 201
    assert client.get("/api/v1/pages/private-draft").status_code == 404
    assert [page["slug"] for page in client.get("/api/v1/pages").json()] == ["about-us"]

    assert client.put(f"/api/v1/admin/pages/{page_id}", json=payload, headers={"Authorization": f"Bearer {token}"}).status_code == 200

    assert client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    admin_token = provision_user(client, "admin@example.org")
    logs = client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert logs.status_code == 200
    assert [item["action"] for item in logs.json()].count("create") == 2
    assert any(item["entity_type"] == "page" for item in logs.json())


def test_event_registration_checks_consent_duplicates_and_capacity(client: TestClient) -> None:
    with Session(client.app.state.database_engine) as db:
        event = ChurchEvent(
            title="Community day",
            location="Masaka",
            starts_at=datetime.now(timezone.utc) + timedelta(days=2),
            capacity=1,
            is_published=True,
        )
        db.add(event)
        db.commit()
        event_id = event.id

    url = f"/api/v1/events/{event_id}/registrations"
    assert client.post(url, json={"name": "A Member", "email": "member@example.org", "consent": False}).status_code == 422

    registration = {"name": "A Member", "email": " Member@Example.org ", "consent": True}
    first = client.post(url, json=registration)
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "registered"
    assert client.post(url, json=registration).status_code == 409
    full = client.post(url, json={"name": "Another Guest", "email": "guest@example.org", "consent": True})
    assert full.status_code == 409

    with Session(client.app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(EventRegistration)) == 1
        stored = db.scalar(select(EventRegistration).where(EventRegistration.event_id == event_id))
        assert stored is not None
        assert "member@example.org" not in stored.encrypted_payload
        assert json.loads(decrypt_text(stored.encrypted_payload)) == {"name": "A Member", "email": "member@example.org"}

    editor_token = provision_user(client, "event-editor@example.org", role="editor")
    attendees = client.get(
        f"/api/v1/admin/events/{event_id}/registrations",
        headers={"Authorization": f"Bearer {editor_token}"},
    )
    assert attendees.status_code == 200
    assert attendees.json()[0]["email"] == "member@example.org"


def test_prayer_request_is_encrypted_and_pastor_only(client: TestClient) -> None:
    response = client.post("/api/v1/prayer-requests", json={
        "name": "Test Member",
        "contact": "+256700000000",
        "message": "Please pray for my family.",
        "consent": True,
    })
    assert response.status_code == 201, response.text
    assert "message" not in response.json()

    with Session(client.app.state.database_engine) as db:
        request = db.get(PrayerRequest, response.json()["id"])
        assert request is not None
        assert "Please pray for my family." not in request.encrypted_payload
        assert json.loads(decrypt_text(request.encrypted_payload))["message"] == "Please pray for my family."

    editor_token = provision_user(client, "editor@example.org", role="editor")
    headers = {"Authorization": f"Bearer {editor_token}"}
    assert client.get("/api/v1/admin/prayer-requests", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/prayer-requests").status_code == 401

    pastor_token = provision_user(client, "pastor@example.org", role="pastor")
    pastoral = client.get("/api/v1/admin/prayer-requests", headers={"Authorization": f"Bearer {pastor_token}"})
    assert pastoral.status_code == 200, pastoral.text
    assert pastoral.json()[0]["message"] == "Please pray for my family."


def test_newsletter_requires_consent_and_is_idempotent(client: TestClient) -> None:
    url = "/api/v1/newsletter"
    payload = {"email": "Guest@Example.org", "consent": False}
    assert client.post(url, json=payload).status_code == 422

    payload["consent"] = True
    assert client.post(url, json=payload).status_code == 201
    assert client.post(url, json=payload).status_code == 201

    with Session(client.app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(NewsletterSubscriber)) == 1


def test_contact_inquiries_are_encrypted_and_restricted_to_pastors_and_admins(client: TestClient) -> None:
    payload = {
        "name": "Guest Member",
        "email": " Guest@Example.org ",
        "subject": "Service times",
        "message": "Could you share this week's schedule?",
        "consent": True,
    }
    url = "/api/v1/contact"
    assert client.post(url, json={**payload, "consent": False}).status_code == 422
    created = client.post(url, json=payload)
    assert created.status_code == 201, created.text

    with Session(client.app.state.database_engine) as db:
        inquiry = db.get(ContactInquiry, created.json()["id"])
        assert inquiry is not None
        assert "Guest@Example.org" not in inquiry.encrypted_payload
        assert json.loads(decrypt_text(inquiry.encrypted_payload)) == {
            "name": "Guest Member",
            "email": "guest@example.org",
            "subject": "Service times",
            "message": "Could you share this week's schedule?",
        }

    assert client.get("/api/v1/admin/contact-inquiries").status_code == 401
    editor_token = provision_user(client, "contact-editor@example.org", role="editor")
    assert client.get("/api/v1/admin/contact-inquiries", headers={
        "Authorization": f"Bearer {editor_token}",
    }).status_code == 403

    pastor_token = provision_user(client, "contact-pastor@example.org", role="pastor")
    headers = {"Authorization": f"Bearer {pastor_token}"}
    listing = client.get("/api/v1/admin/contact-inquiries", headers=headers)
    assert listing.status_code == 200, listing.text
    assert listing.json()[0]["email"] == "guest@example.org"
    updated = client.patch(
        f"/api/v1/admin/contact-inquiries/{created.json()['id']}/status?new_status=follow_up",
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "follow_up"


def test_member_create_requires_consent_and_encrypts_profile(client: TestClient) -> None:
    token = provision_user(client, "member-admin@example.org")
    headers = {"Authorization": f"Bearer {token}"}
    url = "/api/v1/admin/members"
    profile = {"name": "  Alex Member ", "email": " Alex@Example.org ", "phone": "+256700000001"}

    assert client.post(url, json={**profile, "consent_confirmed": False}, headers=headers).status_code == 422
    created = client.post(url, json={**profile, "consent_confirmed": True}, headers=headers)
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Alex Member"
    assert created.json()["email"] == "alex@example.org"
    assert created.json()["status"] == "active"
    assert client.post(url, json={**profile, "consent_confirmed": True}, headers=headers).status_code == 409

    with Session(client.app.state.database_engine) as db:
        member = db.get(Member, created.json()["id"])
        assert member is not None
        assert "Alex Member" not in member.encrypted_profile
        assert "alex@example.org" not in member.encrypted_profile
        assert json.loads(decrypt_text(member.encrypted_profile)) == {
            "name": "Alex Member",
            "email": "alex@example.org",
            "phone": "+256700000001",
        }


def test_member_registry_access_filters_updates_and_audit(client: TestClient) -> None:
    editor_token = provision_user(client, "member-editor@example.org", role="editor")
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    assert client.get("/api/v1/admin/members", headers=editor_headers).status_code == 403

    pastor_token = provision_user(client, "member-pastor@example.org", role="pastor")
    headers = {"Authorization": f"Bearer {pastor_token}"}
    created = client.post("/api/v1/admin/members", json={
        "name": "Jamie Example", "email": "jamie@example.org", "phone": None, "consent_confirmed": True,
    }, headers=headers)
    assert created.status_code == 201, created.text
    member_id = created.json()["id"]
    assert client.get("/api/v1/admin/members", headers=headers).json()[0]["id"] == member_id
    assert client.get(f"/api/v1/admin/members/{member_id}", headers=headers).status_code == 200

    updated = client.put(f"/api/v1/admin/members/{member_id}", json={
        "name": "Jamie Updated", "email": "new@example.org", "phone": "+256700000002",
    }, headers=headers)
    assert updated.status_code == 200
    deactivated = client.patch(
        f"/api/v1/admin/members/{member_id}/status?new_status=inactive", headers=headers,
    )
    assert deactivated.status_code == 200
    assert client.get("/api/v1/admin/members", headers=headers).json() == []
    inactive = client.get("/api/v1/admin/members?status=inactive", headers=headers)
    assert inactive.status_code == 200
    assert inactive.json()[0]["name"] == "Jamie Updated"

    admin_token = provision_user(client, "member-audit@example.org")
    logs = client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert [log["action"] for log in logs.json()].count("create") == 1
    assert any(log["action"] == "status_change" and log["entity_type"] == "member" for log in logs.json())


def test_member_attendance_check_in_duplicate_checkout_and_access(client: TestClient) -> None:
    admin_token = provision_user(client, "attendance-admin@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member = client.post("/api/v1/admin/members", json={
        "name": "Taylor Member", "email": None, "phone": None, "consent_confirmed": True,
    }, headers=admin_headers)
    assert member.status_code == 201, member.text
    member_id = member.json()["id"]
    url = "/api/v1/admin/attendance"
    payload = {
        "member_id": member_id,
        "service_name": "Sunday Worship",
        "service_date": "2026-10-11",
        "check_in_method": "phone",
    }

    assert client.post(url, json=payload).status_code == 401
    editor_token = provision_user(client, "attendance-editor@example.org", role="editor")
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    attendance_members = client.get(f"{url}/members", headers=editor_headers)
    assert attendance_members.status_code == 200
    assert attendance_members.json() == [{"id": member_id, "name": "Taylor Member"}]
    checked_in = client.post(url, json=payload, headers=editor_headers)
    assert checked_in.status_code == 201, checked_in.text
    assert checked_in.json()["member_name"] == "Taylor Member"
    assert checked_in.json()["checked_out_at"] is None
    assert client.post(url, json=payload, headers=admin_headers).status_code == 409

    listing = client.get(f"{url}?service_date=2026-10-11", headers=editor_headers)
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 1
    assert client.get(f"{url}?service_date=2026-10-12", headers=editor_headers).json() == []

    checked_out = client.patch(f"{url}/{checked_in.json()['id']}/check-out", headers=editor_headers)
    assert checked_out.status_code == 200
    assert checked_out.json()["checked_out_at"] is not None

    with Session(client.app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(MemberAttendance)) == 1
        audit_actions = db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "member_attendance")).all()
        assert audit_actions == ["check_in", "check_out"]


def test_three_recorded_sundays_create_one_confidential_attendance_care_task(client: TestClient) -> None:
    admin_token = provision_user(client, "attendance-care-admin@example.org")
    headers = {"Authorization": f"Bearer {admin_token}"}

    def register_member(name: str) -> int:
        response = client.post("/api/v1/admin/members", json={
            "name": name, "email": None, "phone": None, "consent_confirmed": True,
        }, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    missed_member_id = register_member("Member Missing Three Sundays")
    occasional_member_id = register_member("Member Attended Once")
    regular_member_id = register_member("Member Attended Every Sunday")
    sunday_dates = ["2026-09-27", "2026-10-04", "2026-10-11"]
    with Session(client.app.state.database_engine) as db:
        for member_id in (missed_member_id, occasional_member_id, regular_member_id):
            member = db.get(Member, member_id)
            assert member is not None
            member.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        db.commit()

    url = "/api/v1/admin/attendance"
    for service_date in sunday_dates:
        present_ids = [regular_member_id]
        if service_date == "2026-10-04":
            present_ids.append(occasional_member_id)
        for member_id in present_ids:
            response = client.post(url, json={
                "member_id": member_id,
                "service_name": "Sunday Worship",
                "service_date": service_date,
                "check_in_method": "manual",
            }, headers=headers)
            assert response.status_code == 201, response.text
        if service_date != sunday_dates[-1]:
            with Session(client.app.state.database_engine) as db:
                assert db.scalar(select(func.count()).select_from(PastoralCareTask).where(
                    PastoralCareTask.member_id == missed_member_id,
                    PastoralCareTask.care_type == "attendance",
                )) == 0

    with Session(client.app.state.database_engine) as db:
        missed_tasks = db.scalars(select(PastoralCareTask).where(
            PastoralCareTask.member_id == missed_member_id,
            PastoralCareTask.care_type == "attendance",
        )).all()
        assert len(missed_tasks) == 1
        task = missed_tasks[0]
        assert task.attendance_alert_key == ",".join(sunday_dates)
        assert "Member Missing Three" not in task.encrypted_details
        assert "2026-09-27, 2026-10-04, 2026-10-11" in json.loads(decrypt_text(task.encrypted_details))["notes"]
        assert db.scalar(select(func.count()).select_from(PastoralCareTask).where(
            PastoralCareTask.member_id == occasional_member_id,
            PastoralCareTask.care_type == "attendance",
        )) == 0
        assert db.scalar(select(func.count()).select_from(PastoralCareTask).where(
            PastoralCareTask.member_id == regular_member_id,
            PastoralCareTask.care_type == "attendance",
        )) == 0
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_type == "pastoral_care_task",
            AuditLog.action == "attendance_alert_created",
        )) == 1


def test_child_profiles_require_consent_encrypt_data_and_restrict_access(client: TestClient) -> None:
    admin_token = provision_user(client, "child-admin@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    def register_member(name: str) -> int:
        response = client.post("/api/v1/admin/members", json={
            "name": name, "email": None, "phone": None, "consent_confirmed": True,
        }, headers=admin_headers)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    guardian_id = register_member("Primary Guardian")
    pickup_id = register_member("Authorized Pickup")
    payload = {
        "name": "Child Example",
        "primary_guardian_id": guardian_id,
        "authorized_pickup_member_ids": [pickup_id],
        "consent_confirmed": True,
    }
    url = "/api/v1/admin/children"
    assert client.post(url, json={**payload, "consent_confirmed": False}, headers=admin_headers).status_code == 422
    assert client.post(url, json=payload).status_code == 401

    editor_token = provision_user(client, "child-editor@example.org", role="editor")
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    assert client.post(url, json=payload, headers=editor_headers).status_code == 403

    created = client.post(url, json=payload, headers=admin_headers)
    assert created.status_code == 201, created.text
    assert created.json()["name"] == "Child Example"
    assert created.json()["authorized_pickup_member_ids"] == [pickup_id]
    assert client.get(url, headers=editor_headers).status_code == 403

    with Session(client.app.state.database_engine) as db:
        child = db.get(ChildProfile, created.json()["id"])
        assert child is not None
        assert "Child Example" not in child.encrypted_profile
        assert json.loads(decrypt_text(child.encrypted_profile)) == {"name": "Child Example"}


def test_child_check_in_and_pickup_require_authorized_active_members(client: TestClient) -> None:
    admin_token = provision_user(client, "child-attendance-admin@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    def register_member(name: str) -> int:
        response = client.post("/api/v1/admin/members", json={
            "name": name, "email": None, "phone": None, "consent_confirmed": True,
        }, headers=admin_headers)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    guardian_id = register_member("Child Guardian")
    pickup_id = register_member("Child Pickup")
    stranger_id = register_member("Unlisted Adult")
    child = client.post("/api/v1/admin/children", json={
        "name": "Safeguarded Child",
        "primary_guardian_id": guardian_id,
        "authorized_pickup_member_ids": [pickup_id],
        "consent_confirmed": True,
    }, headers=admin_headers)
    assert child.status_code == 201, child.text
    child_id = child.json()["id"]
    url = "/api/v1/admin/child-attendance"
    service = {"child_id": child_id, "service_name": "Sunday School", "service_date": "2026-10-11"}

    unauthorized = client.post(url, json={**service, "checked_in_by_member_id": stranger_id}, headers=admin_headers)
    assert unauthorized.status_code == 403
    checked_in = client.post(url, json={**service, "checked_in_by_member_id": guardian_id}, headers=admin_headers)
    assert checked_in.status_code == 201, checked_in.text
    assert checked_in.json()["checked_in_by_name"] == "Child Guardian"
    assert client.post(url, json={**service, "checked_in_by_member_id": guardian_id}, headers=admin_headers).status_code == 409

    listing = client.get(f"{url}?service_date=2026-10-11", headers=admin_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    attendance_id = checked_in.json()["id"]
    checkout_url = f"{url}/{attendance_id}/check-out"
    assert client.patch(checkout_url, json={"checked_out_by_member_id": stranger_id}, headers=admin_headers).status_code == 403
    checked_out = client.patch(checkout_url, json={"checked_out_by_member_id": pickup_id}, headers=admin_headers)
    assert checked_out.status_code == 200, checked_out.text
    assert checked_out.json()["checked_out_by_name"] == "Child Pickup"
    assert checked_out.json()["checked_out_at"] is not None
    assert client.patch(checkout_url, json={"checked_out_by_member_id": pickup_id}, headers=admin_headers).status_code == 409

    with Session(client.app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(ChildAttendance)) == 1
        audit_actions = db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "child_attendance")).all()
        assert audit_actions == ["check_in", "check_out"]


def test_emergency_alerts_are_staff_managed_active_only_and_expiring(client: TestClient) -> None:
    url = "/api/v1/admin/alerts"
    assert client.get(url).status_code == 401
    editor_token = provision_user(client, "alert-editor@example.org", role="editor")
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    assert client.post(url, json={"title": "No access", "message": "Not allowed."}, headers=editor_headers).status_code == 403
    pastor_token = provision_user(client, "alert-pastor@example.org", role="pastor")
    headers = {"Authorization": f"Bearer {pastor_token}"}
    future_expiry = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    active = client.post(url, json={
        "title": "Service location update",
        "message": "Today's gathering is at the main hall.",
        "expires_at": future_expiry,
        "is_active": True,
    }, headers=headers)
    assert active.status_code == 201, active.text
    alert_id = active.json()["id"]
    inactive = client.post(url, json={
        "title": "Draft notice",
        "message": "This is not published.",
        "is_active": False,
    }, headers=headers)
    assert inactive.status_code == 201
    assert [alert["title"] for alert in client.get("/api/v1/alerts/current").json()] == ["Service location update"]

    with Session(client.app.state.database_engine) as db:
        alert = db.get(EmergencyAlert, alert_id)
        assert alert is not None
        alert.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    assert client.get("/api/v1/alerts/current").json() == []

    expired = client.post(url, json={
        "title": "Expired notice",
        "message": "This must not publish.",
        "expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        "is_active": True,
    }, headers=headers)
    assert expired.status_code == 422

    deactivated = client.patch(f"{url}/{alert_id}/status?new_status=inactive", headers=headers)
    assert deactivated.status_code == 200
    assert client.get("/api/v1/alerts/current").json() == []

    admin_token = provision_user(client, "alert-audit@example.org")
    logs = client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert any(log["entity_type"] == "emergency_alert" and log["action"] == "status_change" for log in logs.json())


def test_volunteer_availability_and_fair_rota_generation(client: TestClient) -> None:
    editor_token = provision_user(client, "rota-editor@example.org", role="editor")
    headers = {"Authorization": f"Bearer {editor_token}"}
    admin_token = provision_user(client, "rota-admin@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member_ids = []
    for name in ("Volunteer One", "Volunteer Two", "Volunteer Three"):
        member = client.post("/api/v1/admin/members", json={
            "name": name, "email": None, "phone": None, "consent_confirmed": True,
        }, headers=admin_headers)
        assert member.status_code == 201, member.text
        member_ids.append(member.json()["id"])

    availability_url = "/api/v1/admin/volunteer-availability"
    assert client.get(f"{availability_url}?service_date=2026-10-18").status_code == 401
    for member_id in member_ids:
        response = client.post(availability_url, json={
            "member_id": member_id,
            "service_name": "Sunday Worship",
            "service_date": "2026-10-18",
            "is_available": True,
        }, headers=headers)
        assert response.status_code == 200, response.text

    generation_url = "/api/v1/admin/rota/generate"
    first = client.post(generation_url, json={
        "service_name": "Sunday Worship",
        "service_date": "2026-10-18",
        "role_names": ["Usher", "Sound desk"],
    }, headers=headers)
    assert first.status_code == 201, first.text
    first_member_ids = {assignment["member_id"] for assignment in first.json()}
    assert len(first_member_ids) == 2
    assert client.post(generation_url, json={
        "service_name": "Sunday Worship",
        "service_date": "2026-10-18",
        "role_names": ["Usher"],
    }, headers=headers).status_code == 409

    for member_id in member_ids:
        response = client.post(availability_url, json={
            "member_id": member_id,
            "service_name": "Sunday Worship",
            "service_date": "2026-10-25",
            "is_available": True,
        }, headers=headers)
        assert response.status_code == 200
    second = client.post(generation_url, json={
        "service_name": "Sunday Worship",
        "service_date": "2026-10-25",
        "role_names": ["Usher"],
    }, headers=headers)
    assert second.status_code == 201
    assert second.json()[0]["member_id"] == next(iter(set(member_ids) - first_member_ids))
    assert len(client.get("/api/v1/admin/rota?service_date=2026-10-18", headers=headers).json()) == 2

    insufficient = client.post(generation_url, json={
        "service_name": "Sunday Worship",
        "service_date": "2026-11-01",
        "role_names": ["Usher", "Sound desk"],
    }, headers=headers)
    assert insufficient.status_code == 409

    with Session(client.app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(VolunteerAvailability)) == 6
        assert db.scalar(select(func.count()).select_from(RotaAssignment)) == 3
        assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_type == "rota_assignment")) == 3


def test_volunteer_availability_invites_are_hashed_single_use_and_expiring(client: TestClient) -> None:
    admin_token = provision_user(client, "availability-invite-admin@example.org")
    headers = {"Authorization": f"Bearer {admin_token}"}
    member = client.post("/api/v1/admin/members", json={
        "name": "Invited Volunteer", "email": "invitee@example.org", "phone": "+256700000100", "consent_confirmed": True,
    }, headers=headers)
    assert member.status_code == 201, member.text
    member_id = member.json()["id"]
    invite_url = "/api/v1/admin/volunteer-availability/invites"
    invite_request = {
        "member_id": member_id,
        "service_name": "Sunday Worship",
        "service_date": "2026-10-18",
    }
    assert client.post(invite_url, json=invite_request).status_code == 401
    created = client.post(invite_url, json=invite_request, headers=headers)
    assert created.status_code == 201, created.text
    token = created.json()["token"]

    with Session(client.app.state.database_engine) as db:
        invite = db.scalar(select(AvailabilityInvite))
        assert invite is not None
        assert invite.token_digest != token
        assert token not in invite.token_digest

    inspect_url = "/api/v1/volunteer-availability/invites/inspect"
    details = client.post(inspect_url, json={"token": token})
    assert details.status_code == 200, details.text
    assert details.json() == {"service_name": "Sunday Worship", "service_date": "2026-10-18"}
    response_url = "/api/v1/volunteer-availability/respond"
    recorded = client.post(response_url, json={"token": token, "is_available": False})
    assert recorded.status_code == 200, recorded.text
    assert client.post(response_url, json={"token": token, "is_available": True}).status_code == 404
    assert client.post(inspect_url, json={"token": token}).status_code == 404

    with Session(client.app.state.database_engine) as db:
        availability = db.scalar(select(VolunteerAvailability))
        assert availability is not None
        assert availability.member_id == member_id
        assert availability.is_available is False
        assert availability.updated_by_id is None

    expiring = client.post(invite_url, json={**invite_request, "service_date": "2026-10-25"}, headers=headers)
    assert expiring.status_code == 201
    with Session(client.app.state.database_engine) as db:
        expired_invite = db.scalar(select(AvailabilityInvite).where(AvailabilityInvite.id != invite.id))
        assert expired_invite is not None
        expired_invite.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    expired_token = expiring.json()["token"]
    assert client.post(inspect_url, json={"token": expired_token}).status_code == 410
    assert client.post(response_url, json={"token": expired_token, "is_available": True}).status_code == 410


def test_visitor_visit_requires_consent_encrypts_contact_and_tracks_followup(client: TestClient) -> None:
    url = "/api/v1/visitors"
    payload = {
        "name": "First-time Visitor",
        "contact": " Visitor@Example.org ",
        "visit_date": "2026-10-25",
        "consent": True,
    }
    assert client.post(url, json={**payload, "consent": False}).status_code == 422
    assert client.post(url, json={**payload, "contact": "not a contact"}).status_code == 422
    created = client.post(url, json=payload)
    assert created.status_code == 201, created.text
    assert "name" not in created.json() and "contact" not in created.json()

    with Session(client.app.state.database_engine) as db:
        visit = db.get(VisitorVisit, created.json()["id"])
        assert visit is not None
        assert "Visitor@Example.org" not in visit.encrypted_payload
        assert json.loads(decrypt_text(visit.encrypted_payload)) == {
            "name": "First-time Visitor",
            "contact": "visitor@example.org",
            "visit_date": "2026-10-25",
        }

    assert client.get("/api/v1/admin/visitors").status_code == 401
    editor_token = provision_user(client, "visitor-editor@example.org", role="editor")
    assert client.get("/api/v1/admin/visitors", headers={
        "Authorization": f"Bearer {editor_token}",
    }).status_code == 403

    pastor_token = provision_user(client, "visitor-pastor@example.org", role="pastor")
    headers = {"Authorization": f"Bearer {pastor_token}"}
    listed = client.get("/api/v1/admin/visitors", headers=headers)
    assert listed.status_code == 200, listed.text
    assert listed.json()[0]["contact"] == "visitor@example.org"
    updated = client.patch(
        f"/api/v1/admin/visitors/{created.json()['id']}/status?new_status=contacted",
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "contacted"

    admin_token = provision_user(client, "visitor-audit@example.org")
    logs = client.get("/api/v1/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert any(log["entity_type"] == "visitor_visit" and log["action"] == "status_change" for log in logs.json())


def test_communication_consent_is_explicit_channel_scoped_and_audited(client: TestClient) -> None:
    admin_token = provision_user(client, "consent-admin@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    member = client.post("/api/v1/admin/members", json={
        "name": "Consenting Member",
        "email": "consenting@example.org",
        "phone": "+256700000200",
        "consent_confirmed": True,
    }, headers=admin_headers)
    assert member.status_code == 201, member.text
    member_id = member.json()["id"]
    url = f"/api/v1/admin/members/{member_id}/communication-consents"

    defaults = client.get(url, headers=admin_headers)
    assert defaults.status_code == 200
    assert {item["channel"]: item["is_consented"] for item in defaults.json()} == {"email": False, "sms": False}
    assert all(item["updated_at"] is None for item in defaults.json())

    editor_token = provision_user(client, "consent-editor@example.org", role="editor")
    assert client.get(url, headers={"Authorization": f"Bearer {editor_token}"}).status_code == 403
    opted_in = client.put(url, json={
        "preferences": [
            {"channel": "email", "is_consented": True, "consent_source": "paper_form"},
            {"channel": "sms", "is_consented": True, "consent_source": "in_person"},
        ],
    }, headers=admin_headers)
    assert opted_in.status_code == 200, opted_in.text
    assert all(item["consented_at"] is not None for item in opted_in.json())
    assert {item["channel"]: item["consent_source"] for item in opted_in.json()} == {
        "email": "paper_form", "sms": "in_person",
    }

    no_phone = client.post("/api/v1/admin/members", json={
        "name": "Email Only", "email": "email-only@example.org", "phone": None, "consent_confirmed": True,
    }, headers=admin_headers)
    assert no_phone.status_code == 201
    invalid_sms = client.put(f"/api/v1/admin/members/{no_phone.json()['id']}/communication-consents", json={
        "preferences": [{"channel": "sms", "is_consented": True, "consent_source": "in_person"}],
    }, headers=admin_headers)
    assert invalid_sms.status_code == 422
    invalid_source = client.put(url, json={
        "preferences": [{"channel": "email", "is_consented": True, "consent_source": "not_provided"}],
    }, headers=admin_headers)
    assert invalid_source.status_code == 422

    revoked = client.put(url, json={
        "preferences": [{"channel": "email", "is_consented": False, "consent_source": "member_request"}],
    }, headers=admin_headers)
    assert revoked.status_code == 200
    assert revoked.json()[0]["is_consented"] is False
    assert revoked.json()[0]["consented_at"] is None
    with Session(client.app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(MemberCommunicationConsent)) == 2
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_type == "member", AuditLog.action == "communication_consent_update",
        )) == 2


def test_small_group_finder_filters_published_groups_and_approximate_distance(client: TestClient) -> None:
    token = provision_user(client, "group-editor@example.org", role="editor")
    headers = {"Authorization": f"Bearer {token}"}
    base = {
        "description": "A welcoming group for shared study and prayer.",
        "meeting_time": "4:00 PM",
        "latitude": -0.305,
        "longitude": 31.700,
        "is_published": True,
    }
    open_group = client.post("/api/v1/admin/groups", json={
        **base,
        "name": "Nyendo Fellowship",
        "meeting_area": "Nyendo",
        "meeting_day": "Sunday",
        "age_group": "Adults",
        "is_open": True,
    }, headers=headers)
    assert open_group.status_code == 201, open_group.text
    closed_group = client.post("/api/v1/admin/groups", json={
        **base,
        "name": "Kimaanya Youth Circle",
        "meeting_area": "Kimaanya",
        "meeting_day": "Friday",
        "age_group": "Youth",
        "latitude": -0.325,
        "longitude": 31.730,
        "is_open": False,
    }, headers=headers)
    assert closed_group.status_code == 201, closed_group.text
    unpublished = client.post("/api/v1/admin/groups", json={
        **base,
        "name": "Private draft",
        "meeting_area": "Masaka",
        "meeting_day": "Saturday",
        "age_group": "All ages",
        "is_published": False,
    }, headers=headers)
    assert unpublished.status_code == 201

    all_groups = client.get("/api/v1/groups")
    assert all_groups.status_code == 200
    assert {group["name"] for group in all_groups.json()} == {"Nyendo Fellowship", "Kimaanya Youth Circle"}
    assert all_groups.json()[0]["coordinates_approximate"] is True
    assert "address" not in all_groups.json()[0]
    assert [group["name"] for group in client.get("/api/v1/groups?meeting_day=Friday&age_group=Youth").json()] == ["Kimaanya Youth Circle"]
    assert [group["name"] for group in client.get("/api/v1/groups?open_only=true").json()] == ["Nyendo Fellowship"]
    nearby = client.get("/api/v1/groups?near_latitude=-0.305&near_longitude=31.700&radius_km=2")
    assert [group["name"] for group in nearby.json()] == ["Nyendo Fellowship"]
    assert client.get("/api/v1/groups?near_latitude=-0.305").status_code == 422

    waitlist_url = f"/api/v1/groups/{closed_group.json()['id']}/waitlist"
    waitlist = {"name": "Interested Visitor", "contact": "visitor@example.org", "consent": True}
    assert client.post(waitlist_url, json={**waitlist, "consent": False}).status_code == 422
    created = client.post(waitlist_url, json=waitlist)
    assert created.status_code == 201, created.text
    assert "contact" not in created.json()
    assert client.post(waitlist_url, json=waitlist).status_code == 409
    open_waitlist = client.post(f"/api/v1/groups/{open_group.json()['id']}/waitlist", json=waitlist)
    assert open_waitlist.status_code == 409

    assert client.get(f"/api/v1/admin/groups/{closed_group.json()['id']}/waitlist", headers=headers).status_code == 403
    pastor_token = provision_user(client, "group-pastor@example.org", role="pastor")
    pastor_headers = {"Authorization": f"Bearer {pastor_token}"}
    requests = client.get(f"/api/v1/admin/groups/{closed_group.json()['id']}/waitlist", headers=pastor_headers)
    assert requests.status_code == 200
    assert requests.json()[0]["contact"] == "visitor@example.org"
    updated = client.patch(
        f"/api/v1/admin/groups/{closed_group.json()['id']}/waitlist/{created.json()['id']}/status?new_status=contacted",
        headers=pastor_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "contacted"

    with Session(client.app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(SmallGroup)) == 3
        waitlist_record = db.get(GroupWaitlist, created.json()["id"])
        assert waitlist_record is not None
        assert "visitor@example.org" not in waitlist_record.encrypted_payload
        assert json.loads(decrypt_text(waitlist_record.encrypted_payload)) == {
            "name": "Interested Visitor",
            "contact": "visitor@example.org",
        }


def test_finance_requires_treasurer_role_and_tracks_approvals_budgets_and_pledges(client: TestClient) -> None:
    admin_token = provision_user(client, "finance-admin@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    editor_token = provision_user(client, "finance-editor@example.org", role="editor")
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    assert client.get("/api/v1/admin/finance/entries", headers=editor_headers).status_code == 403

    income = client.post("/api/v1/admin/finance/entries", headers=admin_headers, json={
        "entry_type": "income",
        "amount_ugx": 100000,
        "fund": "General",
        "category": "Offering",
        "entry_date": "2026-10-10",
        "payment_method": "cash",
        "details": "Sunday service offering",
    })
    assert income.status_code == 201, income.text
    assert income.json()["status"] == "recorded"

    expense = client.post("/api/v1/admin/finance/entries", headers=admin_headers, json={
        "entry_type": "expense",
        "amount_ugx": 25000,
        "fund": "General",
        "category": "Transport",
        "entry_date": "2026-10-11",
        "details": "Pastoral visit transport",
    })
    assert expense.status_code == 201, expense.text
    assert expense.json()["status"] == "pending"
    self_approval = client.patch(
        f"/api/v1/admin/finance/entries/{expense.json()['id']}/approval?status=approved",
        headers=admin_headers,
    )
    assert self_approval.status_code == 403

    treasurer_token = provision_user(client, "treasurer@example.org", role="treasurer")
    treasurer_headers = {"Authorization": f"Bearer {treasurer_token}"}
    approved = client.patch(
        f"/api/v1/admin/finance/entries/{expense.json()['id']}/approval?status=approved",
        headers=treasurer_headers,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    budget = client.post("/api/v1/admin/finance/budgets", headers=treasurer_headers, json={
        "fund": "General",
        "category": "Transport",
        "amount_ugx": 50000,
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
    })
    assert budget.status_code == 201, budget.text
    assert budget.json()["spent_ugx"] == 25000

    pledge = client.post("/api/v1/admin/finance/pledges", headers=treasurer_headers, json={
        "campaign": "Building fund",
        "amount_ugx": 300000,
        "due_date": "2026-10-20",
        "donor_name": "Private Donor",
        "donor_contact": "+256700000000",
    })
    assert pledge.status_code == 201, pledge.text
    partial_pledge = client.patch(
        f"/api/v1/admin/finance/pledges/{pledge.json()['id']}/status",
        headers=treasurer_headers,
        json={"status": "partially_fulfilled", "amount_fulfilled_ugx": 100000},
    )
    assert partial_pledge.status_code == 200, partial_pledge.text
    assert partial_pledge.json()["amount_fulfilled_ugx"] == 100000

    report = client.get(
        "/api/v1/admin/finance/report?period_start=2026-10-01&period_end=2026-10-31",
        headers=treasurer_headers,
    )
    assert report.status_code == 200
    assert report.json() == {
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "income_ugx": 100000,
        "approved_expenses_ugx": 25000,
        "pending_expenses_ugx": 0,
        "pending_corrections_ugx": 0,
        "budgeted_ugx": 50000,
        "pledge_total_ugx": 200000,
    }

    correction = client.post(
        f"/api/v1/admin/finance/entries/{income.json()['id']}/correction",
        headers=treasurer_headers,
        json={"reason": "Income amount was entered incorrectly"},
    )
    assert correction.status_code == 201, correction.text
    assert correction.json()["correction_of_id"] == income.json()["id"]
    assert correction.json()["entry_type"] == "expense"
    assert correction.json()["status"] == "pending"
    assert client.post(
        f"/api/v1/admin/finance/entries/{income.json()['id']}/correction",
        headers=treasurer_headers,
        json={"reason": "Attempt a duplicate correction"},
    ).status_code == 409
    assert client.patch(
        f"/api/v1/admin/finance/entries/{correction.json()['id']}/approval?status=approved",
        headers=treasurer_headers,
    ).status_code == 403

    pending_report = client.get(
        "/api/v1/admin/finance/report?period_start=2026-10-01&period_end=2026-10-31",
        headers=treasurer_headers,
    )
    assert pending_report.json()["pending_corrections_ugx"] == 100000
    corrected = client.patch(
        f"/api/v1/admin/finance/entries/{correction.json()['id']}/approval?status=approved",
        headers=admin_headers,
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["status"] == "approved"
    final_report = client.get(
        "/api/v1/admin/finance/report?period_start=2026-10-01&period_end=2026-10-31",
        headers=treasurer_headers,
    )
    assert final_report.json()["income_ugx"] == 100000
    assert final_report.json()["approved_expenses_ugx"] == 125000
    assert final_report.json()["pending_corrections_ugx"] == 0

    with Session(client.app.state.database_engine) as db:
        stored_expense = db.get(FinanceEntry, expense.json()["id"])
        stored_pledge = db.get(FinancePledge, pledge.json()["id"])
        stored_budget = db.get(FinanceBudget, budget.json()["id"])
        assert stored_expense is not None and "Pastoral visit transport" not in stored_expense.encrypted_details
        assert stored_pledge is not None and "+256700000000" not in stored_pledge.encrypted_details
        assert stored_budget is not None
        stored_income = db.get(FinanceEntry, income.json()["id"])
        assert stored_income is not None and stored_income.amount_ugx == 100000 and stored_income.status == "recorded"


def test_offering_counts_require_two_witnesses_and_third_person_for_discrepancies(client: TestClient) -> None:
    counter_token = provision_user(client, "offering-counter@example.org")
    counter_headers = {"Authorization": f"Bearer {counter_token}"}
    verifier_token = provision_user(client, "offering-verifier@example.org", role="treasurer")
    verifier_headers = {"Authorization": f"Bearer {verifier_token}"}
    resolver_token = provision_user(client, "offering-resolver@example.org")
    resolver_headers = {"Authorization": f"Bearer {resolver_token}"}

    payload = {
        "service_name": "Sunday morning",
        "service_date": "2026-10-11",
        "fund": "General",
        "category": "Offering",
        "amount_ugx": 100000,
        "notes": "Sealed count envelope 14",
    }
    assert client.post("/api/v1/admin/finance/offering-counts", json=payload).status_code == 401
    first_count = client.post(
        "/api/v1/admin/finance/offering-counts",
        headers=counter_headers,
        json=payload,
    )
    assert first_count.status_code == 201, first_count.text
    batch_id = first_count.json()["id"]
    self_verify = client.post(
        f"/api/v1/admin/finance/offering-counts/{batch_id}/verify",
        headers=counter_headers,
        json={"amount_ugx": 100000},
    )
    assert self_verify.status_code == 403

    mismatch = client.post(
        f"/api/v1/admin/finance/offering-counts/{batch_id}/verify",
        headers=verifier_headers,
        json={"amount_ugx": 99000},
    )
    assert mismatch.status_code == 200, mismatch.text
    assert mismatch.json()["status"] == "discrepancy"
    assert mismatch.json()["finance_entry_id"] is None
    with Session(client.app.state.database_engine) as db:
        assert db.scalar(select(func.count()).select_from(FinanceEntry)) == 0
        stored_batch = db.get(OfferingCountBatch, batch_id)
        assert stored_batch is not None and "Sealed count envelope 14" not in stored_batch.encrypted_details

    second_person_resolve = client.post(
        f"/api/v1/admin/finance/offering-counts/{batch_id}/resolve",
        headers=verifier_headers,
        json={"amount_ugx": 99000, "reason": "Independent recount"},
    )
    assert second_person_resolve.status_code == 403
    resolved = client.post(
        f"/api/v1/admin/finance/offering-counts/{batch_id}/resolve",
        headers=resolver_headers,
        json={"amount_ugx": 98000, "reason": "Third person witnessed a recount"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["final_amount_ugx"] == 98000
    assert resolved.json()["finance_entry_id"] is not None

    matching = client.post(
        "/api/v1/admin/finance/offering-counts",
        headers=counter_headers,
        json={**payload, "amount_ugx": 75000},
    )
    assert matching.status_code == 201, matching.text
    verified = client.post(
        f"/api/v1/admin/finance/offering-counts/{matching.json()['id']}/verify",
        headers=verifier_headers,
        json={"amount_ugx": 75000},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "recorded"
    assert verified.json()["final_amount_ugx"] == 75000

    with Session(client.app.state.database_engine) as db:
        income_entries = list(db.scalars(select(FinanceEntry).order_by(FinanceEntry.id)))
        assert len(income_entries) == 2
        assert [entry.amount_ugx for entry in income_entries] == [98000, 75000]
        assert all(entry.status == "recorded" for entry in income_entries)
        assert income_entries[0].reviewed_by_id == resolved.json()["resolved_by_id"]
        assert income_entries[1].reviewed_by_id == verified.json()["verified_by_id"]


def test_governance_meetings_encrypt_minutes_and_enforce_resolution_lifecycle(client: TestClient) -> None:
    pastor_token = provision_user(client, "governance-pastor@example.org", role="pastor")
    pastor_headers = {"Authorization": f"Bearer {pastor_token}"}
    editor_token = provision_user(client, "governance-editor@example.org", role="editor")
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    meetings_url = "/api/v1/admin/governance/meetings"
    meeting_payload = {
        "title": "Quarterly leadership meeting",
        "meeting_date": "2026-10-12",
        "location": "Main hall",
        "status": "held",
        "minutes": "Confidential deliberation and agreed stewardship plan.",
    }

    assert client.get(meetings_url).status_code == 401
    assert client.get(meetings_url, headers=editor_headers).status_code == 403
    meeting = client.post(meetings_url, json=meeting_payload, headers=pastor_headers)
    assert meeting.status_code == 201, meeting.text
    meeting_id = meeting.json()["id"]
    assert meeting.json()["minutes"] == meeting_payload["minutes"]

    with Session(client.app.state.database_engine) as db:
        stored_meeting = db.get(GovernanceMeeting, meeting_id)
        assert stored_meeting is not None
        assert meeting_payload["minutes"] not in stored_meeting.encrypted_minutes
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_type == "governance_meeting",
            AuditLog.entity_id == meeting_id,
            AuditLog.action == "create",
        )) == 1

    resolutions_url = f"{meetings_url}/{meeting_id}/resolutions"
    resolution = client.post(resolutions_url, headers=pastor_headers, json={
        "title": "Approve annual ministry budget",
        "description": "The treasurer will prepare the final budget for approval.",
        "due_date": "2026-11-01",
    })
    assert resolution.status_code == 201, resolution.text
    resolution_id = resolution.json()["id"]
    assert resolution.json()["status"] == "proposed"
    with Session(client.app.state.database_engine) as db:
        stored_resolution = db.get(GovernanceResolution, resolution_id)
        assert stored_resolution is not None
        assert "Approve annual ministry budget" not in stored_resolution.encrypted_content
        assert "final budget" not in stored_resolution.encrypted_content

    status_url = f"/api/v1/admin/governance/resolutions/{resolution_id}/status"
    assert client.patch(status_url, headers=editor_headers, json={"status": "approved"}).status_code == 403
    assert client.patch(status_url, headers=pastor_headers, json={"status": "in_progress"}).status_code == 409
    approved = client.patch(status_url, headers=pastor_headers, json={"status": "approved"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    in_progress = client.patch(status_url, headers=pastor_headers, json={"status": "in_progress"})
    assert in_progress.status_code == 200
    completed = client.patch(status_url, headers=pastor_headers, json={"status": "completed"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert client.patch(status_url, headers=pastor_headers, json={"status": "approved"}).status_code == 409
    assert client.get(resolutions_url, headers=pastor_headers).json()[0]["title"] == "Approve annual ministry budget"


def test_analytics_overview_is_aggregated_role_limited_and_period_scoped(client: TestClient) -> None:
    pastor_token = provision_user(client, "analytics-pastor@example.org", role="pastor")
    pastor_headers = {"Authorization": f"Bearer {pastor_token}"}
    editor_token = provision_user(client, "analytics-editor@example.org", role="editor")
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    report_start = date(2026, 10, 1)
    report_end = date(2026, 10, 31)

    with Session(client.app.state.database_engine) as db:
        actor = db.scalar(select(AdminUser).where(AdminUser.email == "analytics-pastor@example.org"))
        assert actor is not None
        active_members = [
            Member(encrypted_profile=encrypt_text(json.dumps({"name": f"Private Member {index}"})))
            for index in range(2)
        ]
        inactive_member = Member(
            encrypted_profile=encrypt_text(json.dumps({"name": "Inactive Member"})),
            status="inactive",
        )
        db.add_all([*active_members, inactive_member])
        db.flush()

        event = ChurchEvent(
            title="Published October event",
            description="",
            location="Church hall",
            starts_at=datetime(2026, 10, 20, tzinfo=timezone.utc),
            is_published=True,
        )
        draft_event = ChurchEvent(
            title="Private draft event",
            description="",
            location="Church hall",
            starts_at=datetime(2026, 10, 21, tzinfo=timezone.utc),
            is_published=False,
        )
        published_group = SmallGroup(
            name="Published group",
            description="",
            meeting_area="Town",
            meeting_day="Sunday",
            meeting_time="4:00 PM",
            age_group="Adults",
            is_open=True,
            is_published=True,
            updated_by_id=actor.id,
        )
        private_group = SmallGroup(
            name="Private group",
            description="",
            meeting_area="Town",
            meeting_day="Sunday",
            meeting_time="4:00 PM",
            age_group="Adults",
            is_open=True,
            is_published=False,
            updated_by_id=actor.id,
        )
        meeting = GovernanceMeeting(
            title="October meeting",
            meeting_date=report_start,
            location="Main hall",
            status="held",
            encrypted_minutes=encrypt_text(json.dumps({"minutes": "Confidential minutes"})),
            created_by_id=actor.id,
        )
        db.add_all([event, draft_event, published_group, private_group, meeting])
        db.flush()
        db.add_all([
            MemberAttendance(
                member_id=active_members[0].id,
                service_name="Sunday service",
                service_date=date(2026, 10, 5),
                check_in_method="manual",
            ),
            MemberAttendance(
                member_id=active_members[0].id,
                service_name="Sunday service",
                service_date=date(2026, 10, 12),
                check_in_method="manual",
            ),
            MemberAttendance(
                member_id=active_members[1].id,
                service_name="Sunday service",
                service_date=date(2026, 10, 12),
                check_in_method="manual",
            ),
            MemberAttendance(
                member_id=active_members[1].id,
                service_name="Outside period",
                service_date=date(2026, 9, 30),
                check_in_method="manual",
            ),
            VisitorVisit(
                encrypted_payload=encrypt_text(json.dumps({"name": "Private visitor"})),
                status="new",
                created_at=datetime(2026, 10, 15, tzinfo=timezone.utc),
            ),
            VisitorVisit(
                encrypted_payload=encrypt_text(json.dumps({"name": "Followed visitor"})),
                status="contacted",
                created_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
            ),
            VisitorVisit(
                encrypted_payload=encrypt_text(json.dumps({"name": "Old visitor"})),
                status="new",
                created_at=datetime(2026, 9, 30, tzinfo=timezone.utc),
            ),
            EventRegistration(
                event_id=event.id,
                email_digest="a" * 64,
                encrypted_payload=encrypt_text(json.dumps({"name": "Private attendee"})),
            ),
            EventRegistration(
                event_id=draft_event.id,
                email_digest="b" * 64,
                encrypted_payload=encrypt_text(json.dumps({"name": "Draft attendee"})),
            ),
            GovernanceResolution(
                meeting_id=meeting.id,
                encrypted_content=encrypt_text(json.dumps({"title": "Open action", "description": "Private"})),
                status="in_progress",
                created_by_id=actor.id,
            ),
            GovernanceResolution(
                meeting_id=meeting.id,
                encrypted_content=encrypt_text(json.dumps({"title": "Completed action", "description": "Private"})),
                status="completed",
                created_by_id=actor.id,
            ),
        ])
        db.commit()

    url = "/api/v1/admin/analytics/overview?period_start=2026-10-01&period_end=2026-10-31"
    assert client.get("/api/v1/admin/analytics/overview").status_code == 401
    assert client.get(url, headers=editor_headers).status_code == 403
    response = client.get(url, headers=pastor_headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "active_members": 2,
        "attendance_check_ins": 3,
        "distinct_attendees": 2,
        "service_days_recorded": 2,
        "visitor_requests": 2,
        "new_visitor_follow_ups": 1,
        "published_events": 1,
        "event_registrations": 1,
        "published_small_groups": 1,
        "open_governance_actions": 1,
    }
    assert not {"member_names", "visitor_names", "finance_entries", "pastoral_notes"} & response.json().keys()
    default_period = client.get("/api/v1/admin/analytics/overview", headers=pastor_headers)
    assert default_period.status_code == 200
    today = datetime.now(timezone.utc).date()
    assert default_period.json()["period_end"] == today.isoformat()
    assert default_period.json()["period_start"] == (today - timedelta(days=29)).isoformat()
    assert client.get(
        "/api/v1/admin/analytics/overview?period_start=2026-11-01&period_end=2026-10-01",
        headers=pastor_headers,
    ).status_code == 422
    assert client.get(
        "/api/v1/admin/analytics/overview?period_start=2025-01-01&period_end=2026-01-02",
        headers=pastor_headers,
    ).status_code == 422


def test_branch_registry_is_admin_managed_audited_and_archivable(client: TestClient) -> None:
    admin_token = provision_user(client, "branch-admin@example.org")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    pastor_token = provision_user(client, "branch-pastor@example.org", role="pastor")
    pastor_headers = {"Authorization": f"Bearer {pastor_token}"}
    branches_url = "/api/v1/admin/branches"
    payload = {"name": "Masaka Central", "location": "Masaka", "is_active": True}

    assert client.get(branches_url).status_code == 401
    assert client.get(branches_url, headers=pastor_headers).status_code == 403
    created = client.post(branches_url, headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    branch_id = created.json()["id"]
    assert created.json()["name"] == payload["name"]
    duplicate = client.post(branches_url, headers=admin_headers, json=payload)
    assert duplicate.status_code == 409

    listed = client.get(branches_url, headers=admin_headers)
    assert listed.status_code == 200
    assert [branch["id"] for branch in listed.json()] == [branch_id]
    assert client.put(
        f"{branches_url}/{branch_id}",
        headers=admin_headers,
        json={"name": "Masaka Central Campus", "location": "Central Masaka", "is_active": False},
    ).status_code == 200
    assert client.get(branches_url, headers=admin_headers).json() == []
    archived = client.get(f"{branches_url}?include_inactive=true", headers=admin_headers)
    assert archived.status_code == 200
    assert archived.json()[0]["name"] == "Masaka Central Campus"
    assert archived.json()[0]["is_active"] is False
    assert client.put(
        f"{branches_url}/{branch_id}",
        headers=admin_headers,
        json={"name": "Another Name", "location": "", "is_active": True},
    ).status_code == 200
    assert client.put(
        f"{branches_url}/9999",
        headers=admin_headers,
        json={"name": "Missing", "location": "", "is_active": True},
    ).status_code == 404
    with Session(client.app.state.database_engine) as db:
        branch = db.get(Branch, branch_id)
        assert branch is not None and branch.name == "Another Name"
        assert db.scalar(select(func.count()).select_from(AuditLog).where(
            AuditLog.entity_type == "branch",
        )) == 3


def test_pastoral_care_resource_bookings_documents_and_certificates(client: TestClient) -> None:
    pastor_token = provision_user(client, "phase3-pastor@example.org", role="pastor")
    pastor_headers = {"Authorization": f"Bearer {pastor_token}"}
    editor_token = provision_user(client, "phase3-editor@example.org", role="editor")
    editor_headers = {"Authorization": f"******"}

    member = client.post("/api/v1/admin/members", headers=pastor_headers, json={
        "name": "Care Member",
        "consent_confirmed": True,
    })
    assert member.status_code == 201, member.text
    member_id = member.json()["id"]

    care = client.post("/api/v1/admin/pastoral-care/tasks", headers=pastor_headers, json={
        "member_id": member_id,
        "care_type": "pastoral_follow_up",
        "priority": "high",
        "due_date": "2026-10-20",
        "notes": "Confidential care follow-up",
    })
    assert care.status_code == 201, care.text
    editor_headers = {"Authorization": f"Bearer {editor_token}"}
    assert client.get("/api/v1/admin/pastoral-care/tasks", headers=editor_headers).status_code == 403
    with Session(client.app.state.database_engine) as db:
        task = db.get(PastoralCareTask, care.json()["id"])
        assert task is not None and "Confidential care follow-up" not in task.encrypted_details

    resource = client.post("/api/v1/admin/resources", headers=editor_headers, json={
        "name": "Meeting Hall",
        "description": "Main hall",
        "is_active": True,
    })
    assert resource.status_code == 201, resource.text
    booking_day = (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat()
    booking_payload = {
        "resource_id": resource.json()["id"],
        "starts_at": f"{booking_day}T10:00:00Z",
        "ends_at": f"{booking_day}T11:00:00Z",
        "purpose": "Leadership meeting",
    }
    booking = client.post("/api/v1/admin/resource-bookings", headers=editor_headers, json=booking_payload)
    assert booking.status_code == 201, booking.text
    conflict = client.post("/api/v1/admin/resource-bookings", headers=editor_headers, json={
        **booking_payload,
        "starts_at": f"{booking_day}T10:30:00Z",
    })
    assert conflict.status_code == 409
    assert client.patch(
        f"/api/v1/admin/resource-bookings/{booking.json()['id']}/status",
        headers=editor_headers,
        json={"status": "approved"},
    ).status_code == 200

    document = client.post("/api/v1/admin/documents", headers=pastor_headers, json={
        "document_type": "policy",
        "title": "Safeguarding Policy",
        "filename": "policy.txt",
        "content_type": "text/plain",
        "content_base64": "c2Vuc2l0aXZlIGRvY3VtZW50",
    })
    assert document.status_code == 201, document.text
    with Session(client.app.state.database_engine) as db:
        stored_document = db.get(StaffDocument, document.json()["id"])
        assert stored_document is not None and "sensitive document" not in stored_document.encrypted_payload
    downloaded = client.get(f"/api/v1/admin/documents/{document.json()['id']}/download", headers=pastor_headers)
    assert downloaded.status_code == 200
    assert downloaded.content == b"sensitive document"
    assert downloaded.headers["content-disposition"].startswith("attachment;")

    certificate = client.post("/api/v1/admin/certificates", headers=pastor_headers, json={
        "member_id": member_id,
        "certificate_type": "Baptism",
        "issued_on": "2026-10-12",
        "certificate_number": "BW-2026-0001",
        "details": "Baptized at the Sunday service",
    })
    assert certificate.status_code == 201, certificate.text
    certificate_download_url = f"/api/v1/admin/certificates/{certificate.json()['id']}/download"
    assert client.get(certificate_download_url).status_code == 401
    assert client.get(certificate_download_url, headers=editor_headers).status_code == 403
    pdf_download = client.get(certificate_download_url, headers=pastor_headers)
    assert pdf_download.status_code == 200, pdf_download.text
    assert pdf_download.content.startswith(b"%PDF-")
    assert pdf_download.headers["content-type"] == "application/pdf"
    assert pdf_download.headers["content-disposition"] == 'attachment; filename="certificate-BW-2026-0001.pdf"'
    assert pdf_download.headers["cache-control"] == "private, no-store"
    repeated_pdf_download = client.get(certificate_download_url, headers=pastor_headers)
    assert repeated_pdf_download.status_code == 200
    assert repeated_pdf_download.content.startswith(b"%PDF-")
    assert client.get("/api/v1/admin/certificates/9999/download", headers=pastor_headers).status_code == 404
    with Session(client.app.state.database_engine) as db:
        stored_certificate = db.get(MemberCertificate, certificate.json()["id"])
        assert stored_certificate is not None
        assert "Baptized at the Sunday service" not in stored_certificate.encrypted_details
        assert db.scalar(select(func.count()).select_from(ResourceBooking)) == 1