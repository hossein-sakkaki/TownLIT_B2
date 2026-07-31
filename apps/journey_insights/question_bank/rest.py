# apps/journey_insights/question_bank/rest.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="rest_need_001",
        prompt="What kind of rest would be most restorative in your current season?",
        dimension=D.REST,
        secondary_dimensions=[D.PEACE, D.SELF_AWARENESS],
        metadata={"time_context": "current_season", "theme": "rest_type"},
        choices=[
            choice(
                code="physical_rest",
                label="Physical rest and a slower pace",
                base_score=3.31,
                weights={D.REST: 1.22, D.PEACE: 0.71, D.SELF_AWARENESS: 0.52},
            ),
            choice(
                code="mental_space",
                label="Mental space without constant decisions or information",
                base_score=3.38,
                weights={D.REST: 1.16, D.PEACE: 0.86, D.SELF_AWARENESS: 0.61},
            ),
            choice(
                code="relational_safety",
                label="Time with people around whom I do not need to perform",
                base_score=3.45,
                weights={D.REST: 0.96, D.CONNECTION: 1.12, D.PEACE: 0.68},
            ),
            choice(
                code="spiritual_quiet",
                label="Unhurried prayer, worship, or spiritual quiet",
                base_score=3.47,
                weights={D.REST: 1.04, D.FAITH: 1.13, D.PEACE: 0.82},
            ),
        ],
    ),
    question(
        code="rest_resistance_002",
        prompt="What most often makes rest difficult for you?",
        dimension=D.REST,
        secondary_dimensions=[D.SELF_AWARENESS, D.PURPOSE],
        difficulty=3,
        metadata={"time_context": "general_pattern", "theme": "resistance"},
        choices=[
            choice(
                code="unfinished_feeling",
                label="The feeling that I must finish more before I am allowed to stop",
                base_score=3.02,
                weights={D.REST: 0.31, D.SELF_AWARENESS: 1.08, D.PURPOSE: 0.43},
            ),
            choice(
                code="others_need",
                label="Concern that someone else will be disappointed or unsupported",
                base_score=3.08,
                weights={D.REST: 0.36, D.COMPASSION: 0.61, D.SELF_AWARENESS: 0.92},
            ),
            choice(
                code="mind_stays_active",
                label="My body stops, but my mind continues working",
                base_score=3.04,
                weights={D.REST: 0.34, D.PEACE: 0.52, D.SELF_AWARENESS: 1.01},
            ),
            choice(
                code="rest_feels_unproductive",
                label="Rest feels less valuable because its results are not immediate",
                base_score=3.11,
                weights={D.REST: 0.42, D.SELF_AWARENESS: 0.96, D.GROWTH: 0.48},
            ),
        ],
    ),
    question(
        code="rest_boundary_003",
        prompt="Which boundary would most protect healthy rest?",
        dimension=D.REST,
        secondary_dimensions=[D.COURAGE, D.PEACE],
        metadata={"time_context": "forward", "theme": "boundary"},
        choices=[
            choice(
                code="end_time",
                label="A clear time to stop work or responsibility",
                base_score=3.42,
                weights={D.REST: 1.16, D.PEACE: 0.78, D.COURAGE: 0.54},
            ),
            choice(
                code="notification_space",
                label="A period without notifications or incoming requests",
                base_score=3.36,
                weights={D.REST: 1.08, D.PEACE: 0.84, D.SELF_AWARENESS: 0.46},
            ),
            choice(
                code="decline_extra",
                label="Declining one additional commitment",
                base_score=3.47,
                weights={D.REST: 1.14, D.COURAGE: 1.02, D.PURPOSE: 0.59},
            ),
            choice(
                code="ask_shared_load",
                label="Asking someone to share a responsibility",
                base_score=3.44,
                weights={D.REST: 0.96, D.CONNECTION: 1.02, D.COURAGE: 0.72},
            ),
        ],
    ),
    question(
        code="rest_quality_004",
        prompt="Which activity can appear restful but often leaves you less restored?",
        dimension=D.REST,
        secondary_dimensions=[D.SELF_AWARENESS, D.PEACE],
        difficulty=2,
        metadata={"time_context": "general_pattern", "theme": "false_rest"},
        choices=[
            choice(
                code="endless_scrolling",
                label="Consuming information without a clear stopping point",
                base_score=3.04,
                weights={D.REST: 0.37, D.SELF_AWARENESS: 0.91, D.PEACE: 0.32},
            ),
            choice(
                code="avoidance_activity",
                label="Staying busy with easy tasks to avoid an important concern",
                base_score=3.09,
                weights={D.REST: 0.31, D.SELF_AWARENESS: 1.04, D.COURAGE: 0.41},
            ),
            choice(
                code="isolating_too_long",
                label="Withdrawing longer than I actually need",
                base_score=3.01,
                weights={D.REST: 0.35, D.CONNECTION: 0.37, D.SELF_AWARENESS: 0.88},
            ),
            choice(
                code="entertainment_without_attention",
                label="Entertainment I continue even after I stop enjoying it",
                base_score=3.07,
                weights={D.REST: 0.39, D.SELF_AWARENESS: 0.96, D.PEACE: 0.34},
            ),
        ],
    ),
    question(
        code="rest_receive_005",
        prompt="What belief would make it easier to receive rest responsibly?",
        dimension=D.REST,
        secondary_dimensions=[D.FAITH, D.PURPOSE],
        difficulty=3,
        metadata={"time_context": "any", "theme": "belief"},
        choices=[
            choice(
                code="rest_supports_service",
                label="Rest can strengthen my ability to serve responsibly",
                base_score=3.49,
                weights={D.REST: 1.18, D.PURPOSE: 0.91, D.COMPASSION: 0.62},
            ),
            choice(
                code="limit_not_failure",
                label="Having limits is part of being human, not evidence of failure",
                base_score=3.56,
                weights={D.REST: 1.21, D.SELF_AWARENESS: 0.94, D.PEACE: 0.73},
            ),
            choice(
                code="unattended_world",
                label="The world does not depend on my constant attention",
                base_score=3.52,
                weights={D.REST: 1.14, D.PEACE: 1.02, D.FAITH: 0.59},
            ),
            choice(
                code="rhythm_not_reward",
                label="Rest belongs in a healthy rhythm, not only after perfect performance",
                base_score=3.58,
                weights={D.REST: 1.24, D.GROWTH: 0.77, D.PURPOSE: 0.61},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="rest_emotional_006",
        prompt="What kind of emotional rest do you need most in this season?",
        dimension=D.REST,
        secondary_dimensions=[D.PEACE, D.CONNECTION],
        sensitivity=3,
        metadata={"time_context": "current_season", "theme": "emotional_rest"},
        choices=[
            choice(
                code="not_explain_everything",
                label="Space where I do not need to explain or defend everything",
                base_score=3.49,
                weights={D.REST: 1.17, D.PEACE: 0.96, D.SELF_AWARENESS: 0.63},
            ),
            choice(
                code="safe_presence",
                label="The presence of someone with whom I can be emotionally honest",
                base_score=3.56,
                weights={D.REST: 0.98, D.CONNECTION: 1.19, D.PEACE: 0.73},
            ),
            choice(
                code="fewer_decisions",
                label="Relief from carrying too many decisions",
                base_score=3.51,
                weights={D.REST: 1.21, D.PEACE: 0.91, D.PURPOSE: 0.52},
            ),
            choice(
                code="permission_feel",
                label="Permission to feel what I feel without solving it immediately",
                base_score=3.58,
                weights={D.REST: 1.12, D.SELF_AWARENESS: 1.13, D.COMPASSION: 0.69},
            ),
        ],
    ),
    question(
        code="rest_wound_vigilance_007",
        prompt="If past hurt keeps you emotionally alert, what may help your body and mind experience safety?",
        dimension=D.REST,
        secondary_dimensions=[D.PEACE, D.RESILIENCE],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "healing", "theme": "vigilance"},
        choices=[
            choice(
                code="predictable_routine",
                label="A predictable and gentle routine",
                base_score=3.56,
                weights={D.REST: 1.18, D.PEACE: 1.04, D.RESILIENCE: 0.69},
            ),
            choice(
                code="safe_environment",
                label="An environment where boundaries are respected consistently",
                base_score=3.64,
                weights={D.REST: 1.21, D.PEACE: 1.17, D.CONNECTION: 0.72},
            ),
            choice(
                code="trusted_support",
                label="Support from someone who does not pressure me to relax quickly",
                base_score=3.62,
                weights={D.REST: 1.13, D.CONNECTION: 1.18, D.COMPASSION: 0.81},
            ),
            choice(
                code="gradual_body_awareness",
                label="Gradually noticing physical tension without judging it",
                base_score=3.59,
                weights={D.REST: 1.16, D.SELF_AWARENESS: 1.17, D.PEACE: 0.76},
            ),
        ],
    ),
    question(
        code="rest_strength_008",
        prompt="Which ability helps you protect rest more effectively?",
        dimension=D.REST,
        secondary_dimensions=[D.COURAGE, D.SELF_AWARENESS],
        metadata={"time_context": "self_reflection", "theme": "rest_strength"},
        choices=[
            choice(
                code="notice_early_signs",
                label="Noticing signs of exhaustion before they become severe",
                base_score=3.51,
                weights={D.REST: 1.19, D.SELF_AWARENESS: 1.14, D.RESILIENCE: 0.58},
            ),
            choice(
                code="say_no_respectfully",
                label="Saying no respectfully when capacity is limited",
                base_score=3.57,
                weights={D.REST: 1.14, D.COURAGE: 1.18, D.PEACE: 0.63},
            ),
            choice(
                code="enjoy_without_output",
                label="Enjoying something without turning it into achievement",
                base_score=3.54,
                weights={D.REST: 1.23, D.GRATITUDE: 0.94, D.PEACE: 0.71},
            ),
            choice(
                code="ask_share_load",
                label="Asking others to share responsibilities appropriately",
                base_score=3.55,
                weights={D.REST: 1.08, D.CONNECTION: 1.12, D.COURAGE: 0.72},
            ),
        ],
    ),
    question(
        code="rest_guilt_009",
        prompt="Which thought most often creates guilt when you need rest?",
        dimension=D.REST,
        secondary_dimensions=[D.SELF_AWARENESS, D.PURPOSE],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "rest_guilt"},
        choices=[
            choice(
                code="others_working",
                label="Other people are still working, so I should be working too",
                base_score=3.07,
                weights={D.REST: 0.42, D.SELF_AWARENESS: 1.08, D.CONNECTION: 0.38},
            ),
            choice(
                code="unfinished_tasks",
                label="Nothing should remain unfinished when I stop",
                base_score=3.04,
                weights={D.REST: 0.36, D.PURPOSE: 0.51, D.SELF_AWARENESS: 1.12},
            ),
            choice(
                code="worth_productivity",
                label="My value decreases when I am not productive",
                base_score=3.01,
                weights={D.REST: 0.31, D.SELF_AWARENESS: 1.21, D.PEACE: 0.28},
            ),
            choice(
                code="people_disappointed",
                label="Someone may be disappointed if I am less available",
                base_score=3.09,
                weights={D.REST: 0.39, D.CONNECTION: 0.52, D.SELF_AWARENESS: 1.06},
            ),
        ],
    ),
    question(
        code="rest_next_practice_010",
        prompt="Which form of rest could you realistically protect during the next few days?",
        dimension=D.REST,
        secondary_dimensions=[D.PEACE, D.GROWTH],
        metadata={"time_context": "forward", "theme": "realistic_rest"},
        choices=[
            choice(
                code="earlier_stop",
                label="Stop one responsibility earlier than usual",
                base_score=3.47,
                weights={D.REST: 1.16, D.COURAGE: 0.72, D.PEACE: 0.67},
            ),
            choice(
                code="quiet_interval",
                label="Create a short interval without input or notifications",
                base_score=3.51,
                weights={D.REST: 1.21, D.PEACE: 0.94, D.SELF_AWARENESS: 0.51},
            ),
            choice(
                code="restful_connection",
                label="Spend time with someone whose presence is restful",
                base_score=3.53,
                weights={D.REST: 1.04, D.CONNECTION: 1.17, D.PEACE: 0.72},
            ),
            choice(
                code="sleep_preparation",
                label="Protect a simple routine that supports better sleep",
                base_score=3.49,
                weights={D.REST: 1.24, D.GROWTH: 0.76, D.RESILIENCE: 0.54},
            ),
        ],
    ),
]