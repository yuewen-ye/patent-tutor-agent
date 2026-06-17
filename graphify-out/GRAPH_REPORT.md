# Graph Report - .  (2026-06-17)

## Corpus Check
- Corpus is ~41,424 words - fits in a single context window. You may not need a graph.

## Summary
- 625 nodes · 917 edges · 65 communities (42 shown, 23 thin omitted)
- Extraction: 70% EXTRACTED · 30% INFERRED · 0% AMBIGUOUS · INFERRED: 273 edges (avg confidence: 0.69)
- Token cost: 28,500 input · 3,200 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Agent Node Implementations|Agent Node Implementations]]
- [[_COMMUNITY_State & Contract Models|State & Contract Models]]
- [[_COMMUNITY_Workflow Orchestration Core|Workflow Orchestration Core]]
- [[_COMMUNITY_LLM Provider Routing|LLM Provider Routing]]
- [[_COMMUNITY_Agent Node Assembly|Agent Node Assembly]]
- [[_COMMUNITY_Expert & Service Layer|Expert & Service Layer]]
- [[_COMMUNITY_Service & Protocol Layer|Service & Protocol Layer]]
- [[_COMMUNITY_Chat & Diagnosis Pipeline|Chat & Diagnosis Pipeline]]
- [[_COMMUNITY_API & Agent Construction|API & Agent Construction]]
- [[_COMMUNITY_FastAPI Routes|FastAPI Routes]]
- [[_COMMUNITY_Agent System Prompts|Agent System Prompts]]
- [[_COMMUNITY_Patent Law Concepts|Patent Law Concepts]]
- [[_COMMUNITY_Artifact Persistence|Artifact Persistence]]
- [[_COMMUNITY_Agent Common Helpers|Agent Common Helpers]]
- [[_COMMUNITY_Agent Packages|Agent Packages]]
- [[_COMMUNITY_Session Manifest A|Session Manifest A]]
- [[_COMMUNITY_Session Manifest B|Session Manifest B]]
- [[_COMMUNITY_Debate & Review Patterns|Debate & Review Patterns]]
- [[_COMMUNITY_Learner Memory Helpers|Learner Memory Helpers]]
- [[_COMMUNITY_Cross-Cutting System|Cross-Cutting System]]
- [[_COMMUNITY_CLI Workflow Runner|CLI Workflow Runner]]
- [[_COMMUNITY_Fake LLM Clients|Fake LLM Clients]]
- [[_COMMUNITY_Mock RAG References|Mock RAG References]]
- [[_COMMUNITY_LangGraph Config|LangGraph Config]]
- [[_COMMUNITY_Test Fake Variants|Test Fake Variants]]
- [[_COMMUNITY_Dev Environment|Dev Environment]]
- [[_COMMUNITY_LLM Normalization|LLM Normalization]]
- [[_COMMUNITY_Dev Tooling|Dev Tooling]]
- [[_COMMUNITY_Diagnosis Package|Diagnosis Package]]
- [[_COMMUNITY_Expert A Package|Expert A Package]]
- [[_COMMUNITY_Expert B Package|Expert B Package]]
- [[_COMMUNITY_LangGraph Studio Entry|LangGraph Studio Entry]]
- [[_COMMUNITY_RAG Module|RAG Module]]
- [[_COMMUNITY_Feedback Package|Feedback Package]]
- [[_COMMUNITY_Planner Package|Planner Package]]
- [[_COMMUNITY_Service Layer Package|Service Layer Package]]
- [[_COMMUNITY_Contract Models|Contract Models]]
- [[_COMMUNITY_RAG Architecture Target|RAG Architecture Target]]
- [[_COMMUNITY_Error Handling|Error Handling]]
- [[_COMMUNITY_Diagnosis README|Diagnosis README]]
- [[_COMMUNITY_Planner README|Planner README]]
- [[_COMMUNITY_Expert A README|Expert A README]]
- [[_COMMUNITY_Expert B README|Expert B README]]
- [[_COMMUNITY_Judge README|Judge README]]
- [[_COMMUNITY_LLMMessage Type|LLMMessage Type]]
- [[_COMMUNITY_ToolDefinition Type|ToolDefinition Type]]
- [[_COMMUNITY_LLMResponseWithTools Type|LLMResponseWithTools Type]]
- [[_COMMUNITY_FastAPI App Entry|FastAPI App Entry]]
- [[_COMMUNITY_LangGraph Studio Entry|LangGraph Studio Entry]]
- [[_COMMUNITY_Test Helpers|Test Helpers]]
- [[_COMMUNITY_Session API Tests|Session API Tests]]

## God Nodes (most connected - your core abstractions)
1. `LLMMessage` - 27 edges
2. `LLMResponseWithTools` - 22 edges
3. `ContractModel` - 21 edges
4. `SessionService` - 20 edges
5. `AgentLLMRouter` - 20 edges
6. `FakeLLMClient` - 17 edges
7. `ToolCall` - 17 edges
8. `ToolDefinition` - 17 edges
9. `DefaultLLMClient` - 13 edges
10. `build_agent_nodes()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `InMemorySaver Checkpointer` --semantically_similar_to--> `SqliteSaver Checkpointer`  [INFERRED] [semantically similar]
  AGENTS.md → docs/memory-persistence.md
- `InMemoryStore` --semantically_similar_to--> `SqliteStore`  [INFERRED] [semantically similar]
  AGENTS.md → docs/memory-persistence.md
- `LearnerProfile (Current 5-Field)` --semantically_similar_to--> `Five-Dimensional Learner Profile (P0.3 Target)`  [INFERRED] [semantically similar]
  AGENTS.md → docs/agent-interface-spec.md
- `Full Workflow Integration Test` --conceptually_related_to--> `Debate Quality Assessment System`  [INFERRED]
  backend/tests/integration/test_workflow_integration.py → artifacts/sessions/local-real-debug/round-02/feedback_report.md
- `Three-Route Workflow (teach/chat/diagnose)` --conceptually_related_to--> `Debate Quality Assessment System`  [INFERRED]
  backend/tests/integration/test_three_routes_integration.py → artifacts/sessions/local-real-debug/round-02/feedback_report.md

## Hyperedges (group relationships)
- **Debate Loop: Parallel Expert Generation + Judge Evaluation + Revision Cycle** — AGENTSMD_fan_out_experts, AGENTSMD_expert_a_node, AGENTSMD_expert_b_node, AGENTSMD_judge_node, AGENTSMD_revise_experts [EXTRACTED 1.00]
- **Three-Route Workflow: Route + Teach/Chat/Diagnose Paths** — AGENTSMD_route_node, DOCS_IMPLEMENTATION_three_route_workflow, AGENTSMD_diagnosis_node, AGENTSMD_planner_node, AGENTSMD_tool_agent_node, AGENTSMD_chat_answer_node [EXTRACTED 1.00]
- **RAG Pipeline: Chunking + Embedding + Hybrid Retrieval + Reranking** — DOCS_RAG_SELECTION_semantic_chunking, DOCS_RAG_SELECTION_bge_m3, DOCS_RAG_SPEC_hybrid_retrieval, DOCS_RAG_SELECTION_bge_reranker, DOCS_RAG_SELECTION_milvus_lite, AGENTSMD_rag_retrieve, AGENTSMD_retrieval_chunk [EXTRACTED 1.00]
- **Teach Path Workflow Pipeline** — agents_route_node, agents_diagnosis_node, agents_planner_node, agents_expert_a_node, agents_expert_b_node, agents_judge_node [INFERRED 0.80]
- **Common Helper Function Users** — agents_diagnosis_node, agents_planner_node, agents_expert_a_node, agents_expert_b_node, agents_judge_node [EXTRACTED 1.00]
- **Teach Path Workflow** — feedback_buildFeedbackNode, finalize_buildFinalizeNode, schemas_ExpertDraft, schemas_JudgeReport, schemas_FinalAnswer, schemas_FeedbackResult, graph_reviseExpertsNode, graph_fanOutExpertsNode, graph_buildWorkflow [EXTRACTED 1.00]
- **LLM Client Protocol Hierarchy** — llm_LLMClient, llm_DefaultLLMClient, llm_AgentLLMRouter, llm_callLlmJson, llm_callLlmTools [EXTRACTED 1.00]
- **API Service Pipeline** — api_createApiRouter, api_createSessionsRouter, api_createEventsRouter, api_createArtifactsRouter, services_SessionService, services_SessionEventBridge, graph_arunWorkflow [EXTRACTED 1.00]
- **Deterministic Testing Framework** — queue_llm_client, debate_queue_llm_client, memory_queue_llm_client, fake_llm_client, fake_llm_testing_strategy [INFERRED 0.80]
- **LLM Output Normalization Layer** — camelcase_normalization, judge_normalization, planner_nodeid_normalization [INFERRED 0.70]
- **Mock RAG Legal Reference** — rag_retrieve, mock_rag_chunks, patent_law_novelty_utility, patent_law_unpatentable, patent_law_priority [EXTRACTED 0.90]
- **Patent Novelty vs Inventiveness Teaching Core** — final_answer_NoveltyPrinciple, final_answer_InventivenessPrinciple, expert_b_draft_SoleComparison, expert_b_draft_CombinationComparison, judge_report_ThreeStepMethod, judge_report_ConflictingApplication, expert_a_draft_GracePeriod, retrieval_context_MockRAGRetrieval [EXTRACTED 1.00]
- **Workflow Testing Architecture** — test_workflow_integration_FullWorkflow, test_memory_integration_CrossSessionMemory, test_three_routes_RouteWorkflow, test_providers_ProviderRouting, test_schema_extensions_ContractModels, test_run_workflow_CLI, manifest_ArtifactPersistenceSystem [EXTRACTED 1.00]

## Communities (65 total, 23 thin omitted)

### Community 0 - "Agent Node Implementations"
Cohesion: 0.05
Nodes (44): build_chat_answer_node(), Chat answer node: generates a direct answer from tool_agent context., call_llm(), DefaultLLMClient, LLMMessage, LLMResponseWithTools, Adapter used when all Agent nodes should use one provider., A tool call requested by the LLM. (+36 more)

### Community 1 - "State & Contract Models"
Cohesion: 0.06
Nodes (39): revise_experts_node(), rag_retrieve(), RAG retriever — currently a mock, ready for real vector/hybrid retrieval., Retrieve patent law knowledge chunks for a given query.      Currently returns m, # TODO: Replace with real retrieval (embedding + vector search / BM25 / hybrid), agent_output_json_schemas(), AgentEvent, AttackRelation (+31 more)

### Community 2 - "Workflow Orchestration Core"
Cohesion: 0.05
Nodes (35): arun_workflow(), build_workflow(), export_workflow_mermaid(), _fan_out_experts_node(), _print_summary(), LangGraph workflow for the real five-Agent system., Pass-through node that triggers parallel expert_a + expert_b., Print a one-line summary of an agent node's output. (+27 more)

### Community 3 - "LLM Provider Routing"
Cohesion: 0.07
Nodes (32): AgentLLMRouter, _build_chat_body(), _build_chat_body_with_tools(), call_llm_json(), call_llm_tools(), from_env(), LLMConfigurationError, LLMProviderConfig (+24 more)

### Community 4 - "Agent Node Assembly"
Cohesion: 0.06
Nodes (26): schema_note(), build_agent_nodes(), Agent node assembly for the LangGraph workflow., build_diagnosis_node(), Diagnosis Agent node., build_expert_a_node(), build_expert_b_node(), build_feedback_node() (+18 more)

### Community 5 - "Expert & Service Layer"
Cohesion: 0.07
Nodes (36): Artifact Persistence Layer (_with_runtime_side_effects), SessionEventBridge, Expert A Node (Conservative Precise), Expert B Node (Vivid Flexible), ExpertDraft ContractModel, Fan-Out Experts (Parallel Pass-Through), FastAPI Service Layer, Feedback Node (Questionnaire + Profile) (+28 more)

### Community 6 - "Service & Protocol Layer"
Cohesion: 0.09
Nodes (14): LLMClient, Generate and parse a JSON response from a chat model., Generate a response with tool-calling capability. Does NOT use json_mode., Protocol, Thread-safe bridge from workflow AgentEvents to HTTP stream consumers., SessionEventBridge, _Subscriber, _compact_state() (+6 more)

### Community 7 - "Chat & Diagnosis Pipeline"
Cohesion: 0.08
Nodes (31): AgentLLMRouter, ChatAnswer ContractModel, Chat Answer Node (Quick Response), DeepSeek LLM Provider, DefaultLLMClient, Diagnosis Node (Learner Profiling), GLM LLM Provider, IntentResult ContractModel (+23 more)

### Community 8 - "API & Agent Construction"
Cohesion: 0.09
Nodes (31): create_api_router, create_artifacts_router, create_events_router, create_sessions_router, build_chat_answer_node, Debate Loop Pattern, build_feedback_node, build_finalize_node (+23 more)

### Community 9 - "FastAPI Routes"
Cohesion: 0.08
Nodes (20): create_artifacts_router(), Artifact retrieval endpoints., create_events_router(), _format_sse(), SSE and WebSocket event endpoints., _sse_events(), create_api_router(), FastAPI routers for sessionized workflow access. (+12 more)

### Community 10 - "Agent System Prompts"
Cohesion: 0.18
Nodes (21): Agent Common Helpers, Diagnosis Node, Diagnosis System Prompt, Expert A Node, Expert A System Prompt, Expert B Node, Expert B System Prompt, Judge Node (+13 more)

### Community 11 - "Patent Law Concepts"
Cohesion: 0.13
Nodes (17): Absolute Novelty Standard, Grace Period (宽限期, Art 24), Combination Comparison Principle (组合对比), Sole Comparison Principle (单独对比), Debate Quality Assessment System, Patent Inventiveness Principle, Patent Novelty Principle, Conflicting Application (抵触申请) (+9 more)

### Community 12 - "Artifact Persistence"
Cohesion: 0.35
Nodes (9): _artifact_absolute_path(), _artifact_relative_path(), _dict_markdown(), _list_markdown(), _markdown_for(), Markdown artifact persistence for workflow runs., sanitize_session_id(), write_field_artifact() (+1 more)

### Community 13 - "Agent Common Helpers"
Cohesion: 0.29
Nodes (6): _chat_role(), messages_from_prompt(), normalize_key_aliases(), Shared helpers for Agent node modules., Map known provider key variants to the internal contract field names., test_messages_from_prompt_maps_langchain_roles_to_chat_api_roles()

### Community 14 - "Agent Packages"
Cohesion: 0.29
Nodes (7): Diagnosis Package, Expert A Package, Expert B Package, Agent Node Assembly, Judge Package, Planner Package, Route Package

### Community 15 - "Session Manifest A"
Cohesion: 0.29
Nodes (6): artifacts, debate_round, max_debate_rounds, session_id, status, updated_at

### Community 16 - "Session Manifest B"
Cohesion: 0.29
Nodes (6): artifacts, debate_round, max_debate_rounds, session_id, status, updated_at

### Community 17 - "Debate & Review Patterns"
Cohesion: 0.33
Nodes (6): AGM Belief Revision Theory, Debate Loop Pattern, Cross Review (Four-Category Marking), Expert Collaboration Chain (P0.1 Target), Joint Synthesis (A+B Collaborative Merge), Lightweight Review (Changed Paragraphs Only)

### Community 18 - "Learner Memory Helpers"
Cohesion: 0.6
Nodes (5): _learner_id(), learner_namespace(), load_profile_memories(), LangGraph Store helpers for learner memory., save_learner_memories()

### Community 19 - "Cross-Cutting System"
Cohesion: 0.33
Nodes (6): Artifact persistence system, Artifact round scoping, Cross-session learner memory, Learner memory helpers, Workflow CLI runner, Workflow Mermaid exporter

### Community 20 - "CLI Workflow Runner"
Cohesion: 0.4
Nodes (4): main(), Run the current workflow with configured real LLM providers., summary_lines(), test_summary_lines_render_concise_workflow_result()

### Community 21 - "Fake LLM Clients"
Cohesion: 0.7
Nodes (5): DebateQueueLLMClient, FakeLLMClient, Fake LLM testing strategy, MemoryQueueLLMClient, QueueLLMClient

### Community 22 - "Mock RAG References"
Cohesion: 0.4
Nodes (5): Mock RAG chunks, Patent Law Article 22 Novelty Inventiveness Utility, Patent Law Article 29 Priority Rights, Patent Law Article 25 Unpatentable Subject Matter, RAG retrieve function

### Community 23 - "LangGraph Config"
Cohesion: 0.4
Nodes (4): dependencies, graphs, patent-tutor, python_version

### Community 24 - "Test Fake Variants"
Cohesion: 0.5
Nodes (4): DebateQueueLLMClient (Test Fake), FakeLLMClient (Test Fake), MemoryQueueLLMClient (Test Fake), QueueLLMClient (Test Fake)

### Community 25 - "Dev Environment"
Cohesion: 0.5
Nodes (3): PYTHONUTF8, UV_CACHE_DIR, UV_PYTHON_INSTALL_DIR

### Community 28 - "LLM Normalization"
Cohesion: 0.67
Nodes (3): CamelCase key normalization, Judge output normalization, Planner node ID slug normalization

### Community 29 - "Dev Tooling"
Cohesion: 0.67
Nodes (3): LangGraph Dev Launch Script, LangGraph Studio Configuration, Project Structure Verification

## Knowledge Gaps
- **176 isolated node(s):** `python_version`, `dependencies`, `patent-tutor`, `session_id`, `status` (+171 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **23 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `LLMMessage` connect `Agent Node Implementations` to `Workflow Orchestration Core`, `LLM Provider Routing`, `Agent Node Assembly`, `FastAPI Routes`, `Agent Common Helpers`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `SessionService` connect `Service & Protocol Layer` to `FastAPI Routes`, `LLM Provider Routing`, `State & Contract Models`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `StateDict` connect `State & Contract Models` to `Agent Node Assembly`, `Service & Protocol Layer`?**
  _High betweenness centrality (0.091) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `LLMMessage` (e.g. with `QueueLLMClient` and `CamelCaseExpertLLMClient`) actually correct?**
  _`LLMMessage` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `LLMResponseWithTools` (e.g. with `QueueLLMClient` and `TestToolCallDataclass`) actually correct?**
  _`LLMResponseWithTools` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `SessionService` (e.g. with `QueueLLMClient` and `AgentLLMRouter`) actually correct?**
  _`SessionService` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `AgentLLMRouter` (e.g. with `TestTeachRoute` and `TestChatRoute`) actually correct?**
  _`AgentLLMRouter` has 14 INFERRED edges - model-reasoned connections that need verification._