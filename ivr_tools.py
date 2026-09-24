"""Smart IVR Tool Definitions for Gemini Live API.

These Python tool functions are passed directly into `LiveConnectConfig.tools`
and are called autonomously by Gemini during real-time voice conversations.
"""

import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from google.cloud import bigquery
from config_loader import (
    BQ_BOOKINGS_TABLE,
    GOOGLE_CLOUD_PROJECT as BQ_PROJECT,
    GOOGLE_CLOUD_PROJECT_NUMBER,
    SEARCH_ENGINE_ID,
    SEARCH_LOCATION,
)
from mock_ticketing_backend import ticketing_backend as bms_backend

_bq_client: Optional[bigquery.Client] = None
_BQ_BOOKINGS_CACHE: Dict[str, dict] = {}
_RAG_CACHE: Dict[str, dict] = {}
_search_client: Optional[Any] = None


def _get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=BQ_PROJECT)
    return _bq_client


def _get_search_client():
    """Singleton Discovery Engine SearchServiceClient to avoid per-call gRPC TLS handshake."""
    global _search_client
    if _search_client is None:
        from google.cloud import discoveryengine_v1 as discoveryengine
        _search_client = discoveryengine.SearchServiceClient()
    return _search_client


def _format_bq_row(r: dict) -> dict:
    return {
        "found": True,
        "source": f"BigQuery ({BQ_BOOKINGS_TABLE})",
        "primary_key_mobile": r["mobile_number"],
        "booking_id": r["booking_id"],
        "customer_name": r["customer_name"],
        "movie_title": r["movie_name"],
        "language": r["language"],
        "format": r["format"],
        "cinema_name": r["cinema_name"],
        "screen_audi": r["screen_audi"],
        "showtime": r["show_time"],
        "seat_numbers": r["seat_numbers"],
        "total_tickets": r["total_tickets"],
        "amount_paid": f"₹{r['amount_paid']:.2f}",
        "status": r["booking_status"],
        "cancellation_eligible": r["cancellation_eligible"],
        "payment_method": r["payment_method"],
        "entry_instructions": "Show M-ticket QR code on WhatsApp/SMS at the cinema gate.",
    }


def _seed_bq_cache_sync() -> None:
    """Populate _BQ_BOOKINGS_CACHE synchronously in <1ms from FAKE_INDIAN_BOOKINGS."""
    try:
        from setup_bq_bookings import FAKE_INDIAN_BOOKINGS
        for r in FAKE_INDIAN_BOOKINGS:
            _BQ_BOOKINGS_CACHE[r["mobile_number"]] = _format_bq_row(r)
    except Exception:
        pass


def _prewarm_bq() -> None:
    """Sync live BigQuery rows in background."""
    try:
        client = _get_bq_client()
        rows = list(client.query(f"SELECT * FROM `{BQ_BOOKINGS_TABLE}`"))
        for row in rows:
            r = dict(row)
            _BQ_BOOKINGS_CACHE[r["mobile_number"]] = _format_bq_row(r)
    except Exception as e:
        print(f"[Prewarm BQ Warning]: {e}")


def _prewarm_discovery_engine() -> None:
    """Warm Discovery Engine gRPC TLS channel and pre-cache common FAQ queries in background."""
    try:
        for q in [
            "Transaction was canceled but seats appear blocked",
            "My transaction was canceled but seats appear blocked. Why is that?",
            "What are the loyalty cancellation rules?",
        ]:
            search_knowledge_base(q)
    except Exception as e:
        print(f"[Prewarm DiscoveryEngine Warning]: {e}")


def _normalize_indian_mobile(raw_phone: str) -> str:
    """Normalize spoken or formatted Indian phone numbers into 10-digit mobile string."""
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits[-10:] if len(digits) >= 10 else digits


def fetch_booking_by_mobile(mobile_number: str) -> dict:
    """Fetch customer movie booking details from BigQuery using their 10-digit Indian mobile number (Primary Key).

    Use this tool whenever a caller provides their mobile number (e.g., '9876543210', '9811122233',
    '9900112233', '9820098200', '9711122233', '9123456789', '9988776655', '9654321098')
    to retrieve their movie name, seat numbers, show timing, language, format, cinema name, and booking ID.

    Args:
        mobile_number: The customer's 10-digit Indian mobile number (e.g. '9876543210').

    Returns:
        Dictionary containing complete booking details from the configured BigQuery customer bookings table.
    """
    clean_mobile = _normalize_indian_mobile(mobile_number)
    if not clean_mobile:
        return {
            "found": False,
            "error": "Please provide a valid 10-digit Indian mobile number.",
        }

    # 1. Fast path: Check pre-warmed BigQuery read-through cache (< 2 ms)
    if clean_mobile in _BQ_BOOKINGS_CACHE:
        return _BQ_BOOKINGS_CACHE[clean_mobile]

    # 2. Live BigQuery query on cache miss
    try:
        client = _get_bq_client()
        query = f"""
            SELECT
                mobile_number,
                booking_id,
                customer_name,
                movie_name,
                language,
                format,
                cinema_name,
                screen_audi,
                show_time,
                seat_numbers,
                total_tickets,
                amount_paid,
                booking_status,
                cancellation_eligible,
                payment_method
            FROM `{BQ_BOOKINGS_TABLE}`
            WHERE mobile_number = @mobile
            LIMIT 1
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("mobile", "STRING", clean_mobile)
            ]
        )
        rows = list(client.query(query, job_config=job_config))
        if rows:
            formatted = _format_bq_row(dict(rows[0]))
            _BQ_BOOKINGS_CACHE[clean_mobile] = formatted
            return formatted
    except Exception as e:
        print(f"[BQ Lookup Warning]: {e}")

    # Fallback to local backend if not in BQ
    matches = bms_backend.find_bookings_by_phone(clean_mobile)
    if matches:
        b = matches[0]
        return {
            "found": True,
            "source": "Local Memory",
            "primary_key_mobile": clean_mobile,
            "booking_id": b.booking_id,
            "customer_name": b.customer_name,
            "movie_title": b.movie_title,
            "language": b.language,
            "format": b.format,
            "cinema_name": b.cinema_name,
            "screen_audi": b.screen_audi,
            "showtime": b.showtime.strftime("%a, %d %b %Y @ %I:%M %p"),
            "seat_numbers": ", ".join(b.seat_numbers),
            "amount_paid": f"₹{b.total_paid:.2f}",
            "status": b.status,
        }

    return {
        "found": False,
        "mobile_searched": clean_mobile,
        "error": f"No booking found in BigQuery under mobile number {clean_mobile}.",
    }


def fetch_booking_status(booking_id: str = "", phone_number: str = "") -> dict:
    """Fetch real-time booking status by mobile number or booking ID from BigQuery.

    Args:
        booking_id: Optional ticket booking reference code (e.g., 'TKT-882190').
        phone_number: Optional 10-digit registered Indian mobile number (e.g., '9876543210').

    Returns:
        Dictionary containing movie name, show timings, audi, seats, language, and status.
    """
    if phone_number:
        res = fetch_booking_by_mobile(phone_number)
        if res.get("found"):
            return res

    # Check if booking_id is actually a 10-digit mobile number
    clean_input = _normalize_indian_mobile(booking_id)
    if len(clean_input) == 10 and clean_input.isdigit():
        res = fetch_booking_by_mobile(clean_input)
        if res.get("found"):
            return res

    # Query BigQuery by booking_id
    if booking_id:
        try:
            client = _get_bq_client()
            query = f"""
                SELECT * FROM `{BQ_BOOKINGS_TABLE}`
                WHERE UPPER(booking_id) = @bid
                LIMIT 1
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("bid", "STRING", booking_id.strip().upper())
                ]
            )
            rows = list(client.query(query, job_config=job_config))
            if rows:
                r = dict(rows[0])
                return {
                    "found": True,
                    "source": f"BigQuery ({BQ_BOOKINGS_TABLE})",
                    "primary_key_mobile": r["mobile_number"],
                    "booking_id": r["booking_id"],
                    "customer_name": r["customer_name"],
                    "movie_title": r["movie_name"],
                    "language": r["language"],
                    "format": r["format"],
                    "cinema_name": r["cinema_name"],
                    "screen_audi": r["screen_audi"],
                    "showtime": r["show_time"],
                    "seat_numbers": r["seat_numbers"],
                    "total_tickets": r["total_tickets"],
                    "amount_paid": f"₹{r['amount_paid']:.2f}",
                    "status": r["booking_status"],
                    "cancellation_eligible": r["cancellation_eligible"],
                    "payment_method": r["payment_method"],
                }
        except Exception as e:
            print(f"[BQ Booking ID Lookup Warning]: {e}")

    # Fallback to local backend
    booking = bms_backend.get_booking(booking_id)
    if not booking:
        return {
            "found": False,
            "error": f"No booking found for '{booking_id or phone_number}'. Ask caller for their 10-digit mobile number.",
        }

    return {
        "found": True,
        "booking_id": booking.booking_id,
        "customer_name": booking.customer_name,
        "status": booking.status,
        "movie_title": booking.movie_title,
        "format": booking.format,
        "language": booking.language,
        "cinema_name": booking.cinema_name,
        "screen_audi": booking.screen_audi,
        "showtime": booking.showtime.strftime("%A, %d %B %Y at %I:%M %p"),
        "seat_numbers": ", ".join(booking.seat_numbers),
        "amount_paid": f"₹{booking.total_paid:.2f}",
        "cancellation_eligible": booking.cancellation_eligible,
    }


def list_customer_bookings(phone_number: str) -> dict:
    """Retrieve customer booking from BigQuery using their 10-digit Indian mobile number.

    Args:
        phone_number: The 10-digit Indian mobile number (primary key).

    Returns:
        Dictionary with matching booking details from BigQuery.
    """
    return fetch_booking_by_mobile(phone_number)


def request_voice_otp(booking_id: str, phone_number: str = "") -> dict:
    """Generate and issue a 4-digit voice verification OTP to authorize ticket cancellation.

    Security Requirement: Must be called before initiating ticket cancellation and refund.
    Sends an OTP to the customer's registered phone and informs the agent of the expected OTP.

    Args:
        booking_id: The booking ID to be cancelled (e.g., 'TKT-882190').
        phone_number: Optional customer phone number.

    Returns:
        OTP challenge status and delivery details.
    """
    return bms_backend.generate_voice_otp(booking_id, phone_number)


def verify_voice_identity(booking_id: str, voice_otp: str) -> dict:
    """Verify the caller's spoken 4-digit OTP to authorize refund processing.

    Finance & Ops Security Check: Caller must speak the verification code received on
    their registered phone. If valid, returns a verification token.

    Args:
        booking_id: The booking ID undergoing cancellation.
        voice_otp: The 4-digit OTP code spoken by the caller.

    Returns:
        Verification outcome and security verification token.
    """
    return bms_backend.verify_voice_identity(booking_id, voice_otp)


def process_ticket_cancellation(
    booking_id: str,
    verification_token: str,
    refund_destination: str = "ORIGINAL_PAYMENT_METHOD",
    reason: str = "Customer requested cancellation via IVR",
) -> dict:
    """Process ticket cancellation and trigger automated refund with Finance & Ops.

    Requires a valid verification_token obtained from verify_voice_identity.
    Calculates cancellation fees according to standard policy and initiates refund.

    Args:
        booking_id: The booking reference ID to cancel.
        verification_token: The security verification token from verify_voice_identity.
        refund_destination: Either 'ORIGINAL_PAYMENT_METHOD' (default: 3-5 days) or 'INSTANT_WALLET' (instant).
        reason: Optional reason for cancellation.

    Returns:
        Refund receipt, net refund amount, transaction reference, and timeline.
    """
    return bms_backend.process_cancellation_and_refund(
        booking_id=booking_id,
        verification_token=verification_token,
        refund_destination=refund_destination,
        cancellation_reason=reason,
    )


def transfer_to_support_desk(
    booking_id: str = "",
    department: str = "CUSTOMER_CARE",
    reason: str = "Customer requested human representative",
) -> dict:
    """Transfer the call to a human support agent or supervisor.

    Use this if voice verification fails multiple times, or if the caller explicitly
    demands to speak with a human executive.

    Args:
        booking_id: The booking ID if applicable.
        department: Either 'FINANCE_OPS' or 'CUSTOMER_CARE'.
        reason: The reason for the escalation.

    Returns:
        Transfer status and queue wait time estimation.
    """
    return {
        "status": "TRANSFERRING",
        "department": department,
        "booking_id": booking_id,
        "estimated_wait_time": "Under 2 minutes",
        "transfer_message": (
            f"Connecting caller to {department.replace('_', ' ').title()} priority queue. "
            f"Reason: {reason}."
        ),
    }


def search_knowledge_base(query: str) -> dict:
    """Search the official Ticketing RAG Knowledge Base & FAQ system (Vertex AI Search / Discovery Engine).

    Optimized for Ultra-Low Latency (~350ms): Retrieves raw extractive FAQ text segments and snippets
    directly in a single gRPC page call without waiting for Discovery Engine's slow server-side LLM
    SummarySpec, allowing Gemini Live to synthesize and speak the answer immediately.

    Args:
        query: The customer's question or search query (e.g., 'Transaction was canceled but seats appear blocked').

    Returns:
        Dictionary containing the raw retrieved FAQ text chunks (`rag_summary`) and document citations.
    """
    norm_q = (query or "").strip().lower()
    if norm_q in _RAG_CACHE:
        return _RAG_CACHE[norm_q]

    try:
        from google.cloud import discoveryengine_v1 as discoveryengine

        project_id = GOOGLE_CLOUD_PROJECT_NUMBER
        location = SEARCH_LOCATION
        engine_id = SEARCH_ENGINE_ID

        client = _get_search_client()
        serving_config = (
            f"projects/{project_id}/locations/{location}/collections/default_collection/"
            f"engines/{engine_id}/servingConfigs/default_search"
        )

        # Ultra-fast raw retrieval: fetch 1 extractive segment + snippet per doc (NO slow SummarySpec!)
        content_search_spec = discoveryengine.SearchRequest.ContentSearchSpec(
            snippet_spec=discoveryengine.SearchRequest.ContentSearchSpec.SnippetSpec(
                return_snippet=True
            ),
            extractive_content_spec=discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
                max_extractive_segment_count=1,
            ),
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=3,
            content_search_spec=content_search_spec,
            spell_correction_spec=discoveryengine.SearchRequest.SpellCorrectionSpec(
                mode=discoveryengine.SearchRequest.SpellCorrectionSpec.Mode.AUTO
            ),
        )

        # Single RPC round-trip (.pages iterator prevents multi-page pagination overhead)
        first_page = next(iter(client.search(request).pages))

        sources = []
        raw_chunks = []
        for idx, res in enumerate(first_page.results):
            if idx >= 3:
                break
            doc = res.document
            title = ""
            snippet = ""
            extractive_text = ""
            if doc.derived_struct_data:
                ds = dict(doc.derived_struct_data)
                title = ds.get("title", "")
                snippets = ds.get("snippets", [])
                if snippets:
                    snippet = dict(snippets[0]).get("snippet", "")
                segments = ds.get("extractive_segments", [])
                if segments:
                    extractive_text = dict(segments[0]).get("content", "")

            chunk_body = extractive_text or snippet
            if chunk_body:
                raw_chunks.append(f"[{idx + 1}] {title}:\n{chunk_body[:900]}")

            sources.append({
                "id": doc.id,
                "title": title,
                "snippet": snippet,
                "extractive_answer": extractive_text,
            })

        combined_raw_context = "\n\n".join(raw_chunks) if raw_chunks else "No matching FAQ segments found."
        result_payload = {
            "success": True,
            "mode": "RAW_EXTRACTIVE_CHUNKS_FOR_GEMINI_LIVE",
            "query": query,
            "rag_summary": combined_raw_context,
            "sources": sources,
        }
        _RAG_CACHE[norm_q] = result_payload
        return result_payload
    except Exception as e:
        return {
            "success": False,
            "query": query,
            "error": str(e),
        }


# Alias for backward compatibility
search_bms_knowledge_base = search_knowledge_base

# Exported list of tool callables for Gemini Live API
BMS_IVR_TOOLS = [
    fetch_booking_by_mobile,
    fetch_booking_status,
    list_customer_bookings,
    request_voice_otp,
    verify_voice_identity,
    process_ticket_cancellation,
    transfer_to_support_desk,
    search_knowledge_base,
]

# Populate in-memory BigQuery cache synchronously (<1ms) and launch background warmers
_seed_bq_cache_sync()
threading.Thread(target=_prewarm_bq, daemon=True).start()
threading.Thread(target=_prewarm_discovery_engine, daemon=True).start()

