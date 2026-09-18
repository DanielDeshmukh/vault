import pinecone
import cohere

pc = pinecone.Pinecone(api_key="pcsk_51kowd_4vknyxyhZbVj3mucgEqNDouayNhMSnbWWzdsy4cNtU4jH1DXGAmz6wewEPsG7jV")
idx = pc.Index("vault")

co = cohere.ClientV2(api_key="cohere_3JyLroF1j12Qu0aCjaRMwEKGLvIGv9e65tPgogUt4AIwff")
resp = co.embed(texts=["What are the code of conduct rules?"], model="embed-english-v3.0", input_type="search_query")
embedding = resp.embeddings.float[0]
print("Embedding dim:", len(embedding))

results = idx.query(vector=embedding, top_k=5, include_metadata=True, filter=None)
print("Results count:", len(results.get("matches", [])))
for m in results.get("matches", []):
    mid = m["id"]
    score = m["score"]
    title = m["metadata"].get("title", "?")
    print(f"  {mid} score={score:.4f} title={title}")
