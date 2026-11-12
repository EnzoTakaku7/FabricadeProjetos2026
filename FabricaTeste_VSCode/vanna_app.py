"""Interface opcional do Vanna 2.x para consultar o SQLite local."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
DB = BASE_DIR / "empresa_teste.db"
load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError(
        "Configure GOOGLE_API_KEY no arquivo .env antes de iniciar o Vanna."
    )
if not DB.exists():
    raise FileNotFoundError(
        "Banco não encontrado. Execute primeiro: python main.py"
    )

from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.core.user import CookieEmailUserResolver
from vanna.integrations.google import GeminiLlmService
from vanna.integrations.sqlite import SqliteRunner
from vanna.integrations.chromadb import ChromaAgentMemory
from vanna.tools import RunSqlTool
from vanna.servers.fastapi import VannaFastAPIServer

llm = GeminiLlmService(
    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    api_key=api_key
)

sql_tool = RunSqlTool(sql_runner=SqliteRunner(database_path=str(DB)))
registry = ToolRegistry()
registry.register_local_tool(sql_tool, access_groups=["admin", "user", "users"])

memory = ChromaAgentMemory(
    collection_name="fabrica_teste_vanna",
    persist_directory=str(BASE_DIR / "chroma_memory")
)

agent = Agent(
    llm_service=llm,
    tool_registry=registry,
    user_resolver=CookieEmailUserResolver(),
    agent_memory=memory
)

if __name__ == "__main__":
    print("Iniciando Vanna. A interface ficará disponível no endereço informado pelo servidor.")
    server = VannaFastAPIServer(agent)
    server.run()
