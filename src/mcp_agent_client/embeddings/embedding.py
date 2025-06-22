from langchain_core.embeddings import Embeddings

from mcp_agent_client.llms.google_utils import setup_gemini
from mcp_agent_client.llms.openai_utils import setup_openai


def load_embedding_model(
        model_name: str = "openai",
) -> Embeddings:
    split: list[str] = model_name.split("/")
    model_type = split[0].lower()
    model_name = "/".join(split[1:]) if len(split) > 1 else None

    if model_type == "openai":
        from langchain_openai import OpenAIEmbeddings

        setup_openai()

        return OpenAIEmbeddings(
            model=model_name if model_name else "text-embedding-ada-002",
        )
    elif model_type == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        setup_gemini()

        return GoogleGenerativeAIEmbeddings(
            model=model_name if model_name else "models/embedding-001"
        )

    raise NotImplementedError
