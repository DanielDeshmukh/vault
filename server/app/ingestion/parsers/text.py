class TextParser:
    """Parse plain text content."""
    
    async def parse(self, content: str) -> str:
        """
        Parse plain text content.
        
        Args:
            content: Plain text string
            
        Returns:
            Cleaned text
        """
        if not content:
            return ""
        
        # Clean up the text
        lines = content.splitlines()
        cleaned_lines = []
        
        for line in lines:
            # Strip whitespace
            stripped = line.strip()
            # Skip empty lines but preserve paragraph breaks
            if stripped:
                cleaned_lines.append(stripped)
        
        # Join with double newlines for paragraph separation
        return "\n\n".join(cleaned_lines)
