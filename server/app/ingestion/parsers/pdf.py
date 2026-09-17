import base64
from io import BytesIO


class PDFParser:
    """Parse PDF documents."""
    
    async def parse(self, content: str) -> str:
        """
        Parse PDF content.
        
        Args:
            content: Base64-encoded PDF content
            
        Returns:
            Extracted text
        """
        try:
            from pypdf import PdfReader
            
            # Decode base64
            pdf_bytes = base64.b64decode(content)
            pdf_file = BytesIO(pdf_bytes)
            
            # Extract text
            reader = PdfReader(pdf_file)
            text_parts = []
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            
            return "\n\n".join(text_parts)
            
        except Exception as e:
            return f"[PDF parsing error: {str(e)}]"
