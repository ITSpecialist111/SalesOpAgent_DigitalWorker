"""Composes HTML summary emails from MeetingIntelligence data."""

from __future__ import annotations

from src.extraction.schemas import MeetingIntelligence


class EmailComposer:
    """Builds HTML email bodies for meeting summary notifications."""

    def compose(self, intel: MeetingIntelligence) -> str:
        """Build an HTML email summarizing the meeting intelligence."""
        sentiment_color = {
            "positive": "#28a745",
            "neutral": "#6c757d",
            "negative": "#dc3545",
        }.get(intel.sentiment.value, "#6c757d")

        action_items_html = self._render_action_items(intel)
        objections_html = self._render_objections(intel)
        competitors_html = self._render_competitors(intel)
        deal_html = self._render_deal_info(intel)

        return f"""\
<div style="font-family: Segoe UI, Arial, sans-serif; max-width: 700px; margin: 0 auto;">
  <h2 style="color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 8px;">
    Meeting Summary: {_escape(intel.meeting_subject or "Untitled Meeting")}
  </h2>

  <div style="background: #f8f9fa; padding: 16px; border-radius: 8px; margin-bottom: 16px;">
    <p style="margin: 0 0 8px 0;"><strong>Sentiment:</strong>
      <span style="color: {sentiment_color}; font-weight: bold;">
        {intel.sentiment.value.upper()}
      </span>
      <span style="color: #999;"> (confidence: {intel.sentiment_confidence:.0%})</span>
    </p>
    {deal_html}
    <p style="margin: 0;"><strong>Participants:</strong> {_escape(", ".join(intel.participants) or "N/A")}</p>
  </div>

  <h3 style="color: #333;">Executive Summary</h3>
  <p>{_escape(intel.executive_summary or "No summary available.")}</p>

  {action_items_html}
  {objections_html}
  {competitors_html}

  <hr style="border: none; border-top: 1px solid #ddd; margin: 24px 0;" />
  <p style="color: #999; font-size: 12px;">
    This summary was generated automatically by SalesOpsBot.
    {self._salesforce_note(intel)}
  </p>
</div>"""

    def compose_plain_text(self, intel: MeetingIntelligence) -> str:
        """Build a plain-text version of the summary."""
        lines = [
            f"Meeting Summary: {intel.meeting_subject or 'Untitled Meeting'}",
            f"Sentiment: {intel.sentiment.value.upper()} ({intel.sentiment_confidence:.0%})",
            "",
            "EXECUTIVE SUMMARY",
            intel.executive_summary or "No summary available.",
            "",
            "ACTION ITEMS",
            intel.format_next_steps(),
        ]

        if intel.objections:
            lines.append("")
            lines.append("OBJECTIONS RAISED")
            for obj in intel.objections:
                lines.append(f"- {obj.topic}: {obj.details}")

        if intel.competitors_mentioned:
            lines.append("")
            lines.append(f"COMPETITORS MENTIONED: {', '.join(intel.competitors_mentioned)}")

        lines.append("")
        lines.append("---")
        lines.append("Generated automatically by SalesOpsBot.")
        return "\n".join(lines)

    @staticmethod
    def _render_action_items(intel: MeetingIntelligence) -> str:
        if not intel.next_steps:
            return ""
        items = ""
        for item in intel.next_steps:
            owner = f" — <em>{_escape(item.owner)}</em>" if item.owner else ""
            due = f" <span style='color:#999;'>[Due: {_escape(item.due_date)}]</span>" if item.due_date else ""
            items += f"<li>{_escape(item.description)}{owner}{due}</li>\n"
        return f"<h3 style='color: #333;'>Action Items</h3>\n<ul>{items}</ul>"

    @staticmethod
    def _render_objections(intel: MeetingIntelligence) -> str:
        if not intel.objections:
            return ""
        items = ""
        for obj in intel.objections:
            items += f"<li><strong>{_escape(obj.topic)}</strong>: {_escape(obj.details)}</li>\n"
        return f"<h3 style='color: #333;'>Objections Raised</h3>\n<ul>{items}</ul>"

    @staticmethod
    def _render_competitors(intel: MeetingIntelligence) -> str:
        if not intel.competitors_mentioned:
            return ""
        names = ", ".join(_escape(c) for c in intel.competitors_mentioned)
        return f"<h3 style='color: #333;'>Competitors Mentioned</h3>\n<p>{names}</p>"

    @staticmethod
    def _render_deal_info(intel: MeetingIntelligence) -> str:
        if intel.deal_size is None and not intel.deal_stage:
            return ""
        parts = []
        if intel.deal_size is not None:
            parts.append(
                f"<strong>Deal Size:</strong> {intel.deal_currency} {intel.deal_size:,.0f}"
            )
        if intel.deal_stage:
            parts.append(f"<strong>Stage:</strong> {_escape(intel.deal_stage)}")
        return "".join(
            f'<p style="margin: 0 0 8px 0;">{p}</p>' for p in parts
        )

    @staticmethod
    def _salesforce_note(intel: MeetingIntelligence) -> str:
        if intel.opportunity_id:
            return f"Salesforce Opportunity {_escape(intel.opportunity_id)} has been updated."
        return ""


def _escape(text: str) -> str:
    """Basic HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
