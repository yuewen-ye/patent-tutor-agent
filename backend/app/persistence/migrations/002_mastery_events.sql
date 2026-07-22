CREATE TABLE IF NOT EXISTS mastery_events (
  mastery_event_id VARCHAR(128) PRIMARY KEY,
  student_id VARCHAR(128) NOT NULL,
  node_id VARCHAR(128) NOT NULL,
  attempt_id VARCHAR(128),
  observed_correct TINYINT(1) NOT NULL,
  prior_pl DOUBLE NOT NULL,
  posterior_pl DOUBLE NOT NULL,
  updated_pl DOUBLE NOT NULL,
  p_init DOUBLE NOT NULL,
  p_transit DOUBLE NOT NULL,
  p_guess DOUBLE NOT NULL,
  p_slip DOUBLE NOT NULL,
  model_version VARCHAR(64) NOT NULL,
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_mastery_events_student
    FOREIGN KEY(student_id) REFERENCES students(student_id),
  CONSTRAINT fk_mastery_events_attempt
    FOREIGN KEY(attempt_id) REFERENCES attempts(attempt_id),
  UNIQUE KEY uq_mastery_event_attempt(attempt_id),
  KEY ix_mastery_events_student_node_time(student_id, node_id, created_at),
  CHECK(observed_correct IN (0, 1)),
  CHECK(prior_pl >= 0 AND prior_pl <= 1),
  CHECK(posterior_pl >= 0 AND posterior_pl <= 1),
  CHECK(updated_pl >= 0 AND updated_pl <= 1)
) ENGINE=InnoDB;
