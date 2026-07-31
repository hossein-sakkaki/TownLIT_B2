# apps/journey_insights/question_bank/growth.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="growth_edge_001",
        prompt="Which kind of growth feels most relevant in your current season?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.PURPOSE, D.SELF_AWARENESS],
        metadata={"time_context": "current_season", "theme": "growth_area"},
        choices=[
            choice(
                code="deeper_consistency",
                label="Becoming more consistent in something I already understand",
                base_score=3.43,
                weights={D.GROWTH: 1.17, D.RESILIENCE: 0.82, D.PURPOSE: 0.64},
            ),
            choice(
                code="new_skill",
                label="Learning a skill or perspective that is still unfamiliar",
                base_score=3.39,
                weights={D.GROWTH: 1.18, D.COURAGE: 0.68, D.PURPOSE: 0.58},
            ),
            choice(
                code="healthier_limit",
                label="Developing healthier limits around time or responsibility",
                base_score=3.48,
                weights={D.GROWTH: 1.04, D.REST: 1.08, D.SELF_AWARENESS: 0.72},
            ),
            choice(
                code="relational_maturity",
                label="Responding more maturely in an important relationship",
                base_score=3.51,
                weights={D.GROWTH: 1.12, D.CONNECTION: 1.03, D.COMPASSION: 0.63},
            ),
        ],
    ),
    question(
        code="growth_feedback_002",
        prompt="Which kind of feedback is most likely to help you grow?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.SELF_AWARENESS, D.CONNECTION],
        metadata={"time_context": "general_pattern", "theme": "feedback"},
        choices=[
            choice(
                code="specific_behavior",
                label="Feedback tied to a specific behavior or decision",
                base_score=3.42,
                weights={D.GROWTH: 1.11, D.SELF_AWARENESS: 0.93, D.PURPOSE: 0.48},
            ),
            choice(
                code="pattern_over_time",
                label="Someone helping me notice a pattern over time",
                base_score=3.48,
                weights={D.GROWTH: 1.16, D.SELF_AWARENESS: 1.04, D.CONNECTION: 0.54},
            ),
            choice(
                code="challenging_question",
                label="A thoughtful question that I cannot answer immediately",
                base_score=3.46,
                weights={D.GROWTH: 1.19, D.SELF_AWARENESS: 0.86, D.COURAGE: 0.62},
            ),
            choice(
                code="practical_experiment",
                label="A small experiment I can try and evaluate",
                base_score=3.44,
                weights={D.GROWTH: 1.14, D.PURPOSE: 0.91, D.RESILIENCE: 0.57},
            ),
        ],
    ),
    question(
        code="growth_change_003",
        prompt="What makes lasting change more likely for you?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.RESILIENCE, D.PURPOSE],
        difficulty=3,
        metadata={"time_context": "general_pattern", "theme": "change"},
        choices=[
            choice(
                code="small_repeatable",
                label="A small action I can repeat consistently",
                base_score=3.49,
                weights={D.GROWTH: 1.22, D.RESILIENCE: 0.92, D.PURPOSE: 0.68},
            ),
            choice(
                code="clear_reason",
                label="A clear reason that remains meaningful when motivation changes",
                base_score=3.53,
                weights={D.GROWTH: 1.12, D.PURPOSE: 1.16, D.HOPE: 0.53},
            ),
            choice(
                code="support_accountability",
                label="Support from someone who can encourage and challenge me",
                base_score=3.51,
                weights={D.GROWTH: 1.08, D.CONNECTION: 1.13, D.RESILIENCE: 0.62},
            ),
            choice(
                code="review_adjust",
                label="Regular opportunities to review and adjust the approach",
                base_score=3.47,
                weights={D.GROWTH: 1.19, D.SELF_AWARENESS: 0.91, D.RESILIENCE: 0.54},
            ),
        ],
    ),
    question(
        code="growth_discomfort_004",
        prompt="Which kind of discomfort may indicate growth rather than harm?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.COURAGE, D.SELF_AWARENESS],
        difficulty=5,
        metadata={"time_context": "general_pattern", "theme": "discomfort"},
        choices=[
            choice(
                code="beginner_feeling",
                label="Feeling inexperienced while learning something worthwhile",
                base_score=3.42,
                weights={D.GROWTH: 1.16, D.COURAGE: 0.92, D.RESILIENCE: 0.61},
            ),
            choice(
                code="honest_conversation",
                label="The tension of an honest but respectful conversation",
                base_score=3.48,
                weights={D.GROWTH: 1.04, D.COURAGE: 1.08, D.CONNECTION: 0.72},
            ),
            choice(
                code="releasing_pattern",
                label="The unfamiliarity of releasing a long-standing pattern",
                base_score=3.51,
                weights={D.GROWTH: 1.21, D.SELF_AWARENESS: 0.98, D.COURAGE: 0.64},
            ),
            choice(
                code="receiving_correction",
                label="The humility required to receive accurate correction",
                base_score=3.54,
                weights={D.GROWTH: 1.24, D.SELF_AWARENESS: 1.02, D.CONNECTION: 0.58},
            ),
        ],
    ),
    question(
        code="growth_measure_005",
        prompt="Which sign of growth is easiest to miss?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.GRATITUDE, D.RESILIENCE],
        metadata={"time_context": "recent", "theme": "measurement"},
        choices=[
            choice(
                code="faster_recovery",
                label="Recovering more quickly after making a mistake",
                base_score=3.48,
                weights={D.GROWTH: 1.08, D.RESILIENCE: 1.14, D.SELF_AWARENESS: 0.54},
            ),
            choice(
                code="different_question",
                label="Beginning to ask a wiser question than before",
                base_score=3.51,
                weights={D.GROWTH: 1.18, D.SELF_AWARENESS: 1.03, D.PURPOSE: 0.48},
            ),
            choice(
                code="less_reactive",
                label="Having a little more space before reacting",
                base_score=3.53,
                weights={D.GROWTH: 1.11, D.PEACE: 1.04, D.RESILIENCE: 0.62},
            ),
            choice(
                code="accepting_help",
                label="Receiving help earlier instead of waiting until exhaustion",
                base_score=3.49,
                weights={D.GROWTH: 1.02, D.CONNECTION: 0.96, D.REST: 0.74},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="growth_wound_pattern_006",
        prompt="Which old protective pattern may now be limiting your growth?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.SELF_AWARENESS, D.COURAGE],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "healing", "theme": "protective_pattern"},
        choices=[
            choice(
                code="avoid_vulnerability",
                label="Avoiding vulnerability even with trustworthy people",
                base_score=3.11,
                weights={D.GROWTH: 0.62, D.SELF_AWARENESS: 1.18, D.CONNECTION: 0.42},
            ),
            choice(
                code="overcontrol",
                label="Trying to control every detail to prevent disappointment",
                base_score=3.08,
                weights={D.GROWTH: 0.58, D.SELF_AWARENESS: 1.21, D.PEACE: 0.36},
            ),
            choice(
                code="people_pleasing",
                label="Ignoring my limits to avoid rejection or conflict",
                base_score=3.06,
                weights={D.GROWTH: 0.54, D.SELF_AWARENESS: 1.19, D.COURAGE: 0.43},
            ),
            choice(
                code="emotional_distance",
                label="Remaining emotionally distant even when closeness may be safe",
                base_score=3.09,
                weights={D.GROWTH: 0.59, D.CONNECTION: 0.47, D.SELF_AWARENESS: 1.16},
            ),
        ],
    ),
    question(
        code="growth_inner_strength_007",
        prompt="Which inner strength would you like to develop more intentionally?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.COURAGE, D.RESILIENCE],
        metadata={"time_context": "forward", "theme": "inner_strength"},
        choices=[
            choice(
                code="emotional_honesty",
                label="The strength to recognize and express emotions honestly",
                base_score=3.53,
                weights={D.GROWTH: 1.17, D.SELF_AWARENESS: 1.14, D.COURAGE: 0.73},
            ),
            choice(
                code="healthy_patience",
                label="The strength to remain patient without becoming passive",
                base_score=3.56,
                weights={D.GROWTH: 1.13, D.RESILIENCE: 1.08, D.PURPOSE: 0.68},
            ),
            choice(
                code="wise_assertiveness",
                label="The strength to be clear without becoming harsh",
                base_score=3.59,
                weights={D.GROWTH: 1.16, D.COURAGE: 1.17, D.COMPASSION: 0.71},
            ),
            choice(
                code="receive_support",
                label="The strength to receive support without losing dignity",
                base_score=3.57,
                weights={D.GROWTH: 1.08, D.CONNECTION: 1.14, D.RESILIENCE: 0.79},
            ),
        ],
    ),
    question(
        code="growth_painful_feedback_008",
        prompt="What makes painful feedback worth examining rather than immediately rejecting?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.SELF_AWARENESS, D.COURAGE],
        difficulty=5,
        sensitivity=3,
        metadata={"time_context": "after_feedback", "theme": "painful_feedback"},
        choices=[
            choice(
                code="specific_evidence",
                label="It includes specific examples I can examine",
                base_score=3.51,
                weights={D.GROWTH: 1.16, D.SELF_AWARENESS: 1.04, D.PURPOSE: 0.51},
            ),
            choice(
                code="trusted_source",
                label="It comes from someone whose concern and honesty have been consistent",
                base_score=3.54,
                weights={D.GROWTH: 1.09, D.CONNECTION: 1.08, D.SELF_AWARENESS: 0.69},
            ),
            choice(
                code="recognizable_pattern",
                label="It connects with a pattern I have noticed before",
                base_score=3.58,
                weights={D.GROWTH: 1.21, D.SELF_AWARENESS: 1.16, D.COURAGE: 0.61},
            ),
            choice(
                code="actionable_change",
                label="It points toward a responsible and realistic change",
                base_score=3.57,
                weights={D.GROWTH: 1.22, D.PURPOSE: 1.03, D.HOPE: 0.58},
            ),
        ],
    ),
    question(
        code="growth_grief_009",
        prompt="How can growth and grief exist together?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.RESILIENCE, D.COMPASSION],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "loss_or_change", "theme": "growth_and_grief"},
        choices=[
            choice(
                code="learning_not_erasing",
                label="Learning from loss does not erase the value of what was lost",
                base_score=3.66,
                weights={D.GROWTH: 1.16, D.RESILIENCE: 1.09, D.COMPASSION: 0.81},
            ),
            choice(
                code="new_capacity_and_sadness",
                label="New strength can develop while sadness remains real",
                base_score=3.68,
                weights={D.GROWTH: 1.21, D.RESILIENCE: 1.18, D.SELF_AWARENESS: 0.72},
            ),
            choice(
                code="changed_future",
                label="A changed future can still contain meaning without replacing the past",
                base_score=3.69,
                weights={D.GROWTH: 1.17, D.HOPE: 1.21, D.PEACE: 0.74},
            ),
            choice(
                code="healing_not_deadline",
                label="Healing can move forward without obeying a simple deadline",
                base_score=3.67,
                weights={D.GROWTH: 1.12, D.COMPASSION: 1.14, D.RESILIENCE: 0.93},
            ),
        ],
    ),
    question(
        code="growth_next_experiment_010",
        prompt="Which small experiment could teach you something useful about yourself?",
        dimension=D.GROWTH,
        secondary_dimensions=[D.SELF_AWARENESS, D.PURPOSE],
        metadata={"time_context": "forward", "theme": "personal_experiment"},
        choices=[
            choice(
                code="ask_before_assume",
                label="Ask one clarifying question before assuming another person's intent",
                base_score=3.51,
                weights={D.GROWTH: 1.13, D.CONNECTION: 1.04, D.SELF_AWARENESS: 0.71},
            ),
            choice(
                code="pause_before_yes",
                label="Pause before agreeing to a new responsibility",
                base_score=3.54,
                weights={D.GROWTH: 1.09, D.REST: 0.96, D.SELF_AWARENESS: 0.84},
            ),
            choice(
                code="share_need",
                label="Express one need clearly to a trustworthy person",
                base_score=3.57,
                weights={D.GROWTH: 1.12, D.COURAGE: 1.09, D.CONNECTION: 0.83},
            ),
            choice(
                code="review_reaction",
                label="Review one strong reaction before deciding how to act",
                base_score=3.59,
                weights={D.GROWTH: 1.17, D.SELF_AWARENESS: 1.19, D.PEACE: 0.76},
            ),
        ],
    ),
]