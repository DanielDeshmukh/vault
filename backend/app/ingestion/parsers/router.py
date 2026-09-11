from app.ingestion.parsers.pdf import PDFParser
from app.ingestion.parsers.docx import DOCXParser
from app.ingestion.parsers.html import HTMLParser
from app.ingestion.parsers.text import TextParser


class ParserRouter:
    """Routes content to the appropriate parser based on source type."""
    
    def __init__(self):
        self.parsers = {
            "pdf": PDFParser(),
            "docx": DOCXParser(),
            "html": HTMLParser(),
            "text": TextParser(),
            "slack": TextParser(),  # Slack exports are JSON/text
            "confluence": HTMLParser(),  # Confluence exports HTML
            "transcript": TextParser(),
            "policy": TextParser(),
            "csv": TextParser(),
        }
    
    async def parse(self, content: str, source_type: str) -> str:
        """
        Parse content based on source type.
        
        Args:
            content: Raw content string (can be base64 for binary formats)
            source_type: The source type identifier
            
        Returns:
            Parsed plain text content
        """
        parser = self.parsers.get(source_type, TextParser())
        return await parser.parse(content)
