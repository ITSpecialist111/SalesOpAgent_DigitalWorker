# Copyright (c) Microsoft. All rights reserved.

"""
Report Generator Service.
Generates stunning reports for Teams (Adaptive Cards) and Email (HTML).
"""

import json
import os
from html import escape
from typing import Dict, Any, List

class ReportGenerator:
    """
    Generates formatted reports from meeting intelligence.
    """

    def __init__(self):
        self.template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")

    def _coerce_text(self, value: Any, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value)

    def _format_summary_text(self, value: Any) -> str:
        if value is None:
            return "No summary available."

        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or "No summary available."

        if isinstance(value, dict):
            key_agreements = value.get("key_agreements")
            if isinstance(key_agreements, list):
                agreements = [self._coerce_text(item, "").strip() for item in key_agreements]
                agreements = [item for item in agreements if item]
                if agreements:
                    return " ".join(agreements)

            parts: List[str] = []
            for key, item in value.items():
                item_text = self._coerce_text(item, "").strip()
                if not item_text:
                    continue
                if key == "key_agreements":
                    continue
                parts.append(item_text)
            if parts:
                return " ".join(parts)

        if isinstance(value, list):
            items = [self._coerce_text(item, "").strip() for item in value]
            items = [item for item in items if item]
            if items:
                return " ".join(items)

        return self._coerce_text(value, "No summary available.")
        
    def generate_adaptive_card(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a Teams Adaptive Card.
        """
        template_path = os.path.join(self.template_dir, "report_card.json")
        with open(template_path, "r", encoding="utf-8") as f:
            template_str = f.read()

        # Data Preparation — ensure all values are strings (never None)
        meeting_subject = self._coerce_text(
            context.get("subject"), "Unknown Meeting"
        )
        summary = self._coerce_text(
            context.get("summary"), "No summary available."
        )
        meeting_id = self._coerce_text(context.get("meeting_id"), "")
        crm_link = self._coerce_text(
            context.get("crm_link"), "https://dynamics.microsoft.com"
        )

        # Format Tasks for FactSet
        tasks = context.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = [tasks]
        tasks_facts = [
            {"title": str(i+1), "value": self._coerce_text(t, "")}
            for i, t in enumerate(tasks)
        ]
        
        # Format CRM Updates for FactSet
        crm_updates = context.get("crm_updates", {})
        if isinstance(crm_updates, dict):
            crm_facts = [
                {"title": self._coerce_text(k, ""), "value": self._coerce_text(v, "")}
                for k, v in crm_updates.items()
            ]
        else:
            crm_facts = [
                {"title": "update", "value": self._coerce_text(crm_updates, "")}
            ]

        # Simple string replacement (In production, use Jinja2 or Adaptive Cards Templating SDK)
        # Note: We are replacing the *whole* list placeholder, which is tricky with simple replace.
        # For simplicity in this agent, we will inject the JSON dumps.
        
        # Doing a manual JSON construction for the dynamic parts to be safer
        card_data = json.loads(template_str)
        
        # Hydrate Body
        # Subject
        card_data["body"][0]["items"][0]["columns"][1]["items"][1]["text"] = meeting_subject
        # Summary
        card_data["body"][1]["items"][1]["text"] = summary
        # Tasks
        card_data["body"][2]["items"][1]["facts"] = tasks_facts
        # CRM Updates
        card_data["body"][3]["items"][1]["facts"] = crm_facts
        
        # Create Actions
        card_data["actions"][0]["url"] = crm_link
        card_data["actions"][1]["data"]["meeting_id"] = meeting_id

        return card_data

    def generate_email_html(self, context: Dict[str, Any]) -> str:
        """
        Generate an HTML Email body.
        """
        template_path = os.path.join(self.template_dir, "report_email.html")
        with open(template_path, "r", encoding="utf-8") as f:
            template_str = f.read()

        # Data Preparation — ensure all values are strings (never None)
        meeting_subject = self._coerce_text(
            context.get("subject"), "Unknown Meeting"
        )
        summary = self._format_summary_text(
            context.get("executive_summary") or context.get("summary")
        )
        crm_link = self._coerce_text(context.get("crm_link"), "#")

        sentiment_label = self._coerce_text(context.get("sentiment") or "unknown").strip() or "unknown"
        sentiment_timeline = context.get("sentiment_timeline")
        if not isinstance(sentiment_timeline, list):
            sentiment_timeline = [sentiment_timeline] if sentiment_timeline else []
        sentiment_timeline = [self._coerce_text(item, "").strip() for item in sentiment_timeline if self._coerce_text(item, "").strip()]

        churn_risk = context.get("churn_risk") or {}
        if isinstance(churn_risk, dict):
            churn_level = self._coerce_text(churn_risk.get("level") or "unknown")
            churn_reason = self._coerce_text(churn_risk.get("reason") or "Not provided")
        else:
            churn_level = self._coerce_text(churn_risk or "unknown")
            churn_reason = "Not provided"

        customer_satisfaction = context.get("customer_satisfaction") or {}
        if isinstance(customer_satisfaction, dict):
            csat_score = self._coerce_text(customer_satisfaction.get("score") or "N/A")
            csat_reason = self._coerce_text(customer_satisfaction.get("reason") or "Not provided")
        else:
            csat_score = self._coerce_text(customer_satisfaction or "N/A")
            csat_reason = "Not provided"

        sentiment_html = (
            f'<div style="margin-bottom:8px;"><strong>Overall Sentiment:</strong> {escape(sentiment_label)}</div>'
            f'<div style="margin-bottom:8px;"><strong>Churn Risk:</strong> {escape(churn_level)} ({escape(churn_reason)})</div>'
            f'<div style="margin-bottom:8px;"><strong>Customer Satisfaction:</strong> {escape(csat_score)} ({escape(csat_reason)})</div>'
        )
        if sentiment_timeline:
            timeline_html = "".join([f"<li>{escape(item)}</li>" for item in sentiment_timeline[:5]])
            sentiment_html += (
                '<div style="margin-top:8px;"><strong>Sentiment Timeline:</strong>'
                f'<ul style="margin:8px 0 0 18px; padding:0; color:#323130;">{timeline_html}</ul></div>'
            )

        expansion = context.get("expansion_likelihood") or {}
        if isinstance(expansion, dict):
            expansion_level = self._coerce_text(expansion.get("level") or "unknown")
            expansion_score = self._coerce_text(expansion.get("score") or "N/A")
            expansion_reason = self._coerce_text(expansion.get("reason") or "Not provided")
            products = expansion.get("products")
            if not isinstance(products, list):
                products = [products] if products else []
            products = [self._coerce_text(item, "").strip() for item in products if self._coerce_text(item, "").strip()]
        else:
            expansion_level = self._coerce_text(expansion or "unknown")
            expansion_score = "N/A"
            expansion_reason = "Not provided"
            products = []

        products_html = ""
        if products:
            products_html = (
                '<div style="margin-top:8px;"><strong>Potential Product Fit:</strong> '
                + escape(", ".join(products))
                + "</div>"
            )

        expansion_html = (
            f'<div style="margin-bottom:8px;"><strong>Likelihood to Purchase Additional Products:</strong> {escape(expansion_level)}</div>'
            f'<div style="margin-bottom:8px;"><strong>Expansion Score:</strong> {escape(expansion_score)}</div>'
            f'<div style="margin-bottom:8px;"><strong>Rationale:</strong> {escape(expansion_reason)}</div>'
            f"{products_html}"
        )

        # Format Tasks HTML
        tasks = context.get("tasks", []) or []
        if not isinstance(tasks, list):
            tasks = [tasks]
        tasks_html = "".join(
            [
                f'<li class="task-item" style="background-color:#faf9f8;color:#323130;">{escape(self._coerce_text(t, ""))}</li>'
                for t in tasks
            ]
        )

        # Format CRM HTML
        crm_updates = context.get("crm_updates", {}) or {}
        if isinstance(crm_updates, dict):
            crm_html = "".join([
                f'<div class="crm-field" style="color:#323130;"><span class="crm-label" style="color:#005a9e;">{escape(self._coerce_text(k, ""))}:</span><span style="color:#323130;">{escape(self._coerce_text(v, ""))}</span></div>'
                for k, v in crm_updates.items()
            ])
        else:
            crm_html = (
                f'<div class="crm-field" style="color:#323130;"><span style="color:#323130;">{escape(self._coerce_text(crm_updates, ""))}</span></div>'
            )

        # Replace
        html = template_str.replace("${meeting_subject}", meeting_subject)
        html = html.replace("${summary}", escape(summary))
        html = html.replace("${sentiment_html}", sentiment_html)
        html = html.replace("${expansion_html}", expansion_html)
        html = html.replace("${tasks_html}", tasks_html)
        html = html.replace("${crm_updates_html}", crm_html)
        html = html.replace("${crm_link}", crm_link)
        
        return html
