"""Bayesian Knowledge Tracing core shared by diagnosis and feedback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from scipy.stats import beta  # type: ignore[import-untyped]

BKT_MODEL_VERSION = "bkt-cat-v1"
DEFAULT_P_G = 0.08
DEFAULT_P_S = 0.05
UNOBSERVED_PL = 0.15
UNOBSERVED_CI = (0.02, 0.40)


@dataclass(frozen=True, slots=True)
class BKTParameters:
    p_init: float
    p_transit: float
    p_guess: float = DEFAULT_P_G
    p_slip: float = DEFAULT_P_S


BACKGROUND_PARAMETERS: dict[str, BKTParameters] = {
    "法学背景+系统学过程序法": BKTParameters(0.40, 0.30),
    "法学背景+未系统学": BKTParameters(0.25, 0.25),
    "理工背景+有研发经验": BKTParameters(0.15, 0.20),
    "理工背景+无研发经验": BKTParameters(0.10, 0.18),
    "其他": BKTParameters(0.10, 0.15),
}


def parameters_for_background(education_background: str) -> BKTParameters:
    normalized = education_background.replace("，", "+").replace(",", "+").replace(" ", "")
    if "法学" in normalized and "系统学过程序法" in normalized:
        key = "法学背景+系统学过程序法"
    elif "法学" in normalized:
        key = "法学背景+未系统学"
    elif "理工" in normalized and "有研发经验" in normalized:
        key = "理工背景+有研发经验"
    elif "理工" in normalized:
        key = "理工背景+无研发经验"
    else:
        key = "其他"
    return BACKGROUND_PARAMETERS[key]


@dataclass(slots=True)
class NodeState:
    pl: float
    p_transit_base: float
    total_count: int = 0
    correct_count: int = 0
    inferred: bool = False


@dataclass(frozen=True, slots=True)
class BKTStep:
    skill_id: str
    observed_correct: bool
    prior_pl: float
    predicted_pl: float
    posterior_pl: float
    p_init: float
    p_transit: float
    p_guess: float
    p_slip: float
    model_version: str = BKT_MODEL_VERSION

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def compute_bkt_step(
    current: float,
    *,
    observed_correct: bool,
    p_transit: float,
    p_guess: float,
    p_slip: float,
) -> tuple[float, float]:
    """Apply the imported model's transition-before-observation update."""

    predicted = current + (1.0 - current) * p_transit
    if observed_correct:
        numerator = predicted * (1.0 - p_slip)
        denominator = numerator + (1.0 - predicted) * p_guess
    else:
        numerator = predicted * p_slip
        denominator = numerator + (1.0 - predicted) * (1.0 - p_guess)
    posterior = numerator / denominator if denominator else predicted
    return predicted, min(1.0, max(0.0, posterior))


class BKTTracker:
    """Stateful BKT tracker with background priors and uncertainty output."""

    def __init__(
        self,
        education_background: str,
        *,
        parameters: BKTParameters | None = None,
        nodes: Mapping[str, Mapping[str, Any]] | None = None,
        global_answer_count: int = 0,
    ) -> None:
        self.education_background = education_background
        self.parameters = parameters or parameters_for_background(education_background)
        self.nodes: dict[str, NodeState] = {}
        self.global_answer_count = global_answer_count
        for skill_id, raw in (nodes or {}).items():
            self.nodes[str(skill_id)] = NodeState(
                pl=float(raw.get("pl", self.parameters.p_init)),
                p_transit_base=float(raw.get("p_transit_base", self.parameters.p_transit)),
                total_count=int(raw.get("total_count", raw.get("observations", 0))),
                correct_count=int(raw.get("correct_count", 0)),
                inferred=bool(raw.get("inferred", False)),
            )

    def get_prob(self, skill_id: str) -> float:
        state = self.nodes.get(skill_id)
        return state.pl if state is not None else self.parameters.p_init

    def get_obs_count(self, skill_id: str) -> int:
        state = self.nodes.get(skill_id)
        return state.total_count if state is not None else 0

    def force_set(self, skill_id: str, probability: float, *, inferred: bool = True) -> None:
        state = self._node(skill_id)
        state.pl = min(1.0, max(0.0, probability))
        state.inferred = inferred

    def record_answer_event(self) -> None:
        self.global_answer_count += 1

    def update(
        self,
        skill_id: str,
        *,
        p_guess: float,
        p_slip: float,
        observed_correct: bool,
    ) -> BKTStep:
        state = self._node(skill_id)
        effective_transit = self._effective_transit(state)
        prior = state.pl
        predicted, posterior = compute_bkt_step(
            prior,
            observed_correct=observed_correct,
            p_transit=effective_transit,
            p_guess=p_guess,
            p_slip=p_slip,
        )
        state.pl = posterior
        state.total_count += 1
        state.correct_count += int(observed_correct)
        state.inferred = False
        return BKTStep(
            skill_id=skill_id,
            observed_correct=observed_correct,
            prior_pl=prior,
            predicted_pl=predicted,
            posterior_pl=posterior,
            p_init=self.parameters.p_init,
            p_transit=effective_transit,
            p_guess=p_guess,
            p_slip=p_slip,
        )

    def knowledge_snapshot(self, all_node_ids: list[str]) -> dict[str, dict[str, Any]]:
        knowledge: dict[str, dict[str, Any]] = {}
        for node_id in all_node_ids:
            state = self.nodes.get(node_id)
            if state is None:
                knowledge[node_id] = {
                    "pl": UNOBSERVED_PL,
                    "ci_low": UNOBSERVED_CI[0],
                    "ci_high": UNOBSERVED_CI[1],
                    "observations": 0,
                    "low_confidence": True,
                    "inferred": False,
                }
                continue
            probability = state.pl
            if state.total_count == 0 and state.inferred:
                ci_low = max(0.0, probability - 0.3)
                ci_high = min(1.0, probability + 0.3)
                low_confidence = True
            elif state.total_count == 0:
                probability = UNOBSERVED_PL
                ci_low, ci_high = UNOBSERVED_CI
                low_confidence = True
            else:
                ci_low, ci_high = self._credible_interval(probability, state.total_count)
                low_confidence = ci_high - ci_low > 0.30
            knowledge[node_id] = {
                "pl": round(probability, 4),
                "ci_low": round(ci_low, 4),
                "ci_high": round(ci_high, 4),
                "observations": state.total_count,
                "low_confidence": low_confidence,
                "inferred": state.inferred,
            }
        return knowledge

    def state_dict(self) -> dict[str, Any]:
        return {
            "education_background": self.education_background,
            "parameters": asdict(self.parameters),
            "global_answer_count": self.global_answer_count,
            "nodes": {
                skill_id: {
                    "pl": state.pl,
                    "p_transit_base": state.p_transit_base,
                    "total_count": state.total_count,
                    "correct_count": state.correct_count,
                    "inferred": state.inferred,
                }
                for skill_id, state in self.nodes.items()
            },
            "model_version": BKT_MODEL_VERSION,
        }

    @classmethod
    def from_state_dict(cls, payload: Mapping[str, Any]) -> "BKTTracker":
        raw_parameters = payload.get("parameters") or {}
        parameters = BKTParameters(
            p_init=float(raw_parameters.get("p_init", UNOBSERVED_PL)),
            p_transit=float(raw_parameters.get("p_transit", 0.25)),
            p_guess=float(raw_parameters.get("p_guess", DEFAULT_P_G)),
            p_slip=float(raw_parameters.get("p_slip", DEFAULT_P_S)),
        )
        return cls(
            str(payload.get("education_background") or "其他"),
            parameters=parameters,
            nodes=payload.get("nodes") if isinstance(payload.get("nodes"), Mapping) else {},
            global_answer_count=int(payload.get("global_answer_count", 0)),
        )

    def _node(self, skill_id: str) -> NodeState:
        if skill_id not in self.nodes:
            self.nodes[skill_id] = NodeState(
                pl=self.parameters.p_init,
                p_transit_base=self.parameters.p_transit,
            )
        return self.nodes[skill_id]

    def _effective_transit(self, state: NodeState) -> float:
        if self.global_answer_count <= 10:
            return min(1.0, state.p_transit_base * 1.5)
        return state.p_transit_base

    @staticmethod
    def _credible_interval(probability: float, observations: int) -> tuple[float, float]:
        alpha = probability * observations + 1.0
        beta_value = (1.0 - probability) * observations + 1.0
        return (
            max(0.0, float(beta.ppf(0.025, alpha, beta_value))),
            min(1.0, float(beta.ppf(0.975, alpha, beta_value))),
        )
