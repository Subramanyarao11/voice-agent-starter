# Sahaayak Indian Public-Service UI/UX Guide

**Status:** Canonical design and implementation guidance

**Research snapshot:** 9 August 2026

**Applies to:** citizen web experience, benefit and job discovery, voice flows,
saved work, reminders, operator/admin surfaces, and future mobile clients

**Primary references:** GIGW 3.0, Digital Brand Identity Manual (DBIM) V3.0,
and UX4G Design System 3.0

> Sahaayak is an independent guidance product. Adopting public-service design
> conventions does not make it a Government of India website, demonstrate
> government approval, or permit use of the State Emblem of India. The product
> must build trust through verified sources, transparent limitations, and usable
> services - not through imitation of official identity.

## 1. Purpose and rule language

This guide turns official Indian government digital guidance and recurring
patterns across live public-service portals into one implementable system for
Sahaayak. It is intended to answer both design and engineering questions:

- what the site should look and feel like;
- how citizens should move through it;
- how typography, colour, spacing, icons, forms, voice, and AI responses work;
- what accessibility and multilingual behaviour is required;
- how provenance, freshness, privacy, and independent status are communicated;
- how the citizen and workforce/admin experiences remain consistent without
  becoming visually identical; and
- what must be tested before a release.

The terms in this document have the following meaning:

- **MUST** is a Sahaayak release requirement.
- **SHOULD** is the default; deviations require a recorded product or
  accessibility reason.
- **MAY** is optional.
- **Official rule** means a requirement stated for Indian government digital
  platforms. Because Sahaayak is currently independent, such a rule is adopted
  voluntarily unless another law or contract makes it directly applicable.
- **Product decision** means a Sahaayak-specific interpretation selected to
  resolve variation between official portals.

This guide is not a claim of GIGW, DBIM, STQC, WCAG, or legal compliance. Such a
claim requires the applicable assessment and authorization.

## 2. Authority hierarchy and conflict resolution

Use sources in this order when two references appear to disagree:

| Priority | Source | What it governs for this guide |
| --- | --- | --- |
| 1 | Applicable law and regulation | State Emblem restrictions, disability rights, privacy and consent |
| 2 | [GIGW 3.0](https://guidelines.india.gov.in/guidelines/) and its [conformity matrix](https://guidelines.india.gov.in/annexure-ii-matrix-to-check-conformity/) | Quality, accessibility, content lifecycle, navigation, multilingual delivery, security-facing UX |
| 3 | [DBIM V3.0](https://www.stqc.gov.in/sites/default/files/2025-06/DBIM%20Manual%20V%203.0.pdf) | Official colour groups, Noto typography, icon treatment, government header/footer conventions, content and form guidance |
| 4 | [UX4G Design System 3.0](https://www.ux4g.gov.in/foundations?lang=en) | Implementable tokens, components, spacing, interaction, accessibility, and content patterns |
| 5 | Live government portals | Evidence of familiar public-service patterns, never a substitute for the formal standards |
| 6 | This document | Sahaayak-specific decisions and stricter internal targets |

Important reconciliations:

- GIGW 3.0 and UX4G use WCAG 2.1 AA as their documented baseline. Sahaayak
  MUST meet that baseline and SHOULD target WCAG 2.2 AA where it is stricter.
- DBIM gives a compact common website type scale; UX4G gives a larger token
  scale. Sahaayak uses the smaller subset in section 7 so screens remain
  predictable and multilingual text remains readable.
- DBIM requires a government organization to select one primary colour group.
  Sahaayak voluntarily adopts the DBIM **Blue** group rather than combining
  several government palettes or styling the interface as a tricolour.
- Live sites differ substantially in colour and density. Their common
  structural conventions are more important than copying a specific homepage.

## 3. What the live-site review showed

The following official sites were reviewed as a cross-section of national,
transactional, scheme, job, engagement, and district services. Observations are
a 9 August 2026 snapshot and are not normative requirements.

| Site | Useful pattern to retain | Pattern not to copy blindly |
| --- | --- | --- |
| [National Portal of India](https://www.india.gov.in/) | Search-first discovery, topic filters, accessibility controls, content-source attribution, translation disclaimer, report/suggest mechanism, and prominent last-reviewed date | Its broad editorial homepage and campaign content are too dense for a focused voice assistant |
| [myScheme](https://www.myscheme.gov.in/) | Simple “enter details - search - select and apply” model, personalised discovery, dedicated scheme information, support links, last-updated date, and deployed version | Green branding is specific to myScheme; Sahaayak should not clone it or its government identity |
| [DigiLocker](https://www.digilocker.gov.in/) | Utility bar with skip link, text size and language controls; task categories; short getting-started steps; help and policy links; UX4G-based components | Document-wallet information architecture and government programme lockups do not transfer to Sahaayak |
| [MyGov](https://www.mygov.in/) | Visible accessibility controls, search, clear engagement actions, help/feedback, sitemap and policy coverage | Its very large navigation taxonomy would increase cognitive load in a task-focused product |
| [Mysuru district S3WaaS site](https://mysore.nic.in/) | Local-language-first delivery, bilingual ownership, services, helplines, notices, recruitment, contact/feedback and freshness information | Deep menus, rotating announcements, and content-heavy district IA are not appropriate for the primary conversation path |
| [National Career Service](https://www.ncs.gov.in/) | Role-oriented job search, filters, accessible mode, fraud warning, toll-free help, policy links, grievance/feedback and deployment version | Legacy mega-navigation and browser/resolution assumptions should not be repeated |

The recurring visual and interaction language is:

- a light page background with dark readable text;
- one restrained primary colour, with semantic status colours;
- a utility area for language, accessibility, help, and search;
- clear organization/product identity and ownership information;
- task-based navigation and card/list groupings;
- visible source, validity, update, and policy information;
- responsive layouts with text alternatives and keyboard support; and
- explicit citizen help, feedback, grievance, or correction paths.

Sahaayak should match this shared language, not reproduce any portal pixel for
pixel.

## 4. Product design principles

Every design decision MUST support these principles.

### 4.1 Task first

The primary task is to ask for help by speaking or typing, understand relevant
benefits or jobs, verify the evidence, and know what to do next. Campaign
banners, vanity metrics, and secondary information must not displace this task.

### 4.2 Trust through evidence

Official source organization, source link, last verified date, current validity,
review status, uncertainty, and the independent-guidance disclaimer are part of
the result - not hidden in a policy page.

### 4.3 Voice and text parity

Voice is the lead interaction, but every voice action MUST have a visible text
equivalent. A user who cannot speak, hear, grant microphone permission, or use
audio in their environment must still complete the journey.

### 4.4 Language is a service setting

Language selection affects interface copy, screen-reader language, STT, TTS,
validation, dates, and content availability. It is not merely a translation
overlay. Geography and language remain independent settings.

### 4.5 Low confidence must be visible

The interface must distinguish “likely relevant”, “more information needed”,
“does not appear to match”, and “source needs review”. It must not turn an AI
confidence number into an official eligibility decision.

### 4.6 Design for constrained access

The default experience MUST work on low-end Android devices, narrow screens,
intermittent networks, lower digital literacy, keyboard-only input, screen
readers, and 200% browser zoom.

### 4.7 Progressive disclosure

Ask one group of related questions at a time. Explain why sensitive data is
needed. Reveal advanced detail on request while keeping source and uncertainty
visible.

## 5. Identity, affiliation, and trust marks

The [State Emblem of India (Prohibition of Improper Use) Act, 2005](https://www.mha.gov.in/sites/default/files/STATE_EMBLEM_ACT2005.pdf)
prohibits unauthorized use that creates an impression of relation to the
Government. UX4G also states that using its design system does not imply
government endorsement or affiliation.

### 5.1 Required Sahaayak identity

- Use the Sahaayak wordmark and product mark only.
- Place a short descriptor next to or below the wordmark, such as
  **“Independent guidance for public benefits and jobs.”**
- Display **“Not a government website”** in the footer and on the transparency
  page. Display the fuller disclaimer at decision-sensitive points:
  **“Sahaayak provides independent guidance. The responsible department makes
  the final eligibility or recruitment decision.”**
- Attribute every government record to its responsible department and link to
  the official source. Attribution is content provenance, not Sahaayak branding.
- Clearly mark external official links, open them safely, and state that the
  user is leaving Sahaayak.

### 5.2 Prohibited without written authorization

- the State Emblem of India or a colourable imitation;
- a national-flag masthead or decorative tricolour intended to signal official
  status;
- “Government of India”, ministry, department, state, Digital India, or programme
  logos in Sahaayak's identity lockup;
- a `gov.in`/`nic.in` visual treatment or ownership statement;
- text such as “official”, “government approved”, “certified”, or “in
  partnership with” without documented authorization; and
- copying an official site's logo spacing, emblem header, seal, or footer
  lineage.

If a government partnership is established later, create a separately approved
co-branding specification. Do not silently modify this independent-product
system.

## 6. Colour system

### 6.1 Theme direction

The default citizen and admin experiences MUST use a light theme. White is the
main page and card surface, linen is the subtle grouping surface, and dark text
provides a document-like public-service feel. Dark mode MAY be offered as a user
preference, but it must not be the default.

Sahaayak adopts the DBIM Blue group as its single primary group:

| Token | DBIM value | Sahaayak use |
| --- | --- | --- |
| `brand-900` | `#162F6A` | Masthead/footer, highest-emphasis text, selected navigation |
| `brand-700` | `#214AAB` | Primary buttons, links, active controls |
| `brand-500` | `#5279D7` | Large graphics, charts, non-text accents only |
| `brand-200` | `#A3BBF3` | Borders, focus-adjacent tint, illustration accents |
| `brand-100` | `#D2DFFF` | Selected/tinted backgrounds |

Use the DBIM functional palette as the source of neutral and status roles:

| Role | Value | Usage rule |
| --- | --- | --- |
| Inclusive white | `#FFFFFF` | Primary background and text on dark brand surfaces |
| Linen | `#EBEAEA` | Subtle background, callout or image surround |
| Deep earthy brown | `#150202` | Default text on light surfaces |
| Grey 01 | `#C6C6C6` | Borders and dividers |
| Grey 02 | `#8E8E8E` | Disabled graphics only; not normal text on white |
| Grey 03 | `#606060` | Secondary text |
| Liberty green | `#198754` | Success/verified only |
| Mustard yellow | `#FFC107` | Warning/attention background with dark text |
| Coral red | `#DC3545` | Error/destructive only |
| Information blue | `#0D6EFD` | Information and focus/link use where appropriate |

Do not use colour names directly in components. Use semantic tokens:

```css
:root {
  --background: #ffffff;
  --foreground: #150202;
  --card: #ffffff;
  --card-foreground: #150202;
  --popover: #ffffff;
  --popover-foreground: #150202;

  --primary: #214aab;
  --primary-foreground: #ffffff;
  --secondary: #d2dfff;
  --secondary-foreground: #162f6a;
  --muted: #ebeaea;
  --muted-foreground: #606060;
  --accent: #a3bbf3;
  --accent-foreground: #162f6a;

  --success: #198754;
  --success-foreground: #ffffff;
  --warning: #ffc107;
  --warning-foreground: #150202;
  --destructive: #dc3545;
  --destructive-foreground: #ffffff;
  --info: #0d6efd;
  --info-foreground: #ffffff;

  --border: #c6c6c6;
  --input: #606060;
  --ring: #0d6efd;
}
```

### 6.2 Contrast guardrails

GIGW/WCAG requires at least 4.5:1 for normal text, 3:1 for large text, and
3:1 for meaningful interface components and graphics.

- `#150202` on white is approximately 20.16:1.
- `#162F6A` on white is approximately 12.74:1.
- `#214AAB` on white is approximately 7.98:1.
- `#5279D7` on white is approximately 4.14:1 and MUST NOT be used for normal
  text.
- `#8E8E8E` on white is approximately 3.28:1 and MUST NOT be used for normal
  or helper text.
- Green, red, and information blue are close to the 4.5:1 boundary on white.
  Use them for short status labels/icons and pair them with an icon and plain
  text. Use `#150202` for longer explanatory text.
- Warning yellow MUST use dark text; never white text.
- Focus MUST remain visible on every surface. Use a 4px information-blue ring
  with a 2px contrasting offset, or an equivalent dual-colour treatment.
- Every new token pair MUST be checked automatically and manually, including
  hover, focus, active, disabled, high-contrast, forced-colours, and dark modes.

### 6.3 Colour behaviour

- Never communicate eligibility, freshness, risk, recording, or validation by
  colour alone. Pair colour with text and an icon or pattern.
- Green is reserved for verified/success states. It is not a general brand
  colour.
- Red is reserved for errors and destructive actions. It is not used for
  ordinary “not matched” guidance, which should use neutral or warning styling.
- Gradients MAY use two variants from the Blue group but SHOULD be rare and
  MUST not sit behind long text.
- Do not use neon, glassmorphism, blurred colour blobs, or decorative glows on
  citizen task screens.

### 6.4 High contrast and dark mode

- Accessibility controls supplement an accessible base implementation; they
  do not replace semantics, contrast, or testing.
- A high-contrast preference MUST preserve status labels, focus, borders, form
  errors, charts, and voice state.
- Respect `prefers-color-scheme`, `prefers-contrast`, `forced-colors`, and the
  user's explicit saved preference.
- Dark mode tokens require a separate contrast audit. Do not mechanically
  invert the light palette.

## 7. Typography and multilingual fonts

DBIM specifies Noto Sans for the Government of India's digital presence and
regional scripts. UX4G 3.0 uses Noto Sans for all interface text and reserves
Noto Sans Display for large display styles.

### 7.1 Font families

- **MUST:** Noto Sans for body, controls, headings, tables, and navigation.
- **MAY:** Noto Sans Display for exceptional English/Hindi campaign-style
  headings at 36px or larger. Sahaayak normally does not need it.
- **MUST NOT:** use Manrope, DM Mono, serif display type, handwritten type, or a
  decorative font in the citizen experience.
- Monospace MAY be used in admin-only technical values such as request IDs,
  hashes, or JSON. It must not be used for citizen metadata, labels, or
  navigation.
- Use weights 400, 500, 600, and 700 only.

Recommended locale stacks:

| Script/languages | First-choice family |
| --- | --- |
| Latin/English | `Noto Sans` |
| Devanagari/Hindi/Marathi | `Noto Sans Devanagari` |
| Kannada | `Noto Sans Kannada` |
| Tamil | `Noto Sans Tamil` |
| Telugu | `Noto Sans Telugu` |
| Bengali | `Noto Sans Bengali` |
| Gujarati | `Noto Sans Gujarati` |
| Malayalam | `Noto Sans Malayalam` |
| Gurmukhi/Punjabi | `Noto Sans Gurmukhi` |
| Odia | `Noto Sans Oriya`/the current upstream Noto family name |

```css
font-family: var(--font-locale), "Noto Sans", system-ui, sans-serif;
```

Self-host versioned WOFF2 subsets from the same origin. Use `font-display: swap`,
preload only the active locale's critical regular and semibold files, and retain
the system fallback. A third-party Google Fonts request MUST NOT be required for
first render or for a regional script to display.

### 7.2 Sahaayak type scale

This subset is compatible with DBIM's common scale and UX4G's richer tokens.
Sizes use `rem` in implementation and are listed in pixels at a 16px root.

| Role | Desktop size/line | Mobile size/line | Weight | Typical use |
| --- | --- | --- | --- | --- |
| Page H1 | 36/44 | 24/32 | 600-700 | One page title |
| Section H2 | 24/32 | 20/28 | 600-700 | Major section |
| Subsection H3 | 20/28 | 18/24 | 600 | Card group/form section |
| Component title | 18/24 | 16/24 | 600 | Card/dialog title |
| Body large | 18/28 | 16/24 | 400 | Important instructions |
| Body/default | 16/24 | 16/24 | 400 | Default citizen copy |
| Helper/secondary | 14/20 | 14/20 | 400-500 | Field help and metadata |
| Caption | 12/16 | 12/16 | 400-500 | Timestamps/legal detail only |
| Button/label | 16/20 or 14/20 | same | 600 | Controls |

### 7.3 Typography rules

- Default body text is 16px with 1.5 line height.
- Body copy is left-aligned. Do not justify paragraphs.
- Use one `<h1>` per page and do not skip heading levels.
- Use sentence case. Do not use all-caps paragraphs, labels, navigation, or
  tracking-heavy “kickers”.
- Keep body measure to approximately 65-75 characters or 720px.
- Avoid negative letter spacing for Indic scripts. Do not force fixed heights
  that clip vowel marks, conjuncts, or larger line boxes.
- Tables left-align text, right-align numbers, and use clearly associated column
  headers. Do not center all cell content.
- Text must remain usable with browser zoom at 200% and the WCAG text-spacing
  overrides: 1.5 line height, 2x paragraph spacing, 0.12em letter spacing, and
  0.16em word spacing where supported by the script.
- Use actual text, not images of text, for banners, buttons, status, and
  instructions.

## 8. Spacing, layout, radius, and elevation

UX4G uses a base-4 spacing rhythm with 2px fine adjustments. Sahaayak uses this
reduced semantic scale:

| Token | Value | Use |
| --- | --- | --- |
| `space-1` | 4px | Tight icon/detail offset |
| `space-2` | 8px | Inline controls, compact stack |
| `space-3` | 12px | Control internals |
| `space-4` | 16px | Default component padding/gap |
| `space-5` | 24px | Card padding, related block gap |
| `space-6` | 32px | Subsection separation |
| `space-7` | 48px | Page section separation |
| `space-8` | 64px | Large desktop section separation |
| `space-9` | 80px | Exceptional landing-page separation |

### 8.1 Grid and container

- Start at 320 CSS pixels and enhance progressively.
- Use one-column task flows on mobile and for forms at every practical width.
- Use a 12-column desktop grid only where it improves alignment.
- Cap standard content at 1200px and wide admin/data layouts at 1320px.
- Cap paragraph/instruction content at 720px.
- Use 16px horizontal page padding at 320-575px, 24px at tablet widths, and
  32px-48px on desktop.
- Critical content MUST reflow at 320 CSS pixels without two-dimensional
  scrolling. Data tables may scroll horizontally only with a visible cue and an
  accessible card/list alternative where practical.

### 8.2 Touch and control sizing

- Interactive targets MUST be at least 44x44px on mobile and SHOULD remain that
  size on desktop.
- Maintain at least 8px between adjacent touch targets.
- Inputs and primary buttons SHOULD be 44-48px high.
- Do not place two destructive or mutually exclusive actions too close together.

### 8.3 Corner radius

Use the UX4G radius vocabulary:

- 4px: inputs, compact controls, table cells;
- 8px: buttons, cards, alerts;
- 12px: large panels and dialogs;
- full/pill: badges, tags, switches, and circular avatars only.

Do not make every button and navigation item a pill. Restrained geometry feels
more like a dependable service and improves alignment in translated layouts.

### 8.4 Elevation

- Prefer whitespace and `#C6C6C6` borders before shadows.
- Resting cards use no shadow or UX4G Level 1.
- Dropdowns and raised interactive panels may use Level 2.
- Popovers use Level 3; dialogs use Level 4.
- Never use elevation as the only indication of clickability or active state.

## 9. Icons and imagery

### 9.1 Icons

- Use one outlined or rounded icon family across citizen surfaces. The current
  Lucide library is suitable when used consistently.
- Use filled icons only for selected/active state and do not mix filled and
  outlined icons in one toolbar.
- Default sizes are 16px for inline metadata, 20px for controls, and 24px for a
  leading action. Larger icons are reserved for empty states or categories.
- Primary navigation and important actions MUST pair an icon with visible text.
- Icon-only controls require an accessible name and a tooltip available on both
  hover and keyboard focus.
- Directional icons must use logical start/end behaviour so a future RTL locale
  can mirror them.
- Do not use emoji as the only status or functional icon.

### 9.2 Images

- Use photography or illustrations only when they help a citizen understand the
  task. Conversation and result screens do not need decorative hero imagery.
- Obtain usage rights and consent for recognizable people. Do not use
  watermarked or search-engine images without permission.
- Provide meaningful alternative text. DBIM recommends keeping ordinary alt
  text within 140 characters; longer descriptions may be used for complex
  informative images.
- Decorative images use empty alt text and must not create noisy screen-reader
  output.
- Optimize before publishing. Follow DBIM ceilings: up to 500KB for background
  or banner images, up to 100KB for thumbnails, and under 100KB for logos.
- Prefer SVG for icons, WebP/AVIF for appropriate raster imagery, and explicit
  width/height to prevent layout shifts.
- Never place essential text inside an image. Overlay real HTML text only when
  contrast remains stable at all responsive crops.

## 10. Citizen shell and information architecture

Use a predictable shell on every citizen route.

```text
utility bar
  skip to main content | language | accessibility | help
main masthead
  Sahaayak identity | search/find | saved | optional sign in
global navigation
  Home | Find benefits | Government jobs | Saved | Help
page context
  breadcrumb/back | page title | freshness or task status
main content
footer
  independent status | policies | accessibility | feedback | contact | version/update
```

### 10.1 Utility bar

- The first focusable control MUST be “Skip to main content”.
- Language, accessibility, and help controls MUST be text-labelled and remain in
  the same relative position across pages and languages.
- Search MAY be in the utility/masthead area but must have a visible label or
  accessible name and a sufficient input width.
- Text-size or contrast controls MAY be provided, but native browser zoom and
  semantic accessibility must still work.

### 10.2 Masthead and navigation

- Keep the Sahaayak mark, name, and independent descriptor visible.
- Desktop global navigation uses at most five primary items.
- Mobile uses a menu or at most four bottom-navigation destinations: Home,
  Conversation, Saved, and Help. Language and privacy must not be hidden only in
  bottom navigation.
- Mark the current destination with `aria-current="page"` and a non-colour cue.
- Do not use a mega-menu for the citizen product.
- Use breadcrumbs on benefit/job detail, saved task detail, policy, and admin
  drill-down pages. Preserve prior search/conversation state on return.

### 10.3 Search and discovery

- Search supports benefits, scholarships, and government jobs with clear type,
  state, department, and validity filters.
- Search SHOULD support active languages and spelling/synonym tolerance.
- A no-results state suggests corrections, broader filters, a voice/text retry,
  and human help. It must not be an empty panel.
- Users can report a wrong or missing result from search and detail views.
- Do not expose internal terms such as vector search, RAG, embeddings, intent,
  or provider names in citizen copy.

### 10.4 Footer

Every citizen page MUST include:

- “Sahaayak is an independent guidance service, not a government website”;
- About and Transparency;
- Accessibility statement and accessibility feedback;
- Privacy, consent settings, terms, and source/hyperlink policy;
- Help, contact, and report incorrect information;
- data coverage and review policy;
- application version/deployment identifier; and
- “Page updated” or, for content pages, “Information last verified”.

Do not use the DBIM government ownership lineage. Write Sahaayak's actual owner
and operator transparently.

## 11. Page templates

### 11.1 Home and conversation

Priority order:

1. One clear H1 explaining the service.
2. Equal, obvious “Speak” and “Type” actions.
3. Current language and state, with a short coverage statement.
4. A short microphone/privacy explanation before recording.
5. Conversation and transcript.
6. Relevant results and sources.
7. Saved work, reminders, and human-help paths.

Avoid a huge marketing headline, animated decorative background, loaded-record
count as the main trust signal, or long feature lists before the task.

### 11.2 Result list

Each result card MUST show:

- name and type: scheme, scholarship, or government job;
- responsible department/organization;
- state/central scope;
- match state in plain language;
- one or two reasons for relevance or uncertainty;
- application/closing date when applicable;
- verification/freshness status;
- official source link; and
- explicit actions: View details, Save, Compare, or Report.

The card title is a link. Do not make an entire card an unlabeled click target.
Do not truncate critical eligibility, closing-date, or uncertainty content.

### 11.3 Benefit detail

Use this order:

1. Breadcrumb and back-to-results action.
2. Benefit name, department, state/central scope, verification and freshness.
3. “What this may mean for you” with why matched, why uncertain, and missing
   information at criterion level.
4. Benefit offered.
5. Eligibility criteria with source-backed evidence.
6. Required documents as a trackable checklist.
7. Application steps and official apply link.
8. Dates, exceptions, renewal rules, and contact/help centre.
9. Official source, source document, last verified date, reviewer state, and
   report-incorrect action.
10. Save, compare, share, reminder, and talk-to-a-person actions.

Never place “Apply” before the user can see the source and key limitations.

### 11.4 Government-job detail

Show organization, post title, employment type, location, vacancies, category,
age, qualification, fee, pay level, important dates, selection process,
documents, official notification, application link, fraud warning, and source
freshness. Clearly distinguish a job notification from a third-party listing.
Expired jobs remain in archive/search history but cannot appear as open.

### 11.5 Saved work, checklists, and reminders

- Group by “To do”, “Waiting”, “Completed”, and “Expired/closed”.
- Every task has a plain action, due date, source, and completion state.
- Reminder channel, consent, delivery state, and opt-out are visible.
- Destructive actions offer undo or confirmation and never rely on swipe alone.
- Guest data expiry is explained before saving sensitive work.

### 11.6 Admin and operator pages

The workforce shell uses the same fonts, semantic colours, focus, component
states, and accessibility rules. It may use denser spacing, sharper icons, and
wide tables where justified.

- Keep role, environment, deployment version, and data-redaction state visible.
- Use a persistent side navigation on wide screens and an accessible disclosure
  menu on narrow screens; avoid a long horizontal pill scroller.
- Tables need captions, sortable-header announcements, filters, pagination,
  empty/error states, and a mobile alternative.
- Destructive controls show scope, impact, reason, confirmation, audit ID, and
  rollback where supported.
- Charts require a text summary and data table.
- Sensitive fields are redacted by default and reveal actions are authorized and
  audited.

## 12. Component and interaction standards

### 12.1 Buttons and links

- Buttons perform actions; links navigate.
- Use action-led labels, normally one to three words: “Find benefits”, “Save”,
  “Listen again”, “View source”.
- One primary action per section. Secondary actions have less visual weight.
- Destructive actions are red and text-labelled; cancel is never red.
- Support default, hover, focus, active, loading, disabled, success, and error
  states without layout shifts.
- A disabled button is not the only explanation. State what is missing nearby.
- Links are underlined by default in body copy or gain an equally persistent
  non-colour cue. External links include text or an icon with accessible context.

### 12.2 Cards

- Use 8px radius, a visible border, and little or no shadow.
- Use hierarchy and whitespace rather than several tinted backgrounds.
- Keep one card about one subject or task.
- Interactive cards need an explicit title/action and visible focus treatment.
- Do not nest multiple clickable cards or place essential actions on hover only.

### 12.3 Badges and statuses

- Badges contain short nouns/adjectives such as “Verified”, “Needs review”,
  “Closing soon”, or “Central”.
- Pair status colour with readable text and, where important, an icon.
- Do not show machine enums (`human_verified`, `needs_review`) directly.
- Do not use a badge for a sentence or important warning; use an alert/callout.

### 12.4 Alerts, toasts, and status changes

- Inline alerts stay near the affected task and explain what happened and what
  to do next.
- Use `role="alert"` only for urgent errors; use `role="status"` or polite live
  regions for ordinary progress and success.
- Toasts do not contain the only copy of important information and remain long
  enough to read. Provide a persistent activity/history location for delivery
  status and long-running ingestion/admin jobs.

### 12.5 Forms

Follow DBIM and GIGW form guidance:

- Give short instructions and document requirements before the form.
- Arrange fields vertically, normally one field per line.
- Group related controls with `<fieldset>` and `<legend>`.
- Place short sentence-case labels above fields; placeholders never replace
  labels.
- Mark required fields in text and programmatically. Mark optional fields
  consistently.
- Use correct input types, `autocomplete`, input purpose, mobile keyboard, and
  locale-safe parsing.
- Prefer radio buttons for up to six short mutually exclusive options. Do not
  preselect a value where it could cause an unintended declaration or consent.
- Use conditional questions to reduce burden, but do not unexpectedly move or
  erase prior answers.
- Validate on submit or field exit, not on every keystroke.
- Error text identifies the field, explains the problem, and gives a correction.
  Use `aria-invalid`, `aria-describedby`, and an error summary linked to fields.
- Long or sensitive forms use logical steps, save progress, show a progress cue,
  and provide a review/correct screen before final submission.
- Submission shows progress and prevents duplicate actions without trapping the
  user.

### 12.6 Tables

- Use tables only for data, never layout.
- Provide `<caption>`, column/row headers and correct `scope`.
- Keep structures simple; avoid merged cells where possible.
- Right-align comparable numbers and currency.
- On mobile, use a labelled card/list alternative or an explicitly scrollable
  region with a visible cue.

### 12.7 Dialogs and disclosures

- Prefer an inline page for complex work. Use a dialog only when context must be
  retained.
- Move focus into a dialog, trap it while open, close with Escape, and return
  focus to the trigger.
- Give dialogs a visible title and accessible description.
- Disclosure/accordion triggers expose `aria-expanded` and remain keyboard
  operable. Important source or eligibility limitations must not be collapsed by
  default.

### 12.8 Loading, empty, offline, and error states

- Skeletons match final geometry and are hidden from assistive technology.
- Announce long-running status without continuously interrupting a screen
  reader.
- Empty states explain why the area is empty and provide one useful next action.
- Offline/error states preserve typed text or recorded transcript where safe,
  offer retry, and explain whether submission happened.
- Never show raw stack traces, provider errors, or request payloads to citizens.
  A short request/reference ID may be offered for support.

### 12.9 Motion

- Use motion for state continuity and feedback, not decoration.
- Standard transitions are 120-240ms. Avoid parallax, auto-advancing hero
  carousels, repeated pulsing, and blocking entrance animations.
- Any automatically moving or updating content lasting more than five seconds
  has pause/stop/hide controls.
- Nothing flashes more than three times per second.
- `prefers-reduced-motion` removes non-essential animation. Recording,
  processing, and result state must remain clear without motion.

### 12.10 Sahaayak motion and performance policy

The animation rules above are implemented as a product-wide policy rather than
as isolated component preferences:

- `MotionConfig reducedMotion="user"` and `prefers-reduced-motion` remove
  non-essential transforms and transitions for users who request less motion.
- Motion is limited to opacity, small positional changes, and state continuity;
  public content does not use parallax, auto-advancing carousels, decorative
  infinite loops, or hover lift effects.
- Standard timing tokens are 120ms (fast), 180ms (standard), and 240ms (slow)
  with a single ease curve. Loading animation is supplementary; its text status
  remains available to assistive technology.
- Loading indicators use static dots plus a labelled status region; they are
  never used to communicate a state that is not also expressed as text.
- Route-level code splitting keeps admin and benefit-detail code out of the
  landing route. The initial JavaScript, largest chunk, and stylesheet are
  checked against a repeatable build budget.
- Regional font files outside the default English/Hindi/Kannada path load on
  locale selection, so language coverage does not make every first visit pay
  the download cost.

This matches the Government of India's moving-content and flashing checks in
GIGW 3.0, the UX4G guidance to respect `prefers-reduced-motion`, and WCAG's
Pause, Stop, Hide requirement. Loading indicators must remain labelled with a
status role; motion is never the only signal.

## 13. Voice, audio, and AI-specific UX

This section adapts GIGW's media, keyboard, status, time-limit, and error rules
to Sahaayak's core voice journey.

### 13.1 Before recording

- Explain what will be recorded, why it is needed, whether it is retained, for
  how long, and how to use text instead.
- Ask for browser microphone permission only after the user activates a clearly
  labelled “Speak” control.
- Never autoplay a spoken welcome or TTS response. If audio plays for more than
  three seconds, provide independent pause/stop and volume controls.
- Display current language and make changing it possible before recording.

### 13.2 During recording

- Show “Listening” as text, microphone icon, high-contrast state, and elapsed
  time. Animation is supplementary.
- Provide Stop and Cancel controls with at least 44x44px targets.
- Announce recording state changes through a polite live region.
- Barge-in/interruption behaviour must not discard the user's speech silently.
- If VAD is used, explain automatic stopping and allow manual control.

### 13.3 Transcript and submission

- Display the transcript before submission when recognition is uncertain or the
  user has enabled review.
- Allow editing, replaying the source clip where retained, retrying, submitting,
  or switching to text.
- Mark low-confidence words without colour alone and never auto-correct a
  sensitive fact such as income, caste/category, disability, age, or district
  without confirmation.
- Preserve the edited transcript in the conversation; do not replace it later
  with the unedited STT output.

### 13.4 Spoken response

- Render the full text response and source links before or with TTS.
- Provide Play/Pause, Stop, Replay, speed, and mute. Do not hide the text when
  audio is playing.
- Break long responses into useful sections and read the decision summary before
  secondary detail.
- Pronounce department, scheme, district, currency, dates, and acronyms using a
  reviewed locale glossary.
- When TTS fails, retain the complete text and a retry action.

### 13.5 AI and RAG transparency

- Label the response as Sahaayak guidance, not a department decision.
- Distinguish structured matcher evidence from a generated explanation.
- Cite official sources next to the claim they support and expose source title,
  department, date, excerpt/context, and last verification.
- Do not present an unexplained numeric confidence score as citizen-facing
  certainty. Use “Strong match”, “Possible match”, or “More information needed”
  with criterion-level reasons. Raw confidence may remain in admin/evaluation
  views.
- If sources conflict, are stale, or are not human approved, say so and avoid a
  final eligibility claim.
- Offer “Report incorrect information” and “Talk to a person” from every
  consequential result.

## 14. Content design and terminology

DBIM requires concise, impartial, simple, grammatically correct content and
British English. UX4G recommends a Class 8-10 reading level.

### 14.1 Writing rules

- Write directly to the user using familiar words.
- Keep one main idea per sentence and short paragraphs.
- Use bullets for steps, documents, and criteria.
- Use British English in the English UI.
- Expand uncommon acronyms on first use.
- Avoid legalese, department jargon, internal product terminology, blame, and
  promotional superlatives.
- Use sentence case for headings, labels, buttons, and table headers.
- Do not use Hinglish in reviewed formal UI or benefit content. Code-mixed user
  input is supported and must not be treated as an error.
- State limitations positively and actionably.

Examples:

| Avoid | Prefer |
| --- | --- |
| “Authentication failed” | “The code is incorrect. Try again or request a new code.” |
| “Invalid input” | “Enter a 10-digit mobile number.” |
| “Beneficiary is ineligible” | “Your answers do not currently match this rule.” |
| “Click here” | “View official source” |
| “Initiate escalation” | “Talk to a person” |
| “RAG source unavailable” | “We could not check the official source. Try again later.” |
| “You failed to provide income” | “Enter annual household income to continue.” |

### 14.2 Dates, numbers, and currency

- Store ISO dates and canonical numbers; format with `Intl` for the active
  locale.
- Use day before month in English display, for example `9 August 2026`.
- Use the Indian digit grouping system where appropriate, for example
  `₹1,50,000`, and include a spoken form suitable for the locale.
- Do not rely on relative dates alone. “Closes tomorrow” also shows the full
  date and time zone.
- State whether income is individual, household, monthly, or annual.

## 15. Multilingual and localisation system

### 15.1 Language selector

- Place the selector in the utility header on every page.
- Display native name first and English name second where useful, for example
  `ಕನ್ನಡ · Kannada`.
- Persist an explicit choice but let the user change it without losing route,
  scroll position, form data, conversation, or audio state where safe.
- Browser language may suggest a locale; it must not silently override the user.
- Communicate whether UI, voice, and verified content are fully supported,
  preview, or unavailable for the selected language.

### 15.2 Technical requirements

- Use Unicode throughout. No legacy font encodings or text-as-image.
- Set `<html lang>` and passage-level `lang` correctly.
- Use stable locale-specific URLs or query/state that can be linked and restored.
  Add `hreflang` and locale-specific sitemap entries for indexable pages.
- Use logical CSS properties (`margin-inline`, `padding-inline`, `inset-inline`)
  so future RTL support does not require a layout rewrite.
- Search, filters, validation, accessible names, metadata, and status messages
  are localized, not only page copy.
- Use a terminology glossary for scheme, job, legal, geography, and voice
  pronunciation. The same concept uses the same reviewed translation throughout.

### 15.3 Translation governance

- Machine translation may create a draft but cannot activate eligibility rules,
  legal/privacy copy, application instructions, or consequential warnings.
- Use states such as `draft`, `machine_assisted`, `reviewed`, `approved`,
  `active`, and `superseded` with reviewer/date/version metadata.
- When reviewed localized content is missing, show the reviewed English source
  with a visible fallback label. Do not silently display an unreviewed
  translation.
- Update active languages together. If synchronization is not possible, show
  the translation status and date.
- Let users report a translation or pronunciation error.

### 15.4 Locale QA

For each active locale, test:

- all routes at 320px, tablet, and desktop;
- 200% zoom and text-spacing overrides;
- missing glyphs, conjuncts, clipping, wrapping, and mixed-script text;
- keyboard and screen-reader pronunciation;
- date, number, currency, pincode, mobile number, and acronym formatting;
- STT/TTS pronunciation with native speakers;
- pseudo-localized long strings before human translation; and
- screenshots of critical citizen and admin states.

## 16. Accessibility requirements

GIGW 3.0 is based on WCAG 2.1 and the Rights of Persons with Disabilities Act,
2016. UX4G's accessibility controls explicitly do not replace semantic HTML,
contrast, and assistive-technology testing.

### 16.1 Perceivable

- Text contrast: 4.5:1 normal, 3:1 large.
- UI component and meaningful graphic contrast: 3:1.
- Text resizes to 200% without loss of content or function.
- Reflow works at 320 CSS pixels without horizontal page scrolling.
- Information never relies on colour, shape, size, visual location, animation,
  or sound alone.
- Images have appropriate alt text; decorative images have empty alt.
- Prerecorded audio has an equivalent transcript. Synchronized video has
  captions and required audio description/alternative.
- Text remains usable under WCAG text-spacing overrides.

### 16.2 Operable

- All functionality works with keyboard alone, with no keyboard trap.
- Focus order follows reading/task order; avoid positive `tabindex`.
- Every interactive element has a clearly visible focus indicator.
- Skip links bypass repeated header/navigation.
- Links have meaningful purpose; provide more than one way to locate major
  pages.
- Timers warn users and allow extension as required. Guest/session expiry must
  not erase unsaved work without warning.
- Moving, scrolling, blinking, or auto-updating content can be paused/stopped.
- Pointer gestures have a single-pointer alternative; drag has button/keyboard
  controls.
- Touch targets meet the 44x44px product minimum.

### 16.3 Understandable

- Each page has a unique descriptive title and one clear H1.
- Navigation and repeated components remain in the same relative order.
- Focus or changing a select value does not unexpectedly navigate or submit.
- Labels and instructions are visible and specific.
- Errors are text-based, associated with fields, and include correction advice.
- Consequential submissions can be reviewed, corrected, confirmed, or reversed
  where practical.
- The page and content language are programmatically identified.

### 16.4 Robust

- Use semantic `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, and
  `<footer>` landmarks appropriately.
- Use native controls before ARIA. Buttons are `<button>`; navigation is `<a>`.
- Names, roles, values, expanded/selected/current state, and status updates are
  available to assistive technology.
- Dynamic messages use suitable live regions without excessive interruption.
- Headings, lists, forms, and tables retain meaning when CSS fails to load.
- Validate HTML and avoid duplicate IDs.

### 16.5 Accessibility help and statement

Publish an Accessibility page linked from every footer that includes:

- supported standards and the date/scope of the last audit;
- keyboard, screen-reader, text-size, contrast, motion, caption, and language
  help;
- known limitations and accessible alternatives;
- a response-owned accessibility feedback route; and
- supported browsers, operating systems, and assistive technologies based on
  actual testing rather than “best viewed at” language.

## 17. Privacy, consent, and sensitive-data UX

The [Digital Personal Data Protection Act, 2023](https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf)
requires consent, where used as the basis for processing, to be free, specific,
informed, unconditional, unambiguous, and expressed through clear affirmative
action. Consent requests must be in clear/plain language, available in English
or an Eighth Schedule language, and withdrawal should be comparably easy.

- Explain data purpose immediately before collection, particularly for voice,
  income, caste/category, disability, location, mobile number, and documents.
- Collect the minimum information needed for the current task.
- Separate required processing from optional analytics, personalization,
  reminders, and marketing. No pre-checked optional consent.
- “Accept all”, “Reject optional”, and “Choose settings” have comparable visual
  prominence when a consent banner is needed.
- Show what will happen if the user declines; provide a text or in-app fallback
  wherever possible.
- Keep consent, reminders, voice retention, and contact-channel preferences
  reviewable and withdrawable from one settings page.
- Do not use dark patterns, guilt, urgency, or colour imbalance to obtain consent.
- Explain guest-session duration and deletion. Signing in is requested only
  when it provides clear persistence or protected functionality.
- Sensitive values are masked where possible and never repeated unnecessarily in
  audio, notifications, URLs, analytics, or page titles.
- Before external WhatsApp/SMS/email/phone handoff, show destination, data
  shared, purpose, channel cost possibility, and consent/opt-out status.

## 18. Performance and resilience

DBIM emphasizes loading performance, interaction responsiveness, visual
stability, mobile responsiveness, lazy loading, resource optimization, and
ongoing monitoring.

- Render meaningful text and the primary action without waiting for voice,
  analytics, animation, or admin bundles.
- Self-host and subset fonts. Do not block render on Google Fonts.
- Lazy-load below-the-fold media and route-level admin code.
- Reserve image/audio geometry to prevent layout shift.
- Limit third-party scripts and defer non-essential analytics.
- Cache immutable static assets and use resilient API retry rules with bounded
  backoff.
- Preserve text drafts locally during transient failures. Explain whether an
  audio turn was uploaded before offering retry.
- Provide an offline/poor-network state with text-first guidance, saved source
  links, and a later retry path. Do not pretend that live eligibility was checked.
- Monitor loading, interaction latency, layout stability, STT first partial,
  first answer text, first TTS audio, source retrieval, and error recovery by
  device, language, and network class without logging sensitive transcript text.

Internal performance targets for the critical citizen journey:

- Largest Contentful Paint at or below 2.5s at the 75th percentile;
- Interaction to Next Paint at or below 200ms at the 75th percentile;
- Cumulative Layout Shift at or below 0.1;
- visible text composer usable before optional microphone/voice setup; and
- a low-bandwidth test profile included in release QA.

These numeric targets are Sahaayak product targets, not quoted DBIM certification
thresholds.

## 19. Implementation architecture for this repository

Keep React, Tailwind v4, shadcn/Radix primitives, TanStack Router/Query, Zustand,
Zod, Motion, Lucide, and the current voice hooks. Match the official system by
changing tokens, composition, content, and behaviour rather than mixing a second
global CSS framework into the application.

Do not import the complete UX4G CSS bundle alongside Tailwind/shadcn without an
isolated compatibility evaluation; global resets, class collisions, duplicate
component APIs, and bundle cost would make the system harder to govern. UX4G
patterns and tokens can be adapted into the existing component layer.

### 19.1 File-level work map

| Area | Primary files | Required change |
| --- | --- | --- |
| Theme and font foundation | `apps/web/src/index.css`, `apps/web/public/fonts/*` | Remove remote Manrope/DM Mono import; self-host Noto subsets; add light DBIM Blue semantic tokens, dark/high-contrast overrides, focus and print rules |
| Core components | `apps/web/src/components/ui/*` | Standardize 44px targets, 4/8/12px radius, button/link states, semantic status variants, labels, errors, dialogs and table patterns |
| Citizen shell | `apps/web/src/components/app/*`, router root | Add skip link, utility bar, main masthead/nav, breadcrumbs, full footer, mobile navigation and independent-status copy |
| Home/conversation | `apps/web/src/routes/home.tsx`, conversation components | Replace marketing-heavy dark hero with task-first light layout; preserve streaming voice, transcript editing, status live regions and text fallback |
| Benefit/job detail | `benefit-detail-page.tsx` and related components | Reorder around trust, criterion evidence, documents/tasks, source/freshness, report, save/compare/share and human help |
| Saved/reminders | saved/contact components | Add task statuses, due dates, consent/delivery/opt-out clarity and guest retention messaging |
| Admin shell | `admin-shell.tsx`, `admin-pages.tsx` | Light accessible operations shell, responsive side navigation, table/chart alternatives, consistent forms and destructive-action confirmation |
| Localisation | `lib/i18n.ts`, `features/i18n/*` | Move remaining literals to typed locale catalogs, add reviewed metadata/fallback state, locale font mapping, metadata and formatting |
| Testing | web test/e2e configuration | Add contrast/token tests, axe, keyboard, screen-reader-oriented semantics, 320px/200% reflow, locale screenshots and performance budgets |

### 19.2 Token discipline

- Components consume semantic roles such as `primary`, `surface`, `border`,
  `success`, `warning`, `danger`, and `focus`, never raw colour names.
- Create typed component variants for states instead of arbitrary utility strings
  in feature files.
- Keep citizen and admin themes in one token contract with optional density
  aliases; do not fork two unrelated design systems.
- Put script and direction on the application root so every component inherits
  the active locale behaviour.
- Add Storybook or an equivalent component gallery only if it is maintained in
  CI with accessibility and visual-regression checks.

## 20. Recommended migration order

### Phase 0 - foundation and safeguards

1. Add this guide as the canonical design reference.
2. Self-host Noto Sans and active script subsets.
3. Replace global tokens with the light DBIM Blue system.
4. Add automated contrast, focus, reduced-motion, 320px and 200% checks.
5. Add the independent-status and prohibited-identity rule to review checklists.

### Phase 1 - shell and primitives

1. Refactor Button, Badge, Card, Select, inputs, alerts, links, dialogs and table
   primitives.
2. Build the utility bar, masthead, navigation, breadcrumb, footer, mobile
   navigation, Accessibility, Help, Privacy, and Transparency pages.
3. Replace route-level hard-coded colour and typography utilities with semantic
   component variants.

### Phase 2 - core citizen journeys

1. Refactor home/conversation into the task-first template.
2. Refactor result list and benefit/job details.
3. Refactor save, compare, checklists, reminders, reporting, and human handoff.
4. Complete voice permission, recording, transcript, playback, TTS and fallback
   accessibility states.

### Phase 3 - admin and multilingual hardening

1. Refactor admin navigation, forms, tables, charts, dialogs and audit actions.
2. Remove all remaining hard-coded English and build route metadata catalogs.
3. Run native-language, pronunciation, screen-reader, low-bandwidth and device
   validation for each staged locale.
4. Record evidence and activate locale/state cohorts only after release gates
   pass.

## 21. Release gates and evidence

### 21.1 Automated on every pull request

- TypeScript/typecheck and production build pass.
- No unapproved raw palette values in feature components.
- Every documented foreground/background token pair passes its contrast target.
- axe or equivalent finds no serious/critical issues on critical routes.
- Unique page title, one H1, landmarks, labels, accessible names, and duplicate
  IDs are checked.
- Keyboard smoke tests cover navigation, conversation, recording controls,
  transcript edit, result actions, forms, dialogs, admin navigation and logout.
- 320px reflow, 200% zoom approximation, reduced motion, forced colours and
  active-locale screenshots run for critical states.
- Translation keys, fallback, unsupported locale state, missing glyphs and long
  strings are checked.
- Bundle and critical performance budgets do not regress without approval.

### 21.2 Manual before a public release

- Keyboard-only review with visible focus and no traps.
- VoiceOver/Safari and TalkBack/Android at minimum; NVDA/Firefox or Chrome for a
  desktop Windows path.
- 320px mobile, low-end Android, slow/intermittent connection, 200% browser zoom,
  text spacing, orientation change and reduced motion.
- Native-speaker review for every active locale, including government terms,
  names, dates, money, districts, STT, TTS and screen-reader pronunciation.
- Voice tests with microphone denied, silence, noise, interruption, low STT
  confidence, edited transcript, TTS failure and network loss.
- Consent withdrawal, guest expiry, reminder opt-out and external handoff.
- Source/freshness, incorrect-information report, conflicting source, stale data,
  unreviewed data and human escalation.
- Admin tables, destructive actions, redaction, audit, rollback and permission
  denial.
- A usability session with citizens who have lower digital confidence and with
  people who use assistive technology.

### 21.3 Evidence to retain

- test run and commit/deployment identifier;
- browser, OS, device, assistive technology and locale;
- screenshots/video/audio where consent permits;
- issues, severity, owner, workaround and resolution;
- native reviewer and terminology/glossary version;
- accessibility statement update date; and
- sign-off for design, accessibility, content, privacy, security and product.

## 22. Current frontend gap assessment

This assessment is based on the current files in `apps/web/src` on 9 August
2026. It is a design/code audit, not a complete browser accessibility audit.

| Current implementation | Assessment | Required direction |
| --- | --- | --- |
| Dark green `#10251F` page, acid lime primary, orange accent, dark-only colour scheme | Does not match the selected public-service direction | Make light DBIM Blue the default; retain dark mode only as a tested preference |
| Remote Google Fonts import for Manrope and DM Mono | Conflicts with DBIM Noto direction and adds a render/privacy/network dependency | Self-host Noto Sans and locale subsets; reserve mono for admin technical values |
| Very large tightly tracked hero and widespread tiny uppercase mono labels | Risks readability, translation wrapping, and Indic-script clipping | Adopt the constrained type scale, sentence case, 16px default body and 14px helper minimum |
| Decorative blurred colour fields and marketing entrance motion | Adds visual noise before the citizen task | Remove from task screens; keep only restrained functional transitions |
| Pill buttons/navigation and rounded-2xl cards throughout | More consumer/SaaS than restrained public service | Use 8px buttons/cards, 4px inputs, 12px dialogs; pills only for tags/badges |
| Skip-to-conversation, semantic sections, live status regions and reduced-motion CSS | Good foundation | Generalize skip-to-main, verify focus order/live-region behaviour and retain during refactor |
| Voice streaming, VAD, transcript editing, text fallback and visible result/source panels | Strong functional foundation | Recompose into the voice accessibility and trust template without removing capability |
| Benefit details include evidence, source, freshness, report/share/save/compare functions | Strong functional foundation | Reorder content and restyle status, dates, documents, tasks and source blocks |
| Top bar shows brand and technical guest/API state only | Incomplete public-service shell | Add utility bar, language/accessibility/help, task navigation and clearer privacy/guest wording |
| Footer contains two short product phrases | Incomplete for trust and GIGW-inspired lifecycle patterns | Add independent status, policies, help, feedback, accessibility, coverage, owner and version/update |
| Citizen route is one long homepage with downstream panels | Functional but hard to scan and return to | Add stable conversation/results/saved/help routes or anchored task states with restorable URLs |
| UI catalog exists for multiple locales but feature/admin literals remain | Localisation infrastructure is partial | Move all citizen and shared accessible text to typed reviewed catalogs; keep admin localisation policy explicit |
| Admin uses a long horizontal pill navigation and many inline form styles | Hard to scale and inconsistent with the target system | Use responsive side navigation and shared accessible form/table/action primitives |

The refactor should preserve the existing working product capabilities. It is a
visual, information-architecture, content, and accessibility migration - not a
rewrite of RAG, voice, authentication, or business logic.

## 23. Design review checklist

Before accepting a screen or component, confirm:

- [ ] The citizen can identify the page purpose and primary action immediately.
- [ ] Sahaayak's independent status is not confused with government ownership.
- [ ] No restricted emblem, flag treatment, government lockup, or implied
      endorsement is present.
- [ ] Noto Sans and the correct locale font render without clipping or missing
      glyphs.
- [ ] Colour is semantic, contrast passes, and no meaning depends on colour.
- [ ] Body text is at least 16px; helper text is at least 14px except genuinely
      non-essential 12px captions.
- [ ] The screen works at 320px, 200% zoom, text-spacing overrides, high
      contrast, reduced motion, keyboard only, and touch.
- [ ] Heading order, landmarks, labels, names, roles, focus, errors, and status
      announcements are correct.
- [ ] Voice has consent, stop/cancel, transcript, edit/retry, playback and text
      fallback.
- [ ] AI guidance shows reasons, uncertainty, source, freshness and human help.
- [ ] Forms are vertical, concise, labelled, reviewable and recoverable.
- [ ] Language switching preserves task state and clearly indicates coverage or
      fallback.
- [ ] Privacy purpose, retention, consent withdrawal and guest behaviour are
      understandable.
- [ ] Loading, empty, offline, stale, error and permission-denied states are
      designed.
- [ ] Page/footer ownership, policies, help, feedback, version and update
      information are present.
- [ ] Automated and manual evidence is attached to the release.

## 24. Official and observed references

### Official standards and design systems

- [GIGW 3.0 introduction](https://guidelines.india.gov.in/introduction/)
- [GIGW 3.0 scope and objective](https://guidelines.india.gov.in/scope-and-objective/)
- [GIGW guidelines](https://guidelines.india.gov.in/guidelines/)
- [GIGW conformity matrix](https://guidelines.india.gov.in/annexure-ii-matrix-to-check-conformity/)
- [GIGW quick tips](https://guidelines.india.gov.in/quick-tips/)
- [Digital Brand Identity Manual V3.0](https://www.stqc.gov.in/sites/default/files/2025-06/DBIM%20Manual%20V%203.0.pdf)
- [STQC DBIM compliance overview](https://www.stqc.gov.in/en/dbim-compliance-certification)
- [UX4G foundations](https://www.ux4g.gov.in/foundations?lang=en)
- [UX4G typography](https://www.ux4g.gov.in/foundations/typography)
- [UX4G spacing and layout](https://www.ux4g.gov.in/foundations/spacing)
- [UX4G iconography](https://www.ux4g.gov.in/foundations/iconography)
- [UX4G accessibility](https://www.ux4g.gov.in/foundations/accessibility)
- [UX4G spinners](https://doc.ux4g.gov.in/components/spinners.php)
- [UX4G navbar motion and reduced-motion behaviour](https://doc.ux4g.gov.in/components/navbar.php)
- [UX4G content design system](https://www.ux4g.gov.in/foundations/content-system)
- [WCAG 2.2 Pause, Stop, Hide](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide)
- [UX4G disclaimer and implementation responsibility](https://www.ux4g.gov.in/disclaimer)
- [Rights of Persons with Disabilities Act and Rules](https://depwd.gov.in/en/document-category/acts/)
- [BIS accessibility standards programme, including IS 17802 Parts 1 and 2](https://www.services.bis.gov.in/php/BIS_2.0/bisconnect/pow_new/Pow/download_pow_pdf_dept_commtt/66/424/)
- [Digital Personal Data Protection Act, 2023](https://www.meity.gov.in/static/uploads/2024/02/Digital-Personal-Data-Protection-Act-2023.pdf)
- [Ministry of Home Affairs State Emblem resources](https://www.mha.gov.in/en/documents/national-flag-emblem-anthem)

### Representative live services reviewed

- [National Portal of India](https://www.india.gov.in/)
- [myScheme](https://www.myscheme.gov.in/)
- [DigiLocker](https://www.digilocker.gov.in/)
- [MyGov](https://www.mygov.in/)
- [Mysuru district S3WaaS site](https://mysore.nic.in/)
- [Bengaluru Urban district S3WaaS site](https://bengaluruurban.nic.in/)
- [National Career Service](https://www.ncs.gov.in/)
