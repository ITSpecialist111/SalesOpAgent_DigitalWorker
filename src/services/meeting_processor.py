import logging
import json
import os
from typing import Optional, Dict, Any, List

try:
    from integrations.graph_transcript_client import GraphTranscriptClient
    from integrations.ms_learn_client import MsLearnClient
    from services.report_generator import ReportGenerator
    from services.teams_chat_service import TeamsChatService
except ModuleNotFoundError:
    from src.integrations.graph_transcript_client import GraphTranscriptClient
    from src.integrations.ms_learn_client import MsLearnClient
    from src.services.report_generator import ReportGenerator
    from src.services.teams_chat_service import TeamsChatService

from openai import AzureOpenAI

logger = logging.getLogger(__name__)

class MeetingProcessor:
    """
    Process meeting transcripts to generate CRM updates, send email
    summaries, post Teams messages, and enrich with MS Learn references.
    """

    # Email recipients for meeting summaries.
    # In production this would come from meeting organiser / attendees.
    DEFAULT_SUMMARY_RECIPIENTS = os.getenv(
        "MEETING_SUMMARY_RECIPIENTS",
        "meeting-recipient@example.com",
    ).split(",")

    def __init__(self, agent_instance, graph_client: GraphTranscriptClient):
        self.agent = agent_instance  # The calling agent instance (for MCP email fallback)
        self.graph_client = graph_client
        self.report_generator = ReportGenerator()
        self.learn_client = MsLearnClient()
        self.chat_service = TeamsChatService(graph_client)

        # Direct OpenAI client for transcript analysis — avoids recursive
        # tool-calling loops that occur when using agent.run() with tools.
        self._oai_client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
        )
        self._oai_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    async def process_meeting(
        self,
        meeting_id: str,
        subject: str,
        email_recipients: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Main workflow:
        1. Fetch Transcript.
        2. Analyze with Agent/LLM.
        3. Generate Stunning Report (Adaptive Card + HTML).
        4. Enrich with MS Learn documentation references.
        5. Send email summary.
        6. Post summary to meeting Teams chat.
        """
        logger.info(f"Processing meeting: {subject} ({meeting_id})")

        # 1. Fetch Transcript
        transcript = await self.graph_client.get_transcript_content(meeting_id)

        if not transcript or "placeholder" in transcript:
            logger.error(
                "Transcript unavailable for '%s' (%s). Returning explicit failure instead of mock data.",
                subject,
                meeting_id,
            )
            return {
                "error": "Transcript unavailable. Check Microsoft Graph transcript permissions/access for this meeting.",
                "raw_data": {
                    "meeting_id": meeting_id,
                    "subject": subject,
                },
                "email_sent": False,
                "teams_sent": False,
                "learn_references": [],
            }

        # 2. Analyze with LLM
        prompt = f"""
        Analyze the following meeting transcript and identify:
        1. Key Agreements.
        2. Tasks.
        3. Dynamics 365 (Dataverse) Updates (specifically Opportunity Status, Estimated Revenue, Est. Close Date).
        4. Executive summary for leadership.
        5. Sentiment trend across the meeting timeline.
        6. Churn risk level (low/medium/high) with brief rationale.
        7. Customer satisfaction estimate (0-100) with brief rationale.
        8. Recommended account note text suitable for CRM activity history.
        9. Likelihood to purchase additional Microsoft products (expansion likelihood) with score and rationale.

        TRANSCRIPT:
        {transcript}

        Output the result as a structured JSON object with keys:
        - 'summary'
        - 'executive_summary'
        - 'tasks' (list)
        - 'crm_updates' (dict)
        - 'crm_link'
        - 'sentiment' (e.g. positive/neutral/negative)
        - 'sentiment_timeline' (list of short timeline notes)
        - 'churn_risk' (dict with 'level' and 'reason')
        - 'customer_satisfaction' (dict with 'score' and 'reason')
        - 'expansion_likelihood' (dict with 'level', 'score', 'reason', 'products')
        - 'account_note'
        Do not acknowledge, just output the JSON.
        """

        try:
            # Use direct OpenAI completion (no tools) to avoid recursive
            # tool-calling loop through the agent framework.
            response = self._oai_client.chat.completions.create(
                model=self._oai_deployment,
                messages=[
                    {"role": "system", "content": "You are a meeting transcript analyst. Output only valid JSON, no markdown fencing."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=2000,
            )
            analysis_text = response.choices[0].message.content or ""
            
            # Clean up potential markdown
            analysis_text = analysis_text.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON safely
            analysis_data = json.loads(analysis_text)

            # Normalize expected shape for downstream autonomous actions
            if not isinstance(analysis_data.get("tasks"), list):
                raw_tasks = analysis_data.get("tasks")
                analysis_data["tasks"] = [] if raw_tasks in (None, "") else [raw_tasks]

            if not isinstance(analysis_data.get("crm_updates"), dict):
                analysis_data["crm_updates"] = {}

            if not isinstance(analysis_data.get("sentiment_timeline"), list):
                timeline = analysis_data.get("sentiment_timeline")
                analysis_data["sentiment_timeline"] = [] if timeline in (None, "") else [timeline]

            churn_risk = analysis_data.get("churn_risk")
            if not isinstance(churn_risk, dict):
                analysis_data["churn_risk"] = {"level": "unknown", "reason": "Not provided"}
            else:
                analysis_data["churn_risk"].setdefault("level", "unknown")
                analysis_data["churn_risk"].setdefault("reason", "Not provided")

            customer_satisfaction = analysis_data.get("customer_satisfaction")
            if not isinstance(customer_satisfaction, dict):
                analysis_data["customer_satisfaction"] = {"score": "N/A", "reason": "Not provided"}
            else:
                analysis_data["customer_satisfaction"].setdefault("score", "N/A")
                analysis_data["customer_satisfaction"].setdefault("reason", "Not provided")

            expansion_likelihood = analysis_data.get("expansion_likelihood")
            if not isinstance(expansion_likelihood, dict):
                analysis_data["expansion_likelihood"] = {
                    "level": "unknown",
                    "score": "N/A",
                    "reason": "Not provided",
                    "products": [],
                }
            else:
                analysis_data["expansion_likelihood"].setdefault("level", "unknown")
                analysis_data["expansion_likelihood"].setdefault("score", "N/A")
                analysis_data["expansion_likelihood"].setdefault("reason", "Not provided")
                products = analysis_data["expansion_likelihood"].get("products")
                if not isinstance(products, list):
                    analysis_data["expansion_likelihood"]["products"] = [] if products in (None, "") else [products]

            analysis_data.setdefault("executive_summary", analysis_data.get("summary", ""))
            analysis_data.setdefault("sentiment", "unknown")
            analysis_data.setdefault("account_note", "")
            
            # Add metadata
            analysis_data["subject"] = subject
            analysis_data["meeting_id"] = meeting_id
            
        except Exception as e:
            logger.error(f"LLM processing failed: {e}")
            # Fallback data
            analysis_data = {
                "subject": subject,
                "summary": "Failed to analyze meeting.",
                "executive_summary": "Failed to analyze meeting.",
                "tasks": [],
                "crm_updates": {},
                "crm_link": "#",
                "sentiment": "unknown",
                "sentiment_timeline": [],
                "churn_risk": {"level": "unknown", "reason": "LLM analysis failed"},
                "customer_satisfaction": {"score": "N/A", "reason": "LLM analysis failed"},
                "expansion_likelihood": {
                    "level": "unknown",
                    "score": "N/A",
                    "reason": "LLM analysis failed",
                    "products": [],
                },
                "account_note": "",
            }

        # 3. Generate Reports
        logger.info("Analysis complete. Generating reports.")
        email_html = self.report_generator.generate_email_html(analysis_data)
        card_json = self.report_generator.generate_adaptive_card(analysis_data)

        # 4. Enrich with MS Learn references
        learn_refs = await self._fetch_learn_references(analysis_data)
        if learn_refs:
            analysis_data["learn_references"] = learn_refs
            # Append reference links to the email HTML
            email_html = self._append_learn_refs_to_html(email_html, learn_refs)

        # 5. Send email summary
        email_targets = [r.strip() for r in (email_recipients or []) if r and r.strip()]
        if not email_targets:
            email_targets = [r.strip() for r in self.DEFAULT_SUMMARY_RECIPIENTS if r and r.strip()]

        email_sent = await self._send_email_summary(subject, email_html, email_targets)

        # 6. Post summary to meeting Teams chat
        teams_sent = await self._post_teams_summary(meeting_id, subject, email_html)

        return {
            "email_html": email_html,
            "card_json": card_json,
            "raw_data": analysis_data,
            "email_sent": email_sent,
            "email_recipients": email_targets,
            "teams_sent": teams_sent,
            "learn_references": learn_refs,
        }

    # ------------------------------------------------------------------
    # Delivery helpers
    # ------------------------------------------------------------------

    async def _send_email_summary(
        self,
        subject: str,
        email_html: str,
        recipients: Optional[List[str]] = None,
    ) -> bool:
        """Send the meeting summary email.

        Strategy:
        1. Try direct Graph API (requires Mail.Send application permission).
        2. If that fails (403), fall back to the agent's MCP Mail tools
           by asking the LLM to compose and send the email.
        """
        target_recipients = [r.strip() for r in (recipients or []) if r and r.strip()]
        if not target_recipients:
            logger.warning("No valid email recipients resolved for '%s'", subject)
            return False

        recipients_str = ", ".join(target_recipients)
        email_subject = f"Meeting Summary: {subject}"

        # Attempt 1: Direct Graph API
        try:
            sent = await self.graph_client.send_email(
                to_recipients=target_recipients,
                subject=email_subject,
                html_body=email_html,
            )
            if sent:
                logger.info("Email summary sent via Graph API for '%s'", subject)
                return True
        except Exception as e:
            logger.warning("Direct Graph email failed: %s — trying MCP fallback", e)

        # Attempt 2: MCP Mail tools — currently disabled (MailServer removed
        # due to 403 cascade). Keeping the code path for when permissions
        # are granted, but skipping to avoid recursive agent.run() loops.
        logger.warning("MCP email fallback skipped (MailServer not in manifest)")

        return False

    async def _post_teams_summary(
        self, meeting_id: str, subject: str, summary_html: str
    ) -> bool:
        """Post the meeting summary into the meeting's Teams chat."""
        try:
            sent = await self.chat_service.send_summary_message(
                meeting_id, subject, summary_html
            )
            if sent:
                logger.info("Teams summary posted for '%s'", subject)
            return sent
        except Exception as e:
            logger.error("Failed to post Teams summary: %s", e)
            return False

    # ------------------------------------------------------------------
    # MS Learn enrichment
    # ------------------------------------------------------------------

    async def _fetch_learn_references(
        self, analysis_data: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Extract Microsoft product/technology terms from the analysis
        and look up authoritative documentation on Microsoft Learn.
        """
        # Collect search terms from various analysis fields
        terms: list[str] = []

        # CRM updates often mention Dynamics concepts
        crm = analysis_data.get("crm_updates", {})
        if crm:
            terms.append("Dynamics 365 Sales opportunity management")

        # Tasks may reference products/tools
        for task in analysis_data.get("tasks", []):
            task_text = task if isinstance(task, str) else str(task)
            for keyword in ("Copilot", "Teams", "Dynamics", "Dataverse",
                            "SharePoint", "Power BI", "Azure", "Planner"):
                if keyword.lower() in task_text.lower():
                    terms.append(f"Microsoft {keyword}")
                    break

        # Summary text keywords
        summary = analysis_data.get("summary", "")
        if isinstance(summary, str):
            summary_text = summary
        elif isinstance(summary, (dict, list)):
            try:
                summary_text = json.dumps(summary, ensure_ascii=False)
            except Exception:
                summary_text = str(summary)
        else:
            summary_text = str(summary or "")

        for keyword in ("Copilot", "Teams", "Dynamics 365", "Dataverse",
                        "SharePoint", "Power BI", "Azure", "Planner",
                        "Power Automate", "Power Apps"):
            if keyword.lower() in summary_text.lower() and f"Microsoft {keyword}" not in terms:
                terms.append(f"Microsoft {keyword}")

        if not terms:
            logger.info("No Microsoft product terms found for Learn enrichment")
            return []

        # Deduplicate
        terms = list(dict.fromkeys(terms))
        logger.info("Searching MS Learn for terms: %s", terms)

        return await self.learn_client.search_multiple_terms(terms, top_per_term=1)

    @staticmethod
    def _append_learn_refs_to_html(
        email_html: str, refs: List[Dict[str, str]]
    ) -> str:
        """Append a 'Related Documentation' section to the email HTML."""
        if not refs:
            return email_html

        links = ""
        for ref in refs:
            title = ref.get("title", "")
            url = ref.get("url", "")
            summary = ref.get("summary", "")
            links += (
                f'<li style="margin-bottom: 8px;">'
                f'<a href="{url}" style="color: #0078d4; text-decoration: none;">'
                f"{title}</a>"
            )
            if summary:
                links += f'<br/><span style="color: #666; font-size: 13px;">{summary}</span>'
            links += "</li>\n"

        section = (
            '<h3 style="color: #333;">Related Microsoft Documentation</h3>\n'
            f'<ul style="list-style: none; padding-left: 0;">{links}</ul>'
        )

        # Insert before the closing </div> or append at the end
        if "</div>" in email_html:
            # Insert before the last </div>
            idx = email_html.rfind("</div>")
            email_html = email_html[:idx] + section + email_html[idx:]
        else:
            email_html += section

        return email_html

    def _extract_result(self, result) -> str:
        """Helper to extract text from agent result."""
        if not result:
            return ""
        if hasattr(result, "contents"):
            return str(result.contents)
        elif hasattr(result, "text"):
            return str(result.text)
        elif hasattr(result, "content"):
            return str(result.content)
        else:
            return str(result)
