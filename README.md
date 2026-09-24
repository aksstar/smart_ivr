# Smart IVR & Voice Automation (Gemini Live 2.5 Native Audio)

A real-time, full-duplex conversational telephony agent built on the **Google GenAI Multimodal Live API** (`gemini-3.1-flash-live-preview`) with **BigQuery Indian Mobile Number Lookup**, **Vertex AI Search Grounded RAG**, and a **Millisecond-Precision Voice Telemetry Command Center**.

---

## 🎯 Stakeholders & Core Capabilities

| Use Case | Backend / Data Layer | Stakeholder | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **Indian Mobile Booking Lookup** | **BigQuery** (`customer_bookings`) | **Customer Experience** | • Instant lookup using **10-digit Indian mobile number** as primary key (`mobile_number`)<br>• Reads out movie title, language, format (IMAX 3D/Dolby Atmos), showtime, cinema audi, and seat numbers |
| **Grounded FAQ & Policy Search (RAG)** | **Vertex AI Search / Discovery Engine** | **Customer Support & CX** | • Real-time retrieval from official ticketing knowledge base<br>• Answers complex questions (e.g., *Transaction canceled but seats appear blocked*, *Loyalty rewards*, *M-ticket rules*) |
| **Ticket Cancellation & Refund** | Automated refund processing via Voice OTP identity gate | **Finance & Ops** | • Pre-cancellation cutoff check & fee calculation<br>• 4-digit Voice OTP challenge (`request_voice_otp` & `verify_voice_identity`)<br>• Multi-channel refund routing (Original UPI/Card vs. Instant Digital Wallet) |

---

## ⚡ Real-Time Voice AI Telemetry & Latency Architecture

In real-time full-duplex Voice AI systems, measuring total response time alone is misleading because spoken audio streams over several seconds. Our Command Center ([app.py](app.py) + [live_ws_server.py](live_ws_server.py)) decomposes every conversational turn into **5 distinct millisecond-level latency metrics**:

### Conversational Turn Timeline

```text
[Caller Finishes Speaking / Submits Prompt]  (t = turn_start_time)
       │
       ├──► 🛠️ Tool Call Latency (tool_latency_ms)
       │         Executes BigQuery mobile lookup (`fetch_booking_by_mobile`) or
       │         Vertex AI Search RAG (`search_knowledge_base`)
       │
       ├──► 🧠 LLM Model Inference Latency (llm_ttfb_ms)
       │         Pure Gemini 2.5 Flash Native Audio reasoning & synthesis of first audio frame
       │         (t_first_audio - post_tool_start_time)
       ▼
⚡ Perceived TTFB / Time-To-First-Audio Byte (ttfb_ms)  ◄── Speaker begins playing Aria's voice!
       │         (t_first_audio - turn_start_time)
       │
       ├──► 🔊 Audio Streaming Duration (audio_stream_ms)
       │         Streaming 24kHz PCM spoken sentences until final word completes
       │         (t_turn_complete - t_first_audio)
       ▼
🏁 End-to-End (E2E) Turn Latency (e2e_turn_ms)          ◄── Entire turn completed
                 (t_turn_complete - turn_start_time)
```

### Telemetry Metrics Reference Table

| Metric Name | Formula | Target / Benchmark | Definition & Why It Matters |
| :--- | :--- | :--- | :--- |
| **⚡ Perceived TTFB**<br>*(Time-To-First-Audio Byte)* | `t_first_audio − turn_start_time` | **300 – 800 ms** *(Direct)*<br>**800 – 1,500 ms** *(With Tool)* | **The #1 metric for human conversational naturalness.** Measures the silent gap between when the user finishes speaking and when Aria's voice starts coming out of the speaker. Even if an answer takes 6 seconds to speak aloud, a sub-second TTFB makes the AI feel instantaneous. |
| **🧠 LLM Model Inference Latency** | `TTFB − Tool Call Latency`<br>*(or `t_first_audio − post_tool_start`)* | **300 – 650 ms** | Pure **Gemini 2.5 Flash Native Audio** neural reasoning and first-frame audio synthesis time. Isolates Google Gemini's core model speed from external database or network latency. |
| **🛠️ Tool Call Latency** | `t_tool_end − t_tool_start` | **120 – 450 ms** *(BigQuery)*<br>**250 – 600 ms** *(Vertex RAG)* | Exact execution time spent waiting on external backend tools: BigQuery SQL query (`customer_bookings`) or Discovery Engine Search API. When a tool runs, `Perceived TTFB = Tool Call Latency + LLM Inference Latency`. |
| **🔊 Audio Streaming Duration** | `e2e_turn_ms − TTFB` | **2,000 – 7,000 ms**<br>*(Depends on speech length)* | Time spent streaming and speaking the synthesized 24kHz 16-bit PCM audio response from the first audio byte until the final word is spoken. Also tracked as exact spoken duration in seconds (`audio_bytes / 48000`). |
| **🏁 End-to-End (E2E) Turn Latency** | `TTFB + Audio Streaming Duration` | **2,500 – 8,000 ms** | Total wall-clock time from when the caller stops speaking until the entire conversational turn (Tool Calls + LLM Reasoning + Full Audio Stream) is 100% completed. |

---

## 📱 BigQuery Indian Mobile Number Booking Database

Bookings are stored in Google BigQuery table **`customer_bookings`** (configured via `config.json`) with **`mobile_number` (10-digit Indian mobile number)** as the primary lookup key.

### Seeded Indian Mobile Numbers for Live Testing

| Mobile Number (Primary Key) | Customer Name | Booking ID | Movie Name | Language & Format | Seats | Show Time | Cinema & Screen | Amount Paid |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`9876543210`** | Rahul Sharma | `TKT-882190` | **Stree 2: Sarkate Ka Aatang** | Hindi • Dolby Atmos 2D | `D12, D13` (Platinum Recliner) | Today at 07:45 PM | PVR Director's Cut, Ambience Mall, Gurugram (Audi 2) | ₹1,450 |
| **`9811122233`** | Priya Nair | `TKT-774412` | **Kalki 2898 AD** | Telugu • IMAX 3D | `G8, G9, G10` (IMAX Prime) | Tomorrow at 06:30 PM | INOX Megaplex, Inorbit Mall, Malad, Mumbai (IMAX Audi 1) | ₹2,400 |
| **`9900112233`** | Vikramaditya Rao | `TKT-663105` | **Kantara: A Legend Chapter 1** | Kannada • Dolby 7.1 2D | `E5, E6` (Executive) | Today at 08:30 PM | PVR Orion Mall, Rajajinagar, Bengaluru (Audi 4) | ₹1,120 |
| **`9820098200`** | Ananya Iyer | `TKT-551908` | **Jawan** | Hindi • 4DX | `F11, F12` (Prime Motion) | Tomorrow at 06:00 PM | Cinepolis DLF Avenue, Saket, New Delhi (Audi 3) | ₹1,380 |
| **`9711122233`** | Siddharth Malhotra | `TKT-449012` | **Dune: Part Two** | English • IMAX 2D | `H14, H15` (Executive) | Today at 10:15 PM | PVR Select Citywalk, Saket, New Delhi (Audi 1) | ₹1,560 |
| **`9123456789`** | Meera Deshmukh | `TKT-338719` | **3 Idiots (Special Re-Release)** | Hindi • Standard 2D | `C7, C8, C9, C10` (Classic) | Tomorrow at 04:30 PM | PVR Phoenix Marketcity, Viman Nagar, Pune (Audi 6) | ₹960 |
| **`9988776655`** | Arjun Reddy | `TKT-227610` | **Salaar: Part 1 – Ceasefire** | Telugu • Dolby Atmos | `K1, K2` (VIP Lounge) | Today at 09:00 PM | AMB Cinemas, Gachibowli, Hyderabad (Screen 1) | ₹1,200 |
| **`9654321098`** | Rohan Verma | `TKT-119044` | **Leo** | Tamil • IMAX 2D | `J6, J7` (Royal) | Today at 07:00 PM | SPI Palazzo, Nexus Vijaya Mall, Chennai (IMAX Screen) | ₹990 |

To re-seed or reset the BigQuery table at any time:
```bash
python3 setup_bq_bookings.py
```

---

## 🏛️ System Architecture

```text
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │               Browser HTML5 Audio & Real-Time Telemetry Studio                   │
 │   • Continuous 16kHz Mic PCM Capture & Instant Voice Interruption                │
 │   • Indian English (en-IN) Voice Selector (Aoede, Kore, Puck, Fenrir, etc.)      │
 │   • 5-Card Real-Time Latency Strip (TTFB, LLM, Tool, Stream, E2E Turn)           │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │ Full-Duplex WebSocket (`ws://localhost:8765`)
                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────────────┐
 │             Async WebSocket Bridge ([live_ws_server.py](live_ws_server.py))             │
 │   • Bi-directional audio streaming to `gemini-3.1-flash-live-preview`       │
 │   • Millisecond precision timers (`turn_start_time`, `post_tool_start_time`)     │
 └────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │ Autonomous Function Calling
            ┌─────────────────────────────┼─────────────────────────────┐
            ▼                             ▼                             ▼
 ┌──────────────────────┐     ┌─────────────────────────┐   ┌───────────────────────┐
 │   BigQuery Client    │     │  Vertex AI Search RAG   │   │  Ticketing Security   │
 │ `customer_bookings`  │     │  Knowledge Base Engine  │   │  Voice OTP & Refunds  │
 │ Primary Key: Mobile  │     │ Grounded FAQ Retrieval  │   │  Ledger Verification  │
 └──────────────────────┘     └─────────────────────────┘   └───────────────────────┘
```

---

## 📂 Key Files

- [app.py](app.py): Streamlit Real-Time Voice Studio & Telemetry Command Center with 5-metric KPI cards, visual per-turn E2E latency waterfall bars, BigQuery mobile lookup tester, and Vertex AI Search RAG explorer.
- [live_ws_server.py](live_ws_server.py): Full-duplex WebSocket server connecting browser WebAudio directly to `gemini-3.1-flash-live-preview` and computing real-time TTFB, LLM inference, tool call, and E2E turn latencies.
- [ivr_tools.py](ivr_tools.py): Autonomous tools including `fetch_booking_by_mobile` (BigQuery), `search_knowledge_base` (Vertex AI Search RAG), `request_voice_otp`, `verify_voice_identity`, and `process_ticket_cancellation`.
- [mock_ticketing_backend.py](mock_ticketing_backend.py): In-memory backend for Voice OTP identity verification and refund ledger processing.
- [setup_bq_bookings.py](setup_bq_bookings.py): Creates and seeds the BigQuery `customer_bookings` table with Indian mobile numbers.
- [config_loader.py](config_loader.py) & [config.example.json](config.example.json): Configuration loader that reads project ID, location, and resource IDs from the git-ignored `config.json`.

---

## 🚀 Running the Real-Time Voice Studio & Telemetry Console

Copy `config.example.json` to `config.json` (git-ignored) with your GCP project and location, then run:

```bash
SSL_CERT_FILE=$(python3 -m certifi) \
streamlit run app.py --server.port 8501
```

Open **http://localhost:8501** in your browser:
1. Select your preferred **Indian English (`en-IN`) voice** from the top dropdown (`Aoede`, `Kore`, `Leda`, `Puck`, `Charon`, `Fenrir`, etc.).
2. Click **"🟢 Start Hands-Free Call"** and speak naturally (e.g., *"Can you check my movie booking under mobile number 9876543210?"*), or click any one-touch prompt chip.
3. Watch the **5-card Latency KPI Strip** and **Per-Turn E2E Latency Waterfall Breakdown** update live in milliseconds.
