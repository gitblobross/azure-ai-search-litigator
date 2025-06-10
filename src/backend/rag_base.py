import logging
import json
import os
import time
from typing import List
import uuid
from abc import ABC, abstractmethod
from enum import Enum

import asyncio
from fastapi import FastAPI, Request
# PATCHED: Use EventSourceResponse from sse_starlette
from sse_starlette.sse import EventSourceResponse
# PATCH: Make instructor optional
try:
    import instructor
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False
from openai import AsyncAzureOpenAI
from grounding_retriever import GroundingRetriever
from models import (
    AnswerFormat,
    SearchConfig,
    GroundingResult,
    GroundingResults,
)
from processing_step import ProcessingStep

logger = logging.getLogger("rag")


class MessageType(Enum):
    ANSWER = "answer"
    CITATION = "citation"
    LOG = "log"
    ERROR = "error"
    END = "[END]"
    ProcessingStep = "processing_step"
    INFO = "info"


class SSEStream:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()

    async def send(self, event: str, data: dict):
        await self.queue.put((event, data))

    async def close(self):
        await self.queue.put(None)

    async def __aiter__(self):
        while True:
            item = await self.queue.get()
            if item is None:
                break
            event, data = item
            yield f"event:{event}\ndata: {json.dumps(data)}\n\n"


class RagBase(ABC):
    def __init__(
        self,
        openai_client: AsyncAzureOpenAI,
        chatcompletions_model_name: str,
    ):
        self.openai_client = openai_client
        self.chatcompletions_model_name = chatcompletions_model_name

    async def _handle_request(self, request: Request):
        request_params = await request.json()
        search_text = request_params.get("query", "")
        chat_thread = request_params.get("chatThread", [])
        config_dict = request_params.get("config", {})
        search_config = SearchConfig(
            chunk_count=config_dict.get("chunk_count", 10),
            openai_api_mode=config_dict.get("openai_api_mode", "chat_completions"),
            use_semantic_ranker=config_dict.get("use_semantic_ranker", False),
            use_streaming=config_dict.get("use_streaming", False),
            use_knowledge_agent=config_dict.get("use_knowledge_agent", False),
        )
        request_id = request_params.get("request_id", str(int(time.time())))
        stream = SSEStream()

        async def process():
            try:
                await self._process_request(
                    request_id, stream, search_text, chat_thread, search_config
                )
            except Exception as e:
                logger.error(f"Error processing request: {str(e)}")
                await self._send_error_message(request_id, stream, str(e))
            finally:
                await self._send_end(stream)
                await stream.close()

        asyncio.create_task(process())

        return EventSourceResponse(stream)

    @abstractmethod
    async def _process_request(
        self,
        request_id: str,
        stream: SSEStream,
        search_text: str,
        chat_thread: list,
        search_config: SearchConfig,
    ):
        pass

    async def _formulate_response(
        self,
        request_id: str,
        stream: SSEStream,
        messages: list,
        grounding_retriever: GroundingRetriever,
        grounding_results: GroundingResults,
        search_config: SearchConfig,
    ):
        """Handles streaming chat completion and sends citations."""

        logger.info("Formulating LLM response")
        await self._send_processing_step_message(
            request_id,
            stream,
            ProcessingStep(title="LLM Payload", type="code", content=messages),
        )

        complete_response: dict = {}

        if search_config.get("use_streaming", False):
            logger.info("Streaming chat completion")
            chat_stream_response = instructor.from_openai(
                self.openai_client,
            ).chat.completions.create_partial(
                stream=True,
                model=self.chatcompletions_model_name,
                response_model=AnswerFormat,
                messages=messages,
            )
            msg_id = str(uuid.uuid4())

            async for stream_response in chat_stream_response:
                if stream_response.answer is not None:
                    await self._send_answer_message(
                        request_id, stream, msg_id, stream_response.answer
                    )
                    complete_response = stream_response.model_dump()
            if len(complete_response.keys()) == 0:
                raise ValueError("No response received from chat completion stream.")

        else:
            logger.info("Waiting for chat completion")
            chat_completion = await instructor.from_openai(
                self.openai_client,
            ).chat.completions.create(
                stream=False,
                model=self.chatcompletions_model_name,
                response_model=AnswerFormat,
                messages=messages,
            )
            msg_id = str(uuid.uuid4())

            if chat_completion is not None:
                await self._send_answer_message(
                    request_id, stream, msg_id, chat_completion.answer
                )
                complete_response = chat_completion.model_dump()
            else:
                raise ValueError("No response received from chat completion stream.")

        await self._extract_and_send_citations(
            request_id,
            stream,
            grounding_retriever,
            grounding_results["references"],
            complete_response["text_citations"] or [],
            complete_response["image_citations"] or [],
        )

    async def _extract_and_send_citations(
        self,
        request_id: str,
        stream: SSEStream,
        grounding_retriever: GroundingRetriever,
        grounding_results: List[GroundingResult],
        text_citation_ids: list,
        image_citation_ids: list,
    ):
        """Extracts and sends citations from search results."""
        citations = await self.extract_citations(
            grounding_retriever,
            grounding_results,
            text_citation_ids,
            image_citation_ids,
        )

        await self._send_citation_message(
            request_id,
            stream,
            request_id,
            citations.get("text_citations", []),
            citations.get("image_citations", []),
        )

    @abstractmethod
    async def extract_citations(
        self,
        grounding_retriever: GroundingRetriever,
        grounding_results: List[GroundingResult],
        text_citation_ids: list,
        image_citation_ids: list,
    ) -> dict:
        pass


    async def _send_error_message(
        self, request_id: str, stream: SSEStream, message: str
    ):
        """Sends an error message through the stream."""
        await self._send_message(
            stream,
            MessageType.ERROR.value,
            {
                "request_id": request_id,
                "message_id": str(uuid.uuid4()),
                "message": message,
            },
        )

    async def _send_info_message(
        self,
        request_id: str,
        stream: SSEStream,
        message: str,
        details: str = None,
    ):
        """Sends an info message through the stream."""
        await self._send_message(
            stream,
            MessageType.INFO.value,
            {
                "request_id": request_id,
                "message_id": str(uuid.uuid4()),
                "message": message,
                "details": details,
            },
        )

    async def _send_processing_step_message(
        self,
        request_id: str,
        stream: SSEStream,
        processing_step: ProcessingStep,
    ):
        logger.info(
            f"Sending processing step message for step: {processing_step.title}"
        )
        await self._send_message(
            stream,
            MessageType.ProcessingStep.value,
            {
                "request_id": request_id,
                "message_id": str(uuid.uuid4()),
                "processingStep": processing_step.to_dict(),
            },
        )

    async def _send_answer_message(
        self,
        request_id: str,
        stream: SSEStream,
        message_id: str,
        content: str,
    ):
        await self._send_message(
            stream,
            MessageType.ANSWER.value,
            {
                "request_id": request_id,
                "message_id": message_id,
                "role": "assistant",
                "answerPartial": {"answer": content},
            },
        )

    async def _send_citation_message(
        self,
        request_id: str,
        stream: SSEStream,
        message_id: str,
        text_citations: list,
        image_citations: list,
    ):

        await self._send_message(
            stream,
            MessageType.CITATION.value,
            {
                "request_id": request_id,
                "message_id": message_id,
                "textCitations": text_citations,
                "imageCitations": image_citations,
            },
        )

    async def _send_message(self, stream: SSEStream, event: str, data: dict):
        try:
            await stream.send(event, data)
        except ConnectionResetError:
            # TODO: Something is wrong here, the messages attempted and failed here is not what the UI sees, thats another set of stream...
            # logger.warning("Connection reset by client.")
            pass
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    async def _send_end(self, stream: SSEStream):
        await self._send_message(stream, MessageType.END.value, {})

    def attach_to_app(self, app: FastAPI, path: str):
        """Attaches the handler to the FastAPI app."""
        app.post(path)(self._handle_request)
