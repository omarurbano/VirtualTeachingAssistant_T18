# Sprint 3 Report (March 20, 2026 to April 30, 2026)

## YouTube link of Sprint 3 Video
https://youtu.be/2ZYfVHWiXf4

## What's New (User Facing)
 * **Video and Audio Transcription**: Teachers can now import lecture recordings from Google Drive, automatically transcribed using Gemini 2.0 Flash API with speaker identification and timestamps
 * **Google Drive OAuth Integration**: Seamless Drive folder linking per course with secure OAuth 2.0 authentication flow
 * **Student Course Enrollment**: Students can enroll in courses using course codes with real-time card-based UI updates
 * **Instructor Analytics Dashboard**: Real-time learning analytics with confusion heatmaps, engagement statistics, and at-risk student detection
 * **Clickable Citations**: Enhanced citation system with clickable links to source documents and timestamps for media content
 * **Unified Document Processor**: Gemini-powered document processing supporting PDF, DOCX, images, audio, and video with vector embeddings
 * **Supabase Database Integration**: Full backend migration to Supabase with proper schema for users, courses, enrollments, queries, and materials
 * **Responsive Instructor Dashboard**: Terminal-themed dark interface with course management, analytics, and real-time data visualization using Chart.js
 * **Media File Support**: Extended file type support including MP4, MOV, MP3, WAV, and other video/audio formats with automatic MIME type detection

## Work Summary (Developer Facing)
Sprint 3 marked a significant milestone with the alpha prototype implementation of the Virtual Teaching Assistant system. The team successfully integrated Google Drive OAuth for media imports, implemented video and audio transcription using Gemini 2.0 Flash API with speaker diarization and timestamp extraction. The backend was fully migrated to use Supabase as the primary database, with tables for users, courses, enrollments, queries, course materials, and Google Drive links. A comprehensive Express.js API server was developed on port 3000, providing authentication, course CRUD operations, enrollment management, and analytics endpoints. The student frontend enables course enrollment via course codes with WSU-themed Bootstrap 5 styling. The instructor dashboard features a terminal-inspired dark theme with dynamic course cards, real-time analytics visualizations using Chart.js (heatmaps, doughnut charts, line graphs), and at-risk student detection based on query confidence scores. The unified document processor (unified_document_processor.py) was enhanced to handle multimodal content with Gemini Embedding 2.0 for vector generation. Project structure was reorganized with Python backend code moved to Code/backend, frontend to Code/frontend, and documentation to Code/docs. Media transcription workflow stores transcripts with speaker segments, timestamps, and tone analysis while deleting original files after processing for storage efficiency.

## Unfinished Work
The following items were planned but not fully completed in this sprint:
- WebSocket integration for real-time query updates (pending infrastructure setup)
- Predictive analytics model for student performance forecasting
- Production deployment with Nginx reverse proxy (in progress)
- Mobile responsive testing across all device sizes
- Comprehensive end-to-end test suite automation

## Completed Issues/User Stories
Here are links to the issues that we completed in this sprint:

 * GitHub Issue #11: Implement Google Drive OAuth integration for course materials
 * GitHub Issue #12: Build video and audio transcription with Gemini 2.0 Flash API
 * GitHub Issue #13: Create Supabase database schema and migration
 * GitHub Issue #14: Develop Express.js backend API server with authentication
 * GitHub Issue #15: Build student frontend with course enrollment
 * GitHub Issue #16: Implement instructor analytics dashboard with Chart.js
 * GitHub Issue #17: Add clickable citations with source document links
 * GitHub Issue #18: Create media processor for transcription pipeline
 * GitHub Issue #19: Reorganize project structure (backend, frontend, docs separation)
 * GitHub Issue #20: Implement at-risk student detection algorithm
 * GitHub Issue #21: Add real-time engagement tracking and visualization
 * GitHub Issue #22: Build course management CRUD operations

 Reminders (Remove this section when you save the file):
   * Each issue should be assigned to a milestone
   * Each completed issue should be assigned to a pull request
   * Each completed pull request should include a link to a "Before and After" video
   * All team members who contributed to the issue should be assigned to it on GitHub
   * Each issue should be assigned story points using a label
   * Story points contribution of each team member should be indicated in a comment
   
## Incomplete Issues/User Stories
Here are links to issues we worked on but did not complete in this sprint:
  
 * WebSocket real-time updates for query responses (pending)
 * Mobile app development for iOS/Android (planned for future sprints)
 * Full NVIDIA DLI coursework integration (deferred to Sprint 4)

## Code Files for Review
Please review the following code files, which were actively developed during this sprint, for quality:
 * [Code/backend/app.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/Code/backend/app.py) - Main Flask application with RAG API and unified document processing
 * [Code/backend/unified_document_processor.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/Code/backend/unified_document_processor.py) - Gemini-powered multimodal document processor
 * [Code/backend/gdrive/media_processor.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/Code/backend/gdrive/media_processor.py) - Video/audio transcription with Gemini 2.0 Flash
 * [Code/backend/gdrive/oauth.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/Code/backend/gdrive/oauth.py) - Google Drive OAuth integration
 * [server/index.js](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/server/index.js) - Express.js API server with Supabase integration
 * [server/db.js](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/server/db.js) - Supabase database client configuration
 * [Code/frontend/static/studentHome.js](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/Code/frontend/static/studentHome.js) - Student frontend course enrollment
 * [Code/frontend/instructor/app.py](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/Code/frontend/instructor/app.py) - Instructor UI server
 * [Code/docs/ALPHA_PROTOTYPE_DESCRIPTION.md](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/Code/docs/ALPHA_PROTOTYPE_DESCRIPTION.md) - Alpha prototype documentation
 * [Code/docs/VIDEO_AUDIO_TRANSCRIPTION_FEATURE.md](https://github.com/omarurbano/VirtualTeachingAssistant_T18/blob/main/Code/docs/VIDEO_AUDIO_TRANSCRIPTION_FEATURE.md) - Media transcription feature docs
   
## Retrospective Summary
Here's what went well:
   * Successful integration of Gemini 2.0 Flash API for multimodal content processing
   * Smooth migration from traditional RDBMS to Supabase with proper schema design
   * Effective OAuth implementation for Google Drive with secure token management
   * Comprehensive analytics dashboard with meaningful visualizations for instructors
   * Clean project reorganization improving code maintainability and separation of concerns
   * Strong collaboration between frontend and backend teams on API integration
   * Robust error handling and graceful degradation in media transcription pipeline
   * Effective use of Chart.js for real-time data visualization

Here's what we'd like to improve:
    * Increase unit test coverage across all backend and frontend modules
    * Implement continuous integration pipeline for automated testing
    * Optimize Gemini API calls to reduce latency and cost
    * Enhance mobile responsiveness for student and instructor interfaces
    * Add more comprehensive logging and monitoring for production readiness
    * Improve documentation for API endpoints with OpenAPI/Swagger specs
    
Here are changes we plan to implement in the next sprint:
    * Deploy application to production with Nginx reverse proxy and SSL
    * Implement WebSocket support for real-time query streaming
    * Build predictive analytics model for student performance
    * Add mobile app support with React Native or Flutter
    * Integrate NVIDIA DLI coursework materials
    * Implement full end-to-end automated testing suite
    * Add multi-language support for international students
