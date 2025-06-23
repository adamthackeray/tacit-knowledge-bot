import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from langchain_openai import OpenAIEmbeddings

load_dotenv()

class RAGService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index = self.pc.Index(os.getenv("PINECONE_INDEX"))
        self.embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))
        
    def query(self, question: str) -> str:
        try:
            question_embedding = self.embeddings.embed_query(question)
            results = self.index.query(
                vector=question_embedding,
                top_k=3,
                include_metadata=True
            )
            
            context = ""
            if results.matches:
                context = "\n\n".join([match.metadata["content"] for match in results.matches])
            
            if context:
                prompt = f"Based on the following context, answer the question. If the answer is not in the context, say so.\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:"
            else:
                prompt = f"No relevant documents found. Please answer this general question: {question}"
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful knowledge assistant that answers questions based on provided context."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300
            )
            return response.choices[0].message.content
            
        except Exception as e:
            return f"Error: {str(e)}"

rag_service = RAGService()
