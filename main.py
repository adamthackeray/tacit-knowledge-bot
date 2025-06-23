from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from openai import OpenAI
import os
from dotenv import load_dotenv
import PyPDF2
import docx
from pptx import Presentation
import io
import re
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json

load_dotenv()

app = FastAPI(title="Universal Knowledge Bot")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
documents = []

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory="static"), name="static")

def extract_text_from_pdf(file_content):
    pdf_file = io.BytesIO(file_content)
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    return text

def extract_text_from_docx(file_content):
    doc_file = io.BytesIO(file_content)
    doc = docx.Document(doc_file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

def extract_text_from_pptx(file_content):
    ppt_file = io.BytesIO(file_content)
    prs = Presentation(ppt_file)
    text = ""
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"
    return text

def parse_email_content(email_content):
    """Parse email content and extract relevant information"""
    try:
        # Handle both raw email text and structured data
        if isinstance(email_content, str):
            # Simple text-based email parsing
            lines = email_content.split('\n')
            
            subject = ""
            from_addr = ""
            body = ""
            
            in_body = False
            
            for line in lines:
                line = line.strip()
                
                if line.lower().startswith('subject:'):
                    subject = line[8:].strip()
                elif line.lower().startswith('from:'):
                    from_addr = line[5:].strip()
                elif line == "" and not in_body:
                    in_body = True
                elif in_body:
                    body += line + "\n"
            
            return {
                "subject": subject or "No Subject",
                "from": from_addr or "Unknown Sender", 
                "body": body.strip() or email_content,
                "type": "email"
            }
        else:
            return {
                "subject": "Email Content",
                "from": "Unknown",
                "body": str(email_content),
                "type": "email"
            }
            
    except Exception as e:
        return {
            "subject": "Email Content",
            "from": "Unknown", 
            "body": str(email_content),
            "type": "email"
        }

def find_relevant_documents(question, documents, threshold=1):
    """Find documents relevant to the question using keyword matching"""
    if not documents:
        return []
    
    stop_words = {'what', 'how', 'where', 'when', 'why', 'who', 'is', 'are', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'about', 'can', 'could', 'should', 'would', 'do', 'does', 'did'}
    
    question_words = [word.lower().strip('.,!?') for word in question.split() 
                     if len(word) > 2 and word.lower() not in stop_words]
    
    relevant_docs = []
    
    for doc in documents:
        content_lower = doc["content"].lower()
        relevance_score = sum(1 for word in question_words if word in content_lower)
        
        if relevance_score >= threshold:
            relevant_docs.append((doc, relevance_score))
    
    relevant_docs.sort(key=lambda x: x[1], reverse=True)
    return [doc[0] for doc in relevant_docs[:3]]

def should_use_documents(question, documents):
    """Determine if the question needs document context"""
    if not documents:
        return False, []
    
    document_indicators = [
        r'\b(our|my|the company|this document|according to|email|message)\b',
        r'\b(report|file|document|presentation|email)\b',
        r'\b(uploaded|provided|attached|sent)\b'
    ]
    
    question_lower = question.lower()
    
    if any(re.search(pattern, question_lower) for pattern in document_indicators):
        return True, find_relevant_documents(question, documents, threshold=0)
    
    relevant_docs = find_relevant_documents(question, documents, threshold=2)
    
    if relevant_docs:
        return True, relevant_docs
    else:
        general_patterns = [
            r'\b(what is|define|explain|how to|tell me about)\b',
            r'\b(general|generally|typical|usually|common)\b'
        ]
        
        if any(re.search(pattern, question_lower) for pattern in general_patterns):
            return False, []
        
        fallback_docs = find_relevant_documents(question, documents, threshold=1)
        return len(fallback_docs) > 0, fallback_docs

@app.get("/")
def read_root():
    return FileResponse('static/index.html')

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        filename = file.filename.lower()
        content = await file.read()
        
        if filename.endswith('.txt'):
            text_content = content.decode("utf-8")
        elif filename.endswith('.pdf'):
            text_content = extract_text_from_pdf(content)
        elif filename.endswith('.docx') or filename.endswith('.doc'):
            text_content = extract_text_from_docx(content)
        elif filename.endswith('.pptx') or filename.endswith('.ppt'):
            text_content = extract_text_from_pptx(content)
        elif filename.endswith('.eml') or filename.endswith('.msg'):
            # Email file
            email_text = content.decode("utf-8", errors='ignore')
            email_data = parse_email_content(email_text)
            text_content = f"SUBJECT: {email_data['subject']}\nFROM: {email_data['from']}\n\nCONTENT:\n{email_data['body']}"
        else:
            return {"status": "error", "message": f"Unsupported file type: {file.filename}. Supports: PDF, Word, PowerPoint, TXT, Email (.eml)"}
        
        if not text_content.strip():
            return {"status": "error", "message": f"No text extracted from {file.filename}"}
        
        documents.append({
            "content": text_content,
            "filename": file.filename,
            "file_type": filename.split('.')[-1]
        })
        
        return {
            "filename": file.filename,
            "status": "success",
            "message": f"Successfully processed {file.filename}! Total docs: {len(documents)}"
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error: {str(e)}"}

@app.post("/email")
async def process_email(
    subject: str = Form(...),
    from_email: str = Form(...),
    body: str = Form(...)
):
    """Process email content directly"""
    try:
        # Create email document
        email_content = f"SUBJECT: {subject}\nFROM: {from_email}\n\nCONTENT:\n{body}"
        
        documents.append({
            "content": email_content,
            "filename": f"Email_{subject[:30]}...",
            "file_type": "email"
        })
        
        return {
            "status": "success",
            "message": f"Email processed successfully! Subject: '{subject}'. Total docs: {len(documents)}"
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error processing email: {str(e)}"}

@app.post("/email/forward")
async def forward_email(email_text: str = Form(...)):
    """Process forwarded email content"""
    try:
        email_data = parse_email_content(email_text)
        
        email_content = f"SUBJECT: {email_data['subject']}\nFROM: {email_data['from']}\n\nCONTENT:\n{email_data['body']}"
        
        documents.append({
            "content": email_content,
            "filename": f"Email_{email_data['subject'][:30]}...",
            "file_type": "email"
        })
        
        return {
            "status": "success",
            "message": f"Forwarded email processed! Subject: '{email_data['subject']}'. Total docs: {len(documents)}"
        }
        
    except Exception as e:
        return {"status": "error", "message": f"Error processing forwarded email: {str(e)}"}

@app.post("/chat")
async def chat(question: str = Form(...)):
    try:
        use_docs, relevant_docs = should_use_documents(question, documents)
        
        if use_docs and relevant_docs:
            context_parts = []
            doc_names = []
            for doc in relevant_docs:
                doc_type = "📧" if doc['file_type'] == 'email' else "📄"
                context_parts.append(f"=== {doc_type} {doc['filename']} ===\n{doc['content']}")
                doc_names.append(doc['filename'])
            
            context = "\n\n".join(context_parts)
            prompt = f"Based on these documents and emails, answer the question:\n\n{context}\n\nQuestion: {question}\n\nAnswer:"
            source_info = f" (Based on: {', '.join(doc_names)})"
            
        elif documents and any(word in question.lower() for word in ["email", "message", "document"]):
            prompt = f"The user is asking about emails/documents, but I couldn't find relevant information in the uploaded files. Question: {question}\n\nPlease let them know that the information might not be in their uploaded content, but provide a general answer if possible."
            source_info = " (No relevant content found)"
            
        else:
            prompt = f"Answer this general question: {question}"
            source_info = " (General knowledge)"
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that can process both documents and emails. Be clear, concise, and cite sources. Format responses with proper paragraphs and bullet points when appropriate."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500
        )
        
        answer = response.choices[0].message.content
        
        return {
            "question": question, 
            "answer": answer,
            "source": source_info,
            "documents_used": len(relevant_docs) if use_docs else 0
        }
        
    except Exception as e:
        return {"question": question, "answer": f"Error: {str(e)}"}

@app.get("/documents")
def list_documents():
    return {
        "total_documents": len(documents),
        "documents": [
            {
                "filename": doc["filename"], 
                "type": doc["file_type"],
                "icon": "📧" if doc["file_type"] == "email" else "📄"
            } for doc in documents
        ]
    }
