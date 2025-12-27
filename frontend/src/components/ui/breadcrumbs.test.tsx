import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Breadcrumbs } from './breadcrumbs'

// Wrapper component to provide router context
const renderWithRouter = (ui: React.ReactElement, { route = '/' } = {}) => {
  return render(
    <MemoryRouter initialEntries={[route]}>
      {ui}
    </MemoryRouter>
  )
}

describe('Breadcrumbs', () => {
  it('renders nothing when no items provided and on root path', () => {
    const { container } = renderWithRouter(<Breadcrumbs />, { route: '/' })
    expect(container.querySelector('nav')).toBeNull()
  })

  it('renders home link', () => {
    renderWithRouter(
      <Breadcrumbs items={[{ label: 'Problems', href: '/problems' }]} />,
      { route: '/problems' }
    )

    expect(screen.getByLabelText('Home')).toBeInTheDocument()
  })

  it('renders provided breadcrumb items', () => {
    renderWithRouter(
      <Breadcrumbs
        items={[
          { label: 'Problems', href: '/problems' },
          { label: 'URL Shortener', href: '/problems/1' },
          { label: 'Submit' },
        ]}
      />
    )

    expect(screen.getByText('Problems')).toBeInTheDocument()
    expect(screen.getByText('URL Shortener')).toBeInTheDocument()
    expect(screen.getByText('Submit')).toBeInTheDocument()
  })

  it('marks last item as current page', () => {
    renderWithRouter(
      <Breadcrumbs
        items={[
          { label: 'Problems', href: '/problems' },
          { label: 'Submit' },
        ]}
      />
    )

    const submitText = screen.getByText('Submit')
    expect(submitText).toHaveAttribute('aria-current', 'page')
  })

  it('renders links for items with href', () => {
    renderWithRouter(
      <Breadcrumbs
        items={[
          { label: 'Problems', href: '/problems' },
          { label: 'Details' },
        ]}
      />
    )

    const problemsLink = screen.getByRole('link', { name: 'Problems' })
    expect(problemsLink).toHaveAttribute('href', '/problems')
  })

  it('renders text (not link) for last item', () => {
    renderWithRouter(
      <Breadcrumbs
        items={[
          { label: 'Problems', href: '/problems' },
          { label: 'Details' },
        ]}
      />
    )

    // The last item should not be a link
    const links = screen.getAllByRole('link')
    const linkTexts = links.map(link => link.textContent)
    expect(linkTexts).not.toContain('Details')
  })

  it('includes separators between items', () => {
    const { container } = renderWithRouter(
      <Breadcrumbs
        items={[
          { label: 'Problems', href: '/problems' },
          { label: 'Details' },
        ]}
      />
    )

    // Check for ChevronRight icons (used as separators)
    const svgs = container.querySelectorAll('svg')
    // Home icon + 2 chevrons
    expect(svgs.length).toBeGreaterThanOrEqual(2)
  })

  it('has proper accessibility attributes', () => {
    renderWithRouter(
      <Breadcrumbs items={[{ label: 'Problems', href: '/problems' }]} />
    )

    const nav = screen.getByRole('navigation')
    expect(nav).toHaveAttribute('aria-label', 'Breadcrumb')
  })

  it('applies custom className', () => {
    renderWithRouter(
      <Breadcrumbs
        items={[{ label: 'Test' }]}
        className="custom-class"
      />
    )

    const nav = screen.getByRole('navigation')
    expect(nav).toHaveClass('custom-class')
  })
})
