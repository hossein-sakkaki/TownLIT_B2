# apps/journey_insights/question_bank/resilience.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="resilience_recovery_001",
        prompt="What most helps you recover after an emotionally demanding moment?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.REST, D.CONNECTION],
        metadata={"time_context": "general_pattern", "theme": "recovery"},
        choices=[
            choice(
                code="quiet_space",
                label="Enough quiet to understand what I am carrying",
                base_score=3.35,
                weights={D.RESILIENCE: 0.92, D.REST: 1.04, D.SELF_AWARENESS: 0.78},
            ),
            choice(
                code="trusted_conversation",
                label="A conversation with someone who can listen without rushing me",
                base_score=3.47,
                weights={D.RESILIENCE: 0.94, D.CONNECTION: 1.17, D.COMPASSION: 0.64},
            ),
            choice(
                code="practical_action",
                label="One practical action that restores a sense of movement",
                base_score=3.39,
                weights={D.RESILIENCE: 1.08, D.PURPOSE: 0.81, D.HOPE: 0.62},
            ),
            choice(
                code="prayer_perspective",
                label="Prayer or reflection that helps restore perspective",
                base_score=3.49,
                weights={D.RESILIENCE: 1.02, D.FAITH: 1.08, D.PEACE: 0.73},
            ),
        ],
    ),
    question(
        code="resilience_setback_002",
        prompt="What is the most useful question after a setback?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.GROWTH, D.PURPOSE],
        difficulty=3,
        metadata={"time_context": "after_event", "theme": "setback"},
        choices=[
            choice(
                code="what_remains",
                label="What remains possible from here?",
                base_score=3.45,
                weights={D.RESILIENCE: 1.16, D.HOPE: 1.08, D.PURPOSE: 0.54},
            ),
            choice(
                code="what_learn",
                label="What information did this reveal that I did not have before?",
                base_score=3.47,
                weights={D.RESILIENCE: 0.94, D.GROWTH: 1.19, D.SELF_AWARENESS: 0.61},
            ),
            choice(
                code="what_repair",
                label="What needs repair before I move forward?",
                base_score=3.51,
                weights={D.RESILIENCE: 1.02, D.CONNECTION: 0.84, D.COURAGE: 0.72},
            ),
            choice(
                code="what_release",
                label="What expectation may need to change?",
                base_score=3.43,
                weights={D.RESILIENCE: 0.98, D.PEACE: 0.82, D.SELF_AWARENESS: 0.78},
            ),
        ],
    ),
    question(
        code="resilience_pressure_003",
        prompt="Under pressure, which strength are you most likely to overuse?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.SELF_AWARENESS, D.REST],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "overused_strength"},
        choices=[
            choice(
                code="independence",
                label="Independence becomes carrying everything alone",
                base_score=3.08,
                weights={D.RESILIENCE: 0.52, D.SELF_AWARENESS: 1.08, D.CONNECTION: 0.31},
            ),
            choice(
                code="persistence",
                label="Persistence becomes refusing needed rest",
                base_score=3.11,
                weights={D.RESILIENCE: 0.61, D.SELF_AWARENESS: 1.02, D.REST: 0.36},
            ),
            choice(
                code="care_for_others",
                label="Care for others becomes neglecting my real limits",
                base_score=3.14,
                weights={D.RESILIENCE: 0.55, D.COMPASSION: 0.67, D.SELF_AWARENESS: 1.03},
            ),
            choice(
                code="planning",
                label="Planning becomes trying to remove every uncertainty",
                base_score=3.05,
                weights={D.RESILIENCE: 0.48, D.SELF_AWARENESS: 1.07, D.PEACE: 0.32},
            ),
        ],
    ),
    question(
        code="resilience_support_004",
        prompt="Which form of support makes perseverance more sustainable?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.CONNECTION, D.HOPE],
        metadata={"time_context": "general_pattern", "theme": "support"},
        choices=[
            choice(
                code="consistent_check_in",
                label="Someone checking in consistently rather than only once",
                base_score=3.46,
                weights={D.RESILIENCE: 1.03, D.CONNECTION: 1.12, D.HOPE: 0.52},
            ),
            choice(
                code="shared_responsibility",
                label="A responsibility being shared in a clear way",
                base_score=3.49,
                weights={D.RESILIENCE: 1.08, D.CONNECTION: 0.94, D.PURPOSE: 0.68},
            ),
            choice(
                code="honest_encouragement",
                label="Encouragement that acknowledges difficulty instead of minimizing it",
                base_score=3.53,
                weights={D.RESILIENCE: 1.12, D.HOPE: 1.02, D.COMPASSION: 0.66},
            ),
            choice(
                code="permission_adjust",
                label="Permission to adjust the plan without abandoning the goal",
                base_score=3.51,
                weights={D.RESILIENCE: 1.18, D.GROWTH: 0.86, D.PEACE: 0.62},
            ),
        ],
    ),
    question(
        code="resilience_identity_005",
        prompt="Which reminder best protects your identity during a difficult season?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.HOPE, D.FAITH],
        difficulty=4,
        metadata={"time_context": "season", "theme": "identity"},
        choices=[
            choice(
                code="season_not_whole",
                label="This season is real, but it is not the whole of my story",
                base_score=3.56,
                weights={D.RESILIENCE: 1.22, D.HOPE: 1.08, D.SELF_AWARENESS: 0.58},
            ),
            choice(
                code="worth_not_output",
                label="My worth is not measured only by what I can produce",
                base_score=3.58,
                weights={D.RESILIENCE: 1.11, D.REST: 0.92, D.FAITH: 0.76},
            ),
            choice(
                code="help_not_failure",
                label="Receiving help does not erase responsibility or dignity",
                base_score=3.54,
                weights={D.RESILIENCE: 1.06, D.CONNECTION: 1.03, D.COURAGE: 0.63},
            ),
            choice(
                code="change_possible",
                label="A pattern can be deeply established without being unchangeable",
                base_score=3.52,
                weights={D.RESILIENCE: 1.14, D.HOPE: 1.02, D.GROWTH: 0.72},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="resilience_wound_response_006",
        prompt="When a wound affects the way you react, what supports a healthier response?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.SELF_AWARENESS, D.PEACE],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "healing", "theme": "wound_response"},
        choices=[
            choice(
                code="notice_before_action",
                label="Notice the reaction before deciding what it means or requires",
                base_score=3.59,
                weights={D.RESILIENCE: 1.08, D.SELF_AWARENESS: 1.23, D.PEACE: 0.79},
            ),
            choice(
                code="identify_present_difference",
                label="Identify how the present situation differs from the earlier harm",
                base_score=3.62,
                weights={D.RESILIENCE: 1.19, D.SELF_AWARENESS: 1.08, D.HOPE: 0.66},
            ),
            choice(
                code="choose_safe_support",
                label="Choose support that respects both my dignity and my limits",
                base_score=3.64,
                weights={D.RESILIENCE: 1.14, D.CONNECTION: 1.16, D.COURAGE: 0.71},
            ),
            choice(
                code="allow_slow_change",
                label="Allow the pattern to change gradually rather than demanding instant healing",
                base_score=3.66,
                weights={D.RESILIENCE: 1.24, D.COMPASSION: 1.02, D.GROWTH: 0.83},
            ),
        ],
    ),
    question(
        code="resilience_existing_strength_007",
        prompt="Which strength has helped you survive or navigate difficult seasons?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.GRATITUDE, D.SELF_AWARENESS],
        metadata={"time_context": "life_reflection", "theme": "survival_strength"},
        choices=[
            choice(
                code="adaptability",
                label="The ability to adjust when circumstances change",
                base_score=3.51,
                weights={D.RESILIENCE: 1.21, D.GROWTH: 0.93, D.GRATITUDE: 0.52},
            ),
            choice(
                code="persistence",
                label="The ability to continue when progress is slow",
                base_score=3.48,
                weights={D.RESILIENCE: 1.24, D.PURPOSE: 0.81, D.HOPE: 0.61},
            ),
            choice(
                code="seeking_support",
                label="The ability to recognize when I need support",
                base_score=3.57,
                weights={D.RESILIENCE: 1.12, D.CONNECTION: 1.16, D.COURAGE: 0.72},
            ),
            choice(
                code="meaning_making",
                label="The ability to find responsible meaning without denying pain",
                base_score=3.61,
                weights={D.RESILIENCE: 1.19, D.PURPOSE: 1.03, D.SELF_AWARENESS: 0.82},
            ),
        ],
    ),
    question(
        code="resilience_breaking_point_008",
        prompt="Which sign most clearly tells you that perseverance needs to become adjustment?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.REST, D.SELF_AWARENESS],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "adjustment"},
        choices=[
            choice(
                code="repeated_harm",
                label="The same approach repeatedly causes preventable harm",
                base_score=3.41,
                weights={D.RESILIENCE: 0.91, D.SELF_AWARENESS: 1.08, D.COURAGE: 0.72},
            ),
            choice(
                code="values_compromised",
                label="Continuing requires me to compromise important values",
                base_score=3.54,
                weights={D.RESILIENCE: 0.98, D.PURPOSE: 1.19, D.COURAGE: 0.83},
            ),
            choice(
                code="body_warning",
                label="My body or mind is giving persistent warning signs",
                base_score=3.49,
                weights={D.RESILIENCE: 0.94, D.REST: 1.17, D.SELF_AWARENESS: 0.91},
            ),
            choice(
                code="goal_method_confused",
                label="I am protecting the method even though the deeper goal could remain",
                base_score=3.52,
                weights={D.RESILIENCE: 1.08, D.GROWTH: 1.14, D.PURPOSE: 0.76},
            ),
        ],
    ),
    question(
        code="resilience_after_rejection_009",
        prompt="What helps you recover when something important is rejected?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.HOPE, D.SELF_AWARENESS],
        difficulty=4,
        sensitivity=3,
        metadata={"time_context": "after_rejection", "theme": "rejection"},
        choices=[
            choice(
                code="separate_work_identity",
                label="Separate the rejected work or request from my whole identity",
                base_score=3.59,
                weights={D.RESILIENCE: 1.19, D.SELF_AWARENESS: 1.11, D.PEACE: 0.72},
            ),
            choice(
                code="learn_feedback",
                label="Consider whether the rejection contains useful information",
                base_score=3.51,
                weights={D.RESILIENCE: 1.04, D.GROWTH: 1.13, D.COURAGE: 0.62},
            ),
            choice(
                code="receive_encouragement",
                label="Receive encouragement from people who understand the effort",
                base_score=3.48,
                weights={D.RESILIENCE: 1.01, D.CONNECTION: 1.09, D.HOPE: 0.71},
            ),
            choice(
                code="choose_next_path",
                label="Decide whether to revise, try elsewhere, wait, or release it",
                base_score=3.61,
                weights={D.RESILIENCE: 1.21, D.PURPOSE: 1.07, D.HOPE: 0.68},
            ),
        ],
    ),
    question(
        code="resilience_future_support_010",
        prompt="What would make your resilience more sustainable in the coming season?",
        dimension=D.RESILIENCE,
        secondary_dimensions=[D.REST, D.CONNECTION],
        metadata={"time_context": "forward", "theme": "sustainable_resilience"},
        choices=[
            choice(
                code="stronger_rhythm",
                label="A more reliable rhythm of effort and recovery",
                base_score=3.57,
                weights={D.RESILIENCE: 1.14, D.REST: 1.18, D.PURPOSE: 0.62},
            ),
            choice(
                code="earlier_support",
                label="Seeking support earlier rather than at the point of exhaustion",
                base_score=3.61,
                weights={D.RESILIENCE: 1.17, D.CONNECTION: 1.14, D.COURAGE: 0.73},
            ),
            choice(
                code="clearer_limits",
                label="Clearer limits around what I am responsible to carry",
                base_score=3.59,
                weights={D.RESILIENCE: 1.08, D.REST: 1.09, D.SELF_AWARENESS: 0.91},
            ),
            choice(
                code="meaningful_reminder",
                label="A clear reminder of why the effort matters",
                base_score=3.55,
                weights={D.RESILIENCE: 1.13, D.PURPOSE: 1.17, D.HOPE: 0.67},
            ),
        ],
    ),
]