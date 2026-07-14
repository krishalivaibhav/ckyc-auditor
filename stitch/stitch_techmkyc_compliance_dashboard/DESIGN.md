---
name: Autonomous Audit System
colors:
  surface: '#faf8ff'
  surface-dim: '#d8d9e6'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#ecedfa'
  surface-container-high: '#e7e7f4'
  surface-container-highest: '#e1e1ee'
  on-surface: '#191b24'
  on-surface-variant: '#424656'
  inverse-surface: '#2e303a'
  inverse-on-surface: '#eff0fd'
  outline: '#737687'
  outline-variant: '#c2c6d9'
  surface-tint: '#0052dc'
  primary: '#004bca'
  on-primary: '#ffffff'
  primary-container: '#0061ff'
  on-primary-container: '#f1f2ff'
  inverse-primary: '#b4c5ff'
  secondary: '#505f76'
  on-secondary: '#ffffff'
  secondary-container: '#d0e1fb'
  on-secondary-container: '#54647a'
  tertiary: '#9d3000'
  on-tertiary: '#ffffff'
  tertiary-container: '#c73f00'
  on-tertiary-container: '#ffefeb'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#d3e4fe'
  secondary-fixed-dim: '#b7c8e1'
  on-secondary-fixed: '#0b1c30'
  on-secondary-fixed-variant: '#38485d'
  tertiary-fixed: '#ffdbd0'
  tertiary-fixed-dim: '#ffb59d'
  on-tertiary-fixed: '#390c00'
  on-tertiary-fixed-variant: '#832700'
  background: '#faf8ff'
  on-background: '#191b24'
  surface-variant: '#e1e1ee'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: '0'
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: '0'
  label-md:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  mono-sm:
    fontFamily: Geist Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: '0'
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  container-max: 1280px
  gutter: 24px
  margin-mobile: 16px
---

## Brand & Style

The design system is engineered for **TechMKYC**, an autonomous KYC auditor where precision, speed, and trust are paramount. The aesthetic is inspired by the "Utility-Elegant" movement—combining the high-performance feel of developer tools with the refined polish of premium fintech products.

The visual language emphasizes clarity over decoration. It utilizes a **Modern Corporate** style characterized by:
- **Clinical Precision:** Every element exists on a strict grid with defined purpose.
- **Architectural Depth:** Layering is achieved through tonal shifts and subtle borders rather than heavy shadows.
- **Data-First Hierarchy:** Visual weight is reserved for critical status indicators and primary actions, ensuring the user's focus remains on the audit data.

## Colors

The palette is anchored by a "Confident Blue" primary color, designed to feel authoritative and functional. 

- **Primary:** Used for primary call-to-actions, active selection states, and focus indicators.
- **Surface & Backgrounds:** The light theme uses a crisp white background with subtle off-white (`#F8FAFC`) for secondary containers. The dark theme shifts to a deep charcoal to maintain contrast without the harshness of pure black.
- **Functional Status:** Success, Warning, and Error colors are used sparingly. They must always be accompanied by supporting icons or text labels to ensure accessibility and professional restraint.
- **Neutrals:** A sophisticated range of Cool Grays handles the bulk of the UI, including borders (`#E2E8F0`), secondary text (`#64748B`), and disabled states.

## Typography

This design system uses a dual-font strategy to balance character with readability.

- **Headlines & Labels (Geist):** Provides a technical, precise feel. Its geometric construction scales perfectly for large data displays and succinct labels.
- **Body Text (Inter):** Utilized for all long-form content and UI metadata due to its exceptional legibility and neutral tone.
- **Hierarchy:** We use a tight scale. Large display sizes are reserved for dashboard overviews, while body text remains compact (14px) to allow for high-density information display necessary for auditing workflows.
- **Technical Data:** For ID numbers, hash values, or timestamps, use a monospaced variant to emphasize the "autonomous/technical" nature of the auditor.

## Layout & Spacing

The layout is governed by a **Fixed-Fluid Hybrid** grid. 

- **Grid:** A 12-column grid is used for desktop (1280px max width). For data-heavy audit views, the layout may expand to a fluid 100% width to accommodate multi-column tables.
- **Rhythm:** An 8px linear scale is the primary driver for spacing, with a 4px "half-step" used for tight component internals (e.g., icon-to-label spacing).
- **White Space:** Generous outer margins and section spacing (32px+) are used to prevent "dashboard fatigue," ensuring the UI feels airy despite the complexity of the data.
- **Mobile:** On mobile devices, the 12-column grid collapses to a single column with 16px side margins. Horizontal scrolling is permitted for data tables.

## Elevation & Depth

This design system avoids heavy shadows in favor of **Tonal Layering** and **Precision Outlines**.

- **Borders:** The primary method of separation is a subtle 1px border (`#E2E8F0`). In dark mode, these borders become slightly more prominent against the charcoal background.
- **Shadows:** Only used to indicate "interactivity" or "overlay."
  - *Resting State:* No shadow or a very faint 2px blur.
  - *Floating State (Modals/Popovers):* A soft, multi-layered shadow with 10% opacity and a 12px blur, tinted with the neutral gray to keep it grounded.
- **Surfaces:** Use "Surface-Container" tiers. Level 0 is the background; Level 1 is the card surface; Level 2 is for elements nested within cards (like input fields or secondary chips).

## Shapes

The shape language is defined by **Soft Geometricism**. 

A standard corner radius of **12px** (`rounded-lg`) is applied to all primary cards and containers. This "friendly but professional" radius softens the technical density of the data. Smaller components like buttons and input fields use an **8px** radius to maintain a tighter, more functional appearance. Status chips and badges should use a full pill-shape (999px) to clearly differentiate them from interactive buttons.

## Components

- **Buttons:** 
  - *Primary:* Solid primary blue with white text. No gradients.
  - *Secondary:* Ghost style with a 1px neutral border. 
  - *State:* Subtle opacity shift (0.9) on hover; 2px focus ring using the primary color with a 2px offset.
- **Input Fields:** Minimum height of 40px. Use a subtle light gray fill (`#F8FAFC`) that clears to white on focus. Labels are always positioned above the field in `label-md` weight.
- **Cards:** 1px border, 12px radius, and a 16-24px internal padding. Avoid inner shadows.
- **Audit Chips:** Small badges used for "High Risk" (Red text on light red tint), "Review" (Amber), and "Cleared" (Green). Must include a 12px lead icon (e.g., a shield or checkmark).
- **Data Tables:** Row height of 52px for readability. Use horizontal dividers only; no vertical borders between columns. The header row should be in `label-md` uppercase with a light gray background.
- **The "Audit Timeline":** A custom vertical stepper component using thin 1px lines and 8px circular nodes to track autonomous audit progress.