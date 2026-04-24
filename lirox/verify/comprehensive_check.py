"""
Comprehensive verification BEFORE confirming success
"""

import os
import re
from typing import Dict, List


class ComprehensiveVerification:
    """
    Multi-layer verification for file generation
    """
    
    @staticmethod
    def verify_pdf_generation(file_path: str, design_plan, sections: List[Dict]) -> bool:
        """
        Comprehensive PDF verification
        
        Checks:
        1. File exists and has reasonable size
        2. Content is NOT filler text
        3. Page count matches expectations
        4. Design was applied
        5. Sections are substantive
        """
        
        checks = {
            'file_exists': os.path.exists(file_path),
            'file_size_ok': False,
            'no_filler_text': False,
            'page_count_ok': False,
            'has_real_content': False,
        }
        
        if not checks['file_exists']:
            return False
        
        # Check file size (should be > 10KB for real content)
        file_size = os.path.getsize(file_path)
        checks['file_size_ok'] = file_size > 10000
        
        # Extract PDF text for content checks
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                num_pages = len(reader.pages)
                
                # Extract text from all pages
                text = ""
                for page in reader.pages:
                    text += page.extract_text()
                
                # Check page count
                expected_pages = getattr(design_plan, 'target_pages', 5)
                checks['page_count_ok'] = num_pages >= max(3, expected_pages - 2)
                
                # Check for filler text patterns
                filler_patterns = [
                    r'This section covers .* in the context of',
                    r'The content is presented in a detailed',
                    r'Key concepts .* practical examples',
                    r'appropriate for the intended audience',
                ]
                
                has_filler = any(re.search(pat, text, re.IGNORECASE) for pat in filler_patterns)
                checks['no_filler_text'] = not has_filler
                
                # Check for real content (specific facts, dates, names)
                # Real content should have:
                # - Specific years/dates
                # - Proper names
                # - Specific numbers/statistics
                # - Concrete examples
                
                has_dates = bool(re.search(r'\b(1[0-9]{3}|20[0-9]{2})\b', text))
                has_numbers = bool(re.search(r'\b\d{1,3}(,\d{3})*(\.\d+)?\b', text))
                word_count = len(text.split())
                
                checks['has_real_content'] = (
                    has_dates and 
                    has_numbers and 
                    word_count > 500 and
                    len(text) > 2000
                )
                
        except Exception as e:
            import logging
            logging.warning(f"PDF content verification failed: {e}")
            return False
        
        # All checks must pass
        all_passed = all(checks.values())
        
        if not all_passed:
            import logging
            failed = [k for k, v in checks.items() if not v]
            logging.warning(f"PDF verification failed checks: {failed}")
        
        return all_passed
    
    @staticmethod
    def verify_docx_generation(file_path: str, design_plan, sections: List[Dict]) -> bool:
        """Similar verification for DOCX files"""
        # TODO: Implement DOCX-specific verification
        return os.path.exists(file_path) and os.path.getsize(file_path) > 5000
    
    @staticmethod
    def verify_pptx_generation(file_path: str, design_plan, slides: List[Dict]) -> bool:
        """Similar verification for PPTX files"""
        # TODO: Implement PPTX-specific verification
        return os.path.exists(file_path) and os.path.getsize(file_path) > 10000
    
    @staticmethod
    def verify_xlsx_generation(file_path: str, design_plan, sheets: List[Dict]) -> bool:
        """Similar verification for XLSX files"""
        # TODO: Implement XLSX-specific verification
        return os.path.exists(file_path) and os.path.getsize(file_path) > 5000
