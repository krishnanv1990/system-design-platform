#!/usr/bin/env python3
"""
Generate URL Shortener System Design Diagram
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# Set up the figure with a nice size
fig, ax = plt.subplots(1, 1, figsize=(16, 12))
ax.set_xlim(0, 16)
ax.set_ylim(0, 12)
ax.set_aspect('equal')
ax.axis('off')

# Color palette
colors = {
    'client': '#3B82F6',      # Blue
    'lb': '#10B981',          # Green
    'api': '#8B5CF6',         # Purple
    'cache': '#F59E0B',       # Amber
    'db': '#EF4444',          # Red
    'queue': '#EC4899',       # Pink
    'analytics': '#06B6D4',   # Cyan
    'cdn': '#84CC16',         # Lime
    'bg': '#F8FAFC',          # Light gray
    'text': '#1E293B',        # Dark slate
    'arrow': '#64748B',       # Slate
}

def draw_box(ax, x, y, width, height, color, label, sublabel=None, radius=0.3):
    """Draw a rounded rectangle box with label"""
    box = FancyBboxPatch(
        (x - width/2, y - height/2), width, height,
        boxstyle=f"round,pad=0.02,rounding_size={radius}",
        facecolor=color,
        edgecolor='white',
        linewidth=2,
        alpha=0.9
    )
    ax.add_patch(box)

    # Add label
    ax.text(x, y + (0.15 if sublabel else 0), label,
            ha='center', va='center', fontsize=11, fontweight='bold', color='white')
    if sublabel:
        ax.text(x, y - 0.25, sublabel,
                ha='center', va='center', fontsize=8, color='white', alpha=0.9)

def draw_arrow(ax, start, end, color='#64748B', style='simple', curved=False):
    """Draw an arrow between two points"""
    if curved:
        arrow = FancyArrowPatch(
            start, end,
            connectionstyle="arc3,rad=0.2",
            arrowstyle='-|>',
            mutation_scale=15,
            color=color,
            linewidth=2
        )
    else:
        arrow = FancyArrowPatch(
            start, end,
            arrowstyle='-|>',
            mutation_scale=15,
            color=color,
            linewidth=2
        )
    ax.add_patch(arrow)

def draw_database(ax, x, y, color, label):
    """Draw a database cylinder shape"""
    # Draw cylinder body
    width, height = 1.4, 1.0
    ellipse_height = 0.25

    # Bottom ellipse
    ellipse_bottom = mpatches.Ellipse((x, y - height/2), width, ellipse_height,
                                        facecolor=color, edgecolor='white', linewidth=2, alpha=0.9)
    ax.add_patch(ellipse_bottom)

    # Rectangle body
    rect = plt.Rectangle((x - width/2, y - height/2), width, height,
                         facecolor=color, edgecolor='white', linewidth=2, alpha=0.9)
    ax.add_patch(rect)

    # Top ellipse
    ellipse_top = mpatches.Ellipse((x, y + height/2), width, ellipse_height,
                                    facecolor=color, edgecolor='white', linewidth=2, alpha=0.9)
    ax.add_patch(ellipse_top)

    # Label
    ax.text(x, y, label, ha='center', va='center', fontsize=10, fontweight='bold', color='white')

# Title
ax.text(8, 11.5, 'URL Shortener System Design', ha='center', va='center',
        fontsize=20, fontweight='bold', color=colors['text'])
ax.text(8, 11.0, 'Scalable Architecture for High-Throughput URL Shortening Service',
        ha='center', va='center', fontsize=11, color='#64748B')

# Draw components

# Clients (top)
draw_box(ax, 3, 9.5, 1.8, 0.9, colors['client'], 'Web Client', 'Browser')
draw_box(ax, 5.5, 9.5, 1.8, 0.9, colors['client'], 'Mobile App', 'iOS/Android')
draw_box(ax, 8, 9.5, 1.8, 0.9, colors['client'], 'API Client', 'Third-party')

# CDN
draw_box(ax, 13, 9.5, 2.0, 0.9, colors['cdn'], 'CDN', 'CloudFlare/Fastly')

# Load Balancer
draw_box(ax, 5.5, 7.5, 3.0, 0.9, colors['lb'], 'Load Balancer', 'NGINX / Cloud LB')

# API Servers
draw_box(ax, 3, 5.5, 2.0, 1.0, colors['api'], 'API Server 1', 'Node.js/Python')
draw_box(ax, 5.5, 5.5, 2.0, 1.0, colors['api'], 'API Server 2', 'Node.js/Python')
draw_box(ax, 8, 5.5, 2.0, 1.0, colors['api'], 'API Server N', 'Node.js/Python')

# Cache Layer
draw_box(ax, 3.5, 3.5, 2.5, 1.0, colors['cache'], 'Redis Cache', 'URL Lookups')
draw_box(ax, 7, 3.5, 2.5, 1.0, colors['cache'], 'Redis Cache', 'Rate Limiting')

# Databases
draw_database(ax, 3, 1.5, colors['db'], 'PostgreSQL\nPrimary')
draw_database(ax, 5.5, 1.5, colors['db'], 'PostgreSQL\nReplica')
draw_database(ax, 8, 1.5, colors['db'], 'PostgreSQL\nReplica')

# Analytics & Queue
draw_box(ax, 11.5, 5.5, 2.2, 1.0, colors['queue'], 'Message Queue', 'Kafka/RabbitMQ')
draw_box(ax, 11.5, 3.5, 2.2, 1.0, colors['analytics'], 'Analytics', 'ClickHouse')
draw_box(ax, 14, 5.5, 2.0, 1.0, colors['analytics'], 'Metrics', 'Prometheus')

# Key Generation Service
draw_box(ax, 14, 7.5, 2.2, 0.9, colors['queue'], 'Key Gen Service', 'Pre-generated IDs')

# Draw arrows (connections)

# Clients to LB
draw_arrow(ax, (3, 9.0), (4.5, 8.0))
draw_arrow(ax, (5.5, 9.0), (5.5, 8.0))
draw_arrow(ax, (8, 9.0), (6.5, 8.0))

# CDN to LB (for redirects)
draw_arrow(ax, (12, 9.5), (7.0, 7.8), curved=True)

# LB to API Servers
draw_arrow(ax, (4.5, 7.0), (3, 6.0))
draw_arrow(ax, (5.5, 7.0), (5.5, 6.0))
draw_arrow(ax, (6.5, 7.0), (8, 6.0))

# API to Cache
draw_arrow(ax, (3, 5.0), (3.5, 4.0))
draw_arrow(ax, (5.5, 5.0), (5.0, 4.0))
draw_arrow(ax, (5.5, 5.0), (6.5, 4.0))
draw_arrow(ax, (8, 5.0), (7.5, 4.0))

# Cache to DB
draw_arrow(ax, (3.5, 3.0), (3.5, 2.1))
draw_arrow(ax, (4.5, 3.0), (5.5, 2.1))
draw_arrow(ax, (7, 3.0), (7, 2.1), curved=True)

# API to Queue (analytics events)
draw_arrow(ax, (9, 5.5), (10.4, 5.5))

# Queue to Analytics
draw_arrow(ax, (11.5, 5.0), (11.5, 4.0))

# API to Key Gen
draw_arrow(ax, (8.5, 6.0), (13, 7.0), curved=True)

# API to Metrics
draw_arrow(ax, (9, 5.8), (13, 5.8))

# Add legend/notes
legend_y = 1.2
ax.text(11.5, legend_y + 0.8, 'Data Flow:', fontsize=10, fontweight='bold', color=colors['text'])
ax.text(11.5, legend_y + 0.3, '1. Client requests short URL', fontsize=8, color='#64748B')
ax.text(11.5, legend_y - 0.1, '2. Check Redis cache first', fontsize=8, color='#64748B')
ax.text(11.5, legend_y - 0.5, '3. Fallback to database', fontsize=8, color='#64748B')
ax.text(11.5, legend_y - 0.9, '4. Log analytics async', fontsize=8, color='#64748B')

# Add scale indicators
ax.text(1, 5.5, 'Auto-scaling\ngroup', ha='center', fontsize=8, color='#64748B',
        bbox=dict(boxstyle='round', facecolor='#F1F5F9', edgecolor='#E2E8F0'))

ax.text(5.5, 0.5, 'Primary-Replica Replication', ha='center', fontsize=8, color='#64748B',
        bbox=dict(boxstyle='round', facecolor='#F1F5F9', edgecolor='#E2E8F0'))

# Save the figure
plt.tight_layout()
plt.savefig('docs/url-shortener-design.png', dpi=150, bbox_inches='tight',
            facecolor='white', edgecolor='none')
print("Diagram saved to docs/url-shortener-design.png")
