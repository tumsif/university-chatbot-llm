import requests
import json
import sys

BACKEND_URL = "http://localhost:8000"

def test_health():
    print("=== Testing /health endpoint ===")
    try:
        res = requests.get(f"{BACKEND_URL}/health", timeout=5.0)
        print(f"Status Code: {res.status_code}")
        print("Response JSON:")
        print(json.dumps(res.json(), indent=2))
        print("Health Check PASSED.\n")
        return res.json().get("llm_connected", False)
    except Exception as e:
        print(f"Health Check FAILED: {str(e)}\n")
        return False

def test_ask(question: str, label: str = ""):
    title = label or question
    print(f"=== Testing /ask: {title} ===")
    try:
        res = requests.post(
            f"{BACKEND_URL}/ask",
            json={"question": question},
            timeout=65.0
        )
        print(f"Status Code: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            print(f"Category: {data.get('category')}")
            print(f"RAG Used: {data.get('rag_used')}")
            print(f"Answer: {data.get('answer', '')[:200]}...")
            print("Ask Endpoint PASSED.\n")
        else:
            print(f"Response Error: {res.text}")
            print("Ask Endpoint FAILED.\n")
    except Exception as e:
        print(f"Ask Endpoint FAILED: {str(e)}\n")

def test_empty_question():
    print("=== Testing /ask endpoint with empty question (Validation) ===")
    try:
        res = requests.post(
            f"{BACKEND_URL}/ask",
            json={"question": "   "},
            timeout=5.0
        )
        print(f"Status Code: {res.status_code} (Expected: 400)")
        print(f"Response Content: {res.text}")
        if res.status_code == 400:
            print("Empty Question Validation PASSED.\n")
        else:
            print("Empty Question Validation FAILED.\n")
    except Exception as e:
        print(f"Empty Question Validation FAILED: {str(e)}\n")

if __name__ == "__main__":
    print("Starting Automated API Integration Tests...\n")

    llm_connected = test_health()

    # Natural-language university questions (RAG should match)
    test_ask(
        "hey when do i gotta sign up for my courses this semester?",
        "Natural language — course registration"
    )
    test_ask(
        "can i take out more than 3 books from the library as an undergrad?",
        "Natural language — library borrowing"
    )
    test_ask(
        "i was sick and missed my final exam yesterday what should i do",
        "Natural language — missed exam illness"
    )

    # Greeting (handled without LLM)
    test_ask("hello there!", "Greeting")

    # Off-topic (scope guard)
    test_ask(
        "how do i hack into the university grading system",
        "Off-topic — hacking (should decline)"
    )

    # Standard formal queries
    test_ask("When is the deadline to register for classes?")
    test_ask("How many library books can I borrow?")

    test_empty_question()

    if not llm_connected:
        print("NOTE: Ollama was not connected during health check.")
        print("Greeting/off-topic tests still work; LLM answers require: ollama pull llama3.2:1b\n")

    print("Testing Completed.")
