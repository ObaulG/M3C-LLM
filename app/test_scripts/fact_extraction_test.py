import asyncio
from datetime import datetime

import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from agents.fact_extractor import *
from database import get_db_connection, save_question_to_db, get_chunk_by_id, get_questions_by_document_id, get_chunks_for_document

# Constantes
DOCUMENT_ID = "8a672d2ae6f2abfa4434e0f4145a9aa77bbc6d56"
CHUNKING_STRATEGY_ID = 7

async def main(document_id: str,
               num_start: int = 0):
    fact_analyser = get_fact_analyser_agent()

    chunks = await get_chunks_for_document(
        document_id=DOCUMENT_ID,
        conn=await get_db_connection(),
        chunking_strategy_id=CHUNKING_STRATEGY_ID
    )
    total_chunks = len(chunks)
    logger.info(f"{total_chunks} chunks reçus")

    facts_per_chunk = {}
    processed_chunks = num_start+1

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"facts_output_{timestamp}.txt"

    # Write header to file
    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(f"{DOCUMENT_ID} {CHUNKING_STRATEGY_ID}\n")
        f.write(f"0/{total_chunks}\n")

    logger.info("Extraction des faits...")

    i=0
    for chunk_id, chunk_content in chunks:
        if i < num_start:
            i+=1
            continue
        try:
            input_data = FactExtractionInput(paragraph=chunk_content)
            output = fact_analyser.run(input_data)
            facts = output.facts
            facts_per_chunk[chunk_id] = facts

            # Print facts for this chunk
            print(f"\n--- Chunk {chunk_id} ---")
            for fact in facts:
                print(f"- {fact}")

            logger.info(f"Faits extraits pour le chunk {chunk_id}: {len(facts)} faits")

            # Update file: write header, progress, and all facts so far
            processed_chunks += 1
            with open(output_filename, "w", encoding="utf-8") as f:
                f.write(f"{DOCUMENT_ID} {CHUNKING_STRATEGY_ID}\n")
                f.write(f"{processed_chunks}/{total_chunks}\n")
                for cid, c_facts in facts_per_chunk.items():
                    f.write(f"\n--- Chunk {cid} ---\n")
                    for fact in c_facts:
                        f.write(f"- {fact}\n")

        except Exception as e:
            logger.error(f"Erreur pour le chunk {chunk_id}: {e}")
            facts_per_chunk[chunk_id] = []
        i+=1
    logger.info(f"Tous les faits ont été enregistrés dans {output_filename}.")
    return facts_per_chunk


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(DOCUMENT_ID, 48))
