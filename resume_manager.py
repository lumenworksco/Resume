#!/usr/bin/env python3
"""
Resume Manager — A GUI tool for editing your LaTeX resume.

Launch:  python3 resume_manager.py

Parses resume-content.tex, lets you add/edit/delete entries in a GUI,
then regenerates the .tex file and compiles the PDF.
"""

import os
import re
import shutil
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk, messagebox, simpledialog, scrolledtext

# ══════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════

@dataclass
class ContactEntry:
    entry_type: str  # "item" or "link"
    icon: str        # FontAwesome icon name, e.g. "phone-alt"
    text: str        # display text
    url: str = ""    # only for "link" type

@dataclass
class HeaderData:
    name: str
    headline: str
    contact_line_1: list  # list[ContactEntry]
    contact_line_2: list  # list[ContactEntry]

@dataclass
class EducationEntry:
    institution: str
    degree: str
    date: str

@dataclass
class SubRole:
    title: str
    date: str
    bullets: list  # list[str]

@dataclass
class ExperienceEntry:
    title: str
    org: str
    date: str
    location: str
    bullets: list  # list[str]
    subroles: list = field(default_factory=list)  # list[SubRole]

@dataclass
class ProjectEntry:
    title: str
    date: str
    bullets: list  # list[str]

@dataclass
class OrganisationEntry:
    org: str
    role: str
    date: str
    association: str
    bullets: list  # list[str]

@dataclass
class VolunteerEntry:
    role: str
    org: str
    date: str
    category: str
    bullets: list  # list[str]

@dataclass
class SkillCategory:
    category: str
    tags: list  # list[str]

@dataclass
class CertificationEntry:
    name: str
    issuer: str

@dataclass
class CourseEntry:
    name: str
    description: str

@dataclass
class AwardEntry:
    title: str
    issuer: str
    year: str

@dataclass
class LanguageEntry:
    level: str
    languages: str

@dataclass
class ResumeData:
    header: HeaderData = None
    profile: str = ""
    education: list = field(default_factory=list)
    experience: list = field(default_factory=list)
    projects: list = field(default_factory=list)
    organisations: list = field(default_factory=list)
    volunteering: list = field(default_factory=list)
    skills: list = field(default_factory=list)
    certifications: list = field(default_factory=list)
    courses: list = field(default_factory=list)
    awards: list = field(default_factory=list)
    languages: list = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════
#  TEX PARSER
# ══════════════════════════════════════════════════════════════════════════

class TexParser:
    """Parse resume-content.tex into a ResumeData object."""

    def parse(self, filepath: str) -> ResumeData:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        sections = self._split_sections(text)
        data = ResumeData()
        if "header" in sections:
            data.header = self._parse_header(sections["header"])
        if "Profile" in sections:
            data.profile = self._parse_profile(sections["Profile"])
        if "Education" in sections:
            data.education = self._parse_education(sections["Education"])
        if "Experience" in sections:
            data.experience = self._parse_experience(sections["Experience"])
        if "Projects" in sections:
            data.projects = self._parse_projects(sections["Projects"])
        if "Organisations" in sections:
            data.organisations = self._parse_organisations(sections["Organisations"])
        if "Volunteering" in sections:
            data.volunteering = self._parse_volunteering(sections["Volunteering"])
        if "Skills" in sections:
            data.skills = self._parse_skills(sections["Skills"])
        if "Certifications" in sections:
            data.certifications = self._parse_certifications(sections["Certifications"])
        if "Courses" in sections:
            data.courses = self._parse_courses(sections["Courses"])
        for key in ("Honours \\& Awards", "Honours & Awards"):
            if key in sections:
                data.awards = self._parse_awards(sections[key])
                break
        if "Languages" in sections:
            data.languages = self._parse_languages(sections["Languages"])
        return data

    def _split_sections(self, text: str) -> dict:
        """Split text into header (before first \\section) and named sections."""
        sections = {}
        # Find all \section{...} positions
        pattern = re.compile(r"\\section\{(.+?)\}")
        matches = list(pattern.finditer(text))
        if not matches:
            sections["header"] = text
            return sections
        # Everything before the first \section is the header
        sections["header"] = text[: matches[0].start()]
        for i, m in enumerate(matches):
            name = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[name] = text[start:end]
        return sections

    # ── brace / bullet helpers ───────────────────────────────────────────

    def _extract_brace_arg(self, text: str, pos: int):
        """Extract content of next {...} starting from pos. Returns (content, end_pos)."""
        while pos < len(text) and text[pos] in " \t\n\r":
            pos += 1
        if pos >= len(text) or text[pos] != "{":
            return "", pos
        depth = 0
        start = pos + 1
        i = pos
        while i < len(text):
            ch = text[i]
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i], i + 1
            i += 1
        return text[start:], len(text)

    def _extract_bullets(self, text: str, pos: int):
        """Extract bullets from \\begin{bullets}...\\end{bullets}. Returns (list, end_pos)."""
        # Skip whitespace
        while pos < len(text) and text[pos] in " \t\n\r":
            pos += 1
        begin = text.find("\\begin{bullets}", pos)
        if begin < 0 or begin > pos + 50:
            return [], pos
        end = text.find("\\end{bullets}", begin)
        if end < 0:
            return [], pos
        block = text[begin + len("\\begin{bullets}") : end]
        bullets = []
        for m in re.finditer(r"\\item\s+(.*?)(?=\\item|\Z)", block, re.DOTALL):
            bullet = m.group(1).strip()
            if bullet:
                bullets.append(bullet)
        return bullets, end + len("\\end{bullets}")

    # ── section parsers ──────────────────────────────────────────────────

    def _parse_header(self, text: str) -> HeaderData:
        idx = text.find("\\makeheader")
        if idx < 0:
            return HeaderData("", "", [], [])
        pos = idx + len("\\makeheader")
        name, pos = self._extract_brace_arg(text, pos)
        headline, pos = self._extract_brace_arg(text, pos)
        cl1_raw, pos = self._extract_brace_arg(text, pos)
        cl2_raw, pos = self._extract_brace_arg(text, pos)
        return HeaderData(
            name=name.strip(),
            headline=headline.strip(),
            contact_line_1=self._parse_contact_line(cl1_raw),
            contact_line_2=self._parse_contact_line(cl2_raw),
        )

    def _parse_contact_line(self, raw: str) -> list:
        parts = re.split(r"\\contactsep%?\s*", raw)
        entries = []
        for part in parts:
            part = part.strip().rstrip("%").strip()
            if not part:
                continue
            # Try \contactlink{icon}{url}{label}
            m = re.search(r"\\contactlink\{(.+?)\}\{(.+?)\}\{(.+?)\}", part)
            if m:
                icon_raw, url, label = m.groups()
                icon = self._extract_icon_name(icon_raw)
                entries.append(ContactEntry("link", icon, label.strip(), url.strip()))
                continue
            # Try \contactitem{icon}{text}
            m = re.search(r"\\contactitem\{(.+?)\}\{(.+?)\}", part)
            if m:
                icon_raw, txt = m.groups()
                icon = self._extract_icon_name(icon_raw)
                entries.append(ContactEntry("item", icon, txt.strip()))
        return entries

    def _extract_icon_name(self, raw: str) -> str:
        m = re.search(r"\\faIcon\{(.+?)\}", raw)
        return m.group(1) if m else raw.strip()

    def _parse_profile(self, text: str) -> str:
        # Find {\bodysize ... }
        idx = text.find("{\\bodysize")
        if idx < 0:
            return text.strip()
        content, _ = self._extract_brace_arg(text, idx)
        # Remove the \bodysize prefix
        content = re.sub(r"^\\bodysize\s*", "", content).strip()
        return content

    def _parse_education(self, text: str) -> list:
        entries = []
        pos = 0
        while True:
            idx = text.find("\\education", pos)
            if idx < 0:
                break
            p = idx + len("\\education")
            inst, p = self._extract_brace_arg(text, p)
            deg, p = self._extract_brace_arg(text, p)
            date, p = self._extract_brace_arg(text, p)
            entries.append(EducationEntry(inst.strip(), deg.strip(), date.strip()))
            pos = p
        return entries

    def _parse_experience(self, text: str) -> list:
        entries = []
        current = None
        pos = 0
        while pos < len(text):
            exp_idx = text.find("\\experience", pos)
            sub_idx = text.find("\\subrole", pos)
            # Find which comes first
            candidates = []
            if exp_idx >= 0:
                candidates.append(("experience", exp_idx))
            if sub_idx >= 0:
                candidates.append(("subrole", sub_idx))
            if not candidates:
                break
            candidates.sort(key=lambda x: x[1])
            cmd, cmd_idx = candidates[0]
            if cmd == "experience":
                p = cmd_idx + len("\\experience")
                title, p = self._extract_brace_arg(text, p)
                org, p = self._extract_brace_arg(text, p)
                date, p = self._extract_brace_arg(text, p)
                loc, p = self._extract_brace_arg(text, p)
                bullets, p = self._extract_bullets(text, p)
                current = ExperienceEntry(
                    title.strip(), org.strip(), date.strip(), loc.strip(), bullets
                )
                entries.append(current)
                pos = p
            else:
                p = cmd_idx + len("\\subrole")
                title, p = self._extract_brace_arg(text, p)
                date, p = self._extract_brace_arg(text, p)
                bullets, p = self._extract_bullets(text, p)
                sr = SubRole(title.strip(), date.strip(), bullets)
                if current:
                    current.subroles.append(sr)
                pos = p
        return entries

    def _parse_projects(self, text: str) -> list:
        entries = []
        pos = 0
        while True:
            idx = text.find("\\project", pos)
            if idx < 0:
                break
            p = idx + len("\\project")
            title, p = self._extract_brace_arg(text, p)
            date, p = self._extract_brace_arg(text, p)
            bullets, p = self._extract_bullets(text, p)
            entries.append(ProjectEntry(title.strip(), date.strip(), bullets))
            pos = p
        return entries

    def _parse_organisations(self, text: str) -> list:
        entries = []
        pos = 0
        while True:
            idx = text.find("\\organisation", pos)
            if idx < 0:
                break
            p = idx + len("\\organisation")
            org, p = self._extract_brace_arg(text, p)
            role, p = self._extract_brace_arg(text, p)
            date, p = self._extract_brace_arg(text, p)
            assoc, p = self._extract_brace_arg(text, p)
            bullets, p = self._extract_bullets(text, p)
            entries.append(OrganisationEntry(
                org.strip(), role.strip(), date.strip(), assoc.strip(), bullets
            ))
            pos = p
        return entries

    def _parse_volunteering(self, text: str) -> list:
        entries = []
        pos = 0
        while True:
            idx = text.find("\\volunteer", pos)
            if idx < 0:
                break
            p = idx + len("\\volunteer")
            role, p = self._extract_brace_arg(text, p)
            org, p = self._extract_brace_arg(text, p)
            date, p = self._extract_brace_arg(text, p)
            cat, p = self._extract_brace_arg(text, p)
            bullets, p = self._extract_bullets(text, p)
            entries.append(VolunteerEntry(
                role.strip(), org.strip(), date.strip(), cat.strip(), bullets
            ))
            pos = p
        return entries

    def _parse_skills(self, text: str) -> list:
        categories = []
        pos = 0
        while True:
            idx = text.find("\\skillcategory", pos)
            if idx < 0:
                break
            p = idx + len("\\skillcategory")
            cat_name, p = self._extract_brace_arg(text, p)
            tags_raw, p = self._extract_brace_arg(text, p)
            tags = re.findall(r"\\skilltag\{(.+?)\}", tags_raw)
            categories.append(SkillCategory(cat_name.strip(), tags))
            pos = p
        return categories

    def _parse_certifications(self, text: str) -> list:
        entries = []
        for m in re.finditer(
            r"\\item\s+\\textbf\{(.+?)\}\s*\\,\{\\color\{subtle\}---\s*(.+?)\}",
            text
        ):
            entries.append(CertificationEntry(m.group(1).strip(), m.group(2).strip()))
        return entries

    def _parse_courses(self, text: str) -> list:
        entries = []
        for m in re.finditer(r"\\textbf\{(.+?)\}\s*---\s*(.+?)(?:\}|$)", text):
            entries.append(CourseEntry(m.group(1).strip(), m.group(2).strip()))
        return entries

    def _parse_awards(self, text: str) -> list:
        entries = []
        pos = 0
        while True:
            idx = text.find("\\award", pos)
            if idx < 0:
                break
            p = idx + len("\\award")
            title, p = self._extract_brace_arg(text, p)
            issuer, p = self._extract_brace_arg(text, p)
            year, p = self._extract_brace_arg(text, p)
            entries.append(AwardEntry(title.strip(), issuer.strip(), year.strip()))
            pos = p
        return entries

    def _parse_languages(self, text: str) -> list:
        entries = []
        parts = re.split(r"\\contactsep%?\s*", text)
        for part in parts:
            m = re.search(r"\\langentry\{(.+?)\}\{(.+?)\}", part)
            if m:
                entries.append(LanguageEntry(m.group(1).strip(), m.group(2).strip()))
        return entries


# ══════════════════════════════════════════════════════════════════════════
#  TEX GENERATOR
# ══════════════════════════════════════════════════════════════════════════

class TexGenerator:
    """Generate resume-content.tex from a ResumeData object."""

    def generate(self, data: ResumeData) -> str:
        parts = []
        parts.append(self._file_header())
        parts.append(self._gen_header(data.header))
        parts.append(self._gen_profile(data.profile))
        parts.append(self._gen_education(data.education))
        parts.append(self._gen_experience(data.experience))
        parts.append(self._gen_projects(data.projects))
        parts.append(self._gen_organisations(data.organisations))
        parts.append(self._gen_volunteering(data.volunteering))
        parts.append(self._gen_skills(data.skills))
        parts.append(self._gen_certifications(data.certifications))
        parts.append(self._gen_courses(data.courses))
        parts.append(self._gen_awards(data.awards))
        parts.append(self._gen_languages(data.languages))
        return "\n".join(parts) + "\n"

    def _file_header(self) -> str:
        return (
            "%% ==========================================================================\n"
            "%%  CONTENT \u2014 Your actual resume data\n"
            "%%  -----------------------------------------------------------------------\n"
            "%%  This is the ONLY file you need to edit when updating your resume.\n"
            "%%  Just modify entries, add new ones, or reorder sections.\n"
            "%% =========================================================================="
        )

    def _section_comment(self, label: str) -> str:
        prefix = f"% ========================== {label} "
        pad = 76 - len(prefix)
        return f"\n{prefix}{'=' * max(pad, 4)}"

    def _gen_bullets(self, bullets: list) -> str:
        if not bullets:
            return ""
        lines = ["\\begin{bullets}"]
        for b in bullets:
            lines.append(f"    \\item {b}")
        lines.append("\\end{bullets}")
        return "\n".join(lines)

    # ── header ───────────────────────────────────────────────────────────

    def _gen_header(self, h: HeaderData) -> str:
        if not h:
            return ""
        cl1 = self._gen_contact_line(h.contact_line_1)
        cl2 = self._gen_contact_line(h.contact_line_2)
        return (
            f"{self._section_comment('HEADER')}\n"
            f"\\makeheader\n"
            f"    {{{h.name}}}\n"
            f"    {{{h.headline}}}\n"
            f"    {{%\n{cl1}\n    }}\n"
            f"    {{%\n{cl2}\n    }}"
        )

    def _gen_contact_line(self, entries: list) -> str:
        parts = []
        for ce in entries:
            if ce.entry_type == "link":
                parts.append(
                    f"        \\contactlink{{\\faIcon{{{ce.icon}}}}}"
                    f"{{{ce.url}}}{{{ce.text}}}%"
                )
            else:
                parts.append(
                    f"        \\contactitem{{\\faIcon{{{ce.icon}}}}}"
                    f"{{{ce.text}}}%"
                )
        return "\n        \\contactsep%\n".join(parts)

    # ── profile ──────────────────────────────────────────────────────────

    def _gen_profile(self, text: str) -> str:
        return (
            f"{self._section_comment('SUMMARY')}\n"
            f"\\section{{Profile}}\n\n"
            f"{{\\bodysize\n{text}\n}}"
        )

    # ── education ────────────────────────────────────────────────────────

    def _gen_education(self, entries: list) -> str:
        lines = [f"{self._section_comment('EDUCATION')}\n\\section{{Education}}\n"]
        for e in entries:
            lines.append(f"\\education{{{e.institution}}}{{{e.degree}}}{{{e.date}}}")
        return "\n".join(lines)

    # ── experience ───────────────────────────────────────────────────────

    def _gen_experience(self, entries: list) -> str:
        lines = [f"{self._section_comment('EXPERIENCE')}\n\\section{{Experience}}"]
        for e in entries:
            lines.append("")
            lines.append(
                f"\\experience{{{e.title}}}{{{e.org}}}"
                f"{{{e.date}}}{{{e.location}}}"
            )
            lines.append(self._gen_bullets(e.bullets))
            for sr in e.subroles:
                lines.append(f"\\subrole{{{sr.title}}}{{{sr.date}}}")
                lines.append(self._gen_bullets(sr.bullets))
        return "\n".join(lines)

    # ── projects ─────────────────────────────────────────────────────────

    def _gen_projects(self, entries: list) -> str:
        lines = [f"{self._section_comment('PROJECTS')}\n\\section{{Projects}}"]
        for e in entries:
            lines.append("")
            lines.append(f"\\project{{{e.title}}}{{{e.date}}}")
            lines.append(self._gen_bullets(e.bullets))
        return "\n".join(lines)

    # ── organisations ────────────────────────────────────────────────────

    def _gen_organisations(self, entries: list) -> str:
        lines = [f"{self._section_comment('ORGANISATIONS')}\n\\section{{Organisations}}"]
        for e in entries:
            lines.append("")
            lines.append(
                f"\\organisation{{{e.org}}}{{{e.role}}}"
                f"{{{e.date}}}{{{e.association}}}"
            )
            lines.append(self._gen_bullets(e.bullets))
        return "\n".join(lines)

    # ── volunteering ─────────────────────────────────────────────────────

    def _gen_volunteering(self, entries: list) -> str:
        lines = [f"{self._section_comment('VOLUNTEERING')}\n\\section{{Volunteering}}"]
        for e in entries:
            lines.append("")
            lines.append(
                f"\\volunteer{{{e.role}}}{{{e.org}}}"
                f"{{{e.date}}}{{{e.category}}}"
            )
            lines.append(self._gen_bullets(e.bullets))
        return "\n".join(lines)

    # ── skills ───────────────────────────────────────────────────────────

    def _gen_skills(self, categories: list) -> str:
        lines = [f"{self._section_comment('SKILLS')}\n\\section{{Skills}}"]
        for cat in categories:
            tags = "%\n    ".join(f"\\skilltag{{{t}}}" for t in cat.tags)
            lines.append(f"\n\\skillcategory{{{cat.category}}}{{%\n    {tags}%\n}}")
        return "\n".join(lines)

    # ── certifications ───────────────────────────────────────────────────

    def _gen_certifications(self, entries: list) -> str:
        lines = [
            f"{self._section_comment('CERTIFICATIONS')}\n"
            "\\section{Certifications}\n",
            "\\begin{multicols}{2}",
            "\\begin{itemize}[leftmargin=15pt, itemsep=2pt, parsep=1pt, topsep=2pt]",
            "    \\bodysize",
        ]
        for c in entries:
            lines.append(
                f"    \\item \\textbf{{{c.name}}} "
                f"\\,{{\\color{{subtle}}--- {c.issuer}}}"
            )
        lines.append("\\end{itemize}")
        lines.append("\\end{multicols}")
        return "\n".join(lines)

    # ── courses ──────────────────────────────────────────────────────────

    def _gen_courses(self, entries: list) -> str:
        lines = [f"{self._section_comment('COURSES')}\n\\section{{Courses}}\n"]
        for c in entries:
            lines.append(f"{{\\bodysize\\textbf{{{c.name}}} --- {c.description}}}")
        return "\n".join(lines)

    # ── awards ───────────────────────────────────────────────────────────

    def _gen_awards(self, entries: list) -> str:
        lines = [f"{self._section_comment('HONOURS')}\n\\section{{Honours \\& Awards}}\n"]
        for a in entries:
            lines.append(f"\\award{{{a.title}}}{{{a.issuer}}}{{{a.year}}}")
        return "\n".join(lines)

    # ── languages ────────────────────────────────────────────────────────

    def _gen_languages(self, entries: list) -> str:
        lines = [f"{self._section_comment('LANGUAGES')}\n\\section{{Languages}}\n"]
        parts = []
        for i, lang in enumerate(entries):
            if i < len(entries) - 1:
                parts.append(f"\\langentry{{{lang.level}}}{{{lang.languages}}}%")
            else:
                parts.append(f"\\langentry{{{lang.level}}}{{{lang.languages}}}")
        lines.append("\n\\contactsep%\n".join(parts))
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════
#  PDF COMPILER
# ══════════════════════════════════════════════════════════════════════════

def compile_pdf(working_dir: str):
    """Run pdflatex twice. Returns (success, log_text)."""
    cmd = ["pdflatex", "-interaction=nonstopmode", "resume.tex"]
    log = ""
    for pass_num in (1, 2):
        try:
            result = subprocess.run(
                cmd, cwd=working_dir, capture_output=True, text=True, timeout=30,
            )
            log += f"--- Pass {pass_num} ---\n{result.stdout}\n{result.stderr}\n"
            if result.returncode != 0:
                return False, log
        except subprocess.TimeoutExpired:
            return False, log + f"\nPass {pass_num} timed out."
        except FileNotFoundError:
            return False, "pdflatex not found. Is TeX Live installed?"
    return True, log


# ══════════════════════════════════════════════════════════════════════════
#  REUSABLE GUI WIDGETS
# ══════════════════════════════════════════════════════════════════════════

class BulletListWidget(ttk.Frame):
    """A listbox of bullet strings with Add / Edit / Delete buttons."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.listbox = tk.Listbox(self, height=6, selectmode=tk.SINGLE)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.listbox.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0))
        ttk.Button(btn_frame, text="Add", width=6, command=self._add).pack(pady=2)
        ttk.Button(btn_frame, text="Edit", width=6, command=self._edit).pack(pady=2)
        ttk.Button(btn_frame, text="Del", width=6, command=self._delete).pack(pady=2)

    def set_bullets(self, bullets: list):
        self.listbox.delete(0, tk.END)
        for b in bullets:
            self.listbox.insert(tk.END, b)

    def get_bullets(self) -> list:
        return list(self.listbox.get(0, tk.END))

    def _add(self):
        text = simpledialog.askstring("Add Bullet", "Enter bullet text:", parent=self)
        if text:
            self.listbox.insert(tk.END, text)

    def _edit(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        old = self.listbox.get(idx)
        text = simpledialog.askstring("Edit Bullet", "Edit bullet text:",
                                      initialvalue=old, parent=self)
        if text is not None:
            self.listbox.delete(idx)
            self.listbox.insert(idx, text)

    def _delete(self):
        sel = self.listbox.curselection()
        if sel:
            self.listbox.delete(sel[0])


class TagListWidget(ttk.Frame):
    """A listbox of skill tags with Add / Delete buttons."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.listbox = tk.Listbox(self, height=5, selectmode=tk.SINGLE)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(6, 0))
        ttk.Button(btn_frame, text="Add", width=6, command=self._add).pack(pady=2)
        ttk.Button(btn_frame, text="Edit", width=6, command=self._edit).pack(pady=2)
        ttk.Button(btn_frame, text="Del", width=6, command=self._delete).pack(pady=2)

    def set_tags(self, tags: list):
        self.listbox.delete(0, tk.END)
        for t in tags:
            self.listbox.insert(tk.END, t)

    def get_tags(self) -> list:
        return list(self.listbox.get(0, tk.END))

    def _add(self):
        text = simpledialog.askstring("Add Skill Tag", "Enter skill name:", parent=self)
        if text:
            self.listbox.insert(tk.END, text)

    def _edit(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        old = self.listbox.get(idx)
        text = simpledialog.askstring("Edit Skill Tag", "Edit skill name:",
                                      initialvalue=old, parent=self)
        if text is not None:
            self.listbox.delete(idx)
            self.listbox.insert(idx, text)

    def _delete(self):
        sel = self.listbox.curselection()
        if sel:
            self.listbox.delete(sel[0])


# ══════════════════════════════════════════════════════════════════════════
#  SECTION EDITOR FRAMES
# ══════════════════════════════════════════════════════════════════════════

class HeaderEditor(ttk.Frame):
    def __init__(self, parent, header: HeaderData):
        super().__init__(parent)
        self.header = header
        row = 0
        ttk.Label(self, text="Name:").grid(row=row, column=0, sticky="w", pady=4, padx=4)
        self.name_var = tk.StringVar(value=header.name)
        ttk.Entry(self, textvariable=self.name_var, width=50).grid(row=row, column=1, pady=4, sticky="ew")
        row += 1
        ttk.Label(self, text="Headline:").grid(row=row, column=0, sticky="w", pady=4, padx=4)
        self.headline_var = tk.StringVar(value=header.headline)
        ttk.Entry(self, textvariable=self.headline_var, width=50).grid(row=row, column=1, pady=4, sticky="ew")
        row += 1
        ttk.Label(self, text="(Contact info is preserved as-is from the .tex file)",
                  foreground="gray").grid(row=row, column=0, columnspan=2, sticky="w", pady=8, padx=4)
        self.columnconfigure(1, weight=1)

    def save(self):
        self.header.name = self.name_var.get()
        self.header.headline = self.headline_var.get()


class ProfileEditor(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        ttk.Label(self, text="Profile text (raw LaTeX):").pack(anchor="w", padx=4, pady=4)
        self.text_widget = scrolledtext.ScrolledText(self, wrap=tk.WORD, height=12)
        self.text_widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        ttk.Label(self, text="Tip: Use \\& for ampersand, \\textit{...} for italics, "
                  "\\vspace{2pt} for spacing.",
                  foreground="gray").pack(anchor="w", padx=4)

    def load(self, text: str):
        self.text_widget.delete("1.0", tk.END)
        self.text_widget.insert("1.0", text)

    def save(self) -> str:
        return self.text_widget.get("1.0", tk.END).strip()


class SimpleEntryEditor(ttk.Frame):
    """Generic editor for entries with named text fields + optional bullets."""

    def __init__(self, parent, fields: list, has_bullets: bool = False):
        super().__init__(parent)
        self.vars = {}
        self.has_bullets = has_bullets
        for i, (label, key, width) in enumerate(fields):
            ttk.Label(self, text=f"{label}:").grid(row=i, column=0, sticky="w", pady=4, padx=4)
            var = tk.StringVar()
            ttk.Entry(self, textvariable=var, width=width).grid(
                row=i, column=1, pady=4, sticky="ew"
            )
            self.vars[key] = var
        if has_bullets:
            r = len(fields)
            ttk.Label(self, text="Bullet points:").grid(row=r, column=0, sticky="nw", pady=4, padx=4)
            self.bullet_widget = BulletListWidget(self)
            self.bullet_widget.grid(row=r, column=1, pady=4, sticky="ew")
        self.columnconfigure(1, weight=1)

    def load(self, values: dict, bullets: list = None):
        for key, var in self.vars.items():
            var.set(values.get(key, ""))
        if self.has_bullets and bullets is not None:
            self.bullet_widget.set_bullets(bullets)

    def save(self) -> dict:
        result = {key: var.get() for key, var in self.vars.items()}
        if self.has_bullets:
            result["bullets"] = self.bullet_widget.get_bullets()
        return result


class ExperienceEditor(ttk.Frame):
    """Specialized editor for experience entries with subroles."""

    def __init__(self, parent):
        super().__init__(parent)
        fields = [
            ("Title", "title", 50),
            ("Organisation", "org", 50),
            ("Date", "date", 30),
            ("Location", "location", 30),
        ]
        self.vars = {}
        for i, (label, key, width) in enumerate(fields):
            ttk.Label(self, text=f"{label}:").grid(row=i, column=0, sticky="w", pady=3, padx=4)
            var = tk.StringVar()
            ttk.Entry(self, textvariable=var, width=width).grid(
                row=i, column=1, pady=3, sticky="ew"
            )
            self.vars[key] = var
        r = len(fields)
        ttk.Label(self, text="Bullet points:").grid(row=r, column=0, sticky="nw", pady=3, padx=4)
        self.bullet_widget = BulletListWidget(self)
        self.bullet_widget.grid(row=r, column=1, pady=3, sticky="ew")
        r += 1
        # Subrole section
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=r, column=0, columnspan=2, sticky="ew", pady=6)
        r += 1
        ttk.Label(self, text="Sub-roles:", font=("", 10, "bold")).grid(
            row=r, column=0, columnspan=2, sticky="w", padx=4
        )
        r += 1
        self.subrole_frame = ttk.Frame(self)
        self.subrole_frame.grid(row=r, column=0, columnspan=2, sticky="ew", padx=4)
        r += 1
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=r, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        ttk.Button(btn_frame, text="Add Sub-role", command=self._add_subrole).pack(side=tk.LEFT, padx=2)
        self.subrole_widgets = []
        self.columnconfigure(1, weight=1)

    def load(self, entry: ExperienceEntry):
        self.vars["title"].set(entry.title)
        self.vars["org"].set(entry.org)
        self.vars["date"].set(entry.date)
        self.vars["location"].set(entry.location)
        self.bullet_widget.set_bullets(entry.bullets)
        # Clear existing subrole widgets
        for w in self.subrole_widgets:
            w.destroy()
        self.subrole_widgets.clear()
        for sr in entry.subroles:
            self._add_subrole_widget(sr)

    def _add_subrole(self):
        self._add_subrole_widget(SubRole("", "", []))

    def _add_subrole_widget(self, sr: SubRole):
        frame = ttk.LabelFrame(self.subrole_frame, text=f"Sub-role {len(self.subrole_widgets) + 1}")
        frame.pack(fill=tk.X, pady=4)
        title_var = tk.StringVar(value=sr.title)
        date_var = tk.StringVar(value=sr.date)
        ttk.Label(frame, text="Title:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(frame, textvariable=title_var, width=40).grid(row=0, column=1, pady=2, sticky="ew")
        ttk.Label(frame, text="Date:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        ttk.Entry(frame, textvariable=date_var, width=25).grid(row=1, column=1, pady=2, sticky="w")
        ttk.Label(frame, text="Bullets:").grid(row=2, column=0, sticky="nw", padx=4, pady=2)
        bw = BulletListWidget(frame)
        bw.grid(row=2, column=1, pady=2, sticky="ew")
        bw.set_bullets(sr.bullets)
        ttk.Button(frame, text="Remove", command=lambda f=frame: self._remove_subrole(f)).grid(
            row=3, column=1, sticky="e", padx=4, pady=2
        )
        frame.columnconfigure(1, weight=1)
        frame._title_var = title_var
        frame._date_var = date_var
        frame._bullet_widget = bw
        self.subrole_widgets.append(frame)

    def _remove_subrole(self, frame):
        frame.destroy()
        self.subrole_widgets.remove(frame)

    def save(self) -> ExperienceEntry:
        subroles = []
        for w in self.subrole_widgets:
            subroles.append(SubRole(
                title=w._title_var.get(),
                date=w._date_var.get(),
                bullets=w._bullet_widget.get_bullets(),
            ))
        return ExperienceEntry(
            title=self.vars["title"].get(),
            org=self.vars["org"].get(),
            date=self.vars["date"].get(),
            location=self.vars["location"].get(),
            bullets=self.bullet_widget.get_bullets(),
            subroles=subroles,
        )


class SkillsEditor(ttk.Frame):
    """Editor for a skill category: category name + tag list."""

    def __init__(self, parent):
        super().__init__(parent)
        ttk.Label(self, text="Category name:").grid(row=0, column=0, sticky="w", pady=4, padx=4)
        self.cat_var = tk.StringVar()
        ttk.Entry(self, textvariable=self.cat_var, width=40).grid(row=0, column=1, pady=4, sticky="ew")
        ttk.Label(self, text="Skill tags:").grid(row=1, column=0, sticky="nw", pady=4, padx=4)
        self.tag_widget = TagListWidget(self)
        self.tag_widget.grid(row=1, column=1, pady=4, sticky="ew")
        self.columnconfigure(1, weight=1)

    def load(self, cat: SkillCategory):
        self.cat_var.set(cat.category)
        self.tag_widget.set_tags(cat.tags)

    def save(self) -> SkillCategory:
        return SkillCategory(
            category=self.cat_var.get(),
            tags=self.tag_widget.get_tags(),
        )


# ══════════════════════════════════════════════════════════════════════════
#  SECTION CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════

SECTIONS = [
    ("Header", "header"),
    ("Profile", "profile"),
    ("Education", "education"),
    ("Experience", "experience"),
    ("Projects", "projects"),
    ("Organisations", "organisations"),
    ("Volunteering", "volunteering"),
    ("Skills", "skills"),
    ("Certifications", "certifications"),
    ("Courses", "courses"),
    ("Honours & Awards", "awards"),
    ("Languages", "languages"),
]

# Fields definition for SimpleEntryEditor: (label, key, width)
SIMPLE_FIELDS = {
    "education": [("Institution", "institution", 50), ("Degree / Programme", "degree", 50), ("Date", "date", 30)],
    "projects": [("Title", "title", 50), ("Date", "date", 30)],
    "organisations": [("Organisation", "org", 50), ("Role", "role", 50), ("Date", "date", 30), ("Association", "association", 50)],
    "volunteering": [("Role", "role", 50), ("Organisation", "org", 50), ("Date", "date", 30), ("Category", "category", 30)],
    "certifications": [("Certificate Name", "name", 50), ("Issuer", "issuer", 40)],
    "courses": [("Course Name", "name", 50), ("Description", "description", 50)],
    "awards": [("Title", "title", 60), ("Issuer", "issuer", 40), ("Year", "year", 10)],
    "languages": [("Level", "level", 30), ("Languages", "languages", 50)],
}

HAS_BULLETS = {"projects", "organisations", "volunteering"}


def entry_display_text(section_key: str, entry) -> str:
    """Return a short display string for the entry list."""
    if section_key == "education":
        return f"{entry.institution} -- {entry.degree}"
    if section_key == "experience":
        return f"{entry.title} -- {entry.org}"
    if section_key == "projects":
        return entry.title
    if section_key == "organisations":
        return f"{entry.org} -- {entry.role}"
    if section_key == "volunteering":
        return f"{entry.role} -- {entry.org}"
    if section_key == "skills":
        return f"{entry.category} ({len(entry.tags)} tags)"
    if section_key == "certifications":
        return entry.name
    if section_key == "courses":
        return entry.name
    if section_key == "awards":
        return entry.title
    if section_key == "languages":
        return f"{entry.level}: {entry.languages}"
    return str(entry)


def make_default_entry(section_key: str):
    """Create a blank new entry for the given section."""
    if section_key == "education":
        return EducationEntry("", "", "")
    if section_key == "experience":
        return ExperienceEntry("", "", "", "", [])
    if section_key == "projects":
        return ProjectEntry("", "", [])
    if section_key == "organisations":
        return OrganisationEntry("", "", "", "", [])
    if section_key == "volunteering":
        return VolunteerEntry("", "", "", "", [])
    if section_key == "skills":
        return SkillCategory("", [])
    if section_key == "certifications":
        return CertificationEntry("", "")
    if section_key == "courses":
        return CourseEntry("", "")
    if section_key == "awards":
        return AwardEntry("", "", "")
    if section_key == "languages":
        return LanguageEntry("", "")
    return None


def entry_to_dict(section_key: str, entry) -> dict:
    """Convert an entry to a dict for SimpleEntryEditor.load()."""
    if section_key == "education":
        return {"institution": entry.institution, "degree": entry.degree, "date": entry.date}
    if section_key == "projects":
        return {"title": entry.title, "date": entry.date}
    if section_key == "organisations":
        return {"org": entry.org, "role": entry.role, "date": entry.date, "association": entry.association}
    if section_key == "volunteering":
        return {"role": entry.role, "org": entry.org, "date": entry.date, "category": entry.category}
    if section_key == "certifications":
        return {"name": entry.name, "issuer": entry.issuer}
    if section_key == "courses":
        return {"name": entry.name, "description": entry.description}
    if section_key == "awards":
        return {"title": entry.title, "issuer": entry.issuer, "year": entry.year}
    if section_key == "languages":
        return {"level": entry.level, "languages": entry.languages}
    return {}


def dict_to_entry(section_key: str, d: dict):
    """Convert a dict from SimpleEntryEditor.save() back to an entry."""
    if section_key == "education":
        return EducationEntry(d["institution"], d["degree"], d["date"])
    if section_key == "projects":
        return ProjectEntry(d["title"], d["date"], d.get("bullets", []))
    if section_key == "organisations":
        return OrganisationEntry(d["org"], d["role"], d["date"], d["association"], d.get("bullets", []))
    if section_key == "volunteering":
        return VolunteerEntry(d["role"], d["org"], d["date"], d["category"], d.get("bullets", []))
    if section_key == "certifications":
        return CertificationEntry(d["name"], d["issuer"])
    if section_key == "courses":
        return CourseEntry(d["name"], d["description"])
    if section_key == "awards":
        return AwardEntry(d["title"], d["issuer"], d["year"])
    if section_key == "languages":
        return LanguageEntry(d["level"], d["languages"])
    return None


# ══════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════

class ResumeManagerApp(tk.Tk):
    WORKING_DIR = os.path.dirname(os.path.abspath(__file__))
    CONTENT_FILE = "resume-content.tex"

    def __init__(self):
        super().__init__()
        self.geometry("1100x720")
        self.minsize(900, 550)

        self.parser = TexParser()
        self.generator = TexGenerator()
        self.data = ResumeData()
        self.current_section_key = None
        self.current_editor = None
        self.selected_index = None
        self.dirty = False

        self._build_ui()
        self._load_data()
        self._update_title()

        # Select first section
        self.section_listbox.selection_set(0)
        self._on_section_select(None)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── build UI ─────────────────────────────────────────────────────────

    def _build_ui(self):
        # Top: menu-like button bar
        top_bar = ttk.Frame(self)
        top_bar.pack(fill=tk.X, padx=8, pady=(8, 0))
        ttk.Button(top_bar, text="Reload from file", command=self._load_data).pack(side=tk.LEFT, padx=4)
        ttk.Button(top_bar, text="Save & Compile PDF", command=self._save_and_compile).pack(side=tk.RIGHT, padx=4)

        # Main 3-panel area
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left: section list
        left = ttk.LabelFrame(main, text="Sections", width=160)
        self.section_listbox = tk.Listbox(left, exportselection=False)
        for display_name, _ in SECTIONS:
            self.section_listbox.insert(tk.END, display_name)
        self.section_listbox.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.section_listbox.bind("<<ListboxSelect>>", self._on_section_select)
        main.add(left, weight=0)

        # Middle: entry list + buttons
        middle = ttk.Frame(main, width=260)
        ttk.Label(middle, text="Entries:").pack(anchor="w", padx=4)
        self.entry_listbox = tk.Listbox(middle, exportselection=False)
        self.entry_listbox.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.entry_listbox.bind("<<ListboxSelect>>", self._on_entry_select)
        btn_frame = ttk.Frame(middle)
        btn_frame.pack(fill=tk.X, padx=4, pady=4)
        self.btn_add = ttk.Button(btn_frame, text="Add", command=self._add_entry)
        self.btn_add.pack(side=tk.LEFT, padx=2)
        self.btn_del = ttk.Button(btn_frame, text="Delete", command=self._delete_entry)
        self.btn_del.pack(side=tk.LEFT, padx=2)
        self.btn_up = ttk.Button(btn_frame, text="Up", command=self._move_up)
        self.btn_up.pack(side=tk.LEFT, padx=2)
        self.btn_down = ttk.Button(btn_frame, text="Down", command=self._move_down)
        self.btn_down.pack(side=tk.LEFT, padx=2)
        main.add(middle, weight=1)

        # Right: editor area (scrollable)
        right = ttk.LabelFrame(main, text="Edit")
        self.editor_canvas = tk.Canvas(right, highlightthickness=0)
        self.editor_scrollbar = ttk.Scrollbar(right, orient=tk.VERTICAL,
                                               command=self.editor_canvas.yview)
        self.editor_container = ttk.Frame(self.editor_canvas)
        self.editor_container.bind(
            "<Configure>",
            lambda e: self.editor_canvas.configure(scrollregion=self.editor_canvas.bbox("all")),
        )
        self.editor_canvas.create_window((0, 0), window=self.editor_container, anchor="nw")
        self.editor_canvas.configure(yscrollcommand=self.editor_scrollbar.set)
        self.editor_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.editor_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Save entry button
        self.save_btn_frame = ttk.Frame(right)
        self.save_btn_frame.pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(self.save_btn_frame, text="Save Entry", command=self._save_current_entry).pack(
            side=tk.RIGHT, padx=4
        )
        main.add(right, weight=3)

        # Bottom: status bar
        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status.pack(fill=tk.X, padx=8, pady=(0, 8))

    # ── data loading ─────────────────────────────────────────────────────

    def _load_data(self):
        filepath = os.path.join(self.WORKING_DIR, self.CONTENT_FILE)
        try:
            self.data = self.parser.parse(filepath)
            if not self.data.header:
                self.data.header = HeaderData("", "", [], [])
            self.status_var.set(f"Loaded {filepath}")
            self.dirty = False
        except Exception as e:
            messagebox.showerror("Parse Error", f"Could not parse {filepath}:\n{e}")
            self.data = ResumeData(header=HeaderData("", "", [], []))
        self._update_title()

    def _update_title(self):
        name = self.data.header.name if self.data.header and self.data.header.name else ""
        if name:
            self.title(f"Resume Manager \u2014 {name}")
        else:
            self.title("Resume Manager")

    # ── section switching ────────────────────────────────────────────────

    def _on_section_select(self, event):
        sel = self.section_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        _, section_key = SECTIONS[idx]
        self.current_section_key = section_key
        self.selected_index = None
        self._clear_editor()
        self._populate_entry_list()
        # Show/hide buttons for singleton sections
        is_singleton = section_key in ("header", "profile")
        state = "disabled" if is_singleton else "normal"
        self.btn_add.config(state=state)
        self.btn_del.config(state=state)
        self.btn_up.config(state=state)
        self.btn_down.config(state=state)
        # Auto-load singleton
        if is_singleton:
            self._load_singleton_editor()

    def _populate_entry_list(self):
        self.entry_listbox.delete(0, tk.END)
        key = self.current_section_key
        if key in ("header", "profile"):
            self.entry_listbox.insert(tk.END, key.capitalize())
            return
        entries = getattr(self.data, key, [])
        for entry in entries:
            self.entry_listbox.insert(tk.END, entry_display_text(key, entry))

    # ── entry selection ──────────────────────────────────────────────────

    def _on_entry_select(self, event):
        sel = self.entry_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        key = self.current_section_key
        if key in ("header", "profile"):
            self._load_singleton_editor()
            return
        entries = getattr(self.data, key, [])
        if idx >= len(entries):
            return
        self.selected_index = idx
        entry = entries[idx]
        self._load_entry_editor(entry)

    def _load_singleton_editor(self):
        self._clear_editor()
        key = self.current_section_key
        if key == "header":
            editor = HeaderEditor(self.editor_container, self.data.header)
            editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            self.current_editor = editor
        elif key == "profile":
            editor = ProfileEditor(self.editor_container)
            editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            editor.load(self.data.profile)
            self.current_editor = editor

    def _load_entry_editor(self, entry):
        self._clear_editor()
        key = self.current_section_key
        if key == "experience":
            editor = ExperienceEditor(self.editor_container)
            editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            editor.load(entry)
            self.current_editor = editor
        elif key == "skills":
            editor = SkillsEditor(self.editor_container)
            editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            editor.load(entry)
            self.current_editor = editor
        elif key in SIMPLE_FIELDS:
            has_bullets = key in HAS_BULLETS
            editor = SimpleEntryEditor(
                self.editor_container, SIMPLE_FIELDS[key], has_bullets=has_bullets
            )
            editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            d = entry_to_dict(key, entry)
            bullets = getattr(entry, "bullets", None) if has_bullets else None
            editor.load(d, bullets)
            self.current_editor = editor

    def _clear_editor(self):
        for w in self.editor_container.winfo_children():
            w.destroy()
        self.current_editor = None

    # ── save current entry ───────────────────────────────────────────────

    def _save_current_entry(self):
        if not self.current_editor:
            return
        key = self.current_section_key
        if key == "header":
            self.current_editor.save()
            self.dirty = True
            self.status_var.set("Header updated.")
            return
        if key == "profile":
            self.data.profile = self.current_editor.save()
            self.dirty = True
            self.status_var.set("Profile updated.")
            return
        if self.selected_index is None:
            return
        entries = getattr(self.data, key, [])
        if self.selected_index >= len(entries):
            return
        if key == "experience":
            entries[self.selected_index] = self.current_editor.save()
        elif key == "skills":
            entries[self.selected_index] = self.current_editor.save()
        elif key in SIMPLE_FIELDS:
            d = self.current_editor.save()
            entries[self.selected_index] = dict_to_entry(key, d)
        self.dirty = True
        self._populate_entry_list()
        self.entry_listbox.selection_set(self.selected_index)
        self.status_var.set(f"Entry saved in {key}.")

    # ── CRUD ─────────────────────────────────────────────────────────────

    def _add_entry(self):
        key = self.current_section_key
        if key in ("header", "profile"):
            return
        entries = getattr(self.data, key, [])
        new = make_default_entry(key)
        if new is None:
            return
        entries.append(new)
        self.dirty = True
        self._populate_entry_list()
        idx = len(entries) - 1
        self.entry_listbox.selection_set(idx)
        self.selected_index = idx
        self._load_entry_editor(entries[idx])
        self.status_var.set(f"New entry added to {key}.")

    def _delete_entry(self):
        key = self.current_section_key
        if key in ("header", "profile"):
            return
        if self.selected_index is None:
            return
        entries = getattr(self.data, key, [])
        if self.selected_index >= len(entries):
            return
        if not messagebox.askyesno("Delete", "Delete this entry?"):
            return
        entries.pop(self.selected_index)
        self.selected_index = None
        self.dirty = True
        self._clear_editor()
        self._populate_entry_list()
        self.status_var.set(f"Entry deleted from {key}.")

    def _move_up(self):
        key = self.current_section_key
        if self.selected_index is None or self.selected_index == 0:
            return
        entries = getattr(self.data, key, [])
        i = self.selected_index
        entries[i], entries[i - 1] = entries[i - 1], entries[i]
        self.selected_index = i - 1
        self.dirty = True
        self._populate_entry_list()
        self.entry_listbox.selection_set(self.selected_index)

    def _move_down(self):
        key = self.current_section_key
        entries = getattr(self.data, key, [])
        if self.selected_index is None or self.selected_index >= len(entries) - 1:
            return
        i = self.selected_index
        entries[i], entries[i + 1] = entries[i + 1], entries[i]
        self.selected_index = i + 1
        self.dirty = True
        self._populate_entry_list()
        self.entry_listbox.selection_set(self.selected_index)

    # ── save & compile ───────────────────────────────────────────────────

    def _save_and_compile(self):
        filepath = os.path.join(self.WORKING_DIR, self.CONTENT_FILE)
        backup = filepath + ".bak"
        # Backup
        if os.path.exists(filepath):
            shutil.copy2(filepath, backup)
        # Generate
        content = self.generator.generate(self.data)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        self.status_var.set("Compiling PDF...")
        self.update_idletasks()
        success, log = compile_pdf(self.WORKING_DIR)
        if success:
            self.status_var.set("PDF compiled successfully!")
            self.dirty = False
        else:
            self.status_var.set("Compilation failed. See log.")
            self._show_log(log)

    def _show_log(self, log: str):
        win = tk.Toplevel(self)
        win.title("Compile Log")
        win.geometry("700x500")
        text = scrolledtext.ScrolledText(win, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        text.insert("1.0", log)
        text.config(state=tk.DISABLED)

    # ── close handler ────────────────────────────────────────────────────

    def _on_close(self):
        if self.dirty:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes", "Save and compile before exiting?"
            )
            if ans is None:
                return
            if ans:
                self._save_and_compile()
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = ResumeManagerApp()
    app.mainloop()
