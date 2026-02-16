# Copyright (c) Microsoft. All rights reserved.

"""
Graph API Client for fetching meeting transcripts.
"""

import logging
import os
import re
from typing import Optional
from urllib.parse import quote, unquote

from azure.identity import DefaultAzureCredential
from azure.core.credentials import TokenCredential
import httpx

logger = logging.getLogger(__name__)


class GraphTranscriptClient:
    """
    Client for interacting with Microsoft Graph API to fetch meeting transcripts
    and calendar data. Uses application-level credentials (client credentials flow)
    so all requests use /users/{userId} rather than /me.
    """

    # The agent user whose calendar/mailbox we access
    AGENT_USER_ID = os.getenv(
        "AGENT_USER_ID", "ec35260f-ceb9-40b1-9e8b-afafe29187cf"
    )

    def __init__(self, credential: Optional[TokenCredential] = None):
        """Initialize the Graph client."""
        self.credential = credential or DefaultAzureCredential()
        self.base_url = "https://graph.microsoft.com/v1.0"
        self._token = None

    async def _get_token(self) -> str:
        """Get a valid access token, refreshing if expired."""
        if not self._token:
            token_obj = self.credential.get_token("https://graph.microsoft.com/.default")
            self._token = token_obj.token
            self._token_expires = token_obj.expires_on
        else:
            import time
            # Refresh if within 5 minutes of expiry
            if time.time() > (self._token_expires - 300):
                token_obj = self.credential.get_token("https://graph.microsoft.com/.default")
                self._token = token_obj.token
                self._token_expires = token_obj.expires_on
        return self._token

    async def get_transcript_content(
        self, meeting_id: str, transcript_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Fetch the content of a meeting transcript.
        
        Args:
            meeting_id: The ID of the online meeting.
            transcript_id: Optional ID of the specific transcript. If not provided,
                           fetches the first available transcript.
                           
        Returns:
            The transcript content as a string (VTT or text), or None if not found.
        """
        try:
            token = await self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=30) as client:
                online_meeting_id = meeting_id

                resolved_id = None
                if meeting_id and meeting_id.startswith("AAMk"):
                    resolved_id = await self._resolve_online_meeting_id_from_event_id(
                        client, headers, meeting_id
                    )
                    if resolved_id and resolved_id != meeting_id:
                        logger.info(
                            "Resolved calendar event %s to onlineMeeting %s",
                            meeting_id,
                            resolved_id,
                        )
                        online_meeting_id = resolved_id
                    else:
                        logger.warning(
                            "Could not resolve calendar event %s to an onlineMeeting id",
                            meeting_id,
                        )

                transcripts = []
                try:
                    if meeting_id.startswith("AAMk") and online_meeting_id == meeting_id:
                        return None
                    transcripts = await self._list_transcripts(
                        client, headers, online_meeting_id
                    )
                except httpx.HTTPStatusError as ex:
                    status_code = ex.response.status_code if ex.response else None
                    if status_code in (400, 403, 404) and online_meeting_id == meeting_id:
                        resolved_id = await self._resolve_online_meeting_id_from_event_id(
                            client, headers, meeting_id
                        )
                        if resolved_id and resolved_id != meeting_id:
                            logger.info(
                                "Resolved calendar event %s to onlineMeeting %s after %s from transcripts endpoint",
                                meeting_id,
                                resolved_id,
                                status_code,
                            )
                            online_meeting_id = resolved_id
                            transcripts = await self._list_transcripts(
                                client, headers, online_meeting_id
                            )
                        else:
                            raise
                    else:
                        raise

                if not transcripts:
                    logger.warning(
                        "No transcripts found for meeting/event id: %s", meeting_id
                    )
                    return None

                target_transcript = None
                if transcript_id:
                    target_transcript = next(
                        (t for t in transcripts if t.get("id") == transcript_id),
                        None,
                    )
                    if not target_transcript:
                        logger.warning(
                            "Requested transcript id %s not found; falling back to first available",
                            transcript_id,
                        )

                if not target_transcript:
                    target_transcript = transcripts[0]

                target_transcript_id = target_transcript.get("id")
                if not target_transcript_id:
                    logger.warning("Transcript object has no id: %s", target_transcript)
                    return None

                encoded_online_meeting_id = self._encode_path_segment(online_meeting_id)
                encoded_transcript_id = self._encode_path_segment(target_transcript_id)

                content_url = (
                    f"{self.base_url}/users/{self.AGENT_USER_ID}"
                    f"/onlineMeetings/{encoded_online_meeting_id}"
                    f"/transcripts/{encoded_transcript_id}/content"
                )

                try:
                    content_resp = await client.get(
                        content_url,
                        headers={"Authorization": f"Bearer {token}"},
                        params={"$format": "text/vtt"},
                    )
                    content_resp.raise_for_status()
                except httpx.HTTPStatusError as ex:
                    status_code = ex.response.status_code if ex.response else None
                    if status_code == 400:
                        logger.info(
                            "Transcript content request with $format failed (400): %s. Retrying without $format.",
                            self._extract_graph_error_message(ex.response),
                        )
                        content_resp = await client.get(
                            content_url,
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        content_resp.raise_for_status()
                    else:
                        raise

                content_type = (content_resp.headers.get("content-type") or "").lower()

                if "application/json" in content_type:
                    payload = content_resp.json()
                    if isinstance(payload, dict):
                        if payload.get("transcriptContent"):
                            return str(payload.get("transcriptContent"))
                        if payload.get("content"):
                            return str(payload.get("content"))
                        if payload.get("value"):
                            return str(payload.get("value"))
                    return str(payload)

                return content_resp.text

        except Exception as e:
            logger.error("Failed to fetch transcript: %s", e)
            return None

    async def _list_transcripts(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        online_meeting_id: str,
    ) -> list[dict]:
        """List transcripts for a given online meeting id."""
        if not online_meeting_id:
            return []

        encoded_online_meeting_id = self._encode_path_segment(online_meeting_id)

        list_url = (
            f"{self.base_url}/users/{self.AGENT_USER_ID}"
            f"/onlineMeetings/{encoded_online_meeting_id}/transcripts"
        )
        resp = await client.get(list_url, headers=headers)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        return data.get("value", []) if isinstance(data, dict) else []

    async def _resolve_online_meeting_id_from_event_id(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        event_id: str,
    ) -> Optional[str]:
        """Resolve a calendar event id into an onlineMeeting id using join URL lookup."""
        if not event_id:
            return None

        event_url = (
            f"{self.base_url}/users/{self.AGENT_USER_ID}/events/{event_id}"
            "?$select=id,subject,isOnlineMeeting,onlineMeetingProvider,onlineMeeting,onlineMeetingUrl"
        )
        event_resp = await client.get(event_url, headers=headers)
        if event_resp.status_code == 404:
            return None
        event_resp.raise_for_status()
        event_data = event_resp.json() if event_resp.content else {}

        online_meeting = event_data.get("onlineMeeting") or {}
        online_meeting_id = online_meeting.get("id")
        if online_meeting_id:
            return online_meeting_id

        join_url = online_meeting.get("joinUrl") or event_data.get("onlineMeetingUrl")
        if not join_url:
            return None
        conference_id = online_meeting.get("conferenceId")

        query_url = f"{self.base_url}/users/{self.AGENT_USER_ID}/onlineMeetings"
        matches: list[dict] = []

        join_meeting_id = self._extract_join_meeting_id(join_url)
        if join_meeting_id:
            join_meeting_id_filter_value = join_meeting_id.replace("'", "''")
            join_meeting_params = {
                "$filter": f"joinMeetingIdSettings/joinMeetingId eq '{join_meeting_id_filter_value}'",
            }
            try:
                join_meeting_resp = await client.get(
                    query_url, headers=headers, params=join_meeting_params
                )
                if join_meeting_resp.status_code != 404:
                    join_meeting_resp.raise_for_status()
                    join_meeting_data = (
                        join_meeting_resp.json() if join_meeting_resp.content else {}
                    )
                    matches = (
                        join_meeting_data.get("value", [])
                        if isinstance(join_meeting_data, dict)
                        else []
                    )
                    if matches:
                        return matches[0].get("id")
            except httpx.HTTPStatusError as ex:
                status_code = ex.response.status_code if ex.response else None
                if status_code not in (400,):
                    raise
                logger.info(
                    "joinMeetingId lookup failed with %s: %s",
                    status_code,
                    self._extract_graph_error_message(ex.response),
                )

        if conference_id:
            conference_id_filter_value = str(conference_id).replace("'", "''")
            conference_params = {
                "$filter": f"VideoTeleconferenceId eq '{conference_id_filter_value}'",
            }
            try:
                conference_resp = await client.get(
                    f"{self.base_url}/communications/onlineMeetings",
                    headers=headers,
                    params=conference_params,
                )
                if conference_resp.status_code != 404:
                    conference_resp.raise_for_status()
                    conference_data = (
                        conference_resp.json() if conference_resp.content else {}
                    )
                    conference_matches = (
                        conference_data.get("value", [])
                        if isinstance(conference_data, dict)
                        else []
                    )
                    if conference_matches:
                        return conference_matches[0].get("id")
            except httpx.HTTPStatusError as ex:
                status_code = ex.response.status_code if ex.response else None
                if status_code not in (400,):
                    raise
                logger.info(
                    "VideoTeleconferenceId lookup failed with %s: %s",
                    status_code,
                    self._extract_graph_error_message(ex.response),
                )

        join_url_variants = [join_url]
        decoded_once = unquote(join_url)
        if decoded_once and decoded_once not in join_url_variants:
            join_url_variants.append(decoded_once)
        decoded_twice = unquote(decoded_once)
        if decoded_twice and decoded_twice not in join_url_variants:
            join_url_variants.append(decoded_twice)

        for candidate_join_url in join_url_variants:
            filter_value = candidate_join_url.replace("'", "''")
            query_params = {
                "$filter": f"JoinWebUrl eq '{filter_value}'",
            }
            try:
                query_resp = await client.get(
                    query_url, headers=headers, params=query_params
                )
                if query_resp.status_code == 404:
                    continue
                query_resp.raise_for_status()
                query_data = query_resp.json() if query_resp.content else {}
                matches = (
                    query_data.get("value", []) if isinstance(query_data, dict) else []
                )
                if matches:
                    break
            except httpx.HTTPStatusError as ex:
                status_code = ex.response.status_code if ex.response else None
                if status_code in (400,):
                    logger.info(
                        "JoinWebUrl lookup variant failed with %s (%s); trying next variant",
                        status_code,
                        self._extract_graph_error_message(ex.response),
                    )
                    continue
                raise

        if not matches:
            return None

        return matches[0].get("id")

    def _extract_join_meeting_id(self, join_url: str) -> str:
        if not join_url:
            return ""
        decoded = unquote(join_url)
        match = re.search(r"/meetup-join/([^/]+)/", decoded, flags=re.IGNORECASE)
        if not match:
            return ""
        return match.group(1)

    def _normalize_join_url(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        lowered = text.lower().rstrip("/")
        try:
            lowered = unquote(lowered)
        except Exception:
            pass
        return lowered

    def _encode_path_segment(self, value: str) -> str:
        return quote((value or "").strip(), safe="")

    def _extract_graph_error_message(self, response: Optional[httpx.Response]) -> str:
        if response is None:
            return "no response"
        try:
            payload = response.json()
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    message = error.get("message")
                    if message:
                        return str(message)
            return str(payload)
        except Exception:
            text = (response.text or "").strip()
            return text[:300] if text else "no error body"

    # ------------------------------------------------------------------
    # Calendar helpers (used by CalendarHandler)
    # ------------------------------------------------------------------

    async def get_calendar_view(
        self, start: "datetime", end: "datetime"
    ) -> list[dict]:
        """
        Return calendar events between *start* and *end* for the agent user
        using the /me/calendarView endpoint.
        """
        from datetime import datetime  # ensure import available

        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Prefer": 'outlook.timezone="UTC"',
        }
        params = {
            "startDateTime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "$select": "id,subject,start,end,responseStatus,organizer,onlineMeeting",
            "$orderby": "start/dateTime",
            "$top": "25",
        }
        url = f"{self.base_url}/users/{self.AGENT_USER_ID}/calendarView"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            events = data.get("value", [])
            logger.info("calendarView returned %d event(s) for %s..%s", len(events),
                        params["startDateTime"], params["endDateTime"])
            return events

    async def get_pending_invitations(self) -> list[dict]:
        """
        Return calendar events where the agent has NOT yet responded
        (responseStatus.response == 'notResponded' or 'tentativelyAccepted').
        Looks ahead 7 days so we catch invitations early.
        """
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        future = now + timedelta(days=7)

        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Prefer": 'outlook.timezone="UTC"',
        }
        params = {
            "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endDateTime": future.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "$select": "id,subject,start,end,responseStatus",
            "$top": "50",
        }
        url = f"{self.base_url}/users/{self.AGENT_USER_ID}/calendarView"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            events = resp.json().get("value", [])

        # Filter to those not yet accepted
        pending = [
            e for e in events
            if (e.get("responseStatus") or {}).get("response", "")
            in ("notResponded", "tentativelyAccepted", "none")
        ]
        if pending:
            logger.info("%d pending invitation(s) found", len(pending))
        return pending

    async def accept_event(self, event_id: str, comment: str = "") -> None:
        """
        Accept a calendar event invitation via POST /me/events/{id}/accept.
        """
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {"sendResponse": True, "comment": comment or "Accepted by SalesOpsAgent."}
        url = f"{self.base_url}/users/{self.AGENT_USER_ID}/events/{event_id}/accept"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            logger.info("Accepted event %s", event_id)

    # ------------------------------------------------------------------
    # Email sending
    # ------------------------------------------------------------------

    async def send_email(
        self,
        to_recipients: list[str],
        subject: str,
        html_body: str,
        plain_body: str = "",
        cc_recipients: list[str] | None = None,
        save_to_sent: bool = True,
    ) -> bool:
        """
        Send an email via the Graph API on behalf of the agent user.

        Uses POST /users/{userId}/sendMail which requires
        Mail.Send application permission.

        Args:
            to_recipients: List of email addresses to send to.
            subject: Email subject line.
            html_body: HTML content of the email body.
            plain_body: Optional plain-text fallback (unused by Graph but kept for reference).
            cc_recipients: Optional list of CC email addresses.
            save_to_sent: Whether to save a copy in Sent Items.

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            token = await self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            # Build recipient list
            to_list = [
                {"emailAddress": {"address": addr}} for addr in to_recipients
            ]
            cc_list = []
            if cc_recipients:
                cc_list = [
                    {"emailAddress": {"address": addr}} for addr in cc_recipients
                ]

            payload = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": html_body,
                    },
                    "toRecipients": to_list,
                },
                "saveToSentItems": save_to_sent,
            }
            if cc_list:
                payload["message"]["ccRecipients"] = cc_list

            url = f"{self.base_url}/users/{self.AGENT_USER_ID}/sendMail"

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()

            logger.info(
                "📧 Email sent to %s (subject: %s)", to_recipients, subject
            )
            return True

        except Exception as e:
            logger.error("Failed to send email: %s", e)
            return False

    # ------------------------------------------------------------------
    # Teams chat messaging
    # ------------------------------------------------------------------

    async def resolve_chat_thread_id(self, meeting_id: str) -> Optional[str]:
        """
        Resolve a meeting ID to its associated Teams chat thread ID.

        Uses GET /users/{userId}/onlineMeetings/{meetingId} to read
        chatInfo.threadId.  Requires OnlineMeetings.Read[.All] permission.

        Returns:
            The chat thread ID string, or None if resolution fails.
        """
        try:
            token = await self._get_token()
            headers = {"Authorization": f"Bearer {token}"}
            encoded_meeting_id = self._encode_path_segment(meeting_id)
            url = (
                f"{self.base_url}/users/{self.AGENT_USER_ID}"
                f"/onlineMeetings/{encoded_meeting_id}"
            )

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            thread_id = (data.get("chatInfo") or {}).get("threadId")
            if thread_id:
                logger.info(
                    "Resolved meeting %s -> thread %s", meeting_id, thread_id
                )
            else:
                logger.warning(
                    "Meeting %s has no chatInfo.threadId", meeting_id
                )
            return thread_id

        except Exception as e:
            logger.error("Failed to resolve chat thread: %s", e)
            return None

    async def post_chat_message(
        self, chat_thread_id: str, content: str, content_type: str = "html"
    ) -> bool:
        """
        Post a message to a Teams chat thread.

        Uses POST /chats/{threadId}/messages which requires
        Chat.ReadWrite (delegated) or ChatMessage.Send (application) permission.

        Args:
            chat_thread_id: The Teams chat thread ID (e.g. 19:meeting_xxx@thread.v2).
            content: The message body (HTML or text).
            content_type: "html" or "text".

        Returns:
            True if sent successfully, False otherwise.
        """
        try:
            token = await self._get_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            payload = {
                "body": {
                    "contentType": content_type,
                    "content": content,
                }
            }

            url = f"{self.base_url}/chats/{chat_thread_id}/messages"

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()

            logger.info("💬 Chat message posted to thread %s", chat_thread_id)
            return True

        except Exception as e:
            logger.error("Failed to post chat message: %s", e)
            return False

    async def send_meeting_chat_message(
        self, meeting_id: str, content: str, content_type: str = "html"
    ) -> bool:
        """
        Convenience method: resolve a meeting ID to its chat thread
        and post a message in one call.

        Returns:
            True if sent successfully, False otherwise.
        """
        thread_id = await self.resolve_chat_thread_id(meeting_id)
        if not thread_id:
            logger.warning(
                "Cannot send chat message — failed to resolve thread for meeting %s",
                meeting_id,
            )
            return False
        return await self.post_chat_message(thread_id, content, content_type)
