# Architecture

## Overview

The **Next Best Action Platform** is an agentic AI system designed to help Customer Success teams make consistent, evidence-based decisions. It combines Retrieval-Augmented Generation (RAG), specialized AI agents, and a planner/orchestrator to analyze customer interactions and recommend the next best action with supporting evidence.

---

## High-Level Architecture

```
                  +----------------------+
                  |   Streamlit UI       |
                  | (Human in the Loop)  |
                  +----------+-----------+
                             |
                             v
                 +------------------------+
                 |      Planner Agent     |
                 |   Sense → Plan → Act   |
                 +-----------+------------+
                             |
        +--------------------+--------------------+
        |                    |                    |
        v                    v                    v
 +---------------+   +----------------+   +------------------+
 | Ingestion     |   | Retrieval(RAG) |   | Recommendation   |
 | Agent         |   | Agent          |   | Agent            |
 +---------------+   +----------------+   +------------------+
        |                    |                    |
        +--------------------+--------------------+
                             |
                             v
                   +----------------------+
                   | Shared Services      |
                   | LLM • Memory • Config|
                   +----------+-----------+
                              |
                              v
                 +---------------------------+
                 | Data & Knowledge Sources  |
                 | Customers, Playbooks,     |
                 | Memory, Cache             |
                 +---------------------------+
                              |
                              v
                     Google Gemini API
```

---

## System Components

### 1. User Interfaces

The platform supports multiple entry points:

* **Streamlit UI** – Human-in-the-loop interface where users can accept, edit, or reject recommendations.
* **CLI** – Runs the pipeline and records decisions.
* **Evaluation Page** – Measures decision quality against a golden dataset.

---

### 2. Planner (Orchestrator)

The Planner is the central controller of the platform.

It follows three stages:

1. **Sense**

   * Processes raw customer interactions.
   * Converts unstructured input into structured context.

2. **Plan**

   * Applies deterministic business rules.
   * If required, invokes the LLM to determine which specialist agents should execute.
   * Repairs dependencies and execution order before dispatching.

3. **Act**

   * Executes the selected agents.
   * Collects outputs into a decision packet.
   * Records the final recommendation for future learning.

---

### 3. Specialist Agents

#### Ingestion Agent

Transforms raw customer conversations into structured customer information.

#### Retrieval Agent (RAG)

Performs semantic similarity search over the knowledge base using embeddings to retrieve relevant playbooks and documentation.

#### Analysis Agent

Evaluates customer health, identifies risks, detects missing information, and gathers supporting evidence.

#### Recommendation Agent

Generates ranked Next Best Actions along with confidence scores and supporting reasoning.

---

## Shared Services

### LLM Service

Uses **Google Gemini 2.5 Flash** for reasoning and response generation.

### Memory Service

Stores previous decision packets and retrieves similar historical cases to improve recommendations.

### Configuration

Business rules and domain-specific settings are maintained separately to simplify customization.

### Metrics

Evaluates recommendation quality using a golden dataset and scoring framework.

---

## Data Storage

The platform maintains lightweight storage using JSON and Markdown files.

* Customer profiles
* Customer interaction history
* Knowledge base (playbooks)
* Decision memory
* Cached decision packets

---

## External Services

The system integrates with:

* **Google Gemini 2.5 Flash** for conversational reasoning.
* **Gemini Embedding Model** for semantic retrieval.

Communication with external APIs is performed securely over HTTPS.

---

## Key Design Decisions

### Agent-Based Architecture

Each specialist agent is responsible for a single task, improving modularity, maintainability, and scalability.

### Planner-Orchestrated Workflow

A centralized planner dynamically decides which agents should execute, reducing unnecessary computation.

### Retrieval-Augmented Generation (RAG)

Recommendations are grounded in organizational knowledge instead of relying solely on LLM memory, improving accuracy and explainability.

### Human-in-the-Loop

Users can review, modify, or reject AI-generated recommendations before final execution, ensuring trust and accountability.

### Memory-Based Learning

Historical decisions are stored and reused to provide context-aware recommendations over time.

### Modular Configuration

Business rules are separated from implementation, allowing organizations to adapt the system without modifying core code.

---

## End-to-End Workflow

1. User submits a customer interaction.
2. Planner begins the **Sense → Plan → Act** pipeline.
3. Ingestion Agent structures the input.
4. Retrieval Agent gathers relevant organizational knowledge.
5. Analysis Agent identifies customer risks and opportunities.
6. Recommendation Agent generates Next Best Actions.
7. The Streamlit UI presents recommendations for human review.
8. The accepted decision is stored in memory and cache for future learning.
