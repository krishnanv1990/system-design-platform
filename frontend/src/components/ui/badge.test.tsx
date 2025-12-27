import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Badge } from './badge'

describe('Badge', () => {
  it('renders with default variant', () => {
    render(<Badge>Default</Badge>)
    const badge = screen.getByText('Default')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveClass('bg-primary')
  })

  it('renders with different variants', () => {
    const { rerender } = render(<Badge variant="secondary">Secondary</Badge>)
    expect(screen.getByText('Secondary')).toHaveClass('bg-secondary')

    rerender(<Badge variant="destructive">Destructive</Badge>)
    expect(screen.getByText('Destructive')).toHaveClass('bg-destructive')

    rerender(<Badge variant="outline">Outline</Badge>)
    expect(screen.getByText('Outline')).toHaveClass('text-foreground')

    rerender(<Badge variant="success">Success</Badge>)
    expect(screen.getByText('Success')).toHaveClass('bg-success')

    rerender(<Badge variant="warning">Warning</Badge>)
    expect(screen.getByText('Warning')).toHaveClass('bg-warning')
  })

  it('renders error category variants', () => {
    const { rerender } = render(<Badge variant="user_solution">User Solution</Badge>)
    expect(screen.getByText('User Solution')).toHaveClass('bg-amber-100')

    rerender(<Badge variant="platform">Platform</Badge>)
    expect(screen.getByText('Platform')).toHaveClass('bg-purple-100')

    rerender(<Badge variant="deployment">Deployment</Badge>)
    expect(screen.getByText('Deployment')).toHaveClass('bg-blue-100')
  })

  it('applies custom className', () => {
    render(<Badge className="custom-class">Custom</Badge>)
    expect(screen.getByText('Custom')).toHaveClass('custom-class')
  })

  it('renders children correctly', () => {
    render(
      <Badge>
        <span data-testid="child">Child content</span>
      </Badge>
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })
})
