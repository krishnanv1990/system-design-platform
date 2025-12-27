/**
 * Tests for Terms of Service page
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import TermsOfService from './TermsOfService'

const renderWithRouter = (component: React.ReactNode) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('TermsOfService', () => {
  it('renders the page title', () => {
    renderWithRouter(<TermsOfService />)
    expect(screen.getByRole('heading', { name: /Terms of Service/i })).toBeInTheDocument()
  })

  it('displays last updated date', () => {
    renderWithRouter(<TermsOfService />)
    expect(screen.getByText(/Last updated:/)).toBeInTheDocument()
  })

  describe('Required sections', () => {
    it('has AI Disclaimer section', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('heading', { name: /AI Disclaimer/i })).toBeInTheDocument()
    })

    it('has No Employment Guarantee section', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('heading', { name: /No Employment Guarantee/i })).toBeInTheDocument()
    })

    it('has Data Usage section', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('heading', { name: /Data Usage/i })).toBeInTheDocument()
    })

    it('has Account Terms section', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('heading', { name: /Account Terms/i })).toBeInTheDocument()
    })

    it('has Intellectual Property Rights section', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('heading', { name: /Intellectual Property Rights/i })).toBeInTheDocument()
    })

    it('has Service Availability section', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('heading', { name: /Service Availability/i })).toBeInTheDocument()
    })

    it('has Limitation of Liability section', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('heading', { name: /Limitation of Liability/i })).toBeInTheDocument()
    })

    it('has Contact Us section', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('heading', { name: /Contact Us/i })).toBeInTheDocument()
    })
  })

  describe('AI Disclaimer content', () => {
    it('mentions AI-generated feedback', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getAllByText(/AI-generated/i).length).toBeGreaterThan(0)
    })

    it('mentions Claude/Anthropic', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getAllByText(/Claude/i).length).toBeGreaterThan(0)
    })
  })

  describe('No Employment Guarantee content', () => {
    it('mentions educational purposes', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getAllByText(/educational and practice purposes/i).length).toBeGreaterThan(0)
    })

    it('mentions difficulty levels', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getAllByText(/L5\/L6\/L7/i).length).toBeGreaterThan(0)
    })
  })

  describe('Navigation links', () => {
    it('has back button', () => {
      renderWithRouter(<TermsOfService />)
      expect(screen.getByRole('link', { name: /Back/i })).toBeInTheDocument()
    })

    it('links to Privacy Policy', () => {
      renderWithRouter(<TermsOfService />)
      const privacyLinks = screen.getAllByRole('link', { name: /Privacy/i })
      expect(privacyLinks.length).toBeGreaterThan(0)
    })

    it('links to Account Settings', () => {
      renderWithRouter(<TermsOfService />)
      const settingsLinks = screen.getAllByRole('link', { name: /Account Settings|Settings/i })
      expect(settingsLinks.length).toBeGreaterThan(0)
    })
  })
})
