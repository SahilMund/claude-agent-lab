from claude_agent_lab.config import config
from claude_agent_lab.observability.logger import get_logger

logger = get_logger(__name__)

def get_llm():
  """Return the right LangChain LLM based on config.

  Supported llm.provider values: anthropic, openai, gemini, groq, ollama.
  Each provider reads its API key from its own standard env var
  (ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY, GROQ_API_KEY) unless
  passed explicitly — same pattern the original anthropic/openai branches
  already relied on. Ollama needs no key; it talks to a local server
  (OLLAMA_BASE_URL, default http://localhost:11434). Anything unrecognized
  falls through to openai, matching the source's original fallback.
  """
  provider = config["llm"]["provider"]
  model = config["llm"]["model"]
  logger.info(f"Using LLM provider: {provider}, model: {model}")


  if provider == "anthropic":
      from langchain_anthropic import ChatAnthropic
      return ChatAnthropic(model=model)

  if provider == "gemini":
      from langchain_google_genai import ChatGoogleGenerativeAI
      return ChatGoogleGenerativeAI(model=model)

  if provider == "groq":
      from langchain_groq import ChatGroq
      return ChatGroq(model_name=model)

  if provider == "ollama":
      from langchain_ollama import ChatOllama
      import os
      base_url = os.getenv("OLLAMA_BASE_URL")
      return ChatOllama(model=model, base_url=base_url) if base_url else ChatOllama(model=model)

  from langchain_openai import ChatOpenAI
  return ChatOpenAI(model=model)


def get_embedder():
  """Return the right LangChain embedder based on config."""
  provider = config["embeddings"]["provider"]
  model = config["embeddings"]["model"]
  logger.info(f"Using embeddings provider: {provider}, model: {model}")
  if provider == "huggingface":
      from langchain_huggingface import HuggingFaceEmbeddings
      return HuggingFaceEmbeddings(model_name=model)
  from langchain_openai import OpenAIEmbeddings
  return OpenAIEmbeddings(model=model)
