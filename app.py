"""Smart IVR & Voice Automation - Clean Executive Real-Time Telemetry Console.

Features:
1. Continuous Full-Duplex Hands-Free Voice Conversation over WebSockets (`ws://localhost:8765`)
2. Real-Time Latency & Telemetry KPI Dashboard:
   - Time-to-First-Audio (TTFB ms)
   - Individual Tool Execution Latency (ms) for Vertex AI Search RAG & Booking APIs
   - End-to-End Turn Processing Duration (ms)
   - Live Audio Stream Byte Counters
3. Live Tool Execution Waterfall & Payload Inspector
4. Vertex AI Search RAG Explorer & Stakeholder Booking/Refund Monitors
"""

import os
import sys

import streamlit as st
import streamlit.components.v1 as components

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from config_loader import BQ_BOOKINGS_TABLE
from ivr_tools import fetch_booking_by_mobile, search_knowledge_base
from live_ws_server import ensure_background_ws_server
from mock_ticketing_backend import ticketing_backend as bms_backend

# Ensure background full-duplex WebSocket server is running on port 8765
ensure_background_ws_server()

st.set_page_config(
    page_title="Smart IVR • Real-Time Voice & Telemetry",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

h1, h2, h3, h4 {
    font-family: 'Outfit', sans-serif;
}

.stApp {
    background: radial-gradient(circle at 50% 0%, #171226 0%, #090C15 75%);
    color: #F8FAFC;
}

/* Remove extra top padding in Streamlit */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2rem !important;
    max-width: 1440px !important;
}

.top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
    padding: 14px 24px;
    margin-bottom: 18px;
    backdrop-filter: blur(12px);
}

.brand-title {
    font-family: 'Outfit', sans-serif;
    font-size: 1.35rem;
    font-weight: 800;
    color: #FFFFFF;
    display: flex;
    align-items: center;
    gap: 12px;
}

.brand-tag {
    background: linear-gradient(135deg, #F84464, #E11D48);
    color: white;
    font-size: 0.72rem;
    padding: 4px 10px;
    border-radius: 999px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

.arch-pills {
    display: flex;
    gap: 10px;
    align-items: center;
}

.arch-pill {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #CBD5E1;
    font-size: 0.75rem;
    padding: 5px 12px;
    border-radius: 999px;
    font-weight: 500;
}

.ticket-card {
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 12px;
}

.badge-confirmed {
    background: rgba(16, 185, 129, 0.15);
    color: #10B981;
    border: 1px solid rgba(16, 185, 129, 0.35);
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
}

.badge-cancelled {
    background: rgba(239, 68, 68, 0.15);
    color: #EF4444;
    border: 1px solid rgba(239, 68, 68, 0.35);
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 700;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Top Brand & Architecture Header
# -----------------------------------------------------------------------------
st.markdown(
    """
    <div class="top-nav">
        <div class="brand-title">
            <span>🎟️ Smart IVR Studio</span>
            <span class="brand-tag">GEMINI 3.1 FLASH LIVE PREVIEW</span>
        </div>
        <div class="arch-pills">
            <span class="arch-pill">⚡ Full-Duplex 24kHz PCM</span>
            <span class="arch-pill">📱 BigQuery Mobile Lookup</span>
            <span class="arch-pill">🔍 Vertex AI Search RAG</span>
            <span class="arch-pill">🛡️ Voice OTP Identity Gate</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("ℹ️ Voice AI Telemetry & Latency Guide: What is TTFB vs Turn Latency vs Tool Call Latency vs E2E Latency?", expanded=False):
    st.markdown(
        """
| Latency Metric | Definition | Why It Matters in Voice AI |
| :--- | :--- | :--- |
| **⚡ Perceived TTFB (Time-To-First-Audio Byte)** | Time elapsed from the exact millisecond the caller **stops speaking** (or clicks a prompt) until the **very first audio byte** of Aria's voice response arrives at the speaker (`User Speech End → First Audio Byte`). | **This is the single most critical metric for human conversational naturalness.** Humans expect a conversational response to begin within **300–800 ms**. Even if a full answer takes 6 seconds to speak, a low TTFB makes the AI feel instantaneous. |
| **🧠 LLM Model Inference Latency** | Time taken purely by **Gemini 3.1 Flash Live Preview** to reason over the prompt/tool output and synthesize the first audio frame (`TTFB − Tool Call Latency`). | Isolates Google Gemini's core neural audio generation speed from external database or network bottlenecks. |
| **🛠️ Tool Call Latency** | Time spent executing external backend tools: **BigQuery (`customer_bookings` lookup by mobile number)**, **Vertex AI Search RAG**, or **Refund Ledger APIs**. | Shows database and RAG search performance. When a tool is called, `Perceived TTFB = Tool Call Latency + LLM Inference Latency`. |
| **🔊 Audio Streaming Duration** | Time spent streaming and speaking the synthesized 24kHz PCM audio response from the **first audio byte until the final word** is spoken (`E2E Turn Latency − TTFB`). | Depends on how long Aria's spoken sentence is (e.g. reading out movie title, seats, showtime, and cinema name takes ~4–7 seconds of audio). |
| **🏁 End-to-End (E2E) Turn Latency** | Total wall-clock time from when the caller finishes speaking until the **entire turn (Tool Calls + LLM Reasoning + Full Audio Stream)** is 100% completed (`TTFB + Audio Streaming Duration`). | Measures total turn throughput and resource utilization per conversational turn. |
        """
    )

# -----------------------------------------------------------------------------
# Full-Bleed Real-Time Voice & Telemetry Command Center (HTML5 + WebSockets)
# -----------------------------------------------------------------------------
REALTIME_COMMAND_CENTER_HTML = """
<!DOCTYPE html>
<html>
<head>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
    * {
        box-sizing: border-box;
    }
    body {
        margin: 0;
        padding: 0;
        background: transparent;
        font-family: 'Inter', sans-serif;
        color: #F8FAFC;
    }

    /* KPI Latency Strip */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 12px;
        margin-bottom: 16px;
    }
    .kpi-card {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 14px 18px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    .kpi-label {
        font-size: 0.74rem;
        color: #94A3B8;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .kpi-value {
        font-family: 'Outfit', sans-serif;
        font-size: 1.65rem;
        font-weight: 800;
        color: #FFFFFF;
        margin-top: 6px;
        display: flex;
        align-items: baseline;
        gap: 8px;
    }
    .kpi-sub {
        font-size: 0.73rem;
        color: #64748B;
        margin-top: 4px;
        font-family: 'JetBrains Mono', monospace;
    }
    .badge-fast {
        background: rgba(16, 185, 129, 0.15);
        color: #10B981;
        font-size: 0.68rem;
        padding: 2px 8px;
        border-radius: 999px;
        font-weight: 700;
    }
    .badge-med {
        background: rgba(245, 158, 11, 0.15);
        color: #F59E0B;
        font-size: 0.68rem;
        padding: 2px 8px;
        border-radius: 999px;
        font-weight: 700;
    }

    /* Main 2-Column Studio Grid */
    .studio-grid {
        display: grid;
        grid-template-columns: 1.12fr 0.88fr;
        gap: 18px;
    }

    .panel-card {
        background: rgba(15, 23, 42, 0.88);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 16px;
        padding: 18px;
        display: flex;
        flex-direction: column;
        height: 555px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
    }

    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.07);
        margin-bottom: 14px;
    }
    .panel-title {
        font-family: 'Outfit', sans-serif;
        font-size: 1.02rem;
        font-weight: 700;
        color: #FFFFFF;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .status-pill {
        font-size: 0.72rem;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.15);
        color: #94A3B8;
        border: 1px solid rgba(148, 163, 184, 0.3);
    }
    .status-pill.live {
        background: rgba(16, 185, 129, 0.18);
        color: #10B981;
        border-color: rgba(16, 185, 129, 0.45);
    }

    /* Voice Orb & Call Control Bar */
    .voice-hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: rgba(9, 13, 22, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        padding: 14px 18px;
        margin-bottom: 12px;
    }
    .orb-cluster {
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .orb {
        width: 62px;
        height: 62px;
        border-radius: 50%;
        background: radial-gradient(circle at 30% 30%, #F84464, #9333EA 65%, #1E1B4B);
        box-shadow: 0 0 24px rgba(248, 68, 100, 0.4);
        transition: transform 0.08s ease-out, box-shadow 0.15s ease;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        flex-shrink: 0;
    }
    .orb.active {
        background: radial-gradient(circle at 30% 30%, #10B981, #059669 65%, #064E3B);
        box-shadow: 0 0 32px rgba(16, 185, 129, 0.7);
    }
    .orb.speaking {
        background: radial-gradient(circle at 30% 30%, #F84464, #EC4899 65%, #831843);
        box-shadow: 0 0 42px rgba(248, 68, 100, 0.9);
    }
    .orb-info-title {
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 0.95rem;
        color: #FFFFFF;
    }
    .orb-info-sub {
        font-size: 0.78rem;
        color: #94A3B8;
        margin-top: 3px;
    }

    .call-btn {
        padding: 11px 20px;
        border-radius: 10px;
        border: none;
        font-family: 'Outfit', sans-serif;
        font-weight: 700;
        font-size: 0.88rem;
        cursor: pointer;
        transition: all 0.18s ease;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .btn-start {
        background: linear-gradient(135deg, #10B981, #059669);
        color: white;
        box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
    }
    .btn-start:hover {
        filter: brightness(1.1);
    }
    .btn-stop {
        background: linear-gradient(135deg, #EF4444, #DC2626);
        color: white;
        box-shadow: 0 4px 14px rgba(239, 68, 68, 0.35);
        display: none;
    }

    /* Quick Prompt Shortcuts */
    .shortcuts-bar {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 12px;
    }
    .shortcut-chip {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.12);
        color: #E2E8F0;
        border-radius: 8px;
        padding: 6px 11px;
        font-size: 0.74rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .shortcut-chip:hover {
        background: rgba(248, 68, 100, 0.18);
        border-color: #F84464;
        color: #FFFFFF;
    }

    /* Conversation Feed */
    .chat-stream {
        flex: 1;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding-right: 6px;
    }
    .turn-card {
        background: rgba(9, 13, 22, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 11px 14px;
        font-size: 0.84rem;
        line-height: 1.45;
    }
    .turn-user {
        border-left: 3px solid #38BDF8;
    }
    .turn-ai {
        border-left: 3px solid #F84464;
    }
    .turn-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 5px;
    }
    .speaker-name {
        font-weight: 700;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .speaker-user { color: #38BDF8; }
    .speaker-ai { color: #F84464; }

    .turn-metrics {
        display: flex;
        gap: 8px;
        align-items: center;
    }
    .metric-tag {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.7rem;
        background: rgba(255, 255, 255, 0.06);
        color: #CBD5E1;
        padding: 2px 7px;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }
    .metric-tag.ttfb {
        color: #10B981;
        background: rgba(16, 185, 129, 0.12);
        border-color: rgba(16, 185, 129, 0.3);
    }

    /* Right Panel: Tool Execution Waterfall & Latency Inspector */
    .waterfall-list {
        flex: 1;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 10px;
        padding-right: 4px;
    }
    .tool-card {
        background: rgba(9, 13, 22, 0.72);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-left: 3px solid #F59E0B;
        border-radius: 12px;
        padding: 12px 14px;
        font-size: 0.8rem;
    }
    .tool-card.done {
        border-left-color: #10B981;
    }
    .tool-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .tool-name {
        font-family: 'JetBrains Mono', monospace;
        font-weight: 700;
        font-size: 0.82rem;
        color: #F8FAFC;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .latency-badge {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.73rem;
        font-weight: 700;
        padding: 3px 9px;
        border-radius: 999px;
        background: rgba(16, 185, 129, 0.16);
        color: #10B981;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .tool-section-label {
        font-size: 0.7rem;
        color: #94A3B8;
        text-transform: uppercase;
        font-weight: 600;
        margin: 6px 0 3px 0;
    }
    .code-box {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.73rem;
        background: rgba(0, 0, 0, 0.45);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 8px 10px;
        color: #E2E8F0;
        overflow-x: auto;
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 125px;
        overflow-y: auto;
    }
    .empty-placeholder {
        color: #64748B;
        text-align: center;
        margin-top: 140px;
        font-size: 0.85rem;
    }
</style>
</head>
<body>

<!-- TOP 5-CARD KPI TELEMETRY STRIP -->
<div class="kpi-grid">
    <div class="kpi-card" title="Time from end of user speech/prompt until the very first byte of Aria's audio arrives">
        <div class="kpi-label">
            <span>⚡ Perceived TTFB</span>
            <span id="ttfbBadge" class="badge-fast">FIRST AUDIO</span>
        </div>
        <div class="kpi-value">
            <span id="kpiTtfb">--</span>
            <span style="font-size: 0.85rem; font-weight: 600; color: #94A3B8;">ms</span>
        </div>
        <div id="kpiTtfbSub" class="kpi-sub">Wait time before AI speaks</div>
    </div>

    <div class="kpi-card" title="Pure Gemini 3.1 Flash Live Preview model reasoning & speech synthesis latency">
        <div class="kpi-label">
            <span>🧠 LLM Inference</span>
            <span id="llmBadge" class="badge-fast">GEMINI 3.1</span>
        </div>
        <div class="kpi-value">
            <span id="kpiLlmLatency">--</span>
            <span style="font-size: 0.85rem; font-weight: 600; color: #94A3B8;">ms</span>
        </div>
        <div id="kpiLlmSub" class="kpi-sub">Model reasoning time</div>
    </div>

    <div class="kpi-card" title="Execution latency for BigQuery mobile number lookup or Vertex AI Search RAG">
        <div class="kpi-label">
            <span>🛠️ Tool Call Latency</span>
            <span id="toolBadge" class="badge-fast">IDLE</span>
        </div>
        <div class="kpi-value">
            <span id="kpiToolLatency">--</span>
            <span style="font-size: 0.85rem; font-weight: 600; color: #94A3B8;">ms</span>
        </div>
        <div id="kpiToolName" class="kpi-sub">Avg: -- ms (0 calls)</div>
    </div>

    <div class="kpi-card" title="Duration spent streaming the spoken 24kHz PCM audio response after first audio byte">
        <div class="kpi-label">
            <span>🔊 Audio Streaming</span>
            <span id="streamBadge" class="badge-fast">24kHz PCM</span>
        </div>
        <div class="kpi-value">
            <span id="kpiAudioStream">--</span>
            <span style="font-size: 0.85rem; font-weight: 600; color: #94A3B8;">ms</span>
        </div>
        <div id="kpiTurnAudio" class="kpi-sub">0.0s spoken (0 KB)</div>
    </div>

    <div class="kpi-card" title="Total End-to-End Turn Latency from user turn start until full audio stream completion">
        <div class="kpi-label">
            <span>🏁 E2E Turn Total</span>
            <span class="badge-fast">END-TO-END</span>
        </div>
        <div class="kpi-value">
            <span id="kpiTurnTotal">--</span>
            <span style="font-size: 0.85rem; font-weight: 600; color: #94A3B8;">ms</span>
        </div>
        <div id="kpiE2eSub" class="kpi-sub">TTFB + Audio Stream</div>
    </div>
</div>

<!-- MAIN 2-COLUMN STUDIO & TELEMETRY WATERFALL -->
<div class="studio-grid">
    <!-- LEFT PANEL: LIVE VOICE STUDIO & TRANSCRIPT -->
    <div class="panel-card">
        <div class="panel-header">
            <div class="panel-title">
                <span>🎙️</span> Live Full-Duplex Voice Studio
            </div>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <select id="modelSelect" onchange="onVoiceChange()" style="background: rgba(15, 23, 42, 0.95); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.45); border-radius: 8px; padding: 4px 8px; font-size: 0.74rem; font-family: 'JetBrains Mono', monospace; font-weight: 600; cursor: pointer; outline: none;">
                    <option value="gemini-3.1-flash-live-preview" selected>⚡ gemini-3.1-flash-live-preview</option>
                </select>
                <select id="voiceSelect" onchange="onVoiceChange()" style="background: rgba(15, 23, 42, 0.95); color: #F8FAFC; border: 1px solid rgba(248, 68, 100, 0.45); border-radius: 8px; padding: 4px 10px; font-size: 0.76rem; font-family: 'Inter', sans-serif; font-weight: 600; cursor: pointer; outline: none;">
                    <optgroup label="🇮🇳 Indian English (en-IN) • Female Voices">
                        <option value="Aoede" selected>🇮🇳 en-IN-Chirp3-HD-Aoede (Female)</option>
                        <option value="Kore">🇮🇳 en-IN-Chirp3-HD-Kore (Female)</option>
                        <option value="Leda">🇮🇳 en-IN-Chirp3-HD-Leda (Female)</option>
                        <option value="Despina">🇮🇳 en-IN-Chirp3-HD-Despina (Female)</option>
                        <option value="Callirrhoe">🇮🇳 en-IN-Chirp3-HD-Callirrhoe (Female)</option>
                        <option value="Erinome">🇮🇳 en-IN-Chirp3-HD-Erinome (Female)</option>
                        <option value="Achernar">🇮🇳 en-IN-Chirp3-HD-Achernar (Female)</option>
                    </optgroup>
                    <optgroup label="🇮🇳 Indian English (en-IN) • Male Voices">
                        <option value="Puck">🇮🇳 en-IN-Chirp3-HD-Puck (Male)</option>
                        <option value="Charon">🇮🇳 en-IN-Chirp3-HD-Charon (Male)</option>
                        <option value="Fenrir">🇮🇳 en-IN-Chirp3-HD-Fenrir (Male)</option>
                        <option value="Orus">🇮🇳 en-IN-Chirp3-HD-Orus (Male)</option>
                        <option value="Achird">🇮🇳 en-IN-Chirp3-HD-Achird (Male)</option>
                    </optgroup>
                </select>
                <span id="connStatus" class="status-pill">DISCONNECTED</span>
            </div>
        </div>

        <div class="voice-hero">
            <div class="orb-cluster">
                <div id="voiceOrb" class="orb">🎧</div>
                <div>
                    <div id="heroTitle" class="orb-info-title">Aria • Voice: en-IN-Chirp3-HD-Aoede</div>
                    <div id="heroSub" class="orb-info-sub">Click "Start Hands-Free Call" to talk continuously</div>
                </div>
            </div>
            <div>
                <button id="startBtn" class="call-btn btn-start" onclick="startLiveCall()">
                    🟢 Start Hands-Free Call
                </button>
                <button id="stopBtn" class="call-btn btn-stop" onclick="stopLiveCall()">
                    🔴 End Call
                </button>
            </div>
        </div>

        <div class="shortcuts-bar">
            <button class="shortcut-chip" onclick="sendQuickPrompt('Can you check my movie booking under mobile number 9876543210?')">
                📱 BQ Mobile: 9876543210 (Stree 2 • Hindi)
            </button>
            <button class="shortcut-chip" onclick="sendQuickPrompt('Please fetch my booking details for mobile number 9811122233')">
                📱 BQ Mobile: 9811122233 (Kalki 2898 AD • Telugu)
            </button>
            <button class="shortcut-chip" onclick="sendQuickPrompt('Check my movie ticket details for mobile number 9900112233')">
                📱 BQ Mobile: 9900112233 (Kantara • Kannada)
            </button>
            <button class="shortcut-chip" onclick="sendQuickPrompt('My transaction was canceled but seats appear blocked. Why is that?')">
                🔍 Ask RAG: Blocked Seats FAQ
            </button>
            <button class="shortcut-chip" onclick="sendQuickPrompt('What are the loyalty membership cancellation rules?')">
                ⭐ Ask RAG: Loyalty Policy
            </button>
            <button class="shortcut-chip" onclick="sendQuickPrompt('I want to cancel booking TKT-882190 under mobile 9876543210')">
                ❌ Cancel Ticket (TKT-882190)
            </button>
        </div>

        <div id="chatStream" class="chat-stream">
            <div class="empty-placeholder">
                Start the call or click a shortcut above. Live streaming transcripts and per-turn response latency badges will appear here...
            </div>
        </div>
    </div>

    <!-- RIGHT PANEL: LIVE TOOL EXECUTION WATERFALL & LATENCY INSPECTOR -->
    <div class="panel-card">
        <div class="panel-header">
            <div class="panel-title">
                <span>⚙️</span> Tool Execution Waterfall & Latency Inspector
            </div>
            <span style="font-size: 0.74rem; color: #94A3B8; font-family: 'JetBrains Mono', monospace;">Vertex AI Search & Ticketing APIs</span>
        </div>

        <div id="waterfallList" class="waterfall-list">
            <div class="empty-placeholder">
                Autonomous tool calls (<code>search_knowledge_base</code>, <code>fetch_booking_status</code>, <code>request_voice_otp</code>, etc.) will appear here with exact execution latency (ms), arguments, and output payloads.
            </div>
        </div>
    </div>
</div>

<script>
let ws = null;
let micContext = null;
let micStream = null;
let processor = null;
let playContext = null;
let nextPlayTime = 0;
let activeSources = [];

let currentAiCard = null;
let currentUserCard = null;
let pendingToolCards = {};

let totalToolCalls = 0;
let totalToolTimeMs = 0;
let lastTurnTtfb = 0;

const orb = document.getElementById('voiceOrb');
const heroTitle = document.getElementById('heroTitle');
const heroSub = document.getElementById('heroSub');
const connStatus = document.getElementById('connStatus');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const chatStream = document.getElementById('chatStream');
const waterfallList = document.getElementById('waterfallList');

// KPI DOM Elements
const kpiTtfb = document.getElementById('kpiTtfb');
const kpiTtfbSub = document.getElementById('kpiTtfbSub');
const ttfbBadge = document.getElementById('ttfbBadge');
const kpiLlmLatency = document.getElementById('kpiLlmLatency');
const kpiLlmSub = document.getElementById('kpiLlmSub');
const kpiToolLatency = document.getElementById('kpiToolLatency');
const toolBadge = document.getElementById('toolBadge');
const kpiToolName = document.getElementById('kpiToolName');
const kpiAudioStream = document.getElementById('kpiAudioStream');
const kpiTurnAudio = document.getElementById('kpiTurnAudio');
const kpiTurnTotal = document.getElementById('kpiTurnTotal');
const kpiE2eSub = document.getElementById('kpiE2eSub');
let turnCounter = 0;

function clearPlaceholder(container) {
    const ph = container.querySelector('.empty-placeholder');
    if (ph) ph.remove();
}

function createTurnCard(role, speakerLabel) {
    clearPlaceholder(chatStream);
    const card = document.createElement('div');
    card.className = `turn-card ${role === 'user' ? 'turn-user' : 'turn-ai'}`;

    const header = document.createElement('div');
    header.className = 'turn-header';

    const nameSpan = document.createElement('span');
    nameSpan.className = `speaker-name ${role === 'user' ? 'speaker-user' : 'speaker-ai'}`;
    nameSpan.innerText = speakerLabel;

    const metricsDiv = document.createElement('div');
    metricsDiv.className = 'turn-metrics';

    header.appendChild(nameSpan);
    header.appendChild(metricsDiv);

    const bodyDiv = document.createElement('div');
    bodyDiv.className = 'turn-body';
    bodyDiv.style.color = '#F1F5F9';

    card.appendChild(header);
    card.appendChild(bodyDiv);
    chatStream.appendChild(card);
    chatStream.scrollTop = chatStream.scrollHeight;

    return { card, bodyDiv, metricsDiv };
}

function stopAllPlayback() {
    activeSources.forEach(src => {
        try { src.stop(); } catch (e) {}
    });
    activeSources = [];
    if (playContext) {
        nextPlayTime = playContext.currentTime;
    }
}

function playPcm24k(base64Data) {
    if (!playContext) {
        playContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
        nextPlayTime = playContext.currentTime;
    }
    if (playContext.state === 'suspended') {
        playContext.resume();
    }

    const binaryStr = atob(base64Data);
    const len = binaryStr.length;
    const int16 = new Int16Array(len / 2);
    for (let i = 0; i < len; i += 2) {
        int16[i / 2] = binaryStr.charCodeAt(i) | (binaryStr.charCodeAt(i + 1) << 8);
    }

    const float32 = new Float32Array(int16.length);
    let sum = 0;
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768.0;
        sum += Math.abs(float32[i]);
    }

    const avg = sum / float32.length;
    orb.className = 'orb speaking';
    orb.style.transform = `scale(${1 + Math.min(avg * 2.5, 0.32)})`;

    const audioBuffer = playContext.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);

    const source = playContext.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(playContext.destination);

    const now = playContext.currentTime;
    if (nextPlayTime < now) {
        nextPlayTime = now;
    }
    source.start(nextPlayTime);
    nextPlayTime += audioBuffer.duration;
    activeSources.push(source);

    source.onended = () => {
        activeSources = activeSources.filter(s => s !== source);
        if (activeSources.length === 0) {
            orb.className = 'orb active';
            orb.style.transform = 'scale(1)';
            heroSub.innerText = 'Listening continuously • Speak anytime to talk or interrupt';
        }
    };
}

function onVoiceChange() {
    const sel = document.getElementById('voiceSelect');
    const modSel = document.getElementById('modelSelect');
    const selectedVoice = sel.value;
    const selectedModel = modSel ? modSel.value : 'gemini-3.1-flash-live-preview';
    heroTitle.innerText = `Aria • ${selectedModel} • en-IN-${selectedVoice}`;
    if (ws && ws.readyState === WebSocket.OPEN) {
        stopLiveCall();
        setTimeout(() => startLiveCall(), 250);
    }
}

async function startLiveCall() {
    try {
        const selectedVoice = document.getElementById('voiceSelect').value || 'Aoede';
        const selectedModel = document.getElementById('modelSelect') ? document.getElementById('modelSelect').value : 'gemini-3.1-flash-live-preview';
        heroTitle.innerText = `Aria • ${selectedModel} • en-IN-${selectedVoice}`;
        heroSub.innerText = `Connecting to ${selectedModel} (${selectedVoice} • en-IN)...`;
        const parentLoc = (window.parent && window.parent.location && window.parent.location.host)
            ? window.parent.location
            : window.location;
        const isHttps = parentLoc.protocol === 'https:';
        const isDirectLocal8501 = (parentLoc.port === '8501');
        const query = `?model=${encodeURIComponent(selectedModel)}&voice=${encodeURIComponent(selectedVoice)}&lang=en-IN`;
        const wsUrl = isDirectLocal8501
            ? `ws://${parentLoc.hostname || 'localhost'}:8765/${query}`
            : `${isHttps ? 'wss' : 'ws'}://${parentLoc.host}/live-ws/${query}`;
        ws = new WebSocket(wsUrl);

        ws.onopen = async () => {
            connStatus.innerText = `LIVE • ${selectedVoice.toUpperCase()} (en-IN)`;
            connStatus.className = 'status-pill live';
            startBtn.style.display = 'none';
            stopBtn.style.display = 'flex';
            orb.className = 'orb active';
            heroSub.innerText = `Connected (${selectedModel} • en-IN-${selectedVoice})! Speak freely...`;

            micStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            micContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            const source = micContext.createMediaStreamSource(micStream);
            processor = micContext.createScriptProcessor(2048, 1, 1);

            processor.onaudioprocess = (e) => {
                if (!ws || ws.readyState !== WebSocket.OPEN) return;
                const input = e.inputBuffer.getChannelData(0);
                const pcm16 = new Int16Array(input.length);
                let sum = 0;
                for (let i = 0; i < input.length; i++) {
                    const s = Math.max(-1, Math.min(1, input[i]));
                    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                    sum += Math.abs(s);
                }
                const avg = sum / input.length;
                if (avg > 0.035 && activeSources.length === 0) {
                    orb.style.transform = `scale(${1 + Math.min(avg * 2.0, 0.24)})`;
                }
                ws.send(pcm16.buffer);
            };

            source.connect(processor);
            processor.connect(micContext.destination);
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === 'status' && msg.model) {
                heroSub.innerText = `${msg.message} • Speak freely anytime!`;
            }
            else if (msg.type === 'ttfb_metric') {
                lastTurnTtfb = msg.ttfb_ms;
                const llmMs = msg.llm_ttfb_ms !== undefined ? msg.llm_ttfb_ms : msg.ttfb_ms;
                const toolMs = msg.tool_latency_ms || 0;

                kpiTtfb.innerText = msg.ttfb_ms;
                kpiTtfbSub.innerText = toolMs > 0 ? `Includes ${toolMs}ms tool + ${llmMs}ms LLM` : `Direct voice generation`;
                ttfbBadge.innerText = msg.ttfb_ms < 800 ? 'ULTRA FAST' : 'NORMAL';
                ttfbBadge.className = msg.ttfb_ms < 800 ? 'badge-fast' : 'badge-med';

                kpiLlmLatency.innerText = llmMs;
                kpiLlmSub.innerText = toolMs > 0 ? `Post-tool synthesis time` : `Direct neural audio TTFB`;

                if (currentAiCard) {
                    const tag = document.createElement('span');
                    tag.className = 'metric-tag ttfb';
                    tag.innerText = `⚡ TTFB: ${msg.ttfb_ms} ms (LLM: ${llmMs} ms)`;
                    currentAiCard.metricsDiv.appendChild(tag);
                }
            }
            else if (msg.type === 'audio') {
                heroSub.innerText = 'Aria is speaking (speak anytime to interrupt)...';
                playPcm24k(msg.data);
            }
            else if (msg.type === 'interrupted') {
                stopAllPlayback();
                heroSub.innerText = 'Interrupted — listening to you...';
                currentAiCard = null;
            }
            else if (msg.type === 'transcript_user') {
                if (!currentUserCard) {
                    currentUserCard = createTurnCard('user', '👤 Caller (Live Voice)');
                }
                currentUserCard.bodyDiv.innerText += msg.text;
                chatStream.scrollTop = chatStream.scrollHeight;
                currentAiCard = null;
            }
            else if (msg.type === 'transcript_ai') {
                if (!currentAiCard) {
                    currentAiCard = createTurnCard('ai', '🤖 Aria (Smart Voice AI)');
                    if (lastTurnTtfb > 0) {
                        const tag = document.createElement('span');
                        tag.className = 'metric-tag ttfb';
                        tag.innerText = `⚡ TTFB: ${lastTurnTtfb} ms`;
                        currentAiCard.metricsDiv.appendChild(tag);
                    }
                }
                currentAiCard.bodyDiv.innerText += msg.text;
                chatStream.scrollTop = chatStream.scrollHeight;
                currentUserCard = null;
            }
            else if (msg.type === 'tool_start') {
                clearPlaceholder(waterfallList);
                const card = document.createElement('div');
                card.className = 'tool-card';
                card.innerHTML = `
                    <div class="tool-top">
                        <span class="tool-name">⚙️ ${msg.name}</span>
                        <span class="latency-badge" style="background: rgba(245,158,11,0.15); color: #F59E0B;">RUNNING...</span>
                    </div>
                    <div class="tool-section-label">Input Arguments</div>
                    <div class="code-box">${JSON.stringify(msg.args, null, 2)}</div>
                    <div class="tool-output-container"></div>
                `;
                waterfallList.prepend(card);
                pendingToolCards[msg.name] = card;
                currentAiCard = null;
            }
            else if (msg.type === 'tool_result') {
                totalToolCalls += 1;
                totalToolTimeMs += msg.latency_ms;
                const avgMs = Math.round(totalToolTimeMs / totalToolCalls);

                // Update Top KPIs
                kpiToolLatency.innerText = msg.latency_ms;
                kpiToolName.innerText = `${msg.name} • Avg: ${avgMs}ms (${totalToolCalls} calls)`;
                toolBadge.innerText = `${msg.latency_ms} ms`;

                const card = pendingToolCards[msg.name];
                if (card) {
                    card.className = 'tool-card done';
                    const badge = card.querySelector('.latency-badge');
                    if (badge) {
                        badge.style.background = 'rgba(16, 185, 129, 0.16)';
                        badge.style.color = '#10B981';
                        badge.innerText = `⏱️ ${msg.latency_ms} ms`;
                    }
                    const outContainer = card.querySelector('.tool-output-container');
                    if (outContainer) {
                        let summaryHtml = '';
                        if (msg.result && msg.result.rag_summary) {
                            summaryHtml = `<div class="tool-section-label" style="color:#10B981;">Grounded RAG Answer Summary</div>
                                           <div class="code-box" style="border-color:rgba(16,185,129,0.3);">${msg.result.rag_summary}</div>`;
                        } else {
                            summaryHtml = `<div class="tool-section-label">Output Payload</div>
                                           <div class="code-box">${JSON.stringify(msg.result, null, 2)}</div>`;
                        }
                        outContainer.innerHTML = summaryHtml;
                    }
                }
            }
            else if (msg.type === 'turn_complete') {
                turnCounter += 1;
                const e2eMs = msg.e2e_turn_ms || msg.total_turn_ms || 1;
                const ttfbVal = msg.ttfb_ms || lastTurnTtfb || 0;
                const toolVal = msg.tool_latency_ms || 0;
                const llmVal = msg.llm_ttfb_ms !== undefined ? msg.llm_ttfb_ms : Math.max(0, ttfbVal - toolVal);
                const streamVal = msg.audio_stream_ms !== undefined ? msg.audio_stream_ms : Math.max(0, e2eMs - ttfbVal);
                const kb = (msg.audio_bytes / 1024).toFixed(1);
                const audioSec = msg.audio_duration_sec || (msg.audio_bytes / 48000).toFixed(1);

                // Update Top KPIs
                kpiAudioStream.innerText = streamVal;
                kpiTurnAudio.innerText = `${audioSec}s spoken (${kb} KB)`;
                kpiTurnTotal.innerText = e2eMs;
                kpiE2eSub.innerText = `TTFB ${ttfbVal}ms + Stream ${streamVal}ms`;

                if (currentAiCard) {
                    const toolTag = toolVal > 0 ? `<span class="metric-tag" style="color:#F59E0B;">🛠️ Tool: ${toolVal}ms</span>` : '';
                    const streamTag = document.createElement('span');
                    streamTag.className = 'metric-tag';
                    streamTag.innerText = `🔊 Stream: ${streamVal}ms (${audioSec}s)`;
                    currentAiCard.metricsDiv.appendChild(streamTag);

                    const totalTag = document.createElement('span');
                    totalTag.className = 'metric-tag';
                    totalTag.style.color = '#38BDF8';
                    totalTag.innerText = `🏁 E2E: ${e2eMs}ms`;
                    currentAiCard.metricsDiv.appendChild(totalTag);
                }

                // Prepend a visual Turn Latency Breakdown Card in the Waterfall Inspector
                clearPlaceholder(waterfallList);
                const toolPct = Math.min(100, Math.round((toolVal / e2eMs) * 100));
                const llmPct = Math.min(100 - toolPct, Math.round((llmVal / e2eMs) * 100));
                const streamPct = Math.max(5, 100 - toolPct - llmPct);

                const turnBreakdownCard = document.createElement('div');
                turnBreakdownCard.className = 'tool-card';
                turnBreakdownCard.style.borderLeft = '3px solid #38BDF8';
                turnBreakdownCard.innerHTML = `
                    <div class="tool-top">
                        <span class="tool-name" style="color:#38BDF8;">📊 Turn #${turnCounter} E2E Latency Breakdown</span>
                        <span class="latency-badge" style="background:rgba(56,189,248,0.16); color:#38BDF8;">🏁 E2E: ${e2eMs} ms</span>
                    </div>
                    <div style="display:flex; height:10px; border-radius:6px; overflow:hidden; margin:8px 0; background:#1E293B;">
                        ${toolVal > 0 ? `<div style="width:${toolPct}%; background:#F59E0B;" title="Tool Call: ${toolVal}ms"></div>` : ''}
                        <div style="width:${llmPct}%; background:#10B981;" title="LLM Inference: ${llmVal}ms"></div>
                        <div style="width:${streamPct}%; background:#38BDF8;" title="Audio Streaming: ${streamVal}ms"></div>
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:6px; font-size:0.72rem; font-family:'JetBrains Mono',monospace; margin-top:6px;">
                        <div style="background:rgba(245,158,11,0.12); padding:4px 6px; border-radius:6px; color:#FBBF24;">
                            🛠️ Tool: <b>${toolVal}ms</b>
                        </div>
                        <div style="background:rgba(16,185,129,0.12); padding:4px 6px; border-radius:6px; color:#34D399;">
                            🧠 LLM: <b>${llmVal}ms</b>
                        </div>
                        <div style="background:rgba(248,68,100,0.14); padding:4px 6px; border-radius:6px; color:#FB7185;">
                            ⚡ TTFB: <b>${ttfbVal}ms</b>
                        </div>
                        <div style="background:rgba(56,189,248,0.12); padding:4px 6px; border-radius:6px; color:#38BDF8;">
                            🔊 Stream: <b>${streamVal}ms</b>
                        </div>
                    </div>
                `;
                waterfallList.prepend(turnBreakdownCard);

                currentAiCard = null;
                currentUserCard = null;
            }
        };

        ws.onclose = () => {
            stopLiveCall();
        };
    } catch (err) {
        heroSub.innerText = 'Error: ' + err.message;
    }
}

function sendQuickPrompt(text) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
        alert('Please click "Start Hands-Free Call" first so the live WebSocket is active!');
        return;
    }
    stopAllPlayback();
    lastTurnTtfb = 0;
    const userCard = createTurnCard('user', '👤 Caller (Quick Shortcut)');
    userCard.bodyDiv.innerText = text;
    currentAiCard = null;
    currentUserCard = null;
    ws.send(JSON.stringify({ type: 'text_prompt', text: text }));
}

function stopLiveCall() {
    stopAllPlayback();
    if (processor) { processor.disconnect(); processor = null; }
    if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
    if (micContext) { micContext.close(); micContext = null; }
    if (ws) { ws.close(); ws = null; }
    connStatus.innerText = 'DISCONNECTED';
    connStatus.className = 'status-pill';
    startBtn.style.display = 'flex';
    stopBtn.style.display = 'none';
    orb.className = 'orb';
    orb.style.transform = 'scale(1)';
    heroSub.innerText = 'Call ended. Click "Start Hands-Free Call" to reconnect.';
}
</script>
</body>
</html>
"""

components.html(REALTIME_COMMAND_CENTER_HTML, height=685)

# -----------------------------------------------------------------------------
# Bottom Stakeholder & RAG Verification Tabs
# -----------------------------------------------------------------------------
st.markdown("### 🔎 Stakeholder Verification & RAG Knowledge Base Explorer")
tab_rag, tab_bookings, tab_refunds = st.tabs([
    "📚 Vertex AI Search RAG Explorer",
    "🎬 Live Cinema Bookings & Seat Map",
    "💳 Finance & Ops Refund Ledger",
])

with tab_rag:
    col_r1, col_r2 = st.columns([1, 1.3], gap="large")
    with col_r1:
        st.markdown("#### Test Discovery Engine RAG Directly")
        st.caption(
            "Verify answers from the configured Vertex AI Search / Discovery Engine Knowledge Base."
        )
        test_query = st.text_input(
            "Enter any customer support question:",
            value="Transaction was canceled but the seats appear blocked",
        )
        run_rag = st.button("🚀 Query Vertex AI Search RAG", use_container_width=True)

    with col_r2:
        if run_rag:
            import time as _time
            t0 = _time.perf_counter()
            rag_res = search_knowledge_base(test_query)
            elapsed_ms = int((_time.perf_counter() - t0) * 1000)
            if rag_res.get("success"):
                st.success(f"✅ Grounded RAG Answer Retrieved in **{elapsed_ms} ms**")
                st.markdown(f"**AI Summary:**\n\n{rag_res.get('rag_summary')}")
                if rag_res.get("sources"):
                    st.markdown("**Citations & Extractive Answers:**")
                    for idx, src in enumerate(rag_res["sources"], start=1):
                        with st.expander(f"📄 Document [{idx}]: {src.get('title') or src.get('id')}"):
                            if src.get("extractive_answer"):
                                st.markdown(f"**Extractive Answer:**\n> {src['extractive_answer']}")
                            if src.get("snippet"):
                                st.markdown(f"**Snippet:** {src['snippet']}", unsafe_allow_html=True)
            else:
                st.error(f"Error: {rag_res.get('error')}")

with tab_bookings:
    st.markdown(f"#### 📱 BigQuery Indian Mobile Number Booking Database (`{BQ_BOOKINGS_TABLE}`)")
    st.caption(
        "Primary Key: `mobile_number` (10-digit Indian mobile number). Speak any mobile number below to Aria during a live voice call or test directly here."
    )
    col_m1, col_m2 = st.columns([1, 1.4], gap="large")
    with col_m1:
        test_mobile = st.text_input(
            "Enter Indian Mobile Number (10 digits or +91):",
            value="9876543210",
            help="Try: 9876543210, 9811122233, 9900112233, 9820098200, 9711122233, 9123456789, 9988776655, 9654321098",
        )
        lookup_btn = st.button("🔍 Query BigQuery by Mobile Number", use_container_width=True)

    with col_m2:
        if lookup_btn:
            import time as _time
            t0 = _time.perf_counter()
            bq_res = fetch_booking_by_mobile(test_mobile)
            elapsed_ms = int((_time.perf_counter() - t0) * 1000)
            if bq_res.get("found"):
                st.success(f"✅ BigQuery Record Retrieved in **{elapsed_ms} ms** (Primary Key: `{bq_res.get('primary_key_mobile')}`)")
                st.markdown(
                    f"""
                    <div class="ticket-card" style="border-left: 4px solid #38BDF8;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <span style="font-family:'Outfit'; font-weight:700; color:#38BDF8;">📱 +91 {bq_res.get('primary_key_mobile')} • {bq_res.get('booking_id')}</span>
                            <span class="badge-confirmed">{bq_res.get('status')}</span>
                        </div>
                        <div style="font-weight:700; font-size:1.1rem; color:#FFF;">🎬 {bq_res.get('movie_title')} ({bq_res.get('language')} • {bq_res.get('format')})</div>
                        <div style="font-size:0.84rem; color:#94A3B8; margin:4px 0;">📍 {bq_res.get('cinema_name')} • <b>{bq_res.get('screen_audi')}</b></div>
                        <div style="font-size:0.84rem; color:#E2E8F0;">🕒 Show Time: <b>{bq_res.get('showtime')}</b></div>
                        <div style="font-size:0.86rem; color:#10B981; font-weight:600; margin-top:6px;">💺 Seats: {bq_res.get('seat_numbers')}</div>
                        <div style="font-size:0.82rem; color:#CBD5E1; margin-top:4px;">👤 Customer: <b>{bq_res.get('customer_name')}</b> • Paid: {bq_res.get('amount_paid')} via {bq_res.get('payment_method')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.warning(f"⚠️ {bq_res.get('message')}")

    st.markdown(f"##### 📊 All Seeded Indian Mobile Bookings in BigQuery (`{BQ_BOOKINGS_TABLE}`)")
    try:
        from ivr_tools import _BQ_BOOKINGS_CACHE
        cached_bookings = list(_BQ_BOOKINGS_CACHE.values())
        grid_cols = st.columns(4)
        for idx, r in enumerate(cached_bookings):
            with grid_cols[idx % 4]:
                st.markdown(
                    f"""
                    <div class="ticket-card" style="margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                            <span style="font-family:'JetBrains Mono'; font-weight:700; font-size:0.86rem; color:#F84464;">📱 {r.get('primary_key_mobile')}</span>
                            <span class="badge-confirmed">{r.get('status')}</span>
                        </div>
                        <div style="font-weight:700; font-size:0.98rem; color:#FFF;">{r.get('movie_title')}</div>
                        <div style="font-size:0.78rem; color:#38BDF8; font-weight:600;">{r.get('language')} • {r.get('format')}</div>
                        <div style="font-size:0.78rem; color:#94A3B8; margin:4px 0;">📍 {r.get('cinema_name')} ({r.get('screen_audi')})</div>
                        <div style="font-size:0.78rem; color:#E2E8F0;">🕒 {r.get('showtime')}</div>
                        <div style="font-size:0.8rem; color:#10B981; font-weight:600; margin-top:5px;">💺 {r.get('seat_numbers')}</div>
                        <div style="font-size:0.76rem; color:#CBD5E1; margin-top:4px;">👤 {r.get('customer_name')} • {r.get('amount_paid')} • <code>{r.get('booking_id')}</code></div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    except Exception as exc:
        st.error(f"Could not load BigQuery table preview: {exc}")

with tab_refunds:
    if not bms_backend.refund_ledger:
        st.info("No ticket refunds processed yet in this session. Ask Aria to cancel booking `TKT-882190` during the call!")
    else:
        for r_id, rec in bms_backend.refund_ledger.items():
            st.markdown(
                f"""
                <div class="ticket-card" style="border-left: 4px solid #10B981;">
                    <div style="display:flex; justify-content:space-between;">
                        <span style="font-weight:700; color:#10B981;">Refund Ref: {rec.refund_id}</span>
                        <span class="badge-confirmed">REFUNDED • ₹{rec.net_refund_amount:.2f}</span>
                    </div>
                    <div style="font-size:0.84rem; color:#CBD5E1; margin-top:6px;">
                        Booking ID: <b>{rec.booking_id}</b> • Destination: <b>{rec.refund_destination}</b> • Finance Ref: <code>{rec.finance_reference}</code>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
