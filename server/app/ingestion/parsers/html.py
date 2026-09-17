from bs4 import BeautifulSoup


class HTMLParser:
    """Parse HTML content."""
    
    async def parse(self, content: str) -> str:
        """
        Parse HTML content.
        
        Args:
            content: HTML string
            
        Returns:
            Extracted text
        """
        try:
            soup = BeautifulSoup(content, "html.parser")
            
            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()
            
            # Get text
            text = soup.get_text(separator="\n", strip=True)
            
            # Clean up multiple newlines
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            
            return "\n".join(lines)
            
        except Exception as e:
            return f"[HTML parsing error: {str(e)}]"
