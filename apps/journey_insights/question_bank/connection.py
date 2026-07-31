# apps/journey_insights/question_bank/connection.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="connection_presence_001",
        prompt="What helps you feel genuinely present with another person?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.COMPASSION, D.PEACE],
        metadata={"time_context": "general_pattern", "theme": "presence"},
        choices=[
            choice(
                code="curious_questions",
                label="Asking questions without preparing my next reply",
                base_score=3.45,
                weights={D.CONNECTION: 1.18, D.COMPASSION: 0.84, D.SELF_AWARENESS: 0.53},
            ),
            choice(
                code="shared_activity",
                label="Doing something meaningful together",
                base_score=3.32,
                weights={D.CONNECTION: 1.03, D.PURPOSE: 0.72, D.GRATITUDE: 0.49},
            ),
            choice(
                code="honest_vulnerability",
                label="Sharing something honest without demanding a solution",
                base_score=3.49,
                weights={D.CONNECTION: 1.12, D.COURAGE: 0.91, D.SELF_AWARENESS: 0.68},
            ),
            choice(
                code="unhurried_time",
                label="Having enough time that the conversation does not feel rushed",
                base_score=3.39,
                weights={D.CONNECTION: 0.96, D.PEACE: 0.81, D.REST: 0.62},
            ),
        ],
    ),
    question(
        code="connection_repair_002",
        prompt="What is usually the most important first step when a relationship feels strained?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.COURAGE, D.PEACE],
        difficulty=4,
        sensitivity=2,
        metadata={"time_context": "general_pattern", "theme": "repair"},
        choices=[
            choice(
                code="examine_part",
                label="Examine my own part before explaining theirs",
                base_score=3.52,
                weights={D.CONNECTION: 1.02, D.SELF_AWARENESS: 1.12, D.COURAGE: 0.58},
            ),
            choice(
                code="clarify_hurt",
                label="Name the hurt clearly without exaggerating it",
                base_score=3.47,
                weights={D.CONNECTION: 0.96, D.COURAGE: 1.08, D.PEACE: 0.62},
            ),
            choice(
                code="understand_context",
                label="Try to understand what the other person may have experienced",
                base_score=3.49,
                weights={D.CONNECTION: 1.11, D.COMPASSION: 1.03, D.PEACE: 0.51},
            ),
            choice(
                code="choose_timing",
                label="Choose a time when both people can respond thoughtfully",
                base_score=3.38,
                weights={D.CONNECTION: 0.88, D.PEACE: 0.96, D.SELF_AWARENESS: 0.54},
            ),
        ],
    ),
    question(
        code="connection_receive_003",
        prompt="Which kind of support is hardest for you to receive?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.SELF_AWARENESS, D.COURAGE],
        difficulty=3,
        metadata={"time_context": "general_pattern", "theme": "receiving"},
        choices=[
            choice(
                code="practical_help",
                label="Practical help with something I believe I should manage myself",
                base_score=3.02,
                weights={D.CONNECTION: 0.48, D.SELF_AWARENESS: 0.91, D.COURAGE: 0.53},
            ),
            choice(
                code="emotional_presence",
                label="Someone staying close when I do not have clear words",
                base_score=3.08,
                weights={D.CONNECTION: 0.62, D.SELF_AWARENESS: 0.83, D.COMPASSION: 0.44},
            ),
            choice(
                code="honest_correction",
                label="Correction from someone who genuinely cares for me",
                base_score=3.13,
                weights={D.CONNECTION: 0.55, D.GROWTH: 0.98, D.SELF_AWARENESS: 0.72},
            ),
            choice(
                code="patient_time",
                label="Someone giving time when I cannot return the same support immediately",
                base_score=3.05,
                weights={D.CONNECTION: 0.71, D.GRATITUDE: 0.54, D.SELF_AWARENESS: 0.66},
            ),
        ],
    ),
    question(
        code="connection_boundaries_004",
        prompt="What makes a relational boundary loving rather than merely distant?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.COMPASSION, D.COURAGE],
        difficulty=4,
        metadata={"time_context": "general_pattern", "theme": "boundaries"},
        choices=[
            choice(
                code="clear_reason",
                label="Its purpose is clear and connected to what is healthy",
                base_score=3.42,
                weights={D.CONNECTION: 0.82, D.SELF_AWARENESS: 0.94, D.PEACE: 0.71},
            ),
            choice(
                code="respectful_words",
                label="It is communicated without humiliation or threat",
                base_score=3.53,
                weights={D.CONNECTION: 1.03, D.COMPASSION: 1.08, D.COURAGE: 0.63},
            ),
            choice(
                code="consistent_action",
                label="It is practiced consistently rather than used as punishment",
                base_score=3.49,
                weights={D.CONNECTION: 0.96, D.COURAGE: 0.92, D.RESILIENCE: 0.61},
            ),
            choice(
                code="room_for_good",
                label="It still leaves room for appropriate respect and goodwill",
                base_score=3.46,
                weights={D.CONNECTION: 1.04, D.COMPASSION: 0.86, D.PEACE: 0.64},
            ),
        ],
    ),
    question(
        code="connection_initiative_005",
        prompt="Which relational step would be most meaningful for you to take soon?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.COURAGE, D.COMPASSION],
        metadata={"time_context": "forward", "theme": "initiative"},
        choices=[
            choice(
                code="thank_someone",
                label="Thank someone for something specific they may not realize mattered",
                base_score=3.47,
                weights={D.CONNECTION: 1.02, D.GRATITUDE: 1.08, D.COMPASSION: 0.54},
            ),
            choice(
                code="check_in",
                label="Check in with someone without waiting for a crisis",
                base_score=3.44,
                weights={D.CONNECTION: 1.12, D.COMPASSION: 0.93, D.HOPE: 0.44},
            ),
            choice(
                code="clarify_misunderstanding",
                label="Clarify a misunderstanding before it grows",
                base_score=3.48,
                weights={D.CONNECTION: 1.03, D.COURAGE: 1.02, D.PEACE: 0.59},
            ),
            choice(
                code="ask_for_support",
                label="Ask for support in a way that is clear and respectful",
                base_score=3.41,
                weights={D.CONNECTION: 1.01, D.COURAGE: 0.91, D.SELF_AWARENESS: 0.62},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="connection_loneliness_006",
        prompt="When you feel lonely, which kind of connection would be most meaningful?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.SELF_AWARENESS, D.HOPE],
        difficulty=3,
        sensitivity=3,
        metadata={"time_context": "current_need", "theme": "loneliness"},
        choices=[
            choice(
                code="safe_conversation",
                label="One honest conversation where I do not need to appear strong",
                base_score=3.54,
                weights={D.CONNECTION: 1.22, D.SELF_AWARENESS: 0.91, D.COURAGE: 0.72},
            ),
            choice(
                code="shared_activity_no_pressure",
                label="A shared activity without pressure to explain everything",
                base_score=3.43,
                weights={D.CONNECTION: 1.08, D.PEACE: 0.76, D.REST: 0.61},
            ),
            choice(
                code="community_belonging",
                label="A community where I can participate consistently over time",
                base_score=3.51,
                weights={D.CONNECTION: 1.19, D.RESILIENCE: 0.72, D.HOPE: 0.68},
            ),
            choice(
                code="offer_connection",
                label="Reach toward someone else who may also feel alone",
                base_score=3.49,
                weights={D.CONNECTION: 1.11, D.COMPASSION: 1.08, D.COURAGE: 0.58},
            ),
        ],
    ),
    question(
        code="connection_relational_wound_007",
        prompt="What helps you remain open to connection after trust has been hurt?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.COURAGE, D.RESILIENCE],
        difficulty=5,
        sensitivity=5,
        allow_for_new_users=False,
        minimum_journey_entries=8,
        metadata={"time_context": "relational_healing", "theme": "trust_wound"},
        choices=[
            choice(
                code="safe_small_steps",
                label="Begin with small and observable steps rather than immediate vulnerability",
                base_score=3.59,
                weights={D.CONNECTION: 1.06, D.COURAGE: 1.03, D.RESILIENCE: 0.91},
            ),
            choice(
                code="recognize_safe_people",
                label="Learn to recognize people who respect limits and consistency",
                base_score=3.63,
                weights={D.CONNECTION: 1.19, D.SELF_AWARENESS: 1.04, D.PEACE: 0.76},
            ),
            choice(
                code="keep_boundary_and_openness",
                label="Maintain wise boundaries without deciding that everyone is unsafe",
                base_score=3.66,
                weights={D.CONNECTION: 1.14, D.COURAGE: 1.12, D.HOPE: 0.71},
            ),
            choice(
                code="process_with_support",
                label="Process the hurt with someone who will not pressure me to move too quickly",
                base_score=3.61,
                weights={D.CONNECTION: 1.08, D.COMPASSION: 1.13, D.PEACE: 0.82},
            ),
        ],
    ),
    question(
        code="connection_seen_008",
        prompt="What helps you feel truly seen rather than merely noticed?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.COMPASSION, D.SELF_AWARENESS],
        metadata={"time_context": "general_pattern", "theme": "being_seen"},
        choices=[
            choice(
                code="remember_details",
                label="Someone remembers details that mattered to me",
                base_score=3.47,
                weights={D.CONNECTION: 1.18, D.COMPASSION: 0.83, D.GRATITUDE: 0.52},
            ),
            choice(
                code="questions_beneath_surface",
                label="Someone asks questions that go beyond the surface",
                base_score=3.53,
                weights={D.CONNECTION: 1.21, D.SELF_AWARENESS: 0.84, D.COURAGE: 0.46},
            ),
            choice(
                code="accepted_without_performance",
                label="I am welcomed without needing to impress or perform",
                base_score=3.59,
                weights={D.CONNECTION: 1.24, D.PEACE: 0.94, D.REST: 0.67},
            ),
            choice(
                code="truthful_care",
                label="Someone can affirm me and still speak truthfully",
                base_score=3.57,
                weights={D.CONNECTION: 1.19, D.GROWTH: 0.96, D.COMPASSION: 0.76},
            ),
        ],
    ),
    question(
        code="connection_strength_009",
        prompt="Which relational strength do you bring most naturally?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.COMPASSION, D.GRATITUDE],
        metadata={"time_context": "self_reflection", "theme": "relational_strength"},
        choices=[
            choice(
                code="make_space",
                label="I make space for people to speak honestly",
                base_score=3.48,
                weights={D.CONNECTION: 1.14, D.COMPASSION: 1.08, D.PEACE: 0.57},
            ),
            choice(
                code="bring_energy",
                label="I bring encouragement and energy into shared spaces",
                base_score=3.43,
                weights={D.CONNECTION: 1.09, D.HOPE: 1.04, D.GRATITUDE: 0.52},
            ),
            choice(
                code="stay_reliable",
                label="I remain reliable when a relationship requires consistency",
                base_score=3.51,
                weights={D.CONNECTION: 1.17, D.RESILIENCE: 0.91, D.PURPOSE: 0.63},
            ),
            choice(
                code="help_repair",
                label="I am willing to help repair misunderstandings",
                base_score=3.55,
                weights={D.CONNECTION: 1.21, D.COURAGE: 0.94, D.PEACE: 0.69},
            ),
        ],
    ),
    question(
        code="connection_need_expression_010",
        prompt="Which need is hardest for you to express clearly in relationships?",
        dimension=D.CONNECTION,
        secondary_dimensions=[D.SELF_AWARENESS, D.COURAGE],
        difficulty=4,
        sensitivity=3,
        metadata={"time_context": "general_pattern", "theme": "expressing_needs"},
        choices=[
            choice(
                code="need_rest",
                label="The need for space or rest",
                base_score=3.11,
                weights={D.CONNECTION: 0.58, D.REST: 0.91, D.SELF_AWARENESS: 0.86},
            ),
            choice(
                code="need_reassurance",
                label="The need for reassurance or emotional presence",
                base_score=3.08,
                weights={D.CONNECTION: 0.71, D.SELF_AWARENESS: 0.91, D.COURAGE: 0.52},
            ),
            choice(
                code="need_clarity",
                label="The need for clarity about expectations or commitment",
                base_score=3.17,
                weights={D.CONNECTION: 0.78, D.COURAGE: 0.84, D.PEACE: 0.62},
            ),
            choice(
                code="need_help",
                label="The need for practical help before I become overwhelmed",
                base_score=3.14,
                weights={D.CONNECTION: 0.73, D.COURAGE: 0.91, D.REST: 0.66},
            ),
        ],
    ),
]
