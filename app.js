const menuToggle = document.querySelector('.menu-toggle');
const siteNav = document.querySelector('.site-nav');
const localHosts = ['localhost', '127.0.0.1', '0.0.0.0'];
const configuredApiBase = document.querySelector('meta[name="api-base-url"]')?.content.trim();
const apiBase = (configuredApiBase || (localHosts.includes(window.location.hostname)
  ? `${window.location.protocol}//${window.location.hostname}:8000`
  : window.location.origin)).replace(/\/+$/, '');
const cmsPageSlug = new URLSearchParams(window.location.search).get('page');
const availabilityToken = new URLSearchParams(window.location.hash.slice(1)).get('availability');
const offlineStatus = document.querySelector('#offline-status');
const publicCacheKeyPrefix = 'bwala_public_cache_v1:';
const cacheablePublicPath = /^\/api\/v1\/(?:alerts\/current|events|sermons|groups|pages(?:\/[a-z0-9-]+)?)$/;

function updateConnectivityStatus() {
  offlineStatus.hidden = navigator.onLine;
}

function cachedPublicValue(cacheKey) {
  try {
    const cached = localStorage.getItem(cacheKey);
    return cached ? JSON.parse(cached).value : null;
  } catch (error) {
    console.warn('Could not read cached public content.', error);
    return null;
  }
}

function storePublicValue(cacheKey, value) {
  try {
    localStorage.setItem(cacheKey, JSON.stringify({ value, savedAt: Date.now() }));
  } catch (error) {
    console.warn('Could not save public content for offline use.', error);
  }
}

async function apiRequest(path, options = {}) {
  const url = new URL(`${apiBase}/api/v1${path}`);
  const method = (options.method || 'GET').toUpperCase();
  const isCacheable = method === 'GET' && cacheablePublicPath.test(url.pathname);
  const cacheKey = `${publicCacheKeyPrefix}${url.pathname}${url.search}`;
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
  } catch (error) {
    if (isCacheable) {
      const cachedValue = cachedPublicValue(cacheKey);
      if (cachedValue !== null) {
        offlineStatus.textContent = 'Connection unavailable. Showing previously cached public information, which may be out of date. Forms need an internet connection.';
        offlineStatus.hidden = false;
        return cachedValue;
      }
    }
    throw error;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((item) => item.msg).join(', ') : data.detail;
    throw new Error(detail || 'The service is temporarily unavailable.');
  }
  if (isCacheable) storePublicValue(cacheKey, data);
  return data;
}

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.dataset.state = isError ? 'error' : 'success';
}

function messageText(container, heading, detail) {
  container.querySelector('strong').textContent = heading;
  container.querySelector('p').textContent = detail;
}

async function loadWelcomeNote() {
  const section = document.querySelector('#church-note');
  try {
    const page = await apiRequest('/pages/welcome-note');
    document.querySelector('#church-note-title').textContent = page.title;
    document.querySelector('#church-note-body').textContent = page.body;
    section.hidden = false;
  } catch {
    section.hidden = true;
  }
}

async function loadEmergencyAlerts() {
  const region = document.querySelector('#emergency-alerts');
  try {
    const alerts = await apiRequest('/alerts/current');
    region.replaceChildren();
    alerts.forEach((alert) => {
      const article = document.createElement('article');
      article.className = 'emergency-alert';
      const title = document.createElement('h2');
      title.textContent = alert.title;
      const message = document.createElement('p');
      message.textContent = alert.message;
      article.append(title, message);
      region.append(article);
    });
    region.hidden = alerts.length === 0;
  } catch {
    region.hidden = true;
  }
}

async function loadCmsPage(slug) {
  const pageView = document.querySelector('#cms-page-view');
  document.querySelectorAll('main > section').forEach((section) => { section.hidden = true; });
  document.querySelectorAll('.site-nav a[href^="#"], .brand[href="#top"], .back-top').forEach((link) => {
    link.href = `index.html${link.getAttribute('href')}`;
  });
  pageView.hidden = false;
  try {
    const page = await apiRequest(`/pages/${encodeURIComponent(slug)}`);
    document.querySelector('#cms-page-title').textContent = page.title;
    document.title = `${page.title} | Bwala Deliverance and Healing Ministries`;
    const paragraphs = page.body.split(/\r?\n\s*\r?\n/).map((text) => text.trim()).filter(Boolean);
    document.querySelector('#cms-page-body').replaceChildren(...paragraphs.map((text) => {
      const paragraph = document.createElement('p');
      paragraph.textContent = text;
      return paragraph;
    }));
  } catch {
    document.querySelector('#cms-page-title').textContent = 'Page unavailable';
    document.querySelector('#cms-page-body').textContent = 'This page could not be found or is not published.';
  }
}

async function loadAvailabilityResponse(token) {
  document.querySelectorAll('main > section').forEach((section) => { section.hidden = true; });
  document.querySelectorAll('.site-nav a[href^="#"], .brand[href="#top"], .back-top').forEach((link) => {
    link.href = `index.html${link.getAttribute('href')}`;
  });
  const section = document.querySelector('#availability-response');
  const form = document.querySelector('#availability-response-form');
  const status = document.querySelector('#availability-response-status');
  section.hidden = false;
  document.title = 'Volunteer availability | Bwala Deliverance and Healing Ministries';
  try {
    const details = await apiRequest('/volunteer-availability/invites/inspect', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
    const date = new Intl.DateTimeFormat('en-UG', {
      dateStyle: 'full',
      timeZone: 'Africa/Kampala',
    }).format(new Date(`${details.service_date}T00:00:00+03:00`));
    document.querySelector('#availability-response-service').textContent = `${details.service_name} · ${date}`;
  } catch (error) {
    form.hidden = true;
    setStatus(status, error.message, true);
  }
}

async function loadPublishedPages() {
  const navigation = document.querySelector('#published-pages');
  try {
    const pages = await apiRequest('/pages');
    const links = pages.map((page) => {
      const link = document.createElement('a');
      link.href = `index.html?page=${encodeURIComponent(page.slug)}`;
      link.textContent = page.title;
      return link;
    });
    navigation.replaceChildren(...links);
    navigation.hidden = links.length === 0;
  } catch {
    navigation.hidden = true;
  }
}

menuToggle.addEventListener('click', () => {
  const isOpen = menuToggle.getAttribute('aria-expanded') === 'true';
  menuToggle.setAttribute('aria-expanded', String(!isOpen));
  menuToggle.setAttribute('aria-label', isOpen ? 'Open navigation' : 'Close navigation');
  siteNav.classList.toggle('is-open', !isOpen);
});

siteNav.querySelectorAll('a').forEach((link) => {
  link.addEventListener('click', () => {
    menuToggle.setAttribute('aria-expanded', 'false');
    menuToggle.setAttribute('aria-label', 'Open navigation');
    siteNav.classList.remove('is-open');
  });
});

document.querySelector('#current-year').textContent = new Date().getFullYear();
updateConnectivityStatus();
window.addEventListener('online', updateConnectivityStatus);
window.addEventListener('offline', updateConnectivityStatus);
if ('serviceWorker' in navigator && window.location.protocol !== 'file:') {
  navigator.serviceWorker.register('/service-worker.js').catch((error) => {
    console.warn('Public offline support could not be registered.', error);
  });
}
loadEmergencyAlerts();
if (availabilityToken) loadAvailabilityResponse(availabilityToken);
else if (cmsPageSlug) loadCmsPage(cmsPageSlug);
else {
  loadWelcomeNote();
  loadPublishedPages();
}

const sermonSearch = document.querySelector('#sermon-search');
const sermonResults = document.querySelector('#sermon-results');
const sermonEmpty = document.querySelector('#message-empty');
const archiveStatus = document.querySelector('#archive-status');
let sermonRequestNumber = 0;
let sermonSearchTimeout;

function renderSermon(sermon) {
  const article = document.createElement('article');
  article.className = 'sermon-result';
  const heading = document.createElement('h3');
  heading.textContent = sermon.title;
  const meta = document.createElement('p');
  meta.className = 'sermon-meta';
  meta.textContent = [sermon.speaker, sermon.scripture, new Intl.DateTimeFormat('en-UG', { dateStyle: 'medium' }).format(new Date(sermon.published_at))].filter(Boolean).join(' · ');
  const summary = document.createElement('p');
  summary.textContent = sermon.summary || '';
  article.append(heading, meta, summary);
  if (sermon.media_url) {
    try {
      const media = new URL(sermon.media_url);
      if (media.protocol === 'https:') {
        const link = document.createElement('a');
        link.className = 'underlined-link';
        link.href = media.href;
        link.target = '_blank';
        link.rel = 'noreferrer';
        link.textContent = 'Listen or watch ↗';
        article.append(link);
      }
    } catch {
      // Ignore invalid media URLs; the sermon text remains available.
    }
  }
  return article;
}

async function loadSermons() {
  const requestNumber = ++sermonRequestNumber;
  const params = new URLSearchParams({ limit: '30' });
  if (sermonSearch.value.trim()) params.set('q', sermonSearch.value.trim());
  archiveStatus.textContent = 'Loading messages...';
  try {
    const sermons = await apiRequest(`/sermons?${params}`);
    if (requestNumber !== sermonRequestNumber) return;
    sermonResults.replaceChildren(...sermons.map(renderSermon));
    sermonEmpty.hidden = sermons.length > 0;
    archiveStatus.textContent = `${sermons.length} ${sermons.length === 1 ? 'message' : 'messages'}`;
    if (!sermons.length) {
      messageText(sermonEmpty, sermonSearch.value.trim() ? 'No messages match that search.' : 'The message archive is on its way.', 'For recent teachings and recordings, call the church office.');
    }
  } catch {
    if (requestNumber !== sermonRequestNumber) return;
    sermonResults.replaceChildren();
    sermonEmpty.hidden = false;
    archiveStatus.textContent = 'Archive unavailable';
    messageText(sermonEmpty, 'The message archive is unavailable right now.', 'Please call the church office for recent teachings and recordings.');
  }
}

sermonSearch.addEventListener('input', () => {
  window.clearTimeout(sermonSearchTimeout);
  sermonSearchTimeout = window.setTimeout(loadSermons, 250);
});
if (!cmsPageSlug && !availabilityToken) loadSermons();

const eventList = document.querySelector('#event-list');

function renderEvent(churchEvent) {
  const item = document.createElement('article');
  item.className = 'event-item';
  const date = new Date(churchEvent.starts_at);
  const dateLabel = document.createElement('div');
  dateLabel.className = 'event-date';
  dateLabel.textContent = new Intl.DateTimeFormat('en-UG', {
    day: '2-digit', month: 'short', hour: 'numeric', minute: '2-digit', timeZone: 'Africa/Kampala',
  }).format(date);
  const details = document.createElement('div');
  details.className = 'event-details';
  const title = document.createElement('h3');
  title.textContent = churchEvent.title;
  const description = document.createElement('p');
  description.textContent = churchEvent.description;
  const location = document.createElement('div');
  location.className = 'event-location';
  location.textContent = churchEvent.location;
  details.append(title, description, location);
  item.append(dateLabel, details);

  if (churchEvent.registration_open) {
    const registration = document.createElement('div');
    registration.className = 'event-rsvp';
    const disclosure = document.createElement('details');
    const summary = document.createElement('summary');
    summary.className = 'card-link';
    summary.textContent = 'Register ↗';
    const form = document.createElement('form');
    form.dataset.eventId = String(churchEvent.id);
    form.innerHTML = '<label>Name<input name="name" maxlength="120" autocomplete="name" required></label><label>Email<input name="email" type="email" maxlength="320" autocomplete="email" required></label><label class="event-consent"><input name="consent" type="checkbox" required><span>I agree to be contacted about this event.</span></label><button class="button button-green" type="submit">Register</button><p class="form-status" aria-live="polite"></p>';
    disclosure.append(summary, form);
    registration.append(disclosure);
    item.append(registration);
  } else {
    const closed = document.createElement('span');
    closed.className = 'event-date';
    closed.textContent = 'Registration closed';
    item.append(closed);
  }
  return item;
}

async function loadEvents() {
  try {
    const events = await apiRequest('/events');
    eventList.replaceChildren();
    if (!events.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-events';
      empty.textContent = 'No upcoming events are listed. Call the church for this week’s schedule.';
      eventList.append(empty);
      return;
    }
    eventList.append(...events.map(renderEvent));
  } catch {
    const empty = document.createElement('p');
    empty.className = 'empty-events';
    empty.textContent = 'Event details are unavailable right now. Call +256 753 972 515 for the latest schedule.';
    eventList.replaceChildren(empty);
  }
}

if (!cmsPageSlug && !availabilityToken) loadEvents();

if (!cmsPageSlug && !availabilityToken) {
  const groupFilters = document.querySelector('#group-filters');
  const smallGroupsList = document.querySelector('#small-groups-list');
  let groupSearchTimer;
  let visitorLocation;

  function renderSmallGroup(group) {
    const article = document.createElement('article');
    article.className = 'group-result';
    const details = document.createElement('div');
    const name = document.createElement('h3');
    name.textContent = group.name;
    const schedule = document.createElement('p');
    schedule.className = 'group-schedule';
    schedule.textContent = `${group.meeting_day} · ${group.meeting_time} · ${group.age_group}`;
    const area = document.createElement('p');
    area.textContent = group.meeting_area;
    const description = document.createElement('p');
    description.textContent = group.description;
    const groupState = document.createElement('span');
    groupState.className = group.is_open ? 'group-status is-open' : 'group-status';
    groupState.textContent = group.is_open ? 'Open to new members' : 'Waitlist';
    details.append(name, schedule, area, description, groupState);
    article.append(details);

    if (group.distance_km !== null && group.distance_km !== undefined) {
      const distance = document.createElement('p');
      distance.className = 'group-distance';
      distance.textContent = `${group.distance_km.toFixed(1)} km away`;
      article.append(distance);
    }
    if (group.latitude !== null && group.longitude !== null) {
      const mapLink = document.createElement('a');
      mapLink.className = 'underlined-link';
      mapLink.href = `https://www.openstreetmap.org/?mlat=${encodeURIComponent(group.latitude)}&mlon=${encodeURIComponent(group.longitude)}#map=15/${encodeURIComponent(group.latitude)}/${encodeURIComponent(group.longitude)}`;
      mapLink.target = '_blank';
      mapLink.rel = 'noreferrer';
      mapLink.textContent = 'Approximate map point ↗';
      article.append(mapLink);
    }
    if (!group.is_open) {
      const disclosure = document.createElement('details');
      const summary = document.createElement('summary');
      summary.className = 'card-link';
      summary.textContent = 'Join the waitlist';
      const form = document.createElement('form');
      form.className = 'group-waitlist-form';
      form.dataset.groupId = String(group.id);
      form.innerHTML = '<label>Your name<input name="name" maxlength="120" autocomplete="name" required></label><label>Phone or email<input name="contact" maxlength="320" autocomplete="email" required></label><label class="consent-check"><input name="consent" type="checkbox" required><span>I agree to be contacted about this group.</span></label><button class="button button-green" type="submit">Request a place</button><p class="form-status" aria-live="polite"></p>';
      disclosure.append(summary, form);
      article.append(disclosure);
    } else {
      const contactLink = document.createElement('a');
      contactLink.className = 'card-link';
      contactLink.href = 'tel:+256753972515';
      contactLink.textContent = 'Ask about joining ↗';
      article.append(contactLink);
    }
    return article;
  }

  async function loadSmallGroups() {
    const params = new URLSearchParams();
    const search = document.querySelector('#group-search').value.trim();
    const day = document.querySelector('#group-day').value;
    const ageGroup = document.querySelector('#group-age').value;
    if (search) params.set('q', search);
    if (day) params.set('meeting_day', day);
    if (ageGroup) params.set('age_group', ageGroup);
    if (visitorLocation) {
      params.set('near_latitude', String(visitorLocation.latitude));
      params.set('near_longitude', String(visitorLocation.longitude));
      params.set('radius_km', document.querySelector('#group-radius').value);
    }
    const status = document.querySelector('#group-search-status');
    status.textContent = 'Searching groups…';
    try {
      const groups = await apiRequest(`/groups?${params}`);
      smallGroupsList.replaceChildren();
      if (!groups.length) {
        const empty = document.createElement('p');
        empty.className = 'empty-events';
        empty.textContent = 'No groups match those filters. Call the church and we will help you connect.';
        smallGroupsList.append(empty);
      } else {
        smallGroupsList.append(...groups.map(renderSmallGroup));
      }
      status.textContent = `${groups.length} ${groups.length === 1 ? 'group' : 'groups'}`;
    } catch {
      status.textContent = 'Group details are unavailable right now.';
      smallGroupsList.replaceChildren();
    }
  }

  groupFilters.addEventListener('input', () => {
    window.clearTimeout(groupSearchTimer);
    groupSearchTimer = window.setTimeout(loadSmallGroups, 250);
  });
  groupFilters.addEventListener('change', loadSmallGroups);
  document.querySelector('#group-near-me').addEventListener('click', () => {
    if (!navigator.geolocation) {
      document.querySelector('#group-search-status').textContent = 'Location search is not available in this browser.';
      return;
    }
    navigator.geolocation.getCurrentPosition((position) => {
      visitorLocation = { latitude: position.coords.latitude, longitude: position.coords.longitude };
      document.querySelector('#group-clear-location').hidden = false;
      loadSmallGroups();
    }, () => {
      document.querySelector('#group-search-status').textContent = 'Location was not shared. Search by area instead.';
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
  });
  document.querySelector('#group-clear-location').addEventListener('click', () => {
    visitorLocation = null;
    document.querySelector('#group-clear-location').hidden = true;
    loadSmallGroups();
  });
  smallGroupsList.addEventListener('submit', async (event) => {
    if (!event.target.matches('.group-waitlist-form')) return;
    event.preventDefault();
    const form = event.target;
    const button = form.querySelector('button[type="submit"]');
    const status = form.querySelector('.form-status');
    const values = new FormData(form);
    button.disabled = true;
    try {
      await apiRequest(`/groups/${form.dataset.groupId}/waitlist`, {
        method: 'POST',
        body: JSON.stringify({
          name: values.get('name'),
          contact: values.get('contact'),
          consent: values.get('consent') === 'on',
        }),
      });
      setStatus(status, 'Your request was sent. The group leader will follow up.');
      form.reset();
    } catch (error) {
      setStatus(status, error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  loadSmallGroups();
}

eventList.addEventListener('submit', async (event) => {
  if (!event.target.matches('form[data-event-id]')) return;
  event.preventDefault();
  const form = event.target;
  const submit = form.querySelector('button[type="submit"]');
  const status = form.querySelector('.form-status');
  submit.disabled = true;
  const values = new FormData(form);
  try {
    await apiRequest(`/events/${form.dataset.eventId}/registrations`, {
      method: 'POST',
      body: JSON.stringify({ name: values.get('name'), email: values.get('email'), consent: values.get('consent') === 'on' }),
    });
    setStatus(status, 'Registration recorded. Contact the church to confirm; email confirmations are not active yet.');
    form.reset();
  } catch (error) {
    setStatus(status, error.message, true);
    submit.disabled = false;
  }
});

document.querySelector('#giving-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const status = document.querySelector('#giving-status');
  apiRequest('/giving/status')
    .then((result) => setStatus(status, result.message))
    .catch(() => setStatus(status, 'Online giving is unavailable. Please call +256 753 972 515 to arrange giving.', true));
});

document.querySelector('#prayer-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.querySelector('#prayer-status');
  const values = new FormData(form);
  try {
    await apiRequest('/prayer-requests', {
      method: 'POST',
      body: JSON.stringify({
        name: values.get('name') || null,
        contact: values.get('contact') || null,
        message: values.get('message'),
        consent: form.querySelector('[type="checkbox"]').checked,
      }),
    });
    setStatus(status, 'Your request was received securely. Automated follow-up is not active; please call for urgent care.');
    form.reset();
  } catch (error) {
    setStatus(status, `${error.message} Please call +256 753 972 515 for confidential support.`, true);
  }
});

document.querySelector('#contact-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.querySelector('#contact-status');
  const values = new FormData(form);
  try {
    await apiRequest('/contact', {
      method: 'POST',
      body: JSON.stringify({
        name: values.get('name'),
        email: values.get('email'),
        subject: values.get('subject'),
        message: values.get('message'),
        consent: values.get('consent') === 'on',
      }),
    });
    setStatus(status, 'Your message was sent. A church team member will follow up.');
    form.reset();
  } catch (error) {
    setStatus(status, error.message, true);
  }
});

document.querySelector('#visitor-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  const status = document.querySelector('#visitor-status');
  try {
    await apiRequest('/visitors', {
      method: 'POST',
      body: JSON.stringify({
        name: values.get('name'),
        contact: values.get('contact'),
        visit_date: values.get('visit_date') || null,
        consent: values.get('consent') === 'on',
      }),
    });
    setStatus(status, 'Thanks for letting us know. A church team member will follow up.');
    form.reset();
  } catch (error) {
    setStatus(status, error.message, true);
  }
});

document.querySelector('#newsletter-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.querySelector('#newsletter-status');
  try {
    await apiRequest('/newsletter', {
      method: 'POST',
      body: JSON.stringify({
        email: new FormData(form).get('email'),
        consent: form.querySelector('[name="consent"]').checked,
      }),
    });
    setStatus(status, 'You are subscribed. Newsletter delivery is not active yet.');
    form.reset();
  } catch (error) {
    setStatus(status, error.message, true);
  }
});

document.querySelector('#availability-response-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const status = document.querySelector('#availability-response-status');
  const values = new FormData(form);
  try {
    await apiRequest('/volunteer-availability/respond', {
      method: 'POST',
      body: JSON.stringify({
        token: availabilityToken,
        is_available: values.get('is_available') === 'true',
      }),
    });
    setStatus(status, 'Thank you. Your response has been recorded.');
    form.querySelectorAll('input, button').forEach((control) => { control.disabled = true; });
    window.history.replaceState({}, document.title, `${window.location.pathname}${window.location.search}`);
  } catch (error) {
    setStatus(status, error.message, true);
  }
});