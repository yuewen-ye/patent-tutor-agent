-- Persist Planner route provenance and material route identity.
ALTER TABLE learner_learning_plans
  ADD COLUMN route_source VARCHAR(64) NOT NULL DEFAULT 'legacy',
  ADD COLUMN route_fingerprint CHAR(64) NOT NULL DEFAULT '';
CREATE INDEX ix_learner_plans_route_fingerprint
  ON learner_learning_plans(student_id, route_fingerprint);
