import { expect, test } from '@playwright/test';

test('public homepage navigation works on a mobile viewport', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { level: 1, name: /Bwala Deliverance and Healing Ministries/ })).toBeVisible();
  const menuToggle = page.locator('.menu-toggle');
  await menuToggle.click();
  await expect(menuToggle).toHaveAttribute('aria-expanded', 'true');

  await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Plan a visit' }).click();
  await expect(page).toHaveURL(/#visit$/);
  await expect(page.getByRole('heading', { name: /Faith is better/ })).toBeVisible();
});

test('staff sign-in displays an authentication error without exposing the console', async ({ page }) => {
  await page.route('**/api/v1/auth/token', (route) => route.fulfill({
    status: 401,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'Invalid credentials' }),
  }));

  await page.goto('/admin.html');
  await page.locator('#login-email').fill('staff@example.org');
  await page.locator('#login-password').fill('incorrect-password');
  await page.getByRole('button', { name: 'Sign in' }).click();

  await expect(page.locator('#login-status')).toHaveText('Invalid credentials');
  await expect(page.locator('#console-panel')).toBeHidden();
});
test('giving shows manual MTN and Airtel instructions without collecting card data', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel('Choose an amount').fill('50000');
  await page.getByLabel('MTN Mobile Money').check();
  await page.getByRole('button', { name: 'Show payment instructions' }).click();

  const instructions = page.locator('#giving-instructions');
  await expect(instructions).toBeVisible();
  await expect(instructions).toContainText('85380938');
  await expect(instructions).toContainText('50,000');
  await expect(page.locator('#giving-status')).toContainText('no payment was initiated or confirmed');
  await expect(page.locator('#giving-form input[autocomplete="cc-number"]')).toHaveCount(0);

  await page.getByLabel('Airtel Money').check();
  await page.getByRole('button', { name: 'Show payment instructions' }).click();
  await expect(instructions).toContainText('6781771');
});

test('public safeguarding form submits only after privacy acknowledgement', async ({ page }) => {
  let submittedReport;
  await page.route('**/api/v1/safeguarding/reports', async (route) => {
    submittedReport = route.request().postDataJSON();
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ id: 17, status: 'new', retention_until: '2051-11-01', message: 'Received' }),
    });
  });

  await page.goto('/');
  await page.getByLabel('Report type').selectOption('incident');
  await page.getByLabel('Date', { exact: true }).last().fill('2026-10-25');
  await page.locator('#safeguarding-incident-time').fill('14:30');
  await page.locator('#safeguarding-location').fill('Church grounds');
  await page.locator('#safeguarding-people').fill('Volunteer and child');
  await page.locator('#safeguarding-facts').fill('A factual description of the incident was provided.');
  await page.locator('#safeguarding-reporter-name').fill('Concerned Parent');
  await page.locator('#safeguarding-reporter-contact').fill('parent@example.org');

  await page.getByRole('button', { name: 'Submit confidential report' }).click();
  expect(submittedReport).toBeUndefined();

  await page.locator('#safeguarding-report-form [name="privacy_acknowledged"]').check();
  await page.getByRole('button', { name: 'Submit confidential report' }).click();
  await expect(page.locator('#safeguarding-report-status')).toContainText('Report 17 received');
  expect(submittedReport.privacy_acknowledged).toBe(true);
  expect(submittedReport.reporter_contact).toBe('parent@example.org');
});

test('safeguarding lead sees restricted vetting workspace and member selector', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('bwala_staff_token', 'test-session-token'));
  await page.route('**/api/v1/auth/me', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ id: 8, role: 'safeguarding_lead', display_name: 'Safeguarding Lead' }),
  }));
  await page.route('**/api/v1/admin/safeguarding/reports', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([]),
  }));
  await page.route('**/api/v1/admin/safeguarding/vetting/members', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{ id: 12, name: 'Volunteer Member' }]),
  }));
  await page.route('**/api/v1/admin/safeguarding/vetting', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{
      id: 4,
      member_id: 12,
      member_name: 'Volunteer Member',
      government_id: 'TEST-ID',
      reference_names: 'Reference Person',
      reference_contacts: 'reference@example.org',
      background_check_consent: true,
      background_check_status: 'pending',
      references_checked: false,
      training_completed_at: null,
      service_started_at: '2026-10-01',
      service_ended_at: null,
      retention_until: null,
      status: 'pending',
      created_by_id: 2,
      reviewed_by_id: null,
      created_at: '2026-10-01T10:00:00Z',
      updated_at: '2026-10-01T10:00:00Z',
    }]),
  }));

  await page.goto('/admin.html');
  await page.getByRole('tab', { name: 'Volunteer vetting' }).click();
  await expect(page.locator('#volunteer-vetting-form')).toBeVisible();
  await expect(page.locator('#vetting-member')).toContainText('Volunteer Member');
  await expect(page.locator('#volunteer-vetting-list')).toContainText('Volunteer Member');
  await expect(page.locator('#volunteer-vetting-list')).toContainText('TEST-ID');
});