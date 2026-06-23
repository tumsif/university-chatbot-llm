import json
import logging
import string
import httpx
from typing import Dict, Any, Optional, Tuple
from backend.config import settings

logger = logging.getLogger("backend_logger")

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
        # Convert to lowercase and strip punctuation
        text = text.lower()
        for char in string.punctuation:
            text = text.replace(char, " ")
        words = text.split()
        
        # Stopwords to filter out
        stopwords = {
            "is", "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", 
            "with", "do", "does", "how", "what", "where", "when", "why", "my", "your", 
            "i", "you", "me", "he", "she", "it", "they", "we", "can", "could", "should", "would"
        }
        return {word for word in words if word not in stopwords}

    def retrieve_context(self, question: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """
        Calculates simple word overlap similarity between the input question and FAQ questions.
        Returns the best matching FAQ item and its score.
        """
        if not self.faq_data:
            return None, 0.0

        question_tokens = self._clean_and_tokenize(question)
        if not question_tokens:
            return None, 0.0

        best_match = None
        best_score = 0.0

        for faq in self.faq_data:
            faq_tokens = self._clean_and_tokenize(faq["question"])
            if not faq_tokens:
                continue
            
            # Intersection score normalized by union size
            intersection = question_tokens.intersection(faq_tokens)
            union = question_tokens.union(faq_tokens)
            score = len(intersection) / len(union) if union else 0.0

            if score > best_score:
                best_score = score
                best_match = faq

        return best_match, best_score

    async def check_ollama_health(self) -> Tuple[bool, str]:
        """
        Verifies if Ollama is running and has the model pulled.
        Returns (is_healthy, message)
        """
        async with httpx.AsyncClient() as client:
            try:
                # 1. Check general connection to Ollama
                response = await client.get(f"{self.base_url}/api/tags", timeout=3.0)
                if response.status_code != 200:
                    return False, f"Ollama returned status code {response.status_code}"
                
                # 2. Check if the specified model is pulled
                models = response.json().get("models", [])
                pulled_models = [m["name"] for m in models]
                
                # Ollama returns full name tag sometimes, e.g. "llama3.2:1b" or "llama3.2:1b" (matching starts_with/exact)
                found = False
                for pm in pulled_models:
                    if self.model in pm or pm in self.model:
                        found = True
                        break
                
                if not found:
                    return False, f"Model '{self.model}' is not pulled on local Ollama service. Installed models: {pulled_models}"
                
                return True, "Ollama is running and model is available."

            except httpx.ConnectError:
                return False, f"Cannot connect to Ollama at {self.base_url}. Ensure the Ollama service is started."
            except Exception as e:
                return False, f"Ollama connection error: {str(e)}"

    async def generate_response(self, question: str, use_rag: bool = True, history: Optional[list] = None) -> Dict[str, Any]:
        """
        Queries the local Ollama LLM and includes RAG context if applicable, along with conversation history.
        """
        # 1. Health check
        is_healthy, health_msg = await self.check_ollama_health()
        if not is_healthy:
            raise ConnectionError(health_msg)

        # 2. Retrieve FAQ context
        context = ""
        faq_category = "General University Support"
        matched_faq = None
        
        if use_rag:
            matched_faq, score = self.retrieve_context(question)
            # Threshold of overlap score
            if matched_faq and score >= 0.15:
                faq_category = matched_faq["category"]
                context = f"Official University Rule/FAQ Context:\n- Topic: {matched_faq['category']}\n- FAQ Question: {matched_faq['question']}\n- FAQ Answer: {matched_faq['answer']}\n\n"
                logger.info(f"RAG Match Found: '{matched_faq['question']}' with similarity score {score:.2f}")
            else:
                logger.info(f"No strong FAQ match found for: '{question}' (Best score: {score:.2f}). Falling back to general knowledge.")

        # 3. Construct System Prompt & Messages
        system_prompt = (
            "You are an official University Student Support Assistant.\n"
            "Your job is to answer student questions accurately, politely, and professionally.\n"
            "Whenever official university rules or context are provided, you MUST use them as your primary source of truth. "
            "If the student asks something outside of the provided context, answer politely based on general academic standards, "
            "but advise them to consult the administration office for definitive guidelines.\n"
            "Keep answers concise and clear."
        )

        messages = [{"role": "system", "content": system_prompt}]

        # Append conversation history
        if history:
            for item in history:
                messages.append({"role": item["role"], "content": item["content"]})

        # Append latest user query with context
        user_content = f"{context}Student Question: {question}\nAssistant Response:"
        messages.append({"role": "user", "content": user_content})

        # 4. Request Ollama API
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False
                    },
                    timeout=60.0
                )
                
                if response.status_code != 200:
                    raise RuntimeError(f"Ollama API returned code {response.status_code}: {response.text}")
                
                result = response.json()
                reply = result["message"]["content"]
                
                return {
                    "answer": reply.strip(),
                    "category": faq_category,
                    "rag_used": matched_faq is not None and context != "",
                    "matched_faq": matched_faq["question"] if matched_faq and context != "" else None
                }

            except httpx.TimeoutException:
                logger.error("Timeout connecting to Ollama generation API.")
                raise TimeoutError("Ollama model took too long to respond.")
            except Exception as e:
                logger.error(f"Error during Ollama query: {str(e)}")
                raise e
