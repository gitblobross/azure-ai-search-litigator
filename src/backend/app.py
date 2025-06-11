import logging
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from rich.logging import RichHandler
from openai import AsyncAzureOpenAI
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents.aio import SearchClient
from azure.search.documents.indexes.aio import SearchIndexClient
try:
    from azure.search.documents.agent.aio import KnowledgeAgentRetrievalClient
    AGENT_AVAILABLE = True
except ImportError:
    KnowledgeAgentRetrievalClient = None
    AGENT_AVAILABLE = False
from azure.core.pipeline.policies import UserAgentPolicy
from azure.storage.blob.aio import BlobServiceClient
from src.backend.search_grounding import SearchGroundingRetriever
from src.backend.knowledge_agent import KnowledgeAgentGrounding
from src.backend.constants import USER_AGENT
from src.backend.multimodalrag import MultimodalRag
from src.backend.data_model import DocumentPerChunkDataModel
from src.backend.citation_file_handler import CitationFilesHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

def inject_clients():
    tokenCredential = DefaultAzureCredential()
    tokenProvider = get_bearer_token_provider(
        tokenCredential,
        "https://cognitiveservices.azure.com/.default",
    )
    chatcompletions_model_name = os.environ["AZURE_OPENAI_MODEL_NAME"]
    openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    search_endpoint = os.environ["SEARCH_SERVICE_ENDPOINT"]
    search_index_name = os.environ["SEARCH_INDEX_NAME"]
    knowledge_agent_name = os.environ["KNOWLEDGE_AGENT_NAME"]
    openai_deployment_name = os.environ["AZURE_OPENAI_DEPLOYMENT"]

    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=search_index_name,
        credential=tokenCredential,
        user_agent_policy=UserAgentPolicy(base_user_agent=USER_AGENT),
    )
    data_model = DocumentPerChunkDataModel()

    index_client = SearchIndexClient(
        endpoint=search_endpoint,
        credential=tokenCredential,
        user_agent_policy=UserAgentPolicy(base_user_agent=USER_AGENT),
    )

    # KnowledgeAgent init is commented for environments without agent SDK (public RAG only)
    if AGENT_AVAILABLE and knowledge_agent_name:
        ka_retrieval_client = KnowledgeAgentRetrievalClient(
            agent_name=knowledge_agent_name,
            endpoint=search_endpoint,
            credential=tokenCredential,
        )
        knowledge_agent = KnowledgeAgentGrounding(
            ka_retrieval_client,
            search_client,
            index_client,
            data_model,
            search_index_name,
            knowledge_agent_name,
            openai_endpoint,
            openai_deployment_name,
            chatcompletions_model_name,
        )
    else:
        knowledge_agent = None  # Not available in public SDK; classic search only

    openai_client = AsyncAzureOpenAI(
        azure_ad_token_provider=tokenProvider,
        api_version="2024-08-01-preview",
        azure_endpoint=openai_endpoint,
        timeout=30,
    )

    search_grounding = SearchGroundingRetriever(
        search_client,
        openai_client,
        data_model,
        chatcompletions_model_name,
    )

    blob_service_client = BlobServiceClient(
        account_url=os.environ["ARTIFACTS_STORAGE_ACCOUNT_URL"],
        credential=tokenCredential,
    )
    artifacts_container_client = blob_service_client.get_container_client(
        os.environ["ARTIFACTS_STORAGE_CONTAINER"]
    )

    mmrag = MultimodalRag(
        knowledge_agent,
        search_grounding,
        openai_client,
        chatcompletions_model_name,
        artifacts_container_client,
    )

    citation_files_handler = CitationFilesHandler(
        blob_service_client, artifacts_container_client
    )

    current_directory = Path(__file__).parent

    return {
        'index_client': index_client,
        'mmrag': mmrag,
        'citation_files_handler': citation_files_handler,
        'current_directory': current_directory
    }

clients = inject_clients()
app = FastAPI()
app.mount("/", StaticFiles(directory=clients['current_directory'] / "static"), name="static")
clients['mmrag'].attach_to_app(app, "/chat")
clients['mmrag'].attach_to_app(app, "/multiindex_chat")

@app.get("/")
async def root():
    return FileResponse(clients['current_directory'] / "static/index.html")

@app.get("/list_indexes")
async def list_indexes():
    index_client = clients['index_client']
    indexes = []
    async for index in index_client.list_indexes():
        indexes.append(index.name)
    return indexes

@app.post("/get_citation_doc")
async def get_citation_doc(request: Request):
    citation_files_handler = clients['citation_files_handler']
    return await citation_files_handler.handle(request)
