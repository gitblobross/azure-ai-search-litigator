from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from azure.search.documents import SearchClient
import openai

from settings import settings


def ocr_document(document_bytes: bytes) -> dict:
    # Use Azure Document Intelligence to perform OCR on the document bytes
    credential = AzureKeyCredential(settings.docai_key)
    client = DocumentIntelligenceClient(endpoint=settings.docai_endpoint, credential=credential)
    poller = client.begin_analyze_document(model_id="prebuilt-layout", document=document_bytes)
    result = poller.result()
    # You might want to process 'result' into a serializable dict
    return {"result": str(result)}


def search_claims(query: str) -> dict:
    # Use Azure AI Search to query the claims index
    # Note: Depending on your configuration, you might need a dedicated search API key.
    credential = AzureKeyCredential(settings.openai_key)  # Placeholder credential
    client = SearchClient(endpoint=settings.search_endpoint, index_name=settings.search_index, credential=credential)
    results = client.search(query)
    return {"results": [doc for doc in results]}


def openai_chat(question: str) -> dict:
    # Call Azure OpenAI for chat completions
    openai.api_key = settings.openai_key
    response = openai.ChatCompletion.create(
        model="gpt-law",
        deployment_id="gpt-law",
        messages=[
            {"role": "system", "content": "You are a legal assistant."},
            {"role": "user", "content": question}
        ]
    )
    return response


def upload_blob(file_bytes: bytes, filename: str) -> str:
    # Upload file to Blob Storage under the 'evidence' container
    blob_service_client = BlobServiceClient.from_connection_string(settings.blob_conn)
    container_name = "evidence"
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_client.create_container()
    except Exception:
        # Container probably already exists
        pass
    blob_client = container_client.get_blob_client(filename)
    blob_client.upload_blob(file_bytes, overwrite=True)
    return blob_client.url


def save_claim(claim: dict) -> None:
    # Save claim data to Cosmos DB in a database 'litigator' and container 'claims'
    cosmos_client = CosmosClient.from_connection_string(settings.cosmos_conn)
    database_name = "litigator"
    container_name = "claims"
    database = cosmos_client.get_database_client(database_name)
    container = database.get_container_client(container_name)
    container.upsert_item(claim)
