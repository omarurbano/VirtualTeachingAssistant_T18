#!/usr/bin/env python
"""
CPT_S 421 VTA Demo Script
=========================
A simple demonstration script for the client meeting.

This script shows how the VTA Document RAG system works.
Run this to see the system in action from the command line.

Author: CPT_S 421 Development Team
"""

import os
import sys

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def print_header(title):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")

def print_step(step, message):
    """Print a step message."""
    print(f"[{step}] {message}")
    import time
    time.sleep(0.3)

def main():
    """Run the demo."""
    print_header("CPT_S 421 VTA - Document RAG System Demo")
    
    print("""
This demo will show you how the Document Q&A system works:

1. Load a PDF document
2. Ask questions about the content
3. Get answers with proper citations

Let's begin...
""")
    
    # Import the RAG components
    print_step("1", "Initializing the RAG Pipeline...")
    
    try:
        # Try to import our modules
        from document_loader import MultiFileLoader
        from embedding_manager import create_embedding_manager
        from vector_store import InMemoryVectorStore
        from citation_tracker import CitationTracker
        from answer_generator import AnswerGenerator
        
        print("     ✓ All modules loaded successfully")
        
    except ImportError as e:
        print(f"     ✗ Import error: {e}")
        print("\nPlease install dependencies: pip install -r requirements.txt")
        return
    
    # Initialize components
    print_step("2", "Setting up components...")
    
    # Create document loader
    document_loader = MultiFileLoader(chunk_size=1000, chunk_overlap=100)
    print("     ✓ Document Loader created")
    
    # Create embedding manager
    embedding_manager = create_embedding_manager(provider='sentence-transformers')
    print("     ✓ Embedding Manager initialized")
    
    # Create vector store
    dimension = embedding_manager.get_embedding_dimension()
    vector_store = InMemoryVectorStore(dimension=dimension)
    print("     ✓ Vector Store created")
    
    # Create citation tracker
    citation_tracker = CitationTracker(max_citations=10)
    print("     ✓ Citation Tracker ready")
    
    # Create answer generator
    answer_generator = AnswerGenerator(min_confidence_threshold=0.3)
    print("     ✓ Answer Generator ready")
    
    # Find the PDF
    pdf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "my_document.pdf")
    
    if not os.path.exists(pdf_path):
        print(f"\n[!] Demo PDF not found: {pdf_path}")
        print("    Please ensure my_document.pdf exists in the project folder")
        return
    
    print_step("3", f"Loading document: {os.path.basename(pdf_path)}")
    
    # Load and chunk the document
    chunks = document_loader.load_and_chunk_file(pdf_path)
    
    if not chunks:
        print("     ✗ Failed to load document")
        return
    
    print(f"     ✓ Loaded {len(chunks)} chunks")
    
    # Generate embeddings
    print_step("4", "Generating embeddings...")
    
    embeddings = embedding_manager.embed_documents(chunks)
    print(f"     ✓ Generated {len(embeddings)} embeddings")
    
    # Add to vector store
    vector_store.add_documents(chunks, embeddings)
    print("     ✓ Added to vector database")
    
    # Demo questions
    print_header("Ready to Answer Questions!")
    
    demo_questions = [
        "What is the main topic of this document?",
        "What are the key points mentioned?",
        "Summarize the content"
    ]
    
    print("You can now ask questions. Try these examples:")
    for i, q in enumerate(demo_questions, 1):
        print(f"  {i}. {q}")
    
    print("\n" + "=" * 70)
    print("To start the web interface, run:")
    print("  python app.py")
    print("=" * 70)
    
    # Interactive mode
    print("\n[Interactive Mode] Type your questions below (or 'quit' to exit)\n")
    
    while True:
        try:
            query = input("Your question: ").strip()
            
            if not query:
                continue
            if query.lower() in ['quit', 'exit', 'q']:
                break
            
            print("\n--- Searching ---")
            
            # Embed query
            query_embedding = embedding_manager.embed_query(query)
            
            # Search
            results = vector_store.similarity_search(query_embedding, k=3)
            
            if not results:
                print("No relevant content found in the document.\n")
                continue
            
            print(f"Found {len(results)} relevant passages\n")
            
            # Show results
            print("--- Retrieved Content ---")
            for i, result in enumerate(results, 1):
                score = result.metadata.get('similarity_score', 0)
                content = result.page_content[:200]
                print(f"\n[{i}] Relevance: {score:.2%}")
                print(f"    {content}...")
            
            # Generate answer
            print("\n--- AI Answer ---")
            
            # Prepare retrieved data
            retrieved_data = []
            for r in results:
                retrieved_data.append({
                    'content': r.page_content,
                    'metadata': r.metadata,
                    'similarity_score': r.metadata.get('similarity_score', 0)
                })
            
            # Generate answer
            answer = answer_generator.generate(
                query=query,
                retrieved_results=retrieved_data,
                total_documents=1
            )
            
            print(answer.answer_text)
            
            # Show citations
            if results:
                print("\n--- Citations ---")
                for i, r in enumerate(results, 1):
                    metadata = r.metadata
                    source = metadata.get('filename', 'Unknown')
                    page = metadata.get('page_number', 'N/A')
                    score = metadata.get('similarity_score', 0)
                    
                    print(f"\n[{i}] {source} (Page {page})")
                    print(f"    Relevance: {score:.2%}")
                    print(f"    \"{r.page_content[:150]}...\"")
            
            print()
            
        except EOFError:
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n[Demo complete!]")


if __name__ == '__main__':
    main()
