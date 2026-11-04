from src.pdf_tools import split_pages, find_relevant_chunks

def test_page_numbers_preserved():
    chunks=split_pages([{"page":7,"text":"A short passage about data security and passwords."}],size=20,overlap=3)
    assert chunks and all(c["page"]==7 for c in chunks)

def test_matching_passage_ranks_first():
    chunks=[
        {"page":1,"text":"Rainfall patterns and seasonal climate changes."},
        {"page":2,"text":"Password attacks exploit weak authentication and stolen credentials."}
    ]
    assert find_relevant_chunks("How do password attacks work?",chunks)[0]["page"]==2
