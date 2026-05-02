"""Lirox v1.1 — RAG (Retrieval-Augmented Generation) Module

Local-first knowledge retrieval using ChromaDB for vector storage.
Supports ingesting local files (txt, md, py, json, pdf) and retrieving
relevant context for every query.
"""
from lirox.rag.store import RAGStore
from lirox.rag.ingest import RAGIngestor
from lirox.rag.retriever import RAGRetriever

__all__ = ["RAGStore", "RAGIngestor", "RAGRetriever"]
