# SentinelLM: AI Agent Observability & Guardrails

SentinelLM is a production-grade observability system for AI Agents, designed to detect silent failures like infinite loops, token runaways, and latency regressions. It leverages **Datadog Metrics, Monitors, and Incidents** to provide a complete safety layer for autonomous LLM systems.

## 🚀 Quick Start

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration:**
    *   Ensure `.env` has Confluent Cloud, Datadog (`DD_API_KEY`, `DD_SITE`), Gemini, and ElevenLabs credentials.

3.  **Run the Full Pipeline:**
    ```bash
    ./run_demo.sh
    ```

## 📊 Observability Strategy

SentinelLM moves beyond simple logging to a **Metrics-First** approach.

### Signals Collected
We emit custom metrics via the Datadog API (`/api/v1/series`):

*   `sentinellm.token.count`: Total tokens consumed per request.
*   `sentinellm.token.velocity`: Tokens generated per second (detects runaways).
*   `sentinellm.agent.loop.count`: Recursion depth of agent steps.
*   `sentinellm.llm.latency_ms`: End-to-end request latency.
*   `sentinellm.request.error`: Count of failed or anomalous requests.

**Tags:** `agent_id`, `model`, `graph_node`, `deployment_version`.

### Detection Rules (Monitors)
We have defined 3 high-signal detection rules (JSON in `datadog_assets/monitors.json`):

1.  **Agent Loop Detection:** Triggers if `sentinellm.agent.loop.count > 50`. Catches agents stuck in recursive reasoning loops.
2.  **Token Runaway:** Triggers if `sentinellm.token.velocity > 1000`. Identifies prompt injection or infinite generation bugs.
3.  **Latency Regression:** Triggers if `p95 latency > 2000ms`. Detects performance degradation after deployments.

### Incident Management
Each monitor is configured to auto-create a Datadog Incident.
*   **Action:** Gemini 3 Flash analyzes the anomaly and attaches a root cause hypothesis to the incident.
*   **Alert:** ElevenLabs broadcasts a voice summary to the operations center.

## 🛠️ Datadog Assets

All configuration is version-controlled in `datadog_assets/`:

*   **Dashboard:** `SentinelLM – LLM Production Health` (`dashboard.json`)
    *   *Sections:* Application Health, Agent Behavior, Detection & Action.
*   **Monitors:** `monitors.json`
*   **SLOs:** `slos.json` (Latency & Error Rate)

## 🚦 Traffic Generator

Use the included script to simulate production scenarios and trigger incidents:

```bash
# Normal Traffic
python scripts/traffic_generator.py normal

# Trigger Incident #1: Infinite Loop
python scripts/traffic_generator.py loop

# Trigger Incident #2: Token Runaway
python scripts/traffic_generator.py spike

# Trigger Incident #3: Latency Regression
python scripts/traffic_generator.py latency
```

## 🏗️ Architecture

- **Kafka (Confluent Cloud):** Event streaming backbone.
- **Sentinel Engine:** Consumes events, calculates metrics, and pushes to Datadog.
- **Streamlit:** Live visualizer for the hackathon demo.
- **Datadog:** The single pane of glass for health, alerts, and incidents.
