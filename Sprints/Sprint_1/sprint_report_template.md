# Sprint 1 Report (Dates from 1/20/2026 - 2/20/2026)

## YouTube link of Sprint * Video (Make this video unlisted)
https://www.youtube.com/watch?v=placeholder

## What's New (User Facing)
 * Project Requirements & Scope Document completed defining functional and non-functional requirements for the Virtual Teaching Assistant system
 * System Architecture Diagram finalized depicting the Mixture-of-Experts (MoE) implementation with query router and specialized expert modules
 * Dataset & Data Governance Plan established outlining indexing of Jupyter Notebooks, Workshop Manuals, presentation slides, PDF documents, diagrams, and recorded lecture content
 * Evaluation Metrics Definition document created specifying performance targets including 80% response time reduction and 85% accuracy threshold
 * Sprint 1 Design Review Presentation prepared for stakeholder review
 * Sprint 1 Technical Report documenting system design decisions and architectural rationale
 * Implemented PDF Text Extraction using the Unstructured library to pull text elements while maintaining page numbers and metadata for citation requirements
 * Deployed YOLOX model for image detection and Microsoft Table-Transformer for extracting complex tables into HTML representations
 * Built RAG pipeline using LangChain with Intelligent Document Chunking system (Recursive Character Text Splitter, 300 characters with 50-character overlap)
 * Integrated audio-to-text transcription with timestamps for lecture content retrieval

## Work Summary (Developer Facing)
During Sprint 1, the team focused on establishing the foundational requirements and system architecture for the Multimodal Virtual Teaching Assistant. The team refined the problem statement identifying the need for source-grounded, citation-backed responses that integrate text, vision-language, and audio understanding using a Mixture-of-Experts architecture. Key activities included reviewing related work in Retrieval Augmented Generation (RAG), multimodal AI, and MoE architectures; defining learner and instructor personas; identifying necessary datasets and modalities from NVIDIA DLI teaching materials; designing the end-to-end system architecture with specialized expert modules for text, vision, and audio processing; and establishing quantifiable success metrics and evaluation criteria. The technical implementation achieved significant milestones including PDF text extraction using the Unstructured library with preserved page numbers and metadata, visual data processing with YOLOX for image detection and Table-Transformer for table extraction into HTML format, and a complete RAG pipeline using LangChain with Recursive Character Text Splitter for 300-character chunks with 50-character overlap, all-MiniLM-L6-v2 embeddings for 384-dimensional vector generation, and cosine similarity search returning top-k relevant chunks with similarity scores. The team also established a reliability framework with Observability Tracing, automated evaluation pipelines, and Vertex AI SDK integration with Gemini 1.5 Flash for cloud inference. The team overcame challenges in determining the optimal routing mechanism for the MoE architecture and ensuring compliance with FERPA regulations for student data privacy. This sprint delivered all planned artifacts including the requirements document, architecture diagram, data governance plan, and evaluation metrics definition.

## Unfinished Work
All planned Sprint 1 deliverables have been completed. The project requirements and scope document, system architecture diagram, dataset and data governance plan, evaluation metrics definition, design review presentation, and technical report were all finalized within the sprint timeframe.

## Completed Issues/User Stories
 * Project Requirements & Scope Document
 * System Architecture Diagram
 * Dataset & Data Governance Plan
 * Evaluation Metrics Definition
 * Sprint 1 Design Review Presentation
 * Sprint 1 Technical Report
 * PDF Text Extraction Implementation
 * Image Detection and Table Extraction
 * RAG Pipeline Implementation
 * Audio-to-Text with Timestamps
  
 ## Incomplete Issues/User Stories
 No issues remained incomplete during Sprint 1. All planned user stories and deliverables were addressed within the sprint timeline.
  
## Code Files for Review
Please review the following code files, which were actively developed during this sprint, for quality:
 * [System Architecture Diagram]
 * [Requirements Specification Document]
 * [Evaluation Metrics Definition]
 * [RAG Pipeline Implementation]
 * [PDF Extraction Module]
 * [Audio Transcription Module]
 
## Retrospective Summary
Here's what went well:
  * Team effectively collaborated to define clear project scope and objectives for the Virtual Teaching Assistant
  * Comprehensive requirements gathering resulted in detailed functional and non-functional specifications
  * Strong alignment achieved on MoE architecture design with clear routing mechanisms for text, vision, and audio experts
  * Effective research into NVIDIA NeMo framework, RAG implementations, and citation-based grounding approaches
  * Clear identification of stakeholder needs for both students and instructors
  * Successfully implemented end-to-end RAG pipeline with source-grounded citations as promised in user stories
  * Established reliable cloud integration patterns with Vertex AI SDK for Gemini 1.5 Flash inference
 
Here's what we'd like to improve:
   * Begin parallel development of individual expert modules in subsequent sprints
   * Accelerate technical skill development in NVIDIA NeMo framework and GPU-accelerated pipelines
   * Establish earlier integration testing environments for system components
   * Increase frequency of client feedback sessions to validate design decisions
   * Expand testing coverage for the multimodal extraction pipeline
   
Here are changes we plan to implement in the next sprint:
   * Initiate implementation of the Query Processing and Routing Module
   * Begin development of the Text Expert module using NeMo LLMs
   * Set up vector database infrastructure for the RAG pipeline
   * Establish initial prototype for multimodal input processing
   * Begin audio data indexing preparation for NVIDIA Riva integration
   * Scale the RAG pipeline to handle larger document collections
