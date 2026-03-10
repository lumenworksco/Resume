#!/usr/bin/env python3
"""
Research Plan Manager — A GUI tool for editing your LaTeX research plan.

Launch:  python3 research_plan_manager.py
         python3 research_plan_manager.py /path/to/research-plan/

Parses content.tex, lets you edit sections in a GUI,
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
class PlanHeaderData:
    applicant: str
    program: str
    supervisor: str
    department: str

@dataclass
class ResearchQuestion:
    number: str        # "1", "2", etc.
    title: str         # The question text
    description: str   # Free-text paragraph following the question

@dataclass
class MethodologyPhase:
    name: str          # "Phase 1: Literature Review"
    period: str        # "Months 1--4"
    description: str   # Free-text paragraph

@dataclass
class ResearchPlanData:
    header: PlanHeaderData = None
    title: str = ""
    introduction: str = ""
    background_text: str = ""
    background_bullets: list = field(default_factory=list)   # list[str]
    direction_intro: str = ""
    questions: list = field(default_factory=list)             # list[ResearchQuestion]
    methodology_intro: str = ""
    phases: list = field(default_factory=list)                # list[MethodologyPhase]
    contributions: list = field(default_factory=list)         # list[str]
    relevance: str = ""
    academic_background: str = ""


# ══════════════════════════════════════════════════════════════════════════
#  TEX PARSER
# ══════════════════════════════════════════════════════════════════════════

class PlanTexParser:
    """Parse content.tex into a ResearchPlanData object."""

    def parse(self, filepath: str) -> ResearchPlanData:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
        sections = self._split_sections(text)
        data = ResearchPlanData()

        if "header" in sections:
            data.header, data.title = self._parse_plan_header(sections["header"])

        if "Introduction and Motivation" in sections:
            data.introduction = self._parse_text_section(
                sections["Introduction and Motivation"]
            )

        if "Background" in sections:
            data.background_text, data.background_bullets = self._parse_background(
                sections["Background"]
            )

        if "Proposed Research Direction" in sections:
            data.direction_intro, data.questions = self._parse_research_questions(
                sections["Proposed Research Direction"]
            )

        if "Preliminary Methodology" in sections:
            data.methodology_intro, data.phases = self._parse_methodology(
                sections["Preliminary Methodology"]
            )

        if "Expected Contributions" in sections:
            data.contributions = self._parse_contributions(
                sections["Expected Contributions"]
            )

        for key in ("Relevance to the Kawahara Laboratory",
                     "Relevance to the Laboratory"):
            if key in sections:
                data.relevance = self._parse_text_section(sections[key])
                break
        # Fallback: any section with "Relevance" in the name
        if not data.relevance:
            for key in sections:
                if "Relevance" in key:
                    data.relevance = self._parse_text_section(sections[key])
                    break

        if "Academic Background" in sections:
            data.academic_background = self._parse_text_section(
                sections["Academic Background"]
            )

        return data

    # ── section splitting ─────────────────────────────────────────────

    def _split_sections(self, text: str) -> dict:
        """Split text into header (before first \\section) and named sections."""
        sections = {}
        pattern = re.compile(r"\\section\{(.+?)\}")
        matches = list(pattern.finditer(text))
        if not matches:
            sections["header"] = text
            return sections
        sections["header"] = text[: matches[0].start()]
        for i, m in enumerate(matches):
            name = m.group(1)
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections[name] = text[start:end]
        return sections

    # ── brace / bullet helpers ────────────────────────────────────────

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

    def _extract_bullets(self, text: str, pos: int = 0):
        """Extract bullets from \\begin{bullets}...\\end{bullets}. Returns (list, end_pos)."""
        begin = text.find("\\begin{bullets}", pos)
        if begin < 0:
            return [], pos
        end = text.find("\\end{bullets}", begin)
        if end < 0:
            return [], pos
        block = text[begin + len("\\begin{bullets}"):end]
        bullets = []
        for m in re.finditer(r"\\item\s+(.*?)(?=\\item|\Z)", block, re.DOTALL):
            bullet = m.group(1).strip()
            if bullet:
                bullets.append(bullet)
        return bullets, end + len("\\end{bullets}")

    # ── section parsers ───────────────────────────────────────────────

    def _parse_plan_header(self, text: str):
        """Parse \\makeplanheader and \\plantitle from pre-section content."""
        header = PlanHeaderData("", "", "", "")
        title = ""

        idx = text.find("\\makeplanheader")
        if idx >= 0:
            pos = idx + len("\\makeplanheader")
            applicant, pos = self._extract_brace_arg(text, pos)
            program, pos = self._extract_brace_arg(text, pos)
            supervisor, pos = self._extract_brace_arg(text, pos)
            department, pos = self._extract_brace_arg(text, pos)
            header = PlanHeaderData(
                applicant.strip(), program.strip(),
                supervisor.strip(), department.strip(),
            )

        idx = text.find("\\plantitle")
        if idx >= 0:
            pos = idx + len("\\plantitle")
            title, _ = self._extract_brace_arg(text, pos)
            title = title.strip()

        return header, title

    def _parse_text_section(self, text: str) -> str:
        """Extract free-text content, stripping comments."""
        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            # Skip pure comment lines but keep content
            if stripped.startswith("%%") or stripped.startswith("% ==="):
                continue
            lines.append(line)
        result = "\n".join(lines).strip()
        return result

    def _parse_background(self, text: str):
        """Parse background section: text before bullets + bullet list."""
        bullet_start = text.find("\\begin{bullets}")
        if bullet_start < 0:
            return self._parse_text_section(text), []

        pre_text = self._parse_text_section(text[:bullet_start])
        bullets, _ = self._extract_bullets(text, 0)
        return pre_text, bullets

    def _parse_research_questions(self, text: str):
        """Parse \\researchquestion commands with description text between them."""
        questions = []

        # Find all \researchquestion positions
        pattern = re.compile(r"\\researchquestion")
        matches = list(pattern.finditer(text))

        # Extract intro text (before first question)
        intro = ""
        if matches:
            intro_text = text[:matches[0].start()]
            intro = self._parse_text_section(intro_text)

        for i, m in enumerate(matches):
            pos = m.end()
            number, pos = self._extract_brace_arg(text, pos)
            title, pos = self._extract_brace_arg(text, pos)

            # Description is text between end of this command and start of next
            if i + 1 < len(matches):
                desc_text = text[pos:matches[i + 1].start()]
            else:
                desc_text = text[pos:]

            desc = self._parse_text_section(desc_text)
            questions.append(ResearchQuestion(number.strip(), title.strip(), desc))

        return intro, questions

    def _parse_methodology(self, text: str):
        """Parse \\phase commands with description text between them."""
        phases = []

        pattern = re.compile(r"\\phase")
        matches = list(pattern.finditer(text))

        # Extract intro text (before first phase)
        intro = ""
        if matches:
            intro_text = text[:matches[0].start()]
            intro = self._parse_text_section(intro_text)

        for i, m in enumerate(matches):
            pos = m.end()
            name, pos = self._extract_brace_arg(text, pos)
            period, pos = self._extract_brace_arg(text, pos)

            if i + 1 < len(matches):
                desc_text = text[pos:matches[i + 1].start()]
            else:
                desc_text = text[pos:]

            desc = self._parse_text_section(desc_text)
            phases.append(MethodologyPhase(name.strip(), period.strip(), desc))

        return intro, phases

    def _parse_contributions(self, text: str) -> list:
        """Parse bullet list from contributions section."""
        bullets, _ = self._extract_bullets(text, 0)
        return bullets


# ══════════════════════════════════════════════════════════════════════════
#  TEX GENERATOR
# ══════════════════════════════════════════════════════════════════════════

class PlanTexGenerator:
    """Generate content.tex from a ResearchPlanData object."""

    def generate(self, data: ResearchPlanData) -> str:
        parts = []
        parts.append(self._file_header())
        parts.append(self._gen_plan_header(data.header, data.title))
        parts.append(self._gen_introduction(data.introduction))
        parts.append(self._gen_background(data.background_text, data.background_bullets))
        parts.append(self._gen_research_questions(data.direction_intro, data.questions))
        parts.append(self._gen_methodology(data.methodology_intro, data.phases))
        parts.append(self._gen_contributions(data.contributions))
        parts.append(self._gen_relevance(data.relevance))
        parts.append(self._gen_academic_background(data.academic_background))
        return "\n".join(parts) + "\n"

    def _file_header(self) -> str:
        return (
            "%% ==========================================================================\n"
            "%%  CONTENT \u2014 Your actual research plan data\n"
            "%%  -----------------------------------------------------------------------\n"
            "%%  This is the ONLY file you need to edit when updating your research plan.\n"
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

    # ── header & title ────────────────────────────────────────────────

    def _gen_plan_header(self, h: PlanHeaderData, title: str) -> str:
        if not h:
            return ""
        return (
            f"{self._section_comment('HEADER')}\n"
            f"\\makeplanheader\n"
            f"    {{{h.applicant}}}\n"
            f"    {{{h.program}}}\n"
            f"    {{{h.supervisor}}}\n"
            f"    {{{h.department}}}\n"
            f"\n{self._section_comment('TITLE')}\n"
            f"\\plantitle{{{title}}}"
        )

    # ── introduction ──────────────────────────────────────────────────

    def _gen_introduction(self, text: str) -> str:
        return (
            f"{self._section_comment('INTRODUCTION')}\n"
            f"\\section{{Introduction and Motivation}}\n\n"
            f"{text}"
        )

    # ── background ────────────────────────────────────────────────────

    def _gen_background(self, text: str, bullets: list) -> str:
        parts = [
            f"{self._section_comment('BACKGROUND')}\n"
            f"\\section{{Background}}\n\n"
            f"{text}"
        ]
        if bullets:
            parts.append("")
            parts.append(self._gen_bullets(bullets))
        return "\n".join(parts)

    # ── research questions ────────────────────────────────────────────

    def _gen_research_questions(self, intro: str, questions: list) -> str:
        lines = [
            f"{self._section_comment('PROPOSED RESEARCH')}\n"
            f"\\section{{Proposed Research Direction}}\n"
        ]
        if intro:
            lines.append(f"{intro}\n")
        for q in questions:
            lines.append(f"\\researchquestion{{{q.number}}}{{{q.title}}}")
            if q.description:
                lines.append(f"\n{q.description}\n")
        return "\n".join(lines)

    # ── methodology ───────────────────────────────────────────────────

    def _gen_methodology(self, intro: str, phases: list) -> str:
        lines = [
            f"{self._section_comment('METHODOLOGY')}\n"
            f"\\section{{Preliminary Methodology}}\n"
        ]
        if intro:
            lines.append(f"{intro}\n")
        for p in phases:
            lines.append(f"\\phase{{{p.name}}}{{{p.period}}}")
            if p.description:
                lines.append(f"\n{p.description}\n")
        return "\n".join(lines)

    # ── contributions ─────────────────────────────────────────────────

    def _gen_contributions(self, bullets: list) -> str:
        parts = [
            f"{self._section_comment('CONTRIBUTIONS')}\n"
            f"\\section{{Expected Contributions}}\n"
        ]
        if bullets:
            parts.append(self._gen_bullets(bullets))
        return "\n".join(parts)

    # ── relevance ─────────────────────────────────────────────────────

    def _gen_relevance(self, text: str) -> str:
        return (
            f"{self._section_comment('RELEVANCE')}\n"
            f"\\section{{Relevance to the Kawahara Laboratory}}\n\n"
            f"{text}"
        )

    # ── academic background ───────────────────────────────────────────

    def _gen_academic_background(self, text: str) -> str:
        return (
            f"{self._section_comment('ACADEMIC BACKGROUND')}\n"
            f"\\section{{Academic Background}}\n\n"
            f"{text}"
        )


# ══════════════════════════════════════════════════════════════════════════
#  PDF COMPILER
# ══════════════════════════════════════════════════════════════════════════

def compile_pdf(working_dir: str):
    """Run pdflatex twice for research-plan.tex. Returns (success, log_text)."""
    tex_file = "research-plan.tex"
    cmd = ["pdflatex", "-interaction=nonstopmode", tex_file]
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


# ══════════════════════════════════════════════════════════════════════════
#  SECTION EDITOR FRAMES
# ══════════════════════════════════════════════════════════════════════════

class PlanHeaderEditor(ttk.Frame):
    """Editor for the research plan header (applicant, program, supervisor, department)."""

    def __init__(self, parent, header: PlanHeaderData, title: str):
        super().__init__(parent)
        self.header = header
        self._title = title

        fields = [
            ("Applicant:", header.applicant),
            ("Program:", header.program),
            ("Supervisor:", header.supervisor),
            ("Department:", header.department),
            ("Plan Title:", title),
        ]
        self.vars = {}
        for row, (label, value) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=4)
            var = tk.StringVar(value=value)
            ttk.Entry(self, textvariable=var, width=60).grid(
                row=row, column=1, pady=4, sticky="ew"
            )
            self.vars[label] = var
        self.columnconfigure(1, weight=1)

    def save(self) -> str:
        """Update header in place and return the title."""
        self.header.applicant = self.vars["Applicant:"].get()
        self.header.program = self.vars["Program:"].get()
        self.header.supervisor = self.vars["Supervisor:"].get()
        self.header.department = self.vars["Department:"].get()
        return self.vars["Plan Title:"].get()


class TextSectionEditor(ttk.Frame):
    """Editor for a free-text section (introduction, relevance, academic background)."""

    def __init__(self, parent, text: str, label: str = "Content"):
        super().__init__(parent)
        ttk.Label(self, text=f"{label} (raw LaTeX):").pack(anchor="w", padx=4, pady=(4, 0))
        self.text_widget = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, height=20, width=80
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.text_widget.insert("1.0", text)

    def get_text(self) -> str:
        return self.text_widget.get("1.0", tk.END).strip()


class BackgroundEditor(ttk.Frame):
    """Editor for background section: free text + bullet list."""

    def __init__(self, parent, text: str, bullets: list):
        super().__init__(parent)
        ttk.Label(self, text="Background text (raw LaTeX):").pack(
            anchor="w", padx=4, pady=(4, 0)
        )
        self.text_widget = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, height=12, width=80
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.text_widget.insert("1.0", text)

        ttk.Label(self, text="Key research directions:").pack(
            anchor="w", padx=4, pady=(8, 0)
        )
        self.bullet_widget = BulletListWidget(self)
        self.bullet_widget.pack(fill=tk.X, padx=4, pady=4)
        self.bullet_widget.set_bullets(bullets)

    def get_text(self) -> str:
        return self.text_widget.get("1.0", tk.END).strip()

    def get_bullets(self) -> list:
        return self.bullet_widget.get_bullets()


class ResearchQuestionEditor(ttk.Frame):
    """Editor for a single research question entry."""

    def __init__(self, parent, question: ResearchQuestion = None):
        super().__init__(parent)
        if question is None:
            question = ResearchQuestion("", "", "")

        row = 0
        ttk.Label(self, text="Number:").grid(row=row, column=0, sticky="w", pady=4, padx=4)
        self.number_var = tk.StringVar(value=question.number)
        ttk.Entry(self, textvariable=self.number_var, width=10).grid(
            row=row, column=1, pady=4, sticky="w"
        )

        row += 1
        ttk.Label(self, text="Question:").grid(row=row, column=0, sticky="nw", pady=4, padx=4)
        self.title_var = tk.StringVar(value=question.title)
        ttk.Entry(self, textvariable=self.title_var, width=70).grid(
            row=row, column=1, pady=4, sticky="ew"
        )

        row += 1
        ttk.Label(self, text="Description:").grid(row=row, column=0, sticky="nw", pady=4, padx=4)
        self.desc_widget = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, height=10, width=70
        )
        self.desc_widget.grid(row=row, column=1, pady=4, sticky="nsew")
        self.desc_widget.insert("1.0", question.description)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(row, weight=1)

    def save(self) -> ResearchQuestion:
        return ResearchQuestion(
            number=self.number_var.get(),
            title=self.title_var.get(),
            description=self.desc_widget.get("1.0", tk.END).strip(),
        )


class MethodologyPhaseEditor(ttk.Frame):
    """Editor for a single methodology phase entry."""

    def __init__(self, parent, phase: MethodologyPhase = None):
        super().__init__(parent)
        if phase is None:
            phase = MethodologyPhase("", "", "")

        row = 0
        ttk.Label(self, text="Phase name:").grid(row=row, column=0, sticky="w", pady=4, padx=4)
        self.name_var = tk.StringVar(value=phase.name)
        ttk.Entry(self, textvariable=self.name_var, width=50).grid(
            row=row, column=1, pady=4, sticky="ew"
        )

        row += 1
        ttk.Label(self, text="Period:").grid(row=row, column=0, sticky="w", pady=4, padx=4)
        self.period_var = tk.StringVar(value=phase.period)
        ttk.Entry(self, textvariable=self.period_var, width=30).grid(
            row=row, column=1, pady=4, sticky="w"
        )

        row += 1
        ttk.Label(self, text="Description:").grid(row=row, column=0, sticky="nw", pady=4, padx=4)
        self.desc_widget = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, height=10, width=70
        )
        self.desc_widget.grid(row=row, column=1, pady=4, sticky="nsew")
        self.desc_widget.insert("1.0", phase.description)

        self.columnconfigure(1, weight=1)
        self.rowconfigure(row, weight=1)

    def save(self) -> MethodologyPhase:
        return MethodologyPhase(
            name=self.name_var.get(),
            period=self.period_var.get(),
            description=self.desc_widget.get("1.0", tk.END).strip(),
        )


class ContributionsEditor(ttk.Frame):
    """Editor for the contributions section (bullet list only)."""

    def __init__(self, parent, bullets: list):
        super().__init__(parent)
        ttk.Label(self, text="Expected contributions:").pack(
            anchor="w", padx=4, pady=(4, 0)
        )
        self.bullet_widget = BulletListWidget(self)
        self.bullet_widget.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.bullet_widget.set_bullets(bullets)

    def get_bullets(self) -> list:
        return self.bullet_widget.get_bullets()


# ══════════════════════════════════════════════════════════════════════════
#  SECTION CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════

# (display_name, data_key, section_type)
# section_type: "singleton" (one block), "list" (multiple entries)
SECTIONS = [
    ("Header & Title", "header", "singleton"),
    ("Introduction", "introduction", "singleton"),
    ("Background", "background", "singleton"),
    ("Research Questions", "questions", "list"),
    ("Methodology", "phases", "list"),
    ("Contributions", "contributions", "singleton"),
    ("Relevance", "relevance", "singleton"),
    ("Academic Background", "academic_background", "singleton"),
]


# ══════════════════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════

def entry_display_text(section_key: str, entry) -> str:
    """Return a short display string for the entry list."""
    if section_key == "questions":
        return f"RQ{entry.number}: {entry.title[:50]}"
    if section_key == "phases":
        return f"{entry.name} ({entry.period})"
    return str(entry)


def make_default_entry(section_key: str):
    """Create a blank entry of the correct type."""
    if section_key == "questions":
        return ResearchQuestion("", "", "")
    if section_key == "phases":
        return MethodologyPhase("", "", "")
    return None


# ══════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════════════════════

class ResearchPlanManagerApp(tk.Tk):
    CONTENT_FILE = "content.tex"

    def __init__(self, plan_dir=None):
        super().__init__()
        base = os.path.dirname(os.path.abspath(__file__))
        if plan_dir:
            self.WORKING_DIR = os.path.abspath(plan_dir)
        else:
            self.WORKING_DIR = os.path.join(base, "research-plan")
        self.title("Research Plan Manager")
        self.geometry("1100x720")
        self.minsize(900, 550)

        self.parser = PlanTexParser()
        self.generator = PlanTexGenerator()
        self.data = ResearchPlanData()
        self.current_section_key = None
        self.current_section_type = None
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

    # ── build UI ─────────────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        top_bar = ttk.Frame(self)
        top_bar.pack(fill=tk.X, padx=8, pady=(8, 0))
        ttk.Button(top_bar, text="Reload from file", command=self._load_data).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(top_bar, text="Save & Compile PDF",
                    command=self._save_and_compile).pack(side=tk.RIGHT, padx=4)

        # Main 3-panel area
        main = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Left: section list
        left = ttk.LabelFrame(main, text="Sections", width=180)
        self.section_listbox = tk.Listbox(left, exportselection=False)
        for display_name, _, _ in SECTIONS:
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
        self.editor_scrollbar = ttk.Scrollbar(
            right, orient=tk.VERTICAL, command=self.editor_canvas.yview
        )
        self.editor_container = ttk.Frame(self.editor_canvas)
        self.editor_container.bind(
            "<Configure>",
            lambda e: self.editor_canvas.configure(
                scrollregion=self.editor_canvas.bbox("all")
            ),
        )
        self.editor_canvas.create_window(
            (0, 0), window=self.editor_container, anchor="nw"
        )
        self.editor_canvas.configure(yscrollcommand=self.editor_scrollbar.set)
        self.editor_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.editor_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Save entry button
        self.save_btn_frame = ttk.Frame(right)
        self.save_btn_frame.pack(fill=tk.X, padx=8, pady=4)
        ttk.Button(self.save_btn_frame, text="Save Entry",
                    command=self._save_current_entry).pack(side=tk.RIGHT, padx=4)
        main.add(right, weight=3)

        # Bottom: status bar
        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w")
        status.pack(fill=tk.X, padx=8, pady=(0, 8))

    # ── data loading ─────────────────────────────────────────────────

    def _load_data(self):
        filepath = os.path.join(self.WORKING_DIR, self.CONTENT_FILE)
        try:
            self.data = self.parser.parse(filepath)
            if not self.data.header:
                self.data.header = PlanHeaderData("", "", "", "")
            self.status_var.set(f"Loaded {filepath}")
            self.dirty = False
        except Exception as e:
            messagebox.showerror("Parse Error", f"Could not parse {filepath}:\n{e}")
            self.data = ResearchPlanData(header=PlanHeaderData("", "", "", ""))
        self._update_title()
        if self.current_section_key:
            self._populate_entry_list()

    def _update_title(self):
        dirty_mark = " *" if self.dirty else ""
        self.title(f"Research Plan Manager \u2014 {os.path.basename(self.WORKING_DIR)}{dirty_mark}")

    # ── section selection ────────────────────────────────────────────

    def _on_section_select(self, event):
        sel = self.section_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        display_name, key, section_type = SECTIONS[idx]
        self.current_section_key = key
        self.current_section_type = section_type

        # Disable add/delete/reorder buttons for singleton sections
        is_list = section_type == "list"
        state = tk.NORMAL if is_list else tk.DISABLED
        self.btn_add.config(state=state)
        self.btn_del.config(state=state)
        self.btn_up.config(state=state)
        self.btn_down.config(state=state)

        self._populate_entry_list()
        self._clear_editor()

        if section_type == "singleton":
            self._load_singleton_editor(key)
        elif is_list:
            # Select first entry if available
            entries = getattr(self.data, key, [])
            if entries:
                self.entry_listbox.selection_set(0)
                self._on_entry_select(None)

    def _populate_entry_list(self):
        self.entry_listbox.delete(0, tk.END)
        key = self.current_section_key
        if not key:
            return

        if self.current_section_type == "singleton":
            self.entry_listbox.insert(tk.END, "(single section)")
            return

        entries = getattr(self.data, key, [])
        for entry in entries:
            self.entry_listbox.insert(tk.END, entry_display_text(key, entry))

    # ── editor loading ───────────────────────────────────────────────

    def _clear_editor(self):
        for widget in self.editor_container.winfo_children():
            widget.destroy()
        self.current_editor = None
        self.selected_index = None

    def _load_singleton_editor(self, key: str):
        self._clear_editor()

        if key == "header":
            editor = PlanHeaderEditor(
                self.editor_container, self.data.header, self.data.title
            )
        elif key == "introduction":
            editor = TextSectionEditor(
                self.editor_container, self.data.introduction,
                label="Introduction and Motivation"
            )
        elif key == "background":
            editor = BackgroundEditor(
                self.editor_container, self.data.background_text,
                self.data.background_bullets
            )
        elif key == "contributions":
            editor = ContributionsEditor(
                self.editor_container, self.data.contributions
            )
        elif key == "relevance":
            editor = TextSectionEditor(
                self.editor_container, self.data.relevance,
                label="Relevance to the Laboratory"
            )
        elif key == "academic_background":
            editor = TextSectionEditor(
                self.editor_container, self.data.academic_background,
                label="Academic Background"
            )
        else:
            return

        editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.current_editor = editor

    def _on_entry_select(self, event):
        if self.current_section_type != "list":
            return
        sel = self.entry_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.selected_index = idx

        self._clear_editor()
        key = self.current_section_key
        entries = getattr(self.data, key, [])
        if idx >= len(entries):
            return

        entry = entries[idx]

        if key == "questions":
            editor = ResearchQuestionEditor(self.editor_container, entry)
        elif key == "phases":
            editor = MethodologyPhaseEditor(self.editor_container, entry)
        else:
            return

        editor.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.current_editor = editor

    # ── saving entries ───────────────────────────────────────────────

    def _save_current_entry(self):
        if not self.current_editor:
            return

        key = self.current_section_key

        if key == "header":
            self.data.title = self.current_editor.save()
        elif key == "introduction":
            self.data.introduction = self.current_editor.get_text()
        elif key == "background":
            self.data.background_text = self.current_editor.get_text()
            self.data.background_bullets = self.current_editor.get_bullets()
        elif key == "contributions":
            self.data.contributions = self.current_editor.get_bullets()
        elif key == "relevance":
            self.data.relevance = self.current_editor.get_text()
        elif key == "academic_background":
            self.data.academic_background = self.current_editor.get_text()
        elif key == "questions" and self.selected_index is not None:
            entry = self.current_editor.save()
            self.data.questions[self.selected_index] = entry
            self._populate_entry_list()
            self.entry_listbox.selection_set(self.selected_index)
        elif key == "phases" and self.selected_index is not None:
            entry = self.current_editor.save()
            self.data.phases[self.selected_index] = entry
            self._populate_entry_list()
            self.entry_listbox.selection_set(self.selected_index)

        self.dirty = True
        self._update_title()
        self.status_var.set("Entry saved.")

    # ── CRUD for list sections ───────────────────────────────────────

    def _add_entry(self):
        key = self.current_section_key
        if self.current_section_type != "list":
            return
        entries = getattr(self.data, key)
        new_entry = make_default_entry(key)
        if new_entry is None:
            return
        entries.append(new_entry)
        self.dirty = True
        self._update_title()
        self._populate_entry_list()
        self.entry_listbox.selection_set(len(entries) - 1)
        self._on_entry_select(None)

    def _delete_entry(self):
        key = self.current_section_key
        if self.current_section_type != "list" or self.selected_index is None:
            return
        entries = getattr(self.data, key)
        if not entries:
            return
        if not messagebox.askyesno("Delete", "Delete this entry?"):
            return
        entries.pop(self.selected_index)
        self.dirty = True
        self._update_title()
        self._populate_entry_list()
        self._clear_editor()

    def _move_up(self):
        key = self.current_section_key
        if self.selected_index is None or self.selected_index <= 0:
            return
        entries = getattr(self.data, key)
        i = self.selected_index
        entries[i - 1], entries[i] = entries[i], entries[i - 1]
        self.dirty = True
        self._update_title()
        self._populate_entry_list()
        self.entry_listbox.selection_set(i - 1)
        self.selected_index = i - 1

    def _move_down(self):
        key = self.current_section_key
        entries = getattr(self.data, key)
        if self.selected_index is None or self.selected_index >= len(entries) - 1:
            return
        i = self.selected_index
        entries[i], entries[i + 1] = entries[i + 1], entries[i]
        self.dirty = True
        self._update_title()
        self._populate_entry_list()
        self.entry_listbox.selection_set(i + 1)
        self.selected_index = i + 1

    # ── save & compile ───────────────────────────────────────────────

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
            self._update_title()
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

    # ── close handler ────────────────────────────────────────────────

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
    plan_dir = sys.argv[1] if len(sys.argv) > 1 else None
    app = ResearchPlanManagerApp(plan_dir=plan_dir)
    app.mainloop()
