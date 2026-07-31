# apps/journey_insights/question_bank/self_awareness.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="self_awareness_energy_001",
        prompt="What most often changes the quality of your attention?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.REST, D.PEACE],
        metadata={"time_context": "general_pattern", "theme": "attention"},
        choices=[
            choice(
                code="physical_energy",
                label="My physical energy and quality of rest",
                base_score=3.13,
                weights={D.SELF_AWARENESS: 1.08, D.REST: 1.02, D.PEACE: 0.42},
            ),
            choice(
                code="emotional_weight",
                label="An emotional concern that remains unresolved",
                base_score=3.09,
                weights={D.SELF_AWARENESS: 1.12, D.PEACE: 0.46, D.CONNECTION: 0.32},
            ),
            choice(
                code="meaning_clarity",
                label="Whether I understand why the task matters",
                base_score=3.21,
                weights={D.SELF_AWARENESS: 0.91, D.PURPOSE: 1.01, D.GROWTH: 0.42},
            ),
            choice(
                code="environment_pressure",
                label="The pace and interruptions around me",
                base_score=3.04,
                weights={D.SELF_AWARENESS: 0.96, D.PEACE: 0.58, D.REST: 0.51},
            ),
        ],
    ),
    question(
        code="self_awareness_defense_002",
        prompt="When you feel misunderstood, what is your first internal reaction?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.CONNECTION, D.COURAGE],
        difficulty=3,
        metadata={"time_context": "general_pattern", "theme": "defensiveness"},
        choices=[
            choice(
                code="explain_quickly",
                label="I want to explain myself before hearing more",
                base_score=3.01,
                weights={D.SELF_AWARENESS: 0.96, D.CONNECTION: 0.34, D.COURAGE: 0.38},
            ),
            choice(
                code="withdraw",
                label="I become quieter and less willing to engage",
                base_score=2.98,
                weights={D.SELF_AWARENESS: 0.91, D.CONNECTION: 0.31, D.PEACE: 0.37},
            ),
            choice(
                code="question_self",
                label="I begin questioning whether my perspective has value",
                base_score=3.05,
                weights={D.SELF_AWARENESS: 1.04, D.COURAGE: 0.32, D.RESILIENCE: 0.39},
            ),
            choice(
                code="seek_clarity",
                label="I try to identify what may have been heard differently",
                base_score=3.34,
                weights={D.SELF_AWARENESS: 1.13, D.CONNECTION: 0.94, D.GROWTH: 0.62},
            ),
        ],
    ),
    question(
        code="self_awareness_motive_003",
        prompt="Which question best helps you examine your motives?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.PURPOSE, D.FAITH],
        difficulty=4,
        metadata={"time_context": "any", "theme": "motives"},
        choices=[
            choice(
                code="without_recognition",
                label="Would I still consider this worthwhile without recognition?",
                base_score=3.51,
                weights={D.SELF_AWARENESS: 1.18, D.PURPOSE: 1.02, D.FAITH: 0.56},
            ),
            choice(
                code="who_benefits",
                label="Who benefits, and who may carry the cost?",
                base_score=3.54,
                weights={D.SELF_AWARENESS: 1.06, D.COMPASSION: 1.08, D.PURPOSE: 0.71},
            ),
            choice(
                code="fear_or_good",
                label="Am I moving toward what is good or merely away from discomfort?",
                base_score=3.49,
                weights={D.SELF_AWARENESS: 1.21, D.COURAGE: 0.83, D.GROWTH: 0.62},
            ),
            choice(
                code="truthful_story",
                label="What story am I telling myself about why this is necessary?",
                base_score=3.47,
                weights={D.SELF_AWARENESS: 1.24, D.GROWTH: 0.77, D.PEACE: 0.42},
            ),
        ],
    ),
    question(
        code="self_awareness_limit_004",
        prompt="Which sign most clearly tells you that a limit needs attention?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.REST, D.RESILIENCE],
        metadata={"time_context": "general_pattern", "theme": "limits"},
        choices=[
            choice(
                code="less_patience",
                label="My patience becomes noticeably shorter",
                base_score=3.12,
                weights={D.SELF_AWARENESS: 1.08, D.REST: 0.73, D.CONNECTION: 0.42},
            ),
            choice(
                code="simple_tasks_heavy",
                label="Ordinary tasks begin to feel unusually heavy",
                base_score=3.09,
                weights={D.SELF_AWARENESS: 1.04, D.REST: 0.91, D.RESILIENCE: 0.42},
            ),
            choice(
                code="lose_perspective",
                label="Small problems begin to feel like the whole story",
                base_score=3.07,
                weights={D.SELF_AWARENESS: 1.12, D.PEACE: 0.63, D.HOPE: 0.36},
            ),
            choice(
                code="avoid_important",
                label="I repeatedly avoid something important without understanding why",
                base_score=3.15,
                weights={D.SELF_AWARENESS: 1.16, D.COURAGE: 0.61, D.PURPOSE: 0.48},
            ),
        ],
    ),
    question(
        code="self_awareness_feedback_005",
        prompt="What makes feedback easier for you to receive well?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.GROWTH, D.CONNECTION],
        metadata={"time_context": "general_pattern", "theme": "feedback"},
        choices=[
            choice(
                code="specific_examples",
                label="Specific examples rather than broad judgments",
                base_score=3.34,
                weights={D.SELF_AWARENESS: 0.94, D.GROWTH: 0.91, D.CONNECTION: 0.54},
            ),
            choice(
                code="trusted_relationship",
                label="Knowing the person wants my good rather than my embarrassment",
                base_score=3.42,
                weights={D.SELF_AWARENESS: 0.88, D.CONNECTION: 1.08, D.GROWTH: 0.63},
            ),
            choice(
                code="time_to_process",
                label="Having time to process before responding",
                base_score=3.37,
                weights={D.SELF_AWARENESS: 1.03, D.PEACE: 0.71, D.GROWTH: 0.62},
            ),
            choice(
                code="clear_next_step",
                label="Understanding one practical next step instead of receiving only criticism",
                base_score=3.46,
                weights={D.SELF_AWARENESS: 0.91, D.GROWTH: 1.14, D.PURPOSE: 0.66},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="self_awareness_hidden_emotion_006",
        prompt="Which emotion are you most likely to hide beneath productivity or responsibility?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.REST, D.CONNECTION],
        difficulty=4,
        sensitivity=4,
        metadata={"time_context": "general_pattern", "theme": "hidden_emotion"},
        choices=[
            choice(
                code="sadness",
                label="Sadness that I do not know how to express",
                base_score=3.13,
                weights={D.SELF_AWARENESS: 1.19, D.CONNECTION: 0.52, D.REST: 0.58},
            ),
            choice(
                code="fear",
                label="Fear that something important may not work out",
                base_score=3.11,
                weights={D.SELF_AWARENESS: 1.16, D.HOPE: 0.48, D.PEACE: 0.51},
            ),
            choice(
                code="anger",
                label="Anger connected to hurt, unfairness, or crossed limits",
                base_score=3.17,
                weights={D.SELF_AWARENESS: 1.22, D.COURAGE: 0.54, D.PEACE: 0.42},
            ),
            choice(
                code="loneliness",
                label="Loneliness that feels easier to manage by staying busy",
                base_score=3.09,
                weights={D.SELF_AWARENESS: 1.18, D.CONNECTION: 0.61, D.REST: 0.46},
            ),
        ],
    ),
    question(
        code="self_awareness_wound_message_007",
        prompt="Which message can a past wound tempt you to believe about yourself?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.RESILIENCE, D.HOPE],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "past_pattern", "theme": "wound_message"},
        choices=[
            choice(
                code="must_not_need",
                label="I must not need anyone in order to be safe",
                base_score=3.04,
                weights={D.SELF_AWARENESS: 1.21, D.CONNECTION: 0.31, D.RESILIENCE: 0.48},
            ),
            choice(
                code="not_enough",
                label="I will never be enough, regardless of what I do",
                base_score=3.01,
                weights={D.SELF_AWARENESS: 1.23, D.HOPE: 0.24, D.RESILIENCE: 0.39},
            ),
            choice(
                code="always_responsible",
                label="I am responsible for keeping everyone stable",
                base_score=3.07,
                weights={D.SELF_AWARENESS: 1.19, D.REST: 0.32, D.PURPOSE: 0.41},
            ),
            choice(
                code="voice_unsafe",
                label="Speaking honestly will always lead to rejection or harm",
                base_score=3.03,
                weights={D.SELF_AWARENESS: 1.17, D.COURAGE: 0.34, D.CONNECTION: 0.37},
            ),
        ],
    ),
    question(
        code="self_awareness_strength_shadow_008",
        prompt="Which personal strength can become unhelpful when overused?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.GROWTH, D.REST],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "strength_shadow"},
        choices=[
            choice(
                code="responsibility_overcontrol",
                label="Responsibility can become controlling every detail",
                base_score=3.24,
                weights={D.SELF_AWARENESS: 1.14, D.PURPOSE: 0.67, D.PEACE: 0.42},
            ),
            choice(
                code="empathy_overcarry",
                label="Empathy can become carrying emotions that are not mine",
                base_score=3.21,
                weights={D.SELF_AWARENESS: 1.12, D.COMPASSION: 0.72, D.REST: 0.49},
            ),
            choice(
                code="persistence_overexhaustion",
                label="Persistence can become ignoring necessary limits",
                base_score=3.19,
                weights={D.SELF_AWARENESS: 1.16, D.RESILIENCE: 0.68, D.REST: 0.43},
            ),
            choice(
                code="independence_isolation",
                label="Independence can become refusing healthy support",
                base_score=3.17,
                weights={D.SELF_AWARENESS: 1.18, D.CONNECTION: 0.46, D.COURAGE: 0.52},
            ),
        ],
    ),
    question(
        code="self_awareness_body_signal_009",
        prompt="Which physical signal most often tells you that something emotional needs attention?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.REST, D.PEACE],
        sensitivity=2,
        metadata={"time_context": "general_pattern", "theme": "body_awareness"},
        choices=[
            choice(
                code="tightness",
                label="Tightness in my shoulders, chest, jaw, or stomach",
                base_score=3.18,
                weights={D.SELF_AWARENESS: 1.18, D.REST: 0.68, D.PEACE: 0.52},
            ),
            choice(
                code="restlessness",
                label="Restlessness or difficulty remaining still",
                base_score=3.14,
                weights={D.SELF_AWARENESS: 1.12, D.PEACE: 0.57, D.REST: 0.61},
            ),
            choice(
                code="fatigue",
                label="A sudden or persistent sense of fatigue",
                base_score=3.17,
                weights={D.SELF_AWARENESS: 1.16, D.REST: 0.91, D.RESILIENCE: 0.42},
            ),
            choice(
                code="shallow_breath",
                label="My breathing becomes shallow or hurried",
                base_score=3.21,
                weights={D.SELF_AWARENESS: 1.21, D.PEACE: 0.82, D.REST: 0.48},
            ),
        ],
    ),
    question(
        code="self_awareness_inner_need_010",
        prompt="Which inner need would be most useful for you to acknowledge more clearly?",
        dimension=D.SELF_AWARENESS,
        secondary_dimensions=[D.CONNECTION, D.REST],
        difficulty=3,
        metadata={"time_context": "current_season", "theme": "inner_need"},
        choices=[
            choice(
                code="need_safety",
                label="The need to feel emotionally or relationally safe",
                base_score=3.34,
                weights={D.SELF_AWARENESS: 1.16, D.CONNECTION: 0.81, D.PEACE: 0.68},
            ),
            choice(
                code="need_belonging",
                label="The need to belong without constant performance",
                base_score=3.39,
                weights={D.SELF_AWARENESS: 1.11, D.CONNECTION: 1.14, D.REST: 0.56},
            ),
            choice(
                code="need_meaning",
                label="The need to know that my effort has meaningful direction",
                base_score=3.37,
                weights={D.SELF_AWARENESS: 1.04, D.PURPOSE: 1.18, D.HOPE: 0.54},
            ),
            choice(
                code="need_recovery",
                label="The need for recovery before taking on more",
                base_score=3.42,
                weights={D.SELF_AWARENESS: 1.08, D.REST: 1.22, D.PEACE: 0.62},
            ),
        ],
    ),
]