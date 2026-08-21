-- Immutable Planner decisions and plan-version audit trail.

CREATE TABLE IF NOT EXISTS learner_learning_plan_decisions (
  decision_id VARCHAR(128) PRIMARY KEY,
  decision_key VARCHAR(255) NOT NULL,
  student_id VARCHAR(128) NOT NULL,
  session_id VARCHAR(128),
  plan_id VARCHAR(128),
  previous_plan_id VARCHAR(128),
  decision_kind VARCHAR(32) NOT NULL,
  outcome VARCHAR(32) NOT NULL,
  reason_code TEXT,
  learning_goal_hash CHAR(64),
  knowledge_graph_version VARCHAR(64),
  from_plan_version INT,
  to_plan_version INT,
  from_current_node_id VARCHAR(128),
  to_current_node_id VARCHAR(128),
  progress_before_json JSON,
  progress_after_json JSON,
  path_decision_json JSON,
  teaching_context_json JSON,
  created_at DATETIME(6) NOT NULL,
  CONSTRAINT fk_learning_plan_decisions_student FOREIGN KEY(student_id) REFERENCES students(student_id),
  CONSTRAINT fk_learning_plan_decisions_session FOREIGN KEY(session_id) REFERENCES sessions(session_id),
  CONSTRAINT fk_learning_plan_decisions_plan FOREIGN KEY(plan_id) REFERENCES learner_learning_plans(plan_id),
  CONSTRAINT fk_learning_plan_decisions_previous_plan FOREIGN KEY(previous_plan_id) REFERENCES learner_learning_plans(plan_id),
  UNIQUE KEY uq_learning_plan_decision_key(student_id, decision_key),
  CHECK(decision_kind IN ('initial', 'keep', 'replace', 'progress')),
  CHECK(outcome IN ('created', 'kept', 'advanced', 'no_change', 'completed'))
) ENGINE=InnoDB;
CREATE INDEX ix_learning_plan_decisions_student_time
  ON learner_learning_plan_decisions(student_id, created_at);
CREATE INDEX ix_learning_plan_decisions_plan_time
  ON learner_learning_plan_decisions(plan_id, created_at);
CREATE INDEX ix_learning_plan_decisions_session_time
  ON learner_learning_plan_decisions(session_id, created_at);
