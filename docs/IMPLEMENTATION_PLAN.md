# Implementation Plan: Diagram Tool Fixes and Improvements

## Overview

This document outlines the implementation plan to fix all bugs, UX issues, and add missing features identified in the analysis. The plan is organized into phases, with each phase containing related tasks.

**State Tracking:** Progress is tracked in `IMPLEMENTATION_STATE.json` for crash recovery.

---

## Phase 1: Critical Bug Fixes (Priority: Highest)

### 1.1 Fix Arrow Hit Detection
- **File:** `frontend/src/components/DesignCanvas.tsx`
- **Issue:** Only checks midpoint, long arrows impossible to select
- **Solution:** Implement point-to-line-segment distance calculation
- **Tasks:**
  - [ ] Create `pointToLineDistance` utility function
  - [ ] Update arrow click detection to check entire line
  - [ ] Add configurable hit tolerance (e.g., 10px)

### 1.2 Implement Missing Shape Types (Diamond, Cylinder, Hexagon)
- **Files:** `DesignCanvas.tsx`, `canvas.ts`, toolbar
- **Issue:** Types defined but no rendering code
- **Tasks:**
  - [ ] Add diamond shape rendering (rotated square)
  - [ ] Add cylinder shape rendering (for database visualization)
  - [ ] Add hexagon shape rendering
  - [ ] Add tools to toolbar
  - [ ] Add keyboard shortcuts (D, Y, H)

### 1.3 Fix Text Element Bounding Box
- **File:** `DesignCanvas.tsx`
- **Issue:** Fixed 100x24 size regardless of actual text
- **Tasks:**
  - [ ] Create text measurement utility
  - [ ] Update text element creation to measure actual dimensions
  - [ ] Update text element after editing to recalculate bounds

### 1.4 Fix Connection Cleanup on Element Deletion
- **File:** `DesignCanvas.tsx`
- **Issue:** Stale connections remain when connected shapes deleted
- **Tasks:**
  - [ ] Create utility to find arrows connected to an element
  - [ ] On element deletion, clear connection references from arrows
  - [ ] Update arrow positions to current endpoint positions

### 1.5 Fix Z-Index on Paste
- **File:** `DesignCanvas.tsx`
- **Issue:** Duplicate z-indices possible
- **Tasks:**
  - [ ] Ensure pasted elements get unique, sequential z-indices
  - [ ] Place pasted elements on top of existing elements

---

## Phase 2: Medium Bug Fixes

### 2.1 Fix Text Input Overlay Position at High Zoom
- **File:** `DesignCanvas.tsx`
- **Issue:** Overlay offset at extreme zoom levels
- **Tasks:**
  - [ ] Review position calculation
  - [ ] Account for viewport transform correctly
  - [ ] Test at various zoom levels (10%, 50%, 200%, 400%)

### 2.2 Fix Keyboard Shortcuts When Menus Open
- **File:** `DesignCanvas.tsx`
- **Issue:** Shortcuts trigger when menus are open
- **Tasks:**
  - [ ] Add menu open state check to keyboard handler
  - [ ] Prevent tool shortcuts when any dropdown is open

### 2.3 Add Element Position/Size Validation
- **File:** `DesignCanvas.tsx`, resize hooks
- **Issue:** Elements can have negative size or be dragged off-canvas
- **Tasks:**
  - [ ] Add minimum size constraint during resize
  - [ ] Add bounds checking during drag (optional: allow off-canvas with recovery)
  - [ ] Add "fit to canvas" button if elements are off-screen

### 2.4 Improve Export Grid Removal
- **File:** `frontend/src/lib/canvasExport.ts`
- **Issue:** Fragile selector for grid removal
- **Tasks:**
  - [ ] Add data attribute to grid elements for reliable selection
  - [ ] Update export to use data attribute selector

---

## Phase 3: Critical UX Improvements

### 3.1 Add Properties Panel
- **Files:** New component `PropertiesPanel.tsx`
- **Issue:** Can't edit properties after creation
- **Tasks:**
  - [ ] Create PropertiesPanel component
  - [ ] Add stroke width control (1-10px)
  - [ ] Add stroke color picker with custom color input
  - [ ] Add fill color picker with custom color input
  - [ ] Add opacity slider (0-100%)
  - [ ] Add corner radius for rectangles
  - [ ] Add font size for text elements
  - [ ] Add line style selector for arrows
  - [ ] Integrate panel into DesignCanvas layout

### 3.2 Add Multi-line Text Support
- **Files:** `DesignCanvas.tsx`, types
- **Issue:** Single-line text only
- **Tasks:**
  - [ ] Update TextElement type to support multi-line
  - [ ] Change text input to textarea
  - [ ] Implement text wrapping with configurable width
  - [ ] Update text rendering to handle multiple lines
  - [ ] Update bounding box calculation for multi-line

### 3.3 Add Clear Canvas Confirmation
- **File:** `DesignCanvas.tsx`
- **Issue:** No confirmation, accidental deletion
- **Tasks:**
  - [ ] Create confirmation dialog component (or use existing)
  - [ ] Show dialog before clearing canvas
  - [ ] Add "Don't ask again" option (stored in localStorage)

### 3.4 Improve Connection Point Visibility
- **File:** `DesignCanvas.tsx`, `ConnectionPoints.tsx`
- **Issue:** Only visible during arrow drawing
- **Tasks:**
  - [ ] Show connection points on hover over any element
  - [ ] Add visual indicator for connected arrows (dot or highlight)
  - [ ] Show connection lines when arrow is selected

---

## Phase 4: Element Manipulation Features

### 4.1 Add Element Rotation
- **Files:** Types, `DesignCanvas.tsx`, `SelectionHandles.tsx`
- **Tasks:**
  - [ ] Add `rotation` property to BaseElement (default 0)
  - [ ] Add rotation handle above selection
  - [ ] Implement rotation drag behavior
  - [ ] Apply rotation transform to element rendering
  - [ ] Update hit detection for rotated elements
  - [ ] Update resize handles to work with rotation
  - [ ] Add rotation angle display during rotation
  - [ ] Add snap to 0°, 45°, 90° angles with Shift key

### 4.2 Add Element Grouping
- **Files:** Types, `DesignCanvas.tsx`, new `useGroups` hook
- **Tasks:**
  - [ ] Add GroupElement type with childIds array
  - [ ] Implement Ctrl+G to group selected elements
  - [ ] Implement Ctrl+Shift+G to ungroup
  - [ ] Handle group selection (select group, not children)
  - [ ] Handle group move (move all children)
  - [ ] Handle group resize (scale children proportionally)
  - [ ] Handle group delete (delete all children)
  - [ ] Handle double-click to enter group (select children)
  - [ ] Visual indicator for grouped elements

### 4.3 Add Element Locking
- **Files:** `DesignCanvas.tsx`, PropertiesPanel
- **Tasks:**
  - [ ] Implement `locked` property (already in types)
  - [ ] Prevent move/resize/delete of locked elements
  - [ ] Add lock/unlock button to toolbar or context menu
  - [ ] Visual indicator for locked elements (lock icon)
  - [ ] Add Ctrl+L shortcut for lock toggle

---

## Phase 5: Arrow and Connector Improvements

### 5.1 Add Arrow Labels
- **Files:** Types, `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Add `label` property to ArrowElement
  - [ ] Render label at midpoint of arrow
  - [ ] Allow label editing on double-click
  - [ ] Handle label positioning for angled lines
  - [ ] Add label background option for readability

### 5.2 Add Curved Connectors
- **Files:** Types, `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Add `curveType` property: 'straight' | 'curved' | 'elbow'
  - [ ] Implement bezier curve rendering for curved type
  - [ ] Add control point for curve adjustment
  - [ ] Implement elbow (orthogonal) connector
  - [ ] Update arrow head to align with curve end tangent

### 5.3 Add Bidirectional Arrows
- **Files:** Types, `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Add `arrowHead` property: 'end' | 'start' | 'both' | 'none'
  - [ ] Render arrow heads based on property
  - [ ] Add toggle in properties panel

---

## Phase 6: Enhanced Color and Styling

### 6.1 Add Custom Color Picker
- **Files:** `ColorPicker.tsx`
- **Tasks:**
  - [ ] Add hex color input field
  - [ ] Add RGB sliders (optional)
  - [ ] Add recent colors row
  - [ ] Add eyedropper tool (if browser supports)
  - [ ] Validate and sanitize color input

### 6.2 Add Element Opacity
- **Files:** `DesignCanvas.tsx`, PropertiesPanel
- **Tasks:**
  - [ ] Implement opacity property in rendering
  - [ ] Add opacity slider to properties panel
  - [ ] Support opacity in export

---

## Phase 7: Icon and Shape Library

### 7.1 Improve Existing Icons
- **File:** `DesignCanvas.tsx` (icon rendering section)
- **Tasks:**
  - [ ] Increase load balancer arrow visibility
  - [ ] Differentiate cache from database more clearly
  - [ ] Make blob storage more distinctive
  - [ ] Normalize stroke widths across icons
  - [ ] Make icons scale properly with element resize

### 7.2 Add Missing System Design Icons
- **Files:** `DesignCanvas.tsx`, `canvas.ts`, types
- **Tasks:**
  - [ ] Add Kubernetes/Container icon
  - [ ] Add Lambda/Serverless icon
  - [ ] Add CDN icon
  - [ ] Add Firewall icon
  - [ ] Add Mobile device icon
  - [ ] Add Microservice icon
  - [ ] Add Kafka/Event Stream icon
  - [ ] Add S3/Bucket icon
  - [ ] Update component menu with new icons

### 7.3 Add AWS/Azure/GCP Icon Libraries (Future)
- **Note:** This is a larger effort, placeholder for future
- **Tasks:**
  - [ ] Research icon licensing
  - [ ] Create icon browser component
  - [ ] Implement lazy loading for icon categories
  - [ ] Add search functionality

---

## Phase 8: UX Polish

### 8.1 Add Drag-and-Drop File Import
- **File:** `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Add onDragOver, onDragLeave, onDrop handlers
  - [ ] Show drop zone overlay when dragging files
  - [ ] Handle dropped files same as import
  - [ ] Support multiple file drop

### 8.2 Add Zoom to Selection
- **Files:** `useZoomPan.ts`, `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Calculate bounding box of selected elements
  - [ ] Add "Zoom to Selection" button or shortcut
  - [ ] Animate zoom transition

### 8.3 Add Auto-Save to LocalStorage
- **File:** `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Save canvas state to localStorage on change (debounced)
  - [ ] Load from localStorage on mount if no value prop
  - [ ] Add "Recover unsaved work" prompt

### 8.4 Add Alignment Guides
- **Files:** New `AlignmentGuides.tsx`, `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Detect element edges and centers during drag
  - [ ] Show guide lines when aligned with other elements
  - [ ] Snap to guides (in addition to grid)

---

## Phase 9: Performance Optimizations

### 9.1 Throttle Mouse Move Updates
- **File:** `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Use requestAnimationFrame for smooth updates
  - [ ] Debounce history saves during drag
  - [ ] Use refs for temporary state during interactions

### 9.2 Memoize Element Rendering
- **File:** `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Extract element rendering to separate memoized components
  - [ ] Only re-render elements that changed
  - [ ] Use React.memo with proper comparison

### 9.3 Optimize JSON Serialization
- **File:** `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Debounce onChange callback
  - [ ] Consider using structured clone instead of JSON
  - [ ] Only serialize on blur/commit, not every change

---

## Phase 10: Accessibility Improvements

### 10.1 Add Keyboard Navigation Between Elements
- **File:** `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Tab to cycle through elements
  - [ ] Show focus indicator on focused element
  - [ ] Enter to edit, Delete to remove

### 10.2 Add Screen Reader Support
- **File:** `DesignCanvas.tsx`
- **Tasks:**
  - [ ] Add aria-live region for selection changes
  - [ ] Add descriptions for each element type
  - [ ] Announce tool changes

### 10.3 Add High Contrast Mode
- **Files:** CSS/Tailwind config
- **Tasks:**
  - [ ] Detect prefers-contrast media query
  - [ ] Adjust colors for high contrast
  - [ ] Ensure selection indicators are visible

---

## Implementation Order (Priority)

1. **Phase 1** - Critical Bug Fixes (Do First)
2. **Phase 3.3** - Clear Canvas Confirmation (Quick Win)
3. **Phase 3.1** - Properties Panel (High Impact)
4. **Phase 2** - Medium Bug Fixes
5. **Phase 4.1** - Element Rotation
6. **Phase 5.1** - Arrow Labels
7. **Phase 4.2** - Element Grouping
8. **Phase 7.1** - Improve Existing Icons
9. **Phase 6** - Color and Styling
10. **Phase 3.2** - Multi-line Text
11. **Phase 5.2** - Curved Connectors
12. **Phase 7.2** - Add Missing Icons
13. **Phase 8** - UX Polish
14. **Phase 9** - Performance
15. **Phase 10** - Accessibility
16. **Phase 4.3** - Element Locking
17. **Phase 5.3** - Bidirectional Arrows

---

## Estimated Timeline

- **Phase 1:** 1-2 days
- **Phase 2:** 1 day
- **Phase 3:** 2-3 days
- **Phase 4:** 3-4 days
- **Phase 5:** 2-3 days
- **Phase 6:** 1 day
- **Phase 7.1-7.2:** 2-3 days
- **Phase 8:** 2 days
- **Phase 9:** 1 day
- **Phase 10:** 1-2 days

**Total Estimate:** 15-22 days of focused development

---

## State File

Progress is tracked in `IMPLEMENTATION_STATE.json`. Update this file after completing each task to enable crash recovery.
