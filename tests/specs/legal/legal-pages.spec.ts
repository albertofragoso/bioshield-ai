import { test as base, expect } from '@playwright/test'
import { test as mockedTest } from '../../fixtures'

// Alias for readability
const test = base

test.describe('Legal pages', () => {
  test('/privacy loads with correct heading and avatar', async ({ page }) => {
    await page.goto('/privacy')
    await expect(page.getByRole('heading', { name: 'Política de Privacidad' })).toBeVisible()
    await expect(page.getByAltText('BioShield soporte')).toBeVisible()
  })

  test('/privacy contains biomarker privacy statement', async ({ page }) => {
    await page.goto('/privacy')
    await expect(page.getByText(/biomarcadores NUNCA se envían a Gemini/i)).toBeVisible()
  })

  test('/terms loads with correct heading and avatar', async ({ page }) => {
    await page.goto('/terms')
    await expect(page.getByRole('heading', { name: 'Términos y Condiciones' })).toBeVisible()
    await expect(page.getByAltText('BioShield perfil')).toBeVisible()
  })

  test('/terms contains medical disclaimer', async ({ page }) => {
    await page.goto('/terms')
    await expect(page.getByText(/No es un servicio médico/i)).toBeVisible()
  })

  test('/privacy back link navigates to register', async ({ page }) => {
    await page.goto('/privacy')
    const backLink = page.getByRole('link', { name: /volver al registro/i })
    await expect(backLink).toHaveAttribute('href', '/register')
  })

  test('/terms back link navigates to register', async ({ page }) => {
    await page.goto('/terms')
    const backLink = page.getByRole('link', { name: /volver al registro/i })
    await expect(backLink).toHaveAttribute('href', '/register')
  })
})

test.describe('Register — terms consent', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/register')
  })

  test('submit button is disabled when checkbox is unchecked', async ({ page }) => {
    const submitBtn = page.getByRole('button', { name: /crear cuenta/i })
    await expect(submitBtn).toBeDisabled()
  })

  test('submit button enables after checking terms checkbox', async ({ page }) => {
    const submitBtn = page.getByRole('button', { name: /crear cuenta/i })
    await expect(submitBtn).toBeDisabled()

    // Click the custom checkbox label
    await page.getByText(/acepto la/i).click()
    await expect(submitBtn).toBeEnabled()
  })

  test('register checkbox has link to /privacy', async ({ page }) => {
    await expect(page.getByRole('link', { name: /política de privacidad/i }))
      .toHaveAttribute('href', '/privacy')
  })

  test('register checkbox has link to /terms', async ({ page }) => {
    await expect(page.getByRole('link', { name: /términos y condiciones/i }))
      .toHaveAttribute('href', '/terms')
  })
})

mockedTest.describe('BioSync — privacy card', () => {
  mockedTest('privacy card mentions Gemini explicitly', async ({ mockedPage }) => {
    await mockedPage.goto('/biosync')
    await expect(mockedPage.getByText(/Gemini/i)).toBeVisible()
  })
})
