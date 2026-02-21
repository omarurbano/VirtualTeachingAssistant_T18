# Virtual Teaching Assistant (VTA)

## Project Overview

The Virtual Teaching Assistant (VTA) is a Multimodal AI-Driven Learning Assistant designed for the NVIDIA Deep Learning Institute (DLI) at Washington State University. The system provides grounded, transparent assistance for learners working with instructional notebooks, diagrams, and recorded content.

## Team Members

- **Omar Urbano-Rendon** - Computer Science student with minor in Mathematics
- **Niranjan Y. Sudinani** - Honors Computer Science student, Technical Lead
- **Don Manuel Jose** - Senior in Computer Science, ML and Data Engineering
- **Duncan Hintz** - Team Member

**Client:** Parteek Kumar (NVIDIA DLI University Ambassador)

## Project Objectives

1. **Mixture-of-Experts Architecture** - Deploy specialized AI modules for text, vision-language, and audio processing
2. **Intelligent Query Routing** - Dynamic routing using NeMo Guardrails
3. **Source-Grounded Retrieval** - RAG system with GPU-accelerated vector search and citation-backed responses
4. **Personalized Learning Support** - Adaptive responses based on student context
5. **Instructor Analytics Dashboard** - Learning insights from aggregated student queries

## Technical Stack

- **Framework:** NVIDIA NeMo, LangChain
- **Models:** all-MiniLM-L6-v2 (embeddings), Gemini 1.5 Flash (cloud inference)
- **Audio Processing:** NVIDIA Riva
- **Document Processing:** Unstructured library, YOLOX, Table-Transformer

## Sprint Progress

### Sprint 1 (1/20/2026 - 2/20/2026) - COMPLETED

**Completed Deliverables:**
- Project Requirements & Scope Document
- System Architecture Diagram (MoE implementation)
- Dataset & Data Governance Plan
- Evaluation Metrics Definition
- Sprint 1 Design Review Presentation
- Sprint 1 Technical Report

**Technical Accomplishments:**
- PDF Text Extraction using Unstructured library with page numbers and metadata
- YOLOX model for image detection and Table-Transformer for table extraction
- RAG pipeline using LangChain with Recursive Character Text Splitter (300 chars, 50 overlap)
- all-MiniLM-L6-v2 embeddings for 384-dimensional vector generation
- Vector Similarity Search with cosine similarity
- Audio-to-text transcription with timestamps
- Observability Tracing System and automated evaluation pipeline
- Vertex AI SDK Integration with Gemini 1.5 Flash

## Performance Targets

- Response Time: < 10 seconds (80% reduction from manual)
- Accuracy: > 85% on course-specific answers
- Concurrent Users: Support 30+ users
- Uptime: 99% availability

## Project Structure

```
VirtualTeachingAssistant_T18/
├── Sprints/              # Sprint documentation
├── Reports/             # Project reports
├── Code/                 # Source code
├── Data/                 # Datasets
├── Deployment/           # Deployment configs
├── Testing/              # Test strategies
├── Evaluation/           # Metrics and results
├── Reflections/          # Team reflections
├── Resources/            # Links and references
└── Rubric/              # Grading rubrics
```

## Documentation

- [Sprint 1 Report](Sprints/Sprint_1/sprint_report_template.md)

## YouTube

[Sprint 1 Video](https://youtu.be/nKkJCJVQLIY)
