CREATE TABLE IF NOT EXISTS memory_items (
  namespace VARCHAR(512) NOT NULL,
  item_key VARCHAR(255) NOT NULL,
  value_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY(namespace, item_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS students (
  student_id VARCHAR(128) PRIMARY KEY,
  login_id VARCHAR(255) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(255),
  email VARCHAR(320) UNIQUE,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  CHECK(status IN ('active', 'disabled', 'pending'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS auth_sessions (
  auth_session_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  token_hash VARCHAR(255) NOT NULL UNIQUE,
  expires_at DATETIME(6) NOT NULL,
  revoked_at DATETIME(6),
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_auth_sessions_student FOREIGN KEY(student_id) REFERENCES students(student_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sessions (
  session_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128),
  parent_session_id VARCHAR(128),
  workflow_mode VARCHAR(32) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  learning_goal TEXT,
  input_payload JSON NOT NULL,
  error_message TEXT,
  workflow_version VARCHAR(128) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  completed_at DATETIME(6),
  CONSTRAINT fk_sessions_student FOREIGN KEY(student_id) REFERENCES students(student_id),
  CONSTRAINT fk_sessions_parent FOREIGN KEY(parent_session_id) REFERENCES sessions(session_id),
  CHECK(workflow_mode IN ('auto', 'teach', 'chat', 'diagnose', 'feedback')),
  CHECK(status IN ('running', 'completed', 'failed', 'canceled'))
) ENGINE=InnoDB;

CREATE INDEX ix_sessions_student_time ON sessions(student_id, created_at);
CREATE INDEX ix_sessions_status_time ON sessions(status, updated_at);

CREATE TABLE IF NOT EXISTS session_states (
  session_id VARCHAR(128) PRIMARY KEY,
  state_json JSON NOT NULL,
  revision BIGINT NOT NULL DEFAULT 0,
  updated_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_session_states_session FOREIGN KEY(session_id) REFERENCES sessions(session_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS session_events (
  event_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL,
  sequence_no BIGINT NOT NULL,
  event_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_session_events_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  UNIQUE KEY uq_session_event_sequence(session_id, sequence_no)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS session_checkpoints (
  checkpoint_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL,
  thread_id VARCHAR(128) NOT NULL,
  checkpoint_blob LONGBLOB NOT NULL,
  metadata_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_session_checkpoints_session FOREIGN KEY(session_id) REFERENCES sessions(session_id)
) ENGINE=InnoDB;
CREATE INDEX ix_checkpoints_session_time ON session_checkpoints(session_id, created_at);

CREATE TABLE IF NOT EXISTS rounds (
  round_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL,
  round_number INT NOT NULL,
  integration_attempt INT NOT NULL DEFAULT 1,
  stage VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'running',
  judge_decision VARCHAR(32),
  created_at DATETIME(6) NOT NULL,
  completed_at DATETIME(6),
  CONSTRAINT fk_rounds_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  UNIQUE KEY uq_round_attempt(session_id, round_number, integration_attempt),
  CHECK(status IN ('running', 'completed', 'failed')),
  CHECK(judge_decision IS NULL OR judge_decision IN ('accept', 'accept_with_minor_revision', 'revise'))
) ENGINE=InnoDB;
CREATE INDEX ix_rounds_session ON rounds(session_id, round_number);

CREATE TABLE IF NOT EXISTS student_profiles (
  student_id VARCHAR(128) PRIMARY KEY,
  profile_json JSON NOT NULL,
  knowledge_level VARCHAR(32),
  profile_version INT NOT NULL DEFAULT 1,
  updated_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_student_profiles_student FOREIGN KEY(student_id) REFERENCES students(student_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS profile_history (
  profile_history_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  session_id VARCHAR(128),
  round_id VARCHAR(128),
  source VARCHAR(64) NOT NULL,
  profile_version INT NOT NULL,
  profile_json JSON NOT NULL,
  mastery_snapshot JSON NOT NULL,
  snapshot_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_profile_history_student FOREIGN KEY(student_id) REFERENCES students(student_id),
  CONSTRAINT fk_profile_history_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  CONSTRAINT fk_profile_history_round FOREIGN KEY(round_id) REFERENCES rounds(round_id)
) ENGINE=InnoDB;
CREATE INDEX ix_profile_history_student_time ON profile_history(student_id, snapshot_at);

CREATE TABLE IF NOT EXISTS student_weak_points (
  weak_point_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  weak_text TEXT NOT NULL,
  matched_node_id VARCHAR(128),
  source VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  first_seen_at DATETIME(6) NOT NULL,
  last_seen_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_weak_points_student FOREIGN KEY(student_id) REFERENCES students(student_id),
  CHECK(status IN ('active', 'resolved', 'superseded'))
) ENGINE=InnoDB;
CREATE INDEX ix_weak_points_student_status ON student_weak_points(student_id, status);

CREATE TABLE IF NOT EXISTS student_node_mastery (
  student_id VARCHAR(128) NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  pl DOUBLE NOT NULL DEFAULT 0.15,
  observations INT NOT NULL DEFAULT 0,
  correct_count INT NOT NULL DEFAULT 0,
  incorrect_count INT NOT NULL DEFAULT 0,
  last_attempt_id VARCHAR(128),
  model_version VARCHAR(64) NOT NULL DEFAULT 'bkt-v1',
  updated_at DATETIME(6) NOT NULL,
  PRIMARY KEY(student_id, node_id),
  CONSTRAINT fk_mastery_student FOREIGN KEY(student_id) REFERENCES students(student_id),
  CHECK(pl >= 0 AND pl <= 1),
  CHECK(observations >= 0),
  CHECK(correct_count >= 0),
  CHECK(incorrect_count >= 0)
) ENGINE=InnoDB;
CREATE INDEX ix_mastery_student ON student_node_mastery(student_id);

CREATE TABLE IF NOT EXISTS learning_paths (
  path_item_id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(128) NOT NULL,
  path_version INT NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  node_name VARCHAR(255) NOT NULL,
  prerequisites JSON NOT NULL,
  difficulty_cap VARCHAR(32),
  strategy TEXT,
  order_idx INT NOT NULL,
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_learning_paths_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  UNIQUE KEY uq_learning_path_node(session_id, path_version, node_id),
  UNIQUE KEY uq_learning_path_order(session_id, path_version, order_idx)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS session_directives (
  directive_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL,
  directive_version INT NOT NULL,
  question_scope JSON NOT NULL,
  iteration_directive JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_directives_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  UNIQUE KEY uq_directive_version(session_id, directive_version)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS artifacts (
  artifact_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL,
  round_id VARCHAR(128),
  artifact_kind VARCHAR(64) NOT NULL,
  source_field VARCHAR(64),
  content_path VARCHAR(1024) NOT NULL,
  content_sha256 CHAR(64) NOT NULL,
  created_by VARCHAR(64) NOT NULL,
  title VARCHAR(255),
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_artifacts_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  CONSTRAINT fk_artifacts_round FOREIGN KEY(round_id) REFERENCES rounds(round_id)
) ENGINE=InnoDB;
CREATE INDEX ix_artifacts_session_kind ON artifacts(session_id, artifact_kind);
CREATE INDEX ix_artifacts_round ON artifacts(round_id);

CREATE TABLE IF NOT EXISTS questions (
  question_id VARCHAR(128) PRIMARY KEY,
  session_id VARCHAR(128) NOT NULL,
  round_id VARCHAR(128),
  qid VARCHAR(128) NOT NULL,
  kind VARCHAR(32) NOT NULL,
  category VARCHAR(64),
  difficulty VARCHAR(32),
  question_key VARCHAR(255),
  source_tag VARCHAR(64),
  kc_node_id VARCHAR(128),
  kc VARCHAR(255),
  question_text TEXT NOT NULL,
  answer_json JSON,
  options_json JSON,
  evidence_json JSON,
  question_version VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'published',
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_questions_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  CONSTRAINT fk_questions_round FOREIGN KEY(round_id) REFERENCES rounds(round_id),
  UNIQUE KEY uq_question_qid(session_id, round_id, qid, kind),
  CHECK(kind IN ('interactive', 'assessment')),
  CHECK(status IN ('draft', 'published', 'retired'))
) ENGINE=InnoDB;
CREATE INDEX ix_questions_session_round ON questions(session_id, round_id);
CREATE INDEX ix_questions_key ON questions(question_key);

CREATE TABLE IF NOT EXISTS attempts (
  attempt_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  question_id VARCHAR(128) NOT NULL,
  session_id VARCHAR(128) NOT NULL,
  raw_answer_json JSON NOT NULL,
  selected_option VARCHAR(255),
  is_correct TINYINT(1),
  grading_status VARCHAR(32) NOT NULL DEFAULT 'pending',
  grading_source VARCHAR(64),
  response_ms INT,
  idempotency_key VARCHAR(255) NOT NULL UNIQUE,
  created_at DATETIME(6) NOT NULL,
  graded_at DATETIME(6),
  CONSTRAINT fk_attempts_student FOREIGN KEY(student_id) REFERENCES students(student_id),
  CONSTRAINT fk_attempts_question FOREIGN KEY(question_id) REFERENCES questions(question_id),
  CONSTRAINT fk_attempts_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  CHECK(is_correct IS NULL OR is_correct IN (0, 1)),
  CHECK(grading_status IN ('pending', 'graded', 'ungraded', 'invalid'))
) ENGINE=InnoDB;
CREATE INDEX ix_attempts_student_time ON attempts(student_id, created_at);
CREATE INDEX ix_attempts_question ON attempts(question_id);

CREATE TABLE IF NOT EXISTS onboarding_responses (
  response_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  session_id VARCHAR(128),
  questionnaire_version VARCHAR(64) NOT NULL,
  responses_json JSON NOT NULL,
  submitted_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_onboarding_student FOREIGN KEY(student_id) REFERENCES students(student_id),
  CONSTRAINT fk_onboarding_session FOREIGN KEY(session_id) REFERENCES sessions(session_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS feedback_logs (
  feedback_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  session_id VARCHAR(128) NOT NULL,
  profile_history_id VARCHAR(128),
  evaluation_signals JSON NOT NULL,
  bkt_update JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_feedback_student FOREIGN KEY(student_id) REFERENCES students(student_id),
  CONSTRAINT fk_feedback_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  CONSTRAINT fk_feedback_profile FOREIGN KEY(profile_history_id) REFERENCES profile_history(profile_history_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS legal_citations (
  citation_id VARCHAR(128) PRIMARY KEY,
  article VARCHAR(255) NOT NULL,
  source_name VARCHAR(255),
  source_uri VARCHAR(2048),
  chunk_ref VARCHAR(255),
  retrieval_method VARCHAR(64),
  quote_text TEXT,
  verification_status VARCHAR(32) NOT NULL DEFAULT 'unverified',
  created_at DATETIME(6) NOT NULL,
  CHECK(verification_status IN ('verified', 'unverified', 'rejected'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS artifact_citations (
  artifact_id VARCHAR(128) NOT NULL,
  citation_id VARCHAR(128) NOT NULL,
  field_name VARCHAR(64),
  occurrence INT NOT NULL DEFAULT 1,
  PRIMARY KEY(artifact_id, citation_id, occurrence),
  CONSTRAINT fk_artifact_citations_artifact FOREIGN KEY(artifact_id) REFERENCES artifacts(artifact_id),
  CONSTRAINT fk_artifact_citations_citation FOREIGN KEY(citation_id) REFERENCES legal_citations(citation_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS knowledge_nodes (
  catalog_version VARCHAR(64) NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  node_name VARCHAR(255) NOT NULL,
  prerequisites JSON NOT NULL,
  difficulty_hint VARCHAR(32),
  source_path VARCHAR(1024) NOT NULL,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY(catalog_version, node_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS confusion_pairs (
  catalog_version VARCHAR(64) NOT NULL,
  pair_id VARCHAR(128) NOT NULL,
  concept_a VARCHAR(255) NOT NULL,
  concept_b VARCHAR(255) NOT NULL,
  title VARCHAR(255),
  why_confused TEXT,
  related_nodes JSON NOT NULL,
  PRIMARY KEY(catalog_version, pair_id)
) ENGINE=InnoDB;
