---
description: Scan CSS/layout files for common anti-patterns including scroll traps, sticky misuse, nested visual containers (窗口套窗口), flexbox/grid misuse, z-index chaos, height collapse, responsive gaps, and accessibility issues. Works on any web project.
allowed-tools: [Read, Glob, Grep, Bash]
---

# Detect CSS Layout Issues

Scan the project's CSS/SCSS/Vue style blocks for common layout anti-patterns. Group findings by category.

## What to check

### 1. Scroll & Overflow Traps
- Layout containers (`display: grid` / `display: flex`) with `min-height: 100vh` but no `overflow: hidden` — causes the whole page to scroll as one unit
- Sidebar/nav elements inside fixed-height layouts missing `overflow-y: auto`
- Content areas that should scroll independently but lack `overflow-y: auto`
- `overflow: hidden` on body/html that masks scroll issues
- Nested scrollable containers that fight each other (parent and child both `overflow: auto`)

### 2. Header/Navbar Scroll Escape (the most commonly missed issue)
Headers, topbars, navbars, or action bars that live inside a scrollable container (`overflow: auto/scroll`) without `position: sticky`. They scroll away when the user scrolls the content.

**Detection steps:**
1. Find elements with `overflow-y: auto` or `overflow: auto` or `overflow-y: scroll`
2. Check if their children include header-like elements (class names: `topbar`, `header`, `navbar`, `nav-bar`, `action-bar`, `toolbar`, `page-header`, `app-bar`)
3. If those header-like children lack `position: sticky; top: 0`, flag them

**Common wrong fix:** Adding `position: sticky; top: 0` with negative margins to compensate for parent padding. This is a code smell — negative margins on sticky elements indicate the layout structure is wrong.

**Correct fix pattern:** Restructure to flex column layout:
```css
.parent {
  display: flex;
  flex-direction: column;
  overflow: hidden;       /* not overflow-y: auto */
}
.parent-header {
  flex-shrink: 0;         /* stays fixed */
  padding: ...;           /* header owns its own padding */
  background: var(--bg);  /* covers content behind */
}
.parent-content {
  flex: 1;
  overflow-y: auto;       /* only content scrolls */
  padding: ...;           /* content owns its own padding */
}
```

**Also flag:** `position: sticky` combined with negative margin hacks (`margin-inline: calc(... * -1)`, `margin-top: calc(... * -1)`). This means the parent has padding that interferes with sticky — restructure instead.

### 3. Padding on Scroll Containers
Padding on an element with `overflow: auto/scroll` causes:
- Sticky children to be offset from the scroll edge (sticky `top: 0` sticks at the content edge, not the padding edge)
- The last child's bottom padding to not scroll into view (content clips at the padding boundary)

**Detection:** Find `overflow-y: auto` or `overflow: auto` on elements that also have `padding`. Flag if the element contains children that need sticky positioning or if the bottom padding might clip.

**Fix:** Move padding to inner wrapper elements. Keep the scroll container padding-free.

### 4. Nested Visual Containers (窗口套窗口)
Card/panel components placed inside containers that already provide visual framing, creating a "window within window" effect.

**Detection steps:**
1. Find card-like components (`el-card`, `a-card`, `n-card`, or any element with `border` + `box-shadow` + `border-radius`)
2. Check if they are direct children of a layout container that already has `padding` (like a workspace, content area, or page wrapper)
3. If yes, flag as redundant visual nesting

**Key distinction:** Multiple cards side by side for visual grouping (e.g., status cards in a grid) is fine. The problem is when a card is the **sole child** of a content area — it creates an unnecessary visual container wrapping the entire page.

**Also check for duplicate titles:**
1. Find page titles in topbar/header (e.g., `<h1>`, page title text)
2. Check if child components also have their own headers/titles (`<h2>`, `<h3>`, card `#header` slots)
3. If both are visible simultaneously and refer to the same content, flag as duplicate title hierarchy

**Common patterns to flag:**
- A single `el-card` as the only child of `workspace-content` — the workspace padding + card border = nested windows. Replace with plain `<div>`.
- Component with its own `border-top` + `border` + `border-radius` as the sole content of a padded container
- Card header slot (`#header`, `v-slot:header`) when parent page already shows the same title in topbar
- Multiple cards inside a single section where each card is a `v-for` item — this is fine, don't flag

**Fix options:**
- Replace card component with plain `<div>`, use the component's own class for styling (border-top accent, padding)
- Remove duplicate title from component if parent page already shows it in topbar
- If the card is the only child, consider making the workspace-content itself the card (apply border/shadow to the content wrapper)

### 5. Flexbox Pitfalls
- Flex children with `width`/`min-width` set but no `flex-shrink: 0` — they get squished unexpectedly
- Flex containers with `flex-wrap: wrap` but children have no `min-width` — they overflow instead of wrapping
- `flex: 1` vs `flex-grow: 1` confusion — `flex: 1` sets `flex-shrink: 1` which may cause unwanted shrinking
- Missing `min-width: 0` on flex children with long text — text overflows instead of truncating
- `align-items: stretch` on column flex with percentage-height children — children collapse

### 6. Grid Misuse
- `grid-template-columns` with only `1fr` when some columns need minimum widths — content overflows
- `grid-auto-rows: 0` or missing row sizing — content gets clipped
- `gap` used but `grid-template` doesn't account for it — total size exceeds container
- `grid-column: span N` exceeding the defined grid — element wraps unexpectedly

### 7. Height Collapse & Containing Block
- Percentage `height` on child when parent has no explicit height — resolves to 0/auto
- `position: absolute` without a positioned ancestor — escapes to viewport
- `min-height` with `flex-direction: column` — children with `height: 100%` don't fill correctly
- `height: 100vh` inside a `transform` or `will-change` element — 100vh includes mobile browser chrome

### 8. Stacking & z-index Chaos
- `z-index` values > 999 (magic numbers) — indicates unmanaged stacking contexts
- `z-index` on non-positioned elements (has no effect)
- `position: fixed` inside a `transform`/`filter` ancestor — fixed positioning breaks
- Multiple `position: relative` + `z-index` siblings creating unintended stacking

### 9. Responsive & Overflow
- Fixed pixel widths (`width: 800px`) without `max-width` — breaks on small screens
- `overflow: hidden` on containers that should scroll on mobile
- Missing `box-sizing: border-box` — padding increases element width beyond 100%
- Images/media without `max-width: 100%` — overflow on narrow viewports

### 10. Accessibility & Interaction
- `overflow: hidden` clipping focus outlines
- Missing `outline` on `:focus-visible` replacements
- Click targets < 44px (WCAG 2.5.5)
- `user-select: none` on selectable content

### 11. Performance
- `will-change` on too many elements (memory pressure)
- `transform`/`opacity` animations on elements with `overflow: hidden` + `border-radius` (repaint storms)
- `backdrop-filter` on scroll containers (expensive)

## Steps

1. Use `Glob` to find all CSS/SCSS files and Vue files with `<style>` blocks
2. Use `Grep` to search for each pattern category
3. Read surrounding context (5-10 lines) to confirm findings
4. Report grouped by category

## Output format

```
## Category Name
| File | Line | Selector | Issue | Suggested Fix |
|------|------|----------|-------|---------------|
```

If no issues found in a category, skip it. End with a summary count.

$ARGUMENTS
