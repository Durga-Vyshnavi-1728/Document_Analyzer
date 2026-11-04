
"""Gemini document embeddings and answer generation."""

import os
from google import genai
from google.genai import types

RULES = """
You are a careful assistant answering questions about uploaded documents.

Answer the exact question directly in natural, simple language.
Usually use 2-6 sentences or a few useful bullets.

Use complete sentences. Never end a sentence or bullet halfway through.

Understand equivalent terms and paraphrases.
For example, policyholder, proposer and insured may be related,
but do not treat them as identical unless the document says so.

For dates, amounts and durations:
- Include the complete value.
- Keep the value attached to its description.
- Explain what the date or amount refers to.

Use only the supplied document excerpts as evidence.
Never invent missing information.

If the excerpts do not contain the answer, say:
"I couldn't locate that information in the provided passages."

Do not claim that information is absent from the entire document
unless the entire document has actually been checked.

Cite the source file and relevant page, slide, sheet or location.

Do not mention embeddings, chunks, retrieval or internal processes.
"""


def make_client():
    key = os.getenv("GEMINI_API_KEY", "").strip()

    if not key or key == "paste_your_key_here":
        raise RuntimeError(
            "Add your Gemini API key to the .env file, then restart the app."
        )

    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=120000)
    )


def embed_texts(
    texts,
    task_type="RETRIEVAL_DOCUMENT",
    progress_callback=None
):
    if not texts:
        return []

    client = make_client()
    vectors = []

    batch_size = 64
    total_batches = (
        len(texts) + batch_size - 1
    ) // batch_size

    for batch_number, start in enumerate(
        range(0, len(texts), batch_size), 1
    ):
        batch = texts[start:start + batch_size]

        if progress_callback:
            progress_callback(
                batch_number,
                total_batches,
                f"Preparing search index: batch {batch_number} of {total_batches}"
            )

        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=batch,
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=768
            )
        )

        if not result.embeddings or len(result.embeddings) != len(batch):
            raise RuntimeError(
                "The embedding service returned an incomplete batch."
            )

        vectors.extend([
            list(item.values)
            for item in result.embeddings
        ])

        if progress_callback:
            progress_callback(
                batch_number,
                total_batches,
                f"Prepared {min(start + len(batch), len(texts))} of {len(texts)} sections"
            )

    return vectors


def answer_question(question, excerpts, history=None):
    if not excerpts:
        return (
            "I couldn't locate relevant information in the provided "
            "document passages. Try asking about a specific topic, "
            "name, date or amount."
        )

    client = make_client()

    evidence = "\n\n".join(
        f"[Source: {item['source']} | Location: {item['location']}]\n"
        f"{item['text']}"
        for item in excerpts
    )

    recent = ""

    if history:
        recent = "\n".join(
            ("User: " if item["role"] == "user" else "Assistant: ")
            + item["content"]
            for item in history[-4:]
        )

    prompt = f"""
DOCUMENT EVIDENCE:
The following passages are the only source of factual claims.

{evidence}

RECENT CONVERSATION:
This is context only. It is not documentary evidence.

{recent or "(none)"}

USER QUESTION:
{question}

ANSWERING INSTRUCTIONS:
1. Answer the specific question, not a nearby topic.
2. Include complete dates, amounts, names and conditions when available.
3. For a package question, include all relevant package components.
4. For a deadline question, state the action and exact deadline.
5. Keep every label attached to its corresponding value.
6. If the passages do not establish an answer, say so clearly.
7. Do not invent or complete missing values.
8. Cite the source and location.
9. Finish every sentence and bullet.
"""

    result = client.models.generate_content(
        model=os.getenv(
            "GEMINI_MODEL",
            "gemini-3.8-flash"
        ).strip(),
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=RULES,
            temperature=0.1,
            max_output_tokens=900
        )
    )

    answer = (result.text or "").strip()

    if not answer:
        raise RuntimeError(
            "The AI returned an empty answer. Please try again."
        )

    return answer
