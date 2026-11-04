
import hashlib
import os
import streamlit as st

from dotenv import load_dotenv
from src.document_tools import (
    extract_document,
    split_sections,
    SUPPORTED_EXTENSIONS
)
from src.pdf_tools import find_relevant_chunks
from src.gemini_client import answer_question, embed_texts

load_dotenv()

st.set_page_config(
    page_title="Document Analyzer",
    page_icon="📚",
    layout="centered"
)

st.markdown("""
<style>
.block-container {
    max-width: 950px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
[data-testid="stSidebar"] {
    background: #f7f8fa;
}
.title {
    font-size: 2rem;
    font-weight: 750;
    letter-spacing: -.04em;
}
.sub {
    color: #687386;
    margin-bottom: 1.5rem;
}
[data-testid="stChatMessage"] {
    padding-top: .6rem;
    padding-bottom: .6rem;
}
</style>
""", unsafe_allow_html=True)


DEFAULTS = {
    "messages": [],
    "docs_hash": None,
    "sections": [],
    "chunks": [],
    "embeddings": None,
    "embedding_notice": None,
    "doc_names": []
}

for key, default in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


with st.sidebar:
    st.markdown("## 📚 Document Analyzer")
    st.caption("Ask questions across your documents.")

    uploaded_files = st.file_uploader(
        "Upload documents",
        type=[
            ext.lstrip(".")
            for ext in sorted(SUPPORTED_EXTENSIONS)
        ],
        accept_multiple_files=True,
        help=(
            "Supported: PDF, DOCX, XLSX, XLS, PPTX, TXT and MD. "
            "Legacy .doc files are not supported; save them as .docx."
        )
    )

    if uploaded_files:
        file_data = [
            (file.name, file.getvalue())
            for file in uploaded_files
        ]

        digest_builder = hashlib.sha256()

        for name, data in file_data:
            digest_builder.update(name.encode("utf-8"))
            digest_builder.update(data)

        digest = digest_builder.hexdigest()

        if digest != st.session_state.docs_hash:
            st.session_state.sections = []
            st.session_state.chunks = []
            st.session_state.embeddings = None
            st.session_state.embedding_notice = None
            st.session_state.messages = []

            sections = []
            status = st.empty()
            progress = st.progress(0)

            try:
                for name, data in file_data:

                    def report_progress(done, total, message):
                        status.info(message)
                        progress.progress(
                            min(done / max(total, 1), 1.0)
                        )

                    sections.extend(
                        extract_document(
                            data,
                            name,
                            progress_callback=report_progress
                        )
                    )

                progress.empty()
                status.success(
                    "Document text extracted. Preparing search..."
                )

                chunks = split_sections(sections)

                st.session_state.sections = sections
                st.session_state.chunks = chunks
                st.session_state.docs_hash = digest
                st.session_state.doc_names = [
                    name for name, _ in file_data
                ]

                if chunks and os.getenv("GEMINI_API_KEY", "").strip():
                    embed_status = st.empty()
                    embed_progress = st.progress(0)

                    try:
                        def report_embedding(done, total, message):
                            embed_status.info(message)
                            embed_progress.progress(
                                min(done / max(total, 1), 1.0)
                            )

                        st.session_state.embeddings = embed_texts(
                            [chunk["text"] for chunk in chunks],
                            "RETRIEVAL_DOCUMENT",
                            progress_callback=report_embedding
                        )

                        embed_status.success("Search index ready.")
                        embed_progress.empty()

                    except Exception as exc:
                        st.session_state.embedding_notice = (
                            "Semantic search could not be prepared. "
                            "Keyword search will be used instead. "
                            f"Details: {exc}"
                        )
                        embed_status.warning(
                            "Using keyword search instead."
                        )
                        embed_progress.empty()

            except Exception as exc:
                st.session_state.docs_hash = None
                st.error(f"Document processing failed: {exc}")

        if st.session_state.chunks:
            st.success(
                f"Ready · {len(st.session_state.doc_names)} document(s) · "
                f"{len(st.session_state.chunks)} sections"
            )

            for name in st.session_state.doc_names:
                st.caption(name)

            if st.session_state.embedding_notice:
                st.warning(st.session_state.embedding_notice)
            elif st.session_state.embeddings:
                st.caption("Semantic + keyword search ready")

    else:
        st.info("Upload a document to begin.")

    st.divider()

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.caption(
        "Documents are extracted locally. Relevant passages are sent "
        "to Gemini when you ask a question."
    )


st.markdown(
    '<div class="title">Chat with your documents</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="sub">Ask naturally. Get clear answers grounded in your files.</div>',
    unsafe_allow_html=True
)


if not st.session_state.chunks:
    st.markdown("### Try asking")

    st.write(
        "• Summarize these documents.\n\n"
        "• Who is responsible for this agreement?\n\n"
        "• What are the important dates and amounts?\n\n"
        "• Compare the information across my files."
    )

else:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

            if message.get("sources"):
                with st.expander("Sources"):
                    for source in message["sources"]:
                        st.caption(
                            f"{source['source']} · {source['location']}"
                        )
                        st.write(source["text"])

    question = st.chat_input(
        "Ask anything about your documents..."
    )

    if question:
        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            try:
                query_vector = None

                if st.session_state.embeddings:
                    try:
                        query_vector = embed_texts(
                            [question],
                            "RETRIEVAL_QUERY"
                        )[0]
                    except Exception:
                        query_vector = None

                selected = find_relevant_chunks(
                    question,
                    st.session_state.chunks,
                    limit=8,
                    query_embedding=query_vector,
                    chunk_embeddings=st.session_state.embeddings
                )

                if not selected:
                    response = (
                        "I couldn't find sufficiently relevant information "
                        "in the uploaded documents. Try asking with a "
                        "specific name, date, amount or topic."
                    )
                    sources = []
                    st.markdown(response)

                else:
                    with st.spinner("Reviewing the relevant passages..."):
                        response = answer_question(
                            question,
                            selected,
                            st.session_state.messages[:-1]
                        )

                    sources = [
                        {
                            "source": chunk["source"],
                            "location": chunk["location"],
                            "text": chunk["text"]
                        }
                        for chunk in selected
                    ]

                    st.markdown(response)

                    with st.expander("Sources"):
                        for source in sources:
                            st.caption(
                                f"{source['source']} · {source['location']}"
                            )
                            st.write(source["text"])

            except Exception as exc:
                message = str(exc)

                if "503" in message or "UNAVAILABLE" in message:
                    response = (
                        "Gemini is temporarily busy. "
                        "Please try again shortly. Your documents are loaded."
                    )
                elif "504" in message or "DEADLINE_EXCEEDED" in message:
                    response = (
                        "Gemini took too long to respond. "
                        "Please try again. Your documents are loaded."
                    )
                else:
                    response = f"I couldn't generate an answer: {message}"

                sources = []
                st.error(response)

            st.session_state.messages.append({
                "role": "assistant",
                "content": response,
                "sources": sources
            })
