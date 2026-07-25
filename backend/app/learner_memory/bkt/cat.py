"""Computerized adaptive testing engine coupled to the BKT tracker."""

from __future__ import annotations

import math
from itertools import product
from typing import Any, Iterable, Mapping

from backend.app.learner_memory.bkt.contracts import DiagnosticQuestion
from backend.app.learner_memory.bkt.knowledge_graph import KnowledgeGraph
from backend.app.learner_memory.bkt.model import BKTStep, BKTTracker


class CATEngine:
    def __init__(
        self,
        questions: Iterable[DiagnosticQuestion],
        tracker: BKTTracker,
        knowledge_graph: KnowledgeGraph,
        *,
        state: Mapping[str, Any] | None = None,
    ) -> None:
        self.questions = {question.id: question for question in questions}
        self.tracker = tracker
        self.knowledge_graph = knowledge_graph
        self.target_leaves = set(knowledge_graph.get_high_weight_leaves())
        self.diagnosis_skills = set(self.target_leaves)
        for leaf in self.target_leaves:
            self.diagnosis_skills.update(self._ancestors(leaf))
        self.pruned_skills = set(state.get("pruned_skills", [])) if state else set()
        self.used_question_ids = set(state.get("used_question_ids", [])) if state else set()
        self.last_skill = str(state.get("last_skill")) if state and state.get("last_skill") else None
        self.consecutive_same_skill = int(state.get("consecutive_same_skill", 0)) if state else 0
        self.max_consecutive = 2
        self.obs_threshold_for_prune = 3
        self.mastery_threshold = 0.9
        self.unmastery_threshold = 0.1
        self.prerequisite_threshold = 0.8
        self.prerequisite_minimum = 0.6
        self.info_gain_minimum = 0.01
        self.max_questions = 40
        self._validate_question_bank()

    def select_next(self) -> DiagnosticQuestion | None:
        candidates: list[DiagnosticQuestion] = []
        threshold = self.prerequisite_threshold
        while threshold >= self.prerequisite_minimum:
            candidates = self._candidates(threshold)
            if candidates:
                break
            threshold = round(threshold - 0.1, 10)
        best_question: DiagnosticQuestion | None = None
        best_score = -1.0
        for question in candidates:
            if (
                self.last_skill in question.skills
                and self.consecutive_same_skill >= self.max_consecutive
            ):
                continue
            information_gain = self.expected_information_gain(question)
            if information_gain < self.info_gain_minimum:
                continue
            score = information_gain * max(
                self.knowledge_graph.get_weight(skill_id) for skill_id in question.skills
            )
            if score > best_score:
                best_score = score
                best_question = question
        return best_question

    def answer_question(
        self,
        question: DiagnosticQuestion,
        *,
        observed_correct: bool,
    ) -> dict[str, Any]:
        if question.id in self.used_question_ids:
            raise ValueError(f"question already answered: {question.id}")
        self.used_question_ids.add(question.id)
        self.tracker.record_answer_event()
        if set(question.skills) == {self.last_skill}:
            self.consecutive_same_skill += 1
        else:
            self.last_skill = question.skills[0]
            self.consecutive_same_skill = 1

        direct_steps: list[BKTStep] = []
        inferred_before = {
            skill_id: self.tracker.get_prob(skill_id)
            for skill_id in self.knowledge_graph.all_node_ids()
        }
        for skill_id in question.skills:
            direct_steps.append(
                self.tracker.update(
                    skill_id,
                    p_guess=question.p_g,
                    p_slip=question.p_s,
                    observed_correct=observed_correct,
                )
            )
            self._apply_inference(skill_id)
        direct_ids = {step.skill_id for step in direct_steps}
        inferred_changes = [
            {
                "skill_id": skill_id,
                "prior_pl": inferred_before[skill_id],
                "posterior_pl": self.tracker.get_prob(skill_id),
                "inferred": True,
            }
            for skill_id in self.knowledge_graph.all_node_ids()
            if skill_id not in direct_ids
            and abs(self.tracker.get_prob(skill_id) - inferred_before[skill_id]) > 1e-12
        ]
        return {
            "direct_steps": [step.model_dump() for step in direct_steps],
            "inferred_changes": inferred_changes,
        }

    def check_terminate(self) -> tuple[bool, str]:
        all_classified = all(
            leaf in self.pruned_skills
            or (
                self.tracker.get_obs_count(leaf) > 0
                and (
                    self.tracker.get_prob(leaf) <= self.unmastery_threshold
                    or self.tracker.get_prob(leaf) >= self.mastery_threshold
                )
            )
            for leaf in self.target_leaves
        )
        if all_classified:
            return True, "所有高权重知识点状态已明确"
        if len(self.used_question_ids) >= self.max_questions:
            return True, "达到最大诊断题数"
        if self.select_next() is None:
            return True, "无满足条件的题目可测"
        return False, "继续诊断"

    def expected_information_gain(self, question: DiagnosticQuestion) -> float:
        if any(skill in self.pruned_skills for skill in question.skills):
            return 0.0
        probabilities = {
            skill_id: self.tracker.get_prob(skill_id) for skill_id in question.skills
        }
        if len(question.skills) > 3:
            return sum(
                self._single_skill_information_gain(
                    skill_id,
                    question.p_g,
                    question.p_s,
                )
                for skill_id in question.skills
            )

        prior_entropy = sum(self._entropy(probabilities[skill]) for skill in question.skills)
        posterior_entropy = 0.0
        for latent_state in product([True, False], repeat=len(question.skills)):
            state_probability = math.prod(
                probabilities[question.skills[index]]
                if mastered
                else 1.0 - probabilities[question.skills[index]]
                for index, mastered in enumerate(latent_state)
            )
            if state_probability == 0:
                continue
            correct_likelihood = math.prod(
                1.0 - question.p_s if mastered else question.p_g
                for mastered in latent_state
            )
            incorrect_likelihood = math.prod(
                question.p_s if mastered else 1.0 - question.p_g
                for mastered in latent_state
            )
            correct_post = self._latent_posteriors(
                question,
                probabilities,
                latent_state,
                observed_correct=True,
            )
            incorrect_post = self._latent_posteriors(
                question,
                probabilities,
                latent_state,
                observed_correct=False,
            )
            posterior_entropy += state_probability * (
                correct_likelihood
                * sum(self._entropy(correct_post[skill]) for skill in question.skills)
                + incorrect_likelihood
                * sum(self._entropy(incorrect_post[skill]) for skill in question.skills)
            )
        return prior_entropy - posterior_entropy

    def state_dict(self) -> dict[str, Any]:
        return {
            "used_question_ids": sorted(self.used_question_ids),
            "pruned_skills": sorted(self.pruned_skills),
            "last_skill": self.last_skill,
            "consecutive_same_skill": self.consecutive_same_skill,
        }

    def _ancestors(self, skill_id: str) -> set[str]:
        ancestors: set[str] = set()
        pending = list(self.knowledge_graph.get_parents(skill_id))
        while pending:
            parent = pending.pop()
            if parent in ancestors:
                continue
            ancestors.add(parent)
            pending.extend(self.knowledge_graph.get_parents(parent))
        return ancestors

    def _update_ancestors(self, skill_id: str) -> None:
        for parent in self.knowledge_graph.get_parents(skill_id):
            children = self.knowledge_graph.get_children(parent)
            total_weight = sum(self.tracker.get_obs_count(child) + 1 for child in children)
            if not total_weight:
                continue
            probability = sum(
                self.tracker.get_prob(child) * (self.tracker.get_obs_count(child) + 1)
                for child in children
            ) / total_weight
            if abs(probability - self.tracker.get_prob(parent)) > 0.01:
                self.tracker.force_set(parent, probability, inferred=True)
                self._update_ancestors(parent)

    def _propagate_unmastered(self, skill_id: str) -> None:
        if skill_id in self.pruned_skills:
            return
        if (
            self.tracker.get_obs_count(skill_id) >= self.obs_threshold_for_prune
            and self.tracker.get_prob(skill_id) <= self.unmastery_threshold
        ):
            self.pruned_skills.add(skill_id)
            self.tracker.force_set(skill_id, 0.01, inferred=True)
            for dependent in self.knowledge_graph.get_dependents(skill_id):
                self._propagate_unmastered(dependent)

    def _apply_inference(self, skill_id: str) -> None:
        if self.tracker.get_prob(skill_id) <= self.unmastery_threshold:
            self._propagate_unmastered(skill_id)
        self._update_ancestors(skill_id)

    def _prerequisites_satisfied(self, skill_id: str, threshold: float) -> bool:
        return all(
            prerequisite not in self.pruned_skills
            and self.tracker.get_prob(prerequisite) >= threshold
            for prerequisite in self.knowledge_graph.get_prerequisites(skill_id)
        )

    def _candidates(self, threshold: float) -> list[DiagnosticQuestion]:
        return [
            question
            for question in self.questions.values()
            if question.id not in self.used_question_ids
            and all(skill in self.diagnosis_skills for skill in question.skills)
            and all(
                self._prerequisites_satisfied(skill, threshold) for skill in question.skills
            )
        ]

    @staticmethod
    def _entropy(probability: float) -> float:
        if probability <= 0.0 or probability >= 1.0:
            return 0.0
        return -probability * math.log2(probability) - (1.0 - probability) * math.log2(
            1.0 - probability
        )

    def _single_skill_information_gain(
        self,
        skill_id: str,
        p_guess: float,
        p_slip: float,
    ) -> float:
        probability = self.tracker.get_prob(skill_id)
        correct_probability = probability * (1.0 - p_slip) + (1.0 - probability) * p_guess
        if correct_probability <= 0.0 or correct_probability >= 1.0:
            return 0.0
        correct_posterior = probability * (1.0 - p_slip) / correct_probability
        incorrect_posterior = (
            probability * p_slip / (1.0 - correct_probability)
            if correct_probability < 1.0
            else probability
        )
        return self._entropy(probability) - (
            correct_probability * self._entropy(correct_posterior)
            + (1.0 - correct_probability) * self._entropy(incorrect_posterior)
        )

    def _latent_posteriors(
        self,
        question: DiagnosticQuestion,
        probabilities: dict[str, float],
        latent_state: tuple[bool, ...],
        *,
        observed_correct: bool,
    ) -> dict[str, float]:
        posteriors: dict[str, float] = {}
        for index, skill_id in enumerate(question.skills):
            mastered = latent_state[index]
            if observed_correct:
                likelihood = 1.0 - question.p_s if mastered else question.p_g
                alternative = question.p_g
            else:
                likelihood = question.p_s if mastered else 1.0 - question.p_g
                alternative = 1.0 - question.p_s
            numerator = probabilities[skill_id] * likelihood
            denominator = numerator + (1.0 - probabilities[skill_id]) * alternative
            posteriors[skill_id] = (
                numerator / denominator if denominator else probabilities[skill_id]
            )
        return posteriors

    def _validate_question_bank(self) -> None:
        unknown = sorted(
            {
                skill_id
                for question in self.questions.values()
                for skill_id in question.skills
                if skill_id not in self.knowledge_graph.nodes
            }
        )
        if unknown:
            raise ValueError(f"question bank references unknown skills: {', '.join(unknown)}")
