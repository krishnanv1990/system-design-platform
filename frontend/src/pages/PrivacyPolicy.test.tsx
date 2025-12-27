/**
 * Tests for Privacy Policy page
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import PrivacyPolicy from './PrivacyPolicy'

const renderWithRouter = (component: React.ReactNode) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('PrivacyPolicy', () => {
  it('renders the page title', () => {
    renderWithRouter(<PrivacyPolicy />)
    expect(screen.getByRole('heading', { name: /Privacy Policy/i })).toBeInTheDocument()
  })

  it('displays last updated date', () => {
    renderWithRouter(<PrivacyPolicy />)
    expect(screen.getByText(/Last updated:/)).toBeInTheDocument()
  })

  describe('Required sections', () => {
    it('has Information We Collect section', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('heading', { name: /Information We Collect/i })).toBeInTheDocument()
    })

    it('has How We Use Your Information section', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('heading', { name: /How We Use Your Information/i })).toBeInTheDocument()
    })

    it('has Data Storage and Security section', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('heading', { name: /Data Storage and Security/i })).toBeInTheDocument()
    })

    it('has Third-Party Services section', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('heading', { name: /Third-Party Services/i })).toBeInTheDocument()
    })

    it('has Cookies and Tracking section', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('heading', { name: /Cookies and Tracking/i })).toBeInTheDocument()
    })

    it('has Your Rights section', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('heading', { name: /Your Rights/i })).toBeInTheDocument()
    })

    it('has Data Deletion section', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('heading', { name: /Data Deletion/i })).toBeInTheDocument()
    })

    it('has Regional Privacy Rights section', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('heading', { name: /Regional Privacy Rights/i })).toBeInTheDocument()
    })
  })

  describe('Information collection content', () => {
    it('mentions email address collection', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/Email address/i).length).toBeGreaterThan(0)
    })

    it('mentions OAuth providers', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/Google, Facebook, LinkedIn, or GitHub/i).length).toBeGreaterThan(0)
    })

    it('mentions design data', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/System design diagrams/i).length).toBeGreaterThan(0)
    })

    it('mentions chat conversations', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/Chat conversations/i).length).toBeGreaterThan(0)
    })
  })

  describe('Third-party services', () => {
    it('mentions Anthropic/Claude', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/Anthropic/i).length).toBeGreaterThan(0)
    })

    it('mentions Google Cloud Platform', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/Google Cloud Platform/i).length).toBeGreaterThan(0)
    })
  })

  describe('User rights (GDPR/CCPA)', () => {
    it('mentions right to access', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/Request a copy of the personal data/i).length).toBeGreaterThan(0)
    })

    it('mentions right to deletion', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/Request deletion of your account/i).length).toBeGreaterThan(0)
    })

    it('mentions GDPR', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/GDPR/i).length).toBeGreaterThan(0)
    })

    it('mentions CCPA', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/CCPA/i).length).toBeGreaterThan(0)
    })
  })

  describe('Data deletion info', () => {
    it('mentions permanent deletion', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/permanently deleted/i).length).toBeGreaterThan(0)
    })

    it('mentions irreversible action', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getAllByText(/irreversible/i).length).toBeGreaterThan(0)
    })
  })

  describe('Navigation links', () => {
    it('has back button', () => {
      renderWithRouter(<PrivacyPolicy />)
      expect(screen.getByRole('link', { name: /Back/i })).toBeInTheDocument()
    })

    it('links to Terms of Service', () => {
      renderWithRouter(<PrivacyPolicy />)
      const termsLinks = screen.getAllByRole('link', { name: /Terms/i })
      expect(termsLinks.length).toBeGreaterThan(0)
    })

    it('links to Account Settings', () => {
      renderWithRouter(<PrivacyPolicy />)
      const settingsLinks = screen.getAllByRole('link', { name: /Account Settings|Settings/i })
      expect(settingsLinks.length).toBeGreaterThan(0)
    })
  })
})
