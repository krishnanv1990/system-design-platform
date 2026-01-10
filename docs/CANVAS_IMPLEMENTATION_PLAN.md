# DesignCanvas Implementation Plan

A detailed implementation plan to address all issues identified in CANVAS_ANALYSIS.md, including step-by-step instructions, code locations, and testing strategies to achieve 100% test coverage.

---

## Table of Contents

1. [Phase 1: Critical Bug Fixes](#phase-1-critical-bug-fixes)
2. [Phase 2: Medium Bug Fixes](#phase-2-medium-bug-fixes)
3. [Phase 3: Minor Bug Fixes](#phase-3-minor-bug-fixes)
4. [Phase 4: High Priority UX Features](#phase-4-high-priority-ux-features)
5. [Phase 5: Code Quality Refactoring](#phase-5-code-quality-refactoring)
6. [Phase 6: Medium Priority Features](#phase-6-medium-priority-features)
7. [Phase 7: Performance & Accessibility](#phase-7-performance--accessibility)
8. [Testing Strategy](#testing-strategy)
9. [File Structure](#file-structure)

---

## Phase 1: Critical Bug Fixes

### 1.1 Fix Resize Handles (Bug #1)

**Location**: `frontend/src/components/DesignCanvas.tsx:850-900`

**Problem**: Selection handles are rendered but have no resize functionality.

**Implementation Steps**:

1. Create a new hook `useResize.ts`:
   ```typescript
   // frontend/src/hooks/useResize.ts
   interface ResizeState {
     isResizing: boolean;
     handle: 'nw' | 'ne' | 'sw' | 'se' | 'n' | 's' | 'e' | 'w' | null;
     startX: number;
     startY: number;
     startWidth: number;
     startHeight: number;
     startElementX: number;
     startElementY: number;
   }
   ```

2. Implement resize handle detection based on cursor position:
   - Define 8 handle positions (4 corners + 4 edges)
   - Each handle should be 8x8 pixels
   - Calculate handle bounds for hit testing

3. Implement resize logic:
   ```typescript
   const handleResize = (e: MouseEvent, element: CanvasElement, handle: string) => {
     const dx = e.clientX - startX;
     const dy = e.clientY - startY;

     switch(handle) {
       case 'se': // bottom-right
         return { width: startWidth + dx, height: startHeight + dy };
       case 'nw': // top-left
         return {
           x: startElementX + dx,
           y: startElementY + dy,
           width: startWidth - dx,
           height: startHeight - dy
         };
       // ... handle all 8 cases
     }
   };
   ```

4. Add minimum size constraints (e.g., 20x20 pixels)

5. Update cursor styles based on handle hover:
   - `nw-resize`, `ne-resize`, `sw-resize`, `se-resize` for corners
   - `n-resize`, `s-resize`, `e-resize`, `w-resize` for edges

**Tests Required**:
```typescript
// frontend/src/hooks/__tests__/useResize.test.ts
describe('useResize', () => {
  it('should initialize with isResizing false', () => {});
  it('should detect correct handle on mouse position', () => {});
  it('should resize from SE handle correctly', () => {});
  it('should resize from NW handle correctly (moves origin)', () => {});
  it('should resize from N handle (vertical only)', () => {});
  it('should resize from E handle (horizontal only)', () => {});
  it('should enforce minimum size constraints', () => {});
  it('should maintain aspect ratio when shift is held', () => {});
  it('should update cursor style on handle hover', () => {});
  it('should reset state on mouse up', () => {});
});
```

---

### 1.2 Fix Arrow Endpoint Editing (Bug #2)

**Location**: `frontend/src/components/DesignCanvas.tsx:680-720`

**Problem**: Arrow endpoints cannot be adjusted after creation.

**Implementation Steps**:

1. Modify arrow selection to show endpoint handles:
   ```typescript
   interface ArrowElement extends BaseElement {
     type: 'arrow';
     startX: number;
     startY: number;
     endX: number;
     endY: number;
   }
   ```

2. Render endpoint handles when arrow is selected:
   - Circle handle at start point (radius: 6px)
   - Circle handle at end point (radius: 6px)

3. Implement endpoint drag detection:
   ```typescript
   const getArrowHandle = (x: number, y: number, arrow: ArrowElement) => {
     const startDist = Math.hypot(x - arrow.startX, y - arrow.startY);
     const endDist = Math.hypot(x - arrow.endX, y - arrow.endY);

     if (startDist < 8) return 'start';
     if (endDist < 8) return 'end';
     return null;
   };
   ```

4. Update arrow coordinates on endpoint drag

5. Add visual feedback (highlight handle on hover)

**Tests Required**:
```typescript
// frontend/src/components/__tests__/ArrowEditor.test.tsx
describe('ArrowEditor', () => {
  it('should render endpoint handles when arrow selected', () => {});
  it('should detect start handle click', () => {});
  it('should detect end handle click', () => {});
  it('should update startX/startY on start handle drag', () => {});
  it('should update endX/endY on end handle drag', () => {});
  it('should highlight handle on hover', () => {});
  it('should not move arrow body when dragging endpoint', () => {});
});
```

---

### 1.3 Fix Text Position on Long Text (Bug #3)

**Location**: `frontend/src/components/DesignCanvas.tsx:520-560`

**Problem**: Text wrapping causes position misalignment.

**Implementation Steps**:

1. Create a text measurement utility:
   ```typescript
   // frontend/src/utils/textMeasure.ts
   export const measureText = (
     text: string,
     fontSize: number,
     fontFamily: string,
     maxWidth?: number
   ): { width: number; height: number; lines: string[] } => {
     const canvas = document.createElement('canvas');
     const ctx = canvas.getContext('2d')!;
     ctx.font = `${fontSize}px ${fontFamily}`;
     // Calculate wrapped lines and dimensions
   };
   ```

2. Update text element to store computed dimensions:
   ```typescript
   interface TextElement extends BaseElement {
     type: 'text';
     text: string;
     fontSize: number;
     fontFamily: string;
     computedWidth?: number;
     computedHeight?: number;
   }
   ```

3. Modify textarea overlay positioning:
   - Position based on SVG coordinates
   - Match font size and family exactly
   - Apply same line-height

4. Handle text wrapping in both render and edit modes:
   ```typescript
   const renderTextWithWrapping = (element: TextElement, maxWidth: number) => {
     const lines = wrapText(element.text, maxWidth, element.fontSize);
     return lines.map((line, i) => (
       <tspan key={i} x={element.x} dy={i === 0 ? 0 : element.fontSize * 1.2}>
         {line}
       </tspan>
     ));
   };
   ```

**Tests Required**:
```typescript
// frontend/src/utils/__tests__/textMeasure.test.ts
describe('measureText', () => {
  it('should measure single line text width', () => {});
  it('should calculate height for single line', () => {});
  it('should wrap text at maxWidth', () => {});
  it('should return multiple lines for long text', () => {});
  it('should handle empty string', () => {});
  it('should handle special characters', () => {});
});

// frontend/src/components/__tests__/TextEditor.test.tsx
describe('TextEditor', () => {
  it('should position textarea at element coordinates', () => {});
  it('should match font size with element', () => {});
  it('should update element on text change', () => {});
  it('should maintain position during editing', () => {});
  it('should wrap text in SVG render', () => {});
});
```

---

### 1.4 Fix Undo/Redo Element Restoration (Bug #4)

**Location**: `frontend/src/components/DesignCanvas.tsx:180-220`

**Problem**: Undo after delete can cause ID conflicts.

**Implementation Steps**:

1. Refactor history to use immutable state snapshots:
   ```typescript
   // frontend/src/hooks/useCanvasHistory.ts
   interface HistoryState {
     elements: Map<string, CanvasElement>;
     selectedIds: Set<string>;
     timestamp: number;
   }

   interface UseCanvasHistory {
     past: HistoryState[];
     present: HistoryState;
     future: HistoryState[];
     canUndo: boolean;
     canRedo: boolean;
     undo: () => void;
     redo: () => void;
     pushState: (state: HistoryState) => void;
   }
   ```

2. Store complete snapshots instead of diffs (simpler, more reliable):
   - Deep clone elements on each state change
   - Limit history to 50 entries to manage memory

3. Ensure element IDs are preserved exactly:
   ```typescript
   const undo = () => {
     if (past.length === 0) return;

     const previous = past[past.length - 1];
     const newPast = past.slice(0, -1);

     setFuture([present, ...future]);
     setPresent(previous);
     setPast(newPast);
   };
   ```

4. Add debouncing to prevent too many history entries:
   - Group rapid changes (within 500ms) into single entry

**Tests Required**:
```typescript
// frontend/src/hooks/__tests__/useCanvasHistory.test.ts
describe('useCanvasHistory', () => {
  it('should initialize with empty past and future', () => {});
  it('should push state to history on change', () => {});
  it('should undo to previous state', () => {});
  it('should redo to next state', () => {});
  it('should clear future on new action after undo', () => {});
  it('should preserve element IDs on undo', () => {});
  it('should restore deleted elements with same ID', () => {});
  it('should limit history to 50 entries', () => {});
  it('should debounce rapid changes', () => {});
  it('should report canUndo correctly', () => {});
  it('should report canRedo correctly', () => {});
});
```

---

### 1.5 Fix JSON Import Validation (Bug #5)

**Location**: `frontend/src/lib/canvasExport.ts:280-320`

**Problem**: Invalid JSON import crashes the application.

**Implementation Steps**:

1. Create a schema validation module:
   ```typescript
   // frontend/src/lib/canvasSchema.ts
   import { z } from 'zod';

   const BaseElementSchema = z.object({
     id: z.string().uuid(),
     type: z.enum(['rectangle', 'ellipse', 'arrow', 'text', 'icon', 'image']),
     x: z.number(),
     y: z.number(),
     strokeColor: z.string().regex(/^#[0-9a-fA-F]{6}$/),
     fillColor: z.string().regex(/^#[0-9a-fA-F]{6}$/).optional(),
   });

   const RectangleSchema = BaseElementSchema.extend({
     type: z.literal('rectangle'),
     width: z.number().positive(),
     height: z.number().positive(),
   });

   // ... schemas for each element type

   const CanvasSchema = z.object({
     version: z.string(),
     elements: z.array(z.union([
       RectangleSchema,
       EllipseSchema,
       ArrowSchema,
       TextSchema,
       IconSchema,
       ImageSchema,
     ])),
     metadata: z.object({
       createdAt: z.string().datetime(),
       exportedAt: z.string().datetime(),
     }).optional(),
   });
   ```

2. Implement import validation:
   ```typescript
   // frontend/src/lib/canvasExport.ts
   export const importCanvas = (jsonString: string): ImportResult => {
     try {
       const data = JSON.parse(jsonString);
       const result = CanvasSchema.safeParse(data);

       if (!result.success) {
         return {
           success: false,
           error: formatZodError(result.error),
         };
       }

       return {
         success: true,
         elements: result.data.elements,
       };
     } catch (e) {
       return {
         success: false,
         error: 'Invalid JSON format',
       };
     }
   };
   ```

3. Add user-friendly error messages:
   - Specify which field failed validation
   - Suggest corrections for common issues

4. Add version migration for older exports:
   ```typescript
   const migrateSchema = (data: unknown, fromVersion: string): CanvasData => {
     // Handle schema changes between versions
   };
   ```

**Tests Required**:
```typescript
// frontend/src/lib/__tests__/canvasSchema.test.ts
describe('canvasSchema', () => {
  it('should validate valid rectangle element', () => {});
  it('should validate valid ellipse element', () => {});
  it('should validate valid arrow element', () => {});
  it('should validate valid text element', () => {});
  it('should validate valid icon element', () => {});
  it('should validate valid image element', () => {});
  it('should reject element with missing id', () => {});
  it('should reject element with invalid type', () => {});
  it('should reject negative dimensions', () => {});
  it('should reject invalid color format', () => {});
  it('should validate complete canvas export', () => {});
});

// frontend/src/lib/__tests__/canvasExport.test.ts
describe('importCanvas', () => {
  it('should import valid JSON', () => {});
  it('should reject malformed JSON', () => {});
  it('should reject invalid schema', () => {});
  it('should return detailed error messages', () => {});
  it('should migrate old schema versions', () => {});
  it('should handle empty elements array', () => {});
});
```

---

## Phase 2: Medium Bug Fixes

### 2.1 Fix Double-Click Text Edit Inconsistency (Bug #6)

**Location**: `frontend/src/components/DesignCanvas.tsx:490-510`

**Problem**: Race condition between selection and edit mode.

**Implementation Steps**:

1. Implement proper click vs double-click detection:
   ```typescript
   // frontend/src/hooks/useClickDetection.ts
   const useClickDetection = (
     onClick: (e: MouseEvent) => void,
     onDoubleClick: (e: MouseEvent) => void,
     delay = 250
   ) => {
     const clickTimeout = useRef<NodeJS.Timeout | null>(null);
     const clickCount = useRef(0);

     const handleClick = (e: MouseEvent) => {
       clickCount.current++;

       if (clickCount.current === 1) {
         clickTimeout.current = setTimeout(() => {
           if (clickCount.current === 1) {
             onClick(e);
           }
           clickCount.current = 0;
         }, delay);
       } else if (clickCount.current === 2) {
         clearTimeout(clickTimeout.current!);
         clickCount.current = 0;
         onDoubleClick(e);
       }
     };

     return handleClick;
   };
   ```

2. Separate selection state from edit state:
   ```typescript
   const [selectedId, setSelectedId] = useState<string | null>(null);
   const [editingId, setEditingId] = useState<string | null>(null);
   ```

3. Only enter edit mode on confirmed double-click of already-selected element

**Tests Required**:
```typescript
// frontend/src/hooks/__tests__/useClickDetection.test.ts
describe('useClickDetection', () => {
  it('should call onClick for single click after delay', () => {});
  it('should call onDoubleClick for rapid double click', () => {});
  it('should not call onClick when double click detected', () => {});
  it('should handle triple click as double + single', () => {});
  it('should respect custom delay', () => {});
});
```

---

### 2.2 Fix Color Picker Outside Click (Bug #7)

**Location**: `frontend/src/components/DesignCanvas.tsx:300-340`

**Problem**: Color picker doesn't close on outside click.

**Implementation Steps**:

1. Create a reusable click-outside hook:
   ```typescript
   // frontend/src/hooks/useClickOutside.ts
   export const useClickOutside = (
     ref: RefObject<HTMLElement>,
     callback: () => void
   ) => {
     useEffect(() => {
       const handleClick = (e: MouseEvent) => {
         if (ref.current && !ref.current.contains(e.target as Node)) {
           callback();
         }
       };

       document.addEventListener('mousedown', handleClick);
       return () => document.removeEventListener('mousedown', handleClick);
     }, [ref, callback]);
   };
   ```

2. Wrap color picker in a component with outside click detection:
   ```typescript
   const ColorPicker: FC<ColorPickerProps> = ({ isOpen, onClose, onSelect }) => {
     const ref = useRef<HTMLDivElement>(null);
     useClickOutside(ref, onClose);

     if (!isOpen) return null;

     return (
       <div ref={ref} className="color-picker">
         {/* color options */}
       </div>
     );
   };
   ```

3. Close picker on Escape key as well

**Tests Required**:
```typescript
// frontend/src/hooks/__tests__/useClickOutside.test.ts
describe('useClickOutside', () => {
  it('should call callback on outside click', () => {});
  it('should not call callback on inside click', () => {});
  it('should clean up listener on unmount', () => {});
});

// frontend/src/components/__tests__/ColorPicker.test.tsx
describe('ColorPicker', () => {
  it('should render when isOpen is true', () => {});
  it('should not render when isOpen is false', () => {});
  it('should call onClose on outside click', () => {});
  it('should call onSelect when color clicked', () => {});
  it('should close on Escape key', () => {});
});
```

---

### 2.3 Fix PNG/JPG Export Background (Bug #8)

**Location**: `frontend/src/lib/canvasExport.ts:50-100`

**Problem**: Raster exports don't preserve transparency option.

**Implementation Steps**:

1. Add export options interface:
   ```typescript
   interface ExportOptions {
     format: 'png' | 'jpg' | 'svg' | 'json';
     transparent: boolean;
     backgroundColor?: string;
     scale: number;
   }
   ```

2. Modify canvas creation for raster export:
   ```typescript
   export const exportAsRaster = async (
     svgElement: SVGElement,
     options: ExportOptions
   ): Promise<Blob> => {
     const canvas = document.createElement('canvas');
     const ctx = canvas.getContext('2d')!;

     // Set dimensions with scale
     canvas.width = svgElement.clientWidth * options.scale;
     canvas.height = svgElement.clientHeight * options.scale;

     // Handle background
     if (!options.transparent || options.format === 'jpg') {
       ctx.fillStyle = options.backgroundColor || '#ffffff';
       ctx.fillRect(0, 0, canvas.width, canvas.height);
     }

     // Draw SVG to canvas
     const svgData = new XMLSerializer().serializeToString(svgElement);
     const img = new Image();
     img.src = 'data:image/svg+xml;base64,' + btoa(svgData);

     await new Promise(resolve => img.onload = resolve);
     ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

     return new Promise(resolve => {
       canvas.toBlob(resolve, `image/${options.format}`);
     });
   };
   ```

3. Add export options UI:
   - Checkbox for transparent background (PNG only)
   - Color picker for background color
   - Scale selector (1x, 2x, 3x)

**Tests Required**:
```typescript
// frontend/src/lib/__tests__/canvasExport.test.ts
describe('exportAsRaster', () => {
  it('should export PNG with transparent background', () => {});
  it('should export PNG with custom background', () => {});
  it('should export JPG with white background (no transparency)', () => {});
  it('should scale export by specified factor', () => {});
  it('should preserve element colors', () => {});
});
```

---

### 2.4 Fix Arrow Heads Scaling (Bug #9)

**Location**: `frontend/src/components/DesignCanvas.tsx:750-780`

**Problem**: Arrow marker uses fixed size.

**Implementation Steps**:

1. Calculate arrow head size based on line length or zoom:
   ```typescript
   const getArrowHeadSize = (
     startX: number, startY: number,
     endX: number, endY: number,
     zoom: number = 1
   ): number => {
     const length = Math.hypot(endX - startX, endY - startY);
     const baseSize = 10;
     const scaleFactor = Math.min(1, length / 50);
     return baseSize * scaleFactor * zoom;
   };
   ```

2. Create dynamic marker definitions:
   ```typescript
   const ArrowMarker: FC<{ id: string; size: number; color: string }> = ({
     id, size, color
   }) => (
     <marker
       id={id}
       markerWidth={size}
       markerHeight={size}
       refX={size - 1}
       refY={size / 2}
       orient="auto"
     >
       <polygon
         points={`0,0 ${size},${size/2} 0,${size}`}
         fill={color}
       />
     </marker>
   );
   ```

3. Generate unique marker ID per arrow to support different sizes/colors

**Tests Required**:
```typescript
// frontend/src/components/__tests__/ArrowMarker.test.tsx
describe('ArrowMarker', () => {
  it('should render marker with correct size', () => {});
  it('should use specified color', () => {});
  it('should scale with zoom level', () => {});
  it('should scale with arrow length', () => {});
});
```

---

### 2.5 Add Grid Snap Functionality (Bug #10)

**Location**: `frontend/src/components/DesignCanvas.tsx:920-960`

**Problem**: Grid is visual only, no snap functionality.

**Implementation Steps**:

1. Create snap utility:
   ```typescript
   // frontend/src/utils/snap.ts
   export const snapToGrid = (
     value: number,
     gridSize: number,
     enabled: boolean
   ): number => {
     if (!enabled) return value;
     return Math.round(value / gridSize) * gridSize;
   };

   export const snapPoint = (
     x: number, y: number,
     gridSize: number,
     enabled: boolean
   ): { x: number; y: number } => ({
     x: snapToGrid(x, gridSize, enabled),
     y: snapToGrid(y, gridSize, enabled),
   });
   ```

2. Add snap toggle to toolbar:
   ```typescript
   const [snapEnabled, setSnapEnabled] = useState(true);
   ```

3. Apply snap during:
   - Element creation
   - Element dragging
   - Element resizing

4. Show snap indicator when element snaps to grid

**Tests Required**:
```typescript
// frontend/src/utils/__tests__/snap.test.ts
describe('snapToGrid', () => {
  it('should snap value to nearest grid point', () => {});
  it('should round up when closer to next grid point', () => {});
  it('should round down when closer to previous grid point', () => {});
  it('should return original value when disabled', () => {});
  it('should handle negative values', () => {});
  it('should handle zero', () => {});
});

describe('snapPoint', () => {
  it('should snap both x and y', () => {});
  it('should maintain independent snap for each axis', () => {});
});
```

---

## Phase 3: Minor Bug Fixes

### 3.1 Add Resize Cursor Hints (Bug #11)

**Implementation Steps**:

1. Add cursor styles to selection handles:
   ```typescript
   const getHandleCursor = (position: HandlePosition): string => {
     const cursors: Record<HandlePosition, string> = {
       nw: 'nw-resize',
       ne: 'ne-resize',
       sw: 'sw-resize',
       se: 'se-resize',
       n: 'n-resize',
       s: 's-resize',
       e: 'e-resize',
       w: 'w-resize',
     };
     return cursors[position];
   };
   ```

2. Apply cursor on handle hover

**Tests**: Covered by resize handle tests.

---

### 3.2 Add Keyboard Shortcuts Documentation (Bug #12)

**Implementation Steps**:

1. Create keyboard shortcuts modal:
   ```typescript
   // frontend/src/components/KeyboardShortcutsModal.tsx
   const shortcuts = [
     { key: 'Delete', action: 'Delete selected element' },
     { key: 'Ctrl+Z', action: 'Undo' },
     { key: 'Ctrl+Y', action: 'Redo' },
     { key: 'Ctrl+C', action: 'Copy' },
     { key: 'Ctrl+V', action: 'Paste' },
     { key: 'Escape', action: 'Deselect / Cancel' },
     { key: '?', action: 'Show keyboard shortcuts' },
   ];
   ```

2. Add `?` key handler to show modal

3. Add help icon button in toolbar

**Tests Required**:
```typescript
describe('KeyboardShortcutsModal', () => {
  it('should render all shortcuts', () => {});
  it('should open on ? key press', () => {});
  it('should close on Escape', () => {});
  it('should close on outside click', () => {});
});
```

---

### 3.3 Fix SVG Export Image Embedding (Bug #13)

**Location**: `frontend/src/lib/canvasExport.ts:150-200`

**Implementation Steps**:

1. Convert image URLs to data URIs for export:
   ```typescript
   const embedImages = async (svgElement: SVGElement): Promise<string> => {
     const images = svgElement.querySelectorAll('image');

     for (const img of images) {
       const href = img.getAttribute('href');
       if (href && !href.startsWith('data:')) {
         const dataUri = await fetchAsDataUri(href);
         img.setAttribute('href', dataUri);
       }
     }

     return new XMLSerializer().serializeToString(svgElement);
   };

   const fetchAsDataUri = async (url: string): Promise<string> => {
     const response = await fetch(url);
     const blob = await response.blob();
     return new Promise(resolve => {
       const reader = new FileReader();
       reader.onloadend = () => resolve(reader.result as string);
       reader.readAsDataURL(blob);
     });
   };
   ```

**Tests Required**:
```typescript
describe('embedImages', () => {
  it('should convert image URLs to data URIs', () => {});
  it('should leave data URIs unchanged', () => {});
  it('should handle multiple images', () => {});
  it('should handle missing images gracefully', () => {});
});
```

---

## Phase 4: High Priority UX Features

### 4.1 Implement Zoom/Pan (UX #1, #2)

**Implementation Steps**:

1. Create zoom/pan hook:
   ```typescript
   // frontend/src/hooks/useZoomPan.ts
   interface ZoomPanState {
     scale: number;
     translateX: number;
     translateY: number;
   }

   export const useZoomPan = (minScale = 0.1, maxScale = 4) => {
     const [state, setState] = useState<ZoomPanState>({
       scale: 1,
       translateX: 0,
       translateY: 0,
     });

     const handleWheel = (e: WheelEvent) => {
       if (e.ctrlKey) {
         e.preventDefault();
         const delta = e.deltaY > 0 ? 0.9 : 1.1;
         const newScale = Math.max(minScale, Math.min(maxScale, state.scale * delta));

         // Zoom toward cursor position
         const rect = (e.target as Element).getBoundingClientRect();
         const x = e.clientX - rect.left;
         const y = e.clientY - rect.top;

         setState(prev => ({
           scale: newScale,
           translateX: x - (x - prev.translateX) * (newScale / prev.scale),
           translateY: y - (y - prev.translateY) * (newScale / prev.scale),
         }));
       }
     };

     const handlePan = (dx: number, dy: number) => {
       setState(prev => ({
         ...prev,
         translateX: prev.translateX + dx,
         translateY: prev.translateY + dy,
       }));
     };

     const resetView = () => setState({ scale: 1, translateX: 0, translateY: 0 });
     const zoomIn = () => { /* ... */ };
     const zoomOut = () => { /* ... */ };
     const fitToContent = (elements: CanvasElement[]) => { /* ... */ };

     return { state, handleWheel, handlePan, resetView, zoomIn, zoomOut, fitToContent };
   };
   ```

2. Apply transform to SVG viewBox or group:
   ```tsx
   <svg viewBox={`${-translateX/scale} ${-translateY/scale} ${width/scale} ${height/scale}`}>
     <g transform={`scale(${scale}) translate(${translateX}, ${translateY})`}>
       {/* elements */}
     </g>
   </svg>
   ```

3. Add zoom controls UI:
   - Zoom in/out buttons
   - Zoom percentage display
   - Fit to content button
   - Reset view button

4. Implement middle-mouse-button or space+drag for panning

5. Transform mouse coordinates for element interaction:
   ```typescript
   const screenToCanvas = (screenX: number, screenY: number) => ({
     x: (screenX - translateX) / scale,
     y: (screenY - translateY) / scale,
   });
   ```

**Tests Required**:
```typescript
// frontend/src/hooks/__tests__/useZoomPan.test.ts
describe('useZoomPan', () => {
  it('should initialize at scale 1, translate 0,0', () => {});
  it('should zoom in on ctrl+wheel up', () => {});
  it('should zoom out on ctrl+wheel down', () => {});
  it('should zoom toward cursor position', () => {});
  it('should enforce minimum scale', () => {});
  it('should enforce maximum scale', () => {});
  it('should pan on middle mouse drag', () => {});
  it('should pan on space+drag', () => {});
  it('should reset view correctly', () => {});
  it('should fit to content bounds', () => {});
  it('should convert screen to canvas coordinates', () => {});
  it('should convert canvas to screen coordinates', () => {});
});
```

---

### 4.2 Implement Multi-Select (UX #5, #6)

**Implementation Steps**:

1. Change selection state to support multiple:
   ```typescript
   const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
   ```

2. Implement shift+click to add to selection:
   ```typescript
   const handleElementClick = (id: string, e: MouseEvent) => {
     if (e.shiftKey) {
       setSelectedIds(prev => {
         const next = new Set(prev);
         if (next.has(id)) next.delete(id);
         else next.add(id);
         return next;
       });
     } else {
       setSelectedIds(new Set([id]));
     }
   };
   ```

3. Implement marquee (box) selection:
   ```typescript
   // frontend/src/hooks/useMarqueeSelection.ts
   interface MarqueeState {
     isSelecting: boolean;
     startX: number;
     startY: number;
     endX: number;
     endY: number;
   }

   const getElementsInBounds = (
     elements: CanvasElement[],
     bounds: { x1: number; y1: number; x2: number; y2: number }
   ): string[] => {
     return elements
       .filter(el => isElementInBounds(el, bounds))
       .map(el => el.id);
   };
   ```

4. Render selection rectangle during marquee drag

5. Move/delete all selected elements together

**Tests Required**:
```typescript
// frontend/src/hooks/__tests__/useMarqueeSelection.test.ts
describe('useMarqueeSelection', () => {
  it('should start selection on mouse down', () => {});
  it('should update bounds on mouse move', () => {});
  it('should select elements in bounds on mouse up', () => {});
  it('should add to selection with shift key', () => {});
  it('should render selection rectangle', () => {});
});

describe('multi-select behavior', () => {
  it('should add to selection with shift+click', () => {});
  it('should toggle element with shift+click on selected', () => {});
  it('should clear selection on click without shift', () => {});
  it('should move all selected elements together', () => {});
  it('should delete all selected elements', () => {});
  it('should apply color change to all selected', () => {});
});
```

---

### 4.3 Implement Copy/Paste (UX #7)

**Implementation Steps**:

1. Create clipboard handler:
   ```typescript
   // frontend/src/hooks/useCanvasClipboard.ts
   interface ClipboardData {
     elements: CanvasElement[];
     bounds: { x: number; y: number; width: number; height: number };
   }

   export const useCanvasClipboard = () => {
     const [clipboard, setClipboard] = useState<ClipboardData | null>(null);

     const copy = (elements: CanvasElement[]) => {
       const bounds = calculateBounds(elements);
       setClipboard({ elements: cloneDeep(elements), bounds });

       // Also copy to system clipboard as JSON
       navigator.clipboard.writeText(JSON.stringify({ elements, bounds }));
     };

     const paste = (offsetX = 20, offsetY = 20): CanvasElement[] => {
       if (!clipboard) return [];

       return clipboard.elements.map(el => ({
         ...el,
         id: generateId(),
         x: el.x - clipboard.bounds.x + offsetX,
         y: el.y - clipboard.bounds.y + offsetY,
       }));
     };

     const cut = (elements: CanvasElement[]) => {
       copy(elements);
       // Return IDs to delete
       return elements.map(el => el.id);
     };

     return { copy, paste, cut, hasClipboard: clipboard !== null };
   };
   ```

2. Add keyboard handlers:
   ```typescript
   useEffect(() => {
     const handleKeyDown = (e: KeyboardEvent) => {
       if (e.ctrlKey || e.metaKey) {
         switch (e.key) {
           case 'c':
             e.preventDefault();
             copy(getSelectedElements());
             break;
           case 'v':
             e.preventDefault();
             const newElements = paste();
             addElements(newElements);
             setSelectedIds(new Set(newElements.map(e => e.id)));
             break;
           case 'x':
             e.preventDefault();
             const idsToDelete = cut(getSelectedElements());
             deleteElements(idsToDelete);
             break;
         }
       }
     };

     window.addEventListener('keydown', handleKeyDown);
     return () => window.removeEventListener('keydown', handleKeyDown);
   }, [selectedIds]);
   ```

3. Support paste from system clipboard (if valid canvas JSON)

**Tests Required**:
```typescript
// frontend/src/hooks/__tests__/useCanvasClipboard.test.ts
describe('useCanvasClipboard', () => {
  it('should copy selected elements', () => {});
  it('should paste with offset', () => {});
  it('should generate new IDs on paste', () => {});
  it('should cut elements (copy + delete)', () => {});
  it('should paste at cursor position', () => {});
  it('should copy to system clipboard as JSON', () => {});
  it('should paste from system clipboard if valid', () => {});
  it('should maintain relative positions on paste', () => {});
});
```

---

### 4.4 Implement Element Connectors (UX #11)

**Implementation Steps**:

1. Add connection points to shapes:
   ```typescript
   // frontend/src/utils/connectionPoints.ts
   interface ConnectionPoint {
     id: string;
     position: 'top' | 'right' | 'bottom' | 'left' | 'center';
     x: number;
     y: number;
   }

   const getConnectionPoints = (element: CanvasElement): ConnectionPoint[] => {
     const { x, y, width, height } = element;
     return [
       { id: `${element.id}-top`, position: 'top', x: x + width/2, y },
       { id: `${element.id}-right`, position: 'right', x: x + width, y: y + height/2 },
       { id: `${element.id}-bottom`, position: 'bottom', x: x + width/2, y: y + height },
       { id: `${element.id}-left`, position: 'left', x: x, y: y + height/2 },
     ];
   };
   ```

2. Modify arrow element to support connections:
   ```typescript
   interface ConnectedArrow extends ArrowElement {
     startConnection?: {
       elementId: string;
       point: 'top' | 'right' | 'bottom' | 'left';
     };
     endConnection?: {
       elementId: string;
       point: 'top' | 'right' | 'bottom' | 'left';
     };
   }
   ```

3. Show connection points when drawing arrow near shape:
   - Highlight available connection points
   - Snap to connection point within 15px

4. Update arrow position when connected element moves:
   ```typescript
   const updateConnectedArrows = (
     arrows: ConnectedArrow[],
     movedElement: CanvasElement
   ): ConnectedArrow[] => {
     return arrows.map(arrow => {
       let updated = { ...arrow };

       if (arrow.startConnection?.elementId === movedElement.id) {
         const point = getConnectionPoint(movedElement, arrow.startConnection.point);
         updated = { ...updated, startX: point.x, startY: point.y };
       }

       if (arrow.endConnection?.elementId === movedElement.id) {
         const point = getConnectionPoint(movedElement, arrow.endConnection.point);
         updated = { ...updated, endX: point.x, endY: point.y };
       }

       return updated;
     });
   };
   ```

5. Visual feedback:
   - Show connection points on hover
   - Highlight active connection
   - Show "connected" indicator on arrow

**Tests Required**:
```typescript
// frontend/src/utils/__tests__/connectionPoints.test.ts
describe('connectionPoints', () => {
  it('should return 4 connection points for rectangle', () => {});
  it('should calculate correct positions', () => {});
  it('should update points when element resizes', () => {});
});

// frontend/src/components/__tests__/ConnectedArrow.test.tsx
describe('ConnectedArrow', () => {
  it('should render arrow between connected elements', () => {});
  it('should update when start element moves', () => {});
  it('should update when end element moves', () => {});
  it('should snap to connection point when near', () => {});
  it('should show connection points on hover', () => {});
  it('should disconnect when dragging endpoint away', () => {});
});
```

---

### 4.5 Implement Infinite Canvas (UX #3)

**Implementation Steps**:

1. Remove fixed canvas dimensions:
   ```typescript
   // Remove: style={{ height: 500 }}
   // Instead, use viewport-based sizing with dynamic viewBox
   ```

2. Calculate canvas bounds from elements:
   ```typescript
   const getCanvasBounds = (elements: CanvasElement[], padding = 100) => {
     if (elements.length === 0) {
       return { minX: 0, minY: 0, maxX: 800, maxY: 600 };
     }

     let minX = Infinity, minY = Infinity;
     let maxX = -Infinity, maxY = -Infinity;

     elements.forEach(el => {
       minX = Math.min(minX, el.x);
       minY = Math.min(minY, el.y);
       maxX = Math.max(maxX, el.x + (el.width || 0));
       maxY = Math.max(maxY, el.y + (el.height || 0));
     });

     return {
       minX: minX - padding,
       minY: minY - padding,
       maxX: maxX + padding,
       maxY: maxY + padding,
     };
   };
   ```

3. Allow elements to be placed anywhere:
   - Remove boundary checks
   - Allow negative coordinates

4. Update viewBox dynamically:
   ```typescript
   const viewBox = `${bounds.minX} ${bounds.minY} ${bounds.maxX - bounds.minX} ${bounds.maxY - bounds.minY}`;
   ```

**Tests Required**:
```typescript
describe('infiniteCanvas', () => {
  it('should allow elements at negative coordinates', () => {});
  it('should expand bounds when element placed outside', () => {});
  it('should calculate correct viewBox from elements', () => {});
  it('should maintain padding around elements', () => {});
});
```

---

## Phase 5: Code Quality Refactoring

### 5.1 Split DesignCanvas Component (Problem #14)

**Implementation Steps**:

Create these component files:

1. **CanvasToolbar.tsx** (~200 lines)
   ```typescript
   // frontend/src/components/canvas/CanvasToolbar.tsx
   interface CanvasToolbarProps {
     activeTool: Tool;
     onToolChange: (tool: Tool) => void;
     strokeColor: string;
     fillColor: string;
     onStrokeColorChange: (color: string) => void;
     onFillColorChange: (color: string) => void;
     snapEnabled: boolean;
     onSnapToggle: () => void;
     onUndo: () => void;
     onRedo: () => void;
     canUndo: boolean;
     canRedo: boolean;
   }
   ```

2. **CanvasElement.tsx** (~150 lines)
   ```typescript
   // frontend/src/components/canvas/CanvasElement.tsx
   interface CanvasElementProps {
     element: Element;
     isSelected: boolean;
     onSelect: () => void;
     onDoubleClick: () => void;
   }

   // Renders rectangle, ellipse, text, icon, image based on type
   ```

3. **CanvasArrow.tsx** (~100 lines)
   ```typescript
   // frontend/src/components/canvas/CanvasArrow.tsx
   interface CanvasArrowProps {
     arrow: ArrowElement;
     isSelected: boolean;
     onSelect: () => void;
     onEndpointDrag: (handle: 'start' | 'end', x: number, y: number) => void;
   }
   ```

4. **CanvasGrid.tsx** (~50 lines)
   ```typescript
   // frontend/src/components/canvas/CanvasGrid.tsx
   interface CanvasGridProps {
     gridSize: number;
     width: number;
     height: number;
     visible: boolean;
   }
   ```

5. **SelectionHandles.tsx** (~100 lines)
   ```typescript
   // frontend/src/components/canvas/SelectionHandles.tsx
   interface SelectionHandlesProps {
     element: CanvasElement;
     onResize: (handle: HandlePosition, dx: number, dy: number) => void;
   }
   ```

6. **IconPalette.tsx** (~80 lines)
   ```typescript
   // frontend/src/components/canvas/IconPalette.tsx
   interface IconPaletteProps {
     icons: IconDefinition[];
     onSelect: (iconId: string) => void;
     selectedIcon?: string;
   }
   ```

7. **TextEditor.tsx** (~100 lines)
   ```typescript
   // frontend/src/components/canvas/TextEditor.tsx
   interface TextEditorProps {
     element: TextElement;
     position: { x: number; y: number };
     onSave: (text: string) => void;
     onCancel: () => void;
   }
   ```

8. **ExportMenu.tsx** (~80 lines)
   ```typescript
   // frontend/src/components/canvas/ExportMenu.tsx
   interface ExportMenuProps {
     onExport: (format: ExportFormat, options: ExportOptions) => void;
   }
   ```

---

### 5.2 Extract Custom Hooks (Problem #15)

Create these hook files:

1. **useCanvasHistory.ts** (from Phase 1.4)

2. **useCanvasDraw.ts** (~150 lines)
   ```typescript
   // frontend/src/hooks/useCanvasDraw.ts
   export const useCanvasDraw = () => {
     const [isDrawing, setIsDrawing] = useState(false);
     const [drawStart, setDrawStart] = useState<Point | null>(null);

     const startDraw = (point: Point) => { /* ... */ };
     const updateDraw = (point: Point) => { /* ... */ };
     const endDraw = () => { /* ... */ };

     return { isDrawing, startDraw, updateDraw, endDraw };
   };
   ```

3. **useCanvasSelection.ts** (~100 lines)
   ```typescript
   // frontend/src/hooks/useCanvasSelection.ts
   export const useCanvasSelection = () => {
     const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

     const select = (id: string, additive?: boolean) => { /* ... */ };
     const deselect = (id: string) => { /* ... */ };
     const clearSelection = () => { /* ... */ };
     const selectAll = () => { /* ... */ };

     return { selectedIds, select, deselect, clearSelection, selectAll };
   };
   ```

4. **useCanvasElements.ts** (~200 lines)
   ```typescript
   // frontend/src/hooks/useCanvasElements.ts
   export const useCanvasElements = (initialElements: CanvasElement[] = []) => {
     const [elements, setElements] = useState(initialElements);

     const addElement = (element: CanvasElement) => { /* ... */ };
     const updateElement = (id: string, updates: Partial<CanvasElement>) => { /* ... */ };
     const deleteElements = (ids: string[]) => { /* ... */ };
     const moveElements = (ids: string[], dx: number, dy: number) => { /* ... */ };

     return { elements, addElement, updateElement, deleteElements, moveElements };
   };
   ```

---

### 5.3 Add TypeScript Strict Types (Problem #16)

1. Enable strict mode in tsconfig:
   ```json
   {
     "compilerOptions": {
       "strict": true,
       "noImplicitAny": true,
       "strictNullChecks": true
     }
   }
   ```

2. Define element type union:
   ```typescript
   // frontend/src/types/canvas.ts
   type ElementType = 'rectangle' | 'ellipse' | 'arrow' | 'text' | 'icon' | 'image';

   interface BaseElement {
     id: string;
     type: ElementType;
     x: number;
     y: number;
     strokeColor: string;
     fillColor?: string;
   }

   interface RectangleElement extends BaseElement {
     type: 'rectangle';
     width: number;
     height: number;
   }

   interface EllipseElement extends BaseElement {
     type: 'ellipse';
     width: number;
     height: number;
   }

   interface ArrowElement extends BaseElement {
     type: 'arrow';
     endX: number;
     endY: number;
     startConnection?: ConnectionRef;
     endConnection?: ConnectionRef;
   }

   interface TextElement extends BaseElement {
     type: 'text';
     text: string;
     fontSize: number;
     fontFamily: string;
   }

   interface IconElement extends BaseElement {
     type: 'icon';
     iconId: string;
     width: number;
     height: number;
   }

   interface ImageElement extends BaseElement {
     type: 'image';
     src: string;
     width: number;
     height: number;
   }

   type CanvasElement =
     | RectangleElement
     | EllipseElement
     | ArrowElement
     | TextElement
     | IconElement
     | ImageElement;
   ```

---

### 5.4 Extract Magic Numbers (Problem #17)

Create configuration file:
```typescript
// frontend/src/config/canvas.ts
export const CANVAS_CONFIG = {
  // Grid
  GRID_SIZE: 20,
  GRID_COLOR: '#e5e5e5',

  // Selection
  HANDLE_SIZE: 8,
  HANDLE_COLOR: '#2196F3',
  SELECTION_STROKE: '#2196F3',
  SELECTION_STROKE_WIDTH: 1,

  // Snap
  SNAP_THRESHOLD: 8,

  // Zoom
  MIN_ZOOM: 0.1,
  MAX_ZOOM: 4,
  ZOOM_STEP: 0.1,

  // Arrow
  ARROW_HEAD_SIZE: 10,
  CONNECTION_SNAP_DISTANCE: 15,

  // Text
  DEFAULT_FONT_SIZE: 16,
  DEFAULT_FONT_FAMILY: 'Inter, sans-serif',

  // History
  MAX_HISTORY_LENGTH: 50,
  HISTORY_DEBOUNCE_MS: 500,

  // Colors
  DEFAULT_STROKE_COLOR: '#000000',
  DEFAULT_FILL_COLOR: '#ffffff',

  // Sizes
  MIN_ELEMENT_SIZE: 20,
  DEFAULT_ELEMENT_WIDTH: 100,
  DEFAULT_ELEMENT_HEIGHT: 60,
} as const;
```

---

## Phase 6: Medium Priority Features

### 6.1 Z-Order Controls (UX #19)

**Implementation Steps**:

1. Add z-index to elements:
   ```typescript
   interface BaseElement {
     // ... existing fields
     zIndex: number;
   }
   ```

2. Implement ordering functions:
   ```typescript
   // frontend/src/utils/zOrder.ts
   export const bringToFront = (elements: CanvasElement[], ids: string[]): CanvasElement[] => {
     const maxZ = Math.max(...elements.map(e => e.zIndex));
     return elements.map(el =>
       ids.includes(el.id) ? { ...el, zIndex: maxZ + 1 } : el
     );
   };

   export const sendToBack = (elements: CanvasElement[], ids: string[]): CanvasElement[] => {
     const minZ = Math.min(...elements.map(e => e.zIndex));
     return elements.map(el =>
       ids.includes(el.id) ? { ...el, zIndex: minZ - 1 } : el
     );
   };

   export const bringForward = (elements: CanvasElement[], ids: string[]): CanvasElement[] => {
     // Swap with next element in z-order
   };

   export const sendBackward = (elements: CanvasElement[], ids: string[]): CanvasElement[] => {
     // Swap with previous element in z-order
   };
   ```

3. Sort elements by zIndex for rendering

4. Add context menu with z-order options

**Tests Required**:
```typescript
describe('zOrder', () => {
  it('should bring element to front', () => {});
  it('should send element to back', () => {});
  it('should bring forward by one', () => {});
  it('should send backward by one', () => {});
  it('should handle multiple selected elements', () => {});
});
```

---

### 6.2 Element Grouping (UX #20)

**Implementation Steps**:

1. Add group element type:
   ```typescript
   interface GroupElement extends BaseElement {
     type: 'group';
     childIds: string[];
   }
   ```

2. Implement grouping functions:
   ```typescript
   // frontend/src/utils/grouping.ts
   export const createGroup = (elements: CanvasElement[]): GroupElement => {
     const bounds = calculateBounds(elements);
     return {
       id: generateId(),
       type: 'group',
       x: bounds.x,
       y: bounds.y,
       width: bounds.width,
       height: bounds.height,
       childIds: elements.map(e => e.id),
       strokeColor: 'transparent',
     };
   };

   export const ungroup = (group: GroupElement, elements: CanvasElement[]): CanvasElement[] => {
     // Remove group and return children as independent elements
   };
   ```

3. Transform all children when group moves/resizes

4. Add Ctrl+G to group, Ctrl+Shift+G to ungroup

**Tests Required**:
```typescript
describe('grouping', () => {
  it('should create group from selected elements', () => {});
  it('should calculate group bounds from children', () => {});
  it('should move all children when group moves', () => {});
  it('should resize all children proportionally', () => {});
  it('should ungroup and preserve child positions', () => {});
  it('should support nested groups', () => {});
});
```

---

### 6.3 Additional Shapes (UX #14)

**Implementation Steps**:

1. Add shape types:
   ```typescript
   type ShapeType = 'rectangle' | 'ellipse' | 'diamond' | 'cylinder' | 'hexagon' | 'parallelogram';
   ```

2. Create shape path generators:
   ```typescript
   // frontend/src/utils/shapePaths.ts
   export const getShapePath = (type: ShapeType, x: number, y: number, width: number, height: number): string => {
     switch (type) {
       case 'diamond':
         return `M ${x + width/2} ${y} L ${x + width} ${y + height/2} L ${x + width/2} ${y + height} L ${x} ${y + height/2} Z`;

       case 'cylinder':
         const ry = height * 0.15;
         return `
           M ${x} ${y + ry}
           A ${width/2} ${ry} 0 0 1 ${x + width} ${y + ry}
           V ${y + height - ry}
           A ${width/2} ${ry} 0 0 1 ${x} ${y + height - ry}
           Z
           M ${x} ${y + ry}
           A ${width/2} ${ry} 0 0 0 ${x + width} ${y + ry}
         `;

       case 'hexagon':
         const hx = width * 0.25;
         return `M ${x + hx} ${y} L ${x + width - hx} ${y} L ${x + width} ${y + height/2} L ${x + width - hx} ${y + height} L ${x + hx} ${y + height} L ${x} ${y + height/2} Z`;

       // ... other shapes
     }
   };
   ```

3. Add shapes to toolbar

**Tests Required**:
```typescript
describe('shapePaths', () => {
  it('should generate valid diamond path', () => {});
  it('should generate valid cylinder path', () => {});
  it('should generate valid hexagon path', () => {});
  it('should handle edge cases (zero dimensions)', () => {});
});
```

---

### 6.4 Line Styles (UX #13)

**Implementation Steps**:

1. Add line style properties:
   ```typescript
   interface StrokeStyle {
     width: number;
     dashArray: number[];
     lineCap: 'butt' | 'round' | 'square';
   }

   const LINE_STYLES = {
     solid: { dashArray: [] },
     dashed: { dashArray: [8, 4] },
     dotted: { dashArray: [2, 4] },
     dashDot: { dashArray: [8, 4, 2, 4] },
   };
   ```

2. Add line width control (1-8px)

3. Apply stroke-dasharray to SVG elements

**Tests Required**:
```typescript
describe('lineStyles', () => {
  it('should render solid line', () => {});
  it('should render dashed line', () => {});
  it('should render dotted line', () => {});
  it('should apply correct stroke-width', () => {});
});
```

---

### 6.5 Alignment Tools (UX #9)

**Implementation Steps**:

1. Implement alignment functions:
   ```typescript
   // frontend/src/utils/alignment.ts
   export const alignLeft = (elements: CanvasElement[]): CanvasElement[] => {
     const minX = Math.min(...elements.map(e => e.x));
     return elements.map(e => ({ ...e, x: minX }));
   };

   export const alignCenter = (elements: CanvasElement[]): CanvasElement[] => {
     const bounds = calculateBounds(elements);
     const centerX = bounds.x + bounds.width / 2;
     return elements.map(e => ({ ...e, x: centerX - e.width / 2 }));
   };

   export const distributeHorizontally = (elements: CanvasElement[]): CanvasElement[] => {
     const sorted = [...elements].sort((a, b) => a.x - b.x);
     const totalWidth = sorted.reduce((sum, e) => sum + e.width, 0);
     const bounds = calculateBounds(elements);
     const gap = (bounds.width - totalWidth) / (elements.length - 1);

     let currentX = bounds.x;
     return sorted.map(e => {
       const result = { ...e, x: currentX };
       currentX += e.width + gap;
       return result;
     });
   };
   ```

2. Add alignment toolbar (appears when multiple selected)

**Tests Required**:
```typescript
describe('alignment', () => {
  it('should align elements to left edge', () => {});
  it('should align elements to center', () => {});
  it('should align elements to right edge', () => {});
  it('should align elements to top', () => {});
  it('should align elements to middle', () => {});
  it('should align elements to bottom', () => {});
  it('should distribute horizontally evenly', () => {});
  it('should distribute vertically evenly', () => {});
});
```

---

## Phase 7: Performance & Accessibility

### 7.1 Element Virtualization (Problem #1)

**Implementation Steps**:

1. Only render visible elements:
   ```typescript
   // frontend/src/hooks/useVirtualizedElements.ts
   export const useVirtualizedElements = (
     elements: CanvasElement[],
     viewport: Viewport,
     buffer = 100
   ) => {
     return useMemo(() => {
       const visibleBounds = {
         x: viewport.x - buffer,
         y: viewport.y - buffer,
         width: viewport.width + buffer * 2,
         height: viewport.height + buffer * 2,
       };

       return elements.filter(el => isElementVisible(el, visibleBounds));
     }, [elements, viewport, buffer]);
   };
   ```

2. Update visible elements on pan/zoom

**Tests Required**:
```typescript
describe('virtualization', () => {
  it('should return only visible elements', () => {});
  it('should include elements in buffer zone', () => {});
  it('should update on viewport change', () => {});
});
```

---

### 7.2 React.memo Optimization (Problem #2)

**Implementation Steps**:

1. Memoize element components:
   ```typescript
   const CanvasElement = React.memo<CanvasElementProps>(
     ({ element, isSelected, onSelect }) => {
       // render
     },
     (prev, next) => {
       return prev.element === next.element &&
              prev.isSelected === next.isSelected;
     }
   );
   ```

2. Use stable callbacks with useCallback

**Tests Required**:
```typescript
describe('memoization', () => {
  it('should not re-render when props unchanged', () => {});
  it('should re-render when element changes', () => {});
  it('should re-render when selection changes', () => {});
});
```

---

### 7.3 Keyboard Navigation (Problem #4)

**Implementation Steps**:

1. Add keyboard navigation:
   ```typescript
   const handleKeyDown = (e: KeyboardEvent) => {
     if (!selectedIds.size) return;

     const step = e.shiftKey ? 10 : 1;

     switch (e.key) {
       case 'ArrowUp':
         moveElements(selectedIds, 0, -step);
         break;
       case 'ArrowDown':
         moveElements(selectedIds, 0, step);
         break;
       case 'ArrowLeft':
         moveElements(selectedIds, -step, 0);
         break;
       case 'ArrowRight':
         moveElements(selectedIds, step, 0);
         break;
       case 'Tab':
         e.preventDefault();
         selectNextElement(e.shiftKey);
         break;
     }
   };
   ```

2. Add Tab navigation between elements

**Tests Required**:
```typescript
describe('keyboardNavigation', () => {
  it('should move element with arrow keys', () => {});
  it('should move by 10px with shift+arrow', () => {});
  it('should select next element on Tab', () => {});
  it('should select previous element on Shift+Tab', () => {});
});
```

---

### 7.4 Screen Reader Support (Problem #5)

**Implementation Steps**:

1. Add ARIA labels:
   ```typescript
   <svg role="img" aria-label="System design diagram">
     <g role="group" aria-label={`${elements.length} elements`}>
       {elements.map(el => (
         <g
           key={el.id}
           role="graphics-symbol"
           aria-label={getElementLabel(el)}
           tabIndex={0}
         >
           {/* element rendering */}
         </g>
       ))}
     </g>
   </svg>
   ```

2. Announce changes:
   ```typescript
   const announceChange = (message: string) => {
     const announcement = document.createElement('div');
     announcement.setAttribute('role', 'status');
     announcement.setAttribute('aria-live', 'polite');
     announcement.textContent = message;
     document.body.appendChild(announcement);
     setTimeout(() => announcement.remove(), 1000);
   };
   ```

**Tests Required**:
```typescript
describe('accessibility', () => {
  it('should have appropriate ARIA labels', () => {});
  it('should be focusable with keyboard', () => {});
  it('should announce selection changes', () => {});
  it('should announce delete operations', () => {});
});
```

---

## Testing Strategy

### Test Coverage Goals

| Category | Target | Approach |
|----------|--------|----------|
| Hooks | 100% | Unit tests with React Testing Library hooks |
| Utilities | 100% | Pure function unit tests |
| Components | 95% | RTL render tests + user event simulation |
| Integration | 90% | Full canvas interaction tests |

### Test File Organization

```
frontend/src/
├── components/
│   └── canvas/
│       ├── __tests__/
│       │   ├── CanvasToolbar.test.tsx
│       │   ├── CanvasElement.test.tsx
│       │   ├── CanvasArrow.test.tsx
│       │   ├── SelectionHandles.test.tsx
│       │   ├── TextEditor.test.tsx
│       │   └── integration.test.tsx
├── hooks/
│   └── __tests__/
│       ├── useCanvasHistory.test.ts
│       ├── useCanvasDraw.test.ts
│       ├── useCanvasSelection.test.ts
│       ├── useZoomPan.test.ts
│       ├── useResize.test.ts
│       ├── useClickOutside.test.ts
│       └── useMarqueeSelection.test.ts
├── utils/
│   └── __tests__/
│       ├── snap.test.ts
│       ├── textMeasure.test.ts
│       ├── connectionPoints.test.ts
│       ├── zOrder.test.ts
│       ├── grouping.test.ts
│       ├── alignment.test.ts
│       └── shapePaths.test.ts
└── lib/
    └── __tests__/
        ├── canvasExport.test.ts
        └── canvasSchema.test.ts
```

### Mock Strategies

1. **Canvas Context**: Use `jest-canvas-mock` for canvas operations
2. **Clipboard API**: Mock `navigator.clipboard`
3. **Mouse Events**: Use `@testing-library/user-event`
4. **SVG Measurements**: Mock `getBoundingClientRect`

### Integration Test Scenarios

```typescript
// frontend/src/components/canvas/__tests__/integration.test.tsx

describe('Canvas Integration', () => {
  describe('Element Creation', () => {
    it('should create rectangle on drag', async () => {});
    it('should create ellipse on drag', async () => {});
    it('should create arrow from point to point', async () => {});
    it('should create text on click', async () => {});
    it('should place icon on click', async () => {});
  });

  describe('Selection', () => {
    it('should select element on click', async () => {});
    it('should multi-select with shift+click', async () => {});
    it('should box-select with marquee', async () => {});
    it('should deselect on canvas click', async () => {});
  });

  describe('Manipulation', () => {
    it('should drag element to new position', async () => {});
    it('should resize element from corner handle', async () => {});
    it('should rotate element from rotation handle', async () => {});
    it('should edit text on double-click', async () => {});
  });

  describe('Keyboard Shortcuts', () => {
    it('should delete on Delete key', async () => {});
    it('should undo on Ctrl+Z', async () => {});
    it('should redo on Ctrl+Y', async () => {});
    it('should copy on Ctrl+C', async () => {});
    it('should paste on Ctrl+V', async () => {});
  });

  describe('Connectors', () => {
    it('should connect arrow to shape', async () => {});
    it('should update arrow when shape moves', async () => {});
    it('should disconnect on endpoint drag away', async () => {});
  });

  describe('Export/Import', () => {
    it('should export as PNG', async () => {});
    it('should export as SVG', async () => {});
    it('should export as JSON', async () => {});
    it('should import valid JSON', async () => {});
    it('should reject invalid JSON', async () => {});
  });
});
```

### E2E Tests (Playwright)

```typescript
// e2e/canvas.spec.ts
import { test, expect } from '@playwright/test';

test.describe('DesignCanvas', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/design');
  });

  test('should create a complete system diagram', async ({ page }) => {
    // Create load balancer
    await page.click('[data-tool="icon"]');
    await page.click('[data-icon="load_balancer"]');
    await page.click('svg', { position: { x: 100, y: 100 } });

    // Create servers
    // ... continue building diagram

    // Connect with arrows
    // ... add connections

    // Export
    await page.click('[data-action="export-json"]');

    // Verify
    const content = await page.evaluate(() => localStorage.getItem('lastExport'));
    expect(JSON.parse(content)).toHaveProperty('elements');
  });
});
```

---

## File Structure

### New Files to Create

```
frontend/src/
├── components/
│   └── canvas/
│       ├── CanvasToolbar.tsx
│       ├── CanvasElement.tsx
│       ├── CanvasArrow.tsx
│       ├── CanvasGrid.tsx
│       ├── SelectionHandles.tsx
│       ├── IconPalette.tsx
│       ├── TextEditor.tsx
│       ├── ExportMenu.tsx
│       ├── ColorPicker.tsx
│       ├── ZoomControls.tsx
│       ├── AlignmentTools.tsx
│       ├── ConnectionPoints.tsx
│       ├── KeyboardShortcutsModal.tsx
│       └── index.ts
├── hooks/
│   ├── useCanvasHistory.ts
│   ├── useCanvasDraw.ts
│   ├── useCanvasSelection.ts
│   ├── useCanvasElements.ts
│   ├── useCanvasClipboard.ts
│   ├── useZoomPan.ts
│   ├── useResize.ts
│   ├── useClickOutside.ts
│   ├── useClickDetection.ts
│   ├── useMarqueeSelection.ts
│   └── useVirtualizedElements.ts
├── utils/
│   ├── snap.ts
│   ├── textMeasure.ts
│   ├── connectionPoints.ts
│   ├── zOrder.ts
│   ├── grouping.ts
│   ├── alignment.ts
│   └── shapePaths.ts
├── lib/
│   └── canvasSchema.ts
├── config/
│   └── canvas.ts
└── types/
    └── canvas.ts
```

### Files to Modify

```
frontend/src/
├── components/
│   └── DesignCanvas.tsx (refactor to use new components)
├── lib/
│   └── canvasExport.ts (add validation, fix exports)
└── tsconfig.json (enable strict mode)
```

---

## Priority Order

Execute phases in this order:

1. **Phase 1**: Critical bug fixes (must fix)
2. **Phase 5.1-5.2**: Refactoring (makes other work easier)
3. **Phase 4.1-4.2**: Zoom/pan + multi-select (highest value)
4. **Phase 4.3-4.4**: Copy/paste + connectors
5. **Phase 2**: Medium bug fixes
6. **Phase 3**: Minor bug fixes
7. **Phase 6**: Medium priority features
8. **Phase 7**: Performance & accessibility

---

*Generated: January 2026*
*Based on: CANVAS_ANALYSIS.md*
