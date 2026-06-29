import json
import logging
import re
import string
import httpx
from typing import Dict, Any, Optional, Tuple, List
from backend.config import settings
from backend.prompts import (
    IMPROVED_SYSTEM_PROMPT,
    GREETING_PATTERNS,
    OFF_TOPIC_KEYWORDS,
)

logger = logging.getLogger("backend_logger")

# Lightweight synonym expansion for retrieval (not sent to the LLM)
SYNONYM_GROUPS = [
    {"register", "registration", "enroll", "enrollment", "signup", "sign"},
    {"exam", "examination", "exams", "test", "tests"},
    {"hostel", "dorm", "dormitory", "accommodation", "room"},
    {"fee", "fees", "tuition", "payment", "pay"},
    {"library", "books", "borrow", "loan"},
    {"wifi", "wi-fi", "internet", "network"},
    {"password", "login", "portal", "account"},
    {"grade", "grading", "gpa", "marks"},
    {"calendar", "semester", "dates", "schedule"},
]


class LLMClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.llm_model
        self.faq_data = self._load_faq_data()

    def _load_faq_data(self) -> list:
        try:
            with open(settings.faq_data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading FAQ data: {str(e)}")
            return []

    def _clean_and_tokenize(self, text: str) -> set:
        text = text.lower()
        for char in string.punctuation:
            text = text.replace(char, " ")
        words = text.split()

        stopwords = {
            "is", "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of",
            "with", "do", "does", "how", "what", "where", "when", "why", "my", "your",
            "i", "you", "me", "he", "she", "it", "they", "we", "can", "could", "should",
            "would", "am", "are", "was", "were", "be", "been", "being", "have", "has",
            "had", "that", "this", "there", "from", "about", "into", "any", "all", "some",
        }
        tokens = {word for word in words if word not in stopwords and len(word) > 1}
        return self._expand_synonyms(tokens)

    def _expand_synonyms(self, tokens: set) -> set:
        expanded = set(tokens)
        for group in SYNONYM_GROUPS:
            if tokens.intersection(group):
                expanded.update(group)
        return expanded

    def _faq_search_texts(self, faq: Dict[str, Any]) -> List[str]:
        texts = [faq.get("question", "")]
        texts.extend(faq.get("aliases", []))
        texts.extend(faq.get("keywords", []))
        return [t for t in texts if t]

    def retrieve_context(self, question: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Hybrid retrieval: Jaccard overlap on question + aliases + keywords,
        with a bonus when multiple keyword fields match.
        """
        if not self.faq_data:
            return None, 0.0

        question_tokens = self._clean_and_tokenize(question)
        if not question_tokens:
            return None, 0.0

        best_match = None
        best_score = 0.0

        for faq in self.faq_data:
            field_scores = []
            for text in self._faq_search_texts(faq):
                faq_tokens = self._clean_and_tokenize(text)
                if not faq_tokens:
                    continue
                intersection = question_tokens.intersection(faq_tokens)
                union = question_tokens.union(faq_tokens)
                jaccard = len(intersection) / len(union) if union else 0.0
                # Partial credit when user tokens are mostly contained in FAQ tokens
                recall = len(intersection) / len(question_tokens) if question_tokens else 0.0
                field_scores.append(max(jaccard, recall * 0.85))

            if not field_scores:
                continue

            score = max(field_scores)
            # Bonus if aliases/keywords also hit
            if len([s for s in field_scores if s >= 0.2]) >= 2:
                score = min(1.0, score + 0.08)

            if score > best_score:
                best_score = score
                best_match = faq

        return best_match, best_score

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.lower().strip())

    def _is_greeting(self, question: str) -> bool:
        q = self._normalize(question)
        if len(q.split()) > 8:
            return False
        return any(
            q == p or q.startswith(p + " ") or q.startswith(p + "!") or q.startswith(p + ",")
            for p in GREETING_PATTERNS
        )

    def _is_off_topic(self, question: str) -> bool:
        q = self._normalize(question)
        return any(kw in q for kw in OFF_TOPIC_KEYWORDS)

    def _greeting_reply(self, question: str) -> str:
        q = self._normalize(question)
        if any(w in q for w in ("thank", "thanks", "bye", "goodbye", "see you")):
            if "bye" in q or "goodbye" in q or "see you" in q:
                return (
                    "Goodbye! Feel free to return anytime you need help with course registration, "
                    "exams, library, ICT, hostels, fees, or other university services."
                )
            return "You're welcome! Let me know if you have any other university-related questions."

        return (
            "Hello! I'm UniSupport AI, your University Student Support Assistant. "
            "I can help with course registration, examinations, the library, ICT support, "
            "hostels, fees, the academic calendar, and student conduct. How can I help you today?"
        )

    def _off_topic_reply(self) -> str:
        return (
            "I'm only able to assist with official university student services such as registration, "
            "examinations, library access, ICT support, hostels, fees, the academic calendar, and "
            "student conduct. I cannot help with hacking, illegal activity, or topics outside this scope. "
            "Please ask a university-related question or contact the Registry for other matters."
        )

    async def check_ollama_health(self) -> Tuple[bool, str]:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.base_url}/api/tags", timeout=3.0)
                if response.status_code != 200:
                    return False, f"Ollama returned status code {response.status_code}"

                models = response.json().get("models", [])
                pulled_models = [m["name"] for m in models]

                found = any(self.model in pm or pm in self.model for pm in pulled_models)
                if not found:
                    return (
                        False,
                        f"Model '{self.model}' is not pulled on local Ollama service. "
                        f"Installed models: {pulled_models}",
                    )

                return True, "Ollama is running and model is available."

            except httpx.ConnectError:
                return False, f"Cannot connect to Ollama at {self.base_url}. Ensure the Ollama service is started."
            except Exception as e:
                return False, f"Ollama connection error: {str(e)}"

    async def generate_response(
        self,
        question: str,
        use_rag: bool = True,
        history: Optional[list] = None,
    ) -> Dict[str, Any]:
        # Fast-path: greetings and obvious off-topic (no LLM call)
        if self._is_greeting(question):
            return {
                "answer": self._greeting_reply(question),
                "category": "Greeting",
                "rag_used": False,
                "matched_faq": None,
            }

        if self._is_off_topic(question):
            return {
                "answer": self._off_topic_reply(),
                "category": "Out of Scope",
                "rag_used": False,
                "matched_faq": None,
            }

        is_healthy, health_msg = await self.check_ollama_health()
        if not is_healthy:
            # Fallback: return FAQ answer directly when retrieval is confident
            if use_rag:
                matched_faq, rag_score = self.retrieve_context(question)
                if matched_faq and rag_score >= 0.12:
                    logger.warning(
                        f"Ollama unavailable; serving FAQ fallback for '{matched_faq['question']}'"
                    )
                    return {
                        "answer": matched_faq["answer"],
                        "category": matched_faq["category"],
                        "rag_used": True,
                        "matched_faq": matched_faq["question"],
                    }
            raise ConnectionError(health_msg)

        context = ""
        faq_category = "General University Support"
        matched_faq = None
        rag_score = 0.0

        if use_rag:
            matched_faq, rag_score = self.retrieve_context(question)
            if matched_faq and rag_score >= 0.12:
                faq_category = matched_faq["category"]
                context = (
                    f"Official University FAQ (use as source of truth):\n"
                    f"Topic: {matched_faq['category']}\n"
                    f"Question: {matched_faq['question']}\n"
                    f"Official Answer: {matched_faq['answer']}\n\n"
                )
                logger.info(
                    f"RAG Match: '{matched_faq['question']}' score={rag_score:.2f}"
                )
            else:
                logger.info(
                    f"No strong FAQ match for: '{question}' (best score: {rag_score:.2f})"
                )

        system_prompt = IMPROVED_SYSTEM_PROMPT
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for item in history[-10:]:
                messages.append({"role": item["role"], "content": item["content"]})

        user_content = question
        if context:
            user_content = f"{context}Student Question: {question}"
        else:
            user_content = (
                f"No specific FAQ was retrieved for this question. "
                f"If it is about university services, answer briefly and suggest contacting the Registry. "
                f"If it is outside university scope, politely decline.\n\n"
                f"Student Question: {question}"
            )

        messages.append({"role": "user", "content": user_content})

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": 0.3, "num_predict": 256},
                    },
                    timeout=60.0,
                )

                if response.status_code != 200:
                    raise RuntimeError(
                        f"Ollama API returned code {response.status_code}: {response.text}"
                    )

                result = response.json()
                reply = result["message"]["content"]

                return {
                    "answer": reply.strip(),
                    "category": faq_category,
                    "rag_used": matched_faq is not None and context != "",
                    "matched_faq": matched_faq["question"] if matched_faq and context else None,
                }

            except httpx.TimeoutException:
                logger.error("Timeout connecting to Ollama generation API.")
                raise TimeoutError("Ollama model took too long to respond.")
            except Exception as e:
                logger.error(f"Error during Ollama query: {str(e)}")
                raise e
