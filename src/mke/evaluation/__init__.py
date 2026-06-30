from typing import TYPE_CHECKING

from mke.evaluation.chinese_report import (
    render_chinese_retrieval_human,
    render_chinese_retrieval_json,
)
from mke.evaluation.chinese_runner import run_chinese_retrieval_evaluation
from mke.evaluation.cjk_lexical_comparison import (
    render_cjk_lexical_comparison_human,
    render_cjk_lexical_comparison_json,
    run_cjk_lexical_comparison,
)
from mke.evaluation.dense_artifact import validate_dense_comparison_artifact
from mke.evaluation.dense_candidate import (
    DenseCandidateError,
    run_dense_candidate_partition,
    run_dense_development_candidate,
)
from mke.evaluation.dense_workflow import run_dense_evaluation_phase
from mke.evaluation.manifest import (
    FixtureValidationError,
    ManifestValidationError,
    RetrievalEvaluationManifest,
    load_retrieval_manifest,
    snapshot_retrieval_fixtures,
)
from mke.evaluation.numeric_comparison import (
    render_numeric_comparison_human,
    render_numeric_comparison_json,
    run_numeric_comparison,
)
from mke.evaluation.report import (
    render_retrieval_human_report,
    render_retrieval_json_report,
)
from mke.evaluation.runner import run_retrieval_evaluation

if TYPE_CHECKING:
    from mke.evaluation.dense_replay import validate_dense_cache_replay


def __getattr__(name: str) -> object:
    if name == "validate_dense_cache_replay":
        from mke.evaluation.dense_replay import validate_dense_cache_replay

        return validate_dense_cache_replay
    raise AttributeError(name)


__all__ = [
    "FixtureValidationError",
    "ManifestValidationError",
    "RetrievalEvaluationManifest",
    "DenseCandidateError",
    "validate_dense_comparison_artifact",
    "validate_dense_cache_replay",
    "load_retrieval_manifest",
    "render_chinese_retrieval_human",
    "render_chinese_retrieval_json",
    "render_cjk_lexical_comparison_human",
    "render_cjk_lexical_comparison_json",
    "render_numeric_comparison_human",
    "render_numeric_comparison_json",
    "render_retrieval_human_report",
    "render_retrieval_json_report",
    "run_numeric_comparison",
    "run_chinese_retrieval_evaluation",
    "run_cjk_lexical_comparison",
    "run_dense_candidate_partition",
    "run_dense_development_candidate",
    "run_dense_evaluation_phase",
    "run_retrieval_evaluation",
    "snapshot_retrieval_fixtures",
]
