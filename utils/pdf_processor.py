import io
import logging
from typing import Optional
import PyPDF2
import pdfplumber

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFProcessor:
    """Handles PDF text extraction with multiple fallback methods."""
    
    def __init__(self):
        self.logger = logger
    
    def extract_text(self, pdf_file) -> str:
        """
        Extract text from PDF using multiple methods for robustness.
        
        Args:
            pdf_file: Streamlit uploaded file object
            
        Returns:
            str: Extracted text content
        """
        try:
            # Reset file pointer
            pdf_file.seek(0)
            text = ""
            
            # Method 1: Try pdfplumber first (better for tables and complex layouts)
            try:
                with pdfplumber.open(io.BytesIO(pdf_file.read())) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
                    
                    if text.strip():
                        self.logger.info(f"Successfully extracted {len(text)} characters using pdfplumber")
                        return text
                        
            except Exception as e:
                self.logger.warning(f"pdfplumber extraction failed: {e}")
            
            # Method 2: Fallback to PyPDF2
            try:
                pdf_file.seek(0)  # Reset file pointer
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))
                
                fallback_text = ""
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        fallback_text += page_text + "\n"
                
                if fallback_text.strip():
                    self.logger.info(f"Successfully extracted {len(fallback_text)} characters using PyPDF2")
                    return fallback_text
                    
            except Exception as e:
                self.logger.error(f"PyPDF2 extraction also failed: {e}")
            
            # If both methods fail
            raise Exception("Não foi possível extrair texto do PDF usando nenhum método disponível")
            
        except Exception as e:
            self.logger.error(f"PDF processing error: {e}")
            raise Exception(f"Erro ao processar PDF: {str(e)}")
    
    def extract_text_in_chunks(self, pdf_file, pages_per_chunk: int = 20) -> list:
        """
        Extract text from PDF in chunks for better processing of large documents.
        
        Args:
            pdf_file: Streamlit uploaded file object
            pages_per_chunk: Number of pages to process per chunk
            
        Returns:
            list: List of text chunks with metadata
        """
        try:
            chunks = []
            pdf_file.seek(0)
            
            # Try pdfplumber first
            try:
                with pdfplumber.open(io.BytesIO(pdf_file.read())) as pdf:
                    total_pages = len(pdf.pages)
                    self.logger.info(f"Processing {total_pages} pages in chunks of {pages_per_chunk}")
                    
                    for start_page in range(0, total_pages, pages_per_chunk):
                        end_page = min(start_page + pages_per_chunk, total_pages)
                        chunk_text = ""
                        
                        for page_num in range(start_page, end_page):
                            page_text = pdf.pages[page_num].extract_text()
                            if page_text:
                                chunk_text += page_text + "\n"
                        
                        if chunk_text.strip():
                            chunks.append({
                                'text': chunk_text,
                                'start_page': start_page + 1,
                                'end_page': end_page,
                                'total_pages': total_pages
                            })
                    
                    if chunks:
                        self.logger.info(f"Extracted {len(chunks)} chunks using pdfplumber")
                        return chunks
                        
            except Exception as e:
                self.logger.warning(f"pdfplumber chunk extraction failed: {e}")
            
            # Fallback to PyPDF2
            try:
                pdf_file.seek(0)
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_file.read()))
                total_pages = len(pdf_reader.pages)
                
                for start_page in range(0, total_pages, pages_per_chunk):
                    end_page = min(start_page + pages_per_chunk, total_pages)
                    chunk_text = ""
                    
                    for page_num in range(start_page, end_page):
                        page_text = pdf_reader.pages[page_num].extract_text()
                        if page_text:
                            chunk_text += page_text + "\n"
                    
                    if chunk_text.strip():
                        chunks.append({
                            'text': chunk_text,
                            'start_page': start_page + 1,
                            'end_page': end_page,
                            'total_pages': total_pages
                        })
                
                if chunks:
                    self.logger.info(f"Extracted {len(chunks)} chunks using PyPDF2")
                    return chunks
                    
            except Exception as e:
                self.logger.error(f"PyPDF2 chunk extraction failed: {e}")
            
            raise Exception("Não foi possível extrair texto em blocos do PDF")
            
        except Exception as e:
            self.logger.error(f"PDF chunk processing error: {e}")
            raise Exception(f"Erro ao processar PDF em blocos: {str(e)}")
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize extracted text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            str: Cleaned text
        """
        # Basic text cleaning
        cleaned = text.replace('\x00', '')  # Remove null characters
        cleaned = ' '.join(cleaned.split())  # Normalize whitespace
        
        return cleaned
