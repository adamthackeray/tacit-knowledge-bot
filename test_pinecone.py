from dotenv import load_dotenv
import os
from pinecone import Pinecone

load_dotenv()

try:
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    print("Pinecone connected successfully!")
    print("Available indexes:", pc.list_indexes())
except Exception as e:
    print("Error:", e)
