# LaTeX Resume

A modular, professionally designed LaTeX resume collection with **two themes** and a **Python GUI manager** for easy editing.

<p align="center">
  <img src="preview.png" alt="Resume Preview" width="600">
</p>

## Themes

| Theme | Style | Preview |
|-------|-------|---------|
| **`florian/`** | Single-column, navy/steel blue, skill tags, 2-page | Classic professional |
| **`helene/`** | Two-column sidebar, blush pink, rounded banners, 1-page | Modern feminine |

Each theme is self-contained with its own `resume.tex`, `config.tex`, `commands.tex`, and `content.tex`.

## Project Structure

```
.
├── README.md
├── LICENSE
├── preview.png
├── resume_manager.py           # GUI editor (works with any theme)
│
├── florian/                    # Single-column theme
│   ├── resume.tex              # Master document
│   ├── config.tex              # Colors, fonts, margins
│   ├── commands.tex            # LaTeX macros
│   ├── content.tex             # Resume data
│   └── content.example.tex    # Example with placeholder data
│
└── helene/                     # Two-column sidebar theme
    ├── resume.tex              # Master document
    ├── config.tex              # Colors, fonts, margins
    ├── commands.tex            # LaTeX macros
    └── content.tex             # Resume data
```

## Prerequisites

- **TeX Live 2023+** (or MiKTeX) with these packages:
  `fontenc` `inputenc` `geometry` `xcolor` `hyperref` `titlesec` `enumitem` `tabularx` `multicol` `tikz` `fontawesome5` `sourcesanspro` `ragged2e` `parskip`
- **Python 3.10+** (for the GUI manager only — not needed to compile the PDF)
- `pdflatex` on your PATH

## Quick Start

### Option 1: Edit LaTeX directly

```bash
# Clone the repo
git clone https://github.com/lumenworksco/Resume.git
cd Resume

# Pick a theme and compile
cd florian
pdflatex resume.tex && pdflatex resume.tex

# Or use the other theme
cd ../helene
pdflatex resume.tex && pdflatex resume.tex
```

To start from scratch with the single-column theme:
```bash
cd florian
cp content.example.tex content.tex
# Edit content.tex with your information
pdflatex resume.tex && pdflatex resume.tex
```

> Run `pdflatex` twice so hyperlinks and cross-references resolve correctly.

### Option 2: Use the GUI Manager

```bash
# Manage the florian/ resume (default)
python3 resume_manager.py

# Or manage a different theme
python3 resume_manager.py helene
```

The GUI has three panels:

```
┌──────────┬──────────────────┬──────────────────────────┐
│ SECTIONS │  Entry List      │  Edit Form               │
│          │                  │                          │
│ Header   │  MIT             │  Institution: [________] │
│ Profile  │  UC Berkeley (*) │  Degree:      [________] │
│ Education│                  │  Date:        [________] │
│ Experienc│  [Add] [Delete]  │                          │
│ Projects │  [↑]   [↓]      │  Bullet points:          │
│ Skills   │                  │  [________________] [Add]│
│ ...      │                  │  [Save Entry]            │
├──────────┴──────────────────┴──────────────────────────┤
│ Status: Ready                   [Save & Compile PDF]   │
└────────────────────────────────────────────────────────┘
```

Click **Save & Compile PDF** to regenerate `content.tex` and build a fresh PDF. A `.bak` backup is created before every save.

## Customization

### Colors

Edit the color palette in `config.tex` for either theme:

**Single-column theme (`florian/config.tex`):**

| Color | Default | Usage |
|-------|---------|-------|
| `primary` | Dark navy `(20, 50, 90)` | Name, headings |
| `accent` | Steel blue `(42, 98, 154)` | Links, icons, organisation names |
| `subtle` | Warm grey `(108, 117, 125)` | Dates, secondary text |
| `tagbg` / `tagtext` | Soft blue / Deep blue | Skill tag colors |

**Two-column theme (`helene/config.tex`):**

| Color | Default | Usage |
|-------|---------|-------|
| `sidebar` | Warm blush `(243, 228, 221)` | Sidebar background |
| `primary` | Deep brown `(55, 45, 42)` | Name, headings |
| `accent` | Warm rose `(180, 130, 110)` | Icons, links |
| `sectionbg` | Light blush `(238, 222, 215)` | Section heading banners |

### Fonts

The default font is **Source Sans Pro** (light weight). To change it, swap the font package in `config.tex`:

```latex
% \usepackage[default,light]{sourcesanspro}  % current
\usepackage[default]{lato}                    % alternative
```

### PDF Metadata

Update the `pdfauthor` and `pdftitle` fields in `config.tex` to match your name.

## Available Commands (Single-Column Theme)

All commands are defined in `commands.tex`. Use them in `content.tex`:

| Command | Arguments | Description |
|---------|-----------|-------------|
| `\makeheader` | `{Name}{Headline}{Contact Line 1}{Contact Line 2}` | Page header with name, headline, and contact info |
| `\contactitem` | `{\faIcon{icon}}{Text}` | Non-clickable contact item (phone, location) |
| `\contactlink` | `{\faIcon{icon}}{URL}{Label}` | Clickable contact link (email, website, LinkedIn) |
| `\contactsep` | — | Separator between contact items |
| `\education` | `{Institution}{Degree}{Date}` | Education entry |
| `\experience` | `{Title}{Organisation}{Date}{Location}` | Experience entry (follow with `\begin{bullets}`) |
| `\subrole` | `{Title}{Date}` | Additional role at the same organisation |
| `\project` | `{Title}{Date}` | Project entry (follow with `\begin{bullets}`) |
| `\organisation` | `{Organisation}{Role}{Date}{Association}` | Organisation membership |
| `\volunteer` | `{Role}{Organisation}{Date}{Category}` | Volunteering entry |
| `\skillcategory` | `{Category}{\skilltag{...}\skilltag{...}}` | Skill category with tags |
| `\skilltag` | `{Skill Name}` | Individual rounded skill badge |
| `\award` | `{Title}{Issuer}{Year}` | Honour or award |
| `\langentry` | `{Level}{Languages}` | Language proficiency entry |

### Bullet Lists

Use the `bullets` environment after `\experience`, `\project`, `\organisation`, or `\volunteer`:

```latex
\experience{Software Engineer}{Acme Corp}{2023 -- Present}{Remote}
\begin{bullets}
    \item Built a real-time data pipeline processing 1M+ events per day.
    \item Led migration from monolith to microservices architecture.
\end{bullets}
```

## License

MIT — see [LICENSE](LICENSE).
