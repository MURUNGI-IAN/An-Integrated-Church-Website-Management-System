const loginPanel = document.querySelector('#login-panel');
const consolePanel = document.querySelector('#console-panel');
const consoleTabList = document.querySelector('.console-tabs');
const loginForm = document.querySelector('#login-form');
const loginStatus = document.querySelector('#login-status');
let currentStaffRole = null;
let currentStaffId = null;
const localHosts = ['localhost', '127.0.0.1', '0.0.0.0'];
const configuredApiBase = document.querySelector('meta[name="api-base-url"]')?.content.trim();
const apiBase = (configuredApiBase || (localHosts.includes(window.location.hostname)
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : window.location.origin)).replace(/\/+$/, '');
let activeAttendanceMembers = [];
let childProfiles = [];
let branchRecords = [];

function branchName(branchId) {
  if (branchId === null || branchId === undefined) return 'Unassigned';
  return branchRecords.find((branch) => branch.id === branchId)?.name || `Branch #${branchId}`;
}

function setBranchSelectValue(select, branchId) {
  const value = branchId === null || branchId === undefined ? '' : String(branchId);
  if (value && !Array.from(select.options).some((option) => option.value === value)) {
    const branch = branchRecords.find((record) => String(record.id) === value);
    if (branch) select.add(new Option(`${branch.name} · Inactive`, value));
  }
  select.value = value;
}

async function loadBranchSelectors() {
  const selects = document.querySelectorAll('select.branch-select');
  if (!selects.length) return;
  try {
    branchRecords = await apiRequest('/admin/branches?include_inactive=true');
    selects.forEach((select) => {
      const selected = select.value;
      select.replaceChildren(new Option(select.dataset.emptyLabel || 'Unassigned', ''));
      branchRecords.filter((branch) => branch.is_active).forEach((branch) => {
        select.add(new Option(branch.name, branch.id));
      });
      setBranchSelectValue(select, selected || null);
      select.disabled = false;
    });
  } catch (error) {
    selects.forEach((select) => {
      select.replaceChildren(new Option(`Branch options unavailable: ${error.message}`, ''));
      select.disabled = true;
    });
  }
}

function optionalBranchId(formData) {
  const value = formData.get('branch_id');
  return value ? Number(value) : null;
}
async function apiRequest(path, options = {}) {
  const token = sessionStorage.getItem('bwala_staff_token');
  const headers = { 'Content-Type': 'application/json', ...options.headers };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${apiBase}/api/v1${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join(', ') : data.detail;
    if (response.status === 401 && path !== '/auth/token') showLogin('Your session ended. Sign in again.');
    throw new Error(detail || 'The service is temporarily unavailable.');
  }
  return data;
}

function showLogin(message = '') {
  currentStaffRole = null;
  currentStaffId = null;
  sessionStorage.removeItem('bwala_staff_token');
  consolePanel.hidden = true;
  loginPanel.hidden = false;
  loginStatus.textContent = message;
}

function setFormStatus(form, message, isError = false) {
  const status = form.querySelector('.form-status');
  status.textContent = message;
  status.dataset.state = isError ? 'error' : 'success';
}

function addAdminRow(list, title, detail, actionLabel, action) {
  const row = document.createElement('article');
  row.className = 'admin-list-item';
  const copy = document.createElement('div');
  const heading = document.createElement('h3');
  heading.textContent = title;
  const description = document.createElement('p');
  description.textContent = detail;
  copy.append(heading, description);
  row.append(copy);
  if (actionLabel) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = actionLabel;
    button.addEventListener('click', action);
    row.append(button);
  }
  list.append(row);
  return row;
}

function showEmpty(list, message) {
  const empty = document.createElement('p');
  empty.className = 'list-empty';
  empty.textContent = message;
  list.replaceChildren(empty);
}

function attachAdminListTools(list) {
  const tools = document.createElement('div');
  tools.className = 'admin-list-tools';
  tools.hidden = true;

  const searchLabel = document.createElement('label');
  searchLabel.className = 'admin-list-search';
  searchLabel.textContent = 'Search this list';
  const search = document.createElement('input');
  search.type = 'search';
  search.setAttribute('aria-label', `Search ${list.id.replaceAll('-', ' ')}`);
  searchLabel.append(search);

  const showMore = document.createElement('button');
  showMore.type = 'button';
  showMore.className = 'admin-list-more';
  showMore.textContent = 'Show more';
  tools.append(searchLabel, showMore);
  list.before(tools);

  let visibleLimit = 25;
  const refresh = () => {
    const rows = Array.from(list.children).filter((row) => row.classList.contains('admin-list-item'));
    const query = search.value.trim().toLocaleLowerCase();
    const matches = rows.filter((row) => row.textContent.toLocaleLowerCase().includes(query));
    const visibleRows = new Set(matches.slice(0, visibleLimit));

    rows.forEach((row) => { row.hidden = !visibleRows.has(row); });
    tools.hidden = rows.length <= 5;
    showMore.hidden = matches.length <= visibleLimit;
  };

  search.addEventListener('input', () => {
    visibleLimit = 25;
    refresh();
  });
  showMore.addEventListener('click', () => {
    visibleLimit += 25;
    refresh();
  });
  new MutationObserver(refresh).observe(list, { childList: true });
  refresh();
}

document.querySelectorAll('.admin-list').forEach(attachAdminListTools);
document.querySelectorAll('form').forEach((form) => {
  const hiddenId = form.querySelector('input[type="hidden"][name="id"]');
  if (!hiddenId) return;
  form.addEventListener('reset', () => {
    hiddenId.value = '';
    hiddenId.defaultValue = '';
  });
});

const consoleQuickGuides = {
  pages: 'Edit and publish church information pages.',
  sermons: 'Add recordings and notes, then publish messages for visitors.',
  events: 'Publish events and review registrations.',
  alerts: 'Publish urgent notices and set an expiry when appropriate.',
  members: 'Find member records and update contact or consent details.',
  attendance: 'Record service check-ins and check members out.',
  rota: 'Collect availability, generate a rota, and review assignments.',
  groups: 'Maintain public group listings and follow up on waitlists.',
  children: 'Manage consented child records and authorized pickup members.',
  contact: 'Review enquiries and update their follow-up status.',
  visitors: 'Review visit requests and record follow-up progress.',
  prayer: 'Handle prayer requests confidentially and update their status.',
  finance: 'Record transactions and independently review pending items.',
  'care-tasks': 'Assign confidential follow-ups and mark completed tasks.',
  resources: 'Maintain resources and review booking requests.',
  documents: 'Store restricted documents and issue member certificates.',
  governance: 'Record meetings and resolutions; keep pastoral details private.',
  analytics: 'Filter aggregate ministry totals by date and branch.',
  branches: 'Maintain branches and assign records only after approval.',
  audit: 'Review recent staff activity for accountability.',
};

Object.entries(consoleQuickGuides).forEach(([name, guide]) => {
  const panel = document.querySelector(`#panel-${name}`);
  const heading = panel?.querySelector('.console-panel-heading');
  if (!heading) return;
  const guideLine = document.createElement('p');
  guideLine.className = 'console-quick-guide';
  guideLine.textContent = `Quick guide: ${guide}`;
  heading.append(guideLine);
});

consoleTabList.setAttribute('role', 'tablist');
consoleTabList.querySelectorAll('[data-tab]').forEach((button) => {
  const panel = document.getElementById(`panel-${button.dataset.tab}`);
  button.id = `console-tab-${button.dataset.tab}`;
  button.setAttribute('role', 'tab');
  button.setAttribute('aria-controls', panel.id);
  button.tabIndex = -1;
  panel.setAttribute('role', 'tabpanel');
  panel.tabIndex = 0;
});

consoleTabList.addEventListener('keydown', (event) => {
  const visibleTabs = Array.from(consoleTabList.querySelectorAll('[role="tab"]')).filter((button) => !button.hidden);
  const currentIndex = visibleTabs.indexOf(document.activeElement);
  if (currentIndex < 0) return;

  let nextIndex;
  if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % visibleTabs.length;
  else if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + visibleTabs.length) % visibleTabs.length;
  else if (event.key === 'Home') nextIndex = 0;
  else if (event.key === 'End') nextIndex = visibleTabs.length - 1;
  else return;

  event.preventDefault();
  const nextTab = visibleTabs[nextIndex];
  nextTab.focus();
  activateTab(nextTab.dataset.tab);
});

function toLocalDateTime(isoDate) {
  const localDate = new Date(new Date(isoDate).getTime() - new Date(isoDate).getTimezoneOffset() * 60000);
  return localDate.toISOString().slice(0, 16);
}

async function loadMembers() {
  const list = document.querySelector('#members-list');
  const status = document.querySelector('#member-status-filter').value;
  try {
    const members = await apiRequest(`/admin/members?status=${encodeURIComponent(status)}&limit=500`);
    list.replaceChildren();
    if (!members.length) return showEmpty(list, `No ${status === 'all' ? '' : `${status} `}members found.`);
    members.forEach((member) => {
      const details = [member.email, member.phone].filter(Boolean).join(' · ') || 'No contact details';
      const row = addAdminRow(
        list,
        member.name,
        `${member.status === 'active' ? 'Active' : 'Inactive'} · ${branchName(member.branch_id)} · ${details}`,
        'Edit',
        async () => {
          const form = document.querySelector('#member-form');
          form.elements.id.value = member.id;
          form.elements.name.value = member.name;
          form.elements.email.value = member.email || '';
          form.elements.phone.value = member.phone || '';
          setBranchSelectValue(form.elements.branch_id, member.branch_id);
          form.elements.consent_confirmed.required = false;
          form.querySelector('.member-consent').hidden = true;
          try {
            const preferences = await apiRequest(`/admin/members/${member.id}/communication-consents`);
            preferences.forEach((preference) => {
              const channel = preference.channel;
              document.querySelector(`#member-${channel}-consent`).checked = preference.is_consented;
              document.querySelector(`#member-${channel}-consent-source`).value = preference.consent_source;
            });
            if (preferences.length) {
              document.querySelector('#member-communication-frequency').value = preferences[0].delivery_frequency;
              document.querySelector('#member-quiet-hours-start').value = preferences[0].quiet_hours_start;
              document.querySelector('#member-quiet-hours-end').value = preferences[0].quiet_hours_end;
            }
          } catch (error) {
            setFormStatus(form, error.message, true);
          }
          form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
      );
      const statusButton = document.createElement('button');
      statusButton.type = 'button';
      statusButton.textContent = member.status === 'active' ? 'Deactivate' : 'Reactivate';
      statusButton.addEventListener('click', async () => {
        statusButton.disabled = true;
        const newStatus = member.status === 'active' ? 'inactive' : 'active';
        try {
          await apiRequest(`/admin/members/${member.id}/status?new_status=${newStatus}`, { method: 'PATCH' });
          await loadMembers();
        } catch (error) {
          statusButton.textContent = error.message;
          statusButton.disabled = false;
        }
      });
      row.append(statusButton);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadAlerts() {
  const list = document.querySelector('#alerts-list');
  try {
    const alerts = await apiRequest('/admin/alerts');
    list.replaceChildren();
    if (!alerts.length) return showEmpty(list, 'No emergency alerts have been created.');
    alerts.forEach((alert) => {
      const expiration = alert.expires_at
        ? `Expires ${new Intl.DateTimeFormat('en-UG', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(alert.expires_at))}`
        : 'No expiration';
      const row = addAdminRow(
        list,
        alert.title,
        `${alert.is_active ? 'Active' : 'Inactive'} · ${expiration}`,
        'Edit',
        () => {
          const form = document.querySelector('#alert-form');
          form.elements.id.value = alert.id;
          form.elements.title.value = alert.title;
          form.elements.message.value = alert.message;
          form.elements.expires_at.value = alert.expires_at ? toLocalDateTime(alert.expires_at) : '';
          form.elements.is_active.checked = alert.is_active;
          form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
      );
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.textContent = alert.is_active ? 'Deactivate' : 'Activate';
      toggle.addEventListener('click', async () => {
        toggle.disabled = true;
        const newStatus = alert.is_active ? 'inactive' : 'active';
        try {
          await apiRequest(`/admin/alerts/${alert.id}/status?new_status=${newStatus}`, { method: 'PATCH' });
          await loadAlerts();
        } catch (error) {
          toggle.textContent = error.message;
          toggle.disabled = false;
        }
      });
      row.append(toggle);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function showGroupWaitlist(group) {
  const panel = document.querySelector('#group-waitlist-panel');
  const list = document.querySelector('#group-waitlist-list');
  document.querySelector('#group-waitlist-title').textContent = `Waitlist · ${group.name}`;
  panel.hidden = false;
  try {
    const requests = await apiRequest(`/admin/groups/${group.id}/waitlist`);
    list.replaceChildren();
    if (!requests.length) return showEmpty(list, 'There are no waitlist requests for this group.');
    requests.forEach((request) => {
      const row = document.createElement('article');
      row.className = 'admin-list-item';
      const heading = document.createElement('h3');
      heading.textContent = request.name;
      const contact = document.createElement('p');
      contact.textContent = request.contact;
      const followup = document.createElement('div');
      followup.className = 'prayer-followup';
      const status = document.createElement('select');
      status.setAttribute('aria-label', `Waitlist status for ${request.name}`);
      [['new', 'New'], ['contacted', 'Contacted'], ['placed', 'Placed'], ['closed', 'Closed']].forEach(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        status.append(option);
      });
      status.value = request.status;
      const save = document.createElement('button');
      save.type = 'button';
      save.textContent = 'Save status';
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          await apiRequest(`/admin/groups/${group.id}/waitlist/${request.id}/status?new_status=${encodeURIComponent(status.value)}`, { method: 'PATCH' });
          save.textContent = 'Saved';
        } catch (error) {
          save.textContent = error.message;
        } finally {
          save.disabled = false;
        }
      });
      followup.append(status, save);
      row.append(heading, contact, followup);
      list.append(row);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadGroups() {
  const list = document.querySelector('#groups-list');
  try {
    const branchId = document.querySelector('#group-branch-filter').value;
    const groups = await apiRequest(branchId ? `/admin/groups?branch_id=${encodeURIComponent(branchId)}` : '/admin/groups');
    list.replaceChildren();
    if (!groups.length) return showEmpty(list, 'No small groups have been added.');
    groups.forEach((group) => {
      const row = addAdminRow(
        list,
        group.name,
        `${group.meeting_area} · ${branchName(group.branch_id)} · ${group.meeting_day} · ${group.age_group} · ${group.is_open ? 'Open' : 'Waitlist'} · ${group.is_published ? 'Published' : 'Draft'}`,
        'Edit',
        () => {
          const form = document.querySelector('#group-form');
          form.elements.id.value = group.id;
          form.elements.name.value = group.name;
          setBranchSelectValue(form.elements.branch_id, group.branch_id);
          form.elements.description.value = group.description;
          form.elements.meeting_area.value = group.meeting_area;
          form.elements.meeting_day.value = group.meeting_day;
          form.elements.meeting_time.value = group.meeting_time;
          form.elements.age_group.value = group.age_group;
          form.elements.latitude.value = group.latitude ?? '';
          form.elements.longitude.value = group.longitude ?? '';
          form.elements.is_open.checked = group.is_open;
          form.elements.is_published.checked = group.is_published;
          form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
      );
      if (['admin', 'pastor'].includes(currentStaffRole)) {
        const waitlist = document.createElement('button');
        waitlist.type = 'button';
        waitlist.textContent = 'View waitlist';
        waitlist.addEventListener('click', () => showGroupWaitlist(group));
        row.append(waitlist);
      }
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

function rotaScope() {
  return {
    serviceName: document.querySelector('#rota-service-name').value.trim(),
    serviceDate: document.querySelector('#rota-service-date').value,
  };
}

async function loadVolunteerAvailability() {
  const list = document.querySelector('#availability-list');
  const { serviceName, serviceDate } = rotaScope();
  if (!serviceName || !serviceDate) return showEmpty(list, 'Choose a service and date to view availability.');
  try {
    const params = new URLSearchParams({ service_name: serviceName, service_date: serviceDate });
    const records = await apiRequest(`/admin/volunteer-availability?${params}`);
    list.replaceChildren();
    if (!records.length) return showEmpty(list, 'No availability has been recorded for this service.');
    records.forEach((record) => addAdminRow(
      list,
      record.member_name,
      record.is_available ? 'Available' : 'Unavailable',
    ));
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadRota() {
  const list = document.querySelector('#rota-list');
  const { serviceName, serviceDate } = rotaScope();
  if (!serviceName || !serviceDate) return showEmpty(list, 'Choose a service and date to view the rota.');
  try {
    const params = new URLSearchParams({ service_name: serviceName, service_date: serviceDate });
    const assignments = await apiRequest(`/admin/rota?${params}`);
    list.replaceChildren();
    if (!assignments.length) return showEmpty(list, 'No volunteers have been assigned for this service.');
    assignments.forEach((assignment) => addAdminRow(
      list,
      assignment.role_name,
      assignment.member_name,
    ));
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadRotaPanel() {
  const select = document.querySelector('#availability-member');
  try {
    activeAttendanceMembers = await apiRequest('/admin/attendance/members');
    fillMemberSelect(select, activeAttendanceMembers, 'Choose a volunteer');
  } catch (error) {
    select.replaceChildren(new Option(error.message, ''));
  }
  if (!document.querySelector('#rota-service-date').value) {
    document.querySelector('#rota-service-date').value = localDateValue();
  }
  await Promise.all([loadVolunteerAvailability(), loadRota()]);
}

async function loadAttendanceMembers() {
  const select = document.querySelector('#attendance-member');
  const selectedId = select.value;
  try {
    const members = await apiRequest('/admin/attendance/members');
    activeAttendanceMembers = members;
    select.replaceChildren();
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = members.length ? 'Choose a member' : 'No active members';
    select.append(placeholder);
    members.forEach((member) => {
      const option = document.createElement('option');
      option.value = member.id;
      option.textContent = member.name;
      select.append(option);
    });
    select.value = selectedId;
  } catch (error) {
    select.replaceChildren(new Option(error.message, ''));
  }
}

async function loadAttendance() {
  const list = document.querySelector('#attendance-list');
  const serviceDate = document.querySelector('#attendance-list-date').value;
  if (!serviceDate) return;
  try {
    const records = await apiRequest(`/admin/attendance?service_date=${encodeURIComponent(serviceDate)}`);
    list.replaceChildren();
    if (!records.length) return showEmpty(list, 'No attendance has been recorded for this date.');
    records.forEach((record) => {
      const checkedIn = new Intl.DateTimeFormat('en-UG', { timeStyle: 'short' }).format(new Date(record.checked_in_at));
      const checkoutDetail = record.checked_out_at
        ? `Checked out ${new Intl.DateTimeFormat('en-UG', { timeStyle: 'short' }).format(new Date(record.checked_out_at))}`
        : 'Still checked in';
      addAdminRow(
        list,
        record.member_name,
        `${record.service_name} · ${branchName(record.branch_id)} · ${record.check_in_method} · In ${checkedIn} · ${checkoutDetail}`,
        record.checked_out_at ? null : 'Check out',
        async () => {
          try {
            await apiRequest(`/admin/attendance/${record.id}/check-out`, { method: 'PATCH' });
            await loadAttendance();
          } catch (error) {
            showEmpty(list, error.message);
          }
        },
      );
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadAttendancePanel() {
  await Promise.all([loadAttendanceMembers(), loadAttendance()]);
}

function fillMemberSelect(select, members, placeholder, selectedIds = []) {
  select.replaceChildren();
  if (!select.multiple) {
    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = placeholder;
    select.append(emptyOption);
  }
  members.forEach((member) => {
    const option = document.createElement('option');
    option.value = member.id;
    option.textContent = member.name;
    option.selected = selectedIds.includes(member.id);
    select.append(option);
  });
}

function authorizedAdults(child) {
  const ids = new Set([child.primary_guardian_id, ...child.authorized_pickup_member_ids]);
  return activeAttendanceMembers.filter((member) => ids.has(member.id));
}

function updateChildAttendanceAdultOptions() {
  const childId = Number(document.querySelector('#child-attendance-child').value);
  const child = childProfiles.find((profile) => profile.id === childId);
  const select = document.querySelector('#child-attendance-adult');
  fillMemberSelect(select, child ? authorizedAdults(child) : [], child ? 'Choose an authorized adult' : 'Choose a child first');
}

async function loadChildren() {
  const list = document.querySelector('#children-list');
  try {
    childProfiles = await apiRequest('/admin/children?active_only=false');
    list.replaceChildren();
    if (!childProfiles.length) showEmpty(list, 'No child profiles have been created.');
    childProfiles.forEach((child) => {
      const guardianName = activeAttendanceMembers.find((member) => member.id === child.primary_guardian_id)?.name || `Member ${child.primary_guardian_id}`;
      const pickupNames = child.authorized_pickup_member_ids.map((id) => (
        activeAttendanceMembers.find((member) => member.id === id)?.name || `Member ${id}`
      ));
      const detail = `${child.is_active ? 'Active' : 'Inactive'} · Guardian: ${guardianName} · Pickups: ${pickupNames.join(', ') || 'Guardian only'}`;
      const row = addAdminRow(list, child.name, detail, 'Edit', () => {
        const form = document.querySelector('#child-form');
        form.elements.id.value = child.id;
        form.elements.name.value = child.name;
        form.elements.primary_guardian_id.value = child.primary_guardian_id;
        Array.from(form.elements.authorized_pickup_member_ids.options).forEach((option) => {
          option.selected = child.authorized_pickup_member_ids.includes(Number(option.value));
        });
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      const statusButton = document.createElement('button');
      statusButton.type = 'button';
      statusButton.textContent = child.is_active ? 'Deactivate' : 'Reactivate';
      statusButton.addEventListener('click', async () => {
        statusButton.disabled = true;
        const newStatus = child.is_active ? 'inactive' : 'active';
        try {
          await apiRequest(`/admin/children/${child.id}/status?new_status=${newStatus}`, { method: 'PATCH' });
          await loadChildren();
        } catch (error) {
          statusButton.textContent = error.message;
          statusButton.disabled = false;
        }
      });
      row.append(statusButton);
    });

    const activeChildren = childProfiles.filter((child) => child.is_active);
    fillChildSelect(document.querySelector('#child-attendance-child'), activeChildren);
    fillMemberSelect(
      document.querySelector('#child-guardian'),
      activeAttendanceMembers,
      activeAttendanceMembers.length ? 'Choose a guardian' : 'No active members',
    );
    fillMemberSelect(
      document.querySelector('#child-pickups'),
      activeAttendanceMembers,
      'Select authorized pickup members',
    );
    updateChildAttendanceAdultOptions();
  } catch (error) {
    showEmpty(list, error.message);
  }
}

function fillChildSelect(select, children) {
  select.replaceChildren();
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = children.length ? 'Choose a child' : 'No active child profiles';
  select.append(placeholder);
  children.forEach((child) => {
    const option = document.createElement('option');
    option.value = child.id;
    option.textContent = child.name;
    select.append(option);
  });
}

async function loadChildAttendance() {
  const list = document.querySelector('#child-attendance-list');
  const serviceDate = document.querySelector('#child-attendance-list-date').value;
  if (!serviceDate) return;
  try {
    const records = await apiRequest(`/admin/child-attendance?service_date=${encodeURIComponent(serviceDate)}`);
    list.replaceChildren();
    if (!records.length) return showEmpty(list, 'No child check-ins have been recorded for this date.');
    records.forEach((record) => {
      const checkedIn = new Intl.DateTimeFormat('en-UG', { timeStyle: 'short' }).format(new Date(record.checked_in_at));
      const checkedOut = record.checked_out_at
        ? `Picked up by ${record.checked_out_by_name}`
        : `Checked in by ${record.checked_in_by_name} at ${checkedIn}`;
      const row = addAdminRow(list, record.child_name, `${record.service_name} · ${checkedOut}`, null, null);
      if (!record.checked_out_at) {
        const child = childProfiles.find((profile) => profile.id === record.child_id);
        const controls = document.createElement('div');
        controls.className = 'child-checkout-controls';
        const adultSelect = document.createElement('select');
        adultSelect.setAttribute('aria-label', `Authorized pickup adult for ${record.child_name}`);
        fillMemberSelect(adultSelect, child ? authorizedAdults(child) : [], 'Select verified adult');
        const checkout = document.createElement('button');
        checkout.type = 'button';
        checkout.textContent = 'Confirm pickup';
        checkout.disabled = true;
        adultSelect.addEventListener('change', () => { checkout.disabled = !adultSelect.value; });
        checkout.addEventListener('click', async () => {
          checkout.disabled = true;
          try {
            await apiRequest(`/admin/child-attendance/${record.id}/check-out`, {
              method: 'PATCH',
              body: JSON.stringify({ checked_out_by_member_id: Number(adultSelect.value) }),
            });
            await loadChildAttendance();
          } catch (error) {
            checkout.textContent = error.message;
            checkout.disabled = false;
          }
        });
        controls.append(adultSelect, checkout);
        row.append(controls);
      }
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadChildPanel() {
  await loadAttendanceMembers();
  await loadChildren();
  await loadChildAttendance();
}

async function loadPages() {
  const list = document.querySelector('#pages-list');
  try {
    const pages = await apiRequest('/admin/pages');
    list.replaceChildren();
    if (!pages.length) return showEmpty(list, 'No pages have been created yet.');
    pages.forEach((page) => {
      const row = addAdminRow(
        list,
        page.title,
        `/${page.slug} · ${page.is_published ? 'Published' : 'Draft'}`,
        'Edit',
        () => {
        const form = document.querySelector('#page-form');
        form.elements.id.value = page.id;
        form.elements.slug.value = page.slug;
        form.elements.title.value = page.title;
        form.elements.body.value = page.body;
        form.elements.is_published.checked = page.is_published;
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
      );
      if (page.is_published) {
        const preview = document.createElement('a');
        preview.className = 'button button-green';
        preview.href = `index.html?page=${encodeURIComponent(page.slug)}`;
        preview.target = '_blank';
        preview.rel = 'noopener';
        preview.textContent = 'View page';
        row.append(preview);
      }
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadSermons() {
  const list = document.querySelector('#sermons-list');
  try {
    const sermons = await apiRequest('/admin/sermons');
    list.replaceChildren();
    if (!sermons.length) return showEmpty(list, 'No messages have been added yet.');
    sermons.forEach((sermon) => addAdminRow(
      list,
      sermon.title,
      `${sermon.speaker} · ${sermon.is_published ? 'Published' : 'Draft'}`,
      'Edit',
      () => {
        const form = document.querySelector('#sermon-form');
        form.elements.id.value = sermon.id;
        form.elements.title.value = sermon.title;
        form.elements.speaker.value = sermon.speaker;
        form.elements.scripture.value = sermon.scripture || '';
        form.elements.summary.value = sermon.summary || '';
        form.elements.media_url.value = sermon.media_url || '';
        form.elements.published_at.value = toLocalDateTime(sermon.published_at);
        form.elements.is_published.checked = sermon.is_published;
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
      },
    ));
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function showRegistrations(churchEvent) {
  const panel = document.querySelector('#registration-results');
  const heading = document.createElement('h3');
  heading.textContent = `Registrations · ${churchEvent.title}`;
  panel.replaceChildren(heading);
  try {
    const registrations = await apiRequest(`/admin/events/${churchEvent.id}/registrations`);
    if (!registrations.length) {
      const empty = document.createElement('p');
      empty.className = 'list-empty';
      empty.textContent = 'No registrations yet.';
      panel.append(empty);
      return;
    }
    registrations.forEach((registration) => {
      const row = document.createElement('div');
      row.className = 'registration-row';
      row.textContent = `${registration.name} · ${registration.email}`;
      panel.append(row);
    });
  } catch (error) {
    const message = document.createElement('p');
    message.className = 'list-empty';
    message.textContent = error.message;
    panel.append(message);
  }
}

async function loadEvents() {
  const list = document.querySelector('#events-list');
  try {
    const events = await apiRequest('/admin/events');
    list.replaceChildren();
    if (!events.length) return showEmpty(list, 'No events have been created yet.');
    events.forEach((churchEvent) => {
      const row = addAdminRow(
      list,
      churchEvent.title,
      `${new Intl.DateTimeFormat('en-UG', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(churchEvent.starts_at))} · ${branchName(churchEvent.branch_id)} · ${churchEvent.is_published ? 'Published' : 'Draft'}`,
      'Edit',
      () => {
        const form = document.querySelector('#event-form');
        form.elements.id.value = churchEvent.id;
        form.elements.title.value = churchEvent.title;
        form.elements.description.value = churchEvent.description || '';
        form.elements.location.value = churchEvent.location;
        setBranchSelectValue(form.elements.branch_id, churchEvent.branch_id);
        form.elements.starts_at.value = toLocalDateTime(churchEvent.starts_at);
        form.elements.capacity.value = churchEvent.capacity || '';
        form.elements.registration_open.checked = churchEvent.registration_open;
        form.elements.is_published.checked = churchEvent.is_published;
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
      },
      );
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'registrations-button';
      button.textContent = 'View RSVPs';
      button.addEventListener('click', () => showRegistrations(churchEvent));
      row.append(button);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadPrayerRequests() {
  const list = document.querySelector('#prayer-list');
  try {
    const requests = await apiRequest('/admin/prayer-requests');
    list.replaceChildren();
    if (!requests.length) return showEmpty(list, 'There are no prayer requests to follow up yet.');
    requests.forEach((request) => {
      const row = document.createElement('article');
      row.className = 'admin-list-item';
      const title = document.createElement('h3');
      title.textContent = request.name || 'Name not provided';
      const contact = document.createElement('p');
      contact.textContent = request.contact || 'No contact details';
      const message = document.createElement('p');
      message.className = 'prayer-detail';
      message.textContent = request.message;
      const followup = document.createElement('div');
      followup.className = 'prayer-followup';
      const status = document.createElement('select');
      status.setAttribute('aria-label', `Follow-up status for ${title.textContent}`);
      [['new', 'New'], ['follow_up', 'Follow-up'], ['closed', 'Closed']].forEach(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        status.append(option);
      });
      status.value = request.status;
      const save = document.createElement('button');
      save.type = 'button';
      save.textContent = 'Save status';
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          await apiRequest(`/admin/prayer-requests/${request.id}/status?new_status=${encodeURIComponent(status.value)}`, { method: 'PATCH' });
          save.textContent = 'Saved';
        } catch (error) {
          save.textContent = error.message;
        } finally {
          save.disabled = false;
        }
      });
      followup.append(status, save);
      row.append(title, contact, message, followup);
      list.append(row);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadContactInquiries() {
  const list = document.querySelector('#contact-list');
  try {
    const inquiries = await apiRequest('/admin/contact-inquiries');
    list.replaceChildren();
    if (!inquiries.length) return showEmpty(list, 'There are no contact inquiries to follow up yet.');
    inquiries.forEach((inquiry) => {
      const row = document.createElement('article');
      row.className = 'admin-list-item';
      const heading = document.createElement('h3');
      heading.textContent = `${inquiry.subject} · ${inquiry.name}`;
      const email = document.createElement('p');
      email.textContent = inquiry.email;
      const message = document.createElement('p');
      message.className = 'prayer-detail';
      message.textContent = inquiry.message;
      const followup = document.createElement('div');
      followup.className = 'prayer-followup';
      const status = document.createElement('select');
      status.setAttribute('aria-label', `Follow-up status for ${inquiry.subject}`);
      [['new', 'New'], ['follow_up', 'Follow-up'], ['closed', 'Closed']].forEach(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        status.append(option);
      });
      status.value = inquiry.status;
      const save = document.createElement('button');
      save.type = 'button';
      save.textContent = 'Save status';
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          await apiRequest(`/admin/contact-inquiries/${inquiry.id}/status?new_status=${encodeURIComponent(status.value)}`, { method: 'PATCH' });
          save.textContent = 'Saved';
        } catch (error) {
          save.textContent = error.message;
        } finally {
          save.disabled = false;
        }
      });
      followup.append(status, save);
      row.append(heading, email, message, followup);
      list.append(row);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadVisitorVisits() {
  const list = document.querySelector('#visitor-list');
  try {
    const visits = await apiRequest('/admin/visitors');
    list.replaceChildren();
    if (!visits.length) return showEmpty(list, 'No planned visits have been submitted.');
    visits.forEach((visit) => {
      const row = document.createElement('article');
      row.className = 'admin-list-item';
      const heading = document.createElement('h3');
      heading.textContent = visit.name;
      const contact = document.createElement('p');
      contact.textContent = visit.contact;
      const date = document.createElement('p');
      date.textContent = visit.visit_date ? `Hoping to visit: ${visit.visit_date}` : 'Visit date not provided';
      const followup = document.createElement('div');
      followup.className = 'prayer-followup';
      const status = document.createElement('select');
      status.setAttribute('aria-label', `Follow-up status for ${visit.name}`);
      [['new', 'New'], ['contacted', 'Contacted'], ['closed', 'Closed']].forEach(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        status.append(option);
      });
      status.value = visit.status;
      const save = document.createElement('button');
      save.type = 'button';
      save.textContent = 'Save status';
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          await apiRequest(`/admin/visitors/${visit.id}/status?new_status=${encodeURIComponent(status.value)}`, { method: 'PATCH' });
          save.textContent = 'Saved';
        } catch (error) {
          save.textContent = error.message;
        } finally {
          save.disabled = false;
        }
      });
      followup.append(status, save);
      row.append(heading, contact, date, followup);
      list.append(row);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadAudit() {
  const list = document.querySelector('#audit-list');
  try {
    const logs = await apiRequest('/admin/audit-logs');
    list.replaceChildren();
    if (!logs.length) return showEmpty(list, 'No staff activity has been recorded yet.');
    logs.forEach((log) => addAdminRow(
      list,
      `${log.action} · ${log.entity_type} #${log.entity_id}`,
      `Staff account ${log.actor_id} · ${new Intl.DateTimeFormat('en-UG', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(log.occurred_at))}`,
    ));
  } catch (error) {
    showEmpty(list, error.message);
  }
}

function formatUgx(value) {
  return `${new Intl.NumberFormat('en-UG').format(value)} UGX`;
}

async function loadFinance() {
  const entriesList = document.querySelector('#finance-entries-list');
  const budgetsList = document.querySelector('#finance-budgets-list');
  const pledgesList = document.querySelector('#finance-pledges-list');
  const offeringCountsList = document.querySelector('#offering-counts-list');
  try {
    const [entries, budgets, pledges, offeringCounts] = await Promise.all([
      apiRequest('/admin/finance/entries?limit=100'),
      apiRequest('/admin/finance/budgets'),
      apiRequest('/admin/finance/pledges'),
      apiRequest('/admin/finance/offering-counts?limit=100'),
    ]);
    entriesList.replaceChildren();
    if (!entries.length) showEmpty(entriesList, 'No finance entries have been recorded.');
    entries.forEach((entry) => {
      const canReview = entry.status === 'pending'
        && (entry.entry_type === 'expense' || entry.correction_of_id !== null)
        && entry.recorded_by_id !== currentStaffId;
      const row = addAdminRow(
        entriesList,
        `${entry.correction_of_id ? `Correction for #${entry.correction_of_id} · ` : ''}${entry.entry_type === 'income' ? 'Income' : 'Expense'} · ${formatUgx(entry.amount_ugx)}`,
        `${entry.entry_date} · ${branchName(entry.branch_id)} · ${entry.fund} / ${entry.category} · ${entry.status}${entry.details ? ` · ${entry.details}` : ''}`,
        canReview ? 'Approve' : '',
        async () => {
          try {
            await apiRequest(`/admin/finance/entries/${entry.id}/approval?status=approved`, { method: 'PATCH' });
            await loadFinance();
          } catch (error) {
            setFormStatus(document.querySelector('#finance-entry-form'), error.message, true);
          }
        },
      );
      if (canReview) {
        const reject = document.createElement('button');
        reject.type = 'button';
        reject.textContent = 'Reject';
        reject.addEventListener('click', async () => {
          try {
            await apiRequest(`/admin/finance/entries/${entry.id}/approval?status=rejected`, { method: 'PATCH' });
            await loadFinance();
          } catch (error) {
            setFormStatus(document.querySelector('#finance-entry-form'), error.message, true);
          }
        });
        row.append(reject);
      }
      if (!entry.correction_of_id && (entry.status === 'recorded' || (entry.entry_type === 'expense' && entry.status === 'approved'))) {
        const correct = document.createElement('button');
        correct.type = 'button';
        correct.textContent = 'Request correction';
        correct.addEventListener('click', async () => {
          const reason = window.prompt('Why does this entry need a correction? The original stays unchanged; the offset requires independent approval.');
          if (!reason) return;
          correct.disabled = true;
          try {
            await apiRequest(`/admin/finance/entries/${entry.id}/correction`, {
              method: 'POST',
              body: JSON.stringify({ reason }),
            });
            await loadFinance();
          } catch (error) {
            correct.textContent = error.message;
            correct.disabled = false;
          }
        });
        row.append(correct);
      }
    });
    budgetsList.replaceChildren();
    if (!budgets.length) showEmpty(budgetsList, 'No budgets have been set.');
    budgets.forEach((budget) => addAdminRow(
      budgetsList,
      `${budget.fund} · ${budget.category}`,
      `${budget.period_start} to ${budget.period_end} · ${branchName(budget.branch_id)} · ${formatUgx(budget.spent_ugx)} spent of ${formatUgx(budget.amount_ugx)}`,
    ));
    pledgesList.replaceChildren();
    if (!pledges.length) showEmpty(pledgesList, 'No pledges have been recorded.');
    pledges.forEach((pledge) => {
      const row = addAdminRow(
        pledgesList,
        `${pledge.campaign} · ${formatUgx(pledge.amount_ugx)}`,
        `${pledge.donor_name} · ${branchName(pledge.branch_id)}${pledge.due_date ? ` · Due ${pledge.due_date}` : ''} · ${formatUgx(pledge.amount_fulfilled_ugx)} fulfilled · ${pledge.status}`,
      );
      const status = document.createElement('select');
      status.setAttribute('aria-label', `Pledge status for ${pledge.donor_name}`);
      [['pledged', 'Pledged'], ['partially_fulfilled', 'Partially fulfilled'], ['fulfilled', 'Fulfilled'], ['cancelled', 'Cancelled']].forEach(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        status.append(option);
      });
      status.value = pledge.status;
      const fulfilledAmount = document.createElement('input');
      fulfilledAmount.type = 'number';
      fulfilledAmount.min = '0';
      fulfilledAmount.max = String(pledge.amount_ugx);
      fulfilledAmount.step = '1';
      fulfilledAmount.value = String(pledge.amount_fulfilled_ugx);
      fulfilledAmount.setAttribute('aria-label', `Fulfilled pledge amount for ${pledge.donor_name}`);
      status.addEventListener('change', () => {
        if (status.value === 'fulfilled') fulfilledAmount.value = String(pledge.amount_ugx);
        else if (status.value === 'pledged') fulfilledAmount.value = '0';
      });
      const save = document.createElement('button');
      save.type = 'button';
      save.textContent = 'Save status';
      save.disabled = ['fulfilled', 'cancelled'].includes(pledge.status);
      save.addEventListener('click', async () => {
        try {
          await apiRequest(`/admin/finance/pledges/${pledge.id}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status: status.value, amount_fulfilled_ugx: Number(fulfilledAmount.value) }),
          });
          await loadFinance();
        } catch (error) {
          save.textContent = error.message;
        }
      });
      row.append(status, fulfilledAmount, save);
    });
    offeringCountsList.replaceChildren();
    if (!offeringCounts.length) showEmpty(offeringCountsList, 'No two-person offering counts have been recorded.');
    offeringCounts.forEach((batch) => {
      const row = addAdminRow(
        offeringCountsList,
        `${batch.service_name} · ${batch.service_date} · ${batch.fund}/${batch.category}`,
        `${branchName(batch.branch_id)} · First count ${formatUgx(batch.amount_counted_ugx)} · ${batch.verified_amount_ugx === null ? 'Not yet verified' : `Second count ${formatUgx(batch.verified_amount_ugx)}`} · ${batch.status}${batch.final_amount_ugx === null ? '' : ` · Posted ${formatUgx(batch.final_amount_ugx)}`}`,
      );
      if (batch.status === 'pending' && batch.counted_by_id !== currentStaffId) {
        const verify = document.createElement('button');
        verify.type = 'button';
        verify.textContent = 'Enter independent recount';
        verify.addEventListener('click', async () => {
          const amount = window.prompt('Enter your independent recount amount in whole UGX.');
          if (amount === null) return;
          const amountUgx = Number(amount);
          if (!Number.isSafeInteger(amountUgx) || amountUgx < 1) {
            verify.textContent = 'Enter a valid whole UGX amount';
            return;
          }
          verify.disabled = true;
          try {
            const result = await apiRequest(`/admin/finance/offering-counts/${batch.id}/verify`, {
              method: 'POST',
              body: JSON.stringify({ amount_ugx: amountUgx }),
            });
            if (result.status === 'discrepancy') {
              setFormStatus(document.querySelector('#offering-count-form'), 'Counts differ. No income was posted; a third finance staff member must resolve the recount.', true);
            }
            await loadFinance();
          } catch (error) {
            verify.textContent = error.message;
            verify.disabled = false;
          }
        });
        row.append(verify);
      }
      if (batch.status === 'discrepancy' && batch.counted_by_id !== currentStaffId && batch.verified_by_id !== currentStaffId) {
        const resolve = document.createElement('button');
        resolve.type = 'button';
        resolve.textContent = 'Resolve discrepancy';
        resolve.addEventListener('click', async () => {
          const amount = window.prompt('Enter the independently recounted amount in whole UGX. No income posts until this resolution is recorded.');
          if (amount === null) return;
          const amountUgx = Number(amount);
          if (!Number.isSafeInteger(amountUgx) || amountUgx < 1) {
            resolve.textContent = 'Enter a valid whole UGX amount';
            return;
          }
          const reason = window.prompt('Record the reason for this resolution (minimum five characters).');
          if (reason === null || reason.trim().length < 5) return;
          resolve.disabled = true;
          try {
            await apiRequest(`/admin/finance/offering-counts/${batch.id}/resolve`, {
              method: 'POST',
              body: JSON.stringify({ amount_ugx: amountUgx, reason }),
            });
            await loadFinance();
          } catch (error) {
            resolve.textContent = error.message;
            resolve.disabled = false;
          }
        });
        row.append(resolve);
      }
    });
  } catch (error) {
    showEmpty(entriesList, error.message);
    showEmpty(budgetsList, error.message);
    showEmpty(pledgesList, error.message);
    showEmpty(offeringCountsList, error.message);
  }
}

async function loadActiveMembersInto(selectIds) {
  const members = await apiRequest('/admin/members?status=active&limit=500');
  selectIds.forEach((selector) => {
    const select = document.querySelector(selector);
    select.replaceChildren();
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Choose a member';
    select.append(placeholder);
    members.forEach((member) => {
      const option = document.createElement('option');
      option.value = member.id;
      option.textContent = member.name;
      select.append(option);
    });
  });
  return members;
}

async function loadPastoralCareTasks() {
  const list = document.querySelector('#care-tasks-list');
  try {
    const [, tasks] = await Promise.all([
      loadActiveMembersInto(['#care-task-member']),
      apiRequest('/admin/pastoral-care/tasks?status=open'),
    ]);
    list.replaceChildren();
    if (!tasks.length) return showEmpty(list, 'There are no open care follow-ups.');
    tasks.forEach((task) => {
      const row = addAdminRow(
        list,
        `${task.member_name} · ${task.care_type.replaceAll('_', ' ')}`,
        `${task.priority.toUpperCase()} · ${task.due_date || 'No due date'} · ${task.notes}`,
        'Complete',
        async (event) => {
          event.currentTarget.disabled = true;
          try {
            await apiRequest(`/admin/pastoral-care/tasks/${task.id}`, {
              method: 'PUT',
              body: JSON.stringify({
                priority: task.priority,
                due_date: task.due_date,
                status: 'completed',
                notes: task.notes,
                assigned_to_id: task.assigned_to_id,
              }),
            });
            await loadPastoralCareTasks();
          } catch (error) {
            event.currentTarget.textContent = error.message;
            event.currentTarget.disabled = false;
          }
        },
      );
      row.classList.add('prayer-list-item');
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadResourceBookings() {
  const resourcesList = document.querySelector('#resources-list');
  const bookingsList = document.querySelector('#resource-bookings-list');
  try {
    const branchId = document.querySelector('#resource-branch-filter').value;
    const resourceParams = new URLSearchParams({ include_inactive: 'true' });
    if (branchId) resourceParams.set('branch_id', branchId);
    const [resources, bookings] = await Promise.all([
      apiRequest(`/admin/resources?${resourceParams}`),
      apiRequest(branchId ? `/admin/resource-bookings?branch_id=${encodeURIComponent(branchId)}` : '/admin/resource-bookings'),
    ]);
    const resourceSelect = document.querySelector('#booking-resource');
    const activeResources = resources.filter((resource) => resource.is_active);
    resourceSelect.replaceChildren();
    const emptyOption = document.createElement('option');
    emptyOption.value = '';
    emptyOption.textContent = 'Choose a resource';
    resourceSelect.append(emptyOption);
    activeResources.forEach((resource) => {
      const option = document.createElement('option');
      option.value = resource.id;
      option.textContent = resource.name;
      resourceSelect.append(option);
    });
    resourcesList.replaceChildren();
    if (!activeResources.length) showEmpty(resourcesList, 'No active resources have been added.');
    resources.forEach((resource) => {
      const row = addAdminRow(resourcesList, resource.name, `${resource.description || 'No description'} · ${branchName(resource.branch_id)} · ${resource.is_active ? 'Active' : 'Inactive'}`);
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.textContent = 'Edit';
      edit.addEventListener('click', () => {
        const form = document.querySelector('#resource-form');
        form.elements.id.value = resource.id;
        form.elements.name.value = resource.name;
        form.elements.description.value = resource.description || '';
        setBranchSelectValue(form.elements.branch_id, resource.branch_id);
        form.elements.is_active.checked = resource.is_active;
        form.querySelector('h3').textContent = 'Edit resource';
        form.querySelector('button[type="submit"]').textContent = 'Update resource';
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      row.append(edit);
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.textContent = resource.is_active ? 'Deactivate' : 'Reactivate';
      toggle.addEventListener('click', async () => {
        try {
          await apiRequest(`/admin/resources/${resource.id}`, {
            method: 'PUT',
            body: JSON.stringify({ name: resource.name, description: resource.description, is_active: !resource.is_active }),
          });
          await loadResourceBookings();
        } catch (error) {
          toggle.textContent = error.message;
        }
      });
      row.append(toggle);
    });
    bookingsList.replaceChildren();
    if (!bookings.length) showEmpty(bookingsList, 'No resource bookings have been requested.');
    bookings.forEach((booking) => {
      const row = addAdminRow(
        bookingsList,
        `${booking.resource_name} · ${booking.status}`,
        `${new Date(booking.starts_at).toLocaleString('en-UG')} – ${new Date(booking.ends_at).toLocaleString('en-UG')} · ${branchName(booking.branch_id)} · ${booking.purpose}`,
      );
      if (booking.status === 'pending') {
        ['approved', 'rejected'].forEach((nextStatus) => {
          const button = document.createElement('button');
          button.type = 'button';
          button.textContent = nextStatus === 'approved' ? 'Approve' : 'Reject';
          button.addEventListener('click', async () => {
            try {
              await apiRequest(`/admin/resource-bookings/${booking.id}/status`, {
                method: 'PATCH',
                body: JSON.stringify({ status: nextStatus }),
              });
              await loadResourceBookings();
            } catch (error) {
              button.textContent = error.message;
            }
          });
          row.append(button);
        });
      }
      if (booking.status === 'approved') {
        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.textContent = 'Cancel booking';
        cancel.addEventListener('click', async () => {
          try {
            await apiRequest(`/admin/resource-bookings/${booking.id}/status`, {
              method: 'PATCH',
              body: JSON.stringify({ status: 'cancelled' }),
            });
            await loadResourceBookings();
          } catch (error) {
            cancel.textContent = error.message;
          }
        });
        row.append(cancel);
      }
    });
  } catch (error) {
    showEmpty(resourcesList, error.message);
    showEmpty(bookingsList, error.message);
  }
}

async function downloadStaffDocument(documentRecord, button) {
  button.disabled = true;
  try {
    const token = sessionStorage.getItem('bwala_staff_token');
    const response = await fetch(`${apiBase}/api/v1/admin/documents/${documentRecord.id}/download`, {
      headers: { Authorization: `******` },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || 'Document download failed.');
    }
    const downloadUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = documentRecord.filename;
    link.click();
    URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    button.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function downloadMemberCertificate(certificate, button) {
  button.disabled = true;
  try {
    const token = sessionStorage.getItem('bwala_staff_token');
    const response = await fetch(
      `${apiBase}/api/v1/admin/certificates/${certificate.id}/download`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || 'Certificate download failed.');
    }
    const downloadUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `certificate-${certificate.certificate_number.replace(/[^A-Za-z0-9_-]/g, '-')}.pdf`;
    link.click();
    URL.revokeObjectURL(downloadUrl);
  } catch (error) {
    button.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function loadDocumentsAndCertificates() {
  const documentsList = document.querySelector('#documents-list');
  const certificatesList = document.querySelector('#certificates-list');
  try {
    const [documents, certificates] = await Promise.all([
      apiRequest('/admin/documents'),
      apiRequest('/admin/certificates'),
      loadActiveMembersInto(['#certificate-member']),
    ]);
    documentsList.replaceChildren();
    if (!documents.length) showEmpty(documentsList, 'No staff documents have been stored.');
    documents.forEach((documentRecord) => {
      const row = addAdminRow(
        documentsList,
        documentRecord.title,
        `${documentRecord.document_type} · ${documentRecord.filename} · ${new Intl.NumberFormat('en-UG').format(documentRecord.size_bytes)} bytes`,
      );
      const download = document.createElement('button');
      download.type = 'button';
      download.textContent = 'Download';
      download.addEventListener('click', () => downloadStaffDocument(documentRecord, download));
      row.append(download);
    });
    certificatesList.replaceChildren();
    if (!certificates.length) showEmpty(certificatesList, 'No certificates have been issued.');
    certificates.forEach((certificate) => {
      const row = addAdminRow(
        certificatesList,
        `${certificate.member_name} · ${certificate.certificate_type}`,
        `${certificate.certificate_number} · Issued ${certificate.issued_on}${certificate.details ? ` · ${certificate.details}` : ''}`,
      );
      const download = document.createElement('button');
      download.type = 'button';
      download.textContent = 'Download PDF';
      download.addEventListener('click', () => downloadMemberCertificate(certificate, download));
      row.append(download);
    });
  } catch (error) {
    showEmpty(documentsList, error.message);
    showEmpty(certificatesList, error.message);
  }
}

async function loadGovernanceResolutions(meetingId) {
  const list = document.querySelector('#governance-resolutions-list');
  if (!meetingId) return showEmpty(list, 'Choose a meeting to view its resolutions.');
  try {
    const resolutions = await apiRequest(`/admin/governance/meetings/${meetingId}/resolutions`);
    list.replaceChildren();
    if (!resolutions.length) return showEmpty(list, 'No resolutions have been recorded for this meeting.');
    const nextStatuses = {
      proposed: ['approved', 'rejected'],
      approved: ['in_progress', 'completed'],
      in_progress: ['completed'],
    };
    resolutions.forEach((resolution) => {
      const row = addAdminRow(
        list,
        `${resolution.title} · ${resolution.status.replaceAll('_', ' ')}`,
        `${resolution.description}${resolution.due_date ? ` · Due ${resolution.due_date}` : ''}`,
      );
      const transitions = nextStatuses[resolution.status] || [];
      if (!transitions.length) return;
      const status = document.createElement('select');
      status.setAttribute('aria-label', `Next status for ${resolution.title}`);
      transitions.forEach((value) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value.replaceAll('_', ' ');
        status.append(option);
      });
      const save = document.createElement('button');
      save.type = 'button';
      save.textContent = 'Update status';
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          await apiRequest(`/admin/governance/resolutions/${resolution.id}/status`, {
            method: 'PATCH',
            body: JSON.stringify({ status: status.value }),
          });
          await loadGovernanceResolutions(meetingId);
        } catch (error) {
          save.textContent = error.message;
          save.disabled = false;
        }
      });
      row.append(status, save);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadGovernance() {
  const meetingsList = document.querySelector('#governance-meetings-list');
  const meetingSelect = document.querySelector('#governance-resolution-meeting');
  try {
    const meetings = await apiRequest('/admin/governance/meetings');
    const selectedMeetingId = meetingSelect.value;
    meetingsList.replaceChildren();
    meetingSelect.replaceChildren(new Option(meetings.length ? 'Choose a meeting' : 'Create a meeting first', ''));
    meetings.forEach((meeting) => {
      const option = new Option(`${meeting.meeting_date} · ${meeting.title}`, meeting.id);
      meetingSelect.append(option);
      const row = addAdminRow(
        meetingsList,
        `${meeting.title} · ${meeting.status}`,
        `${meeting.meeting_date} · ${branchName(meeting.branch_id)}${meeting.location ? ` · ${meeting.location}` : ''}${meeting.minutes ? ` · ${meeting.minutes}` : ''}`,
      );
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.textContent = 'Edit';
      edit.addEventListener('click', () => {
        const form = document.querySelector('#governance-meeting-form');
        form.elements.id.value = meeting.id;
        form.elements.title.value = meeting.title;
        form.elements.meeting_date.value = meeting.meeting_date;
        form.elements.location.value = meeting.location || '';
        setBranchSelectValue(form.elements.branch_id, meeting.branch_id);
        form.elements.status.value = meeting.status;
        form.elements.minutes.value = meeting.minutes || '';
        form.querySelector('h3').textContent = 'Edit meeting';
        form.querySelector('button[type="submit"]').textContent = 'Update meeting';
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      row.append(edit);
      const view = document.createElement('button');
      view.type = 'button';
      view.textContent = 'View resolutions';
      view.addEventListener('click', async () => {
        meetingSelect.value = String(meeting.id);
        await loadGovernanceResolutions(meeting.id);
      });
      row.append(view);
    });
    meetingSelect.value = meetings.some((meeting) => String(meeting.id) === selectedMeetingId)
      ? selectedMeetingId
      : '';
    await loadGovernanceResolutions(meetingSelect.value);
  } catch (error) {
    showEmpty(meetingsList, error.message);
    showEmpty(document.querySelector('#governance-resolutions-list'), error.message);
  }
}

async function loadAnalytics() {
  const form = document.querySelector('#analytics-filter-form');
  const output = document.querySelector('#analytics-overview');
  if (!form.elements.period_start.value || !form.elements.period_end.value) {
    const end = new Date();
    const start = new Date(end);
    start.setDate(start.getDate() - 29);
    form.elements.period_start.value = localDateValue(start);
    form.elements.period_end.value = localDateValue(end);
  }
  const params = new URLSearchParams({
    period_start: form.elements.period_start.value,
    period_end: form.elements.period_end.value,
  });
  if (form.elements.branch_id.value) params.set('branch_id', form.elements.branch_id.value);
  try {
    const overview = await apiRequest(`/admin/analytics/overview?${params}`);
    output.replaceChildren();
    [
      ['Active members', overview.active_members],
      ['Attendance check-ins', overview.attendance_check_ins],
      ['Distinct attendees', overview.distinct_attendees],
      ['Service days recorded', overview.service_days_recorded],
      ['Visitor requests in period', overview.visitor_requests],
      ['New visitor follow-ups', overview.new_visitor_follow_ups],
      ['Published events in period', overview.published_events],
      ['Registrations for published events', overview.event_registrations],
      ['Published small groups', overview.published_small_groups],
      ['Open governance actions', overview.open_governance_actions],
    ].forEach(([label, value]) => addAdminRow(output, label, String(value)));
    setFormStatus(form, `Overview for ${overview.period_start} to ${overview.period_end}.`);
  } catch (error) {
    showEmpty(output, error.message);
    setFormStatus(form, error.message, true);
  }
}

async function loadBranches() {
  const list = document.querySelector('#branches-list');
  try {
    const branches = await apiRequest('/admin/branches?include_inactive=true');
    branchRecords = branches;
    await loadBranchSelectors();
    list.replaceChildren();
    if (!branches.length) return showEmpty(list, 'No branches have been added.');
    branches.forEach((branch) => {
      const row = addAdminRow(
        list,
        branch.name,
        `${branch.location || 'No location provided'} · ${branch.is_active ? 'Active' : 'Inactive'}`,
      );
      const edit = document.createElement('button');
      edit.type = 'button';
      edit.textContent = 'Edit';
      edit.addEventListener('click', () => {
        const form = document.querySelector('#branch-form');
        form.elements.name.value = branch.name;
        form.elements.location.value = branch.location;
        form.elements.is_active.checked = branch.is_active;
        form.dataset.branchId = branch.id;
        form.querySelector('button[type="submit"]').textContent = 'Update branch';
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      row.append(edit);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadInstitutionsMissions() {
  const list = document.querySelector('#institutions-list');
  try {
    const records = await apiRequest('/admin/institutions-missions?include_inactive=true');
    list.replaceChildren();
    if (!records.length) return showEmpty(list, 'No institution or mission records have been added.');
    records.forEach((record) => {
      const row = addAdminRow(
        list,
        `${record.name} · ${record.record_type.replaceAll('_', ' ')}`,
        `${record.location || 'No location provided'} · ${branchName(record.branch_id)} · ${record.is_active ? 'Active' : 'Inactive'}${record.description ? ` · ${record.description}` : ''}`,
        'Edit',
        () => {
          const form = document.querySelector('#institutions-form');
          form.elements.id.value = record.id;
          form.elements.record_type.value = record.record_type;
          form.elements.name.value = record.name;
          form.elements.location.value = record.location;
          form.elements.description.value = record.description;
          setBranchSelectValue(form.elements.branch_id, record.branch_id);
          form.elements.is_active.checked = record.is_active;
          form.querySelector('button[type="submit"]').textContent = 'Update record';
          form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        },
      );
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.textContent = record.is_active ? 'Deactivate' : 'Reactivate';
      toggle.addEventListener('click', async () => {
        try {
          await apiRequest(`/admin/institutions-missions/${record.id}`, {
            method: 'PUT',
            body: JSON.stringify({
              record_type: record.record_type,
              name: record.name,
              location: record.location,
              description: record.description,
              is_active: !record.is_active,
              branch_id: record.branch_id,
            }),
          });
          await loadInstitutionsMissions();
        } catch (error) {
          toggle.textContent = error.message;
        }
      });
      row.append(toggle);
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadSafeguardingReports() {
  const list = document.querySelector('#safeguarding-reports-list');
  try {
    const reports = await apiRequest('/admin/safeguarding/reports');
    list.replaceChildren();
    if (!reports.length) return showEmpty(list, 'No safeguarding reports are assigned to your review role.');
    reports.forEach((report) => {
      const row = addAdminRow(
        list,
        `Report #${report.id} · ${report.report_type} · ${report.status.replaceAll('_', ' ')}`,
        `${report.incident_date} ${report.incident_time} · ${report.location} · Retain until ${report.retention_until}${report.serious_child_protection ? ' · Serious child-protection referral' : ''}`,
      );
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'View confidential report details';
      details.append(summary);
      [
        ['People involved', report.people_involved],
        ['Witnesses', report.witness_names],
        ['Factual description', report.factual_description],
        ['Action taken', report.action_taken],
        ['Reporter', `${report.reporter_name} · ${report.reporter_contact}`],
      ].forEach(([label, value]) => {
        if (!value) return;
        const paragraph = document.createElement('p');
        paragraph.textContent = `${label}: ${value}`;
        details.append(paragraph);
      });
      row.append(details);

      let nextStatus = null;
      let actionLabel = null;
      if (report.serious_child_protection && report.status === 'referral_required' && currentStaffRole === 'safeguarding_lead') {
        nextStatus = 'referred_to_authorities';
        actionLabel = 'Record external referral';
      } else if (['new', 'investigating'].includes(report.status)
        && ['safeguarding_lead', 'board_chair', 'trustee'].includes(currentStaffRole)) {
        nextStatus = report.status === 'new' ? 'investigating' : 'pending_resolution';
        actionLabel = report.status === 'new' ? 'Start investigation' : 'Request resolution';
      } else if (report.status === 'pending_resolution'
        && ['senior_pastor', 'board_chair', 'trustee'].includes(currentStaffRole)) {
        nextStatus = 'approve_resolution';
        actionLabel = 'Approve resolution';
      }

      if (actionLabel) {
        const action = document.createElement('button');
        action.type = 'button';
        action.textContent = actionLabel;
        action.addEventListener('click', async () => {
          if (nextStatus === 'referred_to_authorities'
            && !window.confirm('Confirm the external authority referral has already been made.')) return;
          action.disabled = true;
          try {
            await apiRequest(`/admin/safeguarding/reports/${report.id}/status`, {
              method: 'PATCH',
              body: JSON.stringify({ status: nextStatus }),
            });
            await loadSafeguardingReports();
          } catch (error) {
            action.textContent = error.message;
            action.disabled = false;
          }
        });
        row.append(action);
      }
      if (report.status === 'pending_resolution'
        && ['senior_pastor', 'board_chair', 'trustee'].includes(currentStaffRole)) {
        const reject = document.createElement('button');
        reject.type = 'button';
        reject.textContent = 'Reject closure';
        reject.addEventListener('click', async () => {
          try {
            await apiRequest(`/admin/safeguarding/reports/${report.id}/status`, {
              method: 'PATCH',
              body: JSON.stringify({ status: 'reject_resolution' }),
            });
            await loadSafeguardingReports();
          } catch (error) {
            reject.textContent = error.message;
          }
        });
        row.append(reject);
      }
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

async function loadVolunteerVetting() {
  const list = document.querySelector('#volunteer-vetting-list');
  const form = document.querySelector('#volunteer-vetting-form');
  const canCreate = ['admin', 'hr_admin', 'safeguarding_lead'].includes(currentStaffRole);
  form.hidden = !canCreate;
  try {
    if (canCreate) {
      const members = await apiRequest('/admin/safeguarding/vetting/members');
      fillMemberSelect(document.querySelector('#vetting-member'), members, 'Choose a volunteer');
    }
    const records = await apiRequest('/admin/safeguarding/vetting');
    list.replaceChildren();
    if (!records.length) return showEmpty(list, 'No volunteer vetting records are available.');
    records.forEach((record) => {
      const row = addAdminRow(
        list,
        `${record.member_name} · ${record.status}`,
        `Background check: ${record.background_check_status} · References: ${record.references_checked ? 'checked' : 'not checked'} · Training: ${record.training_completed_at || 'not completed'} · Retain until ${record.retention_until || 'service end + 7 years'}`,
      );
      const details = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = 'View restricted vetting details';
      [
        ['Government ID', record.government_id],
        ['References', record.reference_names],
        ['Reference contacts', record.reference_contacts],
        ['Background-check consent', record.background_check_consent ? 'Recorded' : 'Not recorded'],
      ].forEach(([label, value]) => {
        const paragraph = document.createElement('p');
        paragraph.textContent = `${label}: ${value}`;
        details.append(paragraph);
      });
      details.prepend(summary);
      row.append(details);

      if (currentStaffRole !== 'safeguarding_lead') return;
      if (record.status === 'pending') {
        const controls = document.createElement('div');
        controls.className = 'prayer-followup';
        const backgroundStatus = document.createElement('select');
        backgroundStatus.setAttribute('aria-label', `Background check status for ${record.member_name}`);
        [['pending', 'Pending'], ['clear', 'Clear'], ['flagged', 'Flagged']].forEach(([value, label]) => {
          backgroundStatus.add(new Option(label, value));
        });
        backgroundStatus.value = record.background_check_status;
        const referencesChecked = document.createElement('input');
        referencesChecked.type = 'checkbox';
        referencesChecked.checked = record.references_checked;
        referencesChecked.setAttribute('aria-label', `References checked for ${record.member_name}`);
        const trainingDate = document.createElement('input');
        trainingDate.type = 'date';
        trainingDate.value = record.training_completed_at || '';
        trainingDate.setAttribute('aria-label', `Training completion date for ${record.member_name}`);
        const saveReview = document.createElement('button');
        saveReview.type = 'button';
        saveReview.textContent = 'Save checks';
        saveReview.addEventListener('click', async () => {
          try {
            await apiRequest(`/admin/safeguarding/vetting/${record.id}/review`, {
              method: 'PATCH',
              body: JSON.stringify({
                background_check_status: backgroundStatus.value,
                references_checked: referencesChecked.checked,
                training_completed_at: trainingDate.value || null,
              }),
            });
            await loadVolunteerVetting();
          } catch (error) {
            saveReview.textContent = error.message;
          }
        });
        controls.append(backgroundStatus, referencesChecked, trainingDate, saveReview);
        row.append(controls);

        [['approved', 'Approve'], ['rejected', 'Reject']].forEach(([status, label]) => {
          const action = document.createElement('button');
          action.type = 'button';
          action.textContent = label;
          action.addEventListener('click', async () => {
            try {
              await apiRequest(`/admin/safeguarding/vetting/${record.id}/status`, {
                method: 'PATCH',
                body: JSON.stringify({ status }),
              });
              await loadVolunteerVetting();
            } catch (error) {
              action.textContent = error.message;
            }
          });
          row.append(action);
        });
      } else if (record.status === 'approved') {
        const endedDate = document.createElement('input');
        endedDate.type = 'date';
        endedDate.setAttribute('aria-label', `Service end date for ${record.member_name}`);
        const endService = document.createElement('button');
        endService.type = 'button';
        endService.textContent = 'End service';
        endService.addEventListener('click', async () => {
          try {
            await apiRequest(`/admin/safeguarding/vetting/${record.id}/status`, {
              method: 'PATCH',
              body: JSON.stringify({ status: 'service_ended', service_ended_at: endedDate.value }),
            });
            await loadVolunteerVetting();
          } catch (error) {
            endService.textContent = error.message;
          }
        });
        row.append(endedDate, endService);
      }
    });
  } catch (error) {
    showEmpty(list, error.message);
  }
}

const loaders = { members: loadMembers, attendance: loadAttendancePanel, rota: loadRotaPanel, groups: loadGroups, children: loadChildPanel, safeguarding: loadSafeguardingReports, vetting: loadVolunteerVetting, alerts: loadAlerts, pages: loadPages, sermons: loadSermons, events: loadEvents, contact: loadContactInquiries, visitors: loadVisitorVisits, prayer: loadPrayerRequests, finance: loadFinance, 'care-tasks': loadPastoralCareTasks, resources: loadResourceBookings, documents: loadDocumentsAndCertificates, governance: loadGovernance, analytics: loadAnalytics, branches: loadBranches, institutions: loadInstitutionsMissions, audit: loadAudit };

async function activateTab(name) {
  document.querySelectorAll('[data-tab]').forEach((button) => {
    const isSelected = button.dataset.tab === name;
    button.setAttribute('aria-selected', String(isSelected));
    button.tabIndex = isSelected ? 0 : -1;
  });
  document.querySelectorAll('[data-panel]').forEach((panel) => {
    panel.hidden = panel.dataset.panel !== name;
  });
  if (['members', 'attendance', 'events', 'finance', 'governance', 'analytics', 'groups', 'resources', 'institutions'].includes(name)) {
    await loadBranchSelectors();
  }
  loaders[name]?.();
}

function showConsole(user) {
  currentStaffRole = user.role;
  currentStaffId = user.id;
  loginPanel.hidden = true;
  consolePanel.hidden = false;
  document.querySelector('#staff-identity').textContent = `${user.display_name} · ${user.role}`;
  const capabilities = {
    members: ['admin', 'pastor'].includes(user.role),
    attendance: ['admin', 'editor', 'pastor'].includes(user.role),
    rota: ['admin', 'editor', 'pastor'].includes(user.role),
    groups: ['admin', 'editor', 'pastor'].includes(user.role),
    children: ['admin', 'pastor'].includes(user.role),
    safeguarding: ['safeguarding_lead', 'senior_pastor', 'board_chair', 'trustee'].includes(user.role),
    vetting: ['admin', 'hr_admin', 'safeguarding_lead', 'senior_pastor'].includes(user.role),
    alerts: ['admin', 'editor', 'pastor'].includes(user.role),
    pages: ['admin', 'editor'].includes(user.role),
    sermons: ['admin', 'editor'].includes(user.role),
    events: ['admin', 'editor'].includes(user.role),
    contact: ['admin', 'pastor'].includes(user.role),
    visitors: ['admin', 'pastor'].includes(user.role),
    prayer: ['admin', 'pastor'].includes(user.role),
    finance: ['admin', 'treasurer'].includes(user.role),
    'care-tasks': ['admin', 'pastor'].includes(user.role),
    resources: ['admin', 'editor', 'pastor'].includes(user.role),
    documents: ['admin', 'pastor'].includes(user.role),
    governance: ['admin', 'pastor'].includes(user.role),
    analytics: ['admin', 'pastor'].includes(user.role),
    branches: user.role === 'admin',
    institutions: ['admin', 'pastor'].includes(user.role),
    audit: user.role === 'admin',
  };
  document.querySelectorAll('[data-tab]').forEach((button) => {
    button.hidden = !capabilities[button.dataset.tab];
    button.setAttribute('aria-controls', `panel-${button.dataset.tab}`);
  });
  const firstTab = Object.keys(capabilities).find((name) => capabilities[name]);
  if (firstTab) activateTab(firstTab);
  else consolePanel.querySelector('.console-tabs').insertAdjacentText('afterend', 'No console tools are enabled for this account yet.');
}

document.querySelectorAll('[data-tab]').forEach((button) => {
  button.addEventListener('click', () => activateTab(button.dataset.tab));
});

document.querySelector('#group-branch-filter').addEventListener('change', loadGroups);
document.querySelector('#resource-branch-filter').addEventListener('change', loadResourceBookings);

const volunteerVettingForm = document.querySelector('#volunteer-vetting-form');
volunteerVettingForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const values = new FormData(volunteerVettingForm);
  const button = volunteerVettingForm.querySelector('button[type="submit"]');
  button.disabled = true;
  try {
    await apiRequest('/admin/safeguarding/vetting', {
      method: 'POST',
      body: JSON.stringify({
        member_id: Number(values.get('member_id')),
        government_id: values.get('government_id'),
        reference_names: values.get('reference_names'),
        reference_contacts: values.get('reference_contacts'),
        background_check_consent: values.get('background_check_consent') === 'on',
        service_started_at: values.get('service_started_at') || null,
      }),
    });
    volunteerVettingForm.reset();
    setFormStatus(volunteerVettingForm, 'Pending vetting record saved.');
    await loadVolunteerVetting();
  } catch (error) {
    setFormStatus(volunteerVettingForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = loginForm.querySelector('button[type="submit"]');
  submit.disabled = true;
  loginStatus.textContent = '';
  try {
    const values = new FormData(loginForm);
    const result = await apiRequest('/auth/token', {
      method: 'POST',
      body: JSON.stringify({ email: values.get('email'), password: values.get('password') }),
    });
    sessionStorage.setItem('bwala_staff_token', result.access_token);
    const user = await apiRequest('/auth/me');
    showConsole(user);
  } catch (error) {
    loginStatus.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

document.querySelector('#sign-out').addEventListener('click', () => showLogin('You have signed out.'));

const memberForm = document.querySelector('#member-form');
memberForm.addEventListener('reset', () => {
  memberForm.querySelector('.form-status').textContent = '';
  memberForm.elements.consent_confirmed.required = true;
  memberForm.querySelector('.member-consent').hidden = false;
});
memberForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = memberForm.querySelector('button[type="submit"]');
  const values = new FormData(memberForm);
  const memberId = values.get('id');
  const payload = {
    name: values.get('name'),
    email: values.get('email') || null,
    phone: values.get('phone') || null,
    branch_id: optionalBranchId(values),
  };
  if (!memberId) payload.consent_confirmed = values.get('consent_confirmed') === 'on';
  button.disabled = true;
  try {
    const savedMember = await apiRequest(memberId ? `/admin/members/${memberId}` : '/admin/members', {
      method: memberId ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
    });
    try {
      await apiRequest(`/admin/members/${savedMember.id}/communication-consents`, {
        method: 'PUT',
        body: JSON.stringify({
          preferences: ['email', 'sms', 'whatsapp'].map((channel) => ({
            channel,
            is_consented: document.querySelector(`#member-${channel}-consent`).checked,
            consent_source: document.querySelector(`#member-${channel}-consent-source`).value,
            delivery_frequency: document.querySelector('#member-communication-frequency').value,
            quiet_hours_start: document.querySelector('#member-quiet-hours-start').value || '21:00',
            quiet_hours_end: document.querySelector('#member-quiet-hours-end').value || '07:00',
            timezone: 'Africa/Kampala',
          })),
        }),
      });
    } catch (error) {
      memberForm.reset();
      setFormStatus(memberForm, `Profile saved, but communication consent was not saved: ${error.message}`, true);
      await loadMembers();
      return;
    }
    memberForm.reset();
    setFormStatus(memberForm, 'Member record saved.');
    await loadMembers();
  } catch (error) {
    setFormStatus(memberForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

document.querySelector('#member-status-filter').addEventListener('change', loadMembers);

function localDateValue(date = new Date()) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

const attendanceForm = document.querySelector('#attendance-form');
const attendanceDate = document.querySelector('#attendance-date');
const attendanceListDate = document.querySelector('#attendance-list-date');
attendanceDate.value = localDateValue();
attendanceListDate.value = attendanceDate.value;
attendanceListDate.addEventListener('change', loadAttendance);
attendanceForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = attendanceForm.querySelector('button[type="submit"]');
  const values = new FormData(attendanceForm);
  button.disabled = true;
  try {
    await apiRequest('/admin/attendance', {
      method: 'POST',
      body: JSON.stringify({
        member_id: Number(values.get('member_id')),
        service_name: values.get('service_name'),
        service_date: values.get('service_date'),
        check_in_method: values.get('check_in_method'),
        branch_id: optionalBranchId(values),
      }),
    });
    setFormStatus(attendanceForm, 'Member checked in.');
    attendanceListDate.value = values.get('service_date');
    await loadAttendance();
  } catch (error) {
    setFormStatus(attendanceForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

const availabilityForm = document.querySelector('#availability-form');
const rotaServiceName = document.querySelector('#rota-service-name');
const rotaServiceDate = document.querySelector('#rota-service-date');
rotaServiceDate.addEventListener('change', () => Promise.all([loadVolunteerAvailability(), loadRota()]));
rotaServiceName.addEventListener('change', () => Promise.all([loadVolunteerAvailability(), loadRota()]));
availabilityForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = availabilityForm.querySelector('button[type="submit"]');
  const scope = rotaScope();
  if (!scope.serviceName || !scope.serviceDate) {
    setFormStatus(availabilityForm, 'Enter the service name and date first.', true);
    return;
  }
  button.disabled = true;
  try {
    await apiRequest('/admin/volunteer-availability', {
      method: 'POST',
      body: JSON.stringify({
        member_id: Number(document.querySelector('#availability-member').value),
        service_name: scope.serviceName,
        service_date: scope.serviceDate,
        is_available: document.querySelector('#availability-value').checked,
      }),
    });
    setFormStatus(availabilityForm, 'Availability saved.');
    await loadVolunteerAvailability();
  } catch (error) {
    setFormStatus(availabilityForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

const availabilityInviteButton = document.querySelector('#create-availability-invite');
const availabilityInviteLink = document.querySelector('#availability-invite-link');
availabilityInviteButton.addEventListener('click', async () => {
  const scope = rotaScope();
  const memberId = Number(document.querySelector('#availability-member').value);
  if (!scope.serviceName || !scope.serviceDate || !memberId) {
    setFormStatus(availabilityForm, 'Choose a volunteer, service name, and date first.', true);
    return;
  }
  availabilityInviteButton.disabled = true;
  try {
    const invite = await apiRequest('/admin/volunteer-availability/invites', {
      method: 'POST',
      body: JSON.stringify({
        member_id: memberId,
        service_name: scope.serviceName,
        service_date: scope.serviceDate,
      }),
    });
    const link = new URL('index.html', window.location.href);
    link.hash = new URLSearchParams({ availability: invite.token }).toString();
    availabilityInviteLink.value = link.href;
    availabilityInviteLink.hidden = false;
    availabilityInviteLink.focus();
    availabilityInviteLink.select();
    setFormStatus(availabilityForm, 'One-use link created. Copy it and share privately; it expires in seven days.');
  } catch (error) {
    setFormStatus(availabilityForm, error.message, true);
  } finally {
    availabilityInviteButton.disabled = false;
  }
});

const rotaGenerateForm = document.querySelector('#rota-generate-form');
rotaGenerateForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = rotaGenerateForm.querySelector('button[type="submit"]');
  const roles = document.querySelector('#rota-role-names').value.split(',').map((role) => role.trim()).filter(Boolean);
  const scope = rotaScope();
  if (!scope.serviceName || !scope.serviceDate) {
    setFormStatus(rotaGenerateForm, 'Enter the service name and date first.', true);
    return;
  }
  button.disabled = true;
  try {
    await apiRequest('/admin/rota/generate', {
      method: 'POST',
      body: JSON.stringify({ service_name: scope.serviceName, service_date: scope.serviceDate, role_names: roles }),
    });
    setFormStatus(rotaGenerateForm, 'Rota generated.');
    await loadRota();
  } catch (error) {
    setFormStatus(rotaGenerateForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

const childForm = document.querySelector('#child-form');
childForm.addEventListener('reset', () => {
  childForm.querySelector('.form-status').textContent = '';
});
childForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = childForm.querySelector('button[type="submit"]');
  const values = new FormData(childForm);
  const childId = values.get('id');
  const payload = {
    name: values.get('name'),
    primary_guardian_id: Number(values.get('primary_guardian_id')),
    authorized_pickup_member_ids: values.getAll('authorized_pickup_member_ids').map(Number),
    consent_confirmed: values.get('consent_confirmed') === 'on',
  };
  button.disabled = true;
  try {
    await apiRequest(childId ? `/admin/children/${childId}` : '/admin/children', {
      method: childId ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
    });
    childForm.reset();
    setFormStatus(childForm, 'Child profile saved.');
    await loadChildPanel();
  } catch (error) {
    setFormStatus(childForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

const childCheckinForm = document.querySelector('#child-checkin-form');
const childAttendanceDate = document.querySelector('#child-attendance-date');
const childAttendanceListDate = document.querySelector('#child-attendance-list-date');
childAttendanceDate.value = localDateValue();
childAttendanceListDate.value = childAttendanceDate.value;
document.querySelector('#child-attendance-child').addEventListener('change', updateChildAttendanceAdultOptions);
childAttendanceListDate.addEventListener('change', loadChildAttendance);
childCheckinForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = childCheckinForm.querySelector('button[type="submit"]');
  const values = new FormData(childCheckinForm);
  button.disabled = true;
  try {
    await apiRequest('/admin/child-attendance', {
      method: 'POST',
      body: JSON.stringify({
        child_id: Number(values.get('child_id')),
        checked_in_by_member_id: Number(values.get('checked_in_by_member_id')),
        service_name: values.get('service_name'),
        service_date: values.get('service_date'),
      }),
    });
    setFormStatus(childCheckinForm, 'Child checked in. Verify identity in person at pickup.');
    childAttendanceListDate.value = values.get('service_date');
    await loadChildAttendance();
  } catch (error) {
    setFormStatus(childCheckinForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

function connectContentForm(formId, endpoint, makePayload, refresh) {
  const form = document.querySelector(formId);
  form.addEventListener('reset', () => {
    form.querySelector('.form-status').textContent = '';
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    const recordId = form.elements.id.value;
    const method = recordId ? 'PUT' : 'POST';
    const path = recordId ? `${endpoint}/${recordId}` : endpoint;
    button.disabled = true;
    try {
      const payload = makePayload(new FormData(form));
      await apiRequest(path, { method, body: JSON.stringify(payload) });
      form.reset();
      setFormStatus(form, 'Saved.');
      await refresh();
    } catch (error) {
      setFormStatus(form, error.message, true);
    } finally {
      button.disabled = false;
    }
  });
}

connectContentForm('#page-form', '/admin/pages', (values) => ({
  slug: values.get('slug'), title: values.get('title'), body: values.get('body'), is_published: values.get('is_published') === 'on',
}), loadPages);

connectContentForm('#sermon-form', '/admin/sermons', (values) => ({
  title: values.get('title'), speaker: values.get('speaker'), scripture: values.get('scripture') || null,
  summary: values.get('summary') || '', media_url: values.get('media_url') || null,
  published_at: new Date(values.get('published_at')).toISOString(), is_published: values.get('is_published') === 'on',
}), loadSermons);

connectContentForm('#event-form', '/admin/events', (values) => ({
  title: values.get('title'), description: values.get('description') || '', location: values.get('location'),
  branch_id: optionalBranchId(values),
  starts_at: new Date(values.get('starts_at')).toISOString(), capacity: values.get('capacity') ? Number(values.get('capacity')) : null,
  registration_open: values.get('registration_open') === 'on', is_published: values.get('is_published') === 'on',
}), loadEvents);

connectContentForm('#alert-form', '/admin/alerts', (values) => ({
  title: values.get('title'),
  message: values.get('message'),
  expires_at: values.get('expires_at') ? new Date(values.get('expires_at')).toISOString() : null,
  is_active: values.get('is_active') === 'on',
}), loadAlerts);

connectContentForm('#group-form', '/admin/groups', (values) => ({
  name: values.get('name'),
  branch_id: optionalBranchId(values),
  description: values.get('description') || '',
  meeting_area: values.get('meeting_area'),
  meeting_day: values.get('meeting_day'),
  meeting_time: values.get('meeting_time'),
  age_group: values.get('age_group'),
  latitude: values.get('latitude') === '' ? null : Number(values.get('latitude')),
  longitude: values.get('longitude') === '' ? null : Number(values.get('longitude')),
  is_open: values.get('is_open') === 'on',
  is_published: values.get('is_published') === 'on',
}), loadGroups);

function connectPhase3JsonForm(formId, endpoint, makePayload, refresh) {
  const form = document.querySelector(formId);
  const submit = form.querySelector('button[type="submit"]');
  const defaultSubmitText = submit.textContent;
  form.addEventListener('reset', () => {
    form.querySelector('.form-status').textContent = '';
    submit.textContent = defaultSubmitText;
    const heading = form.querySelector('h3');
    if (form.id === 'resource-form') heading.textContent = 'Add resource';
    if (form.id === 'governance-meeting-form') heading.textContent = 'Record a meeting';
  });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const values = new FormData(form);
    const recordId = values.get('id');
    const method = recordId ? 'PUT' : 'POST';
    const path = recordId ? `${endpoint}/${recordId}` : endpoint;
    submit.disabled = true;
    try {
      await apiRequest(path, { method, body: JSON.stringify(makePayload(values)) });
      form.reset();
      setFormStatus(form, 'Saved.');
      await refresh();
    } catch (error) {
      setFormStatus(form, error.message, true);
    } finally {
      submit.disabled = false;
    }
  });
}

const today = localDateValue();
['#finance-entry-form [name="entry_date"]', '#finance-budget-form [name="period_start"]', '#finance-budget-form [name="period_end"]',
  '#finance-report-form [name="period_start"]', '#finance-report-form [name="period_end"]', '#certificate-form [name="issued_on"]',
  '#offering-count-form [name="service_date"]', '#governance-meeting-form [name="meeting_date"]']
  .forEach((selector) => { document.querySelector(selector).value = today; });

connectPhase3JsonForm('#finance-entry-form', '/admin/finance/entries', (values) => ({
  entry_type: values.get('entry_type'),
  amount_ugx: Number(values.get('amount_ugx')),
  fund: values.get('fund'),
  category: values.get('category'),
  entry_date: values.get('entry_date'),
  payment_method: values.get('payment_method'),
  details: values.get('details') || '',
  branch_id: optionalBranchId(values),
}), loadFinance);

connectPhase3JsonForm('#finance-budget-form', '/admin/finance/budgets', (values) => ({
  fund: values.get('fund'),
  category: values.get('category'),
  amount_ugx: Number(values.get('amount_ugx')),
  period_start: values.get('period_start'),
  period_end: values.get('period_end'),
  branch_id: optionalBranchId(values),
}), loadFinance);

connectPhase3JsonForm('#finance-pledge-form', '/admin/finance/pledges', (values) => ({
  campaign: values.get('campaign'),
  amount_ugx: Number(values.get('amount_ugx')),
  due_date: values.get('due_date') || null,
  donor_name: values.get('donor_name'),
  donor_contact: values.get('donor_contact') || null,
  details: values.get('details') || '',
  branch_id: optionalBranchId(values),
}), loadFinance);

connectPhase3JsonForm('#offering-count-form', '/admin/finance/offering-counts', (values) => ({
  service_name: values.get('service_name'),
  service_date: values.get('service_date'),
  fund: values.get('fund'),
  category: values.get('category'),
  amount_ugx: Number(values.get('amount_ugx')),
  notes: values.get('notes') || '',
  branch_id: optionalBranchId(values),
}), loadFinance);

connectPhase3JsonForm('#governance-meeting-form', '/admin/governance/meetings', (values) => ({
  title: values.get('title'),
  meeting_date: values.get('meeting_date'),
  location: values.get('location') || '',
  status: values.get('status'),
  minutes: values.get('minutes') || '',
  branch_id: optionalBranchId(values),
}), loadGovernance);

const governanceResolutionForm = document.querySelector('#governance-resolution-form');
governanceResolutionForm.addEventListener('reset', () => {
  governanceResolutionForm.querySelector('.form-status').textContent = '';
});
governanceResolutionForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = governanceResolutionForm.querySelector('button[type="submit"]');
  const values = new FormData(governanceResolutionForm);
  const meetingId = values.get('meeting_id');
  if (!meetingId) {
    setFormStatus(governanceResolutionForm, 'Choose a meeting first.', true);
    return;
  }
  button.disabled = true;
  try {
    await apiRequest(`/admin/governance/meetings/${meetingId}/resolutions`, {
      method: 'POST',
      body: JSON.stringify({
        title: values.get('title'),
        description: values.get('description'),
        due_date: values.get('due_date') || null,
      }),
    });
    governanceResolutionForm.reset();
    document.querySelector('#governance-resolution-meeting').value = meetingId;
    setFormStatus(governanceResolutionForm, 'Resolution saved as proposed.');
    await loadGovernanceResolutions(meetingId);
  } catch (error) {
    setFormStatus(governanceResolutionForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});
document.querySelector('#governance-resolution-meeting').addEventListener('change', (event) => {
  loadGovernanceResolutions(event.currentTarget.value);
});

document.querySelector('#analytics-filter-form').addEventListener('submit', (event) => {
  event.preventDefault();
  loadAnalytics();
});

const branchForm = document.querySelector('#branch-form');
branchForm.addEventListener('reset', () => {
  branchForm.querySelector('.form-status').textContent = '';
  delete branchForm.dataset.branchId;
  branchForm.querySelector('button[type="submit"]').textContent = 'Save branch';
});
branchForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = branchForm.querySelector('button[type="submit"]');
  const values = new FormData(branchForm);
  const branchId = branchForm.dataset.branchId;
  button.disabled = true;
  try {
    await apiRequest(branchId ? `/admin/branches/${branchId}` : '/admin/branches', {
      method: branchId ? 'PUT' : 'POST',
      body: JSON.stringify({
        name: values.get('name'),
        location: values.get('location') || '',
        is_active: values.get('is_active') === 'on',
      }),
    });
    branchForm.reset();
    setFormStatus(branchForm, branchId ? 'Branch updated.' : 'Branch added.');
    await loadBranches();
  } catch (error) {
    setFormStatus(branchForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

const financeReportForm = document.querySelector('#finance-report-form');
financeReportForm.addEventListener('reset', () => {
  financeReportForm.querySelector('.form-status').textContent = '';
  document.querySelector('#finance-report-output').replaceChildren();
});
financeReportForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = financeReportForm.querySelector('button[type="submit"]');
  const values = new FormData(financeReportForm);
  const output = document.querySelector('#finance-report-output');
  button.disabled = true;
  try {
    const report = await apiRequest(`/admin/finance/report?${new URLSearchParams({
      period_start: values.get('period_start'),
      period_end: values.get('period_end'),
      ...(values.get('branch_id') ? { branch_id: values.get('branch_id') } : {}),
    })}`);
    output.replaceChildren();
    addAdminRow(output, `Report · ${report.period_start} to ${report.period_end}`, [
      `Income ${formatUgx(report.income_ugx)}`,
      `Approved expenses ${formatUgx(report.approved_expenses_ugx)}`,
      `Pending expenses ${formatUgx(report.pending_expenses_ugx)}`,
      `Pending corrections ${formatUgx(report.pending_corrections_ugx)}`,
      `Budget ${formatUgx(report.budgeted_ugx)}`,
      `Pledges due ${formatUgx(report.pledge_total_ugx)}`,
    ].join(' · '));
    setFormStatus(financeReportForm, 'Report generated.');
  } catch (error) {
    setFormStatus(financeReportForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

connectPhase3JsonForm('#care-task-form', '/admin/pastoral-care/tasks', (values) => ({
  member_id: Number(values.get('member_id')),
  care_type: values.get('care_type'),
  priority: values.get('priority'),
  due_date: values.get('due_date') || null,
  notes: values.get('notes'),
}), loadPastoralCareTasks);

connectPhase3JsonForm('#resource-form', '/admin/resources', (values) => ({
  name: values.get('name'),
  description: values.get('description') || '',
  is_active: values.get('is_active') === 'on',
  branch_id: optionalBranchId(values),
}), loadResourceBookings);

connectPhase3JsonForm('#institutions-form', '/admin/institutions-missions', (values) => ({
  record_type: values.get('record_type'),
  name: values.get('name'),
  location: values.get('location') || '',
  description: values.get('description') || '',
  is_active: values.get('is_active') === 'on',
  branch_id: optionalBranchId(values),
}), loadInstitutionsMissions);

connectPhase3JsonForm('#resource-booking-form', '/admin/resource-bookings', (values) => ({
  resource_id: Number(values.get('resource_id')),
  starts_at: new Date(values.get('starts_at')).toISOString(),
  ends_at: new Date(values.get('ends_at')).toISOString(),
  purpose: values.get('purpose'),
}), loadResourceBookings);

const documentForm = document.querySelector('#document-form');
documentForm.addEventListener('reset', () => {
  documentForm.querySelector('.form-status').textContent = '';
});
documentForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = documentForm.querySelector('button[type="submit"]');
  const values = new FormData(documentForm);
  const file = values.get('file');
  if (!(file instanceof File) || !file.size) {
    setFormStatus(documentForm, 'Choose a document file.', true);
    return;
  }
  if (file.size > 2 * 1024 * 1024) {
    setFormStatus(documentForm, 'Files must be 2 MB or smaller.', true);
    return;
  }
  button.disabled = true;
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = '';
    for (let offset = 0; offset < bytes.length; offset += 0x8000) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
    }
    await apiRequest('/admin/documents', {
      method: 'POST',
      body: JSON.stringify({
        document_type: values.get('document_type'),
        title: values.get('title'),
        filename: file.name,
        content_type: file.type,
        content_base64: btoa(binary),
      }),
    });
    documentForm.reset();
    setFormStatus(documentForm, 'Document encrypted and stored.');
    await loadDocumentsAndCertificates();
  } catch (error) {
    setFormStatus(documentForm, error.message, true);
  } finally {
    button.disabled = false;
  }
});

connectPhase3JsonForm('#certificate-form', '/admin/certificates', (values) => ({
  member_id: Number(values.get('member_id')),
  certificate_type: values.get('certificate_type'),
  issued_on: values.get('issued_on'),
  certificate_number: values.get('certificate_number'),
  details: values.get('details') || '',
}), loadDocumentsAndCertificates);

const savedToken = sessionStorage.getItem('bwala_staff_token');
if (savedToken) {
  apiRequest('/auth/me').then(showConsole).catch(() => showLogin('Please sign in to continue.'));
}