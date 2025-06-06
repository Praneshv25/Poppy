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


def add_document(doc_text):
    doc_id = str(uuid.uuid4())
    collection.add(documents=[doc_text], ids=[doc_id])
    print(f"Added document with ID: {doc_id}")


def retrieve_context(query, n=3):
    results = collection.query(
        query_texts=[query],
        n_results=n
    )
    matches = results.get("documents", [[]])[0]  # top list of matches
    return matches


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
