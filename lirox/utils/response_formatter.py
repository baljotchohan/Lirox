"""
Lirox v0.8 — Response Formatter

Formats unified executor output into rich, structured responses
with sources, confidence, and verification status.
"""

from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum


class ConfidenceLevel(Enum):
    """Confidence levels for responses."""
    LOW = "🔴 Low"
    MEDIUM = "🟡 Medium"
    HIGH = "🟢 High"


class VerificationStatus(Enum):
    """Verification status."""
    VERIFIED = "✓ Verified"
    PARTIAL = "◐ Partially Verified"
    UNVERIFIED = "✗ Unverified"
    N_A = "N/A"


class ResponseFormatter:
    """Formats execution results into beautiful responses."""
    
    @staticmethod
    def format_response(execution_result: Dict) -> str:
        """
        Format execution result into beautiful response.
        
        Args:
            execution_result: Result from UnifiedExecutor.execute()
        
        Returns:
            Formatted response string
        """
        
        if execution_result.get("status") == "error":
            return ResponseFormatter._format_error(execution_result)
        
        mode = execution_result.get("mode", "unknown")
        
        if mode == "chat":
            return ResponseFormatter._format_chat(execution_result)
        elif mode == "research":
            return ResponseFormatter._format_research(execution_result)
        elif mode == "browser":
            return ResponseFormatter._format_browser(execution_result)
        elif mode == "hybrid":
            return ResponseFormatter._format_hybrid(execution_result)
        else:
            return execution_result.get("answer", "No response generated.")
    
    @staticmethod
    def _format_chat(result: Dict) -> str:
        """Format CHAT mode response."""
        return result.get("answer", "No response generated.")
    
    @staticmethod
    def _format_research(result: Dict) -> str:
        """Format RESEARCH mode response with sources."""
        
        parts = []
        
        # Main answer
        parts.append(result.get("answer", "No answer generated."))
        
        # Key findings
        if result.get("key_findings"):
            parts.append("\n### 🔍 Key Findings\n")
            for finding in result["key_findings"][:5]:
                confidence_emoji = "🟢" if finding.get("confidence") == "high" else "🟡" if finding.get("confidence") == "medium" else "🔴"
                parts.append(f"  {confidence_emoji} {finding.get('claim', '')}")
        
        # Sources
        if result.get("sources"):
            parts.append("\n### 📚 Sources\n")
            for i, source in enumerate(result["sources"][:5], 1):
                parts.append(f"  [{i}] {source.get('title', 'Unknown')} ({source.get('domain', 'N/A')})")
                parts.append(f"      {source.get('url', 'N/A')}\n")
        
        # Metadata
        parts.append(ResponseFormatter._format_metadata(result))
        
        return "\n".join(parts)
    
    @staticmethod
    def _format_browser(result: Dict) -> str:
        """Format BROWSER mode response."""
        
        parts = []
        
        # Main answer
        parts.append(result.get("answer", "No content extracted."))
        
        # Sources
        if result.get("sources"):
            parts.append("\n### 📄 Fetched Pages\n")
            for source in result["sources"]:
                parts.append(f"  • {source.get('title', 'Unknown')} ({source.get('method', 'unknown')})")
                parts.append(f"    {source.get('url', 'N/A')}\n")
        
        # Metadata
        parts.append(ResponseFormatter._format_metadata(result))
        
        return "\n".join(parts)
    
    @staticmethod
    def _format_hybrid(result: Dict) -> str:
        """Format HYBRID mode response (research + browser)."""
        
        parts = []
        
        # Main answer
        parts.append(result.get("answer", "No answer generated."))
        
        # Key findings
        if result.get("key_findings"):
            parts.append("\n### 🔍 Key Findings\n")
            for finding in result["key_findings"][:5]:
                confidence_emoji = "🟢" if finding.get("confidence") == "high" else "🟡" if finding.get("confidence") == "medium" else "🔴"
                parts.append(f"  {confidence_emoji} {finding.get('claim', '')}")
        
        # Enrichment summary
        if result.get("enrichment_summary"):
            summary = result["enrichment_summary"]
            parts.append("\n### ✓ Verification Summary\n")
            parts.append(f"  Sources analyzed: {summary.get('total_sources', 0)}")
            parts.append(f"  Verified sources: {summary.get('enriched_sources', 0)}")
            parts.append(f"  Verification rate: {summary.get('verification_rate', 0):.0%}")
        
        # Sources
        if result.get("sources"):
            parts.append("\n### 📚 Verified Sources\n")
            for i, source in enumerate(result["sources"][:5], 1):
                verification = "✓" if source.get("verification") == "verified" else "◐" if source.get("verification") == "partial" else "✗"
                parts.append(f"  [{i}] {verification} {source.get('title', 'Unknown')} ({source.get('domain', 'N/A')})")
                parts.append(f"      {source.get('url', 'N/A')}")
                parts.append(f"      Confidence: {source.get('confidence', 0):.0%}\n")
        
        # Metadata
        parts.append(ResponseFormatter._format_metadata(result))
        
        return "\n".join(parts)
    
    @staticmethod
    def _format_error(result: Dict) -> str:
        """Format error response."""
        return f"❌ Error: {result.get('error', 'Unknown error')}"
    
    @staticmethod
    def _format_metadata(result: Dict) -> str:
        """Format execution metadata."""
        
        parts = []
        
        # Confidence
        confidence = result.get("confidence", 0)
        confidence_level = (
            ConfidenceLevel.HIGH if confidence > 0.8 else
            ConfidenceLevel.MEDIUM if confidence > 0.5 else
            ConfidenceLevel.LOW
        )
        parts.append(f"\n### 📊 Metadata")
        parts.append(f"**Mode:** {result.get('mode', 'unknown').upper()}")
        parts.append(f"**Confidence:** {confidence_level.value} ({confidence:.0%})")
        
        # Verification status
        verification = result.get("verification_status", "n/a").lower()
        verification_emoji = (
            "✓" if verification == "verified" else
            "◐" if verification == "partial" else
            "✗" if verification == "unverified" else
            "─"
        )
        parts.append(f"**Verification:** {verification_emoji} {verification.title()}")
        
        # Execution time
        execution_time = result.get("execution_time", 0)
        parts.append(f"**Time:** {execution_time:.2f}s")
        
        # Source count
        if result.get("source_count"):
            parts.append(f"**Sources:** {result['source_count']}")
        
        # Fallback note
        if result.get("mode") != result.get("routing_confidence"):
            if result.get("fallback_mode"):
                parts.append(f"**Fallback:** {result['fallback_mode']}")
        
        return "\n".join(parts)


def format_for_display(execution_result: Dict) -> str:
    """Helper function to format and display result."""
    return ResponseFormatter.format_response(execution_result)
