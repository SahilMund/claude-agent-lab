from langchain.tools import tool


from claude_agent_lab.context.retrievers.factory import get_retriever
from claude_agent_lab.memory.long_term import recall as recall_facts, remember as remember_fact
from claude_agent_lab.observability.logger import get_logger


logger = get_logger(__name__)


@tool
def search_codebase(query: str) -> str:
   """
   Search the codebase for relevant classes, functions or logic.
   Use this tool whenever you need to find code related to a question.
   """
   logger.info(f"Tool called: search_codebase with query: {query}")
   retrieve = get_retriever()
   chunks = retrieve(query, k=5)
   if not chunks:
       return "No relevant code found."


   results = []
   for chunk in chunks:
       results.append(
           f"File: {chunk['source']} (lines {chunk['start_line']}-{chunk['end_line']})\n"
           f"Type: {chunk['type']} — {chunk['name']}\n"
           f"Code:\n{chunk['content']}\n"
       )
   return "\n---\n".join(results)


@tool
def remember(fact: str, category: str = "general") -> str:
   """
   Save a durable fact or preference that should be remembered in every
   future session, not just this one — e.g. a coding-style preference the
   user states, a project convention, a correction to something you got
   wrong. Do not use this for one-off details only relevant to this turn.
   """
   logger.info(f"Tool called: remember (category={category}): {fact}")
   return remember_fact(fact, category=category)


@tool
def recall(query: str) -> str:
   """
   Look up previously saved long-term facts/preferences relevant to a query.
   Use this before answering questions where a past preference, correction,
   or project convention might apply — it searches across every past
   session, not just the current one.
   """
   logger.info(f"Tool called: recall with query: {query}")
   facts = recall_facts(query, k=3)
   if not facts:
       return "No relevant long-term facts found."

   return "\n".join(
       f"- {f['fact']} (category: {f['category']}, saved: {f['created_at']})"
       for f in facts
   )
