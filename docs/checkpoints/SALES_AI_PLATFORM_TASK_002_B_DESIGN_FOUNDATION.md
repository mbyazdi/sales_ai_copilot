# Task 002-B — Persian RTL design foundations

Baseline: fast-track, 7edda33. The approved top navigation, route names and
authorization conditions remain unchanged. No feature-page visual migration.

## Ownership and loading

`static/css/design-system.css` owns namespaced `--ds-*` tokens and opt-in `ds-*`
classes. Base loads feature CSS first, foundations second and shell CSS last.
`static/css/app.css` maps its existing `--shell-*` tokens to these foundations.
Update the asset revision in base.html when changing either shared stylesheet.
Existing Customer360 tokens and feature styles remain unchanged to avoid an
implicit redesign. Migrate individual components only under approved page tasks.

## Tokens and primitives

- Typography: Tahoma, Segoe UI, Arial, sans-serif; sizes from 12–24px at the
  default root size, weights 400/600/700, line height 1.75. Change only
  `--ds-font-family` after legally available licensed assets are supplied; no
  fonts are downloaded or assumed installed. Use ds-title/heading/caption/muted.
- Colors: brand, brand hover/soft, text, muted, background, surface/soft, border
  and strong border, success/warning/danger/info with soft surfaces and focus.
- Dimensions: 4/8/12/16/20/24/32px spacing, 44px controls, 20px icons, 1600px
  content width, 6/10/14px radii and pill radius, two restrained shadow levels.
- Layout: ds-container, ds-page-header, ds-stack, ds-row, ds-surface, ds-card.
- Buttons: ds-button with secondary/quiet variants; ds-icon-button. Use real
  button elements for actions and anchors for navigation, not clickable spans.
- Forms: ds-field, ds-label, ds-control, ds-field-error, ds-search. Associate
  labels with controls and hints/errors through aria-describedby. Set
  aria-invalid=true on invalid controls; use native disabled for unavailable
  controls. CSS does not perform validation or disable actions.
- Status: ds-badge with success/warning/danger/info variants. Always include
  meaningful Persian text; color alone must not communicate state.
- Tables: ds-table-region wraps ds-table. Provide caption and scope on th.
  If horizontal scrolling is needed, give the region tabindex=0 and an
  accessible Persian label. Use ds-number for tabular numeric alignment.
- States: ds-state with empty/loading/error variants. Use role=status for
  loading/nonurgent messages, role=alert for actionable errors, and aria-busy
  on the real loading region. Keep text visible; no animated spinner required.
- Keyboard: visible focus rings; shell skip link preserved. Forced-colors
  support preserves component boundaries. Use native details for expansion.

## Icon convention

Inline SVG, 24×24 viewBox, 1.75 stroke, currentColor, no fill, using ds-icon.
Decorative SVGs use aria-hidden=true and focusable=false. Icon-only buttons need
an accessible Persian aria-label. Use ds-icon--directional only for symbols
whose direction must mirror in RTL; search/info symbols must not mirror.
Existing feature emojis remain unchanged. No icon dependency is introduced.

## Visible review

The shared shell uses the foundation typography, palette, sizes and focus tokens.
On any shell page, expand «راهنمای رابط کاربری» to inspect surface treatment,
semantic status examples, labeled search controls, primary button and SVGs.
The search submits to the existing customer route only for staff or active
salespeople. Examples explicitly do not represent actual business status.
The guide is collapsed initially and introduces no new endpoint or sales flow.

Check desktop and 600px/mobile widths, wrapped navigation, keyboard Tab/Enter,
visible focus, and active links. Search forms stack below 600px; table regions
scroll locally. These foundations are RTL-first and use logical alignment and
spacing; numeric/code fields can explicitly set dir=ltr when appropriate.

Full feature adoption, font licensing, feature emoji replacement and further
page redesign remain follow-up work requiring manual UI approval.
