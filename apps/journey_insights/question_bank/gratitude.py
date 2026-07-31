# apps/journey_insights/question_bank/gratitude.py

from apps.journey_insights.constants import ReflectionDimension
from apps.journey_insights.question_bank.schema import choice, question


D = ReflectionDimension


QUESTIONS = [
    question(
        code="gratitude_attention_001",
        prompt="As you enter this part of your day, what would you most like to notice?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.PEACE, D.CONNECTION],
        is_brand_core=True,
        metadata={"time_context": "day_start", "theme": "attention"},
        choices=[
            choice(
                code="ordinary_good",
                label="The good hidden in ordinary moments",
                base_score=3.24,
                weights={D.GRATITUDE: 1.25, D.PEACE: 0.45, D.SELF_AWARENESS: 0.25},
            ),
            choice(
                code="people_nearby",
                label="The needs and kindness of people around me",
                base_score=3.31,
                weights={D.GRATITUDE: 0.72, D.CONNECTION: 1.12, D.COMPASSION: 0.62},
            ),
            choice(
                code="forward_movement",
                label="Small signs that something is moving forward",
                base_score=3.17,
                weights={D.GRATITUDE: 0.62, D.HOPE: 0.88, D.PURPOSE: 0.66},
            ),
            choice(
                code="inner_response",
                label="How I respond when things do not go as expected",
                base_score=3.08,
                weights={D.GRATITUDE: 0.32, D.SELF_AWARENESS: 1.14, D.RESILIENCE: 0.72},
            ),
        ],
    ),
    question(
        code="gratitude_recent_memory_002",
        prompt="Which kind of recent moment is easiest for you to receive with gratitude?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.CONNECTION, D.PURPOSE],
        metadata={"time_context": "recent", "theme": "memory"},
        choices=[
            choice(
                code="unexpected_help",
                label="Help that arrived when I did not expect it",
                base_score=3.42,
                weights={D.GRATITUDE: 1.32, D.CONNECTION: 0.76, D.HOPE: 0.42},
            ),
            choice(
                code="quiet_progress",
                label="Progress that was small but real",
                base_score=3.18,
                weights={D.GRATITUDE: 0.78, D.PURPOSE: 0.92, D.GROWTH: 0.64},
            ),
            choice(
                code="needed_pause",
                label="A pause that gave me space to breathe",
                base_score=3.26,
                weights={D.GRATITUDE: 0.82, D.REST: 1.02, D.PEACE: 0.66},
            ),
            choice(
                code="new_understanding",
                label="A difficult moment that helped me understand something",
                base_score=3.29,
                weights={D.GRATITUDE: 0.58, D.GROWTH: 1.08, D.SELF_AWARENESS: 0.73},
            ),
        ],
    ),
    question(
        code="gratitude_practice_003",
        prompt="When gratitude does not come naturally, which response feels most honest?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.SELF_AWARENESS, D.FAITH],
        difficulty=3,
        metadata={"time_context": "any", "theme": "honesty"},
        choices=[
            choice(
                code="name_one_thing",
                label="Name one thing I can appreciate without forcing a feeling",
                base_score=3.36,
                weights={D.GRATITUDE: 1.18, D.SELF_AWARENESS: 0.72, D.PEACE: 0.38},
            ),
            choice(
                code="acknowledge_both",
                label="Acknowledge both what is good and what is painful",
                base_score=3.48,
                weights={D.GRATITUDE: 0.72, D.SELF_AWARENESS: 1.16, D.RESILIENCE: 0.74},
            ),
            choice(
                code="borrow_perspective",
                label="Ask someone I trust what they can see that I may be missing",
                base_score=3.27,
                weights={D.GRATITUDE: 0.58, D.CONNECTION: 1.12, D.GROWTH: 0.54},
            ),
            choice(
                code="leave_room",
                label="Leave room for gratitude to grow later rather than pretending now",
                base_score=3.25,
                weights={D.GRATITUDE: 0.46, D.PEACE: 0.71, D.SELF_AWARENESS: 0.92},
            ),
        ],
    ),
    question(
        code="gratitude_receive_004",
        prompt="Which form of goodness do you sometimes overlook most easily?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.CONNECTION, D.REST],
        difficulty=2,
        metadata={"time_context": "any", "theme": "blind_spots"},
        choices=[
            choice(
                code="steady_people",
                label="People who are consistently present",
                base_score=3.14,
                weights={D.GRATITUDE: 0.92, D.CONNECTION: 0.84, D.COMPASSION: 0.31},
            ),
            choice(
                code="ordinary_stability",
                label="Ordinary stability that does not feel dramatic",
                base_score=3.08,
                weights={D.GRATITUDE: 0.98, D.PEACE: 0.72, D.REST: 0.36},
            ),
            choice(
                code="lessons_limits",
                label="Limits that protect me from taking on too much",
                base_score=3.22,
                weights={D.GRATITUDE: 0.64, D.REST: 1.02, D.SELF_AWARENESS: 0.62},
            ),
            choice(
                code="unseen_growth",
                label="Growth that is happening too slowly to notice",
                base_score=3.16,
                weights={D.GRATITUDE: 0.71, D.GROWTH: 1.04, D.HOPE: 0.47},
            ),
        ],
    ),
    question(
        code="gratitude_share_005",
        prompt="What is one way gratitude could become visible through you?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.COMPASSION, D.CONNECTION],
        is_brand_core=True,
        metadata={"time_context": "forward", "theme": "expression"},
        choices=[
            choice(
                code="specific_thanks",
                label="Offer specific thanks instead of a general compliment",
                base_score=3.46,
                weights={D.GRATITUDE: 1.12, D.CONNECTION: 0.96, D.COMPASSION: 0.48},
            ),
            choice(
                code="careful_attention",
                label="Give someone my full attention for a few minutes",
                base_score=3.39,
                weights={D.GRATITUDE: 0.67, D.CONNECTION: 1.08, D.COMPASSION: 0.82},
            ),
            choice(
                code="responsible_use",
                label="Use something I have been given with greater care",
                base_score=3.23,
                weights={D.GRATITUDE: 0.86, D.PURPOSE: 0.74, D.GROWTH: 0.42},
            ),
            choice(
                code="quiet_service",
                label="Do something helpful without needing recognition",
                base_score=3.51,
                weights={D.GRATITUDE: 0.72, D.COMPASSION: 1.18, D.PURPOSE: 0.63},
            ),
        ],
    ),
]


QUESTIONS += [
    question(
        code="gratitude_difficult_season_006",
        prompt="When life feels heavy, which form of gratitude feels most honest rather than forced?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.SELF_AWARENESS, D.HOPE],
        difficulty=4,
        sensitivity=3,
        metadata={"time_context": "difficult_season", "theme": "honest_gratitude"},
        choices=[
            choice(
                code="one_present_good",
                label="Recognizing one good thing without denying what hurts",
                base_score=3.47,
                weights={D.GRATITUDE: 1.18, D.SELF_AWARENESS: 0.94, D.HOPE: 0.52},
            ),
            choice(
                code="support_received",
                label="Remembering the support I have received, even if the problem remains",
                base_score=3.52,
                weights={D.GRATITUDE: 1.09, D.CONNECTION: 1.03, D.RESILIENCE: 0.61},
            ),
            choice(
                code="strength_to_continue",
                label="Acknowledging the strength that has helped me continue this far",
                base_score=3.49,
                weights={D.GRATITUDE: 0.91, D.RESILIENCE: 1.13, D.HOPE: 0.72},
            ),
            choice(
                code="permission_not_ready",
                label="Accepting that I may not be ready for gratitude yet, while remaining open to it",
                base_score=3.44,
                weights={D.GRATITUDE: 0.73, D.SELF_AWARENESS: 1.11, D.PEACE: 0.78},
            ),
        ],
    ),
    question(
        code="gratitude_personal_strength_007",
        prompt="Which strength within you are you learning to appreciate more honestly?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.SELF_AWARENESS, D.GROWTH],
        difficulty=3,
        metadata={"time_context": "current_season", "theme": "inner_strength"},
        choices=[
            choice(
                code="ability_to_endure",
                label="My ability to continue through difficulty",
                base_score=3.43,
                weights={D.GRATITUDE: 0.94, D.RESILIENCE: 1.17, D.SELF_AWARENESS: 0.62},
            ),
            choice(
                code="ability_to_care",
                label="My ability to care about what others are carrying",
                base_score=3.49,
                weights={D.GRATITUDE: 0.89, D.COMPASSION: 1.21, D.CONNECTION: 0.62},
            ),
            choice(
                code="ability_to_learn",
                label="My willingness to learn when I do not have the answer",
                base_score=3.46,
                weights={D.GRATITUDE: 0.83, D.GROWTH: 1.19, D.COURAGE: 0.58},
            ),
            choice(
                code="ability_to_begin_again",
                label="My capacity to begin again after disappointment",
                base_score=3.53,
                weights={D.GRATITUDE: 0.91, D.HOPE: 1.08, D.RESILIENCE: 0.89},
            ),
        ],
    ),
    question(
        code="gratitude_unreceived_008",
        prompt="Which kind of kindness is sometimes difficult for you to receive?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.CONNECTION, D.SELF_AWARENESS],
        difficulty=3,
        sensitivity=2,
        metadata={"time_context": "general_pattern", "theme": "receiving_kindness"},
        choices=[
            choice(
                code="help_without_repayment",
                label="Help I cannot immediately repay",
                base_score=3.12,
                weights={D.GRATITUDE: 0.62, D.CONNECTION: 0.84, D.SELF_AWARENESS: 0.91},
            ),
            choice(
                code="affirmation",
                label="A sincere affirmation about something good in me",
                base_score=3.08,
                weights={D.GRATITUDE: 0.58, D.SELF_AWARENESS: 1.02, D.CONNECTION: 0.54},
            ),
            choice(
                code="patient_presence",
                label="Someone remaining patient when I am struggling",
                base_score=3.17,
                weights={D.GRATITUDE: 0.72, D.CONNECTION: 1.03, D.COMPASSION: 0.61},
            ),
            choice(
                code="forgiveness",
                label="Forgiveness that I know I did not earn",
                base_score=3.21,
                weights={D.GRATITUDE: 0.91, D.FAITH: 0.84, D.SELF_AWARENESS: 0.78},
            ),
        ],
    ),
    question(
        code="gratitude_past_wound_009",
        prompt="What can gratitude contribute when you remember a painful part of your story?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.RESILIENCE, D.SELF_AWARENESS],
        difficulty=5,
        sensitivity=4,
        allow_for_new_users=False,
        minimum_journey_entries=5,
        metadata={"time_context": "past_reflection", "theme": "painful_memory"},
        choices=[
            choice(
                code="honor_survival",
                label="Honor the strength it took to survive or continue",
                base_score=3.51,
                weights={D.GRATITUDE: 0.82, D.RESILIENCE: 1.24, D.SELF_AWARENESS: 0.73},
            ),
            choice(
                code="recognize_helpers",
                label="Recognize people who offered care during or after it",
                base_score=3.47,
                weights={D.GRATITUDE: 1.04, D.CONNECTION: 1.11, D.COMPASSION: 0.51},
            ),
            choice(
                code="notice_growth_without_justifying",
                label="Notice growth that followed without calling the pain good",
                base_score=3.58,
                weights={D.GRATITUDE: 0.91, D.GROWTH: 1.16, D.SELF_AWARENESS: 0.94},
            ),
            choice(
                code="respect_unfinished_healing",
                label="Respect the healing that is still unfinished",
                base_score=3.54,
                weights={D.GRATITUDE: 0.68, D.COMPASSION: 1.06, D.PEACE: 0.92},
            ),
        ],
    ),
    question(
        code="gratitude_future_practice_010",
        prompt="Which simple gratitude practice would feel most natural to continue?",
        dimension=D.GRATITUDE,
        secondary_dimensions=[D.GROWTH, D.PEACE],
        metadata={"time_context": "forward", "theme": "sustainable_practice"},
        choices=[
            choice(
                code="brief_written_note",
                label="Write one specific thing I received or noticed",
                base_score=3.42,
                weights={D.GRATITUDE: 1.18, D.GROWTH: 0.72, D.SELF_AWARENESS: 0.52},
            ),
            choice(
                code="thank_person_directly",
                label="Thank one person directly and specifically",
                base_score=3.49,
                weights={D.GRATITUDE: 1.09, D.CONNECTION: 1.06, D.COMPASSION: 0.42},
            ),
            choice(
                code="pause_before_next",
                label="Pause before moving on from something good",
                base_score=3.45,
                weights={D.GRATITUDE: 1.14, D.PEACE: 0.96, D.REST: 0.54},
            ),
            choice(
                code="remember_in_prayer",
                label="Include gratitude naturally within prayer or reflection",
                base_score=3.52,
                weights={D.GRATITUDE: 1.13, D.FAITH: 1.04, D.PEACE: 0.62},
            ),
        ],
    ),
]