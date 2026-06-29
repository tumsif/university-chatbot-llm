# University Student Support assistant

This is a support chat assistance AI that will help students to ask questions about the university services such as:
- Course registration
- Examination rules
- Library services
- ICT support
- Hostel application
- Fee payment
- Academic calendar
- Student conduct

## Project Focus
To demonstrate how to integrate running local models into an interactive full-stack application that can be easily used by normal users.

## Project Structure
```
support-assistant-llm/
├── backend/
│   ├── main.py            # FastAPI endpoints, logging, and error handling
│   ├── llm_client.py      # Ollama API client & RAG keyword matching
│   ├── config.py          # Port config, model configurations, Ollama URL
│   └── logs/
│       └── app.log        # Interaction log (timestamp, Q&A, errors)
├── web/
│   ├── src/
│   │   ├── app/           # Angular component scripts, html view, styles
│   │   └── styles.css     # Global stylesheets (Tailwind v4)
│   ├── package.json       # Node package manager configurations
│   └── pnpm-lock.yaml     # pnpm package lockfile
├── tests/
│   └── test_api.py        # Backend API testing script
├── docs/
│   └── report.md          # Technical report draft and reflection answers
├── requirements.txt       # Unified Python requirements list
└── README.md              # Project instructions and usage guide (This file)
```

## Setup & Running Instructions

### 1. Requirements & Prerequisites
- Python 3.10+ installed
- [Ollama](https://ollama.com/) installed and running locally

### 2. Environment Configuration
Create and activate a Python virtual environment, then install dependencies:
```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Setup Local LLM Model
Ensure the Ollama service is running, and pull the lightweight `llama3.2:1b` model:

```bash
# Install Ollama (Linux — requires sudo)
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama (usually starts automatically after install)
ollama serve

# Pull the model used by this project
ollama pull llama3.2:1b

# Verify
ollama list
```

If Ollama is not installed, the backend `/health` endpoint will report `llm_connected: false` and the frontend will show an amber "LLM Service Disconnected" banner. Greeting and off-topic responses still work without the model.

### 4. Running the Backend API
Start the FastAPI server on port `8000`:
```bash
uvicorn backend.main:app --port 8000 --reload
```
You can verify the backend endpoints and interact with the Swagger documentation by visiting: [http://localhost:8000/docs](http://localhost:8000/docs)

### 5. Running the Frontend Interface
With the backend running, launch the Angular frontend from the `web` directory in a new terminal tab:
```bash
# Navigate to web directory
cd web

# Start Angular development server
pnpm start
```
The interface will automatically open in your default browser at [http://localhost:4200](http://localhost:4200).

### 6. Automated Testing
Run the API integration script to verify backend endpoints `/health` and `/ask`:
```bash
python3 tests/test_api.py
```

### 7. Demo
![Screenshot 1](DESIGN.png)
