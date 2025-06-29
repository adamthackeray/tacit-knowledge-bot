from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Simple Knowledge Bot")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
documents = []

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"message": "Simple Knowledge Bot running!"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith('.txt'):
            return {"error": "Only .txt files supported"}
        
        content = await file.read()
        text_content = content.decode("utf-8")
        documents.append({"content": text_content, "filename": file.filename})
        
        return {"filename": file.filename, "status": "success", "message": f"Uploaded successfully. Total docs: {len(documents)}"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/chat")
async def chat(question: str):
    try:
        context = "\n\n".join([doc["content"] for doc in documents])
        
        if context:
            prompt = f"Based on these documents:\n{context}\n\nQuestion: {question}"
        else:
            prompt = question
            
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        return {"question": question, "answer": response.choices[0].message.content}
    except Exception as e:
        return {"error": str(e)}
