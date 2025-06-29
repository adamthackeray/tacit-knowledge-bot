import os
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from dotenv import load_dotenv
import uuid

load_dotenv()

class DocumentProcessor:
    def __init__(self):
        self.pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index = self.pc.Index(os.getenv("PINECONE_INDEX"))
        # Use sentence transformer that outputs 1024 dimensions
        self.embeddings = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Split documents into chunks
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
    
    def process_document(self, content: str, filename: str) -> dict:
        try:
            # Split into chunks
            chunks = self.text_splitter.split_text(content)
            
            # Generate embeddings and upload to Pinecone
            vectors = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"{filename}_{i}_{str(uuid.uuid4())[:8]}"
                embedding = self.embeddings.encode(chunk).tolist()
                
                vectors.append({
                    "id": chunk_id,
                    "values": embedding,
                    "metadata": {
                        "content": chunk,
                        "filename": filename,
                        "chunk_index": i
                    }
                })
            
            # Upload to Pinecone
            self.index.upsert(vectors)
            
            return {
                "status": "success",
                "chunks_processed": len(chunks),
                "filename": filename
            }
            
        except Exception as e:
            return {"status": "error", "message": str(e)}

doc_processor = DocumentProcessor()
