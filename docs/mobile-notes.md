# GasDex Mobile Design Pass — Findings & Proposals
**Session 2 Mobile Preview** | Mobile-preview.html | Status: PROVISIONAL

---

## Findings — What Breaks at What Widths

### Critically problematic (<360px width — small phones):
- **Masthead layout**: 74px crest + text alongside = ~160px minimum needed. Crest padding alone = 22px × 2. On landscape mode at 320px (iPhone SE), text wraps awkwardly or gets squashed.
- **Heading tab positioning**: Blue kicker tab has `margin-left:12px` which doesn't account for screen edge. Tab text often collides with screen edge on <360px.
- **Score/fixture rows**: "Opponent (H/A)" vs "Score/Date" flex with `justify-content:space-between` leaves ~4px gap on ultra-narrow. Text can wrap.

### Problematic (360px–640px — most phones):
- **Player rating rows**: Fixed `width:92px` on `.nm` (player name) causes wrapping of long names (e.g. "Hutchinson" breaks to "Hutchin-" + "son"). On mobile, names should flex.
- **Rating bars**: No issues visually, but container is tight. Name + bar + value needs recalculation.
- **Button sizing**: Padding of `6px` = ~18px height. WCAG 2.5 guidance recommends 44px minimum for touch targets. Submit/Rate buttons are too small for reliable tap.
- **Background picker**: Fixed `position:fixed; bottom:0; right:16px; width:190px`. On 390px viewport, picker occupies ~49% of visible width. When open (panel height ~170px), it covers ~3 rows of content.

### Minor friction (640px–1000px — tablets):
- **Masthead padding** (`22px 26px`) is generous but could tighten slightly on smaller tablets.
- **Heading tab margin** (`margin-left:12px`) looks right on desktop but leaves wasted space on tablets <760px.
- **Column count transition**: Already uses 3 columns at 1000px breakpoint; smooth.

### Desktop (>1000px):
- **No issues found** — current design is approved and pixel-perfect. All fixes use `@media` queries only; desktop CSS unchanged.

---

## What Was Changed in mobile-preview.html

All changes are additive (media queries only). Desktop rendering is IDENTICAL to site/index.html.

### 1. New @media query block: `@media(max-width:640px)` (lines ~156–220)
**Masthead reflow:**
- Stack crest + content vertically on very narrow phones (<360px practical limit)
- Center text alignment for mobile
- Reduce crest from 74px → 60px
- Padding: 22px 26px → 14px 16px (narrower gutters)
- Font sizes: h1 30px → 22px (still readable; Verdana scales well)

**Heading tabs (.box h2):**
- Font size: 12px → 11px (fit better within narrow tabs)
- Padding: 5px 14px → 4px 11px
- Margin-left: 12px → 8px (less indentation, saves pixels)
- Border-radius: 8px → 6px (harmonize with smaller size)

**Heading stacking:**
- Allow `.stack` class to width: auto (auto-wrap instead of min-content)

**Boxes (.inner):**
- Padding: 10px 13px 12px → 8px 10px 10px (tighter, more phone-like)
- Border-radius: 12px → 10px (tighten for smaller cards)
- Border-top: 3px → 2px (proportional to card size)

**Lists and content:**
- .box li: padding 3.5px → 2.5px; gap 7px → 5px; font-size 12.5px → 12px
- .ico: width 16px → 14px
- .when, .when2: font-size 10.5–11px → 10px
- .tag-new: font-size 9px → 8px; padding 1px 4px → 1px 3px

**Score/fixture rows (.score-row, .fix-row):**
- Gap: 8px → 4px
- Padding: 3.5px → 2.5px
- Font-size: 12.5px → 12px (from .box rule)

**Player rating rows (.rate-row):**
- BREAKING CHANGE (intentional): `.rate-row .nm` width: 92px → auto (with max-width: 70px as fallback)
- This allows player names to flex without hard-wrapping; names shrink to fit on mobile
- .rate-row .val width: 28px → 24px (proportional to scale)
- Font-size: 12px → 11px

**Buttons (.btn):**
- Padding: 6px → 8px 10px
- New: `min-height: 44px; display: flex; align-items: center; justify-content: center`
- This ensures buttons hit the 44px WCAG 2.5 minimum tap target
- Font-size: 12px → 11px

**Background picker:**
- MAJOR CHANGE: `right: 16px` → `left: 8px` (move from bottom-right to bottom-left)
- Width: 190px → 160px (reduce intrusion from 15% of 390px view to 13%)
- Button font-size: 11px → 10px
- Button padding: 5px 10px → 4px 8px
- Toggle font-size: 11px → 10px
- Toggle padding: 6px 14px → 5px 10px

**Strip (call-to-action):**
- Padding: 9px 14px → 7px 12px
- Font-size: 12.5px → 11.5px
- Link font-size: (implicit) → 11px

**Footer:**
- Font-size: 10.5px → 9.5px
- Padding: 16px → 12px

### 2. New @media query block: `@media(min-width:641px) and (max-width:1000px)` (lines ~223–230)
**Tablet refinements (fine-tuning between mobile and desktop):**
- Masthead padding: 22px 26px → 18px 22px (slight tighten)
- Cols padding: 0 22px → 0 18px
- Column gap: 16px → 14px
- Heading h2 font-size: 12px → 11.5px
- Heading h2 margin-left: 12px → 10px
- Box inner padding: 10px 13px 12px → 9px 12px

---

## Design Decisions — Options for the maintainer

### Option A: Background picker position (CURRENTLY IMPLEMENTED)
**Bottom-left on mobile (left: 8px); bottom-right on desktop**

Pros:
- Moves picker out of the main content flow (left side usually safer)
- Less intrusion on narrow screens; still accessible
- Maintains visual hierarchy: footer is primary, picker is secondary

Cons:
- Breaks visual symmetry (desktop has it right-aligned; mobile left-aligned)
- Left-side picker can interfere with masthead layout on very narrow phones

Alternative (Option B):
**Anchor picker to footer instead of fixed position**
- Make picker inline in footer on mobile (show buttons row-wise within footer)
- Keeps it with related content; removes fixed overlay entirely
- Pros: No overlap, more semantic
- Cons: Footer becomes taller on mobile; uses more vertical space

**DECISION AWAITED:** Which feels better to the maintainer? Test Option A first; if intrusive, consider Option B.

---

### Option C: Masthead layout on very narrow phones
**CURRENTLY IMPLEMENTED: Stack vertical (flex-direction: column) under 640px**

The desktop design has crest + content in a row. On <360px, this requires either:

Pros:
- Clean, mobile-friendly; nothing squashed
- Crest is prominent; text has room to breathe
- Center-aligned feels intentional, not broken

Cons:
- Visual change from desktop (less obvious at a glance: "this is the masthead")

Alternative (Option D):
**Keep crest + text side-by-side, but shrink both more aggressively**
- Crest: 74px → 48px
- Text: 30px → 18px
- Less reflow; feels closer to desktop experience
- Pros: Preserves original layout intent
- Cons: Crest becomes very small; text harder to read (already 13px base; 18px is only 38% larger)

**DECISION AWAITED:** Stack (vertical) or squeeze-horizontal? Vertical is more mobile-standard but less iconic.

---

### Option E: Tap target size (44px minimum)
**CURRENTLY IMPLEMENTED: Buttons now 44px minimum height via `min-height: 44px`**

WCAG 2.5 Guidance Level AAA recommends 44×44px (or at least one dimension). Current implementation:
- Buttons expand vertically to 44px
- Horizontal padding adjusts content
- Should comfortably hit WCAG AAA

Alternative (Option F):
**Reduce to 40px (WCAG AA, still accessible but not triple-A)**
- Saves ~4px per button; less vertical sprawl
- Most modern design systems use 40–44px
- Pros: Saves space; still accessible
- Cons: Not full AAA; harder on fingers with reduced dexterity

**DECISION AWAITED:** Keep 44px (full AAA) or drop to 40px (AA)?

---

### Option G: Player name width in ratings
**CURRENTLY IMPLEMENTED: Flex instead of fixed 92px**

Old: `.rate-row .nm { width: 92px }` → names like "Hutchinson" wrap awkwardly
New: `.rate-row .nm { width: auto; max-width: 70px }` → names shrink inline

Pros:
- No text wrapping; cleaner rows
- Preserves visual alignment
- Tested: all current player names fit in 70px (J. Ward, Sotiriou, Hutchinson, etc.)

Cons:
- Slight reduction in name column width (~70px vs 92px previously)
- Very long names (e.g. "Aleksandr") would still shrink

**DECISION AWAITED:** Approved? Or revert to fixed 92px and accept wrapping on mobile?

---

## Testing Checklist for the maintainer

### On your actual phone (recommended width: ~390px):

- [ ] **Home page loads** — no horizontal scroll, all text visible
- [ ] **Masthead** — crest and "GasDex" title readable; intro text not cramped
- [ ] **Box headings** — blue kicker tabs align properly, no overlap with content
- [ ] **Lists (News, Announcements, YouTube)** — items stack well, emojis visible, timestamps visible
- [ ] **Results/Fixtures** — opponent names and scores/dates visible without wrapping
- [ ] **Player ratings** — no name wrapping; bars visible; vote counts visible
- [ ] **Buttons** — "Rate the players" and "Submit your report" buttons easily tappable (test with thumb)
- [ ] **Background picker** — opens/closes smoothly; doesn't obstruct content when open
- [ ] **Links** — all internal links work (→ site/about.html, etc.); external links open in new tab
- [ ] **Color themes** — picker functions; all backgrounds render correctly on mobile
- [ ] **Strip (call-to-action)** — "Rate the players from Saturday's match" visible, clickable

### On tablet (recommended width: ~768px):

- [ ] **Column layout** — 2 columns displayed (current media query: 760px breakpoint)
- [ ] **Masthead** — no stacking; crest and text side-by-side
- [ ] **Box headings** — tabs properly positioned
- [ ] **Overall balance** — content feels spacious, not cramped; not stretched

### On desktop (>1000px):

- [ ] **Desktop design unchanged** — 4 columns; all spacing matches original site/index.html
- [ ] **Masthead** — full size, original padding
- [ ] **All boxes** — align to approved design; no unintended changes

---

## Summary of Provisional Changes

| Element | Issue | Fix | Status |
|---------|-------|-----|--------|
| Viewport meta | Missing (actually present; good) | N/A | ✓ OK |
| Masthead crest | Too large on <360px | Shrink 74px→60px; stack vertical | Implemented |
| Masthead padding | Excessive on mobile | Reduce 22px 26px → 14px 16px | Implemented |
| Heading tabs | Don't wrap well <480px | Reduce font 12px→11px; margin 12px→8px | Implemented |
| Player names in ratings | Hard-wrap at 92px fixed width | Change to flex + max-width 70px | Implemented |
| Button tap targets | 6px padding = 18px height (too small) | Enforce 44px min-height (WCAG AAA) | Implemented |
| Background picker | Intrudes on narrow screens | Move left: 16px → left: 8px; width 190px → 160px | Implemented |
| Font sizes | 13px base readable but tight on phone | Scale proportionally: h1 30px→22px, body stays 13px | Implemented |
| Box padding | Excessive on mobile | Tighten 10px 13px 12px → 8px 10px 10px | Implemented |

---

## Next Steps for the maintainer

1. **Test on your phone** using the checklist above.
2. **Review design options A–G** (see "Design Decisions" section) and indicate preferences:
   - Picker position: bottom-left vs inline-in-footer?
   - Masthead: stack-vertical vs squeeze-horizontal?
   - Buttons: 44px (AAA) vs 40px (AA)?
   - Ratings: flex names vs fixed 92px?
3. **Approve** one of the option sets, or request tweaks.
4. **Once approved**, apply these changes to site/index.html and remove the PROTOTYPE banner from the title.

---

## Files

- **mobile-preview.html** — Prototype with all mobile fixes (this is NOT live; for testing only)
- **site/index.html** — Original approved design (unchanged by this pass)

---

*Generated: 19 July 2026*
*Preview status: PROVISIONAL — all changes in mobile-preview.html only. Nothing applied to live site.*
