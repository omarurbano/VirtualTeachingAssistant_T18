# Sprint 2 Report (February 21, 2026 to March 20, 2026)

## YouTube link of Sprint 2 Video
*(To be added when video is uploaded - make this video unlisted)*

## What's New (User Facing)
 * **BLIP-2 Image Captioning**: Automatic generation of natural language descriptions for uploaded images, providing richer context for document understanding
 * **Tesseract OCR Integration**: Text extraction from images, charts, and diagrams - fully configured for Windows environment
 * **Multimodal PDF Processing**: Extraction of text, tables, and images from PDF documents with position tracking and structure preservation
 * **Direct Image Upload**: Users can now upload standalone images via the UI with drag-and-drop support and real-time processing
 * **Enhanced RAG Pipeline**: Multimodal retrieval that retrieves from text chunks, image captions, OCR text, and table content with confidence scores
 * **Responsive UI Design**: Terminal-themed dark interface with green accents, working across desktop and mobile devices

## Work Summary (Developer Facing)
Sprint 2 marked a critical transition from planning to implementation of the TradeBuzz Virtual Teaching Assistant's core intelligence. The team built robust multimodal data pipelines capable of extracting and processing text, images, tables, and audio from various document formats. Key implementations include BLIP-2 model integration for image captioning, Tesseract OCR configuration, Whisper for audio transcription, and a complete Flask REST API. The team overcame Windows-specific configuration challenges with Tesseract path settings and implemented graceful fallback mechanisms for model unavailability. A comprehensive frontend was developed with image upload capabilities, real-time status updates, and responsive design. All components were integrated into a cohesive Flask application with proper error handling, logging, and health check endpoints.

## Unfinished Work
The following items were planned but not fully completed in this sprint:
- Docker containerization final testing (Dockerfile created but pending production validation)
- Full Canvas LTI integration (planned for future sprints)
- NVIDIA DLI coursework integration (planned for future sprints)
- Advanced audio processing beyond basic transcription pipeline

## Completed Issues/User Stories
Here are links to the issues that we completed in this sprint:

 * GitHub Issue #1: Implement BLIP-2 image captioning integration
 * GitHub Issue #2: Configure Tesseract OCR for Windows environment
 * GitHub Issue #3: Build multimodal PDF extraction pipeline
 * GitHub Issue #4: Create image upload API endpoint
 * GitHub Issue #5: Implement sentence transformer embeddings
 * GitHub Issue #6: Build Flask REST API with all endpoints
 * GitHub Issue #7: Create responsive frontend UI
 * GitHub Issue #8: Implement vector similarity search
 * GitHub Issue #9: Add graceful fallback mechanisms
 * GitHub Issue #10: Set up logging infrastructure

 Reminders (Remove this section when you save the file):
  * Each issue should be assigned to a milestone
  * Each completed issue should be assigned to a pull request
  * Each completed pull request should include a link to a "Before and After" video
  * All team members who contributed to the issue should be assigned to it on GitHub
  * Each issue should be assigned story points using a label
  * Story points contribution of each team member should be indicated in a comment
  
## Incomplete Issues/User Stories
Here are links to issues we worked on but did not complete in this sprint:
 
 * N/A - All planned issues were completed in this sprint

## Code Files for Review
Please review the following code files, which were actively developed during this sprint, for quality:
 * [app.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/app.py) - Main Flask application with REST API endpoints
 * [image_analyzer.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/image_analyzer.py) - BLIP-2 and Tesseract integration for image analysis
 * [multimodal_processor.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/multimodal_processor.py) - Orchestrates multimodal document processing
 * [pdf_extractor.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/pdf_extractor.py) - PDF extraction with PyMuPDF
 * [multimodal_chunker.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/multimodal_chunker.py) - Chunking strategy for RAG
 * [embedding_manager.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/embedding_manager.py) - Sentence transformer embeddings
 * [vector_store.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/vector_store.py) - Vector similarity search implementation
 * [answer_generator.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/answer_generator.py) - Answer synthesis from retrieved chunks
 * [document_loader.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/DEMO_MAIN/document_loader.py) - Multi-format document loading
  
## Retrospective Summary
Here's what went well:
  * Successful integration of multiple AI models (BLIP-2, Tesseract, Whisper) into a cohesive pipeline
  * Effective Windows environment configuration for all required dependencies
  * Strong error handling and graceful degradation when models are unavailable
  * Clear separation of concerns across modules (extraction, processing, storage, generation)
  * Responsive UI that works across different screen sizes
  * Good documentation within code files for future maintenance

Here's what we'd like to improve:
   * More comprehensive unit testing coverage
   * Better performance optimization for large documents
   * More thorough documentation of API endpoints
   * Earlier integration testing with actual user workflows
   
Here are changes we plan to implement in the next sprint:
   * Complete Docker containerization with production-ready configuration
   * Add user authentication and session management
   * Implement Canvas LTI integration for WSU course integration
   * Add more robust error handling and retry logic
   * Improve performance metrics and monitoring
