from functools import wraps
from typing import List
from app.database import SessionLocal
from app.exceptions import CreditLimitExceededException
from app.models.asset_content import AssetProcessingStatus
from app.processing.process_scheduler import ProcessScheduler
from app.repositories import process_repository
from app.repositories import project_repository
from concurrent.futures import ThreadPoolExecutor
from app.models import ProcessStatus
from app.requests import (
    extract_data,
)
from datetime import datetime
from app.models.process_step import ProcessStepStatus
from app.repositories import user_repository
from app.config import settings
import concurrent.futures
from app.logger import Logger
import traceback

from app.utils import clean_text
from app.vectorstore.chroma import ChromaDB
import re

executor = ThreadPoolExecutor(max_workers=5)

logger = Logger()


def submit_process(process_id: int) -> None:
    executor.submit(process_task, process_id)


process_execution_scheduler = ProcessScheduler(60, submit_process, logger)

# Background task processing function
def process_step_task(
    process_id: int,
    process_step_id: int,
    summaries: List[str],
    failed_docs: List[int],
    api_key: str,
):
    try:
        # Initial DB operations (open and fetch relevant data)
        with SessionLocal() as db:
            process = process_repository.get_process(db, process_id)
            project_id = process.project_id
            process_step = process_repository.get_process_step(db, process_step_id)
            filename =  process_step.asset.filename
            if process.status == ProcessStatus.STOPPED:
                return False  # Stop processing if the process is stopped

            logger.log(f"Processing file: {process_step.asset.path}")
            if process_step.status == ProcessStepStatus.COMPLETED and process.type!="extract":
                summaries.append(process_step.output.get("summary", ""))
                return True

            # Mark step as in progress
            update_process_step_status(db, process_step, ProcessStepStatus.IN_PROGRESS)

            retries = 0
            success = False
            asset_content = project_repository.get_asset_content(
                db, asset_id=process_step.asset.id
            )

        # Move the expensive external operations out of the DB session
        while retries < settings.max_retries and not success:
            try:
                if process.type == "extract":
                    # Handle non-extractive summary process
                    data = extract_process(
                        api_key, process, process_step, asset_content
                    )

                    # Update process step output outside the expensive operations
                    with SessionLocal() as db:
                        update_process_step_status(
                            db,
                            process_step,
                            ProcessStepStatus.COMPLETED,
                            output=data["fields"],
                            output_references=data["context"],
                        )

                    # vectorize extraction result
                    try:
                        vectorize_extraction_process_step(project_id=project_id,
                                                        process_step_id=process_step_id,
                                                        filename=filename,
                                                        references=data["context"])
                    except Exception :
                        logger.error(f"Failed to vectorize extraction results for chat {traceback.format_exc()}")

                success = True

            except CreditLimitExceededException:
                with SessionLocal() as db:
                    process = process_repository.get_process(db, process_id)
                    process_repository.update_process_status(
                        db, process, ProcessStatus.STOPPED
                    )

            except Exception:
                logger.error(traceback.format_exc())
                retries += 1
                if retries == settings.max_retries:
                    failed_docs.append(process_step.asset.id)
                    with SessionLocal() as db:
                        update_process_step_status(
                            db, process_step, ProcessStepStatus.FAILED
                        )

        return True

    except Exception:
        logger.error(traceback.format_exc())
        return False


def process_task(process_id: int):
    try:
        # Step 1: Fetch process details from the database and update its status
        with SessionLocal() as db:
            process = process_repository.get_process(db, process_id)
            process.status = ProcessStatus.IN_PROGRESS
            process.started_at = datetime.utcnow()
            db.commit()

            process_steps = process_repository.get_process_steps_with_asset_content(db, process.id, [ProcessStepStatus.PENDING.name, ProcessStepStatus.FAILED.name, ProcessStepStatus.IN_PROGRESS.name])
            if not process_steps:
                raise Exception("No process found!")

            api_key = user_repository.get_user_api_key(db)
            api_key = api_key.key
            db.refresh(process)

        # Step 2: Process each step in parallel outside the database connection
        failed_docs = []
        summaries = []

        ready_process_steps = [process_step for process_step in process_steps if process_step.asset.content.processing == AssetProcessingStatus.COMPLETED]

        all_process_steps_ready = len(ready_process_steps) == len(process_steps) # Check if all process steps are ready

        # Step 3: Concurrently process all process steps
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(
                    process_step_task,
                    process.id,
                    process_step.id,
                    summaries,
                    failed_docs,
                    api_key,
                )
                for process_step in ready_process_steps
            ]
            # Wait for all submitted tasks to complete
            concurrent.futures.wait(futures)

        # Step 4: After all steps are processed, update the process status and output in the DB
        with SessionLocal() as db:
            process = process_repository.get_process(db, process_id)

            if process.status != ProcessStatus.STOPPED:
                # If summary extraction was performed, add it to the process output
                if not all_process_steps_ready:
                    logger.info(f"Process id: [{process.id}] some steps preprocessing is missing moving to waiting queue")
                    process_execution_scheduler.add_process_to_queue(process.id)
                    db.commit()
                    # Skip status update since not all steps are ready
                    return

                process.status = (
                    ProcessStatus.COMPLETED if not failed_docs else ProcessStatus.FAILED
                )
                process.completed_at = datetime.utcnow()

            db.commit()

    except Exception as e:
        logger.error(traceback.format_exc())
        # Step 5: Handle failure cases and update the status accordingly
        with SessionLocal() as db:
            process = process_repository.get_process(db, process_id)
            process.status = ProcessStatus.FAILED
            process.message = str(e)
            db.commit()


def handle_exceptions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CreditLimitExceededException:
            logger.error("Credit limit exceeded")
            raise
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    return wrapper


@handle_exceptions
def extract_process(api_key, process, process_step, asset_content):
    pdf_content = ""
    # TODO - Disable Vector store pdf content fetching temporarily until fixed.
    # vectorstore = ChromaDB(f"panda-etl-{process.project_id}", similarity_threshold=3)
    # if (
    #     ("multiple_fields" not in process.details or not process.details["multiple_fields"])
    #     and asset_content.content
    #     and asset_content.content.get("word_count", 0) > 500
    # ):
    #     for field in process.details["fields"]:
    #         relevant_docs = vectorstore.get_relevant_docs(
    #             field["key"],
    #             where={
    #                 "$and": [
    #                     {"asset_id": process_step.asset.id},
    #                     {"project_id": process.project_id},
    #                 ]
    #             },
    #             k=5,
    #         )

    #         for index, metadata in enumerate(relevant_docs["metadatas"][0]):
    #             segment_data = [relevant_docs["documents"][0][index]]
    #             if metadata.get("previous_sentence_id", -1) != -1:
    #                 prev_sentence = vectorstore.get_relevant_docs_by_id(
    #                     ids=[metadata["previous_sentence_id"]]
    #                 )
    #                 if prev_sentence["documents"] and len(prev_sentence["documents"][0]) > 0:
    #                     segment_data = [prev_sentence["documents"][0]] + segment_data
    #                 else:
    #                     logger.warning("Previous sentence document is empty.")

    #             if metadata.get("next_sentence_id", -1) != -1:
    #                 next_sentence = vectorstore.get_relevant_docs_by_id(
    #                     ids=[metadata["next_sentence_id"]]
    #                 )
    #                 if next_sentence["documents"] and len(next_sentence["documents"][0]) > 0:
    #                     segment_data.append(next_sentence["documents"][0])
    #                 else:
    #                     logger.warning("Next sentence document is empty.")

    #             pdf_content += "\n" + " ".join(segment_data)

    if not pdf_content:
        pdf_content = (
            "\n".join(item["text"] for item in asset_content.content.get("content", []) if "text" in item)
            if asset_content.content
            else None
        )

    data = extract_data(
        api_key,
        process.details,
        file_path=(process_step.asset.path if not pdf_content else None),
        pdf_content=pdf_content if pdf_content else None,
    )

    vectorstore = ChromaDB(f"panda-etl-{process.project_id}", similarity_threshold=3)
    all_relevant_docs = []

    for references in data.references:
        for reference in references:
            page_numbers = []
            for source_index, source in enumerate(reference.sources):
                if len(source) < 30:

                    best_match = find_best_match_for_short_reference(
                        source,
                        all_relevant_docs,
                        process_step.asset.id,
                        process.project_id
                    )
                    if best_match:
                        reference.sources[source_index] = best_match["text"]
                        page_numbers.append(best_match["page_number"])

                else:
                    relevant_docs = vectorstore.get_relevant_docs(
                        source,
                        where={
                            "$and": [
                                {"asset_id": process_step.asset.id},
                                {"project_id": process.project_id},
                            ]
                        },
                        k=5,
                    )
                    all_relevant_docs.append(relevant_docs)

                    most_relevant_index = 0
                    match = False
                    clean_source = clean_text(source)
                    # search for exact match Index
                    for index, relevant_doc in enumerate(relevant_docs["documents"][0]):
                        if not relevant_docs["documents"][0]:
                            logger.warning("No relevant documents found.")
                            continue
                        if clean_source in clean_text(relevant_doc):
                            most_relevant_index = index
                            match = True
                            break

                    if not match and len(relevant_docs["documents"][0]) > 0:
                        reference.sources[source_index] = relevant_docs["documents"][0][0]
                        if relevant_docs["documents"][0]:
                            page_numbers.append(
                                relevant_docs["metadatas"][0][most_relevant_index]["page_number"]
                            )
                        else:
                            logger.warning("No documents available to assign to source.")

                    if len(relevant_docs["metadatas"][0]) > 0:
                        page_numbers.append(
                            relevant_docs["metadatas"][0][most_relevant_index]["page_number"]
                        )

            if page_numbers:
                reference.page_numbers = page_numbers

    data_dict = data.model_dump()

    return {
        "fields": data_dict["fields"],
        "context": data_dict["references"],
    }

def find_best_match_for_short_reference(source, all_relevant_docs, asset_id, project_id, threshold=0.8):
    source_words = set(re.findall(r'\w+', source.lower()))
    if not source_words:
        return None  # Return None if the source is empty

    best_match = None
    best_match_score = 0

    for relevant_docs in all_relevant_docs:
        for doc, metadata in zip(relevant_docs["documents"][0], relevant_docs["metadatas"][0]):
            if metadata["asset_id"] == asset_id and metadata["project_id"] == project_id:
                doc_words = set(re.findall(r'\w+', doc.lower()))
                common_words = source_words.intersection(doc_words)
                match_score = len(common_words) / len(source_words)

                if match_score > best_match_score:
                    best_match_score = match_score
                    best_match = {"text": doc, "page_number": metadata["page_number"]}

    return best_match if best_match_score >= threshold else None


def update_process_step_status(
    db, process_step, status, output=None, output_references=None
):
    """
    Update the status of a process step.

    Args:
    db: Database session
    process_step: The process step to update
    status: The new status
    output: Optional output data
    output_references: Optional output references
    """
    process_repository.update_process_step_status(
        db, process_step, status, output=output, output_references=output_references
    )

def vectorize_extraction_process_step(project_id: int, process_step_id: int, filename: str, references: dict) -> None:
    # Vectorize extraction result and dump in database
    field_references = {}

    # Loop to concatenate sources for each reference
    for extraction_references in references:
        for extraction_reference in extraction_references:
            sources = extraction_reference.get("sources", [])
            if sources:
                sources_catenated = "\n".join(sources)
                field_references.setdefault(extraction_reference["name"], "")
                field_references[extraction_reference["name"]] += (
                    "\n" + sources_catenated if field_references[extraction_reference["name"]] else sources_catenated
                )

    # Only proceed if there are references to add
    if not field_references:
        return

    # Initialize Vectorstore
    vectorstore = ChromaDB(f"panda-etl-extraction-{project_id}")

    docs = [f"{filename} {key}" for key in field_references]
    metadatas = [
        {
            "project_id": project_id,
            "process_step_id": process_step_id,
            "filename": filename,
            "reference": reference
        }
        for reference in field_references.values()
    ]

    # Add documents to vectorstore
    vectorstore.add_docs(docs=docs, metadatas=metadatas, batch_size=settings.chroma_batch_size)
