import chromadb
import uuid
from sentence_transformers import SentenceTransformer
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


model = SentenceTransformer("all-MiniLM-L6-v2")


class LocalEmbeddingFunction(DefaultEmbeddingFunction):
    def __call__(self, texts):
        return model.encode(texts).tolist()


embedding_function = LocalEmbeddingFunction()


chroma_client = chromadb.PersistentClient(path="/Users/PV/PycharmProjects/meLlamo/pvelsDB.chroma")

collection = chroma_client.get_or_create_collection(name="pvels", embedding_function=embedding_function)


def add_document(doc_text, doc_id=None):
    if doc_id is None:
        doc_id = str(uuid.uuid4())
    collection.add(documents=[doc_text], ids=[doc_id])
    print(f"Added document with ID: {doc_id}")
    return doc_id # Return the doc_id so it can be stored in task_manager


def retrieve_context(query, n=3):
    results = collection.query(
        query_texts=[query],
        n_results=n,
        include=['documents'] # Only include documents, as 'ids' is not a valid include parameter
    )
    # The results object itself contains the 'ids' of the matched documents
    return results.get("documents", [[]])[0], results.get("ids", [[]])[0]


def get_all_documents():
    """
    Retrieves and returns all documents currently stored in the ChromaDB collection.
    """
    all_entries = collection.get(
        ids=collection.get()['ids'],
        include=['documents', 'metadatas']
    )
    return all_entries['documents']


# Debug code
# if __name__ == "__main__":
#     print("All documents in ChromaDB:")
#     documents = get_all_documents()
#     if documents:
#         for i, doc in enumerate(documents):
#             print(f"Document {i+1}: {doc}")
#     else:
#         print("No documents found in the collection.")

# collection.add(
#     documents=[
#         "This is a document about pineapple",
#         "This is a document about oranges"
#     ],
#     ids=["id1", "id2"]
# )
#
# results = collection.query(
#     query_texts=["This is a query document about hawaii"], # Chroma will embed this for you
#     n_results=2 # how many results to return
# )
# print(results)
#
