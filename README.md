| Payments | Manual instructions only | MTN merchant and Airtel business-till instructions are shown; automated collection, payment confirmation, and card processing require provider integrations |
Bwala Deliverance and Healing Ministries International (Masaka)

An Integrated Church Website & Management System

Replacing paper registers, scattered spreadsheets, and chaotic group chats with one connected platform.

Show Image Show Image Show Image Show Image

Overview

This project is the official website and management platform for Bwala Deliverance and Healing Ministries International, Masaka, Uganda. It has two parts:

Public website: helps first-time visitors, online viewers, and members find service times, watch and search sermons, give online, send prayer requests, register for events, and join small groups.
Internal management system: helps pastors, treasurers, secretaries, and volunteer coordinators manage members, attendance, finances, pastoral care, rotas, resources, and communication from a single source of truth.

The platform is designed for Ugandan conditions: mobile-first, low-bandwidth friendly, and integrated with local mobile money (MTN and Airtel).

Church contact: Tel: +256 753 972 515

Core Features
Public Website
Feature	Description
Visitor Essentials	Service times, location with map, "Plan a Visit" page, statement of faith, About Us, leadership, and ministry pages.
Sermon Archive	Searchable audio, video, and notes by speaker, series, scripture, and keyword, plus livestream links and a podcast feed.
Online Giving	Tithes, offerings, and building fund pledges via mobile money and cards, with digital receipts.
Events & RSVP	Events calendar with online registration and capacity limits.
Prayer Requests	Private submission with a confidential follow-up workflow.
Small Group Finder	Map-based search for open cell groups, with filters and waitlists.
Newsletter & Alerts	Newsletter signup and emergency notices by banner, SMS, and push.
Accessibility & Languages	Multi-language pages, accessible design, and live captions (later phase).
Internal System
Module	Description
Finance	Tithe and offering recording with audit trail, offering-count verification, pledges, budgets, expenses, giving statements, welfare and bereavement funds.
Members & Pastoral Care	Single member and household registry, attendance-based care alerts, follow-up tasks, counseling booking, certificates, onboarding, and discipleship tracking.
Attendance & Safeguarding	QR or phone check-in, secure child check-in and pick-up, volunteer vetting, incident logs, and confidential complaint reporting.
Operations	Volunteer rota with availability and reminders, room and equipment booking, QR asset tracking, maintenance logs, and service planning.
Leadership & Governance	Meeting minutes, resolutions, voting, succession tracking, analytics dashboards, and multi-branch reporting.
Communication	Segmented SMS, email, and push notifications with delivery reports, plus surveys and a suggestion box.
Platform & Security	Role-based access control, encryption, audit logs, backups, a document store, and an admin CMS so staff can edit content without a developer.
Institutions & Missions	Records for church-run schools, clinics, and savings groups, and tracking of church plants and mission fields.

System Architecture

The system is modular, so each module can be built and released in phases while sharing one member registry.

Layer	Technology	Purpose
Frontend	HTML, CSS, and JavaScript	Public website and staff console
Backend	FastAPI (Python)	REST API, authentication, role-based access control, business logic
Database	SQLite by default; PostgreSQL supported	Application records and staff accounts
Background Jobs	Not configured	Planned reminders, rota generation, and report generation
Payments	Not configured	MTN Mobile Money, Airtel Money, and card processing are planned
Messaging	Not configured	Planned SMS, email, and push notifications

Prerequisites
Python 3.10+
Git
A modern web browser

SQLite is used by default, so PostgreSQL is not required for local development.

Local Development Setup

1. Start the backend

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate         # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

# Use stable local secrets; changing the encryption key makes stored records unreadable.
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DATA_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"

alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API uses SQLite at `backend/church.db` by default. Set `DATABASE_URL` before starting the server to use PostgreSQL. API documentation is available at http://localhost:8000/docs.

2. Serve the website and staff console

In a second terminal, from the repository root:

```bash
python3 -m http.server 8080
```

Open http://localhost:8080 for the public site or http://localhost:8080/admin.html for the staff console. The API allows this origin by default.

For a manual SQLite backup, run `python -m app.cli backup-db` from `backend/`. By default, backups are written outside the repository to `~/.local/state/bwala/backups` with owner-only file permissions. To automate daily backups on Linux, schedule this command with cron or a systemd timer. Test restores regularly. Back up `DATA_ENCRYPTION_KEY` separately in a secure secret store; database backups alone cannot recover encrypted records if that key is lost. PostgreSQL deployments should configure and test provider-managed backups.

3. Provision an administrator

There is no public admin registration. Run this from a third terminal in the repository root:

```bash
cd backend
source .venv/bin/activate         # Windows: .venv\\Scripts\\activate
python -m app.cli create-admin --email <address>
```

The command prompts for the password twice. For unattended deployments, pass `--password-stdin` and pipe the password in. Add `--name` to set a display name.

The current API supports public pages, sermons, events and RSVPs, emergency alert banners, contact inquiries, prayer requests, newsletter subscriptions, giving availability status, staff authentication, CMS management for pages, sermons, and events, an authenticated member registry, member attendance, child safeguarding records, and volunteer scheduling. Member routes allow administrators and pastors to create, list, read, update, and deactivate records. Member profiles are encrypted at rest, email addresses are normalized and protected by keyed digests, consent is required at creation, and changes are audited. Attendance supports staff check-in, date-filtered lists, and checkout for active members; attendance changes are audited. Child profiles require guardian consent and are encrypted at rest. Check-in and checkout are restricted to the primary guardian or an active authorized pickup member, and safeguarding changes are audited. Emergency alerts can be published and automatically expire on the public site; publishing is restricted to administrators and pastors and does not send SMS or push notifications. Staff can record volunteer availability or issue a seven-day, one-use response link that volunteers can share manually; the link exposes only the service/date and records an available/unavailable response. Rota generation only assigns active members who marked themselves available and balances assignments across the previous 30 days. Contact inquiries and prayer requests are also encrypted at rest and visible only to pastors and administrators. Event registrations are encrypted at rest and visible to content staff. Newsletter email addresses are encrypted and deduplicated using keyed digests.

The child API verifies stored authorization but cannot verify the identity of the adult physically collecting a child. Staff must verify identity in person and follow church safeguarding procedures; review these workflows against local law and church policy before use with real children.

Member endpoints are `POST /api/v1/admin/members` (requires `consent_confirmed: true`), `GET /api/v1/admin/members` (supports `status=active|inactive|all`, `limit`, and `offset`), `GET /api/v1/admin/members/{id}`, `PUT /api/v1/admin/members/{id}`, and `PATCH /api/v1/admin/members/{id}/status?new_status=inactive`.

Email/SMS/WhatsApp consent is stored separately from member-record consent. Administrators and pastors can review it with `GET /api/v1/admin/members/{id}/communication-consents` and update it with `PUT /api/v1/admin/members/{id}/communication-consents`. Channels default to opted out; an email address or phone number and an affirmative consent source are required to opt in. Per-channel preferences record weekly/monthly/essential-only frequency and quiet hours (default 21:00–07:00 Africa/Kampala). No notification is sent by these endpoints; delivery caps, one-click unsubscribe links, STOP webhooks, and the 24-hour opt-out SLA require a configured messaging provider and are not active yet.

Safeguarding reports can be submitted at `POST /api/v1/safeguarding/reports`; payloads are encrypted and retained for 25 years. `GET /api/v1/admin/safeguarding/reports` and the status endpoint are role-partitioned: Safeguarding Leads/Senior Pastors review ordinary cases, Board Chair/Trustees review reports involving restricted staff and pending second approvals. Serious child-protection cases cannot be internally resolved; a Safeguarding Lead must record that an external referral was made. This system does not contact authorities. Volunteer vetting records are encrypted and restricted to Admin/HR/Safeguarding Lead/Senior Pastor; only Safeguarding Leads can enter check results and decide approval. Records are retained until seven years after service ends and cannot be deleted through the API. These retention and safeguarding rules require qualified legal review before live use.

Attendance endpoints are `GET /api/v1/admin/attendance/members` (IDs and names only), `POST /api/v1/admin/attendance`, `GET /api/v1/admin/attendance?service_date=YYYY-MM-DD`, and `PATCH /api/v1/admin/attendance/{id}/check-out`. Attendance can be managed by administrators, editors, and pastors.

Child endpoints are `POST /api/v1/admin/children`, `GET /api/v1/admin/children`, `PUT /api/v1/admin/children/{id}`, `PATCH /api/v1/admin/children/{id}/status`, `POST /api/v1/admin/child-attendance`, `GET /api/v1/admin/child-attendance?service_date=YYYY-MM-DD`, and `PATCH /api/v1/admin/child-attendance/{id}/check-out`. Only administrators and pastors can manage child records and check-in.

Emergency alerts are publicly listed by `GET /api/v1/alerts/current`; administrators and pastors manage them through `GET` and `POST /api/v1/admin/alerts`, `PUT /api/v1/admin/alerts/{id}`, and `PATCH /api/v1/admin/alerts/{id}/status`.

Volunteer scheduling endpoints are `POST` and `GET /api/v1/admin/volunteer-availability`, `POST /api/v1/admin/volunteer-availability/invites`, public `POST /api/v1/volunteer-availability/invites/inspect` and `POST /api/v1/volunteer-availability/respond`, `POST /api/v1/admin/rota/generate`, and `GET /api/v1/admin/rota`. Staff availability and rota management are restricted to administrators, editors, and pastors. Invite links are one-use, expire after seven days, and must be shared manually; reminders are not configured.

The public small-group finder uses `GET /api/v1/groups` with text, day, age-group, open-status, and approximate-radius filters. Administrators, editors, and pastors manage listings through `GET` and `POST /api/v1/admin/groups` and `PUT /api/v1/admin/groups/{id}`. Public waitlist requests use `POST /api/v1/groups/{id}/waitlist` and require consent; waitlist contact details are encrypted and restricted to administrators and pastors. Publish approximate public-area coordinates only, never private home addresses.

Visitors can request a welcome follow-up through `POST /api/v1/visitors`, with consent and encrypted contact details. Administrators and pastors review requests at `GET /api/v1/admin/visitors` and update status with `PATCH /api/v1/admin/visitors/{id}/status`. Staff follow up manually; no automatic contact message is sent.

### Phase 3 implementation

The current Phase 3 baseline adds manual finance records, budget and pledge tracking, expense approval, confidential pastoral follow-up tasks, resource inventory and booking, encrypted staff documents, and member certificate records. Small-group listings and consented waitlists are already available through the endpoints above.

Finance endpoints are under `/api/v1/admin/finance`: `POST` and `GET /entries`, `PATCH /entries/{id}/approval?status=approved|rejected`, `POST /entries/{id}/correction`, `POST` and `GET /offering-counts`, `POST /offering-counts/{id}/verify`, `POST /offering-counts/{id}/resolve`, `POST` and `GET /budgets`, `POST` and `GET /pledges`, `PATCH /pledges/{id}/status`, and `GET /report?period_start=YYYY-MM-DD&period_end=YYYY-MM-DD`. Finance access is restricted to administrators and treasurers. Income entries are recorded immediately; expense entries remain pending until a different finance-authorized staff member reviews them. Entries cannot be edited or deleted. A correction creates one linked, equal-and-opposite entry, records the reason encrypted, and requires review by a different finance-authorized staff member; the original stays unchanged. Reports show unapproved corrections separately and count their amounts only after approval. Amounts are whole Ugandan shillings (UGX). Details and pledge contacts are encrypted at rest.

Offering counts are posted as finance income only after a second finance-authorized staff member independently enters the same amount. A mismatch is retained as a discrepancy with no income posted; a third finance-authorized person, different from both counters, must record the recount amount and reason to resolve it and post the income. Count notes are encrypted and each step is audited.

Pastoral follow-up uses `POST` and `GET /api/v1/admin/pastoral-care/tasks` and `PUT /api/v1/admin/pastoral-care/tasks/{id}`. Only administrators and pastors can access care notes. Manual tasks do not send messages. Separate attendance-based alerts are evaluated when Sunday attendance is recorded, as described below.

Resource management uses `POST` and `GET /api/v1/admin/resources`, `PUT /api/v1/admin/resources/{id}`, `POST` and `GET /api/v1/admin/resource-bookings`, and `PATCH /api/v1/admin/resource-bookings/{id}/status`. Times entered in the staff console are converted from browser-local time to UTC. Overlapping pending or approved bookings are rejected. Administrators, editors, and pastors can manage these workflows.

Confidential documents use `POST` and `GET /api/v1/admin/documents` and `GET /api/v1/admin/documents/{id}/download`; documents are limited to 2 MB and encrypted in the database. Certificates are recorded with `POST` and `GET /api/v1/admin/certificates` and downloaded as landscape PDFs through `GET /api/v1/admin/certificates/{id}/download`. Only administrators and pastors can access documents, certificates, and pastoral-care records. Back up `DATA_ENCRYPTION_KEY` separately from the database.

Attendance-based pastoral care alerts are evaluated when staff record a Sunday attendance entry. After three distinct Sundays with recorded service attendance, active members with no attendance on any of those three dates receive one confidential, auditable follow-up task for that Sunday window. The rule considers Sundays with recorded attendance, not a separately configured service calendar; it does not run on a schedule or emit alerts for Sundays with no attendance records.

This baseline does not include payroll, payment-provider integrations, giving statements, or counseling appointment scheduling. Review the full workbook checklist with church staff before treating every Phase 3 workbook row as complete; this README describes the delivered scope, not a row-by-row workbook sign-off.

### Phase 4 implementation

The first Phase 4 governance deliverable is a private register for leadership meetings and resolutions. Administrators and pastors can create and update meeting records, store minutes, propose resolutions, and track a resolution through proposed → approved/rejected → in progress → completed. Minutes and resolution text are encrypted at rest, and each creation or update is audited. Endpoints are under `/api/v1/admin/governance`: `POST` and `GET /meetings`, `PUT /meetings/{id}`, `POST` and `GET /meetings/{id}/resolutions`, and `PATCH /resolutions/{id}/status`. Resolutions can only advance through the defined status transitions; rejected and completed resolutions are terminal. Formal voting, quorum, succession tracking, and governance policy rules are not implemented and must be agreed with church leadership before adding them.

The Phase 4 analytics overview is available to administrators and pastors at `GET /api/v1/admin/analytics/overview`, with optional `period_start` and `period_end` dates (maximum 366 days; defaults to the last 30 days). It reports aggregate active-member, attendance, visitor follow-up, published event and registration, published small-group, and open governance-action counts. The staff console has matching date filters. It intentionally excludes member identities, child records, pastoral-care details, donor information, and financial amounts; finance reporting remains in the treasurer/admin finance workflow.

The initial multi-branch foundation follows the shared-staff model. Administrators can create, update, list, and archive branches through `POST`, `GET`, and `PUT /api/v1/admin/branches`; archived branches remain visible when `include_inactive=true`. Branches are not deleted. Optional branch IDs are supported on member, attendance, event, finance, offering-count, governance, small-group, and resource records; resource bookings inherit their resource's branch. Group/resource staff lists and analytics can be filtered by branch. Existing records remain unassigned until staff update them; staff retain cross-branch access. Child, care, visitor, volunteer, document, and certificate records are not branch-tagged, and branch-level permissions are not implemented. Add branch names with church leadership before assigning existing records.

A starter institutions and missions register supports schools, clinics, savings groups, church plants, and mission fields. Administrators and pastors can create, update, list, and deactivate records; changes are audited and records may be branch-tagged. The register contains name, location, and a description only; it is not a beneficiary, staffing, finance, or outcomes-management system. Do not enter personal or beneficiary details in descriptions. Church leadership must approve classifications and data-handling rules before operational use.

Public offline support is an installable web app served over HTTPS (or localhost for development). Its service worker caches the public shell only, never staff pages or API responses. The public client separately retains successful responses for the public events, sermons, groups, published pages, and current-alert endpoints in this browser, and uses those cached responses if the network request fails. Cached information may be stale; data is only available offline after it has been loaded once while online. Forms do not queue or submit offline. External images and fonts require a connection.

Languages, caption/translation languages, and external service providers have not yet been specified. No provider integrations or unreviewed translations are configured. Institutions and missions also remain a future Phase 4 workstream.

Security & Regulatory Compliance

Church records include giving, counseling notes, and information about children, so privacy and security are built in from the start:

Uganda Data Protection and Privacy Act, 2019 (DPPA): explicit consent, secure storage, and registration requirements for handling personal and sensitive data
Electronic Transactions Act, 2011: rules for electronic records and online transactions
Payment provider requirements: compliance with MTN, Airtel, and card processor terms for online giving
Child safeguarding: check-in and pick-up controls, volunteer vetting, and incident logs reviewed against church and local policy
Technical controls: role-based access control, encryption at rest for supported records, and audit logging. A local SQLite backup command is available; automated off-site backups, tested recovery, and production HTTPS still require deployment configuration.

Confirm the final legal requirements with a qualified advisor before launch.

Implementation Roadmap
Phase 1 – MVP: Public Presence and Security Basics

Public website, sermon archive, events, contact, online giving, prayer requests, newsletter, admin CMS, encryption, backups, and role-based access.

Phase 2 – Core Operations

Member database, attendance and child check-in, communications, volunteer rota, and emergency alerts.

Phase 3 – Finance and Care (manual baseline implemented)

Finance and budgeting, pastoral care alerts, small groups, resource booking, documents, and certificates.

Phase 4 – Growth and Scale (governance meeting and resolution register started)

Governance, analytics, multi-branch support, captions and translation, offline support, institutions and missions, and integrations.

### Phase completion checklist (audit: 2026-11-01)

Status is based on the code and documentation in this repository, not a church or production sign-off. A phase is complete only after its remaining work is implemented, tested, and accepted by the responsible church staff; provider-dependent items also require provider configuration and sandbox verification.

| Phase | Status | Remaining work and completion checks |
| --- | --- | --- |
| 1 – Public presence and security | Partial | Configure and verify online giving with the selected providers, including payment confirmation and reconciliation. Newsletter signup stores consented addresses but does not deliver messages. Complete deployment checks for HTTPS, off-site backups, and tested restore. |
| 1 – Public presence and security | Partial | Manual MTN and Airtel payment instructions are configured. Implement and verify provider integrations, payment confirmation, reconciliation, and card checkout through a selected hosted payment gateway. Newsletter signup stores consented addresses but does not deliver messages. Complete deployment checks for HTTPS, off-site backups, and tested restore. |
| 2 – Core operations | Partial | Member, attendance, child check-in, volunteer availability/rota, and emergency-alert workflows exist. Encrypted safeguarding incident/complaint intake and volunteer-vetting records now implement the supplied role, review, and retention rules. Email/SMS/WhatsApp consent preferences are recorded, but delivery, frequency enforcement, STOP/unsubscribe, push delivery, and rota reminders need providers. Background checks and external authority referrals happen outside the system; obtain legal review and staff acceptance before live use. |
| 3 – Finance and care | Partial | The manual finance/care baseline exists. Payroll, payment-provider integrations, giving statements, and counseling appointment scheduling are not implemented. Reconcile this implementation against the full Phase 3 workbook with the treasurer and pastoral staff; the workbook is not in this repository. |
| 4 – Growth and scale | Partial | Governance meeting/resolution records, aggregate analytics, a branch registry with optional tagging for selected records (including groups/resources), a starter institutions/missions register, and public read-only offline caching exist. Formal voting/quorum, succession tracking, branch-level permissions, tagging remaining record types, full institution/mission operations, captions/translations, and provider integrations remain. Offline forms do not queue submissions. Obtain policy, language, branch, and provider decisions before implementation. |

### Cross-phase release gates

- [ ] Church staff validate the 73-problem plan and sign off each applicable workflow; attach the current workbook to the project before claiming row-by-row completion.
- [ ] A qualified advisor confirms launch requirements for sensitive records, consent, child safeguarding, and applicable Ugandan law.
- [ ] Production deployment has HTTPS, protected secrets, off-site backups, and a tested recovery procedure.
- [x] Backend suite passes: `PYTHONPATH=. python3 -m pytest -q tests` from `backend/` (30 passed on 2026-11-01).
- [x] Frontend JavaScript syntax checks pass, and the public page, staff console, and core assets return HTTP 200 from the local static server (2026-11-01).
- [x] Resolve the supplied staff-console fixes F-01 through F-14 in source; F-01 and F-11 were already present, and F-12 was not applicable because no inline `MutationObserver` script was present.
- [x] Playwright smoke tests pass: public mobile navigation, staff sign-in error handling, manual MTN/Airtel giving instructions, public safeguarding intake, and Safeguarding Lead vetting workspace (5 passed on 2026-11-01).
- [ ] Complete role-specific and end-to-end browser acceptance for all public and staff workflows before release.

The passing run emits one Starlette deprecation warning because `httpx` is used with `starlette.testclient`; update the test-client dependency when the project adopts the recommended replacement.

Before building each phase, the problem list is validated with church staff (pastor, treasurer, secretary, youth leader, and volunteer coordinator).

Documentation
Document	Description
Architecture	System design, data model, and module breakdown
API Reference	Endpoints, request and response shapes, and errors
Church Operations Guide	Runbook for staff: giving reports, care alerts, rotas, and daily checks
Problem & Solution Plan	The 73 problems the platform addresses, with phases
Contributing	Workflow, coding standards, and review process
Contributing

Contributions of all kinds are welcome: code, documentation, testing, and ideas. Please read the Contribution Guide before submitting a pull request.

License

License to be decided by the church and maintainer. Add a LICENSE file and update the badge above.

Contact

Bwala Deliverance and Healing Ministries International Masaka, Uganda Tel: +256 753 972 515

Maintainer: [Your name] Email: [your email]

Built to help every member, visitor, and leader stay connected and cared for.