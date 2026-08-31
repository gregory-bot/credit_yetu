"""ML shadow-scoring: train/evaluate a model on real loan outcomes, then run
it alongside the rule-based score as a monitored, non-authoritative signal.

The rule engine in ``app.services.scoring`` computes ``credit_score``,
``grade`` and the loan limit — that never changes here. This package exists
to honestly answer "would a trained model do better?", using real repayment
outcomes only, once there are enough of them (see ``train.py``). See the
README's "ML shadow-scoring" section for the full rationale.
"""
