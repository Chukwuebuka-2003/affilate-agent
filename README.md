# AI Affiliate Marketing System

This project implements an AI-powered affiliate marketing system using LangGraph for workflow orchestration and FastAPI for the API server. It includes agents for various tasks such as scouting potential affiliates, outreach, CRM management, commission tracking, payment processing, and performance analysis. The system is designed to be extensible and uses mock data for development and testing purposes.

## Table of Contents

- [Project Overview](#project-overview)
- [Directory Structure](#directory-structure)
- [Core Components](#core-components)
  - [State Management](#state-management)
  - [Agents](#agents)
  - [Orchestrator](#orchestrator)
  - [LangGraph Workflow](#langgraph-workflow)
- [Setup and Installation](#setup-and-installation)
  - [Prerequisites](#prerequisites)
  - [Installation Steps](#installation-steps)
  - [Environment Variables](#environment-variables)
- [Running the System](#running-the-system)
  - [API Server](#api-server)
  - [Example Standalone Run](#example-standalone-run)
- [API Endpoints](#api-endpoints)
- [Mock Data](#mock-data)
- [Future Enhancements](#future-enhancements)

## Project Overview

The system automates various aspects of an affiliate marketing program. It identifies potential affiliates, manages outreach, tracks their performance, calculates commissions, and processes payments. The core logic is built around a stateful graph managed by LangGraph, where different "agents" (specialized Python classes) perform specific tasks.

## Directory Structure

```
affiliate_system/
├── .env                  # Environment variables (OpenAI, Composio API keys)
├── __init__.py
├── api_server.py         # FastAPI application server
├── main.py               # Main script to create LangGraph system and run example
├── orchestrator.py       # MasterOrchestrator class
├── agents/               # Directory for different agent implementations
│   ├── __init__.py
│   ├── social_scout_agent.py
│   ├── outreach_agent.py
│   ├── crm_agent.py
│   ├── commission_agent.py
│   ├── payment_agent.py
│   └── performance_agent.py
├── core/                 # Core data structures and enums
│   ├── __init__.py
│   └── state.py          # Defines AffiliateSystemState, AffiliateLead, etc.
```

## Core Components

### State Management

-   **`core/state.py`**: Defines the Pydantic models for the system's state.
    -   `AffiliateLead`: Represents a potential or active affiliate.
    -   `Commission`: Represents a commission earned.
    -   `LeadStatus`, `CommissionStatus`: Enums for statuses.
    -   `AffiliateSystemState`: The main Pydantic model representing the entire graph's state. It includes lists of prospects, active affiliates, commissions, and other tracking information.

### Agents

Located in the `affiliate_system/agents/` directory, each agent is a Python class responsible for a specific function:

-   **`SocialScoutAgent`**: Identifies potential affiliates from various platforms (currently uses mock data). Scores prospects using an LLM (or mock scores).
-   **`OutreachAgent`**: Manages outreach to selected prospects. Generates personalized messages using an LLM and simulates sending them (currently uses mock logic for sending and conversion).
-   **`CRMAgent`**: Handles CRM-related tasks. Updates lead statuses and moves converted leads to the active affiliates list (currently uses mock logic for CRM sync).
-   **`CommissionAgent`**: Tracks sales (uses mock sales data), calculates commissions based on affiliate performance and sales, and prepares them for payment.
-   **`PaymentAgent`**: Processes payments for approved commissions (currently uses mock logic and simulates interactions with payment processors).
-   **`PerformanceAgent`**: Analyzes campaign performance metrics, detects anomalies, and generates optimization suggestions using an LLM.

### Orchestrator

-   **`orchestrator.py` (`MasterOrchestrator`)**: This class is the central node in the LangGraph. It determines which agent should run next based on the current state of `AffiliateSystemState`.

### LangGraph Workflow

-   **`main.py` (`create_affiliate_system`)**:
    -   Initializes the LLM client (`ChatOpenAI`) and the Composio client (currently falls back to a mock version if `composio_langgraph` or `composio_openai` are not installed).
    -   Initializes the `MasterOrchestrator` and all agents.
    -   Defines the `StateGraph` using `AffiliateSystemState`.
    -   Adds the `MasterOrchestrator` as the primary node.
    -   Sets up conditional edges to loop back to the orchestrator or end the cycle based on `state.current_task`.
    -   Uses `MemorySaver` for in-memory state persistence per campaign/thread.

## Setup and Installation

### Prerequisites

-   Python 3.10+
-   `pip` for package management
-   An OpenAI API key (if using live LLM calls; mock data currently bypasses some LLM calls or uses them for non-critical tasks like scoring).
-   (Optional) A Composio API key if you intend to use real Composio tools.

### Installation Steps

1.  **Clone the repository (if applicable):**
    ```bash
    # git clone <repository_url>
    # cd affiliate_system_project_root
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    A `requirements.txt` file would typically be provided. Based on the codebase, essential libraries include:
    ```bash
    pip install fastapi uvicorn "langchain>=0.1.0" "langgraph>=0.0.30" "langchain-openai>=0.1.0" "pydantic>=2.0" python-dotenv
    # Optional, for live Composio integration:
    # pip install composio-langgraph
    # or
    # pip install composio-openai
    # pip install composio # Base client, used by the mock fallback
    ```
    (Ensure you have the correct versions as per your project's specific needs.)

### Environment Variables

Create a `.env` file in the `affiliate_system` directory:
```env
# affiliate_system/.env

OPENAI_API_KEY="sk-your_openai_api_key"
COMPOSIO_API_KEY="your_composio_api_key" # Optional if not using live Composio tools
```
The system loads these variables using `python-dotenv`.

## Running the System

### API Server

The primary way to interact with the system is through the FastAPI server.

1.  **Navigate to the project root directory** (the directory containing the `affiliate_system` folder).
2.  **Run Uvicorn:**
    ```bash
    uvicorn affiliate_system.api_server:app --reload --port 8000
    ```
    -   `--reload`: Enables auto-reloading on code changes (for development).
    -   `--port 8000`: Specifies the port (default is 8000).

    The API server will be accessible at `http://127.0.0.1:8000`.
    Interactive API documentation (Swagger UI) will be available at `http://127.0.0.1:8000/docs`.

### Example Standalone Run

The `affiliate_system/main.py` script contains an `async def run_example()` function that demonstrates how to create and run the LangGraph system directly in Python. This is useful for testing the core graph logic independently of the API.

To run it:
```bash
python -m affiliate_system.main
```
*(Ensure your current directory allows this module path to be resolved, or run from the project root with adjusted path if necessary.)*

## API Endpoints

The `affiliate_system/api_server.py` defines several endpoints to manage and interact with affiliate campaigns:

-   `GET /`: Basic API information.
-   `POST /campaigns`: Create a new campaign.
-   `GET /campaigns`: List all campaigns and their summary stats.
-   `GET /campaigns/{campaign_id}`: Get detailed information about a specific campaign, including its current state.
-   `POST /campaigns/{campaign_id}/run`: Manually trigger a new processing cycle for a campaign.
-   `GET /campaigns/{campaign_id}/status`: Get the current status and key metrics of a campaign.
-   `POST /campaigns/{campaign_id}/outreach`: Manually set specific leads as outreach targets for a campaign.
-   `GET /campaigns/{campaign_id}/leads`: Get a filtered list of prospects/leads for a campaign.
-   `GET /campaigns/{campaign_id}/affiliates`: Get active affiliates for a campaign.
-   `GET /campaigns/{campaign_id}/commissions`: Get commissions for a campaign, with optional status filtering.

Refer to the `/docs` endpoint for detailed request/response schemas.

## Mock Data

Currently, several agents are configured to use mock data to simulate interactions with external services (like Composio for data fetching or payment processing) or to provide predictable outcomes for testing:

-   **`SocialScoutAgent`**: Fetches mock prospect data and assigns hardcoded scores to known mock prospects.
-   **`OutreachAgent`**: Simulates sending outreach messages and mock-converts specific leads.
-   **`CommissionAgent`**: Fetches mock sales data and simulates payment processing.
-   **`CRMAgent`**: Simulates CRM synchronization.

This allows testing the end-to-end workflow and agent logic without live API calls or dependencies.

## Future Enhancements

-   **Full Composio Integration**: Replace mock Composio calls in agents with actual tool usage via the `ComposioToolSet`.
-   **Database Integration**: Replace in-memory `campaign_registry` and `MemorySaver` with a persistent database solution (e.g., SQL database with `SQLAlchemyCheckpoint`) for robust campaign and state storage.
-   **Advanced LLM Usage**:
    -   Improve LLM prompts for better JSON parsing and more nuanced responses.
    -   Use LLM for more sophisticated decision-making within agents.
-   **Enhanced Error Handling and Retries**: Implement more robust error handling and retry mechanisms for external API calls and agent operations.
-   **User Interface**: Develop a more comprehensive frontend application for managing campaigns and viewing analytics.
-   **Testing**: Add unit and integration tests for agents and the overall workflow.
-   **Configuration Management**: Allow more granular campaign configuration via the API.
-   **Security**: Implement proper authentication and authorization for API endpoints.