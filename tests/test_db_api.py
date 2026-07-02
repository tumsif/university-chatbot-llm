import os
import unittest
import shutil
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Setup temp SQLite db path
TEST_DB_FILE = "./test_temp.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

# Force database URL in settings
os.environ["APP_DATABASE_URL"] = TEST_DATABASE_URL

from backend.main import app, Base, get_db
import backend.main as main_mod

# Mock client for LLM interaction
class MockLLMClient:
    async def check_ollama_health(self):
        return True, "Mock Ollama running"

    def faq_status(self):
        return {"faq_entries_loaded": 19, "faq_file": "mock", "faq_last_modified": None}

    async def generate_response(self, question, use_rag=True, history=None, document_content=None, document_name=None):
        if document_content:
            return {
                "answer": f"Mock document answer to: {question}",
                "category": "Document Q&A",
                "rag_used": True,
                "matched_faq": document_name or "test.md",
                "document_used": True,
            }
        return {
            "answer": f"Mock answer to: {question}",
            "category": "Mock Category",
            "rag_used": True,
            "matched_faq": "Mock FAQ Question",
            "document_used": False,
        }

class TestDatabaseAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Inject Mock LLM Client
        cls.original_llm_client = main_mod.llm_client
        main_mod.llm_client = MockLLMClient()
        
        # Setup testing SQLite DB
        cls.engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
        cls.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        
        # Override get_db dependency in the FastAPI app
        def override_get_db():
            db = cls.TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()
                
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        # Restore LLM client and clean up overrides
        main_mod.llm_client = cls.original_llm_client
        app.dependency_overrides.clear()
        
        # Remove the temporary test database file if it exists
        if os.path.exists(TEST_DB_FILE):
            try:
                os.remove(TEST_DB_FILE)
            except Exception as e:
                print(f"Error cleaning up test db file: {e}")

    def setUp(self):
        # Recreate tables before each test to ensure a clean state
        Base.metadata.drop_all(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

    def _register_and_login(self, email="student@udsm.ac.tz", password="secret12", full_name="Test Student"):
        response = self.client.post(
            "/auth/register",
            json={"email": email, "password": password, "full_name": full_name},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        return data["access_token"]

    def _auth_headers(self, token: str):
        return {"Authorization": f"Bearer {token}"}

    def test_auth_register_and_login(self):
        response = self.client.post(
            "/auth/register",
            json={
                "email": "alice@udsm.ac.tz",
                "password": "password1",
                "full_name": "Alice Student",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())
        self.assertEqual(response.json()["user"]["email"], "alice@udsm.ac.tz")

        response = self.client.post(
            "/auth/login",
            json={"email": "alice@udsm.ac.tz", "password": "password1"},
        )
        self.assertEqual(response.status_code, 200)
        token = response.json()["access_token"]

        response = self.client.get("/auth/me", headers=self._auth_headers(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["full_name"], "Alice Student")

    def test_sessions_require_auth(self):
        response = self.client.get("/sessions")
        self.assertEqual(response.status_code, 401)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["llm_connected"])

    def test_session_lifecycle(self):
        token = self._register_and_login()
        headers = self._auth_headers(token)

        # 1. Create session
        response = self.client.post("/sessions", json={"title": "Test Chat Thread"}, headers=headers)
        self.assertEqual(response.status_code, 200)
        session_data = response.json()
        session_id = session_data["id"]
        self.assertEqual(session_data["title"], "Test Chat Thread")
        
        # 2. List sessions
        response = self.client.get("/sessions", headers=headers)
        self.assertEqual(response.status_code, 200)
        sessions = response.json()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["id"], session_id)
        
        # 3. Post question
        response = self.client.post(
            "/ask",
            json={"question": "What is the library hours?", "session_id": session_id},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        ask_data = response.json()
        self.assertEqual(ask_data["session_id"], session_id)
        self.assertIsNotNone(ask_data["question_id"])
        self.assertIsNotNone(ask_data["answer_id"])
        
        # 4. Fetch messages
        response = self.client.get(f"/sessions/{session_id}/messages", headers=headers)
        self.assertEqual(response.status_code, 200)
        messages = response.json()
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
        self.assertEqual(messages[0]["content"], "What is the library hours?")
        self.assertEqual(messages[1]["role"], "assistant")
        self.assertEqual(messages[1]["content"], "Mock answer to: What is the library hours?")
        
        # 5. Rate assistant response
        msg_id = ask_data["answer_id"]
        response = self.client.post(f"/messages/{msg_id}/rate", json={"rating": "Good"}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")
        
        # Verify rating updated in database
        response = self.client.get(f"/sessions/{session_id}/messages", headers=headers)
        messages = response.json()
        self.assertEqual(messages[1]["rating"], "Good")

        # 6. Delete session
        response = self.client.delete(f"/sessions/{session_id}", headers=headers)
        self.assertEqual(response.status_code, 200)
        
        # Verify deletion cascades to session and lists empty
        response = self.client.get("/sessions", headers=headers)
        self.assertEqual(len(response.json()), 0)

    def test_auto_session_creation(self):
        token = self._register_and_login(email="bob@udsm.ac.tz")
        headers = self._auth_headers(token)

        # Asking question without session ID should create session automatically using truncated query as title
        question = "How do I register for classes next fall semester?"
        response = self.client.post("/ask", json={"question": question}, headers=headers)
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        session_id = data["session_id"]
        
        response = self.client.get("/sessions", headers=headers)
        sessions = response.json()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["id"], session_id)
        self.assertEqual(sessions[0]["title"], "How do I register for classes next fall ...")

    def test_document_upload_and_ask(self):
        token = self._register_and_login(email="doc@udsm.ac.tz")
        headers = self._auth_headers(token)

        content = (
            "# Hostel Policy\n\n"
            "First-year students must apply via ARIS before 15 August.\n"
            "Hostel fees are paid through GePG control numbers."
        )
        response = self.client.post(
            "/documents/upload",
            headers=headers,
            files={"file": ("hostel-policy.md", content, "text/markdown")},
        )
        self.assertEqual(response.status_code, 200)
        doc = response.json()
        self.assertEqual(doc["filename"], "hostel-policy.md")
        doc_id = doc["id"]

        response = self.client.post(
            "/ask",
            json={
                "question": "When must first-year students apply for hostel?",
                "document_id": doc_id,
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["document_used"])
        self.assertEqual(data["category"], "Document Q&A")

        response = self.client.get("/documents", headers=headers)
        self.assertEqual(len(response.json()), 1)

        response = self.client.delete(f"/documents/{doc_id}", headers=headers)
        self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
