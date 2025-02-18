import uuid
from typing import Callable, Iterable, List, Optional, Tuple
from pydantic_settings import BaseSettings

import chromadb
from app.config import settings as default_settings
from app.vectorstore import VectorStore
from app.logger import Logger
from chromadb import config
from chromadb.utils import embedding_functions
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

logger = Logger(verbose=True)

DEFAULT_EMBEDDING_FUNCTION = embedding_functions.DefaultEmbeddingFunction()

class ChromaDB(VectorStore):
    """
    Implementation of ChromeDB vector store
    """

    def __init__(
        self,
        collection_name: str = "panda-etl",
        embedding_function: Optional[Callable[[List[str]], List[float]]] = None,
        persist_path: Optional[str] = None,
        client_settings: Optional[config.Settings] = None,
        max_samples: int = 3,
        similarity_threshold: int = 1.5,
        batch_size: Optional[int] = None,
        settings: Optional[BaseSettings] = None,
    ) -> None:
        self.settings = settings or default_settings
        self._max_samples = max_samples
        self._similarity_threshold = similarity_threshold
        self._batch_size = batch_size or self.settings.chroma_batch_size

        # Initialize Chromadb Client
        if client_settings:
            client_settings.persist_directory = (
                persist_path or client_settings.persist_directory
            )
            _client_settings = client_settings
        elif persist_path:
            _client_settings = config.Settings(
                is_persistent=True, anonymized_telemetry=False
            )
            _client_settings.persist_directory = persist_path
        else:
            _client_settings = config.Settings(
                is_persistent=True, anonymized_telemetry=False
            )
            _client_settings.persist_directory = self.settings.chromadb_url

        self._client_settings = _client_settings
        self._client = chromadb.Client(_client_settings)
        self._persist_directory = _client_settings.persist_directory

        # Use the embedding function from config
        if self.settings.use_openai_embeddings and self.settings.openai_api_key:
            self._embedding_function = OpenAIEmbeddingFunction(
                api_key=self.settings.openai_api_key,
                model_name=self.settings.openai_embedding_model
            )
        else:
            self._embedding_function = embedding_function or DEFAULT_EMBEDDING_FUNCTION

        self._docs_collection = self._client.get_or_create_collection(
            name=collection_name, embedding_function=self._embedding_function
        )

    def add_docs(
        self,
        docs: Iterable[str],
        ids: Optional[Iterable[str]] = None,
        metadatas: Optional[List[dict]] = None,
        batch_size: Optional[int] = None,
    ) -> List[str]:
        """
        Add docs to the training set
        Args:
            docs: Iterable of strings to add to the vectorstore.
            ids: Optional Iterable of ids associated with the texts.
            metadatas: Optional list of metadatas associated with the texts.
            batch_size: Optional batch size for adding documents. If not provided, uses the instance's batch size.

        Returns:
            List of ids from adding the texts into the vectorstore.
        """
        if ids is None:
            ids = [f"{str(uuid.uuid4())}-docs" for _ in docs]

        if metadatas is None:
            metadatas = [{}] * len(docs)

        # Add previous_id and next_id to metadatas
        for idx, metadata in enumerate(metadatas):
            metadata["previous_sentence_id"] = ids[idx - 1] if idx > 0 else -1
            metadata["next_sentence_id"] = ids[idx + 1] if idx < len(ids) - 1 else -1

        filename = metadatas[0].get('filename', 'unknown')
        logger.info(f"Adding {len(docs)} sentences to the vector store for file {filename}")

        # Batching the document processing
        batch_size = batch_size or self._batch_size

        for i in range(0, len(docs), batch_size):
            logger.info(f"Processing batch {i} to {i + batch_size}")
            self._docs_collection.add(
                documents=docs[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
                ids=ids[i : i + batch_size],
            )

        return list(ids)

    def delete_docs(
        self, ids: Optional[List[str]] = None, where: Optional[dict] = None
    ) -> Optional[bool]:
        """
        Delete by vector ID to delete docs
        Args:
            ids: List of ids to delete

        Returns:
            Optional[bool]: True if deletion is successful,
            False otherwise
        """

        if ids is None and where is not None:
            records_to_delete = self._docs_collection.get(where=where)
            ids = records_to_delete["ids"]

        self._docs_collection.delete(ids=ids)
        return True

    def get_relevant_docs(
        self, question: str, where: Optional[dict] = None, k: int = None
    ) -> List[dict]:
        """
        Returns relevant documents based search
        """
        k = k or self._max_samples

        if not where:
            relevant_data: chromadb.QueryResult = self._docs_collection.query(
                query_texts=question,
                n_results=k,
                include=["metadatas", "documents", "distances"],
            )
        else:
            relevant_data: chromadb.QueryResult = self._docs_collection.query(
                query_texts=question,
                n_results=k,
                include=["metadatas", "documents", "distances"],
                where=where,
            )

        return self._filter_docs_based_on_distance(
            relevant_data, self._similarity_threshold
        )

    def get_relevant_segments(
        self,
        question: str,
        k: int = None,
        num_surrounding_sentences: int = 3,
        metadata_filter: Optional[dict] = None,
    ) -> Tuple[List[str], List[str], List[dict]]:
        k = k or self._max_samples

        relevant_docs = self.get_relevant_docs(
            question,
            k=k,
            where=metadata_filter,
        )

        segments = []
        doc_ids = []
        metadatas = []
        # Iterate over each document's metadata and fetch surrounding sentences
        for index, metadata in enumerate(relevant_docs["metadatas"][0]):
            pdf_content = ""
            segment_data = [relevant_docs["documents"][0][index]]

            # Get previous sentences
            prev_id = metadata.get("previous_sentence_id")
            for _ in range(num_surrounding_sentences):
                if prev_id != -1:
                    prev_sentence = self.get_relevant_docs_by_id(ids=[prev_id])
                    segment_data = [prev_sentence["documents"][0]] + segment_data
                    prev_id = prev_sentence["metadatas"][0].get(
                        "previous_sentence_id", -1
                    )
                else:
                    break

            # Get next sentences
            next_id = metadata.get("next_sentence_id")
            for _ in range(num_surrounding_sentences):
                if next_id != -1:
                    next_sentence = self.get_relevant_docs_by_id(ids=[next_id])
                    segment_data.append(next_sentence["documents"][0])
                    next_id = next_sentence["metadatas"][0].get("next_sentence_id", -1)
                else:
                    break

            # Add the segment data to the PDF content
            pdf_content += "\n" + " ".join(segment_data)
            segments.append(pdf_content)
            doc_ids.append(metadata["asset_id"])
            metadatas.append(metadata)

        return (segments, doc_ids, metadatas)

    def get_relevant_docs_by_id(self, ids: Iterable[str]) -> List[dict]:
        """
        Returns relevant question answers based on ids
        """

        relevant_data: chromadb.QueryResult = self._docs_collection.get(
            ids=ids,
            include=["metadatas", "documents"],
        )

        return relevant_data

    def _filter_docs_based_on_distance(
        self, documents: chromadb.QueryResult, threshold: int
    ) -> List[str]:
        """
        Filter documents based on threshold
        Args:
            documents (List[str]): list of documents in string
            distances (List[float]): list of distances in float
            threshold (int): similarity threshold

        Returns:
            _type_: _description_
        """
        filtered_data = [
            (doc, distance, metadata, ids)
            for doc, distance, metadata, ids in zip(
                documents["documents"][0],
                documents["distances"][0],
                documents["metadatas"][0],
                documents["ids"][0],
            )
            if distance < threshold
        ]

        return {
            key: [[data[i] for data in filtered_data]]
            for i, key in enumerate(["documents", "distances", "metadatas", "ids"])
        }
