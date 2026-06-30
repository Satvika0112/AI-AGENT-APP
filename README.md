# Next Best Action Platform

## Team Details

**Team Name:StarGirls**

**Team Members:**

* Bhavya Sree Nuthalapati(23071A05T3)(bhavyasreenuthalapati@gmail.com)
* Sri Vijaya Satvika Appana(23071A67D5)(satvika.appana@googlemail.com)

---

## Project Overview

Next Best Action is an AI-powered decision-support platform for SaaS Customer Success teams. It analyzes customer interactions such as emails, call transcripts, and CSM notes using a multi-agent architecture and Retrieval-Augmented Generation (RAG). The platform identifies customer intent, detects churn risks or upsell opportunities, retrieves relevant knowledge, and recommends the most appropriate next actions with supporting evidence and confidence scores.

Key Features:

* Multi-agent AI workflow (Ingestion, Retrieval, Analysis, Recommendation)
* Retrieval-Augmented Generation (RAG) for grounded responses
* Dynamic planner with rule-based and LLM-based orchestration
* Human-in-the-loop approval before recommendations
* Shared memory to improve future recommendations
* Streamlit dashboard for interactive decision support

---

## GitHub Repository Link

```
https://github.com/Satvika0112/AI-AGENT-APP.git
```

---

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/Satvika0112/AI-AGENT-APP.git
cd AI-AGENT-APP
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

Activate the environment:

**Windows**

```bash
venv\Scripts\activate
```

**macOS/Linux**

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure API Key

Create a `.env` file and add:

```text
GEMINI_API_KEY=your_api_key
```

### 5. Run the application

```bash
streamlit run src/app.py
```

---

## Additional Notes

* Built using Python, Streamlit, Google Gemini, and Retrieval-Augmented Generation (RAG).
* Uses synthetic customer data for demonstration purposes.
* Recommendations are always reviewed by a human before execution.
* The business logic is configurable through `config/domain.yaml`, making the platform reusable across multiple domains.
* Supports evaluation metrics and shared-memory learning for continuous improvement.
