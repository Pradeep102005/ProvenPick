import os
import asyncio
import numpy as np
import structlog
from lightrag import LightRAG
from lightrag.utils import wrap_embedding_func_with_attrs

logger = structlog.get_logger()

# ─────────────────────────────────────────────────────────────────────────────
# Eager/Defensive Importing for Gemini LLM and Embeddings in LightRAG
# ─────────────────────────────────────────────────────────────────────────────
try:
    # Try importing from standard LightRAG package paths
    from lightrag.llm.gemini import gemini_model_complete, gemini_embed
    
    async def llm_model_func(prompt: str, system_prompt: str = None, history_messages: list = [], **kwargs) -> str:
        api_key = os.environ.get("GEMINI_API_KEY")
        model_name = kwargs.pop("model_name", "gemini-2.5-flash")
        if not model_name.startswith("gemini"):
            model_name = "gemini-2.5-flash"
        # Rate limit protection for free-tier API: space out requests
        await asyncio.sleep(1.5)
        return await gemini_model_complete(
            prompt,
            system_prompt=system_prompt,
            history_messages=history_messages,
            api_key=api_key,
            model_name=model_name,
            **kwargs
        )

    logger.info("Successfully imported LightRAG native Gemini LLM completion services.")

except ImportError:
    # Fallback to direct google-generativeai wrappers if LightRAG imports fail
    logger.warn("LightRAG native Gemini imports failed. Falling back to google-generativeai direct wrappers.")
    import google.generativeai as genai

    async def llm_model_func(prompt: str, system_prompt: str = None, history_messages: list = [], **kwargs) -> str:
        api_key = os.environ.get("GEMINI_API_KEY")
        genai.configure(api_key=api_key)
        model_name = kwargs.pop("model_name", "gemini-2.5-flash")
        if not model_name.startswith("gemini"):
            model_name = "gemini-2.5-flash"
        
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt
        )
        
        contents = []
        for msg in history_messages:
            contents.append({"role": msg["role"], "parts": [msg["content"]]})
        contents.append({"role": "user", "parts": [prompt]})
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: model.generate_content(contents)
        )
        return response.text

@wrap_embedding_func_with_attrs(
    embedding_dim=768,
    max_token_size=2048
)
async def embedding_func(texts: list[str]) -> np.ndarray:
    """
    Unified embedding function using google.genai Client and models/gemini-embedding-001
    truncated to 768 dimensions using output_dimensionality configuration.
    """
    from google import genai
    from google.genai import types
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    loop = asyncio.get_event_loop()
    
    def call_api():
        res = client.models.embed_content(
            model="models/gemini-embedding-001",
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        return [e.values for e in res.embeddings]
        
    embeddings = await loop.run_in_executor(None, call_api)
    return np.array(embeddings)

# ─────────────────────────────────────────────────────────────────────────────
# LightRAG Class Instantiation and Setup
# ─────────────────────────────────────────────────────────────────────────────

# Create local storage directory for LightRAG cache if not exists
WORKING_DIR = os.path.join(os.path.dirname(__file__), "../../rag_storage")
os.makedirs(WORKING_DIR, exist_ok=True)

class LightRAGManager:
    """
    Manages the lifecycle and connection of the LightRAG instance
    connected to the Neo4j database.
    """
    def __init__(self):
        self.rag = None

    async def get_rag_instance(self) -> LightRAG:
        """
        Retrieves the initialized LightRAG instance.
        Establishes database connection asynchronously.
        """
        if self.rag is not None:
            return self.rag

        # Verify Neo4j env variables are present (used by LightRAG Neo4JStorage internally)
        os.environ["NEO4J_URI"] = os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        os.environ["NEO4J_USERNAME"] = os.environ.get("NEO4J_USERNAME", "neo4j")
        os.environ["NEO4J_PASSWORD"] = os.environ.get("NEO4J_PASSWORD", "provenpick123")
        os.environ["NEO4J_DATABASE"] = os.environ.get("NEO4J_DATABASE", "neo4j")
        
        logger.info("Initializing LightRAG with Neo4JStorage...", uri=os.environ["NEO4J_URI"])
        
        self.rag = LightRAG(
            working_dir=WORKING_DIR,
            llm_model_func=llm_model_func,
            embedding_func=embedding_func,
            graph_storage="Neo4JStorage",
            llm_model_name="gemini-2.5-flash"
        )
        
        # Asynchronously connect and verify Neo4j storage tables/indexes
        await self.rag.initialize_storages()
        logger.info("LightRAG Neo4JStorage successfully initialized.")
        return self.rag

# Singleton manager instance
lightrag_manager = LightRAGManager()
