from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

os.getenv("OPENAI_API_KEY")

class LLMManager:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    def invoke(self, prompt: ChatPromptTemplate, parser , **kwargs) -> str:
        messages = prompt.format_messages(**kwargs)
        new_llm = self.llm.with_structured_output(parser)
        response = new_llm.invoke(messages)
        return response
    
