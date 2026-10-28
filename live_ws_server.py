"""Real-Time Full-Duplex WebSocket Audio Bridge for Gemini Live IVR.

Connects the browser's continuous Web Audio API microphone stream (16kHz PCM) directly to
Google GenAI Multimodal Live API (`gemini-3.8-flash-live-preview`) over WebSockets,
with millisecond-precision telemetry tracking:
- Time-to-First-Audio (TTFB ms)
- Individual Tool Execution Latency (ms) for Vertex AI Search RAG & Booking APIs
- Total Turn Processing Duration (ms)
- Audio Stream Byte Counters
"""

import asyncio
import base64
import json
import os
import sys
import threading
import time
from typing import Any, Callable, Dict

import websockets
from google import genai
from google.genai import types

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from config_loader import GOOGLE_CLOUD_LOCATION, GOOGLE_CLOUD_PROJECT, VERTEX_LIVE_MODEL
from ivr_tools import BMS_IVR_TOOLS

IVR_SYSTEM_INSTRUCTION = """
You are "Aria", the official AI Voice Support Assistant for Cinema & Entertainment IVR telephony.
You assist customers calling customer care with their movie ticket bookings, real-time show status, ticket cancellations, and general ticketing FAQs.

STAKEHOLDER & BUSINESS OBJECTIVES:
1. CUSTOMER EXPERIENCE (Booking Status by Mobile Number — BigQuery Primary Key):
   - The primary key for customer bookings in our BigQuery `customer_bookings` database is the 10-digit Indian mobile number (e.g., 9876543210, 9811122233, 9900112233, 9820098200, 9711122233, 9123456789).
   - When a caller asks about their booking, show timings, seats, or cinema location, ask for or use their 10-digit mobile number and call `fetch_booking_by_mobile` (or `fetch_booking_status`).
   - Clearly state the movie name, language, format (e.g., IMAX 3D, Dolby Atmos), cinema name, audi/screen number, show timing, and exact seat numbers.
   - Mention that their M-ticket QR code on WhatsApp/SMS can be scanned directly at the cinema gate.

2. FINANCE & OPERATIONS (Ticket Cancellation & Automated Refund Processing):
   - When a caller requests to cancel a ticket, look up the booking first using `fetch_booking_status`.
   - Explain the cancellation fee policy and quote the net refund amount clearly.
   - MANDATORY SECURITY REQUIREMENT: Before any cancellation or refund can be executed, you MUST perform Voice Identity Verification.
   - Call `request_voice_otp` to send/issue a 4-digit voice verification code to their registered mobile.
   - Ask the caller: "For security and to authorize your refund, please read out the 4-digit verification code sent to your registered phone."
   - Once the caller speaks the code, call `verify_voice_identity`.
   - If verified: ask if they prefer the refund to their Original Payment Method (3-5 business days) or instant Digital Wallet.
   - Call `process_ticket_cancellation` with the verification token and selected refund preference.
   - State the Refund Reference ID, refunded amount, and timeline to the caller.

3. RAG KNOWLEDGE BASE & POLICY INQUIRIES (Vertex AI Search / Discovery Engine):
   - Whenever a caller asks general questions about ticketing policies, payment failures, why seats appear blocked after a canceled transaction, refund processing timelines, loyalty membership privileges, gift vouchers, or general FAQs, ALWAYS call the `search_knowledge_base` tool with their question.
   - Summarize the retrieved `rag_summary` clearly and concisely in 2-3 sentences for spoken telephony.

4. CONVERSATIONAL TELEPHONY STYLE:
   - Speak in a warm, polite, professional, and clear tone.
   - Keep each spoken response concise (1-3 sentences). Do not speak long walls of text over the phone.
   - If the caller needs help with something beyond your capabilities or verification fails repeatedly, call `transfer_to_support_desk`.
"""

WS_HOST = "0.0.0.0"
WS_PORT = 8765

TOOL_MAP: Dict[str, Callable] = {t.__name__: t for t in BMS_IVR_TOOLS}


DEFAULT_LIVE_MODEL = os.getenv("GEMINI_LIVE_MODEL", "gemini-3.8-flash-live-preview")
VERTEX_FALLBACK_MODEL = VERTEX_LIVE_MODEL


def get_genai_client(
    requested_model: str = DEFAULT_LIVE_MODEL,
    api_key_override: str = "",
) -> tuple[genai.Client, str, bool]:
    """Initialize GenAI client using Gemini API Key (preferred for gemini-3.8-flash-live-preview) or Vertex AI."""
    api_key = api_key_override.strip() or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key), requested_model, False
    project_id = GOOGLE_CLOUD_PROJECT
    location = GOOGLE_CLOUD_LOCATION
    return (
        genai.Client(vertexai=True, project=project_id, location=location),
        requested_model,
        True,
    )


def get_live_config(voice_name: str = "Aoede", language_code: str = "en-IN") -> types.LiveConnectConfig:
    """Create LiveConnectConfig with bidirectional audio, Indian English (en-IN) speech config, and IVR/RAG tools."""
    # Map full Chirp3-HD label to Gemini Live prebuilt voice_name if passed
    clean_voice = voice_name.split("-")[-1] if "-" in voice_name else voice_name
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            language_code=language_code,
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=clean_voice)
            ),
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        system_instruction=types.Content(
            parts=[types.Part.from_text(text=IVR_SYSTEM_INSTRUCTION)]
        ),
        tools=BMS_IVR_TOOLS,
    )


async def handle_browser_client(websocket) -> None:
    """Handle a single browser WebSocket connection bridged to Gemini Live Session with telemetry."""
    import urllib.parse

    path = getattr(websocket, "path", "") or getattr(getattr(websocket, "request", None), "path", "")
    query_params = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    selected_voice = query_params.get("voice", ["Aoede"])[0]
    selected_lang = query_params.get("lang", ["en-IN"])[0]
    selected_model = query_params.get("model", [DEFAULT_LIVE_MODEL])[0]
    api_key_param = query_params.get("api_key", [""])[0]

    print(
        f"🌐 [Live WebSocket] Browser connected with model={selected_model}, voice={selected_voice} ({selected_lang})"
    )
    client, model_name, is_vertex = get_genai_client(
        requested_model=selected_model,
        api_key_override=api_key_param,
    )
    config = get_live_config(voice_name=selected_voice, language_code=selected_lang)

    # Telemetry state per turn
    turn_start_time = time.perf_counter()
    post_tool_start_time = time.perf_counter()
    first_audio_received = False
    first_audio_timestamp = 0.0
    ttfb_ms = 0
    llm_ttfb_ms = 0
    turn_audio_bytes = 0
    turn_tool_latencies = []

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _connect_with_fallback():
        try:
            async with client.aio.live.connect(model=model_name, config=config) as s:
                yield s, model_name
        except Exception as first_err:
            if is_vertex and "1008" in str(first_err) and model_name != VERTEX_FALLBACK_MODEL:
                async with client.aio.live.connect(model=VERTEX_FALLBACK_MODEL, config=config) as s:
                    yield s, DEFAULT_LIVE_MODEL
            else:
                raise

    try:
        async with _connect_with_fallback() as (gemini_session, active_model):
            await websocket.send(json.dumps({
                "type": "status",
                "status": "connected",
                "model": active_model,
                "message": f"Connected to Aria ({active_model})",
            }))

            # Reset turn timer for initial greeting
            turn_start_time = time.perf_counter()
            post_tool_start_time = turn_start_time
            first_audio_received = False
            turn_audio_bytes = 0

            await gemini_session.send_client_content(
                turns=[
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(
                            text="Hello! I just dialed into customer support. Please greet me briefly."
                        )],
                    )
                ],
                turn_complete=True,
            )

            async def browser_to_gemini() -> None:
                """Stream incoming 16kHz PCM audio chunks or text prompts from browser to Gemini."""
                nonlocal turn_start_time, post_tool_start_time, first_audio_received, turn_audio_bytes, turn_tool_latencies
                async for message in websocket:
                    if isinstance(message, bytes):
                        await gemini_session.send_realtime_input(
                            audio=types.Blob(data=message, mime_type="audio/pcm;rate=16000")
                        )
                    elif isinstance(message, str):
                        data = json.loads(message)
                        msg_type = data.get("type")
                        if msg_type == "audio_b64":
                            pcm_bytes = base64.b64decode(data["data"])
                            await gemini_session.send_realtime_input(
                                audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                            )
                        elif msg_type == "user_speech_end":
                            # Marker sent when user finishes speaking or clicks a prompt
                            turn_start_time = time.perf_counter()
                            post_tool_start_time = turn_start_time
                            first_audio_received = False
                            turn_audio_bytes = 0
                            turn_tool_latencies = []
                        elif msg_type == "text_prompt":
                            text_query = data.get("text", "")
                            if text_query:
                                turn_start_time = time.perf_counter()
                                post_tool_start_time = turn_start_time
                                first_audio_received = False
                                turn_audio_bytes = 0
                                turn_tool_latencies = []
                                await gemini_session.send_client_content(
                                    turns=[
                                        types.Content(
                                            role="user",
                                            parts=[types.Part.from_text(text=text_query)],
                                        )
                                    ],
                                    turn_complete=True,
                                )

            async def gemini_to_browser() -> None:
                """Stream Gemini 24kHz audio chunks, transcriptions, tool calls, and latency metrics."""
                nonlocal turn_start_time, post_tool_start_time, first_audio_received, first_audio_timestamp, ttfb_ms, llm_ttfb_ms, turn_audio_bytes, turn_tool_latencies
                while True:
                    tool_calls_to_resolve = []
                    async for msg in gemini_session.receive():
                        # 1. Handle Autonomous Tool Calls
                        if msg.tool_call:
                            for fc in msg.tool_call.function_calls:
                                tool_calls_to_resolve.append(fc)

                        # 2. Handle Server Content
                        if msg.server_content:
                            sc = msg.server_content

                            if getattr(sc, "interrupted", False):
                                await websocket.send(json.dumps({"type": "interrupted"}))
                                turn_start_time = time.perf_counter()
                                post_tool_start_time = turn_start_time
                                first_audio_received = False
                                turn_audio_bytes = 0

                            # User input transcription (marks active user turn)
                            if sc.input_transcription and sc.input_transcription.text:
                                turn_start_time = time.perf_counter()
                                post_tool_start_time = turn_start_time
                                first_audio_received = False
                                turn_tool_latencies = []
                                await websocket.send(json.dumps({
                                    "type": "transcript_user",
                                    "text": sc.input_transcription.text,
                                }))

                            # AI output transcription
                            if sc.output_transcription and sc.output_transcription.text:
                                await websocket.send(json.dumps({
                                    "type": "transcript_ai",
                                    "text": sc.output_transcription.text,
                                }))

                            # Real-time 24kHz PCM audio stream
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data and part.inline_data.data:
                                        now = time.perf_counter()
                                        if not first_audio_received:
                                            first_audio_received = True
                                            first_audio_timestamp = now
                                            ttfb_ms = int((now - turn_start_time) * 1000)
                                            llm_ttfb_ms = int((now - post_tool_start_time) * 1000)
                                            total_tool_ms = sum(t["latency_ms"] for t in turn_tool_latencies)
                                            # Emit immediate TTFB metric to UI
                                            await websocket.send(json.dumps({
                                                "type": "ttfb_metric",
                                                "ttfb_ms": ttfb_ms,
                                                "llm_ttfb_ms": llm_ttfb_ms,
                                                "tool_latency_ms": total_tool_ms,
                                            }))

                                        pcm_chunk = part.inline_data.data
                                        turn_audio_bytes += len(pcm_chunk)
                                        b64_pcm = base64.b64encode(pcm_chunk).decode("ascii")
                                        await websocket.send(json.dumps({
                                            "type": "audio",
                                            "data": b64_pcm,
                                        }))

                            if getattr(sc, "turn_complete", False):
                                now = time.perf_counter()
                                e2e_turn_ms = int((now - turn_start_time) * 1000)
                                total_tool_ms = sum(t["latency_ms"] for t in turn_tool_latencies)
                                audio_stream_ms = int((now - first_audio_timestamp) * 1000) if first_audio_received else 0
                                audio_duration_sec = round(turn_audio_bytes / (24000 * 2), 2)
                                await websocket.send(json.dumps({
                                    "type": "turn_complete",
                                    "ttfb_ms": ttfb_ms,
                                    "llm_ttfb_ms": llm_ttfb_ms,
                                    "tool_latency_ms": total_tool_ms,
                                    "audio_stream_ms": audio_stream_ms,
                                    "total_turn_ms": e2e_turn_ms,
                                    "e2e_turn_ms": e2e_turn_ms,
                                    "audio_bytes": turn_audio_bytes,
                                    "audio_duration_sec": audio_duration_sec,
                                    "tool_latencies": turn_tool_latencies,
                                    "timestamp": time.strftime("%H:%M:%S"),
                                }))

                    # Resolve tool calls and measure exact execution latency
                    if tool_calls_to_resolve:
                        function_responses = []
                        for fc in tool_calls_to_resolve:
                            func_name = fc.name
                            args = dict(fc.args or {})
                            t_start = time.perf_counter()

                            await websocket.send(json.dumps({
                                "type": "tool_start",
                                "name": func_name,
                                "args": args,
                                "timestamp": time.strftime("%H:%M:%S"),
                            }))

                            func = TOOL_MAP.get(func_name)
                            if func:
                                try:
                                    loop = asyncio.get_running_loop()
                                    tool_output = await loop.run_in_executor(None, lambda: func(**args))
                                except Exception as err:
                                    tool_output = {"error": str(err)}
                            else:
                                tool_output = {"error": f"Unknown tool: {func_name}"}

                            tool_latency_ms = int((time.perf_counter() - t_start) * 1000)
                            turn_tool_latencies.append({
                                "name": func_name,
                                "latency_ms": tool_latency_ms,
                            })
                            print(f"⚙️ [Live Tool] {func_name} completed in {tool_latency_ms} ms")

                            await websocket.send(json.dumps({
                                "type": "tool_result",
                                "name": func_name,
                                "args": args,
                                "result": tool_output,
                                "latency_ms": tool_latency_ms,
                                "timestamp": time.strftime("%H:%M:%S"),
                            }))

                            function_responses.append(
                                types.FunctionResponse(
                                    name=func_name,
                                    id=fc.id,
                                    response={"result": tool_output},
                                )
                            )

                        # Record post-tool start time so we measure pure LLM generation latency after tool execution
                        post_tool_start_time = time.perf_counter()
                        first_audio_received = False
                        await gemini_session.send_tool_response(function_responses=function_responses)

            await asyncio.gather(browser_to_gemini(), gemini_to_browser())

    except websockets.exceptions.ConnectionClosed:
        print("📴 [Live WebSocket] Browser client disconnected.")
    except Exception as e:
        print(f"❌ [Live WebSocket Error]: {e}")
        try:
            await websocket.send(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass


async def start_ws_server() -> None:
    """Start the WebSocket bridge server on WS_PORT."""
    print(f"🚀 Starting Smart IVR Real-Time Voice WebSocket Server on ws://{WS_HOST}:{WS_PORT}")
    async with websockets.serve(handle_browser_client, WS_HOST, WS_PORT, max_size=10 * 1024 * 1024):
        await asyncio.Future()


def ensure_background_ws_server() -> None:
    """Ensure the WebSocket server is running in a background daemon thread."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("127.0.0.1", WS_PORT))
    sock.close()
    if result == 0:
        return

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(start_ws_server())

    t = threading.Thread(target=_run, daemon=True)
    t.start()


if __name__ == "__main__":
    asyncio.run(start_ws_server())
