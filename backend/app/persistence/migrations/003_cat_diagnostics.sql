ALTER TABLE questions
  ADD COLUMN skills_json JSON NULL AFTER kc_node_id;

ALTER TABLE mastery_events
  DROP INDEX uq_mastery_event_attempt,
  ADD COLUMN predicted_pl DOUBLE NULL AFTER prior_pl,
  ADD UNIQUE KEY uq_mastery_event_attempt_node(attempt_id, node_id);

CREATE TABLE IF NOT EXISTS diagnostic_sessions (
  diagnostic_session_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  status VARCHAR(32) NOT NULL,
  learning_goal TEXT NOT NULL,
  education_background VARCHAR(255) NOT NULL,
  model_version VARCHAR(64) NOT NULL,
  payload_json JSON NOT NULL,
  created_at DATETIME(6) NOT NULL,
  updated_at DATETIME(6) NOT NULL,
  completed_at DATETIME(6),
  CONSTRAINT fk_diagnostic_sessions_student
    FOREIGN KEY(student_id) REFERENCES students(student_id),
  CHECK(status IN ('running', 'completed'))
) ENGINE=InnoDB;
CREATE INDEX ix_diagnostic_sessions_student_time
  ON diagnostic_sessions(student_id, created_at);

CREATE TABLE IF NOT EXISTS diagnostic_attempts (
  diagnostic_attempt_id VARCHAR(128) PRIMARY KEY,
  diagnostic_session_id VARCHAR(128) NOT NULL,
  student_id VARCHAR(128) NOT NULL,
  question_id VARCHAR(128) NOT NULL,
  skills_json JSON NOT NULL,
  selected_option VARCHAR(32) NOT NULL,
  is_correct TINYINT(1) NOT NULL,
  response_ms INT,
  attempt_json JSON NOT NULL,
  idempotency_key VARCHAR(255),
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_diagnostic_attempts_session
    FOREIGN KEY(diagnostic_session_id)
    REFERENCES diagnostic_sessions(diagnostic_session_id),
  CONSTRAINT fk_diagnostic_attempts_student
    FOREIGN KEY(student_id) REFERENCES students(student_id),
  UNIQUE KEY uq_diagnostic_attempt_order(diagnostic_session_id, question_id),
  UNIQUE KEY uq_diagnostic_attempt_idempotency(diagnostic_session_id, idempotency_key),
  CHECK(is_correct IN (0, 1))
) ENGINE=InnoDB;
CREATE INDEX ix_diagnostic_attempts_student_time
  ON diagnostic_attempts(student_id, created_at);

CREATE TABLE IF NOT EXISTS diagnostic_mastery_events (
  diagnostic_mastery_event_id VARCHAR(128) PRIMARY KEY,
  diagnostic_attempt_id VARCHAR(128) NOT NULL,
  student_id VARCHAR(128) NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  event_type VARCHAR(32) NOT NULL,
  observed_correct TINYINT(1),
  prior_pl DOUBLE NOT NULL,
  predicted_pl DOUBLE,
  posterior_pl DOUBLE NOT NULL,
  p_init DOUBLE,
  p_transit DOUBLE,
  p_guess DOUBLE,
  p_slip DOUBLE,
  model_version VARCHAR(64) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_diagnostic_mastery_attempt
    FOREIGN KEY(diagnostic_attempt_id)
    REFERENCES diagnostic_attempts(diagnostic_attempt_id),
  CONSTRAINT fk_diagnostic_mastery_student
    FOREIGN KEY(student_id) REFERENCES students(student_id),
  UNIQUE KEY uq_diagnostic_mastery_attempt_node(
    diagnostic_attempt_id,
    node_id,
    event_type
  ),
  CHECK(event_type IN ('observed', 'inferred')),
  CHECK(observed_correct IS NULL OR observed_correct IN (0, 1)),
  CHECK(prior_pl >= 0 AND prior_pl <= 1),
  CHECK(posterior_pl >= 0 AND posterior_pl <= 1)
) ENGINE=InnoDB;
CREATE INDEX ix_diagnostic_mastery_student_node_time
  ON diagnostic_mastery_events(student_id, node_id, created_at);
