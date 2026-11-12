"""
Pruebas Unitarias para la Capa 3: RAG y Base Documental (NetDiagBench-L7)
"""

from src.core.contracts import ContextoRAGContract
from src.layer3_rag.retriever import RAGKnowledgeEngine


def test_rag_knowledge_engine_indexing():
    rag = RAGKnowledgeEngine()
    assert len(rag._chunks) > 0, "Debe indexar fragmentos de RFCs y SOPs"
    assert rag.verify_memory_budget() is True, "El uso de memoria debe ser <= 0.45 GB"


def test_rag_semantic_query():
    rag = RAGKnowledgeEngine()
    # Consulta sobre DNS
    dns_res = rag.query("NXDOMAIN authoritative BIND9", top_k=2)
    assert isinstance(dns_res, ContextoRAGContract)
    assert len(dns_res.chunks) == 2
    assert any("1035" in c.source_document or "dns" in c.source_document.lower() for c in dns_res.chunks)

    # Consulta sobre HTTP 502
    http_res = rag.query("502 Bad Gateway upstream connection refused", top_k=2)
    assert len(http_res.chunks) == 2
    assert any("9110" in c.source_document or "nginx" in c.source_document.lower() for c in http_res.chunks)


def test_rag_freezing():
    rag = RAGKnowledgeEngine()
    assert rag._is_frozen is False
    rag.freeze()
    assert rag._is_frozen is True


def test_rag_query_tls_certificates():
    rag = RAGKnowledgeEngine()
    tls_res = rag.query("TLS handshake certificate expired chain invalid", top_k=2)
    assert isinstance(tls_res, ContextoRAGContract)
    assert len(tls_res.chunks) == 2
    assert any("8446" in c.source_document or "tls" in c.source_document.lower() or "sop" in c.source_document.lower() for c in tls_res.chunks)


def test_rag_query_empty_or_nonsense():
    rag = RAGKnowledgeEngine()
    empty_res = rag.query("", top_k=2)
    assert isinstance(empty_res, ContextoRAGContract)
    assert len(empty_res.chunks) == 0

    nonsense_res = rag.query("xyzqwerty12345nonexistent", top_k=2)
    assert isinstance(nonsense_res, ContextoRAGContract)


def test_rag_memory_footprint_measurement():
    rag = RAGKnowledgeEngine()
    mem_mb = rag.get_memory_footprint_mb()
    assert 0.0 < mem_mb < 5.0  # Ultra-lightweight: should be around 0.02 MB
    assert rag.verify_memory_budget() is True


def test_rag_tokenization_technical_terms():
    rag = RAGKnowledgeEngine()
    tokens = rag._tokenize("BIND9 returned NXDOMAIN (RCODE 3) for service.corp:53 over UDP/IP")
    assert "bind9" in tokens
    assert "nxdomain" in tokens
    assert "rcode" in tokens
    assert "service.corp" in tokens or "service.corp:53" in tokens or "service" in tokens

