from typing import List
import os

from fastapi import FastAPI
from pydantic import BaseModel

from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents.aio import SearchClient
from openai import AsyncAzureOpenAI


app = FastAPI()

# Initialize Azure credentials and clients
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(
    credential, "https://cognitiveservices.azure.com/.default"
)

search_client = SearchClient(
    endpoint=os.environ["SEARCH_SERVICE_ENDPOINT"],
    index_name=os.environ["SEARCH_INDEX_NAME"],
    credential=credential,
)

openai_client = AsyncAzureOpenAI(
    api_version="2024-08-01-preview",
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    azure_ad_token_provider=token_provider,
)
openai_model = os.environ["AZURE_OPENAI_MODEL_NAME"]
openai_deployment = os.environ["AZURE_OPENAI_DEPLOYMENT"]


class Question(BaseModel):
    text: str


@app.post("/ask")
async def ask_question(question: Question):
    """Query Azure AI Search and generate an answer with Azure OpenAI."""
    # Retrieve top documents from the search index
    results = search_client.search(question.text, top=3)
    docs: List[str] = []
    async for doc in results:
        # 'content' is the text field created by the indexing process
        docs.append(doc.get("content", ""))

    context = "\n".join(docs)
    prompt = f"{context}\n\nQuestion: {question.text}\nAnswer:"

    completion = await openai_client.chat.completions.create(
        model=openai_model,
        deployment_id=openai_deployment,
        messages=[{"role": "user", "content": prompt}],
    )

    answer = completion.choices[0].message.content
    return {"answer": answer, "sources": docs}
