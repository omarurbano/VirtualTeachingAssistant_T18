#!/usr/bin/env python
"""
Multi-File RAG System with Local AI
==================================================
This showcases the RAG system processing a PDF document
with real-time AI reasoning using local models.
"""

import os
import sys
import time
import logging
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger()

# Disable verbose library logging
logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
logging.getLogger('transformers').setLevel(logging.WARNING)

# File path - use local PDF in the project folder
PDF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_document.pdf")

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def print_progress(step, message):
    """Print a progress step."""
    print(f"[{step}] {message}")
    time.sleep(0.3)

def initialize_rag():
    """Initialize the RAG pipeline."""
    print_progress("1", "Initializing RAG Pipeline...")
    
    from enhanced_rag_pipeline import EnhancedRAGPipeline
    
    rag = EnhancedRAGPipeline()
    print(f"      [OK] Pipeline initialized")
    print(f"      [OK] Embedding model: sentence-transformers (all-MiniLM-L6-v2)")
    
    return rag

def load_document(rag, pdf_path):
    """Load and process the PDF document."""
    print_progress("2", f"Loading document: {os.path.basename(pdf_path)}")
    
    if not os.path.exists(pdf_path):
        print(f"      [X] File not found: {pdf_path}")
        return None
    
    result = rag.add_file(pdf_path)
    
    if result.get('success'):
        print(f"      [OK] Successfully loaded {result.get('chunks_created')} chunks")
        print(f"      [OK] Document ID: {result.get('document_id')}")
        return result
    else:
        print(f"      [X] Failed to load document: {result.get('error')}")
        return None

def initialize_local_llm():
    """Initialize local LLM for answer generation."""
    print_progress("3", "Initializing Local AI Model (Ollama)...")
    
    try:
        # Try Ollama with langchain_ollama import
        try:
            from langchain_ollama import OllamaLLM
            print("      >> Loading Ollama model (llama3.2:1b)...")
            
            llm = OllamaLLM(
                model="llama3.2:1b",
                temperature=0.3,
            )
            
            # Test the connection
            test_response = llm.invoke("Hello")
            print(f"      [OK] Local AI Model ready")
            return llm
            
        except ImportError:
            # Fallback to old langchain import
            from langchain_community.llms import Ollama
            print("      >> Loading Ollama model (llama3.2:1b)...")
            
            llm = Ollama(
                model="llama3.2:1b",
                temperature=0.3,
                verbose=False
            )
            
            # Test the connection
            test_response = llm.invoke("Hello")
            print(f"      [OK] Local AI Model ready")
            return llm
        
    except Exception as ollama_error:
        print(f"      [!] Ollama not available: {ollama_error}")
        
        # Fallback to GPT4All
        try:
            from langchain_community.llms import GPT4All
            
            print("      >> Trying GPT4All fallback...")
            
            llm = GPT4All(
                model="gpt4all-falcon-q4_0.gguf",
                verbose=False
            )
            
            print(f"      [OK] Local AI Model ready (GPT4All)")
            return llm
            
        except Exception as e:
            print(f"      [!] Could not initialize any local LLM: {e}")
            print(f"      >> Falling back to basic retrieval mode")
            return None

def process_query(rag, llm, query_text):
    """Process a query with AI reasoning."""
    print_progress("4", f"Processing query: \"{query_text}\"")
    
    # Get search results first
    results = rag.query(query_text, k=4)
    
    if not results.get('success'):
        print(f"      [X] Query failed: {results.get('error')}")
        return
    
    print(f"      [OK] Retrieved {results.get('num_results')} relevant passages")
    
    # Display retrieved content
    print("\n" + "-" * 70)
    print("RETRIEVED CONTENT:")
    print("-" * 70)
    
    for i, r in enumerate(results.get('results', []), 1):
        content = r['content']
        metadata = r['metadata']
        score = r.get('similarity_score', 0)
        
        # Get page info from various possible metadata keys
        page_info = metadata.get('page_number') or metadata.get('page') or metadata.get('source', '')
        if not page_info:
            # Try to extract page from source if it's a PDF
            source = metadata.get('source', '')
            if '.pdf' in source.lower():
                page_info = f"See source: {os.path.basename(source)}"
            else:
                page_info = 'N/A'
        
        print(f"\n[Passage {i}] (Relevance: {score:.2%})")
        print(f"  Source: {metadata.get('filename', 'unknown')}")
        print(f"  Location: {page_info}")
        print(f"  Content: {content[:300]}..." if len(content) > 300 else f"  Content: {content}")
    
    print("\n" + "-" * 70)
    
    # If we have LLM, generate answer with reasoning
    if llm:
        print("\n" + "-" * 70)
        print("AI ANALYSIS & REASONING:")
        print("-" * 70)
        
        # Build context from retrieved content
        context = "\n\n".join([
            f"[{i+1}] {r['content']}"
            for i, r in enumerate(results.get('results', []))
        ])
        
        # Create prompt with reasoning
        prompt = f"""Based on the following context from the document, answer the question.
Include your reasoning process and cite the sources.

CONTEXT:
{context}

QUESTION: {query_text}

ANSWER (with reasoning):"""

        print("  >> Generating answer with local AI...")
        
        try:
            # Get AI response
            answer = llm.invoke(prompt)
            print(f"\n{answer}")
            
            # Show the source paragraphs used for verification
            print("\n" + "-" * 70)
            print("SOURCE PARAGRAPHS USED BY AI:")
            print("-" * 70)
            for i, r in enumerate(results.get('results', []), 1):
                content = r['content']
                metadata = r['metadata']
                filename = metadata.get('filename', 'unknown')
                print(f"\n[{i}] Source: {filename}")
                print(f"    Relevance: {r.get('similarity_score', 0):.2%}")
                print(f"    Full content:\n    {content}")
                print()
        except Exception as e:
            print(f"  [!] AI generation error: {e}")
            print("  >> Showing retrieved content as answer")
    else:
        # Show formatted citations
        print("\nCITATIONS:")
        print("-" * 70)
        print(results.get('citations', 'No citations available'))

def main():
    """Main function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Multi-File RAG Client')
    parser.add_argument('--question', '-q', type=str, help='Question to ask (optional, defaults to interactive mode)')
    parser.add_argument('--pdf', '-p', type=str, default=None, help='Path to PDF file (optional, defaults to my_document.pdf)')
    args = parser.parse_args()
    
    # Override PDF path if provided
    global PDF_PATH
    if args.pdf:
        PDF_PATH = args.pdf
    
    print_header("MULTI-FILE RAG SYSTEM")
    
    print("This showcases:")
    print("  * PDF document processing")
    print("  * Semantic embeddings with sentence-transformers")
    print("  * Local AI for answer generation (Ollama)")
    print("  * Source citations with location tracking")
    
    # Step 1: Initialize RAG
    rag = initialize_rag()
    
    # Step 2: Load document
    doc_result = load_document(rag, PDF_PATH)
    if not doc_result:
        print("\n[X] Failed to load document")
        return
    
    # Step 3: Initialize local LLM
    llm = initialize_local_llm()
    
    # Step 4: Query mode
    if args.question:
        # Single question mode (non-interactive)
        process_query(rag, llm, args.question)
    else:
        # Interactive mode
        print_header("QUERY MODE")
        print("Enter your questions about the document (or 'quit' to exit)\n")
        
        while True:
            try:
                query = input("Your question: ").strip()
                
                if not query:
                    continue
                if query.lower() in ['quit', 'exit', 'q']:
                    break
                
                print()
                process_query(rag, llm, query)
                print()
                
            except EOFError:
                # Handle EOF gracefully (when input is piped)
                print("\n\n[COMPLETE - Input ended]")
                break
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    
if __name__ == '__main__':
    main()
