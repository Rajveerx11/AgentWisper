---
name: AgentWisper
description: A calm Windows signal desk for private, technical dictation.
colors:
  mineral-worktop: "#F3F5F7"
  paper-white: "#FFFFFF"
  frosted-panel: "#EDF1F5"
  navigation-paper: "#F8FAFB"
  rule: "#D8E0E7"
  strong-rule: "#BBC7D3"
  deep-navy-ink: "#111C2E"
  slate-copy: "#263548"
  muted-slate: "#647386"
  cobalt-route: "#2F67E8"
  cobalt-hover: "#2454C5"
  cobalt-mist: "#E8EFFF"
  jade-signal: "#087456"
  jade-mist: "#E5F5EF"
  crimson-error: "#B63A50"
  crimson-mist: "#FCEBED"
  amber-warning: "#A36616"
  carbon-control: "#111820"
  carbon-control-hover: "#18222D"
  carbon-edge: "#344252"
  carbon-copy: "#F7FAFC"
  carbon-muted: "#AAB7C5"
typography:
  display:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "22pt"
    fontWeight: 700
    lineHeight: 1.2
  title:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "12pt"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "10pt"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Segoe UI, sans-serif"
    fontSize: "9pt"
    fontWeight: 700
    lineHeight: 1.3
  mono:
    fontFamily: "Cascadia Mono, Consolas, monospace"
    fontSize: "8pt"
    fontWeight: 400
    lineHeight: 1.35
rounded:
  square: "0px"
  compact-control: "10px"
  signal-node: "18px"
  circular: "999px"
spacing:
  hairline: "1px"
  micro: "2px"
  xs: "4px"
  sm: "8px"
  md: "12px"
  control: "18px"
  section: "20px"
  page-y: "28px"
  page-x: "34px"
components:
  button-primary:
    backgroundColor: "{colors.cobalt-route}"
    textColor: "{colors.paper-white}"
    typography: "{typography.body}"
    rounded: "{rounded.square}"
    padding: "10px 18px"
  button-primary-hover:
    backgroundColor: "{colors.cobalt-hover}"
    textColor: "{colors.paper-white}"
    rounded: "{rounded.square}"
  button-secondary:
    backgroundColor: "{colors.frosted-panel}"
    textColor: "{colors.deep-navy-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.square}"
    padding: "10px 18px"
  surface-card:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.slate-copy}"
    rounded: "{rounded.square}"
    padding: "20px"
  input:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.deep-navy-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.square}"
    padding: "8px"
  signal-node:
    backgroundColor: "{colors.carbon-control}"
    textColor: "{colors.carbon-copy}"
    rounded: "{rounded.signal-node}"
    height: "58px"
---

# Design System: AgentWisper

## Overview

**Creative North Star: "Signal Desk"**

AgentWisper feels like a precise audio routing desk reduced to its essential signal path. Mineral-gray workspace, paper-white surfaces, fine rules, and deep navy text keep the main app calm. Cobalt, jade, crimson, and amber communicate routing state; they are functional signals, not decoration.

The main window is a quiet control room. The persistent carbon Signal Node is its compact field instrument: visible at the edge of the active workspace, animated only while work is happening, and explicit about readiness, listening, processing, success, or failure. This visual system supports technical confidence without mimicking a centered dictation bar.

**Key Characteristics:**

- Light mineral workspace with precise, square-edged surfaces.
- Speech shown as a route from microphone to model to active cursor.
- Cobalt interaction, jade completion, amber caution, and crimson recovery states.
- Carbon Signal Node as the only dark persistent surface.
- Native Windows density, direct labels, and restrained motion.

## Colors

Palette pairs cool mineral neutrals with scarce signal colors and one compact carbon control surface.

### Primary

- **Cobalt Route** (`colors.cobalt-route`): live routes, primary actions, keyboard focus, and the listening state.
- **Cobalt Hover** (`colors.cobalt-hover`): pressed and hover feedback for primary actions.
- **Cobalt Mist** (`colors.cobalt-mist`): selected navigation and gentle active-node fills.

### Secondary

- **Jade Signal** (`colors.jade-signal`): local privacy, readiness, and successful completion.
- **Amber Warning** (`colors.amber-warning`): cloud-routing notice and processing caution.
- **Crimson Error** (`colors.crimson-error`): failures and destructive actions that need recovery.

### Neutral

- **Mineral Worktop** (`colors.mineral-worktop`): application workspace.
- **Paper White** (`colors.paper-white`): transcript, settings, and history surfaces.
- **Navigation Paper** (`colors.navigation-paper`): fixed navigation rail.
- **Rule / Strong Rule** (`colors.rule`, `colors.strong-rule`): separation, field boundaries, and focus-ready structure.
- **Deep Navy Ink / Slate Copy / Muted Slate** (`colors.deep-navy-ink`, `colors.slate-copy`, `colors.muted-slate`): title, body, and secondary information hierarchy.
- **Carbon Control / Carbon Copy** (`colors.carbon-control`, `colors.carbon-copy`): persistent Signal Node shell and its high-contrast text.

**The Rare Signal Rule.** Signal colors mark action or state; no screen becomes a cobalt, jade, amber, or crimson field.

**The One Dark Surface Rule.** Carbon belongs to the floating Signal Node. Main application pages remain mineral and paper.

## Typography

**Display Font:** Segoe UI (with sans-serif fallback)
**Body Font:** Segoe UI (with sans-serif fallback)
**Label/Mono Font:** Cascadia Mono (with Consolas and monospace fallbacks)

**Character:** Segoe UI keeps controls familiar, readable, and unmistakably Windows-native. Cascadia Mono appears sparingly where information describes a model, provider, count, or system state.

### Hierarchy

- **Display** (`typography.display`): 22-point page titles; one per page.
- **Title** (`typography.title`): section and surface headings.
- **Body** (`typography.body`): instructions, transcripts, field values, and history text.
- **Label** (`typography.label`): buttons, route status, fields, and high-priority metadata.
- **Mono** (`typography.mono`): model names, provider metadata, counts, and short technical labels.

**The Two Voices Rule.** Segoe UI explains and directs; Cascadia Mono identifies machine-facing details. Never set ordinary paragraphs in mono.

## Layout

Desktop workspace opens at 1120 by 760 pixels and must remain useful at its 940 by 660 pixel minimum. A fixed 184-pixel navigation rail anchors the left edge. Pages use 34-pixel horizontal insets, 28-pixel top spacing, and a 20-pixel internal surface rhythm.

Home follows one vertical command sequence: page context, 172-pixel signal route, current action, then latest transcript. History and Settings retain the same page insets and surface language. Keep the first viewport focused on dictation; no analytics grid or decorative dashboard modules.

Signal Node docks 22 pixels from the active monitor work-area edges. It expands by state: 248 by 58 pixels at rest, 318 by 70 while listening, and 278 by 62 for processing, success, or failure. It stays non-activating so the user's typing target remains untouched.

**The Route Before Record Rule.** Show microphone, selected model, and cursor as one readable path; never reduce the primary workspace to a giant microphone control.

## Elevation & Depth

Main application surfaces are flat. Depth comes from mineral-to-paper tonal changes, one-pixel rules, and hierarchy—not ambient card shadows. Signal Node uses a small dark underlay inside its canvas to lift it from the desktop without introducing a general shadow vocabulary.

**The Flat Workbench Rule.** Main surfaces stay flat at rest; use borders, spacing, and state color before elevation.

## Shapes

Primary pages, cards, inputs, buttons, and navigation remain square-edged. This creates the precise, instrument-panel character of Signal Desk. Circular ports represent route nodes and state indicators. Rounded geometry is reserved for the floating Signal Node (18-pixel radius) and its compact Stop control (10-pixel radius).

**The Rounded Instrument Rule.** Rounded forms belong to live signal controls and ports, not every container.

## Components

### Buttons

- **Shape:** square, compact, and direct (`rounded.square`).
- **Primary:** Cobalt Route with Paper White text and 10 by 18 pixel internal spacing (`components.button-primary`).
- **Hover / Focus:** Cobalt Hover on pointer feedback; a two-pixel Cobalt Route focus boundary remains keyboard-visible.
- **Secondary / Quiet / Danger:** neutral tonal fill for ordinary actions, parent-surface quiet treatment for low priority, and Crimson Mist with Crimson Error text for destructive actions.
- **Disabled:** retain the control silhouette, replace emphasis with Muted Slate, and remove action styling.

### Cards / Containers

- **Corner Style:** square (`rounded.square`).
- **Background:** Paper White over Mineral Worktop.
- **Shadow Strategy:** none in the main window.
- **Border:** one-pixel Rule; use Strong Rule for form fields.
- **Internal Padding:** 20-pixel section rhythm, with 34-pixel page insets outside.

### Inputs / Fields

- **Style:** Paper White field, Deep Navy Ink value, Strong Rule boundary, square corners.
- **Focus:** boundary switches to Cobalt Route; selected text uses Cobalt Mist.
- **Error / Disabled:** pair Crimson Error or Muted Slate with readable text; never rely on color alone.

### Navigation

Fixed left rail uses Navigation Paper. Items use bold 10-point Segoe UI, generous 11-pixel vertical padding, and square geometry. Selected items receive Cobalt Mist with Cobalt Route text; keyboard focus keeps a visible cobalt boundary.

### Signal Stage

The signature main-window component. Three circular ports map Microphone, selected model, and Active cursor across one rule. Listening draws a live cobalt waveform; processing advances a dot; success completes the route in jade; errors use crimson and a written status.

### Signal Node

The signature desktop component. Carbon shell, 18-pixel corners, white primary copy, muted secondary copy, and a three-lane routed trace make it recognizable without resembling a centered voice bar. Click toggles dictation; right-click returns to the main app. Listening and processing animate at a 55-millisecond cadence. Success holds for 1.8 seconds; errors hold for 2.8 seconds before returning to Ready.

## Do's and Don'ts

### Do:

- **Do** keep privacy and provider routing visible in plain text.
- **Do** use signal colors for specific states and pair them with written labels.
- **Do** preserve the microphone-to-model-to-cursor route as the core visual metaphor.
- **Do** keep the floating control at the active monitor edge without stealing focus.
- **Do** use Segoe UI for human guidance and Cascadia Mono for compact machine metadata.

### Don't:

- **Don't** copy Wispr Flow's centered bar or its composition.
- **Don't** turn the app into a generic dark card dashboard.
- **Don't** use a giant microphone as the primary workspace control.
- **Don't** add decorative charts, fake metrics, or ornamental animation.
- **Don't** hide recording, processing, privacy, or failure state behind color alone.
