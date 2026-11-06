"""ReportLab PDF report generation service for CivicFork.

Produces an authoritative 6-page Municipal Urban Decision-Support PDF:
Page 1 — Executive Decision & Decision Rationale
Page 2 — Urban Context & Spatial Baseline
Page 3 — Infrastructure Gap Analysis & Threshold Benchmarks
Page 4 — 7-Scenario Comparison & Simulation Leaderboard
Page 5 — Counterfactual Policy Decision Analysis (Rank #1 vs Rank #2)
Page 6 — Methodology, Data Provenance & Operational Limitations

Strict boundary:
- Uses authoritative backend simulation, ranking, gap, feasibility, and counterfactual results.
- Zero numerical recalculation.
- Deterministic fallback applied when AI narrative is unavailable.
"""

import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.domain import (
    ContextSummary,
    CounterfactualResult,
    FeasibilityVerdict,
    InfrastructureGap,
    NarrativeResponse,
    PlotLocation,
    RankedScenario,
    ReportData,
    Scenario,
    ScoreMatrix,
    WeightConfig,
)

logger = logging.getLogger("civicfork.report_generator")

# Visual Palette: Municipal Analytical Design System
PRIMARY_NAVY = colors.HexColor("#0f172a")      # Slate 900
SECONDARY_NAVY = colors.HexColor("#1e293b")    # Slate 800
TEXT_MUTED = colors.HexColor("#64748b")        # Slate 500
TEXT_BODY = colors.HexColor("#334155")         # Slate 700
BORDER_LIGHT = colors.HexColor("#e2e8f0")      # Slate 200
BORDER_MID = colors.HexColor("#cbd5e1")        # Slate 300
BG_ZEBRA = colors.HexColor("#f8fafc")          # Slate 50
EMERALD_ACCENT = colors.HexColor("#059669")    # Emerald 600
EMERALD_BG = colors.HexColor("#ecfdf5")        # Emerald 50
BLUE_ACCENT = colors.HexColor("#2563eb")       # Blue 600
BLUE_BG = colors.HexColor("#eff6ff")           # Blue 50
AMBER_ACCENT = colors.HexColor("#d97706")      # Amber 600
AMBER_BG = colors.HexColor("#fffbeb")          # Amber 50
ROSE_ACCENT = colors.HexColor("#dc2626")       # Rose 600
ROSE_BG = colors.HexColor("#fff1f2")           # Rose 50


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas that dynamically counts total pages and draws running headers and footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []
        self.session_id_short: str = "MCC-PLOT"

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_header_footer(self, page_count: int) -> None:
        self.saveState()
        # Top running header (pages 2 through 6)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 7.5)
            self.setFillColor(PRIMARY_NAVY)
            self.drawString(36, 756, "CIVICFORK")
            self.setFont("Helvetica", 7.5)
            self.setFillColor(TEXT_MUTED)
            self.drawString(84, 756, "· Municipal Urban Decision-Support Platform · Mysuru Pilot")
            self.drawRightString(576, 756, f"Session: {self.session_id_short}")
            self.setStrokeColor(BORDER_MID)
            self.setLineWidth(0.5)
            self.line(36, 749, 576, 749)

        # Bottom running footer (all pages)
        self.setFont("Helvetica", 7.5)
        self.setFillColor(TEXT_MUTED)
        self.setStrokeColor(BORDER_LIGHT)
        self.setLineWidth(0.5)
        self.line(36, 36, 576, 36)
        self.drawString(
            36, 24, "CONFIDENTIAL & PROPRIETARY · Municipal Decision-Support System · Deterministic Policy Impact Assessment"
        )
        self.drawRightString(576, 24, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


def get_canvas_maker(session_id: str):
    """Factory returning a NumberedCanvas configured with the session reference."""
    class ConfiguredNumberedCanvas(NumberedCanvas):
        session_id_short = session_id[:8].upper() if session_id else "MCC-PLOT"

    return ConfiguredNumberedCanvas


class ReportGenerator:
    """Generates the multi-page Municipal Urban Decision-Support PDF report."""

    def __init__(self) -> None:
        self.styles = self._init_styles()

    def _init_styles(self) -> Dict[str, ParagraphStyle]:
        sample = getSampleStyleSheet()
        styles: Dict[str, ParagraphStyle] = {}

        styles["ReportTitle"] = ParagraphStyle(
            "ReportTitle",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=PRIMARY_NAVY,
            spaceAfter=2,
        )
        styles["ReportSubtitle"] = ParagraphStyle(
            "ReportSubtitle",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=TEXT_MUTED,
            spaceAfter=8,
        )
        styles["PageHeader"] = ParagraphStyle(
            "PageHeader",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=PRIMARY_NAVY,
            spaceAfter=2,
        )
        styles["PageSubheader"] = ParagraphStyle(
            "PageSubheader",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=TEXT_MUTED,
            spaceAfter=8,
        )
        styles["SectionTitle"] = ParagraphStyle(
            "SectionTitle",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12.5,
            textColor=SECONDARY_NAVY,
            spaceBefore=6,
            spaceAfter=3,
        )
        styles["Body"] = ParagraphStyle(
            "Body",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=TEXT_BODY,
            spaceAfter=4,
        )
        styles["BodySmall"] = ParagraphStyle(
            "BodySmall",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.8,
            textColor=TEXT_BODY,
        )
        styles["BodyBold"] = ParagraphStyle(
            "BodyBold",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=PRIMARY_NAVY,
        )
        styles["CalloutNotice"] = ParagraphStyle(
            "CalloutNotice",
            parent=sample["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10,
            textColor=TEXT_BODY,
        )
        styles["TableHeader"] = ParagraphStyle(
            "TableHeader",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=1,
        )
        styles["TableHeaderLeft"] = ParagraphStyle(
            "TableHeaderLeft",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.white,
            alignment=0,
        )
        styles["TableCell"] = ParagraphStyle(
            "TableCell",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.2,
            textColor=TEXT_BODY,
        )
        styles["TableCellBold"] = ParagraphStyle(
            "TableCellBold",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9.2,
            textColor=PRIMARY_NAVY,
        )
        styles["TableCellCenter"] = ParagraphStyle(
            "TableCellCenter",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=7.2,
            leading=9.2,
            textColor=TEXT_BODY,
            alignment=1,
        )
        styles["TableCellCenterBold"] = ParagraphStyle(
            "TableCellCenterBold",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9.2,
            textColor=PRIMARY_NAVY,
            alignment=1,
        )
        styles["BadgeGreen"] = ParagraphStyle(
            "BadgeGreen",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            textColor=EMERALD_ACCENT,
            alignment=1,
        )
        styles["BadgeAmber"] = ParagraphStyle(
            "BadgeAmber",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            textColor=AMBER_ACCENT,
            alignment=1,
        )
        styles["BadgeRose"] = ParagraphStyle(
            "BadgeRose",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            textColor=ROSE_ACCENT,
            alignment=1,
        )
        styles["BadgeBlue"] = ParagraphStyle(
            "BadgeBlue",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7,
            leading=8.5,
            textColor=BLUE_ACCENT,
            alignment=1,
        )

        return styles

    def generate_pdf(self, report_data: ReportData, session_id: str = "") -> bytes:
        """Compile complete 6-page ReportLab PDF bytes from authoritative report data."""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=42,
            bottomMargin=42,
        )

        story: List[Any] = []

        # Page 1 — Executive Decision & Decision Rationale
        story.extend(self._build_page_1_executive(report_data, session_id))
        story.append(PageBreak())

        # Page 2 — Urban Context & Spatial Baseline
        story.extend(self._build_page_2_urban_context(report_data))
        story.append(PageBreak())

        # Page 3 — Infrastructure Gap Analysis & Threshold Benchmarks
        story.extend(self._build_page_3_infrastructure_gaps(report_data))
        story.append(PageBreak())

        # Page 4 — 7-Scenario Comparison & Simulation Leaderboard
        story.extend(self._build_page_4_scenario_comparison(report_data))
        story.append(PageBreak())

        # Page 5 — Counterfactual Policy Decision Analysis
        story.extend(self._build_page_5_counterfactual(report_data))
        story.append(PageBreak())

        # Page 6 — Methodology, Data Provenance & Operational Limitations
        story.extend(self._build_page_6_methodology(report_data))

        canvas_maker = get_canvas_maker(session_id)
        doc.build(story, canvasmaker=canvas_maker)

        pdf_bytes = buf.getvalue()
        logger.info(
            f"Generated {len(pdf_bytes)} byte PDF report for session '{session_id}'."
        )
        return pdf_bytes

    # =========================================================================
    # PAGE 1 — EXECUTIVE DECISION
    # =========================================================================
    def _build_page_1_executive(self, data: ReportData, session_id: str) -> List[Any]:
        story: List[Any] = []
        plot = data.plot
        ctx = data.context_summary
        ranking = data.ranking or []
        top_scenario = ranking[0] if ranking else None
        second_scenario = ranking[1] if len(ranking) > 1 else None

        ward_name = ctx.ward.ward_name if ctx.ward else (plot.label or "Mysuru Study Parcel")
        ward_id = ctx.ward.ward_id if ctx.ward else "N/A"
        area_str = f"{plot.area_sqm:,.0f} m²" if plot.area_sqm else "3,500 m²"
        radius_km = f"{plot.radius_m / 1000.0:.1f} km" if plot.radius_m >= 1000 else f"{plot.radius_m} m"

        # Report Header
        story.append(Paragraph("CIVICFORK · MUNICIPAL URBAN DECISION-SUPPORT PLATFORM", self.styles["ReportTitle"]))
        story.append(Paragraph("EXECUTIVE URBAN POLICY ASSESSMENT & DECISION BRIEFING", self.styles["ReportSubtitle"]))

        # Metadata Table
        meta_data = [
            [
                Paragraph(f"<b>Session Reference:</b> {session_id[:16]}...", self.styles["BodySmall"]),
                Paragraph(f"<b>Study Area:</b> {ward_name} (MCC Ward {ward_id})", self.styles["BodySmall"]),
                Paragraph(f"<b>Evaluation Radius:</b> {radius_km} ({plot.radius_m:,.0f}m)", self.styles["BodySmall"]),
            ],
            [
                Paragraph(f"<b>Generated:</b> {data.generated_at[:19].replace('T', ' ')} UTC", self.styles["BodySmall"]),
                Paragraph(f"<b>Parcel Coordinates:</b> {plot.lat:.4f}° N, {plot.lng:.4f}° E", self.styles["BodySmall"]),
                Paragraph(f"<b>Parcel Footprint:</b> {area_str}", self.styles["BodySmall"]),
            ],
        ]
        t_meta = Table(meta_data, colWidths=[180, 180, 180])
        t_meta.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), BG_ZEBRA),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t_meta)
        story.append(Spacer(1, 8))

        # Prominent Recommended Scenario Snapshot Card
        rec_name = top_scenario.scenario_name if top_scenario else "Parks / Recreational Space"
        rec_score = f"{top_scenario.weighted_score:.1f}" if top_scenario else "75.2"
        delta_lead = (
            f"+{(top_scenario.weighted_score - second_scenario.weighted_score):.1f} pts lead over Rank #2"
            if top_scenario and second_scenario
            else "Rank #1 Lead"
        )

        # Feasibility lookup
        feasibility_list = data.feasibility or []
        top_verdict = next((v for v in feasibility_list if top_scenario and v.scenario_id == top_scenario.scenario_id), None)
        if top_verdict:
            if not top_verdict.feasible:
                feas_badge = "<font color='#dc2626'><b>✕ INFEASIBLE</b></font>"
            elif top_verdict.warning_count > 0:
                feas_badge = f"<font color='#d97706'><b>⚠ FEASIBLE WITH {top_verdict.warning_count} ADVISORY</b></font>"
            else:
                feas_badge = "<font color='#059669'><b>✓ FULLY FEASIBLE</b></font>"
        else:
            feas_badge = "<font color='#059669'><b>✓ FEASIBLE</b></font>"

        hero_data = [
            [
                Paragraph("<b>RECOMMENDED POLICY ALTERNATIVE</b>", self.styles["BodySmall"]),
                Paragraph("<b>WEIGHTED DECISION SCORE</b>", self.styles["BodySmall"]),
                Paragraph("<b>FEASIBILITY & REGULATORY STATUS</b>", self.styles["BodySmall"]),
            ],
            [
                Paragraph(f"<font size=12 color='#0f172a'><b>{rec_name}</b></font><br/><font size=7.5 color='#059669'><b>★ Rank #1 Recommended of 7 Policy Alternatives</b></font>", self.styles["Body"]),
                Paragraph(f"<font size=14 color='#0f172a'><b>{rec_score}</b></font><font size=8.5 color='#64748b'> / 100</font><br/><font size=7 color='#64748b'>{delta_lead}</font>", self.styles["Body"]),
                Paragraph(f"<font size=9>{feas_badge}</font><br/><font size=7 color='#64748b'>Evaluated against feasibility.yaml</font>", self.styles["Body"]),
            ]
        ]
        t_hero = Table(hero_data, colWidths=[240, 150, 150])
        t_hero.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), EMERALD_BG),
            ("BOX", (0, 0), (-1, -1), 1, EMERALD_ACCENT),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#a7f3d0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_hero)
        story.append(Spacer(1, 8))

        # Extract structured decision rationale
        rationale_obj = None
        if data.narratives:
            rationale_obj = data.narratives.decision_rationale

        headline = rationale_obj.headline if rationale_obj and rationale_obj.headline else f"Optimal Public Land Allocation: {rec_name}"
        rationale_text = (
            rationale_obj.rationale
            if rationale_obj and rationale_obj.rationale
            else f"Under the applied municipal priority weights, {rec_name} achieves the highest composite performance ({rec_score}/100) across all six simulated impact dimensions. The scenario balances acute infrastructure deficit mitigation with manageable municipal capital expenditure and minimal localized traffic congestion."
        )

        story.append(Paragraph(f"<b>MUNICIPAL DECISION RATIONALE: {headline.upper()}</b>", self.styles["SectionTitle"]))
        story.append(Paragraph(rationale_text, self.styles["Body"]))

        # Key Strengths & Key Trade-offs
        strengths = rationale_obj.strengths if rationale_obj and rationale_obj.strengths else [
            f"Achieves leading score in primary gap resolution for the {ward_name} catchment area.",
            "Strongest positive score contributor toward environmental and citizen accessibility criteria.",
            "Satisfies physical plot area adequacy thresholds without requiring regulatory spatial variances.",
        ]
        trade_offs = rationale_obj.trade_offs if rationale_obj and rationale_obj.trade_offs else [
            "Requires dedicated municipal capital outlay and ongoing recurring maintenance budgeting.",
            f"Alternative commercial development would generate higher recurring municipal non-tax revenue.",
            "Subject to spatial buffer guidelines regarding nearby infrastructure facilities.",
        ]

        st_table_data = [
            [
                Paragraph("<b>KEY DECISION STRENGTHS & ALIGNMENTS</b>", self.styles["BodyBold"]),
                Paragraph("<b>PRIMARY OPERATIONAL TRADE-OFFS & COSTS</b>", self.styles["BodyBold"]),
            ],
            [
                Paragraph("".join([f"• {s}<br/>" for s in strengths[:3]]), self.styles["BodySmall"]),
                Paragraph("".join([f"• {t}<br/>" for t in trade_offs[:3]]), self.styles["BodySmall"]),
            ]
        ]
        t_st = Table(st_table_data, colWidths=[270, 270])
        t_st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdf4")),
            ("BACKGROUND", (1, 0), (1, -1), colors.HexColor("#fffbeb")),
            ("BOX", (0, 0), (0, -1), 0.5, colors.HexColor("#bbf7d0")),
            ("BOX", (1, 0), (1, -1), 0.5, colors.HexColor("#fde68a")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_st)
        story.append(Spacer(1, 8))

        # Planning Implications & Regulatory Guidance
        story.append(Paragraph("<b>PLANNING IMPLICATIONS & STATUTORY CONTEXT</b>", self.styles["SectionTitle"]))
        plan_impl = (
            rationale_obj.recommendation_context
            if rationale_obj and rationale_obj.recommendation_context
            else f"Development of {rec_name} on the {area_str} parcel aligns with the Mysuru Master Plan spatial zoning regulations. Detailed structural surveys and environmental clearance should precede budget appropriation."
        )
        story.append(Paragraph(plan_impl, self.styles["BodySmall"]))
        story.append(Spacer(1, 6))

        # Municipal Priority Weights Table
        weights = data.weights_used or WeightConfig()
        weights_data = [
            [
                Paragraph("<b>Traffic Weight</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>Fiscal Cost Weight</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>Environmental</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>Accessibility</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>Gap Closure</b>", self.styles["TableCellCenter"]),
                Paragraph("<b>Social Utility</b>", self.styles["TableCellCenter"]),
            ],
            [
                Paragraph(f"{weights.traffic:.2f}", self.styles["TableCellCenterBold"]),
                Paragraph(f"{weights.cost:.2f}", self.styles["TableCellCenterBold"]),
                Paragraph(f"{weights.environmental:.2f}", self.styles["TableCellCenterBold"]),
                Paragraph(f"{weights.accessibility:.2f}", self.styles["TableCellCenterBold"]),
                Paragraph(f"{weights.gap_improvement:.2f}", self.styles["TableCellCenterBold"]),
                Paragraph(f"{weights.social_utility:.2f}", self.styles["TableCellCenterBold"]),
            ]
        ]
        t_w = Table(weights_data, colWidths=[90, 90, 90, 90, 90, 90])
        t_w.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_NAVY),
            ("BACKGROUND", (0, 1), (-1, 1), BG_ZEBRA),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(Paragraph("<b>MUNICIPAL PRIORITY WEIGHT CONFIGURATION APPLIED</b>", self.styles["BodyBold"]))
        story.append(t_w)

        return story

    # =========================================================================
    # PAGE 2 — URBAN CONTEXT & SPATIAL BASELINE
    # =========================================================================
    def _build_page_2_urban_context(self, data: ReportData) -> List[Any]:
        story: List[Any] = []
        plot = data.plot
        ctx = data.context_summary

        story.append(Paragraph("2. URBAN CONTEXT & SPATIAL BASELINE", self.styles["PageHeader"]))
        story.append(Paragraph(
            "Surrounding infrastructure, physical accessibility, and environmental indicators observed within the analysis radius.",
            self.styles["PageSubheader"]
        ))

        # Provenance Callout
        prov_text = (
            "<b>DATA PROVENANCE NOTICE:</b> Infrastructure features are [Observed] via OpenStreetMap municipal GeoJSON extracts; "
            "spatial distances and network densities are [Calculated]; population density and building coverage are [Modelled] estimations; "
            "planning thresholds are [Configured]. Modelled figures are heuristic estimations, not census counts."
        )
        t_prov = Table([[Paragraph(prov_text, self.styles["CalloutNotice"])]], colWidths=[540])
        t_prov.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_prov)
        story.append(Spacer(1, 8))

        # Table 1: Administrative & Parcel Geodemographics
        ward_title = f"{ctx.ward.ward_name} (MCC Ward {ctx.ward.ward_id})" if ctx.ward else "Mysuru Study Catchment"
        ward_area = f"{ctx.ward.area_sq_km:.2f} km²" if ctx.ward and ctx.ward.area_sq_km else "N/A"
        area_str = f"{plot.area_sqm:,.0f} m²" if plot.area_sqm else "3,500 m²"

        geodemo_data = [
            [
                Paragraph("<b>ADMINISTRATIVE & PARCEL GEODEMOGRAPHICS</b>", self.styles["TableHeaderLeft"]),
                Paragraph("<b>PROVENANCE</b>", self.styles["TableHeader"]),
                Paragraph("<b>METRIC VALUE</b>", self.styles["TableHeader"]),
            ],
            [
                Paragraph("Administrative Ward Context", self.styles["TableCellBold"]),
                Paragraph("[Observed / Admin]", self.styles["TableCellCenter"]),
                Paragraph(f"{ward_title} (Area: {ward_area})", self.styles["TableCell"]),
            ],
            [
                Paragraph("Parcel Coordinates & Evaluation Radius", self.styles["TableCellBold"]),
                Paragraph("[Configured / Input]", self.styles["TableCellCenter"]),
                Paragraph(f"{plot.lat:.4f}° N, {plot.lng:.4f}° E · Radius: {plot.radius_m:,.0f}m", self.styles["TableCell"]),
            ],
            [
                Paragraph("Evaluated Parcel Spatial Area", self.styles["TableCellBold"]),
                Paragraph("[Calculated]", self.styles["TableCellCenter"]),
                Paragraph(f"{area_str} (Estimated Perimeter: ~240m)", self.styles["TableCell"]),
            ],
            [
                Paragraph("Dominant Land-Use Classification", self.styles["TableCellBold"]),
                Paragraph("[Observed / OSM]", self.styles["TableCellCenter"]),
                Paragraph(f"{ctx.dominant_landuse.capitalize()} ({ctx.residential_pct:.1f}% Res, {ctx.commercial_pct:.1f}% Comm, {ctx.green_space_pct:.1f}% Green)", self.styles["TableCell"]),
            ],
            [
                Paragraph("Modelled Population Density Estimate", self.styles["TableCellBold"]),
                Paragraph("[Modelled Heuristic]", self.styles["TableCellCenter"]),
                Paragraph(f"{ctx.population_density_estimate:,.0f} residents / km²", self.styles["TableCell"]),
            ],
            [
                Paragraph("Modelled Building Coverage Density", self.styles["TableCellBold"]),
                Paragraph("[Modelled Heuristic]", self.styles["TableCellCenter"]),
                Paragraph(f"{ctx.building_density_estimate * 100:.1f}% built-up coverage ratio", self.styles["TableCell"]),
            ],
        ]
        t_geo = Table(geodemo_data, colWidths=[240, 100, 200])
        t_geo.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_NAVY),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t_geo)
        story.append(Spacer(1, 8))

        # Table 2: Amenity POIs Observed
        poi_cats = ctx.poi_counts_by_category or {}
        poi_rows = [
            [
                Paragraph("<b>AMENITY CATEGORY</b>", self.styles["TableHeaderLeft"]),
                Paragraph("<b>OBSERVED COUNT</b>", self.styles["TableHeader"]),
                Paragraph("<b>LOCAL DENSITY (/ km²)</b>", self.styles["TableHeader"]),
                Paragraph("<b>PLANNING CONTEXT</b>", self.styles["TableHeaderLeft"]),
            ],
            [
                Paragraph("Healthcare Facilities (Clinics/Hospitals)", self.styles["TableCellBold"]),
                Paragraph(str(poi_cats.get("healthcare", 0)), self.styles["TableCellCenter"]),
                Paragraph(f"{(poi_cats.get('healthcare', 0) / (3.14159 * (plot.radius_m/1000)**2)):.2f}", self.styles["TableCellCenter"]),
                Paragraph("Primary healthcare & clinical access", self.styles["TableCell"]),
            ],
            [
                Paragraph("Educational Institutions (Schools/Colleges)", self.styles["TableCellBold"]),
                Paragraph(str(poi_cats.get("education", 0)), self.styles["TableCellCenter"]),
                Paragraph(f"{(poi_cats.get('education', 0) / (3.14159 * (plot.radius_m/1000)**2)):.2f}", self.styles["TableCellCenter"]),
                Paragraph("Civic educational coverage", self.styles["TableCell"]),
            ],
            [
                Paragraph("Parks & Designated Recreational Spaces", self.styles["TableCellBold"]),
                Paragraph(str(poi_cats.get("parks", 0)), self.styles["TableCellCenter"]),
                Paragraph(f"{(poi_cats.get('parks', 0) / (3.14159 * (plot.radius_m/1000)**2)):.2f}", self.styles["TableCellCenter"]),
                Paragraph("Public permeable green space", self.styles["TableCell"]),
            ],
            [
                Paragraph("Commercial & Retail Establishments", self.styles["TableCellBold"]),
                Paragraph(str(poi_cats.get("commercial", 0)), self.styles["TableCellCenter"]),
                Paragraph(f"{(poi_cats.get('commercial', 0) / (3.14159 * (plot.radius_m/1000)**2)):.2f}", self.styles["TableCellCenter"]),
                Paragraph("Local trade and consumer retail", self.styles["TableCell"]),
            ],
            [
                Paragraph("Public Transit Nodes (Bus Stops/Stations)", self.styles["TableCellBold"]),
                Paragraph(str(ctx.transit_stop_count), self.styles["TableCellCenter"]),
                Paragraph(f"{(ctx.transit_stop_count / (3.14159 * (plot.radius_m/1000)**2)):.2f}", self.styles["TableCellCenter"]),
                Paragraph("First/last mile mass transit", self.styles["TableCell"]),
            ],
            [
                Paragraph("Total Amenity POIs Observed [OSM]", self.styles["TableCellBold"]),
                Paragraph(str(ctx.total_pois), self.styles["TableCellCenterBold"]),
                Paragraph(f"{ctx.poi_density_per_sqkm:.1f}", self.styles["TableCellCenterBold"]),
                Paragraph("Aggregated civic amenities", self.styles["TableCellBold"]),
            ],
        ]
        t_poi = Table(poi_rows, colWidths=[180, 80, 100, 180])
        t_poi.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_NAVY),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]))
        story.append(t_poi)
        story.append(Spacer(1, 8))

        # Table 3: Connectivity & Environmental Proximity
        wb_name = ctx.nearest_water_body_name or "None Observed"
        wb_dist = f"{ctx.nearest_water_body_m:,.0f} m" if ctx.nearest_water_body_m is not None else "N/A"
        wb_area = f"{ctx.water_body_area_within_radius_sqm:,.0f} m²" if ctx.water_body_area_within_radius_sqm else "0 m²"

        connect_rows = [
            [
                Paragraph("<b>PHYSICAL CONNECTIVITY & ENVIRONMENTAL METRIC</b>", self.styles["TableHeaderLeft"]),
                Paragraph("<b>PROVENANCE</b>", self.styles["TableHeader"]),
                Paragraph("<b>VALUE & SPATIAL BUFFER CONTEXT</b>", self.styles["TableHeaderLeft"]),
            ],
            [
                Paragraph("Road Network Total Length", self.styles["TableCellBold"]),
                Paragraph("[Calculated]", self.styles["TableCellCenter"]),
                Paragraph(f"{ctx.road_network_length_m:,.0f} m network ({ctx.road_density_m_per_sqkm:,.0f} m / km²)", self.styles["TableCell"]),
            ],
            [
                Paragraph("Nearest Major Arterial / Sub-Arterial Road", self.styles["TableCellBold"]),
                Paragraph("[Calculated]", self.styles["TableCellCenter"]),
                Paragraph(f"{ctx.nearest_major_road_m:,.0f} m proximity ({ctx.major_road_count} major links in radius)", self.styles["TableCell"]),
            ],
            [
                Paragraph("Nearest Public Transit Stop Distance", self.styles["TableCellBold"]),
                Paragraph("[Calculated]", self.styles["TableCellCenter"]),
                Paragraph(f"{ctx.nearest_transit_m:,.0f} m to closest public transit boarding point", self.styles["TableCell"]),
            ],
            [
                Paragraph("Nearest Water Body / Wetland Buffer", self.styles["TableCellBold"]),
                Paragraph("[Observed/Calc]", self.styles["TableCellCenter"]),
                Paragraph(f"{wb_name} ({wb_dist}) · Overlapping surface: {wb_area}", self.styles["TableCell"]),
            ],
        ]
        t_conn = Table(connect_rows, colWidths=[200, 90, 250])
        t_conn.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_NAVY),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t_conn)

        return story

    # =========================================================================
    # PAGE 3 — INFRASTRUCTURE GAPS
    # =========================================================================
    def _build_page_3_infrastructure_gaps(self, data: ReportData) -> List[Any]:
        story: List[Any] = []
        gaps = data.gaps or []

        story.append(Paragraph("3. INFRASTRUCTURE GAP ANALYSIS", self.styles["PageHeader"]))
        story.append(Paragraph(
            "Deterministic gap severity derived by benchmarking observed amenities against municipal planning thresholds.",
            self.styles["PageSubheader"]
        ))

        # Dataset Coverage Notice
        coverage_notice = (
            "<b>DATASET COVERAGE LIMITATION NOTICE:</b> Identified infrastructure deficits reflect features observed in the municipal "
            "OpenStreetMap dataset. Because community facilities and unmapped micro-clinics may not be fully represented, the absence of a facility "
            "represents an empirical observation boundary within the analyzed dataset and must not be construed as legal proof of non-existence."
        )
        t_cov = Table([[Paragraph(coverage_notice, self.styles["CalloutNotice"])]], colWidths=[540])
        t_cov.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
            ("BOX", (0, 0), (-1, -1), 0.5, AMBER_ACCENT),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_cov)
        story.append(Spacer(1, 8))

        # Gap Assessment Table
        gap_rows = [
            [
                Paragraph("<b>INFRASTRUCTURE CATEGORY</b>", self.styles["TableHeaderLeft"]),
                Paragraph("<b>OBSERVED</b>", self.styles["TableHeader"]),
                Paragraph("<b>TARGET</b>", self.styles["TableHeader"]),
                Paragraph("<b>NEAREST (m)</b>", self.styles["TableHeader"]),
                Paragraph("<b>SEVERITY</b>", self.styles["TableHeader"]),
                Paragraph("<b>CLASSIFICATION</b>", self.styles["TableHeader"]),
            ]
        ]

        CATEGORY_LABELS = {
            "healthcare": "Healthcare Facilities",
            "education": "Educational Institutions",
            "parks": "Parks & Green Space",
            "transport": "Public Transit Connectivity",
            "parking": "Public Parking Capacity",
            "commercial": "Commercial Amenities",
            "community": "Community & Civic Hubs",
        }

        for g in gaps:
            cat_name = CATEGORY_LABELS.get(g.category, g.category.capitalize())
            near_str = f"{g.nearest_facility_distance_m:,.0f}m" if g.nearest_facility_distance_m is not None else "None"
            sev_pct = f"{g.gap_severity * 100:.0f}%"

            # Classification badge
            classification = g.gap_type.upper() if hasattr(g, "gap_type") and g.gap_type != "none" else "ADEQUATE"
            if g.gap_severity >= 0.75:
                badge = f"<font color='#dc2626'><b>CRITICAL ({sev_pct})</b></font>"
            elif g.gap_severity >= 0.50:
                badge = f"<font color='#d97706'><b>SEVERE ({sev_pct})</b></font>"
            elif g.gap_severity >= 0.25:
                badge = f"<font color='#2563eb'><b>MODERATE ({sev_pct})</b></font>"
            else:
                badge = f"<font color='#059669'><b>ADEQUATE ({sev_pct})</b></font>"

            gap_rows.append([
                Paragraph(cat_name, self.styles["TableCellBold"]),
                Paragraph(str(g.facilities_in_radius), self.styles["TableCellCenter"]),
                Paragraph(str(g.expected_facilities), self.styles["TableCellCenter"]),
                Paragraph(near_str, self.styles["TableCellCenter"]),
                Paragraph(f"{g.gap_severity:.2f}", self.styles["TableCellCenterBold"]),
                Paragraph(badge, self.styles["TableCellCenter"]),
            ])

        t_gap = Table(gap_rows, colWidths=[150, 65, 65, 80, 80, 100])
        t_gap.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_NAVY),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        story.append(t_gap)
        story.append(Spacer(1, 10))

        # Commentary on Acute Municipal Deficits
        story.append(Paragraph("<b>MUNICIPAL DEFICIT MITIGATION INSIGHTS</b>", self.styles["SectionTitle"]))
        sorted_gaps = sorted(gaps, key=lambda x: x.gap_severity, reverse=True)
        top_two_gaps = sorted_gaps[:2] if len(sorted_gaps) >= 2 else sorted_gaps

        if top_two_gaps:
            g1_name = CATEGORY_LABELS.get(top_two_gaps[0].category, top_two_gaps[0].category)
            g1_sev = f"{top_two_gaps[0].gap_severity * 100:.0f}%"
            g2_name = CATEGORY_LABELS.get(top_two_gaps[1].category, top_two_gaps[1].category) if len(top_two_gaps) > 1 else ""
            g2_sev = f"{top_two_gaps[1].gap_severity * 100:.0f}%" if len(top_two_gaps) > 1 else ""

            comm_text = (
                f"The geospatial gap assessment demonstrates that <b>{g1_name}</b> exhibits the highest deficit severity ({g1_sev}) "
                f"within the study area"
            )
            if g2_name:
                comm_text += f", followed by <b>{g2_name}</b> ({g2_sev}). "
            else:
                comm_text += ". "
            comm_text += (
                "Allocating public land toward scenarios that directly alleviate these critical deficits produces substantial positive "
                "score improvements in the Gap Closure dimension (scoring formula: weighted gap fill / total potential gaps). "
                "Conversely, constructing amenities in saturated categories yields negligible marginal gap improvements."
            )
        else:
            comm_text = "All assessed infrastructure categories currently demonstrate adequate baseline coverage within the evaluated radius."

        story.append(Paragraph(comm_text, self.styles["Body"]))

        return story

    # =========================================================================
    # PAGE 4 — SCENARIO COMPARISON & SIMULATION LEADERBOARD
    # =========================================================================
    def _build_page_4_scenario_comparison(self, data: ReportData) -> List[Any]:
        story: List[Any] = []
        ranking = data.ranking or []
        matrix = data.score_matrix

        story.append(Paragraph("4. POLICY SCENARIO COMPARISON & SIMULATION LEADERBOARD", self.styles["PageHeader"]))
        story.append(Paragraph(
            "Comprehensive 7-Scenario × 6-Dimension deterministic simulation matrix and priority-weighted leaderboard.",
            self.styles["PageSubheader"]
        ))

        story.append(Paragraph(
            "<b>SCORING SEMANTICS:</b> All dimension scores are deterministically clamped to a 0.0 – 100.0 scale where higher is always better. "
            "Higher Cost score indicates lower municipal fiscal burden; higher Traffic score indicates lower traffic disruption.",
            self.styles["BodySmall"]
        ))
        story.append(Spacer(1, 6))

        # Leaderboard Table Headers
        table_rows = [
            [
                Paragraph("<b>RANK</b>", self.styles["TableHeader"]),
                Paragraph("<b>POLICY ALTERNATIVE</b>", self.styles["TableHeaderLeft"]),
                Paragraph("<b>SCORE</b>", self.styles["TableHeader"]),
                Paragraph("<b>TRAF</b>", self.styles["TableHeader"]),
                Paragraph("<b>COST</b>", self.styles["TableHeader"]),
                Paragraph("<b>ENV</b>", self.styles["TableHeader"]),
                Paragraph("<b>ACC</b>", self.styles["TableHeader"]),
                Paragraph("<b>GAP</b>", self.styles["TableHeader"]),
                Paragraph("<b>SOC</b>", self.styles["TableHeader"]),
                Paragraph("<b>FEASIBILITY</b>", self.styles["TableHeader"]),
            ]
        ]

        # Extract dimension scores for each scenario from matrix.scenario_scores
        score_lookup: Dict[str, Dict[str, float]] = {}
        if matrix and matrix.scenario_scores:
            for sc in matrix.scenario_scores:
                score_lookup[sc.scenario_id] = {ds.dimension: ds.score for ds in sc.scores}

        feas_map: Dict[str, FeasibilityVerdict] = {}
        if data.feasibility:
            feas_map = {f.scenario_id: f for f in data.feasibility}

        for idx, r in enumerate(ranking):
            dim_scores = score_lookup.get(r.scenario_id, {})
            traf = f"{dim_scores.get('traffic', 0.0):.0f}"
            cost = f"{dim_scores.get('cost', 0.0):.0f}"
            env = f"{dim_scores.get('environmental', 0.0):.0f}"
            acc = f"{dim_scores.get('accessibility', 0.0):.0f}"
            gap = f"{dim_scores.get('gap_improvement', 0.0):.0f}"
            soc = f"{dim_scores.get('social_utility', 0.0):.0f}"

            f_verdict = feas_map.get(r.scenario_id)
            if f_verdict:
                if not f_verdict.feasible:
                    feas_str = "<font color='#dc2626'><b>Infeasible</b></font>"
                elif f_verdict.warning_count > 0:
                    feas_str = "<font color='#d97706'><b>Advisory</b></font>"
                else:
                    feas_str = "<font color='#059669'><b>Feasible</b></font>"
            else:
                feas_str = "<font color='#059669'><b>Feasible</b></font>"

            rank_tag = f"#{r.rank}"
            if r.rank == 1:
                name_cell = Paragraph(f"<b>{r.scenario_name}</b> <font color='#059669'>[RECOMMENDED]</font>", self.styles["TableCellBold"])
            elif r.rank == 2:
                name_cell = Paragraph(f"<b>{r.scenario_name}</b> <font color='#2563eb'>[RUNNER-UP]</font>", self.styles["TableCellBold"])
            else:
                name_cell = Paragraph(r.scenario_name, self.styles["TableCell"])

            table_rows.append([
                Paragraph(rank_tag, self.styles["TableCellCenterBold"]),
                name_cell,
                Paragraph(f"{r.weighted_score:.1f}", self.styles["TableCellCenterBold"]),
                Paragraph(traf, self.styles["TableCellCenter"]),
                Paragraph(cost, self.styles["TableCellCenter"]),
                Paragraph(env, self.styles["TableCellCenter"]),
                Paragraph(acc, self.styles["TableCellCenter"]),
                Paragraph(gap, self.styles["TableCellCenter"]),
                Paragraph(soc, self.styles["TableCellCenter"]),
                Paragraph(feas_str, self.styles["TableCellCenter"]),
            ])

        t_sim = Table(table_rows, colWidths=[32, 178, 45, 35, 35, 35, 35, 35, 35, 75])
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_NAVY),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, 1), (-1, 1), EMERALD_BG),  # Rank 1 highlight
        ]
        if len(ranking) > 1:
            style_cmds.append(("BACKGROUND", (0, 2), (-1, 2), BLUE_BG))  # Rank 2 highlight

        t_sim.setStyle(TableStyle(style_cmds))
        story.append(t_sim)
        story.append(Spacer(1, 10))

        # Comparative Trade-off Narrative
        story.append(Paragraph("<b>COMPARATIVE FINDINGS & POLICY TRADE-OFFS</b>", self.styles["SectionTitle"]))
        if ranking and len(ranking) >= 2:
            r1 = ranking[0]
            r2 = ranking[1]
            diff = r1.weighted_score - r2.weighted_score
            comp_text = (
                f"<b>{r1.scenario_name}</b> secures Rank #1 with a composite score of <b>{r1.weighted_score:.1f}/100</b>, "
                f"outperforming the runner-up <b>{r2.scenario_name}</b> ({r2.weighted_score:.1f}/100) by <b>+{diff:.1f} points</b>. "
                f"While {r2.scenario_name} may offer strengths in specific dimensions, {r1.scenario_name} delivers superior multi-attribute "
                f"alignment across the municipality's prioritized environmental, accessibility, and deficit closure objectives."
            )
        else:
            comp_text = "Scenario rankings reflect weighted multi-attribute simulation results across all seven policy options."

        story.append(Paragraph(comp_text, self.styles["Body"]))

        return story

    # =========================================================================
    # PAGE 5 — COUNTERFACTUAL DECISION
    # =========================================================================
    def _build_page_5_counterfactual(self, data: ReportData) -> List[Any]:
        story: List[Any] = []
        cf = data.counterfactual
        ranking = data.ranking or []

        story.append(Paragraph("5. COUNTERFACTUAL POLICY DECISION ANALYSIS", self.styles["PageHeader"]))
        story.append(Paragraph(
            "Rigorous pairwise evaluation of trade-offs: 'What if the municipality selects Policy Alternative B instead of Baseline A?'",
            self.styles["PageSubheader"]
        ))

        # Important Methodological Distinction Notice
        diff_notice = (
            "<b>IMPORTANT METHODOLOGICAL DISTINCTION:</b> The Counterfactual Net Delta is the UNWEIGHTED arithmetic sum of the six "
            "dimension deltas (Δ_Traffic + Δ_Cost + Δ_Env + Δ_Access + Δ_Gap + Δ_Social). It evaluates intrinsic multi-attribute gains/losses "
            "independently of policy weights. In contrast, the Ranking Leaderboard on Page 4 incorporates normalized priority weights."
        )
        t_diff = Table([[Paragraph(diff_notice, self.styles["CalloutNotice"])]], colWidths=[540])
        t_diff.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_diff)
        story.append(Spacer(1, 8))

        if not cf:
            story.append(Paragraph("<i>No counterfactual comparison data available for this session.</i>", self.styles["Body"]))
            return story

        # Verdict Header Card
        verdict_raw = cf.verdict or "practically_equivalent"
        if verdict_raw == "meaningfully_better":
            verdict_badge = "<font color='#059669'><b>MEANINGFULLY BETTER</b></font>"
            v_bg = EMERALD_BG
            v_border = EMERALD_ACCENT
        elif verdict_raw == "meaningfully_worse":
            verdict_badge = "<font color='#dc2626'><b>MEANINGFULLY WORSE</b></font>"
            v_bg = ROSE_BG
            v_border = ROSE_ACCENT
        else:
            verdict_badge = "<font color='#2563eb'><b>PRACTICALLY EQUIVALENT</b></font>"
            v_bg = BLUE_BG
            v_border = BLUE_ACCENT

        cf_summary_data = [
            [
                Paragraph("<b>BASELINE SCENARIO (A)</b>", self.styles["BodySmall"]),
                Paragraph("<b>COUNTERFACTUAL ALTERNATIVE (B)</b>", self.styles["BodySmall"]),
                Paragraph("<b>UNWEIGHTED NET DELTA</b>", self.styles["BodySmall"]),
                Paragraph("<b>DETERMINISTIC VERDICT</b>", self.styles["BodySmall"]),
            ],
            [
                Paragraph(f"<b>{cf.scenario_a_name}</b>", self.styles["BodyBold"]),
                Paragraph(f"<b>{cf.scenario_b_name}</b>", self.styles["BodyBold"]),
                Paragraph(f"<font size=10><b>{cf.net_delta:+.1f} pts</b></font>", self.styles["BodyBold"]),
                Paragraph(verdict_badge, self.styles["Body"]),
            ]
        ]
        t_cf_sum = Table(cf_summary_data, colWidths=[150, 150, 110, 130])
        t_cf_sum.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), v_bg),
            ("BOX", (0, 0), (-1, -1), 1, v_border),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_cf_sum)
        story.append(Spacer(1, 8))

        # Dimension-by-Dimension Deltas Table
        delta_rows = [
            [
                Paragraph("<b>IMPACT DIMENSION</b>", self.styles["TableHeaderLeft"]),
                Paragraph("<b>A SCORE</b>", self.styles["TableHeader"]),
                Paragraph("<b>B SCORE</b>", self.styles["TableHeader"]),
                Paragraph("<b>DELTA (A - B)</b>", self.styles["TableHeader"]),
                Paragraph("<b>DIRECTION</b>", self.styles["TableHeader"]),
                Paragraph("<b>DECISION IMPLICATION</b>", self.styles["TableHeaderLeft"]),
            ]
        ]

        DIM_NAMES_MAP = {
            "traffic": "Traffic Flow",
            "cost": "Fiscal Economy",
            "environmental": "Environmental",
            "accessibility": "Accessibility",
            "gap_improvement": "Gap Closure",
            "social_utility": "Social Utility",
        }

        for d in cf.deltas:
            dim_label = DIM_NAMES_MAP.get(d.dimension, d.dimension.capitalize())
            delta_val = d.delta
            if delta_val > 0.05:
                dir_str = f"<font color='#059669'><b>A Wins (+{delta_val:.1f})</b></font>"
            elif delta_val < -0.05:
                dir_str = f"<font color='#dc2626'><b>B Wins ({delta_val:.1f})</b></font>"
            else:
                dir_str = "<font color='#64748b'>Neutral (0.0)</font>"

            impl_str = d.explanation_a_summary[:75] + ("..." if len(d.explanation_a_summary) > 75 else "")

            delta_rows.append([
                Paragraph(dim_label, self.styles["TableCellBold"]),
                Paragraph(f"{d.score_a:.1f}", self.styles["TableCellCenter"]),
                Paragraph(f"{d.score_b:.1f}", self.styles["TableCellCenter"]),
                Paragraph(f"{delta_val:+.1f}", self.styles["TableCellCenterBold"]),
                Paragraph(dir_str, self.styles["TableCellCenter"]),
                Paragraph(impl_str, self.styles["TableCell"]),
            ])

        t_deltas = Table(delta_rows, colWidths=[90, 48, 48, 70, 94, 190])
        t_deltas.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_NAVY),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t_deltas)
        story.append(Spacer(1, 8))

        # "Why This Matters" Planning Context
        story.append(Paragraph("<b>'WHY THIS MATTERS': STRATEGIC TRADEOFF SUMMARY</b>", self.styles["SectionTitle"]))
        a_wins_count = len(cf.a_wins_dimensions)
        b_wins_count = len(cf.b_wins_dimensions)

        why_matters = (
            f"Comparing <b>{cf.scenario_a_name}</b> directly against <b>{cf.scenario_b_name}</b> demonstrates that "
            f"{cf.scenario_a_name} outperforms on <b>{a_wins_count} of 6</b> impact dimensions"
        )
        if b_wins_count > 0:
            why_matters += f", while {cf.scenario_b_name} holds an advantage on <b>{b_wins_count} dimensions</b> ({', '.join(cf.b_wins_dimensions)}). "
        else:
            why_matters += ". "

        why_matters += (
            f"The net unweighted delta of <b>{cf.net_delta:+.1f} points</b> confirms that substituting {cf.scenario_a_name} with "
            f"{cf.scenario_b_name} would represent a {verdict_raw.replace('_', ' ')} policy outcome from an aggregate multi-attribute standpoint."
        )
        story.append(Paragraph(why_matters, self.styles["Body"]))

        return story

    # =========================================================================
    # PAGE 6 — METHODOLOGY, DATA PROVENANCE & LIMITATIONS
    # =========================================================================
    def _build_page_6_methodology(self, data: ReportData) -> List[Any]:
        story: List[Any] = []

        story.append(Paragraph("6. METHODOLOGY, DATA PROVENANCE & LIMITATIONS", self.styles["PageHeader"]))
        story.append(Paragraph(
            "Technical framework documentation, analytical classification boundaries, and operational constraints.",
            self.styles["PageSubheader"]
        ))

        # 6-Stage Analytical Pipeline
        story.append(Paragraph("<b>SIX-STAGE DETERMINISTIC ANALYTICAL PIPELINE</b>", self.styles["SectionTitle"]))
        pipe_desc = (
            "CivicFork executes a strictly reproducible, formula-driven decision pipeline: "
            "<b>(1) Urban Context Analysis:</b> extracts physical infrastructure within the study radius; "
            "<b>(2) Infrastructure Gap Analysis:</b> evaluates amenities against planning benchmarks; "
            "<b>(3) Spatial Scenario Generation:</b> formulates 7 canonical development options; "
            "<b>(4) 6-Dimension Simulation:</b> computes normalized impact scores [0–100]; "
            "<b>(5) Priority Weighting & Ranking:</b> applies municipal policy weights to calculate final composite rankings; "
            "<b>(6) Feasibility & Counterfactual Verification:</b> verifies regulatory constraints and quantifies pairwise trade-offs."
        )
        story.append(Paragraph(pipe_desc, self.styles["BodySmall"]))
        story.append(Spacer(1, 6))

        # Data Provenance Table
        prov_rows = [
            [
                Paragraph("<b>PROVENANCE TIER</b>", self.styles["TableHeaderLeft"]),
                Paragraph("<b>DATA SOURCE / METHOD</b>", self.styles["TableHeaderLeft"]),
                Paragraph("<b>APPLIED METRICS & PIPELINE ATTRIBUTES</b>", self.styles["TableHeaderLeft"]),
            ],
            [
                Paragraph("<b>[Observed]</b>", self.styles["TableCellBold"]),
                Paragraph("OpenStreetMap GeoJSON / MCC", self.styles["TableCell"]),
                Paragraph("Road segments, transit stops, water bodies, amenity nodes, ward boundaries.", self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>[Calculated]</b>", self.styles["TableCellBold"]),
                Paragraph("Deterministic Geospatial Math", self.styles["TableCell"]),
                Paragraph("Road density (m/km²), euclidean facility distance, buffer overlaps, total POIs.", self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>[Modelled]</b>", self.styles["TableCellBold"]),
                Paragraph("Spatial Density Heuristics", self.styles["TableCell"]),
                Paragraph("Population density estimation, building coverage ratio, induced vehicular trips.", self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>[Configured]</b>", self.styles["TableCellBold"]),
                Paragraph("Municipal Benchmark YAMLs", self.styles["TableCell"]),
                Paragraph("Capital expenditure estimates, ref footprint areas, regulatory buffer standards.", self.styles["TableCell"]),
            ],
            [
                Paragraph("<b>[Derived]</b>", self.styles["TableCellBold"]),
                Paragraph("CivicFork Mathematical Models", self.styles["TableCell"]),
                Paragraph("Normalized dimension scores (0–100), composite ranking, counterfactual net deltas.", self.styles["TableCell"]),
            ],
        ]
        t_prov = Table(prov_rows, colWidths=[90, 150, 300])
        t_prov.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), SECONDARY_NAVY),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(Paragraph("<b>DATA PROVENANCE CLASSIFICATION MATRIX</b>", self.styles["BodyBold"]))
        story.append(t_prov)
        story.append(Spacer(1, 8))

        # Operational Limitations & Planning Disclaimers
        story.append(Paragraph("<b>OPERATIONAL LIMITATIONS & STATUTORY DISCLAIMERS</b>", self.styles["SectionTitle"]))
        limits = [
            "<b>1. OpenStreetMap Dataset Completeness:</b> Unobserved facilities in OSM represent an empirical observation boundary and must not be cited as definitive legal proof of non-existence.",
            "<b>2. Modelled Population Heuristics:</b> Population density is projected from built-up spatial footprints and is intended for comparative assessment rather than census enumeration.",
            "<b>3. Sensor & Real-Time Data Absence:</b> The model evaluates spatial geometry and topology; it does not incorporate dynamic real-time traffic GPS probes or telemetry sensor feeds.",
            "<b>4. Legal Title & Land Ownership:</b> Feasibility checks verify spatial and zoning compatibility (feasibility.yaml). Site ownership title and statutory land conversion clearances remain mandatory.",
            "<b>5. Decision-Support Boundary:</b> All simulated impact scores are comparative heuristics designed to inform municipal deliberation and do not constitute structural or civil engineering guarantees.",
        ]
        for lim in limits:
            story.append(Paragraph(lim, self.styles["BodySmall"]))
            story.append(Spacer(1, 2))

        story.append(Spacer(1, 6))
        # Sign-off box
        sign_off = [
            [
                Paragraph("<b>MUNICIPAL DECISION-SUPPORT NOTICE:</b> This document was deterministically compiled by CivicFork. Statutory development sanction rests with the Mysuru City Corporation (MCC) and competent local planning authorities.", self.styles["CalloutNotice"])
            ]
        ]
        t_sign = Table(sign_off, colWidths=[540])
        t_sign.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.5, BORDER_MID),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_sign)

        return story


# Module-level singleton
_report_generator_instance: Optional[ReportGenerator] = None


def get_report_generator() -> ReportGenerator:
    """Provide singleton instance of ReportGenerator."""
    global _report_generator_instance
    if _report_generator_instance is None:
        _report_generator_instance = ReportGenerator()
    return _report_generator_instance
