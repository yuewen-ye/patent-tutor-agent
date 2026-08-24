-- Distinguish feedback-backed teaching completion from legacy mastery-only flags.
ALTER TABLE learner_learning_plan_nodes
  ADD COLUMN completion_session_id VARCHAR(128) NULL,
  ADD CONSTRAINT fk_learner_plan_node_completion_session
    FOREIGN KEY (completion_session_id) REFERENCES sessions(session_id);
UPDATE learner_learning_plan_nodes
SET node_status = 'pending', completed_at = NULL
WHERE node_status = 'completed' AND completion_session_id IS NULL;
CREATE INDEX ix_learner_plan_node_completion_session
  ON learner_learning_plan_nodes(completion_session_id);
