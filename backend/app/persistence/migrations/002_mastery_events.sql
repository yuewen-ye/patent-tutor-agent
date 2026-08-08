-- Add source audit column to mastery_events so BKT observations can be
-- attributed to exercise / questionnaire / diagnostic flows.
ALTER TABLE mastery_events
  ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'exercise' AFTER event_kind;
