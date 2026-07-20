"""Idempotent literature database seeder for seeding mock scientific papers."""

from __future__ import annotations

import asyncio
import sys

from config.settings import get_settings
from db.repository import LiteratureRepository
from db.session import AsyncSessionLocal, init_engine, dispose_engine
from orchestrator.agents.literature_rag.embedding import get_embedding_provider

# Standard mock papers/reports content to seed
MOCK_PAPERS = [
    {
        "document_id": "paper_tokyo_seismic_2025",
        "title": "A Study on Seismic Vulnerability and High-Magnitude Earthquake Probability in Tokyo (2025)",
        "source_url": "https://science.planetaryrisk.org/papers/tokyo-seismic-2025.pdf",
        "text": (
            "The metropolitan area of Tokyo is situated directly above a complex convergent plate boundary. "
            "Over the past decade, seismic measurements show a steady build-up of strain across the fault lines. "
            "We calculate a 70% probability of a magnitude 7.0 or greater earthquake occurring within the next 30 years. "
            "Local building codes have been upgraded, but soft-soil regions near the coast remain vulnerable to liquefaction. "
            "In addition, secondary tsunami waves present a significant risk to low-lying bayside infrastructure."
        ),
    },
    {
        "document_id": "paper_california_wildfires_2026",
        "title": "Atmospheric Temperature Increases and Wildfire Propagation Dynamics in California (2026)",
        "source_url": "https://science.planetaryrisk.org/papers/california-wildfires-2026.pdf",
        "text": (
            "Climate modeling indicates that average atmospheric temperatures in California have risen by 1.5 degrees Celsius "
            "over the historical baseline. This warming trend, coupled with prolonged periods of drought, results in extremely "
            "low fuel moisture levels. During high-wind events, wildfires propagate at accelerated speeds, often exceeding "
            "10 kilometers per hour. Analysis of recent fire perimeters reveals that forest density and dry shrub accumulation "
            "are the primary drivers of fire intensity, outstripping regional weather variances."
        ),
    },
    {
        "document_id": "paper_ocean_marine_heatwaves_2025",
        "title": "Marine Heatwaves and Sea Surface Temperature Anomalies in the Western Pacific (2025)",
        "source_url": "https://science.planetaryrisk.org/papers/ocean-heatwaves-2025.pdf",
        "text": (
            "Sea surface temperatures (SST) in the Western Pacific have registered persistent anomalies exceeding +2.5 degrees "
            "Celsius during summer months. These marine heatwaves disrupt regional marine ecosystems, triggering massive "
            "coral bleaching events and shifting fish migration patterns. High-resolution satellite imagery confirms that "
            "these thermal plumes are expanding in area. The correlation between increased ocean temperature and severe "
            "storm intensity is well-documented, indicating a high risk of category 4 typhoons in the region."
        ),
    },
]


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Slice text into overlapping character-based chunks."""
    if chunk_size <= 0:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
        if start >= len(text) or chunk_size <= chunk_overlap:
            break
    return chunks


async def run_seeder() -> None:
    settings = get_settings()
    provider = get_embedding_provider(settings)

    print(f"Resolving database connection...")
    init_engine()
    
    if AsyncSessionLocal is None:
        print("Error: Database session local factory is None.")
        sys.exit(1)

    print(f"Preparing chunks with size={settings.chunk_size}, overlap={settings.chunk_overlap}...")
    
    prepared_chunks = []
    for paper in MOCK_PAPERS:
        doc_id = paper["document_id"]
        title = paper["title"]
        source_url = paper["source_url"]
        text_content = paper["text"]
        
        chunks = chunk_text(text_content, settings.chunk_size, settings.chunk_overlap)
        
        for idx, chunk_text_content in enumerate(chunks):
            # Compute embedding for chunk
            embedding = await provider.embed_query(chunk_text_content)
            
            prepared_chunks.append({
                "document_id": doc_id,
                "chunk_text": chunk_text_content,
                "embedding": embedding,
                "source_url": source_url,
                "extra_metadata": {
                    "title": title,
                    "chunk_id": idx + 1,
                }
            })

    print(f"Inserting {len(prepared_chunks)} chunks (idempotent verification active)...")
    async with AsyncSessionLocal() as session:
        await LiteratureRepository.seed_chunks(session, prepared_chunks)
        print("Seeding successful!")

    await dispose_engine()


if __name__ == "__main__":
    asyncio.run(run_seeder())
