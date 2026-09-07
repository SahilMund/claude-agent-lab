import logging


# Set root logger to WARNING — suppresses noisy third-party library logs (OpenAI, httpcore etc.)
logging.basicConfig(
   level=logging.WARNING,
   format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# langchain-google-genai logs a WARNING per tool, per agent step, for every
# JSON-Schema key it strips before sending a tool's schema to Gemini
# (Gemini's function-calling API rejects `additionalProperties` and
# `$schema`, which Pydantic's schema generator always includes). This is
# expected on every Gemini call with tools bound and carries no actionable
# information — silenced at ERROR rather than left to spam WARNING.
logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)


def get_logger(name: str) -> logging.Logger:
   # Our own loggers run at DEBUG — only third-party libraries are suppressed
   logger = logging.getLogger(name)
   logger.setLevel(logging.DEBUG)
   return logger
